"""Checks of the Standard change tier (route/STANDARD.md): one plan, a build gate, an acceptance gate.

The run dir holds `plan.md` (Change, Files, Checks, Retired tests), `review.md` and the run log;
a cross-stack change is one run with both engineers.
Steps in the log: 1 plan, 2 build, 3 tests, 4 review.
"""
import re

from . import checks, docs, runlog, runner, snap
from .common import PASS, UNAVAILABLE, bad, na, ok, read_json

ENGINEERS = ("be-developer", "fe-engineer")
TESTERS = ("be-tester", "fe-tester")
PLAN = "plan.md"
CHK = re.compile(r"CHK-\d+")
MANUAL = re.compile(r"\bmanual\s*[:：]\s*`?([^\s`|]+)", re.I)


def _events(ctx):
    return runlog.events(ctx.run / "run-log.jsonl")


def _last_dispatched(ctx, roles):
    return next((ev["agent"] for ev in reversed(_events(ctx))
                 if ev.get("event") == "dispatch" and ev.get("agent") in roles), None)


def _engineer(ctx):
    """Who a build failure goes back to: the engineer last dispatched (a cross-stack change has both),
    else the one of the run's scope."""
    scope = (read_json(ctx.run / "state.json") or {}).get("scope")
    return _last_dispatched(ctx, ENGINEERS) or ("fe-engineer" if scope == "frontend" else "be-developer")


def _rows(text, heading):
    """Data rows of the tables under the plan's `## <heading>`, backticks stripped."""
    sec = checks._section(text or "", [r"^\W*%s\b" % heading]) or ""
    return [[c.strip("` ") for c in cells] for cells in docs.table_rows(sec)]


def _check_rows(text):
    """{CHK id: its whole row as text}."""
    return {cells[0]: " | ".join(cells) for cells in _rows(text, "checks") if cells and CHK.fullmatch(cells[0])}


def _plan(ctx, owner):
    text = ctx.doc(PLAN)
    if text is None:
        return bad("STD.plan", f"{ctx.run_rel}/{PLAN} missing (route/STANDARD.md §2)", owner)
    files = [c[0] for c in _rows(text, "files") if c and c[0] and not c[0].startswith(("<", "{"))]
    chks = _check_rows(text)
    problems = ([] if files else ["§ Files: no table row names a path"]) + (
        [] if chks else ["§ Checks: no table row starts with a CHK-nnn id"])
    return (bad("STD.plan", f"{PLAN} does not say what changes or how it is checked", owner, problems) if problems
            else ok("STD.plan", f"{PLAN}: {len(files)} files, {len(chks)} checks", owner))


def _checks(ctx):
    """Every CHK of the plan is made by a test that carries its id (name, comment or docstring), or
    is `manual:` with evidence that exists. Before a tester has worked, a check without its test is
    not yet a failure; acceptance does not pass on it (`STD.gates`)."""
    tester = _last_dispatched(ctx, TESTERS)
    locs = runner.tc_locations(ctx.project, checks._test_code(ctx), ctx.cfg, prefix="CHK")
    untested, no_evidence = [], []
    for chk, row in sorted(_check_rows(ctx.doc(PLAN)).items()):
        m = MANUAL.search(row)
        if m:
            path = m.group(1).rstrip(".,;")
            if not ((ctx.project / path).exists() or (ctx.run / path).exists()):
                no_evidence.append(f"{chk}: manual evidence {path} does not exist")
        elif chk not in locs:
            untested.append(f"{chk}: no test carries this id")
    if untested and tester is None:
        return na("STD.checks", "Checks without a test: the tester writes them at step 3", "orchestrator",
                  untested + no_evidence)
    if untested or no_evidence:
        return bad("STD.checks", "Checks of the plan that nothing makes (a test carrying the CHK id, or "
                   "`manual: <evidence path>`)", tester if untested else "orchestrator", untested + no_evidence)
    return ok("STD.checks", "Every check of the plan has its test or its evidence", tester or "orchestrator")


