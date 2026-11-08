"""Computational checks, one function per gate. Each returns (results, data)."""
import hashlib
import json
import pathlib
import re
import shutil
import time

from . import docs, runlog, runner, snap
from .common import (FAIL, PASS, WAIVED, ConfigError, bad, glob_match, na, ok, read_json, utc_now,
                     write_json)

FIX_STATUS = re.compile(r"fixed|resolved|accepted|已修复|已接受|已解决", re.I)
NO_REQ = {"none", "n/a", "-", "—", "deferred", ""}
# Both teams' run dirs (and legacy ones) hold harness artifacts, not anyone's production work.
RUN_DIRS = ("docs/backend", "docs/waterfall", "docs/frontend", "docs/uiux", "uiux")


def ids_in_other_runs(ctx, names, prefix):
    """{id: run dir} for every PREFIX-nnn heading in NAMES under the project's other run dirs.
    Tests carry these ids project-wide, so a new run continues the numbering instead of restarting."""
    rel = pathlib.PurePosixPath(ctx.run_rel)
    bases = (set(RUN_DIRS) | {ctx.run_rel, rel.parent.as_posix()}) - {".", "", "docs"}
    out = {}
    for b in sorted(bases):
        for name in names:
            for f in [ctx.project / b / name, *sorted((ctx.project / b).glob(f"*/{name}"))]:
                if not f.is_file() or f.parent.resolve() == ctx.run.resolve():
                    continue
                for i in docs.id_blocks(docs.read(f) or "", prefix):
                    out.setdefault(i, f.parent.relative_to(ctx.project).as_posix())
    return out


def unique_ids_check(ctx, cid, ids, names, prefix, owner):
    used = ids_in_other_runs(ctx, names, prefix)
    clash = [f"{i}: already used in {used[i]}" for i in sorted(ids) if i in used]
    if not clash:
        return ok(cid, f"{len(ids)} {prefix} ids new to the project", owner)
    nxt = max(int(i.split("-")[1]) for i in used) + 1
    return bad(cid, f"{prefix} ids reused from an earlier run: continue from {prefix}-{nxt:03d} "
                    "(ids never restart in a project)", owner, clash)


class Ctx:
    def __init__(self, project, run_dir, cfg):
        self.project = pathlib.Path(project).resolve()
        self.run_rel = run_dir.strip("/")
        self.run = self.project / self.run_rel
        self.gdir = self.run / "gates"
        self.cfg = cfg
        self.git = snap.is_git(self.project)

    def doc(self, name):
        return docs.read(self.run / name)

    def snapshot(self):
        return snap.snapshot(self.project, [f"{self.run_rel}/gates/**"])

    def cmd(self, name):
        return (self.cfg.get("commands") or {}).get(name)

    def log(self, name):
        return self.gdir / "logs" / f"{utc_now().replace(':', '')}-{name}.log"

    def is_test(self, p):
        return glob_match(p, self.cfg["test_globs"])

    def is_doc(self, p):
        return glob_match(p, self.cfg["doc_globs"])


# ---------- shared ----------

def upstream(ctx, names, owner):
    missing = [n for n in names if not docs.nontrivial(ctx.doc(n), ctx.cfg["min_doc_lines"])]
    if missing:
        return bad("ALL.upstream", "Upstream document missing or near-empty", owner,
                   [f"{ctx.run_rel}/{n}" for n in missing])
    return ok("ALL.upstream", "Upstream documents present", owner)


def state(ctx):
    s = read_json(ctx.run / "state.json")
    if s is None:
        return bad("ALL.state", "state.json missing", "orchestrator")
    problems = [f"missing key: {k}" for k in
                ("harness_version", "feature", "status", "current_phase", "phases", "models", "loops")
                if k not in s]
    if s.get("status") not in ("in_progress", "blocked", "accepted"):
        problems.append(f"status must be in_progress|blocked|accepted, got {s.get('status')!r}")
    if not isinstance(s.get("phases", []), list):
        problems.append("phases must be a list")
    if "tier" in s and s["tier"] not in ("small", "prototype", "full"):
        problems.append(f"tier must be small|prototype|full, got {s['tier']!r}")
    if "risk" in s and s["risk"] not in ("high", "normal"):
        problems.append(f"risk must be high|normal, got {s['risk']!r}")
    if problems:
        return bad("ALL.state", "state.json does not match the schema (PLAYBOOK §8)", "orchestrator", problems)
    return ok("ALL.state", "state.json valid", "orchestrator")


def _reqs(ctx):
    return docs.requirements(ctx.doc("01-requirements.md") or "")


def _command_check(ctx, name, owner):
    cmd = ctx.cmd(name)
    cid = f"CMD.{name}"
    if not cmd:
        if name in ctx.cfg["required_commands"]:
            return bad(cid, f"No {name} command configured, and it is required", "user"), None
        return na(cid, f"No {name} command configured", owner), None
    r = runner.run(cmd, ctx.project, ctx.cfg["timeout_seconds"], ctx.log(name))
    detail = [f"$ {cmd} -> exit {r['exit']} ({r['seconds']}s), log: {r['log']}"]
    if r["exit"] != 0:
        return bad(cid, f"{name} failed", owner, detail + r["tail"][-15:]), r
    return ok(cid, f"{name} passed", owner, detail), r


def _tests(ctx, owner, baseline=None):
    cmd = ctx.cmd("test")
    if not cmd:
        return bad("CMD.test", "No test command configured, and it is required", "user"), None
    r = runner.run_tests(cmd, ctx.project, ctx.cfg["timeout_seconds"], ctx.log("test"),
                         ctx.gdir / "junit.xml", ctx.cfg.get("junit"))
    c = r["counts"]
    detail = [f"$ {r['cmd']} -> exit {r['exit']} ({r['seconds']}s), log: {r['log']}",
              f"counts: {c if c is not None else 'not parsed'}", f"per-test results: {r['junit_note']}"]
    problems = []
    if r["exit"] != 0 or (c and (c["failed"] or c["errors"])):
        problems.append("tests are red")
        detail += [f"failed: {t}" for t in r["failed_tests"][:20]] or r["tail"][-15:]
    if baseline and c and baseline.get("counts"):
        b = baseline["counts"]
        if runner.total(c) < runner.total(b):
            problems.append(f"test total fell from {runner.total(b)} to {runner.total(c)}")
        skipped_now, skipped_then = c["skipped"] + c["xfailed"], b["skipped"] + b["xfailed"]
        if skipped_now > skipped_then:
            problems.append(f"skipped/xfailed rose from {skipped_then} to {skipped_now}")
    if problems:
        return bad("CMD.test", "; ".join(problems), owner, detail), r
    return ok("CMD.test", "tests green", owner, detail), r


