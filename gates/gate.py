#!/usr/bin/env python3
"""Computational gates for the backend and frontend teams.

    gate.py profile                      draft <project>/.claude/gates.json (user confirms it)
    gate.py p1                           after Phase 1 (requirements)
    gate.py p2                           after Phase 2 (design + fixture answers); writes the Plan review sheet
    gate.py fixtures-approve --by <who>  lock the fixtures the user approved at Plan (never without their yes;
                                         --by orchestrator --because "<newer decision>" re-locks what it replaced)
    gate.py baseline                     Phase 4 start: clean tree, baseline tests, snapshot
    gate.py mark --role <agent>          snapshot before dispatching a writing agent or reviewers
    gate.py p4 | p5 | p6 | p7            gates after build, verification, review, acceptance
    gate.py log <event> [--agent --model --step --status --stop --decision --by --note]
                                         append to the run log (dispatch | return | human | decision);
                                         the hooks log dispatches and returns, so by hand only what they missed
    gate.py log void --seq <n> --by <who> --note "<why>"
                                         void a wrong entry (the log is append-only; the gates skip it)
    gate.py timeline                     write <run-dir>/run-log.md and print it

Frontend team (run dir docs/frontend; pass --team frontend to baseline, mark, log, timeline):
    gate.py fe-product | fe-ux | fe-ui | fe-queue | fe-plan
    gate.py fe-approve --by <who>        lock the queue's observables and frame exports confirmed at the Prototype stop
    gate.py fe-build | fe-capture-plan | fe-verify | fe-review | fe-accept
    gate.py log return ... --figma-calls <n>   record the Figma calls an agent reported (PLAYBOOK §1E)
    gate.py log dispatch ... --figma-left <n>  calls left, required for fe-ux / fe-ui / fe-engineer when the run has a budget
    gate.py fe-promote --by <who> [--exclude Q-…]   after Acceptance: register accepted rows as OBS-###
    gate.py fe-approve --by <who> [--retire OBS-…]  also retires registered observables the user drops
    gate.py capture --round <n>          capture evidence per docs/frontend/capture-plan.json
    gate.py demo before|after [--team]   capture the goal's entry point per <run-dir>/demo-plan.json

    gate.py log dispatch ... --redo     the dispatch redoes its step's work (a fix, a revision, re-work
                                         after an answer); refused past the round cap (loops.max_rounds)

Exit: 0 pass · 1 fail (send failures to their owners, fix, re-run) · 3 round cap reached
(escalate to the user) · 2 usage or configuration error · 4 busy: a writer is dispatched and not
returned — the other team's (`mark`, `capture`, `demo` and every check gate wait) or this run's
(`capture`, `demo` and every check gate wait) (ORCHESTRATOR.md).
Reports: <run-dir>/gates/<phase>-<utc>.json and <phase>-latest.json.
"""
import argparse
import hashlib
import json
import pathlib
import re
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from gatelib import auto, capture, checks, frontend, profile, registry, runlog  # noqa: E402
from gatelib.common import ConfigError, FAIL, PASS, UNAVAILABLE, WAIVED, read_json, stamp, utc_now, write_json  # noqa: E402


def load_cfg(project, need_profile=True):
    """Harness gate config merged with the project's confirmed profile. `log`, `timeline` and `demo`
    run no check, so they pass need_profile=False and work before a profile exists (route/PROTOTYPE.md;
    the demo's before is taken at kickoff)."""
    cfg = read_json(HERE / "config.json")
    cfg.pop("_comment", None)
    proj = read_json(project / ".claude" / "gates.json")
    if not need_profile and (proj is None or not proj.get("confirmed")):
        return cfg
    if proj is None:
        raise ConfigError("no .claude/gates.json — run `gate.py profile` and have the user confirm it")
    if not proj.get("confirmed"):
        raise ConfigError(".claude/gates.json is not confirmed by the user (set confirmed: true, confirmed_on)")
    cfg.update({k: v for k, v in proj.items() if not k.startswith("_")})
    return cfg


