#!/usr/bin/env python3
"""Computational gates of a run: one run directory, one state, one run log for both teams.

    gate.py <command> --project <root> [--run <slug>]

A run is `<runs root>/<slug>/` (runs root: `artifacts.run_dir` of the harness config, default
docs/runs). Without --run a command works on the one open run: the one whose state.json status is
not accepted, abandoned or prototype_confirmed. `timeline`, `stats`, `status`, `worktrees` and
`fe-promote` take a settled run with --run.

    gate.py profile                      draft <project>/.claude/gates.json (user confirms it)
    gate.py p1                           after Phase 1 (requirements)
    gate.py p2                           after Phase 2 (design + fixture answers); writes the Plan review sheet
    gate.py fixtures-approve --by <who>  lock the fixtures the user approved at Plan (never without their yes;
                                         --by orchestrator --because "<newer decision>" re-locks what it replaced)
    gate.py baseline                     before the run's first code writer: clean tree, baseline tests, snapshot
                                         (--rebaseline: the user agreed to start over from the tree as it is)
    gate.py p4 | p5 | p6 | p7            gates after build, verification, review, acceptance
    gate.py std-build | std-accept       the Standard change tier's two gates (route/STANDARD.md)
    gate.py check <gate>                 read-only self-check for the author of a document or change: the
                                         gate's checks without running a project command; writes nothing,
                                         logs nothing, counts no round, never waits. Sub-agents may run it,
                                         an isolated one with --project <its worktree>
    gate.py waive --check <ID> --gate <gate> --by <user> --reason "<why>" [--tests <failing tests it covers>]
                                         the user's waiver of one check failing at one gate, kept in the run
                                         log; it covers the failure lines of that gate's latest report and
                                         stops applying when a new line appears
    gate.py status                       where the run is: scope, step, open dispatches (in tree or in a
                                         worktree), returns not landed, each gate's last verdict, rounds
                                         used, what the last writers changed, the next ordinals
    gate.py stats                        time, tokens and result per dispatch, and the run's totals;
                                         also written to <run-dir>/stats.md
    gate.py log <event> [--agent --model --step --status --stop --decision --by --note]
                                         append to the run log (dispatch | return | human | decision);
                                         the hooks log dispatches and returns, so by hand only what they
                                         missed (dispatch --isolated, return --worktree <path>: an agent
                                         that worked in a worktree of its own)
    gate.py log void --seq <n> --by <who> --note "<why>"
                                         void a wrong entry (the log is append-only; the gates skip it)
    gate.py timeline                     write <run-dir>/run-log.md and print it
    gate.py mark --role <agent>          repair only: the dispatch hook takes each in-tree writer's snapshot
                                         itself; by hand when a dispatch went out without the hook

Writers. The run's tree (the main checkout, on the run's branch) has one writer out at a time;
writers that are out together are dispatched with isolation: "worktree" and each work in a git
worktree of their own. A returned writer's work is put on the run's branch by `land`:
    gate.py land [--agent <type>] [--seq <dispatch seq>]
                                         every returned writer not landed yet, oldest return first: an
                                         in-tree writer's changes are committed; an isolated writer's are
                                         checked against its role, committed in its worktree, merged with
                                         the run's branch there and fast-forwarded into the run's tree.
                                         One line per writer: merged | committed | empty, or conflict
                                         (the files, left to their author in its worktree) | refused
    gate.py worktrees [--clean]          the agents' worktrees: agent, state (out, unlanded, conflict,
                                         landed), age; --clean removes the landed ones
    gate.py worktrees --setup [--link <dir> …]
                                         once per project: make Claude Code start worktrees from the local
                                         HEAD (worktree.baseRef in .claude/settings.json) and symlink the
                                         named dependency directories into each

Frontend gates:
    gate.py fe-product | fe-ux | fe-ui | fe-queue | fe-plan
    gate.py fe-approve --by <who>        lock the queue's observables and frame exports confirmed at the Prototype stop
    gate.py fe-build | fe-capture-plan | fe-verify | fe-review | fe-accept
    gate.py log return ... --figma-calls <n>   record the Figma calls an agent reported (PLAYBOOK §1E)
    gate.py log dispatch ... --figma-left <n>  calls left, required for fe-ux / fe-ui / fe-engineer when the run has a budget
    gate.py fe-promote --by <who> [--exclude Q-…]   after Acceptance: register accepted rows as OBS-###
    gate.py fe-approve --by <who> [--retire OBS-…]  also retires registered observables the user drops
    gate.py capture --round <n>          capture evidence per <run-dir>/capture-plan.json
    gate.py demo before|after            capture the goal's entry point per <run-dir>/demo-plan.json

Rounds are counted in one place, the run log: a dispatch that redoes work at its step counts one
round for each item its brief names (`Only:`), and the dispatch hook refuses it past the cap
(loops.max_rounds, plus the same again for each yes the user gave at that step). The hook infers the
redo from the log; by hand:
    gate.py log dispatch ... --redo [--items Q-3 FND-002]

Exit: 0 pass · 1 fail (send each failure to its owner, fix, re-run; `land`: a conflict or a refusal) ·
2 usage or configuration error (no open run, several open runs without --run, files of an earlier
harness layout) · 3 `log dispatch --redo` past the round cap (ask the user; a check gate never returns
3) · 4 busy: `capture`, `demo` and every check gate wait while a writer is out in the run's tree
(wait for its return) or a returned writer is not landed (`gate.py land` first); isolated writers
still out keep no gate waiting; `land` waits only for an in-tree writer that is out · 5 the gate
itself crashed (a defect of the gate, not a verdict on the work).
Reports: <run-dir>/gates/<phase>-<utc>.json and <phase>-latest.json.
"""
import argparse
import hashlib
import json
import os
import pathlib
import re
import sys
import traceback

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from gatelib import auto, capture, checks, frontend, profile, registry, runlog, snap, standard, taste, worktree  # noqa: E402
from gatelib.common import (ConfigError, FAIL, PASS, UNAVAILABLE, WAIVED, bad, harness_cfg, merge, read_json,  # noqa: E402
                            stamp, utc_now, write_json)


def load_cfg(project, need_profile=True):
    """Harness gate config with the project's confirmed profile on top; dict-valued keys (`commands`,
    `doc_budgets`) are merged key by key. `log`, `timeline`, `demo`, `check`, `status` and `stats` pass
    need_profile=False and work before a profile exists (route/PROTOTYPE.md; the demo's before is
    taken at kickoff)."""
    cfg = read_json(HERE / "config.json")
    cfg.pop("_comment", None)
    proj = read_json(project / ".claude" / "gates.json")
    if not need_profile and (proj is None or not proj.get("confirmed")):
        return cfg
    if proj is None:
        raise ConfigError("no .claude/gates.json — run `gate.py profile` and have the user confirm it")
    if not proj.get("confirmed"):
        raise ConfigError(".claude/gates.json is not confirmed by the user (set confirmed: true, confirmed_on)")
    return merge(cfg, proj)