def _test_file_drift(ctx, baseline, owner, cid):
    files = snap.list_files(ctx.project)
    now = runner.test_file_stats(ctx.project, files, ctx.cfg)
    then = baseline.get("test_files", {})
    problems = []
    for f, s in then.items():
        cur = now.get(f)
        if cur is None and s["tests"]:
            problems.append(f"{f}: deleted ({s['tests']} tests)")
        elif cur and cur["tests"] < s["tests"]:
            problems.append(f"{f}: tests {s['tests']} -> {cur['tests']}")
        if cur and cur["skips"] > s["skips"]:
            problems.append(f"{f}: skip markers {s['skips']} -> {cur['skips']}")
    for f, s in now.items():
        if f not in then and s["skips"]:
            problems.append(f"{f}: new file with {s['skips']} skip markers")
    if problems:
        return bad(cid, "Tests were removed or skipped (Constitution §4.5)", owner, problems)
    return ok(cid, "No test removed or skipped", owner)


def _load_mark(ctx, role):
    m = read_json(ctx.gdir / f"snap-{role}.json")
    if m is None:
        raise ConfigError(f"no mark for {role}: run `gate.py mark --role {role}` before dispatching it")
    return m


def _is_reviewer(role):
    """Review coordinators and panelists: their mark guards the tree, not a writer."""
    return role in ("be-reviewer", "fe-reviewer") or role.startswith(("be-review-", "fe-review-"))


def _other_team(ctx, role):
    """Paths another team may change in the same tree while `role` runs: never charged to `role`."""
    pats = [f"{d}/**" for d in RUN_DIRS if d != ctx.run_rel]
    if role.startswith("fe-"):
        pats += [f"{_fx_dir(ctx)}/**", f"{_fx_cand(ctx)}/**"]
    return pats


def _latest_writer(ctx):
    marks = [read_json(p) for p in ctx.gdir.glob("snap-*.json")]
    marks = [m for m in marks if m and not _is_reviewer(m["role"])]
    if not marks:
        raise ConfigError("no writer mark: run `gate.py mark --role <agent>` before dispatching it")
    return max(marks, key=lambda m: m["time_ns"])


def role_checks(ctx):
    """Role rules for the most recently marked writer, on exactly its own changes."""
    m = _latest_writer(ctx)
    role, before = m["role"], m["snapshot"]
    d = snap.diff(before, ctx.snapshot())
    other = _other_team(ctx, role)
    d = {k: [p for p in v if not glob_match(p, other)] if isinstance(v, list) else v for k, v in d.items()}
    ch = snap.changed(d)
    if role == "be-developer":
        fe = [p for p in ch if glob_match(p, ctx.cfg["frontend_globs"])]
        tests = [p for p in d["modified"] + d["deleted"] if ctx.is_test(p)]
        # A frontend run's backend-side queue rows name their files in 03-queue.md.
        plan = "".join(ctx.doc(n) or "" for n in ("03-detailed-design.md", "08-implementation-log.md",
                                                  "03-queue.md"))
        unplanned = [p for p in ch if not ctx.is_test(p) and not ctx.is_doc(p) and not _mentioned(p, plan)]
        return [bad("ROLE.frontend", "be-developer changed frontend files (PLAYBOOK §3C)", role, fe) if fe
                else ok("ROLE.frontend", "No frontend file changed by be-developer", role),
                bad("ROLE.tests", "be-developer modified or deleted existing tests", role, tests) if tests
                else ok("ROLE.tests", "No existing test changed by be-developer", role),
                bad("ROLE.unplanned", "Changed files named in none of 03-detailed-design.md, "
                    "08-implementation-log.md, 03-queue.md (log the deviation or get a design amendment)", role, unplanned)
                if unplanned else ok("ROLE.unplanned", "Every changed file is planned or logged", role)], ch
    if role == "be-tester":
        outside = [p for p in ch if not ctx.is_test(p) and not ctx.is_doc(p)]
        return [bad("ROLE.tester-scope", "be-tester changed non-test files", role, outside) if outside
                else ok("ROLE.tester-scope", "be-tester changed only tests and documents", role)], ch
    if role == "fe-engineer":
        tests = [p for p in d["modified"] + d["deleted"] if ctx.is_test(p)]
        queue = ctx.doc("03-queue.md") or ""
        unplanned = [p for p in ch if not ctx.is_test(p) and not ctx.is_doc(p) and not _mentioned(p, queue)]
        return [bad("ROLE.tests", "fe-engineer modified or deleted existing tests", role, tests) if tests
                else ok("ROLE.tests", "No existing test changed by fe-engineer", role),
                bad("ROLE.unplanned", "Changed files not named in 03-queue.md (a row or § Scaffold)", role, unplanned)
                if unplanned else ok("ROLE.unplanned", "Every changed file is named in a queue row", role)], ch
    if role == "fe-tester":
        outside = [p for p in ch if not ctx.is_test(p) and not ctx.is_doc(p)]
        return [bad("ROLE.tester-scope", "fe-tester changed non-test files", role, outside) if outside
                else ok("ROLE.tester-scope", "fe-tester changed only tests and documents", role)], ch
    if role in ("fe-ux", "fe-ui"):
        outside = [p for p in ch if not glob_match(p, [f"{ctx.run_rel}/**"])]
        return [bad("ROLE.designer-scope", f"{role} changed files outside {ctx.run_rel}/", role, outside)
                if outside else ok("ROLE.designer-scope", f"{role} changed only design documents", role)], ch
    return [na("ROLE.none", f"No role rules for {role}", role)], ch


def _baseline(ctx):
    b = read_json(ctx.gdir / "baseline.json")
    if b is None:
        raise ConfigError("no baseline: run `gate.py baseline` at the start of Phase 4")
    return b


def _mentioned(path, text):
    return path in text or pathlib.PurePath(path).name in text


# ---------- run log ----------

def log_valid(ctx):
    path = ctx.run / "run-log.jsonl"
    if not path.exists():
        return bad("LOG.valid", "No run log: log every dispatch and return (`gate.py log dispatch …`)",
                   "orchestrator")
    found = runlog.problems(path)
    return (bad("LOG.valid", "Run log invalid or tampered", "orchestrator", found) if found
            else ok("LOG.valid", "Run log intact", "orchestrator"))