def loop_cap(project, team="backend"):
    """Rounds a step may redo its work: `loops.max_rounds` from the team's config, then the project's."""
    cap = 2
    for p in (HERE.parent / team / "config.json", project / ".claude" / f"{team}.json"):
        cap = ((read_json(p) or {}).get("loops") or {}).get("max_rounds", cap)
    return cap


def redo_round(log, step, agent, cap):
    """(the round this redo would be, the rounds allowed): `cap`, plus `cap` for each yes the user
    gave to more rounds at this step (`log human --stop conditional --decision approved --step <s>`)."""
    used, granted = runlog.rounds(log)
    return used.get((str(step), agent), 0) + 1, cap * (1 + granted.get(str(step), 0))


PHASES = {**checks.PHASES, **frontend.PHASES}


def resolve_run_dir(project, arg, team):
    if arg:
        return arg
    if team == "frontend":
        over = read_json(project / ".claude" / "frontend.json") or {}
        return (over.get("artifacts") or {}).get("run_dir") or "docs/frontend"
    return "docs/backend"


class Busy(Exception):
    """The other team has a writer out: snapshots and checks taken now would mix its changes in."""


SETTLED = ("accepted", "prototype_confirmed")


def other_team_logs(project, team):
    other = "backend" if team == "frontend" else "frontend"
    base = project / resolve_run_dir(project, None, other)
    out = []
    for log in [base / "run-log.jsonl", *sorted(base.glob("*/run-log.jsonl"))]:
        status = (read_json(log.parent / "state.json") or {}).get("status")
        if log.exists() and status not in SETTLED:
            out.append(log)
    return out


def ensure_not_busy(project, team, own_log=None):
    """No writer out: of the other team (snapshots would mix its changes in), nor, for a check
    (`own_log`), of this run (the tree is half-written and its role checks would misfire)."""
    for logs, whose in ((other_team_logs(project, team), "the other team has"),
                        ([own_log] if own_log else [], "this run has")):
        out = checks.open_writers(logs)
        if out:
            names = "; ".join(f"{a} ×{n} in {p.relative_to(project)}" for p, a, n in out)
            raise Busy(f"{whose} a writer out ({names}). Wait for its return and log it, then re-run. "
                       f"A dead agent: log its return as failed (ORCHESTRATOR.md, Handoff).")


def apply_waivers(results, gdir):
    """The user's waivers (`<run-dir>/gates/waivers.json`: check, approved_by, date, reason). A check that
    names failing tests is waived only for the tests the waiver lists (`tests`: ids or parts of names):
    a new failure, or anything else wrong with it, is not waived."""
    waivers = {w["check"]: w for w in (read_json(gdir / "waivers.json") or [])
               if w.get("approved_by") and w.get("date")}
    for r in results:  # a tool that did not run has no reading to waive (TOOL.*)
        if r["status"] != FAIL or r["id"] not in waivers or r["id"].startswith("TOOL."):
            continue
        w = waivers[r["id"]]
        if "failed_tests" in r:
            listed = [str(t) for t in w.get("tests") or []]
            beyond = [t for t in r["failed_tests"] if not any(x in t for x in listed)]
            if not listed or beyond or r.get("other_problems"):
                why = ("the waiver lists no tests; add \"tests\": [the failing tests it covers]" if not listed
                       else f"not covered by the waiver: {', '.join(beyond[:10] or r['other_problems'])}")
                r["details"].insert(0, f"waiver of {w['date']} does not apply: {why}")
                continue
        r["status"] = WAIVED
        r["details"].append(f"waived by {w['approved_by']} on {w['date']}: {w.get('reason', '')}"
                            + (f" (tests: {', '.join(w['tests'])})" if w.get("tests") else ""))


FIGMA_ROLES = ("fe-ux", "fe-ui", "fe-engineer")


class Refused(Exception):
    """A dispatch the hook must stop: the reason goes back to the orchestrator."""