def loop_cap(project):
    """Rounds a step may redo its work: `loops.max_rounds` of the harness config."""
    return (harness_cfg(project).get("loops") or {}).get("max_rounds", 2)


def redo_round(log, step, agent, cap, items=()):
    """(the round this redo would be, the rounds allowed, the item that has used most): rounds are
    counted per (step, agent, item); allowed is `cap`, plus `cap` for each yes the user gave to more
    rounds at this step (`log human --stop conditional --decision approved --step <s>`)."""
    used, granted = runlog.rounds(log)
    key = max(runlog.round_keys(step, agent, items), key=lambda k: used.get(k, 0))
    return used.get(key, 0) + 1, cap * (1 + granted.get(str(step), 0)), key[2]


def cap_reached(agent, step, item, allowed):
    on = "" if item == "*" else f" on {item}"
    return (f"ROUND CAP: {agent} at step {step}{on} has used {allowed} of {allowed} rounds. Ask the user; "
            f"on yes: gate.py log human --stop conditional --decision approved --step {step} "
            f"--by <user> --note \"<why more rounds>\"")


def rounds_used(log, cap):
    """["step 2 be-architect 3/4", "step 3 fe-engineer Q-5 1/2"]: rounds used per key against its cap."""
    used, granted = runlog.rounds(log)
    return [f"step {s} {ag}{'' if item == '*' else ' ' + item} {n}/{cap * (1 + granted.get(s, 0))}"
            for (s, ag, item), n in sorted(used.items())]


PHASES = {**checks.PHASES, **frontend.PHASES, **standard.PHASES}
# The code map and the handoff are owed once code is being written: checked at the build, verify
# and accept gates (and always by `check`), not at the document gates.
CONTEXT_GATES = ("p4", "p5", "p7", "fe-build", "fe-verify", "fe-accept", "std-build", "std-accept")
READ_ONLY = ("check", "status", "stats")
SETTLED = ("accepted", "prototype_confirmed", "abandoned")
# With --run these take a settled run too: what reads a finished run, or finishes it.
ANY_RUN = ("timeline", "stats", "status", "worktrees", "fe-promote")
DEAD_AGENT = "A dead agent: log its return as failed (ORCHESTRATOR.md, Handoff)."


class Busy(Exception):
    """A writer is out in the run's tree, or a returned writer is not landed: what a gate reads now
    is half-written, or not on the run's branch yet."""


def run_state(run):
    """A run's state.json; {} when it is missing or unreadable (the gates' own check says which)."""
    try:
        st = read_json(run / "state.json")
    except ValueError:
        st = None
    return st if isinstance(st, dict) else {}


def open_runs(project):
    """The run dirs under the runs root whose state is not settled."""
    root = project / checks.runs_root(project)
    return [p.parent for p in sorted(root.glob("*/state.json")) if run_state(p.parent).get("status") not in SETTLED]


def _names(project, runs):
    return ", ".join(r.relative_to(project).as_posix() for r in runs)


def resolve_run(project, slug, phase):
    """The run a command works on, project-relative: `--run <slug>`, else the one open run."""
    root = checks.runs_root(project)
    if slug:
        rel = f"{root}/{slug.strip('/').split('/')[-1]}"
        if not (project / rel / "state.json").is_file():
            raise ConfigError(f"no run {rel}: no state.json there")
        status = run_state(project / rel).get("status")
        if status in SETTLED and phase not in ANY_RUN:
            raise ConfigError(f"{rel} is settled ({status}): only {', '.join(ANY_RUN)} take a settled run")
        return rel
    runs = open_runs(project)
    if not runs:
        raise ConfigError(f"no open run under {root}")
    if len(runs) > 1:
        raise ConfigError(f"several runs are open under {root} ({_names(project, runs)}): pass --run <slug>, "
                          "or settle the finished one")
    return runs[0].relative_to(project).as_posix()


def legacy(project):
    """Files of the layout before 16.0.0 (a run dir and a config per team): refused with the fix,
    before any run is read. Settled old runs are history and are left alone."""
    found = []
    cfgs = [f".claude/{n}" for n in ("backend.json", "frontend.json") if (project / ".claude" / n).is_file()]
    if cfgs:
        found.append(f"{', '.join(cfgs)}: move their keys into .claude/harness.json; models are now under `models`")
    runs = [p.relative_to(project).as_posix() for d in ("docs/backend", "docs/frontend")
            for p in sorted((project / d).rglob("state.json")) if run_state(p.parent).get("status") not in SETTLED]
    if runs:
        found.append(f"{', '.join(runs)}: this run was started by an earlier harness version: finish it with that "
                     "version, or set its status to abandoned and start a new run")
    if (project / "docs/frontend/observables.json").is_file() and not (project / "docs/observables.json").is_file():
        found.append("docs/frontend/observables.json: the registry is now docs/observables.json: "
                     "git mv docs/frontend/observables.json docs/observables.json")
    if found:
        raise ConfigError("this project holds files of an earlier harness layout. " + ". ".join(found))


def _agents(dispatches):
    return ", ".join(f"{d.get('agent')} · step {d.get('phase')}" for d in dispatches)


def ensure_not_busy(log):
    """A gate reads the run's tree: not while a writer is out in it, nor before every returned
    writer's work is on the run's branch. Isolated writers still out change nothing a gate reads."""
    events = runlog.events(log)
    out = runlog.in_tree_out(events)
    if out:
        raise Busy(f"a writer is out in the run's tree ({_agents(out)}). Wait for its return, land it, "
                   f"then re-run. {DEAD_AGENT}")
    waiting = runlog.unlanded(events)
    if waiting:
        raise Busy(f"returned and not landed: {_agents(waiting)}. Run `gate.py land` first, then re-run")


# ---------- waivers ----------

NEVER_WAIVED = ("LOG.valid", "CTRL.waivers-file")  # and every TOOL.*: a tool that did not run has no reading
WAIVER_NOTE = "[waiver] "  # a detail line the waiver logic added: never part of what a waiver covers


def waivable(check_id):
    return not check_id.startswith("TOOL.") and check_id not in NEVER_WAIVED


def failure_lines(r):
    return [d for d in r.get("details") or [] if not d.startswith(WAIVER_NOTE)]