def _trail_common(events):
    """Every dispatch returned; every writer mark was followed by its dispatch before the next gate
    run. Several marks may precede their dispatches (backend Phase 4 marks the tester, then the
    developer, then dispatches both in one message)."""
    problems, open_ = [], {}
    for ev in events:
        if ev["event"] == "dispatch":
            open_[ev["agent"]] = open_.get(ev["agent"], 0) + 1
        elif ev["event"] == "return":
            if not open_.get(ev["agent"]):
                problems.append(f"#{ev['seq']}: return from {ev['agent']} with no dispatch")
            else:
                open_[ev["agent"]] -= 1
    problems += [f"{a}: {n} dispatch(es) never returned" for a, n in open_.items() if n]
    for i, ev in enumerate(events):
        if ev["event"] == "mark" and not _is_reviewer(ev["role"]):
            dispatched = False
            for e in events[i + 1:]:
                if e["event"] == "gate" or (e["event"] == "mark" and e["role"] == ev["role"]):
                    break
                if e["event"] == "dispatch" and e["agent"] == ev["role"]:
                    dispatched = True
                    break
            if not dispatched:
                problems.append(f"#{ev['seq']}: mark for {ev['role']} not followed by its dispatch")
    return problems


def open_writers(log_paths):
    """[(log, agent, n)] writers dispatched and not yet returned in the given run logs."""
    out = []
    for path in log_paths:
        open_ = {}
        for _, ev in runlog.read(path):
            if ev.get("event") == "dispatch":
                open_[ev["agent"]] = open_.get(ev["agent"], 0) + 1
            elif ev.get("event") == "return" and open_.get(ev.get("agent")):
                open_[ev["agent"]] -= 1
        out += [(path, a, n) for a, n in sorted(open_.items()) if n and not _is_reviewer(a)]
    return out


def _prototype_first(ctx, events, design_phases):
    """Full-development runs: the user confirms a prototype before design (Constitution §2.7)."""
    if (read_json(ctx.run / "state.json") or {}).get("tier") != "full":
        return []
    proto = next((e["seq"] for e in events if e["event"] == "human" and e["stop"] == "Prototype"
                  and e["decision"] == "approved"), None)
    design = next((e["seq"] for e in events if e["event"] == "dispatch"
                   and str(e["phase"]) in design_phases), None)
    if proto is None:
        return ["no approved Prototype stop in the log"]
    if design is not None and design < proto:
        return [f"design dispatched (#{design}) before the Prototype was approved (#{proto})"]
    return []


def _log_trail(ctx, design_phases=("2", "3")):
    """Backend trail: the common checks, then the Plan approved before build and (full tier) the
    Prototype approved before design. design_phases: Phase 2 since 3.2.0, Phase 3 in older runs.
    The Frontend team has its own trail (frontend._trail)."""
    events = [ev for _, ev in runlog.read(ctx.run / "run-log.jsonl")]
    owner, problems = "orchestrator", _trail_common(events)
    plan = next((e["seq"] for e in events if e["event"] == "human" and e["stop"] == "Plan"
                 and e["decision"] == "approved"), None)
    # Phase 1b prototype dispatches are throwaway work and may precede the Plan (route/PROTOTYPE.md).
    build = next((e["seq"] for e in events if e["event"] == "dispatch"
                  and e["agent"] in ("be-developer", "fe-engineer") and str(e["phase"]) != "1b"), None)
    if plan is None:
        problems.append("no approved Plan stop in the log")
    elif build is not None and build < plan:
        problems.append(f"builder dispatched (#{build}) before the Plan was approved (#{plan})")
    problems += _prototype_first(ctx, events, design_phases)
    return (bad("LOG.trail", "Run log does not account for the run", owner, problems) if problems
            else ok("LOG.trail", f"{len(events)} events account for every dispatch and the Plan approval", owner))


# ---------- Phase 1–2: documents ----------

def _prose_check(ctx, cid, text, owner):
    limit = ctx.cfg["doc_budgets"]["prose_unit_words"]
    long = [f"{n} words: {first}…" for first, n in docs.prose_units(text) if n > limit]
    return (bad(cid, f"Prose longer than {limit} words: split into bullets or a table", owner, long) if long
            else ok(cid, f"No paragraph or bullet over {limit} words", owner))


def _length_check(ctx, cid, items, key, owner, what):
    limit = ctx.cfg["doc_budgets"][key]
    long = [f"{i}: {n} words" for i, n in items if n > limit]
    return (bad(cid, f"{what} longer than {limit} words (code excluded)", owner, long) if long
            else ok(cid, f"Every {what} within {limit} words", owner))

def phase1(ctx, name="01-requirements.md"):
    """Requirements. The Frontend team reuses it for 00-requirements.md (frontend-only runs)."""
    owner = "be-analyst"
    text = ctx.doc(name)
    res = [state(ctx), upstream(ctx, [name], owner)]
    if res[-1]["status"] == FAIL:
        return res, {}
    reqs = docs.requirements(text)
    live = {r: v for r, v in reqs.items() if not v["retired"]}
    dups = [r for r, v in reqs.items() if v["blocks"] > 1]
    res.append(bad("P1.req-ids", "No `### REQ-nnn` headings", owner) if not reqs else
               bad("P1.req-ids", "Duplicate REQ ids", owner, dups) if dups else
               ok("P1.req-ids", f"{len(reqs)} REQs, ids unique", owner))
    no_gwt = [r for r, v in live.items() if not v["gwt"]]
    res.append(bad("P1.acceptance", "REQs without Given/When/Then", owner, no_gwt) if no_gwt else
               ok("P1.acceptance", "Every REQ has Given/When/Then", owner))
    no_cut = [r for r, v in live.items() if v["cut"] is None]
    res.append(bad("P1.cut-line", "REQs without `Cut: above|below`", owner, no_cut) if no_cut else
               ok("P1.cut-line", "Every REQ is placed against the cut line", owner))
    res.append(ok("P1.understanding", "§0 Understanding present", owner)
               if re.search(r"^#{1,6}\s+\W*0?\.?\s*(understanding|理解)", docs.mask_code(text), re.I | re.M)
               else bad("P1.understanding", "No `## 0. Understanding` section (ask, meaning, ambiguities)", owner))
    no_src = [r for r, v in live.items() if not v["source"]]
    res.append(bad("P1.source", "REQs whose Source neither quotes the user nor cites an artifact", owner, no_src)
               if no_src else ok("P1.source", "Every REQ traces to the user's words or an artifact", owner))
    res.append(_length_check(ctx, "P1.req-length", [(r, v["words"]) for r, v in live.items()],
                             "req_words", owner, "REQ"))
    res.append(_prose_check(ctx, "P1.prose", text, owner))
    active = docs.active_reqs(reqs)
    undeclared = [r for r in sorted(active) if not reqs[r]["fixtures"] and not reqs[r]["fixtures_na"]]
    res.append(bad("P1.fixtures", "Active REQs without `Fixtures: FX-nnn` or `Fixtures: n/a — <reason>`",
                   owner, undeclared) if undeclared else
               ok("P1.fixtures", "Every active REQ declares fixtures or why not", owner))
    iface = sorted(r for r, v in live.items() if v["interface"])
    res.append(ok("P1.interface", f"{len(iface)} [interface] REQs", owner, iface))
    return res, {"active_reqs": sorted(docs.active_reqs(reqs)), "interface_reqs": iface}