def build(ctx):
    """After the build and after every fix or new test (route/STANDARD.md §3–§4)."""
    base = checks._baseline(ctx)
    run_diff = snap.diff(base["snapshot"], ctx.snapshot())
    owner = _engineer(ctx)
    res = [checks.state(ctx), _plan(ctx, owner)]
    roles, changed = checks.role_checks(ctx)
    res += roles
    res.append(checks._dependency_check(ctx, base, run_diff, PLAN, owner, "STD.dependencies"))
    res += checks._scan(ctx, base, run_diff, owner)
    for name in ("build", "lint", "typecheck"):
        res.append(checks._command_check(ctx, name, owner)[0])
    t, r = checks._tests(ctx, owner, base)
    res += [t, checks._test_file_drift(ctx, base, owner, "STD.test-drift"), _checks(ctx)]
    return res, {"writer_changed": changed, "counts": r["counts"] if r else None}


def _gates(ctx):
    """The tree accepted is the tree `std-build` passed: its last run is green, every check of the
    plan was read then, and no writer has been dispatched since."""
    owner, events = "orchestrator", _events(ctx)
    at = max((i for i, ev in enumerate(events) if ev.get("event") == "gate" and ev.get("gate") == "std-build"),
             default=None)
    if at is None:
        return bad("STD.gates", "std-build has never run", owner)
    problems = [] if events[at].get("overall") == PASS else [f"#{events[at].get('seq')}: std-build "
                                                             f"{events[at].get('overall')}"]
    problems += [f"#{ev.get('seq')}: {ev['agent']} dispatched after the last std-build" for ev in events[at + 1:]
                 if ev.get("event") == "dispatch" and not checks._is_reviewer(ev.get("agent") or "")]
    latest = read_json(ctx.gdir / "std-build-latest.json") or {}
    problems += [f"{c['id']}: not checked at the last std-build ({c['message']})"
                 for c in latest.get("checks", []) if c["id"] == "STD.checks" and c["status"] == UNAVAILABLE]
    return (bad("STD.gates", "std-build is not green on this tree: run it again after the last change",
                owner, problems) if problems else ok("STD.gates", "std-build green, nothing changed since", owner))


def _findings(ctx):
    owner, text = "orchestrator", ctx.doc("review.md")
    if text is None:
        return bad("STD.findings", f"{ctx.run_rel}/review.md missing: file what the reviewer returned "
                   "(route/STANDARD.md §5)", owner)
    found = docs.findings(text)
    open_ = checks.open_findings(found)
    return (bad("STD.findings", "Blocker/major findings still open", owner, open_) if open_
            else ok("STD.findings", f"{len(found)} findings, no open blocker or major", owner))


def _trail(ctx):
    """The common trail, and the Plan approved before any engineer builds (step 1 is the plan itself)."""
    events = _events(ctx)
    owner, problems = "orchestrator", checks._trail_common(events)
    plan = next((e["seq"] for e in events if e["event"] == "human" and e["stop"] == "Plan"
                 and e["decision"] == "approved"), None)
    build_ = next((e["seq"] for e in events if e["event"] == "dispatch" and e["agent"] in ENGINEERS
                   and str(e.get("phase")) != "1"), None)
    if plan is None:
        problems.append("no approved Plan stop in the log")
    elif build_ is not None and build_ < plan:
        problems.append(f"engineer dispatched to build (#{build_}) before the Plan was approved (#{plan})")
    return (bad("LOG.trail", "Run log does not account for the run", owner, problems) if problems
            else ok("LOG.trail", f"{len(events)} events account for every dispatch and the Plan approval", owner))


def accept(ctx):
    """Before the Acceptance stop (route/STANDARD.md §6)."""
    return [checks.state(ctx), _gates(ctx), _findings(ctx), _trail(ctx), checks.demo(ctx)], {}


PHASES = {"std-build": build, "std-accept": accept}