def waivers_file(ctx):
    """Waivers live in the run log, written by `gate.py waive`. A waivers.json is a file any agent
    could write, so one left in the gates dir fails instead of being read or silently ignored."""
    if not (ctx.gdir / "waivers.json").exists():
        return []
    return [bad("CTRL.waivers-file", f"{ctx.run_rel}/gates/waivers.json is not read any more: waivers are "
                "entries of the run log", "orchestrator",
                ["re-enter each with `gate.py waive --check <ID> --gate <gate> --by <user> --reason \"<why>\"`, "
                 "then delete the file"])]


def apply_waivers(results, events, gate):
    """The user's waivers, read from the run log only (`waive` entries; a voided one is gone). The
    latest waiver of a check at this gate applies while every failure line of the check is one the
    waiver was given for: a new line is a new failure and is not waived. A check that names failing
    tests is waived only for the tests the waiver lists (`tests`: ids or parts of names), and for
    nothing else wrong with it."""
    latest = {ev["check"]: ev for ev in events if ev.get("event") == "waive" and ev.get("gate") == gate}
    for r in results:
        w = latest.get(r["id"])
        if r["status"] != FAIL or w is None or not waivable(r["id"]):
            continue
        day = str(w.get("ts", ""))[:10]
        if "failed_tests" in r:
            listed = [str(t) for t in w.get("tests") or []]
            beyond = [t for t in r["failed_tests"] if not any(x in t for x in listed)]
            why = ("the waiver lists no tests; waive again with --tests <the failing tests it covers>" if not listed
                   else f"not covered by the waiver: {', '.join(beyond[:10] or r['other_problems'])}"
                   if beyond or r.get("other_problems") else None)
        else:
            new = [d for d in failure_lines(r) if d not in set(w.get("details") or [])]
            why = f"new since the waiver: {'; '.join(new[:10])}" if new else None
        if why:
            r["details"].insert(0, f"{WAIVER_NOTE}waiver #{w.get('seq')} of {day} does not apply: {why}")
            continue
        r["status"] = WAIVED
        r["details"].append(f"{WAIVER_NOTE}waived by {w['by']} on {day} (#{w.get('seq')}): {w['reason']}"
                            + (f" (tests: {', '.join(w['tests'])})" if w.get("tests") else ""))


def waive(ctx, a, log):
    if not (a.check and a.gate and a.by and a.reason):
        raise ConfigError("waive needs --check <ID> --gate <gate> --by <user> --reason \"<why>\"")
    if a.gate not in PHASES:
        raise ConfigError(f"--gate {a.gate}: not a check gate ({', '.join(PHASES)})")
    if not waivable(a.check):
        raise ConfigError(f"{a.check} cannot be waived: fix what it reports")
    rep = read_json(ctx.gdir / f"{a.gate}-latest.json") or {}
    r = next((c for c in rep.get("checks", []) if c.get("id") == a.check), None)
    if r is None or r.get("status") != FAIL:
        raise ConfigError(f"{a.check} is not failing in {ctx.run_rel}/gates/{a.gate}-latest.json: a waiver "
                          f"covers a failure the user has seen; run `gate.py {a.gate}` first")
    if "failed_tests" in r and not a.tests:
        raise ConfigError(f"{a.check} names failing tests: add --tests <the failing tests this waiver covers> "
                          f"({', '.join(r['failed_tests'][:10])})")
    lines = sorted(failure_lines(r))
    ev = runlog.append(log, "waive", check=a.check, gate=a.gate, by=a.by, reason=a.reason, tests=a.tests or None,
                       details=lines or None, sig=hashlib.sha256("\n".join(lines).encode("utf-8")).hexdigest())
    print(f"[gate] logged #{ev['seq']}: {a.check} waived at {a.gate} by {a.by} for {len(lines)} failure line(s); "
          "a new line is not covered")
    return 0


# ---------- dispatches and returns, from the hooks ----------

FIGMA_ROLES = ("fe-ux", "fe-ui", "fe-engineer")
MODEL_RANK = ("haiku", "sonnet", "opus")


class Refused(Exception):
    """A dispatch the hook must stop: the reason goes back to the orchestrator."""


def _continued(payload):
    """(agent id, type) of the finished be-*/fe-* agent a SendMessage continues, else (None, None)
    (hooks/no-agent-continuation.py)."""
    to = _to(payload)
    transcript = payload.get("transcript_path")
    if not to or to == "main" or not transcript:
        return None, None
    sub = pathlib.Path(transcript).with_suffix("") / "subagents"
    metas = [sub / f"agent-{to}.meta.json", *sub.glob("agent-*.meta.json")]
    for m in metas:
        meta = read_json(m) if m.is_file() else None
        if meta and (m.name == f"agent-{to}.meta.json" or meta.get("name") == to):
            return m.name[len("agent-"):-len(".meta.json")], meta.get("agentType") if meta.get("finished") is True else None
    return None, None


def _to(payload):
    return re.sub(r"\s*\[[^\]]*\]$", "", str((payload.get("tool_input") or {}).get("to", "")).strip())


def _toplevel(cwd):
    r = snap.git(cwd, "rev-parse", "--show-toplevel") if cwd.is_dir() else None
    return pathlib.Path(r.stdout.strip()).resolve() if r is not None and r.returncode == 0 and r.stdout.strip() else None


def project_root(cwd):
    """The project a hook payload belongs to: the main checkout of the repository its cwd is in, so
    a session that moved into a subdirectory, and a hook fired from inside an agent's worktree,
    still find the run; the cwd itself outside git, or when the cwd holds an open run and the top
    level holds none (a project kept in a subdirectory of a larger repository)."""
    cwd = pathlib.Path(cwd or ".").resolve()
    own = _toplevel(cwd) or cwd                 # the checkout the cwd is in: the main one, or a worktree
    main = worktree.main_root(cwd) or own
    try:
        here = main / cwd.relative_to(own)      # the cwd as a directory of the main checkout
    except ValueError:
        here = main
    return here if here != main and not open_runs(main) and open_runs(here) else main


def _ctx(project, run):
    return checks.Ctx(project, run.relative_to(project).as_posix(), load_cfg(project, need_profile=False))


def _active_run(project):
    """(ctx, state) of the one open run, or (None, None) outside a run."""
    runs = open_runs(project)
    if not runs:
        return None, None
    if len(runs) > 1:
        raise Refused(f"several runs are open ({_names(project, runs)}): in state.json set the finished one's "
                      f"status to accepted, or the dropped one's to abandoned, so the log goes to the right run")
    return _ctx(project, runs[0]), run_state(runs[0])