def _architecture(ctx):
    owner = "be-architect"
    res = [state(ctx), upstream(ctx, ["01-requirements.md", "02-architecture.md"], owner)]
    if res[-1]["status"] == FAIL:
        return res, {}
    text = ctx.doc("02-architecture.md")
    missing = sorted(docs.active_reqs(_reqs(ctx)) - docs.ids_in(text, "REQ"))
    res.append(bad("P2.coverage", "Active REQs not covered by the architecture", owner, missing) if missing else
               ok("P2.coverage", "Every active REQ is covered", owner))
    prose = sum(n for _, n in docs.prose_units(text))
    limit = ctx.cfg["doc_budgets"]["architecture_prose_words"]
    res.append(bad("P2.length", f"{prose} words of prose outside tables and code (limit {limit})", owner)
               if prose > limit else ok("P2.length", f"{prose} words of prose (limit {limit})", owner))
    res.append(_prose_check(ctx, "P2.prose", text, owner))
    return res, {}


def _detailed_design(ctx):
    owner = "be-architect"
    res = [state(ctx), upstream(ctx, ["01-requirements.md", "03-detailed-design.md"], owner)]
    if res[-1]["status"] == FAIL:
        return res, {}
    reqs = _reqs(ctx)
    des = docs.designs(ctx.doc("03-detailed-design.md"))
    dups = [d for d, v in des.items() if v["blocks"] > 1]
    res.append(bad("P3.des-ids", "No `### DES-nnn` headings", owner) if not des else
               bad("P3.des-ids", "Duplicate DES ids", owner, dups) if dups else
               ok("P3.des-ids", f"{len(des)} DES, ids unique", owner))
    bad_serves = [f"{d}: serves {sorted(v['serves']) or 'nothing'}" for d, v in des.items()
                  if not v["serves"] or not v["serves"] <= set(reqs)]
    res.append(bad("P3.serves", "DES without a valid REQ", owner, bad_serves) if bad_serves else
               ok("P3.serves", "Every DES serves existing REQs", owner))
    no_side = [d for d, v in des.items() if v["side"] is None]
    res.append(bad("P3.side", "DES without `Side: backend|frontend`", owner, no_side) if no_side else
               ok("P3.side", "Every DES has a side", owner))
    claimed = set().union(*[v["serves"] for v in des.values()]) if des else set()
    unclaimed = sorted(docs.active_reqs(reqs) - claimed)
    res.append(bad("P3.req-claimed", "Active REQs no DES claims", owner, unclaimed) if unclaimed else
               ok("P3.req-claimed", "Every active REQ is claimed", owner))
    res.append(_length_check(ctx, "P3.des-length", [(d, v["words"]) for d, v in des.items()],
                             "des_words", owner, "DES"))
    res.append(_prose_check(ctx, "P3.prose", ctx.doc("03-detailed-design.md"), owner))
    fe = sorted(d for d, v in des.items() if v["side"] == "frontend")
    contract = docs.read(ctx.project / "contracts" / "FRONTEND_BACKEND_CONTRACT.md") or ""
    absent = [d for d in fe if d not in contract]
    res.append(bad("P3.contract", "Frontend DES missing from contracts/FRONTEND_BACKEND_CONTRACT.md",
                   owner, absent) if absent else ok("P3.contract", f"{len(fe)} frontend DES in contract", owner))
    return res, {"frontend_des": fe}


def phase2(ctx):
    """Phase 2 — Design: architecture, detailed design and fixture answers; writes the Plan review sheet."""
    res, data = [], {}
    events = [ev for _, ev in runlog.read(ctx.run / "run-log.jsonl")]
    early = _prototype_first(ctx, events, ("2", "3"))
    res.append(bad("P2.prototype-first", "Design started without an approved Prototype (route/PROTOTYPE.md §5)",
                   "orchestrator", early) if early else
               ok("P2.prototype-first", "Prototype approved before design (or not a Full development run)",
                  "orchestrator"))
    for part in (_architecture, _detailed_design, _fixtures_for_plan):
        r, d = part(ctx)
        res += [x for x in r if not (x["id"] == "ALL.state" and any(y["id"] == "ALL.state" for y in res))]
        data.update(d)
    return res, data


# ---------- Phase 4 start ----------

def baseline(ctx):
    res = []
    if ctx.git:
        dirty = [p for p in snap.dirty_paths(ctx.project)
                 if not glob_match(p, [f"{ctx.run_rel}/**", *(f"{d}/**" for d in RUN_DIRS), ".claude/**",
                                       "contracts/**", "prototype/**", f"{_fx_dir(ctx)}/**", f"{_fx_cand(ctx)}/**"])]
        res.append(bad("BASE.clean-tree", "Uncommitted work outside the run dir; commit it or get the "
                       "user's explicit acceptance before any writer is dispatched", "user", dirty[:50])
                   if dirty else ok("BASE.clean-tree", "Tree clean", "orchestrator"))
    else:
        res.append(na("BASE.clean-tree", "Not a git repository", "orchestrator"))
    t, r = _tests(ctx, "user")
    if t["status"] == FAIL:
        t["message"] = "Baseline is already red: " + t["message"] + " (fix separately or waive)"
    res.append(t)
    files = snap.list_files(ctx.project)
    data = {"time": utc_now(), "head": snap.head(ctx.project) if ctx.git else None,
            "snapshot": ctx.snapshot(), "counts": r["counts"] if r else None,
            "failed_tests": r["failed_tests"] if r else [],
            "test_files": runner.test_file_stats(ctx.project, files, ctx.cfg)}
    write_json(ctx.gdir / "baseline.json", data)
    return res, {"head": data["head"], "counts": data["counts"]}


def mark(ctx, role):
    write_json(ctx.gdir / f"snap-{role}.json", {"role": role, "time": utc_now(), "time_ns": time.time_ns(),
                                                "snapshot": ctx.snapshot()})
    return [ok("MARK", f"Snapshot taken before dispatching {role}", "orchestrator")], {}


# ---------- Phase 4: build ----------

