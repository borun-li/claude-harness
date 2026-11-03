#!/usr/bin/env python3
"""Computational gates for the backend team.

    gate.py profile                      draft <project>/.claude/gates.json (user confirms it)
    gate.py p1                           after Phase 1 (requirements)
    gate.py p2                           after Phase 2 (design + fixture answers); writes the Plan review sheet
    gate.py fixtures-approve --by <who>  lock the fixtures the user approved at Plan (never without their yes)
    gate.py baseline                     Phase 4 start: clean tree, baseline tests, snapshot
    gate.py mark --role <agent>          snapshot before dispatching a writing agent or reviewers
    gate.py p4 | p5 | p6 | p7            gates after build, verification, review, acceptance
    gate.py log <event> [--agent --model --step --status --stop --decision --by --note]
                                         append to the run log (dispatch | return | human | decision)
    gate.py timeline                     write <run-dir>/run-log.md and print it

Frontend team (run dir docs/frontend; pass --team frontend to baseline, mark, log, timeline):
    gate.py fe-product | fe-ux | fe-ui | fe-queue | fe-plan
    gate.py fe-approve --by <who>        lock the queue's observables and frame exports confirmed at the UI stop
    gate.py fe-build | fe-capture-plan | fe-verify | fe-review | fe-accept
    gate.py log return ... --figma-calls <n>   record the Figma calls an agent reported (PLAYBOOK §1E)
    gate.py fe-promote --by <who> [--exclude Q-…]   after Acceptance: register accepted rows as OBS-###
    gate.py fe-approve --by <who> [--retire OBS-…]  also retires registered observables the user drops
    gate.py capture --round <n>          capture evidence per docs/frontend/capture-plan.json

Exit: 0 pass · 1 fail (send failures to their owners, fix, re-run) · 3 loop cap reached
(escalate to the user) · 2 usage or configuration error.
Reports: <run-dir>/gates/<phase>-<utc>.json and <phase>-latest.json.
"""
import argparse
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from gatelib import capture, checks, frontend, profile, registry, runlog  # noqa: E402
from gatelib.common import ConfigError, FAIL, PASS, UNAVAILABLE, WAIVED, read_json, stamp, utc_now, write_json  # noqa: E402

HARNESS = pathlib.Path.home() / ".claude" / "backend" / "config.json"


def load_cfg(project, need_profile=True):
    """Harness gate config merged with the project's confirmed profile. `log` and `timeline` run no
    check, so they pass need_profile=False and work before a profile exists (route/PROTOTYPE.md)."""
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


def loop_cap(project):
    cap = 3
    for p in (HARNESS, project / ".claude" / "backend.json"):
        cap = ((read_json(p) or {}).get("loops") or {}).get("max_gate_fix_rounds", cap)
    return cap


PHASES = {**checks.PHASES, **frontend.PHASES}


def resolve_run_dir(project, arg, team):
    if arg:
        return arg
    if team == "frontend":
        over = read_json(project / ".claude" / "frontend.json") or {}
        # `artifacts.run_dir`, as in frontend/config.json; a top-level `run_dir` is the older form.
        run = (over.get("artifacts") or {}).get("run_dir") or over.get("run_dir") or "docs/frontend"
        if not (project / run).exists():
            for legacy in ("docs/uiux", "uiux"):
                if (project / legacy).exists():
                    return legacy
        return run
    if not (project / "docs/backend").exists() and (project / "docs/waterfall").exists():
        return "docs/waterfall"
    return "docs/backend"