def _model_floor(project, st, agent, model):
    """An agent listed in `models.floor` is not dispatched on a weaker model than its own: the one
    the run's state.json gives it, else the active tier's."""
    models = harness_cfg(project).get("models") or {}
    if agent not in (models.get("floor") or []):
        return
    own = (st.get("models") or {}).get(agent) or ((models.get("tiers") or {}).get(models.get("_active_tier")) or {}).get(agent)
    rank = lambda m: next((i for i, name in enumerate(MODEL_RANK) if name in str(m).lower()), None)
    if None not in (rank(model), rank(own)) and rank(model) < rank(own):
        raise Refused(f"MODEL FLOOR: {agent} runs on {own} or stronger (models.floor in the harness config); "
                      f"this dispatch names {model}. Dispatch it on {own}")


def _where(ctx, agent, tool, isolated, events):
    """Refuse a dispatch that breaks the rule of the run's tree: one writer in it at a time; writers
    out together each in a worktree of their own, started from a commit that holds the run's work."""
    if agent not in runlog.WRITERS:
        if isolated:
            raise Refused(f"{agent} is dispatched with isolation: \"worktree\", but reviewers read the run's tree: "
                          "dispatch it without isolation")
        return
    in_tree = runlog.in_tree_out(events)
    if not isolated:
        out = [r["dispatch"] for r in runlog.dispatches(events)
               if r["return"] is None and r["dispatch"].get("agent") in runlog.WRITERS]
        busy = [f"{d['agent']} (out{', isolated' if d.get('isolated') else ''})" for d in out] \
            + [f"{d['agent']} (returned, not landed)" for d in runlog.unlanded(events)]
        if busy:
            raise Refused("one writer in the run's tree at a time: wait for " + ", ".join(busy) + ", land it "
                          "(`gate.py land`), or dispatch this one with isolation: \"worktree\"")
        return
    if in_tree:
        raise Refused(f"a writer is out in the run's tree ({_agents(in_tree)}): an isolated writer starts from "
                      "what is committed, so wait for its return and land it (`gate.py land`) first")
    if tool == "Agent" and not worktree.base_setting(ctx.project):
        raise Refused("isolated agents would start from the remote's default branch: run `gate.py worktrees "
                      "--setup` (and restart the session if the next isolated agent still starts from the "
                      "wrong commit)")
    dirty = worktree.dirty_ok(ctx)
    if dirty:
        raise Refused("an isolated agent starts from the last commit: land or commit these first: "
                      + ", ".join(dirty[:20]) + (f" (+{len(dirty) - 20} more)" if len(dirty) > 20 else ""))


def auto_dispatch(payload):
    """PreToolUse(Agent), and PreToolUse(SendMessage) through no-agent-continuation.py: check where
    the agent will work, mark an in-tree writer, then log the dispatch."""
    tool, ti = payload.get("tool_name"), payload.get("tool_input") or {}
    agent_id = None
    if tool == "Agent":
        agent, text = str(ti.get("subagent_type") or ""), str(ti.get("prompt") or "")
    elif tool == "SendMessage":
        agent_id, kind = _continued(payload)
        agent_id = agent_id or _to(payload) or None
        agent = str(payload.get("harness_agent_type") or kind or "")
        text = str(ti.get("message") or ti.get("content") or "")
    else:
        return 0
    if not auto.HARNESS.match(agent):
        return 0
    project = project_root(payload.get("cwd"))
    legacy(project)
    ctx, st = _active_run(project)
    if ctx is None:
        return 0
    log = ctx.run / "run-log.jsonl"
    events = runlog.events(log)
    step, rnd, budget = auto.parse_brief(text)
    answer = tool == "SendMessage" and step is None  # an answer to a blocked agent, same step and round
    if answer:
        step = next((ev.get("phase") for ev in reversed(events)
                     if ev.get("event") == "dispatch" and ev.get("agent") == agent), "x")
    if step is None:
        raise Refused(f"the brief's first line names no step: write `{auto.FIRST_LINE}` (route/HANDOFF.md §3)")
    figma = (st.get("figma") or {}).get("budget") if agent in FIGMA_ROLES else None
    if tool == "Agent" and figma is not None and budget is None:
        raise Refused(f"{agent} brief has no `Budget: <Figma calls left of {figma}>` line (frontend PLAYBOOK §1E)")
    if tool == "Agent" and ti.get("model"):
        _model_floor(project, st, agent, ti["model"])
    # Where it will work: an Agent call says so; a continued author goes on where it last worked.
    wt_rel = None
    if tool == "SendMessage":
        last = next((r for r in reversed(runlog.dispatches(events))
                     if (r["return"] or {}).get("agent_id") == agent_id), None)
        wt_rel = last["return"].get("worktree") if last else None
        if last and (wt_rel or last["dispatch"].get("isolated")) and not (wt_rel and (project / wt_rel).is_dir()):
            raise Refused(f"{agent} worked in {wt_rel or 'a worktree of its own'} and its worktree is gone: "
                          "dispatch a fresh agent")
    isolated = bool(wt_rel) or (tool == "Agent" and ti.get("isolation") == "worktree")
    _where(ctx, agent, tool, isolated, events)
    # A redo is what the log shows, not what the brief claims (auto.is_redo); a brief that says
    # round 1 for a redo is still counted, and told so.
    items = auto.brief_items(text)
    said = bool(rnd and rnd > 1)
    n = allowed = None
    if said or (not answer and auto.is_redo(events, agent, step, items)):
        n, allowed, item = redo_round(log, step, agent, loop_cap(project), items)
        if n > allowed:  # a continued author too: its rounds count the same (Constitution §5.4)
            raise Refused(cap_reached(agent, step, item, allowed))
        if not said:
            print(f"[gate] counted as redo round {n} of {allowed}: {agent} already returned work at step {step}"
                  f"{' on ' + ', '.join(items) if items else ''}; write the round in the brief's first line",
                  file=sys.stderr)
    if wt_rel:
        worktree.refresh(ctx, project / wt_rel)
    # An isolated writer has no mark: its changes are read from its worktree when it is landed.
    marks = [agent] if agent in runlog.WRITERS and not isolated else []
    coord = auto.coordinator(agent)
    if coord:
        since_gate = []
        for ev in events:
            since_gate = [] if ev.get("event") == "gate" else since_gate + [ev]
        if not any(ev.get("event") == "mark" and ev.get("role") == coord for ev in since_gate):
            marks.append(coord)
    for role in marks:
        checks.mark(ctx, role)
        runlog.append(log, "mark", role=role)
    task = re.search(r"^\s*Task:\s*(.+)$", text, re.M)
    ev = runlog.append(log, "dispatch", agent=agent,
                       model=ti.get("model") or auto.agent_model(HERE.parent / "agents", agent),
                       phase=step, note=(task.group(1) if task else ti.get("description") or "dispatch")[:200],
                       redo=n, items=items or None, figma_left=budget if figma is not None else None,
                       continued=True if tool == "SendMessage" else None, agent_id=agent_id,
                       brief=auto.brief_hash(text) if tool == "Agent" else None,
                       isolated=True if isolated else None, worktree=wt_rel,
                       head=snap.head(project) if isolated and tool == "Agent" else None)
    try:  # the dispatch is logged; without the hashes its return only cannot say which control files changed
        auto.keep_control(project, ctx.run, ctx.run_rel, agent, ev["seq"])
    except Exception as e:
        print(f"[gate] control files not hashed for #{ev['seq']}: {e}", file=sys.stderr)
    return 0