def _added_lines(ctx, base_head, rel):
    """[(line_no, text)] added since the baseline commit (whole file if new or no git)."""
    path = ctx.project / rel
    if ctx.git and base_head and snap.git(ctx.project, "cat-file", "-e", f"{base_head}:{rel}").returncode == 0:
        out, lines, n = snap.git(ctx.project, "diff", "--no-color", "-U0", base_head, "--", rel).stdout, [], 0
        for l in out.splitlines():
            m = re.match(r"@@ -\S+ \+(\d+)", l)
            if m:
                n = int(m.group(1))
            elif l.startswith("+") and not l.startswith("+++"):
                lines.append((n, l[1:]))
                n += 1
        return lines
    try:
        return list(enumerate(path.read_text(encoding="utf-8", errors="replace").splitlines(), 1))
    except OSError:
        return []


def _dep_names(name, text):
    if text is None:
        return set()
    if name == "package.json":
        try:
            pkg = json.loads(text)
        except ValueError:
            return set()
        return {k for sec in ("dependencies", "devDependencies", "peerDependencies", "optionalDependencies")
                for k in pkg.get(sec, {})}
    if name.startswith("requirements") or name == "environment.yml":
        return {re.split(r"[<>=!~\[; ]", l.strip().lstrip("- "))[0].lower() for l in text.splitlines()
                if l.strip() and not l.strip().startswith(("#", "-r", "-e", "name:", "channels", "dependencies"))}
    if name == "pyproject.toml":
        return {m.lower() for m in re.findall(r"^\s*['\"]([A-Za-z0-9_.\-]+)", text, re.M)}
    if name == "go.mod":
        return set(re.findall(r"^\s*(?:require\s+)?([\w.\-]+\.[\w./\-]+)\s+v", text, re.M))
    if name == "Cargo.toml":
        out, on = set(), False
        for l in text.splitlines():
            if l.startswith("["):
                on = "dependencies" in l
            elif on and re.match(r"[A-Za-z0-9_\-]+\s*=", l):
                out.add(l.split("=")[0].strip())
        return out
    return None


def _dependency_check(ctx, base, run_diff, design_doc="03-detailed-design.md", owner="be-developer",
                      cid="P4.dependencies"):
    design = (ctx.doc(design_doc) or "").lower()
    manifests = [p for p in snap.changed(run_diff) if glob_match(p, ctx.cfg["dependency_manifests"])]
    if not manifests:
        return ok(cid, "No dependency manifest changed", owner)
    problems = []
    for rel in manifests:
        name = pathlib.PurePath(rel).name
        old = (snap.git(ctx.project, "show", f"{base['head']}:{rel}").stdout
               if ctx.git and base.get("head") else None)
        new = docs.read(ctx.project / rel)
        if old is None and rel not in base["snapshot"]:
            old = ""
        before, after = _dep_names(name, old), _dep_names(name, new)
        if before is None or after is None:
            problems.append(f"{rel}: changed, format not parsed — confirm the change in {design_doc}")
            continue
        problems += [f"{rel}: new dependency `{d}` not named in {design_doc}"
                     for d in sorted(after - before) if d.lower() not in design]
    return (bad(cid, "Dependencies added outside the approved design (Constitution §4.2)",
                owner, problems) if problems else
            ok(cid, "Every new dependency is named in the design", owner))


def _scan(ctx, base, run_diff):
    secret = [re.compile(p) for p in ctx.cfg["secret_patterns"]]
    personal = [re.compile(p) for p in ctx.cfg["personal_path_patterns"]]
    hits_s, hits_p = [], []
    for rel in run_diff["added"] + run_diff["modified"]:
        if ctx.is_doc(rel):
            continue
        for n, line in _added_lines(ctx, base.get("head"), rel):
            if any(r.search(line) for r in secret):
                hits_s.append(f"{rel}:{n}")
            if any(r.search(line) for r in personal):
                hits_p.append(f"{rel}:{n}: {line.strip()[:100]}")
    return [bad("P4.secrets", "Possible secret in new code", "be-developer", hits_s) if hits_s else
            ok("P4.secrets", "No secret patterns in new code", "be-developer"),
            bad("P4.personal-paths", "Absolute personal path in new code", "be-developer", hits_p) if hits_p else
            ok("P4.personal-paths", "No absolute personal paths in new code", "be-developer")]


def phase4(ctx):
    base = _baseline(ctx)
    run_diff = snap.diff(base["snapshot"], ctx.snapshot())
    res = [state(ctx), upstream(ctx, ["03-detailed-design.md", "04-test-plan.md"], "orchestrator")]
    roles, changed = role_checks(ctx)
    res += roles
    res.append(_dependency_check(ctx, base, run_diff))
    res += _scan(ctx, base, run_diff)
    for name in ("build", "lint", "typecheck"):
        res.append(_command_check(ctx, name, "be-developer")[0])
    t, r = _tests(ctx, "be-developer", base)
    res.append(t)
    res.append(_test_file_drift(ctx, base, "be-developer", "P4.test-drift"))
    res.append(_fixture_integrity(ctx, "P4.fixtures", "be-developer"))

    owner = "be-tester"
    reqs, tcs = _reqs(ctx), docs.testcases(ctx.doc("04-test-plan.md") or "")
    dups = [t for t, v in tcs.items() if v["blocks"] > 1]
    res.append(bad("P4.plan-ids", "No `### TC-nnn` headings", owner) if not tcs else
               bad("P4.plan-ids", "Duplicate TC ids", owner, dups) if dups else
               ok("P4.plan-ids", f"{len(tcs)} TCs, ids unique", owner))
    if tcs:
        res.append(unique_ids_check(ctx, "P4.tc-ids", tcs, ("04-test-plan.md",), "TC", owner))
    bad_tc = [f"{t}: verifies {sorted(v['verifies']) or 'nothing'}, mode {v['mode']}" for t, v in tcs.items()
              if not v["verifies"] or not v["verifies"] <= set(reqs) or v["mode"] is None]
    res.append(bad("P4.plan-cases", "TCs without a valid REQ or automated/manual mode", owner, bad_tc)
               if bad_tc else ok("P4.plan-cases", "Every TC verifies REQs and has a mode", owner))
    tested = set().union(*[v["verifies"] for v in tcs.values()]) if tcs else set()
    untested = sorted(docs.active_reqs(reqs) - tested)
    res.append(bad("P4.plan-coverage", "Active REQs without a TC", owner, untested) if untested else
               ok("P4.plan-coverage", "Every active REQ has a TC", owner))
    return res, {"writer_changed": changed, "counts": r["counts"] if r else None}


# ---------- Phase 5: verification ----------

def _test_code(ctx):
    """Test files, excluding the fixture data itself (which names its own FX ids)."""
    return [f for f in snap.list_files(ctx.project)
            if not glob_match(f, [f"{_fx_dir(ctx)}/**", f"{_fx_cand(ctx)}/**"])]