def apply_waivers(results, gdir):
    waivers = {w["check"]: w for w in (read_json(gdir / "waivers.json") or [])
               if w.get("approved_by") and w.get("date")}
    for r in results:
        if r["status"] == FAIL and r["id"] in waivers:
            w = waivers[r["id"]]
            r["status"] = WAIVED
            r["details"].append(f"waived by {w['approved_by']} on {w['date']}: {w.get('reason', '')}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("phase", choices=["profile", "mark", "fixtures-approve", "fe-approve", "fe-promote", "capture", "log",
                                      "timeline", *PHASES])
    ap.add_argument("--round")
    ap.add_argument("--exclude", nargs="*", default=[])
    ap.add_argument("--retire", nargs="*", default=[])
    ap.add_argument("--team", choices=["backend", "frontend"], default="backend")
    ap.add_argument("event", nargs="?", help="log: dispatch | return | human | decision")
    for f in ("agent", "model", "step", "status", "stop", "decision", "note"):
        ap.add_argument(f"--{f}")
    ap.add_argument("--figma-calls", type=int, help="log return: Figma MCP calls the agent made")
    ap.add_argument("--project", default=".")
    ap.add_argument("--run-dir")
    ap.add_argument("--role")
    ap.add_argument("--by", help="fixtures-approve: who approved (the user)")
    ap.add_argument("--reapprove", nargs="*", default=[], help="fixtures-approve: FX ids whose approved answer changes")
    a = ap.parse_args()
    project = pathlib.Path(a.project).resolve()

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
                     load_cfg(project, need_profile=a.phase not in ("log", "timeline")))
    log = ctx.run / "run-log.jsonl"
    if a.phase == "log":
        if a.event in ("gate", "mark", "approve"):
            raise ConfigError(f"`{a.event}` events are written by the gates themselves")
        ev = runlog.append(log, a.event or "", agent=a.agent, model=a.model, phase=a.step, status=a.status,
                           stop=a.stop, decision=a.decision, by=a.by, note=a.note,
                           figma_calls=a.figma_calls if a.event == "return" else None)
        print(f"[gate] logged #{ev['seq']} {ev['event']}")
        return 0
    if a.phase == "timeline":
        md = runlog.timeline(log)
        if ctx.run.is_dir():
            (ctx.run / "run-log.md").write_text(md, encoding="utf-8")
        print(md)
        return 0
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
    if a.phase == "fe-promote":
        if not a.by:
            raise ConfigError("fe-promote needs --by <who accepted>")
        added = registry.promote(ctx, a.by, set(a.exclude), frontend._queue_rows)
        runlog.append(log, "approve", by=a.by, fixtures=added)
        print(f"[gate] registered {len(added)}: {', '.join(added)}")
        return 0
    if a.phase == "fe-approve":
        if not a.by:
            raise ConfigError("fe-approve needs --by <who approved>")
        results, _ = frontend.approve(ctx, a.by, a.retire)
        runlog.append(log, "approve", by=a.by, fixtures=results[0]["details"] + [f"retired {i}" for i in a.retire])
        print(f"[gate] {results[0]['message']}")
        return 0
    if a.phase == "fixtures-approve":
        if not a.by:
            raise ConfigError("fixtures-approve needs --by <who approved>")
        results, _ = checks.approve_fixtures(ctx, a.by, set(a.reapprove))
        runlog.append(log, "approve", by=a.by, fixtures=results[0]["details"])
        print(f"[gate] {results[0]['message']}: {', '.join(results[0]['details'])}")
        return 0

    results, data = PHASES[a.phase](ctx)
    results.append(checks.log_valid(ctx))
    apply_waivers(results, ctx.gdir)
    overall = FAIL if any(r["status"] == FAIL for r in results) else PASS

    attempts = read_json(ctx.gdir / "attempts.json", {})
    attempts[a.phase] = attempts.get(a.phase, 0) + 1 if overall == FAIL else 0
    write_json(ctx.gdir / "attempts.json", attempts)
    cap = loop_cap(project)
    capped = overall == FAIL and attempts[a.phase] > cap

    by_owner = {}
    for r in results:
        if r["status"] == FAIL:
            by_owner.setdefault(r["owner"], []).append(r["id"])
    report = {"phase": a.phase, "time": utc_now(), "project": str(project), "run_dir": ctx.run_rel,
              "overall": overall, "consecutive_failures": attempts[a.phase], "fix_round_cap": cap,
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
    print(f"\n[gate] {a.phase}: {overall.upper()}  report: {ctx.run_rel}/gates/{a.phase}-latest.json")
    for extra in data.get("not_machine_checked", []):
        print(f"[gate] not machine-checked: {extra}")
    if overall == FAIL:
        print(f"[gate] owners to fix: {by_owner}")
        if capped:
            print(f"[gate] LOOP CAP: {attempts[a.phase] - 1} fix rounds used (cap {cap}). Escalate to the user.")
            return 3
        print(f"[gate] fix round {attempts[a.phase]} of {cap}: send each failure to its owner, then re-run.")
        return 1
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except ConfigError as e:
        print(f"[gate] ERROR: {e}", file=sys.stderr)
        sys.exit(2)