def _numstat(ctx, paths):
    """{path: (added, deleted) lines} against HEAD for `paths`; an untracked file counts as all added."""
    out = {}
    r = snap.git(ctx.project, "diff", "--numstat", "--no-renames", "--relative", "-z", "HEAD", "--", *paths)
    for row in r.stdout.split("\0") if r.returncode == 0 else []:
        cells = row.split("\t", 2)
        if len(cells) == 3 and cells[0].isdigit() and cells[1].isdigit():
            out[cells[2]] = (int(cells[0]), int(cells[1]))
    tracked = set(snap.git(ctx.project, "ls-files", "-z", "--", *paths).stdout.split("\0"))
    for p in paths:
        if p not in out and p not in tracked and (ctx.project / p).is_file():
            try:
                out[p] = (len((ctx.project / p).read_text(encoding="utf-8").splitlines()), 0)
            except (UnicodeDecodeError, OSError):
                continue
    return out


def writer_diff(ctx, role):
    """What changed in the run's tree since a writer's mark: `{"added", "modified", "deleted"}`, each a
    list of paths. The run's own books and the saved reports, which the hooks and the orchestrator
    write, are left out. None without a mark."""
    mark = read_json(ctx.gdir / f"snap-{role}.json") or {}
    if not isinstance(mark.get("snapshot"), dict):
        return None
    books = {f"{ctx.run_rel}/{n}" for n in ("run-log.jsonl", "run-log.md", "state.json", "stats.md")}
    d = snap.diff(mark["snapshot"], ctx.snapshot())
    return {k: [p for p in v if p not in books and not p.startswith(f"{ctx.run_rel}/logs/returns/")]
            for k, v in d.items() if k in ("added", "modified", "deleted")}


def writer_changes(ctx, role):
    """What an in-tree writer changed since its mark, for its return: the counts of `writer_diff`
    and `files` as `path (+a/-b)` (at most 20; line counts in a git repository only). None without a mark."""
    d = writer_diff(ctx, role)
    if d is None:
        return None
    shown = (d["added"] + d["modified"] + d["deleted"])[:20]
    lines = _numstat(ctx, shown) if ctx.git and shown else {}
    return {"added": len(d["added"]), "modified": len(d["modified"]), "deleted": len(d["deleted"]),
            "files": [f"{p} (+{lines[p][0]}/-{lines[p][1]})" if p in lines else p for p in shown]}


def _save_report(project, run_rel, seq, agent, text):
    """The agent's full report, kept next to the log entry that names it; None when it cannot be written."""
    rel = f"{run_rel}/logs/returns/{seq}-{agent}.md"
    try:
        (project / rel).parent.mkdir(parents=True, exist_ok=True)
        (project / rel).write_text(text, encoding="utf-8")
    except OSError:
        return None
    return rel


def _worktree_of(project, dispatch, agent_id, cwd):
    """The worktree a returning agent worked in, or None: the one Claude Code made for that agent
    when it still exists; else, for an isolated dispatch, the checkout the hook fired in when that
    is a linked worktree."""
    wt = worktree.path_of(project, agent_id) if agent_id else None
    if wt is None and dispatch.get("isolated"):
        cwd = pathlib.Path(cwd or ".").resolve()
        own, main = _toplevel(cwd), worktree.main_root(cwd)
        wt = own if own and main and own != main else None
    return wt


def auto_return(payload):
    """Stop in a be-*/fe-* agent: log its return against its own open dispatch, with what the hook
    can see for itself — how long it took, where it worked, what it changed, what it cost."""
    agent, agent_id = str(payload.get("agent_type") or ""), payload.get("agent_id")
    if not auto.HARNESS.match(agent):
        return 0
    project = project_root(payload.get("cwd"))
    # The return goes where its dispatch went: an open run holding an open dispatch of this agent type.
    runs = open_runs(project)
    found = [(run, r["dispatch"]) for run in runs for r in runlog.dispatches(runlog.events(run / "run-log.jsonl"))
             if r["return"] is None and r["dispatch"].get("agent") == agent]
    if not found:
        auto.drop_report(agent_id)
        if runs:  # a run is open and this agent's dispatch is not in it: say so now, not at a gate
            print(f"[gate] {agent} returned but its dispatch was never logged: the session that dispatched it "
                  "probably has no run hooks (reopen it through /route-resume); log this dispatch and its "
                  "return by hand", file=sys.stderr)
            return 1
        return 0
    # Its own dispatch among those open: the continuation of this agent, else the one sent the brief
    # this agent's transcript starts with, else the oldest.
    transcript = payload.get("agent_transcript_path") or ""
    brief = auto.brief_hash(auto.first_prompt(transcript))
    run, dispatch = (next((f for f in found if agent_id and f[1].get("agent_id") == agent_id), None)
                     or next((f for f in found if f[1].get("brief") == brief), None)
                     or min(found, key=lambda f: f[1].get("ts", "")))
    log, run_rel = run / "run-log.jsonl", run.relative_to(project).as_posix()
    # the report kept at the handback, else the transcript's, else the one the stop event itself carries
    last = str(payload.get("last_assistant_message") or "")
    text = auto.take_report(agent_id, transcript) or (last if last.strip() else "")
    status, figma, note = auto.parse_report(text) if text else ("failed", None, "ended without a report")

    def extra(read):  # the extras never cost the return itself
        try:
            return read()
        except Exception as e:
            print(f"[gate] return of {agent}: a detail was left out ({type(e).__name__}: {e})", file=sys.stderr)
            return None

    wt = extra(lambda: _worktree_of(project, dispatch, agent_id, payload.get("cwd")))

    def changed():
        ctx = _ctx(project, run)
        if wt is not None:
            return {k: v for k, v in worktree.changes(ctx, wt).items() if k != "paths"}
        if dispatch.get("isolated"):  # Claude Code removes a worktree its agent left unchanged
            return {"added": 0, "modified": 0, "deleted": 0, "files": []}
        return writer_changes(ctx, agent)

    budget = (run_state(run).get("figma") or {}).get("budget") if agent in FIGMA_ROLES else None
    context, out_tokens = extra(lambda: auto.usage(transcript)) or (None, None)
    runlog.append(log, "return", agent=agent, phase=dispatch.get("phase"), status=status, note=note,
                  dispatch=dispatch["seq"], agent_id=agent_id,
                  worktree=pathlib.Path(os.path.relpath(wt, project)).as_posix() if wt is not None else None,
                  figma_calls=(figma if figma is not None else 0 if budget is not None else None)
                  if agent in FIGMA_ROLES else None,
                  seconds=extra(lambda: runlog.seconds_between(dispatch.get("ts"), utc_now())),
                  changed=extra(changed) if agent in runlog.WRITERS else None,
                  visible=extra(lambda: auto.visible(text)), context=context, out_tokens=out_tokens,
                  control_changed=extra(lambda: auto.take_control(project, run, run_rel, agent, dispatch["seq"])) or None,
                  report=(lambda seq: _save_report(project, run_rel, seq, agent, text)) if text else None)
    return 0