def _fx_dir(ctx):
    return (ctx.cfg.get("fixtures_dir") or "tests/fixtures/approved").strip("/")


def _fx_cand(ctx):
    return (ctx.cfg.get("fixture_candidates_dir") or "tests/fixtures/candidates").strip("/")


def _manifest(ctx):
    return read_json(ctx.project / _fx_dir(ctx) / "APPROVED.json", {"cases": {}})


def _declared_fx(ctx):
    """{FX: REQ} for the active REQs of this round."""
    reqs = _reqs(ctx)
    return {fx: r for r in docs.active_reqs(reqs) for fx in (reqs[r]["fixtures"] or [])}


def _sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _valid_compare(rule):
    return rule in ("exact", "json-unordered", "text-whitespace") or bool(re.fullmatch(r"numeric:[0-9.eE+-]+", rule or ""))


def _fixture_integrity(ctx, cid, owner):
    """Every approved file is unchanged, and every declared FX of this round is approved."""
    base, man = ctx.project / _fx_dir(ctx), _manifest(ctx)
    problems = []
    for fx, case in man["cases"].items():
        for rel, digest in case["files"].items():
            f = base / fx / rel
            if not f.exists():
                problems.append(f"{fx}/{rel}: missing")
            elif _sha(f) != digest:
                problems.append(f"{fx}/{rel}: changed since approval on {case['date']}")
    problems += [f"{fx} ({r}): declared but never approved at Plan" for fx, r in _declared_fx(ctx).items()
                 if fx not in man["cases"]]
    return (bad(cid, "Approved fixtures changed or missing (only the user re-approves, at Plan)", owner, problems)
            if problems else ok(cid, f"{len(man['cases'])} approved fixtures intact", owner))


def _preview(path, lines=15):
    try:
        text = path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        return [f"(binary, {path.stat().st_size} bytes)"]
    out = text.splitlines()
    return out[:lines] + ([f"… ({len(out) - lines} more lines)"] if len(out) > lines else [])


def _fixtures_for_plan(ctx):
    """Before the user's Plan review: fixture candidates complete; writes the one-page review sheet."""
    res = [state(ctx)]
    marks = [read_json(p) for p in ctx.gdir.glob("snap-*.json")]
    if any(m and not _is_reviewer(m["role"]) for m in marks):
        res += role_checks(ctx)[0]
    man, cand = _manifest(ctx), ctx.project / _fx_cand(ctx)
    declared = _declared_fx(ctx)
    missing_in, missing_out, bad_meta, to_approve = [], [], [], []
    sheet = _plan_summary(ctx) + ["## Fixtures", "",
             "Approve, edit or reject each case. Approved cases become the answers every later test must match.",
             ""]
    for fx, req in sorted(declared.items()):
        d = cand / fx
        if not d.exists() and fx in man["cases"]:
            continue  # approved in an earlier round, unchanged
        ins, exps = sorted(d.glob("input*")), sorted(d.glob("expected*"))
        meta = read_json(d / "meta.json", {}) if d.exists() else {}
        if not ins:
            missing_in.append(f"{fx} ({req}): no {_fx_cand(ctx)}/{fx}/input.*")
        if not exps:
            missing_out.append(f"{fx} ({req}): no {_fx_cand(ctx)}/{fx}/expected.*")
        if d.exists() and (meta.get("req") != req or not _valid_compare(meta.get("compare"))
                           or not meta.get("source")):
            bad_meta.append(f"{fx}: meta.json needs req={req}, source, compare in "
                            f"{ctx.cfg['fixture_compare_rules']} (got {meta})")
        if ins and exps:
            to_approve.append(fx)
            sheet += [f"## {fx} — {req}" + ("  (RE-APPROVAL: changes an approved answer)" if fx in man["cases"] else ""),
                      f"- source: {meta.get('source')}", f"- compare: {meta.get('compare')}", ""]
            for label, files in (("Input", ins), ("Expected output", exps)):
                for f in files:
                    sheet += [f"**{label}** `{f.relative_to(ctx.project)}`", "```", *_preview(f), "```", ""]
    res.append(bad("PLAN.inputs", "Declared fixtures without a real input", "be-analyst", missing_in)
               if missing_in else ok("PLAN.inputs", "Every declared fixture has an input", "be-analyst"))
    res.append(bad("PLAN.expected", "Declared fixtures without a drafted expected output", "be-analyst", missing_out)
               if missing_out else ok("PLAN.expected", "Every declared fixture has an expected output", "be-analyst"))
    res.append(bad("PLAN.meta", "Fixture meta.json incomplete", "be-analyst", bad_meta)
               if bad_meta else ok("PLAN.meta", "Every fixture names its REQ, source and compare rule", "be-analyst"))
    if not declared:
        sheet.append("_No fixtures this round._")
    (ctx.gdir / "plan-review.md").parent.mkdir(parents=True, exist_ok=True)
    (ctx.gdir / "plan-review.md").write_text("\n".join(sheet) + "\n", encoding="utf-8")
    return res, {"to_approve": to_approve, "review_sheet": f"{ctx.run_rel}/gates/plan-review.md"}


def _plan_summary(ctx):
    """Requirements, non-goals, decisions and dependencies, lifted from 01–03 without rewording."""
    text = ctx.doc("01-requirements.md") or ""
    reqs = docs.requirements(text)
    out = ["# Plan review", "", "Approve the plan, or say what to change. Nothing is built before you do.", "",
           "## Requirements", "", "| REQ | Cut | Behaviour | Fixtures |", "|---|---|---|---|"]
    for rid, block in sorted(docs.id_blocks(text, "REQ").items()):
        m = re.search(r"\bbehaviou?r\b[:*\s]{0,6}([^\n]*)", block[0], re.I)
        title = block[0].splitlines()[0].lstrip("# ").strip()
        v = reqs[rid]
        fx = ", ".join(v["fixtures"] or []) or (f"n/a: {v['fixtures_na']}" if v["fixtures_na"] else "—")
        out.append(f"| {title} | {v['cut'] or '?'} | {m.group(1).strip() if m else '—'} | {fx} |")
    for label, doc, pats in (("Non-goals", "01-requirements.md", [r"non-goals?", r"非目标"]),
                             ("Key decisions", "02-architecture.md", [r"decisions?", r"决定"]),
                             ("Dependencies", "03-detailed-design.md", [r"dependenc", r"依赖"])):
        sec = _section(ctx.doc(doc) or "", pats)
        out += ["", f"## {label}", "", *(sec.splitlines()[1:] if sec else ["—"])]
    return out + [""]