def _continued_type(payload):
    """The type of a finished be-*/fe-* agent a SendMessage continues, else None (hooks/no-agent-continuation.py)."""
    to = re.sub(r"\s*\[[^\]]*\]$", "", str((payload.get("tool_input") or {}).get("to", "")).strip())
    transcript = payload.get("transcript_path")
    if not to or to == "main" or not transcript:
        return None
    sub = pathlib.Path(transcript).with_suffix("") / "subagents"
    metas = [sub / f"agent-{to}.meta.json", *sub.glob("agent-*.meta.json")]
    for m in metas:
        meta = read_json(m) if m.is_file() else None
        if meta and (m.name == f"agent-{to}.meta.json" or meta.get("name") == to):
            return meta.get("agentType") if meta.get("finished") is True else None
    return None


def open_runs(project, team):
    """The team's run dirs whose state is not settled: its root and every `<root>/<slug>/`."""
    base = project / resolve_run_dir(project, None, team)
    dirs = [base, *sorted(p.parent for p in base.glob("*/state.json"))]
    states = {d: read_json(d / "state.json") for d in dirs}
    return [d for d in dirs if states[d] is not None and states[d].get("status") not in SETTLED]


def _ctx(project, run):
    return checks.Ctx(project, run.relative_to(project).as_posix(), load_cfg(project, need_profile=False))


def _active_run(project, agent):
    """(ctx, team, state) of the run a dispatch of `agent` belongs to, or (None, team, None) outside a
    run. `fe-*` work in the Frontend run. `be-*` work in the Backend run when one is open (it drives a
    cross-stack run), otherwise in the Frontend run (Phase 0 features, backend-side queue rows)."""
    if agent.startswith("fe-") or (not open_runs(project, "backend") and open_runs(project, "frontend")):
        team = "frontend"
    else:
        team = "backend"
    runs = open_runs(project, team)
    if not runs:
        return None, team, None
    if len(runs) > 1:
        names = ", ".join(r.relative_to(project).as_posix() for r in runs)
        raise Refused(f"several {team} runs are open ({names}): set the finished one's state.json status "
                      f"to accepted, so the log goes to the right run")
    return _ctx(project, runs[0]), team, read_json(runs[0] / "state.json")


def auto_dispatch(payload):
    """PreToolUse(Agent), and PreToolUse(SendMessage) through no-agent-continuation.py: mark, then log the dispatch."""
    tool, ti = payload.get("tool_name"), payload.get("tool_input") or {}
    project = pathlib.Path(payload.get("cwd") or ".").resolve()
    if tool == "Agent":
        agent, text = str(ti.get("subagent_type") or ""), str(ti.get("prompt") or "")
    elif tool == "SendMessage":
        agent = str(payload.get("harness_agent_type") or _continued_type(payload) or "")
        text = str(ti.get("message") or ti.get("content") or "")
    else:
        return 0
    if not auto.HARNESS.match(agent):
        return 0
    ctx, team, st = _active_run(project, agent)
    if ctx is None:
        return 0
    log = ctx.run / "run-log.jsonl"
    events = runlog.events(log)
    step, rnd, budget = auto.parse_brief(text)
    if tool == "SendMessage" and step is None:  # an answer to a blocked agent, same step and round
        step = next((ev.get("phase") for ev in reversed(events)
                     if ev.get("event") == "dispatch" and ev.get("agent") == agent), "x")
    if step is None:
        raise Refused(f"the brief's first line names no step: write `{auto.FIRST_LINE}` (route/HANDOFF.md §3)")
    figma = (st.get("figma") or {}).get("budget")
    if tool == "Agent" and team == "frontend" and agent in FIGMA_ROLES and figma is not None and budget is None:
        raise Refused(f"{agent} brief has no `Budget: <Figma calls left of {figma}>` line (frontend PLAYBOOK §1E)")
    n = allowed = None
    if rnd and rnd > 1:
        n, allowed = redo_round(log, step, agent, loop_cap(project, team))
        if n > allowed:  # a continued author too: its rounds count the same (Constitution §5.4)
            raise Refused(f"ROUND CAP: {agent} at step {step} has used {allowed} of {allowed} rounds. Ask the user; "
                          f"on yes: gate.py log human --stop conditional --decision approved --step {step} "
                          f"--by <user> --note \"<why more rounds>\"")
    marks = [agent] if agent in auto.WRITERS else []
    coord = auto.coordinator(agent)
    if coord:
        since_gate = []
        for ev in events:
            since_gate = [] if ev.get("event") == "gate" else since_gate + [ev]
        if not any(ev.get("event") == "mark" and ev.get("role") == coord for ev in since_gate):
            marks.append(coord)
    if marks:
        ensure_not_busy(project, team)
    for role in marks:
        checks.mark(ctx, role)
        runlog.append(log, "mark", role=role)
    task = re.search(r"^\s*Task:\s*(.+)$", text, re.M)
    runlog.append(log, "dispatch", agent=agent, model=ti.get("model") or auto.agent_model(HERE.parent / "agents", agent),
                  phase=step, note=(task.group(1) if task else ti.get("description") or "dispatch")[:200],
                  redo=n, figma_left=budget if team == "frontend" and agent in FIGMA_ROLES else None,
                  continued=True if tool == "SendMessage" else None)
    return 0