# ---------- landing and worktrees ----------

LAND_FIELDS = ("result", "commit", "files", "paths", "note", "owner")


def land(ctx, a, log):
    """`gate.py land`: put every returned writer's work on the run's branch, oldest return first."""
    events = runlog.events(log)
    out = runlog.in_tree_out(events)
    if out:
        raise Busy(f"a writer is out in the run's tree ({_agents(out)}): the tree is half-written. Wait for "
                   f"its return, then land. {DEAD_AGENT}")
    todo = [d for d in runlog.unlanded(events)
            if (not a.agent or d.get("agent") == a.agent) and (a.seq is None or d.get("seq") == a.seq)]
    if not todo:
        print("[land] nothing to land")
        return 0
    returns = {r["dispatch"]["seq"]: r["return"] for r in runlog.dispatches(events)}
    code = 0
    for d in todo:
        ret = returns[d["seq"]]
        if not ctx.git:
            res = {"result": "empty", "note": "not a git repository: nothing to commit"}
        else:
            isolated = d.get("isolated") or d.get("worktree") or ret.get("worktree")
            diff = None if isolated else writer_diff(ctx, d["agent"])
            res = worktree.land(ctx, log, d, ret, tree_paths=snap.changed(diff) if diff else None)
        ev = runlog.append(log, "land", agent=d["agent"], dispatch=d["seq"],
                           **{k: res.get(k) for k in LAND_FIELDS if res.get(k) not in (None, "", [])})
        print(worktree.line(events, ev) + (f" · owner: {ev['owner']}" if ev.get("owner") else ""))
        code = code or (0 if ev["result"] in runlog.LANDED else 1)
    return code


def worktrees(ctx, a, log):
    """`gate.py worktrees [--clean]`: the agents' worktrees and their state."""
    events = runlog.events(log)
    if a.clean:
        removed = worktree.clean(ctx, events)
        print("[worktrees] removed: " + (", ".join(removed) or "none"))
    rows = worktree.listing(ctx, events)
    for r in rows:
        print(f"  {r['path']} · {r.get('agent') or 'no dispatch in this run'} · {r['state']} · "
              f"{runlog.duration(r.get('age'))} old")
    if not rows:
        print("[worktrees] none")
    return 0


# ---------- read-only views ----------

def check(ctx, gate, log):
    """`gate.py check <gate>`: what an author can see of a gate before returning. Nothing is written."""
    ctx.dry = True
    results, _ = PHASES[gate](ctx)
    results += checks.context_files(ctx)
    try:
        apply_waivers(results, runlog.events(log), gate)
    except ConfigError:
        pass  # an unreadable log is the orchestrator's to repair; the author still gets the checks
    for r in results:
        if r["status"] == FAIL:
            print(f"[FAIL] {r['id']}: {r['message']}  ({r['owner']})")
            for d in r["details"][:12]:
                print(f"         {d}")
    count = {k: sum(1 for r in results if r["status"] == k) for k in (PASS, FAIL, WAIVED, UNAVAILABLE)}
    print(f"[check] {gate}: {'FAIL' if count[FAIL] else 'PASS'} — {count[PASS]} pass, {count[FAIL]} fail, "
          f"{count[WAIVED]} waived, {count[UNAVAILABLE]} not checked here (commands, snapshots and the run "
          "log are the gate's). Nothing was recorded.")
    return 1 if count[FAIL] else 0


def status(ctx, log):
    """`gate.py status`: where the run is, from state.json and the run log. Nothing is written."""
    st, events = run_state(ctx.run), runlog.events(log)
    rows = runlog.dispatches(events)
    out = [f"[status] {ctx.run_rel}: tier {st.get('tier', '?')} · scope {st.get('scope', '?')} · "
           f"step {st.get('current_phase', '?')} · {st.get('status', '?')}", "Open dispatches:"]
    where = lambda d, ret=None: ((ret or {}).get("worktree") or d.get("worktree") or "a worktree of its own"
                                 if d.get("isolated") or (ret or {}).get("worktree") else "in tree")
    out += [f"  {r['dispatch']['agent']} · step {r['dispatch'].get('phase')} · {where(r['dispatch'])} · "
            f"since {runlog.when(r['dispatch'].get('ts'))}" for r in rows if r["return"] is None] or ["  none"]
    returns = {r["dispatch"]["seq"]: r["return"] for r in rows}
    tried = {ev.get("dispatch"): ev for ev in events if ev.get("event") == "land"}
    out.append("Returned, not landed (`gate.py land`):")
    out += [f"  {d['agent']} · step {d.get('phase')} · {where(d, returns[d['seq']])}"
            + (f" · last land: {tried[d['seq']]['result']}"
               + (f" ({', '.join(tried[d['seq']].get('paths') or [])})" if tried[d["seq"]].get("paths") else "")
               if d["seq"] in tried else "")
            for d in runlog.unlanded(events)] or ["  none"]
    verdicts = {}
    for ev in events:
        if ev.get("event") == "gate":
            fails = "; ".join(f"{o}: {', '.join(ids)}" for o, ids in (ev.get("fails") or {}).items())
            verdicts[ev["gate"]] = f"  {ev['gate']}: {ev['overall']}" + (f" — {fails}" if fails else "") \
                                   + f" ({runlog.when(ev.get('ts'))})"
    out += ["Gates, latest run of each:", *(verdicts.values() or ["  none run"])]
    used = rounds_used(log, loop_cap(ctx.project))
    out += ["Redo rounds used / allowed:", *([f"  {u}" for u in used] or ["  none"])]
    last = [r for r in rows if r["return"] and r["dispatch"]["agent"] in runlog.WRITERS][-5:]
    out.append("Last writer returns:")
    out += [" · ".join(x for x in (f"  {r['dispatch']['agent']}", f"step {r['return'].get('phase')}",
                                   runlog.change_summary(r["return"].get("changed")) or "changes not recorded",
                                   f"visible: {r['return'].get('visible') or 'not stated'}") if x)
            for r in last] or ["  none"]
    seen = {}
    for r in rows:  # a continued agent keeps its ordinal
        seen[r["dispatch"]["agent"]] = seen.get(r["dispatch"]["agent"], 0) + (0 if r["dispatch"].get("continued") else 1)
    # Every type seen, plus the roles of the run's scope (both teams' when the scope is cross-stack or unset).
    prefixes = {"backend": ("be-",), "frontend": ("fe-",)}.get(st.get("scope"), ("be-", "fe-"))
    for f in sorted((HERE.parent / "agents").glob("*.md")):
        if f.stem.startswith(prefixes):
            seen.setdefault(f.stem, 0)
    out += ["Next ordinal of each agent type:",
            "  " + (" · ".join(f"{a}: #{n + 1}" for a, n in sorted(seen.items()) if auto.HARNESS.match(a)) or "none")]
    print("\n".join(out))
    return 0