def _section(text, patterns):
    hs = docs.headings(text)
    for i, (lvl, title, start, _) in enumerate(hs):
        if any(re.search(p, title, re.I) for p in patterns):
            end = next((st for l, _, st, _ in hs[i + 1:] if l <= lvl), len(text))
            return text[start:end].strip()
    return None


def approve_fixtures(ctx, by, reapprove):
    """Lock the candidates the user approved at Plan. Never run without the user's explicit yes."""
    plan = read_json(ctx.gdir / "p2-latest.json")
    if not plan or plan["overall"] != PASS:
        raise ConfigError("`p2` has not passed; run it and get the user's approval first")
    man, base, cand = _manifest(ctx), ctx.project / _fx_dir(ctx), ctx.project / _fx_cand(ctx)
    todo = plan["data"]["to_approve"]
    blocked = [fx for fx in todo if fx in man["cases"] and fx not in reapprove]
    if blocked:
        raise ConfigError(f"{blocked} change already-approved answers; pass --reapprove {' '.join(blocked)} "
                          "only after the user has seen the difference")
    date = utc_now()[:10]
    for fx in todo:
        src, dst = cand / fx, base / fx
        meta = read_json(src / "meta.json")
        prev = man["cases"].get(fx)
        if dst.exists():
            shutil.rmtree(dst)
        shutil.copytree(src, dst)
        files = {f.relative_to(dst).as_posix(): _sha(f) for f in sorted(dst.rglob("*")) if f.is_file()}
        man["cases"][fx] = {"req": meta["req"], "source": meta["source"], "compare": meta["compare"],
                            "approved_by": by, "date": date, "files": files,
                            "history": (prev.get("history", []) + [{k: prev[k] for k in ("date", "approved_by", "files")}])
                            if prev else []}
        shutil.rmtree(src)
    write_json(base / "APPROVED.json", man)
    return [ok("PLAN.approve", f"Locked {len(todo)} fixtures, approved by {by} on {date}", "orchestrator", todo)], {}


def _fixture_use(ctx, cases):
    """Every approved fixture is referenced by a test (tagged FX-nnn) that passes in this run."""
    locs = runner.tc_locations(ctx.project, _test_code(ctx), ctx.cfg, prefix="FX")
    fxs = sorted(_manifest(ctx)["cases"])
    unused = [fx for fx in fxs if fx not in locs]
    observed = _observed_ids(locs, {fx: None for fx in fxs if fx in locs}, cases) if cases is not None else {}
    red = [f"{fx}: {st}" for fx, st in observed.items() if st != "passed"]
    if unused or red:
        details = [f"{fx}: no test references it" for fx in unused] + red
        return bad("P5.fixtures-used", "Approved fixtures not exercised by a passing test (tag the test FX-nnn)",
                   "be-tester", details), observed
    if cases is None and fxs:
        return na("P5.fixtures-used", "Fixtures referenced; pass status needs a JUnit report", "be-tester"), {}
    return ok("P5.fixtures-used", f"{len(fxs)} approved fixtures used by passing tests", "be-tester"), observed


def _observed_tc(ctx, tcs, cases):
    """{TC: passed|failed|not-executed} for automated TCs, from JUnit cases."""
    locs = runner.tc_locations(ctx.project, _test_code(ctx), ctx.cfg)
    return _observed_ids(locs, {t: v for t, v in tcs.items() if v["mode"] == "automated"}, cases)


def id_in_name(tid, name):
    """The id appears in a test name: `Q-003 cards`, `TestRows/Q-003_cards` (Go turns spaces into `_`),
    `test_x[Q-003]`; never `Q-0031` or `XQ-003`."""
    return re.search(r"(?<![A-Za-z0-9-])%s(?!\d)" % re.escape(tid), name or "") is not None


def _observed_ids(locs, ids, cases):
    """{id: passed|failed|not-executed}: a JUnit case counts when its name carries the id, or when it
    is the tagged test (python function name, or JS test title)."""
    out = {}
    for tc in ids:
        statuses = [st for cls, name, st in cases if id_in_name(tc, name)]
        for rel, fn in locs.get(tc, []):
            stem = pathlib.PurePath(rel).with_suffix("").as_posix().replace("/", ".")
            for cls, name, st in cases:
                if not fn or id_in_name(tc, name):
                    continue
                if " " in fn or not fn.isidentifier():  # a JS test title
                    if fn in name:
                        statuses.append(st)
                elif name.split("[")[0] == fn and (cls.endswith(stem) or stem.endswith(cls.split(".")[-1])
                                                    or pathlib.PurePath(rel).stem in cls):
                    statuses.append(st)
        out[tc] = ("not-executed" if not statuses else
                   "passed" if all(s == "passed" for s in statuses) else "failed")
    return out


def phase5(ctx):
    base = _baseline(ctx)
    res = [state(ctx), upstream(ctx, ["04-test-plan.md", "05-test-report.md"], "be-tester")]
    res += role_checks(ctx)[0]
    t, r = _tests(ctx, "be-developer", base)
    res.append(t)
    res.append(_test_file_drift(ctx, base, "be-tester", "P5.test-drift"))

    tcs = docs.testcases(ctx.doc("04-test-plan.md") or "")
    auto = sorted(t for t, v in tcs.items() if v["mode"] == "automated")
    locs = runner.tc_locations(ctx.project, _test_code(ctx), ctx.cfg)
    absent = [t for t in auto if t not in locs]
    res.append(bad("P5.tc-in-code", "Automated TCs not found in test code (tag the test with its TC id)",
                   "be-tester", absent) if absent else
               ok("P5.tc-in-code", f"{len(auto)} automated TCs found in test code", "be-tester"))
    observed = {}
    if r and r.get("cases") is not None:
        observed = _observed_tc(ctx, tcs, r["cases"])
        not_green = [f"{t}: {s}" for t, s in observed.items() if s != "passed"]
        res.append(bad("P5.tc-results", "Automated TCs not passing in this run", "be-tester", not_green)
                   if not_green else ok("P5.tc-results", "Every automated TC passed in this run", "be-tester"))
    else:
        res.append(na("P5.tc-results", "Per-test results need a JUnit report (pytest, vitest, playwright, jest-junit, or gates.json junit)", "be-tester"))

    reported = docs.report_results(ctx.doc("05-test-report.md"))
    missing = [t for t in tcs if t not in reported]
    res.append(bad("P5.report-complete", "TCs with no pass/fail/blocked verdict in 05-test-report.md",
                   "be-tester", missing) if missing else
               ok("P5.report-complete", "Every TC has a verdict in the report", "be-tester"))
    false_pass = [f"{t}: reported pass, observed {observed[t]}" for t, v in reported.items()
                  if v == "pass" and observed.get(t) not in (None, "passed")]
    res.append(bad("P5.report-honest", "Report claims passes this run did not observe (Constitution §2.3)",
                   "be-tester", false_pass) if false_pass else
               ok("P5.report-honest", "Reported passes match observed results", "be-tester"))
    res.append(_fixture_integrity(ctx, "P5.fixtures", "be-tester"))
    use, fx_observed = _fixture_use(ctx, r.get("cases") if r else None)
    res.append(use)
    return res, {"tc_observed": observed, "tc_reported": reported, "fx_observed": fx_observed,
                 "counts": r["counts"] if r else None}