def auto_return(payload):
    """Stop in a be-*/fe-* agent: log its return against its oldest open dispatch."""
    agent = str(payload.get("agent_type") or "")
    if not auto.HARNESS.match(agent):
        return 0
    project = pathlib.Path(payload.get("cwd") or ".").resolve()
    # The return goes where its dispatch went: the open run holding this agent's oldest open dispatch.
    found = []
    for team in ("backend", "frontend"):
        for run in open_runs(project, team):
            evs = runlog.events(run / "run-log.jsonl")
            open_at = [ev.get("ts", "") for ev in evs if ev.get("event") == "dispatch" and ev.get("agent") == agent]
            steps = auto.open_dispatches(evs).get(agent)
            if steps:
                found.append((open_at[-len(steps)], team, run, steps))
    if not found:
        return 0
    _, team, run, steps = min(found, key=lambda f: f[0])
    log = run / "run-log.jsonl"
    text = auto.take_report(payload.get("agent_id"), payload.get("agent_transcript_path") or "")
    status, figma, note = auto.parse_report(text) if text else ("failed", None, "ended without a report")
    runlog.append(log, "return", agent=agent, phase=steps[0], status=status, note=note,
                  figma_calls=(figma or 0) if team == "frontend" and agent in FIGMA_ROLES else None)
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("phase", choices=["profile", "mark", "fixtures-approve", "fe-approve", "fe-promote", "capture", "demo", "log", "auto",
                                      "timeline", *PHASES])
    ap.add_argument("--round")
    ap.add_argument("--exclude", nargs="*", default=[])
    ap.add_argument("--retire", nargs="*", default=[])
    ap.add_argument("--team", choices=["backend", "frontend"], default="backend")
    ap.add_argument("event", nargs="?", help="log: dispatch | return | human | decision | void; demo: before | after; "
                    "auto (hooks/run-log.py, payload on stdin): dispatch | return")
    for f in ("agent", "model", "step", "status", "stop", "decision", "note"):
        ap.add_argument(f"--{f}")
    ap.add_argument("--figma-calls", type=int, help="log return: Figma MCP calls the agent made")
    ap.add_argument("--figma-left", type=int, help="log dispatch: Figma calls left for fe-ux / fe-ui / fe-engineer")
    ap.add_argument("--redo", action="store_true", help="log dispatch: this dispatch redoes its step's work")
    ap.add_argument("--parallel", action="store_true",
                    help="log dispatch: another agent of this type is already out at this step, on purpose")
    ap.add_argument("--seq", type=int, help="log void: the entry to void")
    ap.add_argument("--project", default=".")
    ap.add_argument("--run-dir")
    ap.add_argument("--role")
    ap.add_argument("--by", help="fixtures-approve: who approved (the user)")
    ap.add_argument("--reapprove", nargs="*", default=[], help="fixtures-approve: FX ids whose approved answer changes")
    ap.add_argument("--because", help="fixtures-approve / fe-approve: the newer decision (whose words, when) that "
                                      "replaces what was approved; required with --by orchestrator")
    a = ap.parse_args()
    project = pathlib.Path(a.project).resolve()
    if a.phase == "auto":
        payload = json.load(sys.stdin)
        try:
            return auto_dispatch(payload) if a.event == "dispatch" else auto_return(payload)
        except (Refused, Busy, ConfigError) as e:
            print(f"[gate] {e}", file=sys.stderr)
            return 2

    if a.phase == "profile":
        target = project / ".claude" / "gates.json"
        if target.exists():
            raise ConfigError(f"{target} already exists; edit it instead")
        write_json(target, profile.detect(project))
        print(target.read_text())
        print(f"[gate] draft written to {target}. Show it to the user; on approval set confirmed/confirmed_on.")
        return 0

    team = "frontend" if a.phase.startswith("fe-") or a.phase == "capture" else a.team
    ctx = checks.Ctx(project, resolve_run_dir(project, a.run_dir, team),
                     load_cfg(project, need_profile=a.phase not in ("log", "timeline", "demo")))
    log = ctx.run / "run-log.jsonl"
    if a.phase == "log":
        if a.event in ("gate", "mark", "approve"):
            raise ConfigError(f"`{a.event}` events are written by the gates themselves")
        budget = ((read_json(ctx.run / "state.json") or {}).get("figma") or {}).get("budget")
        if (a.event == "dispatch" and team == "frontend" and a.agent in ("fe-ux", "fe-ui", "fe-engineer")
                and budget is not None and a.figma_left is None):
            raise ConfigError(f"dispatch of {a.agent}: add --figma-left <calls left of {budget}>, the number "
                              "the brief's Budget line gives (PLAYBOOK §1E)")
        if a.redo and a.event != "dispatch":
            raise ConfigError("--redo goes with `log dispatch`")
        if a.event == "void":
            rows = {ev["seq"]: ev for _, ev in runlog.read(log)}
            target = rows.get(a.seq)
            if not (a.seq and a.by and a.note):
                raise ConfigError("log void needs --seq <n> --by <who> --note \"<why it is wrong>\"")
            if not target or target["event"] not in runlog.VOIDABLE:
                raise ConfigError(f"#{a.seq} is not a {' / '.join(runlog.VOIDABLE)} entry of this log")
            if any(ev.get("voids") == a.seq for ev in rows.values()):
                raise ConfigError(f"#{a.seq} is already voided")
            ev = runlog.append(log, "void", voids=a.seq, by=a.by, note=a.note)
            print(f"[gate] logged #{ev['seq']}: voids #{a.seq} ({target['event']} {target.get('agent', '')})")
            return 0
        n = allowed = None
        if a.redo:
            n, allowed = redo_round(log, a.step, a.agent, loop_cap(project, team))
            if n > allowed:
                print(f"[gate] ROUND CAP: {a.agent} at step {a.step} has used {allowed} of {allowed} rounds; "
                      f"not logged. Ask the user; on yes: log human --stop conditional --decision approved "
                      f"--step {a.step} --by <user> --note \"<why more rounds>\"")
                return 3
        # By hand only what the hooks missed: a copy of a hook's entry would count twice.
        open_ = auto.open_dispatches(runlog.events(log))
        if a.event == "dispatch" and str(a.step) in map(str, open_.get(a.agent, [])) and not a.parallel:
            raise ConfigError(f"{a.agent} already has an open dispatch at step {a.step} (see `gate.py timeline`); "
                              "a second copy would never be returned. Another one out on purpose: add --parallel. "
                              "A wrong entry: `log void` it first")
        if a.event == "return" and not open_.get(a.agent):
            raise ConfigError(f"{a.agent} has no open dispatch: its return is already logged, or its dispatch is "
                              "missing (log that first)")
        ev = runlog.append(log, a.event or "", agent=a.agent, model=a.model, phase=a.step, status=a.status,
                           stop=a.stop, decision=a.decision, by=a.by, note=a.note, redo=n,
                           figma_calls=a.figma_calls if a.event == "return" else None,
                           figma_left=a.figma_left if a.event == "dispatch" else None)
        print(f"[gate] logged #{ev['seq']} {ev['event']}" + (f": round {n} of {allowed} at step {a.step}" if n else ""))
        return 0
    if a.phase == "timeline":
        cap, (used, _) = loop_cap(project, team), runlog.rounds(log)
        md = runlog.timeline(log)
        if used:
            md += "\nRounds used: " + ", ".join(f"step {s} {ag} {n}/{redo_round(log, s, ag, cap)[1]}"
                                               for (s, ag), n in sorted(used.items())) + "\n"
        if ctx.run.is_dir():
            (ctx.run / "run-log.md").write_text(md, encoding="utf-8")
        print(md)
        return 0
    if a.phase in ("mark", "capture", "demo", *PHASES):
        ensure_not_busy(project, team, None if a.phase == "mark" else log)
    if a.phase == "mark":
        if not a.role:
            raise ConfigError("mark needs --role")
        results, data = checks.mark(ctx, a.role)
        runlog.append(log, "mark", role=a.role)
        print(f"[gate] mark {a.role}: snapshot saved")
        return 0

    if a.phase == "capture":
        if not a.round:
            raise ConfigError("capture needs --round <n>")
        entries, out = capture.run(ctx, a.round)
        runlog.append(log, "capture", round=a.round, captures=len(entries),
                      failed=[f"{e['id']}@{e.get('size')}" for e in entries if not e["ok"]] or None)
        bad_n = sum(1 for e in entries if not e["ok"])
        print(f"[gate] captured {len(entries)} ({bad_n} failed) into {out.relative_to(project)}/manifest.md")
        return 1 if bad_n else 0
    if a.phase == "demo":
        if a.event not in capture.DEMO_KINDS:
            raise ConfigError("demo needs before | after")
        entries, out = capture.demo(ctx, a.event)
        runlog.append(log, "capture", round=f"demo-{a.event}", captures=len(entries),
                      failed=[f"{e['id']}@{e.get('size')}" for e in entries if not e["ok"]] or None)
        failed = [e for e in entries if not e["ok"]]
        print(f"[gate] demo {a.event}: {len(entries)} captured ({len(failed)} failed) into "
              f"{out.relative_to(project)}/manifest.md")
        for e in failed:
            print(f"  {e['id']}@{e.get('size')}: {e.get('error', '?')}")
        return 1 if failed and a.event == "after" else 0
    if a.phase == "fe-promote":
        if not a.by:
            raise ConfigError("fe-promote needs --by <who accepted>")
        added = registry.promote(ctx, a.by, set(a.exclude), frontend._queue_rows)
        runlog.append(log, "approve", by=a.by, fixtures=added)
        print(f"[gate] registered {len(added)}: {', '.join(added)}")
        return 0
    if a.phase in ("fe-approve", "fixtures-approve") and a.by == "orchestrator" and not a.because:
        raise ConfigError(f"{a.phase} --by orchestrator re-locks only what a newer decision replaced: "
                          "add --because \"<whose words, when>\" (Constitution §5)")
    if a.phase == "fe-approve":
        if not a.by:
            raise ConfigError("fe-approve needs --by <who approved>")
        results, _ = frontend.approve(ctx, a.by, a.retire, a.because)
        runlog.append(log, "approve", by=a.by, note=a.because,
                      fixtures=results[0]["details"] + [f"retired {i}" for i in a.retire])
        print(f"[gate] {results[0]['message']}")
        return 0
    if a.phase == "fixtures-approve":
        if not a.by:
            raise ConfigError("fixtures-approve needs --by <who approved>")
        results, _ = checks.approve_fixtures(ctx, a.by, set(a.reapprove), a.because)
        runlog.append(log, "approve", by=a.by, note=a.because, fixtures=results[0]["details"])
        print(f"[gate] {results[0]['message']}: {', '.join(results[0]['details'])}")
        return 0

    results, data = PHASES[a.phase](ctx)
    results.append(checks.log_valid(ctx))
    results += checks.context_files(ctx)
    apply_waivers(results, ctx.gdir)
    overall = FAIL if any(r["status"] == FAIL for r in results) else PASS

    # A fix round is a failure on a different tree or with different failures; re-running the gate
    # on the same tree (to look again, or after a waiver) is not another round (H12).
    attempts = read_json(ctx.gdir / "attempts.json", {})
    last, runs = attempts.setdefault("_last", {}), attempts.setdefault("_runs", {})
    if overall == FAIL:
        failing = sorted(r["id"] for r in results if r["status"] == FAIL)
        books = {f"{ctx.run_rel}/{n}" for n in ("run-log.jsonl", "run-log.md", "state.json")}  # written by the run itself
        tree = sorted((k, v) for k, v in ctx.snapshot().items() if k not in books)
        sig = hashlib.sha256(json.dumps([failing, tree]).encode()).hexdigest()[:16]
        if sig != last.get(a.phase):
            attempts[a.phase] = attempts.get(a.phase, 0) + 1
        last[a.phase], runs[a.phase] = sig, runs.get(a.phase, 0) + 1
    else:
        attempts[a.phase], runs[a.phase] = 0, 0
        last.pop(a.phase, None)
    write_json(ctx.gdir / "attempts.json", attempts)
    cap = loop_cap(project, team)
    capped = overall == FAIL and attempts[a.phase] > cap

    by_owner = {}
    for r in results:
        if r["status"] == FAIL:
            by_owner.setdefault(r["owner"], []).append(r["id"])
    report = {"phase": a.phase, "time": utc_now(), "project": str(project), "run_dir": ctx.run_rel,
              "overall": overall, "consecutive_failures": attempts[a.phase], "failed_runs": runs[a.phase],
              "fix_round_cap": cap,
              "escalate": capped, "fail_by_owner": by_owner, "checks": results, "data": data}
    write_json(ctx.gdir / f"{a.phase}-{stamp()}.json", report)
    write_json(ctx.gdir / f"{a.phase}-latest.json", report)
    runlog.append(log, "gate", gate=a.phase, overall=overall, fails=by_owner or None,
                  report=f"{ctx.run_rel}/gates/{a.phase}-latest.json")

    mark_of = {PASS: "PASS", FAIL: "FAIL", UNAVAILABLE: "N/A ", WAIVED: "WAIV"}
    for r in results:
        print(f"[{mark_of[r['status']]}] {r['id']}: {r['message']}  ({r['owner']})")
        if r["status"] in (FAIL, WAIVED, UNAVAILABLE):
            for d in r["details"][:12]:
                print(f"         {d}")
        elif r["details"] and r["details"][0].startswith("reused"):  # a green read from an earlier run
            for d in r["details"][:3]:
                print(f"         {d}")
    count = {k: sum(1 for r in results if r["status"] == k) for k in mark_of}
    print(f"\n[gate] {a.phase}: {overall.upper()} — {count[PASS]} pass, {count[FAIL]} fail, "
          f"{count[WAIVED]} waived, {count[UNAVAILABLE]} not checked  report: {ctx.run_rel}/gates/{a.phase}-latest.json")
    if count[UNAVAILABLE]:
        print("[gate] not checked (N/A) is not a pass: "
              + ", ".join(r["id"] for r in results if r["status"] == UNAVAILABLE))
    for extra in data.get("not_machine_checked", []):
        print(f"[gate] not machine-checked: {extra}")
    if overall == FAIL:
        print(f"[gate] owners to fix: {by_owner}")
        if capped:
            print(f"[gate] LOOP CAP: {attempts[a.phase] - 1} fix rounds used (cap {cap}). Escalate to the user.")
            return 3
        print(f"[gate] fix round {attempts[a.phase]} of {cap} ({runs[a.phase]} failed runs on "
              f"{attempts[a.phase]} distinct trees): send each failure to its owner, then re-run.")
        return 1
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except ConfigError as e:
        print(f"[gate] ERROR: {e}", file=sys.stderr)
        sys.exit(2)
    except Busy as e:
        print(f"[gate] BUSY: {e}", file=sys.stderr)
        sys.exit(4)