def _own_control_write(project, write):
    """Run `write`, which changes a `.claude/*.json` of the project: gate.py's own write, not that of
    an agent now out."""
    before = auto.control_set(project, None) if auto.control_out(project) else None
    out = write()
    if before is not None:
        auto.own_control_writes(project, None, before, auto.control_set(project, None))
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("phase", choices=["profile", "mark", "fixtures-approve", "fe-approve", "fe-promote", "capture", "demo", "log", "auto",
                                      "timeline", "check", "waive", "status", "stats", "land", "worktrees", *PHASES])
    ap.add_argument("--round")
    ap.add_argument("--exclude", nargs="*", default=[])
    ap.add_argument("--retire", nargs="*", default=[])
    ap.add_argument("event", nargs="?", help="log: dispatch | return | human | decision | void; demo: before | after; "
                    "check: the gate to check; auto (hooks/run-log.py, payload on stdin): dispatch | return")
    for f in ("agent", "model", "step", "status", "stop", "decision", "note"):
        ap.add_argument(f"--{f}")
    ap.add_argument("--figma-calls", type=int, help="log return: Figma MCP calls the agent made")
    ap.add_argument("--figma-left", type=int, help="log dispatch: Figma calls left for fe-ux / fe-ui / fe-engineer")
    ap.add_argument("--redo", action="store_true", help="log dispatch: this dispatch redoes its step's work")
    ap.add_argument("--items", nargs="*", default=[], help="log dispatch: the item ids of the brief's Only: line")
    ap.add_argument("--isolated", action="store_true",
                    help="log dispatch: the agent works in a git worktree of its own")
    ap.add_argument("--worktree", help="log return: the worktree the agent worked in (a path in the project)")
    ap.add_argument("--seq", type=int, help="log void: the entry to void; land: the dispatch to land")
    ap.add_argument("--clean", action="store_true", help="worktrees: remove the landed ones")
    ap.add_argument("--setup", action="store_true",
                    help="worktrees: make Claude Code start worktrees from the local HEAD (.claude/settings.json)")
    ap.add_argument("--link", nargs="*", default=[],
                    help="worktrees --setup: dependency directories to symlink into each worktree")
    ap.add_argument("--project", default=".")
    ap.add_argument("--run", help="the run's slug under the runs root (default: the one open run)")
    ap.add_argument("--role")
    ap.add_argument("--by", help="who approved, decided or waived (the user)")
    ap.add_argument("--reapprove", nargs="*", default=[], help="fixtures-approve: FX ids whose approved answer changes")
    ap.add_argument("--because", help="fixtures-approve / fe-approve: the newer decision (whose words, when) that "
                                      "replaces what was approved; required with --by orchestrator")
    ap.add_argument("--rebaseline", action="store_true",
                    help="baseline: the user agreed to replace the baseline after work began")
    ap.add_argument("--check", help="waive: the failing check's id")
    ap.add_argument("--gate", help="waive: the gate it fails at")
    ap.add_argument("--reason", help="waive: why the user accepts the failure")
    ap.add_argument("--tests", nargs="*", default=[], help="waive: the failing tests the waiver covers")
    a = ap.parse_args()
    project = pathlib.Path(a.project).resolve()
    if a.phase == "auto":
        payload = json.load(sys.stdin)
        try:
            return auto_dispatch(payload) if a.event == "dispatch" else auto_return(payload)
        except (Refused, ConfigError) as e:
            print(f"[gate] {e}", file=sys.stderr)
            return 2

    legacy(project)
    if a.phase == "profile":
        target = project / ".claude" / "gates.json"
        if target.exists():
            raise ConfigError(f"{target} already exists; edit it instead")
        _own_control_write(project, lambda: write_json(target, profile.detect(project)))
        print(target.read_text())
        print(f"[gate] draft written to {target}. Show it to the user; on approval set confirmed/confirmed_on.")
        return 0
    if a.phase == "worktrees" and a.setup:
        block = _own_control_write(project, lambda: worktree.setup(project, a.link))
        print(f"[worktrees] .claude/settings.json: worktree = {json.dumps(block)}. Restart the session if the "
              "next isolated agent still starts from the wrong commit.")
        return 0

    named = a.event if a.phase == "check" else a.phase
    if a.phase == "check" and named not in PHASES:
        raise ConfigError(f"check needs a gate: gate.py check <{' | '.join(PHASES)}>")
    ctx = checks.Ctx(project, resolve_run(project, a.run, a.phase), load_cfg(
        project, need_profile=a.phase not in ("log", "timeline", "demo", "waive", "land", "worktrees", *READ_ONLY)))
    log = ctx.run / "run-log.jsonl"
    if a.phase == "check":
        return check(ctx, named, log)
    if a.phase == "status":
        return status(ctx, log)
    if a.phase == "stats":
        md = runlog.stats(log)
        (ctx.run / "stats.md").write_text(md, encoding="utf-8")
        print(md)
        return 0
    # What gate.py itself writes into the control files while agents are out is not theirs.
    before = auto.control_set(project, ctx.run) if auto.control_out(project) else None
    try:
        return run(a, project, ctx, log)
    finally:
        if before is not None:
            auto.own_control_writes(project, ctx.run_rel, before, auto.control_set(project, ctx.run))