# ---------- Phase 6: review ----------

def phase6(ctx):
    owner = "orchestrator"
    before = _load_mark(ctx, "be-reviewer")["snapshot"]
    d = snap.diff(before, ctx.snapshot())
    changed = [p for p in snap.changed(d) if not glob_match(p, [f"{ctx.run_rel}/**"])]
    res = [state(ctx),
           bad("P6.tree-unchanged", "Files changed while reviewers ran (backend PLAYBOOK §4.4)", owner, changed)
           if changed else ok("P6.tree-unchanged", "Tree unchanged during review", owner),
           upstream(ctx, ["06-review-report.md"], owner)]
    if res[-1]["status"] == FAIL:
        return res, {}
    reqs = set(_reqs(ctx))
    problems = []
    for fid, f in docs.findings(ctx.doc("06-review-report.md")).items():
        if f.get("severity") not in ("blocker", "major", "minor"):
            problems.append(f"{fid}: severity {f.get('severity')!r}")
        m = re.fullmatch(r"`?([^`:\s]+):(\d+)(?:-\d+)?`?", (f.get("where") or "").strip())
        if not m:
            problems.append(f"{fid}: where {f.get('where')!r} is not path:line")
        else:
            p = ctx.project / m.group(1)
            if not p.is_file():
                problems.append(f"{fid}: {m.group(1)} does not exist")
            elif int(m.group(2)) > len(p.read_text(encoding="utf-8", errors="replace").splitlines()):
                problems.append(f"{fid}: line {m.group(2)} beyond end of {m.group(1)}")
        req = (f.get("req") or "").strip()
        ids = docs.ids_in(req, "REQ")
        if ids - reqs:
            problems.append(f"{fid}: unknown {sorted(ids - reqs)}")
        elif not ids and req.lower().split(" ")[0] not in NO_REQ and "none" not in req.lower():
            problems.append(f"{fid}: REQ column {req!r} names no REQ")
        if not f.get("scenario"):
            problems.append(f"{fid}: no failure scenario")
    res.append(bad("P6.findings", "Findings fail the format or point at nothing", owner, problems) if problems
               else ok("P6.findings", "Every finding is well-formed and anchored", owner))
    return res, {}


# ---------- Phase 7: acceptance ----------

def phase7(ctx):
    owner = "orchestrator"
    res = [state(ctx), upstream(ctx, ["07-acceptance.md"], owner)]
    latest = {p: read_json(ctx.gdir / f"{p}-latest.json") for p in ("p1", "p2", "p4", "p5", "p6")}
    problems = [f"{p}: {'never run' if r is None else r['overall']}" for p, r in latest.items()
                if r is None or r["overall"] not in (PASS, WAIVED)]
    if latest["p4"] and latest["p5"] and latest["p5"]["time"] < latest["p4"]["time"]:
        problems.append("p5 is older than the last p4: tests were not re-verified after the last code change")
    res.append(bad("P7.gates", "Earlier gates not green", owner, problems) if problems else
               ok("P7.gates", "All earlier gates green", owner))

    reqs = _reqs(ctx)
    des = docs.designs(ctx.doc("03-detailed-design.md") or "")
    tcs = docs.testcases(ctx.doc("04-test-plan.md") or "")
    p5 = (latest["p5"] or {}).get("data", {})
    observed, reported = p5.get("tc_observed", {}), p5.get("tc_reported", {})
    fx_obs = p5.get("fx_observed", {})
    rows, gaps = [], []
    for rid in sorted(docs.active_reqs(reqs)):
        d = sorted(k for k, v in des.items() if rid in v["serves"])
        t = sorted(k for k, v in tcs.items() if rid in v["verifies"])
        verdicts = {k: observed.get(k) or reported.get(k) or "no result" for k in t}
        fx = {k: fx_obs.get(k, "not observed") for k in (reqs[rid]["fixtures"] or [])}
        ok_all = t and all(v in ("passed", "pass") for v in verdicts.values()) and \
            all(v == "passed" for v in fx.values())
        fx_cell = ", ".join(f"{k} {v}" for k, v in fx.items()) or f"n/a: {reqs[rid]['fixtures_na'] or '—'}"
        rows.append(f"| {rid} | {', '.join(d) or '—'} | "
                    f"{', '.join(f'{k} {v}' for k, v in verdicts.items()) or '—'} | {fx_cell} | "
                    f"{'yes' if d and ok_all else 'NO'} |")
        if not d or not ok_all:
            gaps.append(f"{rid}: DES {d or 'none'}, TC {verdicts or 'none'}, FX {fx or 'n/a'}")
    matrix = ("| REQ | DES | TC result | Fixtures | Verified |\n|---|---|---|---|---|\n" + "\n".join(rows) + "\n")
    (ctx.gdir / "traceability.md").parent.mkdir(parents=True, exist_ok=True)
    (ctx.gdir / "traceability.md").write_text(matrix, encoding="utf-8")
    res.append(bad("P7.matrix", "Active REQs not verified end to end", owner, gaps) if gaps else
               ok("P7.matrix", f"{len(rows)} active REQs verified; matrix in {ctx.run_rel}/gates/traceability.md",
                  owner))
    open_f = [f"{k} ({v['severity']}): status {v.get('status')!r}"
              for k, v in docs.findings(ctx.doc("06-review-report.md")).items()
              if v.get("severity") in ("blocker", "major") and not FIX_STATUS.search(v.get("status") or "")]
    res.append(bad("P7.open-findings", "Blocker/major findings still open", owner, open_f) if open_f else
               ok("P7.open-findings", "No open blocker or major finding", owner))
    res.append(_log_trail(ctx))
    return res, {"not_machine_checked": [
        "Constitution §6.4: delivered thing run once through its real entry point (orchestrator shows evidence)",
        "Constitution §6.6: report states what the user must do to make it live",
        "Constitution §6.7: user accepted at Acceptance, with date"]}


PHASES = {"p1": phase1, "p2": phase2, "baseline": baseline, "p4": phase4,
          "p5": phase5, "p6": phase6, "p7": phase7}