def run(a, project, ctx, log):
    """Every command that may write: the log, a mark, a commit, an approval, evidence, a gate report."""
    if a.phase == "log":
        if a.event in ("gate", "mark", "approve", "waive", "capture", "land"):
            raise ConfigError(f"`{a.event}` events are written by the gates themselves"
                              + (": a waiver is entered with `gate.py waive`" if a.event == "waive" else ""))
        budget = (run_state(ctx.run).get("figma") or {}).get("budget")
        if a.event == "dispatch" and a.agent in FIGMA_ROLES and budget is not None and a.figma_left is None:
            raise ConfigError(f"dispatch of {a.agent}: add --figma-left <calls left of {budget}>, the number "
                              "the brief's Budget line gives (PLAYBOOK §1E)")
        if (a.redo or a.items) and a.event != "dispatch":
            raise ConfigError("--redo and --items go with `log dispatch`")
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
            if target["event"] == "dispatch":  # no return will come for it: its kept hashes go too
                auto.take_control(project, ctx.run, ctx.run_rel, target.get("agent"), a.seq)
            print(f"[gate] logged #{ev['seq']}: voids #{a.seq} ({target['event']} {target.get('agent', '')})")
            return 0
        fields = dict(agent=a.agent, model=a.model, phase=a.step, status=a.status, stop=a.stop,
                      decision=a.decision, by=a.by, note=a.note)
        missing = ["--step" if k == "phase" else f"--{k}" for k in runlog.REQUIRED.get(a.event or "", ())
                   if fields.get(k) in (None, "")]
        if missing:
            raise ConfigError(f"log {a.event} needs {' '.join(missing)}"
                              + (" (who decided: the user's name or `user`)" if "--by" in missing else ""))
        n = allowed = None
        if a.redo:
            n, allowed, item = redo_round(log, a.step, a.agent, loop_cap(project), a.items)
            if n > allowed:
                print(f"[gate] {cap_reached(a.agent, a.step, item, allowed)}; not logged")
                return 3
        # By hand only what the hooks missed: a copy of a hook's entry would count twice.
        open_ = [r["dispatch"] for r in runlog.dispatches(runlog.events(log))
                 if r["return"] is None and r["dispatch"].get("agent") == a.agent]
        same = [d for d in open_ if str(d.get("phase")) == str(a.step)]
        if a.event == "dispatch" and same and not (a.isolated and all(d.get("isolated") for d in same)):
            raise ConfigError(f"{a.agent} already has an open dispatch at step {a.step} (see `gate.py timeline`); "
                              "a second copy would never be returned. Agents of one type are out together only "
                              "in worktrees of their own: add --isolated. A wrong entry: `log void` it first")
        if a.event == "return" and not open_:
            raise ConfigError(f"{a.agent} has no open dispatch: its return is already logged, or its dispatch is "
                              "missing (log that first)")
        if a.worktree and not (a.event == "return" and (project / a.worktree).is_dir()):
            raise ConfigError("--worktree goes with `log return` and names an existing directory in the project")
        changed = None
        if a.event == "return":  # by hand for an agent whose hook did not fire: the same control-file check
            changed = auto.take_control(project, ctx.run, ctx.run_rel, a.agent, open_[0]["seq"]) or None
        ev = runlog.append(log, a.event or "", **fields, redo=n, items=a.items or None,
                           control_changed=changed,
                           isolated=True if a.isolated and a.event == "dispatch" else None,
                           worktree=pathlib.Path(os.path.relpath((project / a.worktree).resolve(), project)).as_posix()
                           if a.worktree else None,
                           figma_calls=a.figma_calls if a.event == "return" else None,
                           figma_left=a.figma_left if a.event == "dispatch" else None)
        print(f"[gate] logged #{ev['seq']} {ev['event']}" + (f": round {n} of {allowed} at step {a.step}" if n else ""))
        return 0
    if a.phase == "timeline":
        md, used = runlog.timeline(log), rounds_used(log, loop_cap(project))
        if used:
            md += "\nRounds used: " + ", ".join(used) + "\n"
        (ctx.run / "run-log.md").write_text(md, encoding="utf-8")
        print(md)
        return 0
    if a.phase == "waive":
        return waive(ctx, a, log)
    if a.phase == "land":
        return land(ctx, a, log)
    if a.phase == "worktrees":
        return worktrees(ctx, a, log)
    if a.phase in ("capture", "demo", *PHASES):
        ensure_not_busy(log)
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
        for line in taste.notes(ctx, out)[0]:  # leads for the reviewer's brief; they fail nothing
            print(f"[gate] reported, fails nothing: FE4.taste: {line}")
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
    if a.phase in ("fe-approve", "fixtures-approve"):
        if not a.by:
            raise ConfigError(f"{a.phase} needs --by <who approved>")
        if a.phase == "fe-approve":
            results, _ = frontend.approve(ctx, a.by, a.retire, a.because)
            locked, shown = results[0]["details"] + [f"retired {i}" for i in a.retire], results[0]["message"]
        else:
            results, _ = checks.approve_fixtures(ctx, a.by, set(a.reapprove), a.because)
            locked, shown = results[0]["details"], f"{results[0]['message']}: {', '.join(results[0]['details'])}"
        # What was locked, by hash, and the scope approved with it: the gates compare against the log.
        runlog.append(log, "approve", by=a.by, note=a.because, fixtures=locked,
                      manifest_sha=results[0].get("manifest_sha"), active_reqs=results[0].get("active_reqs"))
        print(f"[gate] {shown}")
        return 0

    ctx.rebaseline = a.rebaseline
    results, data = PHASES[a.phase](ctx)
    results.append(checks.log_valid(ctx))
    results += checks.control_files(ctx)
    results += waivers_file(ctx)
    if a.phase in CONTEXT_GATES:
        results += checks.context_files(ctx)
    apply_waivers(results, runlog.events(log), a.phase)
    overall = FAIL if any(r["status"] == FAIL for r in results) else PASS

    by_owner = {}
    for r in results:
        if r["status"] == FAIL:
            by_owner.setdefault(r["owner"], []).append(r["id"])
    report = {"phase": a.phase, "time": utc_now(), "project": str(project), "run_dir": ctx.run_rel,
              "overall": overall, "fail_by_owner": by_owner, "checks": results, "data": data}
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
    for line in data.get("reported", []):  # measures that fail nothing: leads for the reviewer and the user
        print(f"[gate] reported, fails nothing: {line}")
    if overall == FAIL:
        # The gate reports and names the owners; rounds are counted where the fixes are dispatched.
        print(f"[gate] owners to fix: {by_owner}")
        print("[gate] send each failure to its owner, then re-run.")
        return 1
    return 0


def cli():
    """main() with its outcome as an exit code: a usage error, a busy tree and a crash of the gate
    itself each get their own, so none of them reads as a failed check."""
    try:
        return main()
    except ConfigError as e:
        print(f"[gate] ERROR: {e}", file=sys.stderr)
        return 2
    except Busy as e:
        print(f"[gate] BUSY: {e}", file=sys.stderr)
        return 4
    except Exception as e:
        print(f"[gate] CRASH: {type(e).__name__}: {e}", file=sys.stderr)
        traceback.print_exc()
        return 5


if __name__ == "__main__":
    sys.exit(cli())
