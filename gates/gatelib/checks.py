"""Computational checks, one function per gate. Each returns (results, data)."""
import hashlib
import json
import pathlib
import re
import shutil
import tempfile
import time

from . import capture, common, docs, runlog, runner, snap
from .common import (FAIL, PASS, ConfigError, bad, glob_match, na, ok, read_json, utc_now,
                     write_json)

CLOSED = re.compile(r"(?:fixed(?:\s+in\s+round\s+\d+)?|resolved|accepted)(?!\w)|已修复|已解决|已接受", re.I)
STILL_OPEN = re.compile(r"(?:open|not\s+fixed|not\s+resolved|unresolved|unfixed)(?!\w)|未修复|未解决", re.I)
NO_REQ = {"none", "n/a", "-", "—", "deferred", ""}
RUNS_ROOT = "docs/runs"


def runs_root(project):
    """The directory that holds every run (`<root>/<slug>/`), project-relative: `artifacts.run_dir`
    of the harness config, else docs/runs. Runs hold harness artifacts, not anyone's production work."""
    art = common.harness_cfg(project).get("artifacts")
    return str((art.get("run_dir") if isinstance(art, dict) else None) or RUNS_ROOT).strip("/")


def _status(status):
    """A finding's status as written, without markdown emphasis, backticks or surrounding space."""
    return re.sub(r"[*`]|(?<!\w)_+|_+(?!\w)", "", status or "").strip()


def finding_closed(status):
    """Closed only when the status starts with a closing word: `fixed` (`in round n`), `resolved`,
    `accepted`, or their Chinese forms. `not fixed`, `unresolved`, and the unfilled template line
    `open | fixed in round n | accepted as-is` are open."""
    s = _status(status)
    return "|" not in s and CLOSED.match(s) is not None


def finding_status(status):
    """How an open finding's status reads in a failure detail: `status 'open'`, or `unrecognised
    status '<text>'` when it is neither an open nor a closed form."""
    s = _status(status)
    known = not s or STILL_OPEN.match(s) is not None
    return f"status {status!r}" if known else f"unrecognised status {status!r}"


def ids_in_other_runs(ctx, names, prefix):
    """{id: run dir} for every PREFIX-nnn heading in NAMES in the project's other runs.
    Tests carry these ids project-wide, so a new run continues the numbering instead of restarting."""
    out = {}
    for name in names:
        for f in sorted((ctx.project / ctx.runs_root).glob(f"*/{name}")):
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
        self.runs_root = runs_root(self.project)
        # dry (`gate.py check`): no project command is run, no file written, no role snapshot read.
        self.dry = False
        # rebaseline: the user agreed to replace the baseline after work began (`baseline`).
        self.rebaseline = False

    def doc(self, name):
        return docs.read(self.run / name)

    def unsnapped(self):
        """Globs no snapshot holds: the gates' own books, and volatile_globs, the files the running
        product rewrites (logs, a local database); no agent's change."""
        return [f"{self.run_rel}/gates/**", *self.cfg.get("volatile_globs", [])]

    def snapshot(self):
        return snap.snapshot(self.project, self.unsnapped(), write_cache=not self.dry)

    def cmd(self, name):
        return (self.cfg.get("commands") or {}).get(name)

    def log(self, name):
        return self.gdir / "logs" / f"{utc_now().replace(':', '')}-{name}.log"

    def is_test(self, p):
        return glob_match(p, self.cfg["test_globs"])

    def is_doc(self, p):
        return glob_match(p, self.cfg["doc_globs"])

    def is_control(self, p):
        """Gate and team configuration: the orchestrator's, no writer's (ROLE.control)."""
        return glob_match(p, self.cfg.get("control_globs", []))


# ---------- shared ----------

def upstream(ctx, names, owner):
    missing = [n for n in names if not docs.nontrivial(ctx.doc(n), ctx.cfg["min_doc_lines"])]
    if missing:
        return bad("ALL.upstream", "Upstream document missing or near-empty", owner,
                   [f"{ctx.run_rel}/{n}" for n in missing])
    return ok("ALL.upstream", "Upstream documents present", owner)


STATE_KEYS = ("harness_version", "feature", "goal", "status", "tier", "scope", "models", "current_phase",
              "phases")
STATE_VALUES = {"status": ("in_progress", "blocked", "accepted", "abandoned", "prototype_confirmed"),
                "tier": ("small", "standard", "prototype", "full"),
                "scope": ("backend", "frontend", "cross-stack"),
                "risk": ("normal", "high")}


def state(ctx):
    """The run's state.json, one schema for every gate of both teams. Where the run is, is the step
    (`current_phase`, display only), never the status. The design keys are read only where an
    interface is designed: scope not backend, tier prototype or full."""
    s = read_json(ctx.run / "state.json")
    if s is None:
        return bad("ALL.state", "state.json missing", "orchestrator")
    if not isinstance(s, dict):
        return bad("ALL.state", "state.json is not a JSON object", "orchestrator")
    problems = [f"missing key: {k}" for k in STATE_KEYS if k not in s]
    g = s.get("goal")
    if "goal" in s and not (isinstance(g, dict) and g.get("change") and g.get("check")):
        problems.append("goal needs change and check, set by the user at kickoff (Constitution §7.4)")
    problems += [f"{k} must be {'|'.join(allowed)}, got {s[k]!r}" for k, allowed in STATE_VALUES.items()
                 if k in s and s[k] not in allowed]
    if not isinstance(s.get("phases", []), list):
        problems.append("phases must be a list")
    if s.get("scope") != "backend" and s.get("tier") in ("prototype", "full"):
        if "design" in s and s["design"] not in ("new", "external", "reused"):
            problems.append(f"design must be new|external|reused, got {s['design']!r}")
        if s.get("product_class") not in (None, "tool", "showcase"):
            problems.append(f"product_class must be tool|showcase, got {s['product_class']!r}")
        stops = (0,) if s.get("design") == "external" else (1, 2)
        if "design_stops" in s and s["design_stops"] not in stops:
            problems.append(f"design_stops must be {' or '.join(map(str, stops))} for design "
                            f"{s.get('design', 'new')!r}, got {s['design_stops']!r}")
    if problems:
        return bad("ALL.state", "state.json does not match the schema (PLAYBOOK §8)", "orchestrator", problems)
    return ok("ALL.state", "state.json valid", "orchestrator")


def _reqs(ctx):
    return docs.requirements(ctx.doc("01-requirements.md") or "")


REQ_FILES = ("01-requirements.md", "00-requirements.md")


def known_reqs(ctx, current):
    """REQ ids a design, test or finding may name: this run's, and those an earlier run defined (a
    regression of last round's behaviour names last round's REQ). Coverage still counts this run's."""
    return set(current) | set(ids_in_other_runs(ctx, REQ_FILES, "REQ"))


DRY = "not run by `check`"


def _command_check(ctx, name, owner):
    cmd = ctx.cmd(name)
    cid = f"CMD.{name}"
    if not cmd:
        if name in ctx.cfg["required_commands"]:
            return bad(cid, f"No {name} command configured, and it is required", "user"), None
        return na(cid, f"No {name} command configured", owner), None
    if ctx.dry:
        return na(cid, DRY, owner), None
    r = runner.run(cmd, ctx.project, ctx.cfg["timeout_seconds"], ctx.log(name))
    detail = [f"$ {cmd} -> exit {r['exit']} ({r['seconds']}s), log: {r['log']}"]
    if name != "build" and runner.did_not_run(r):
        return bad(f"TOOL.{name}", f"{name} did not run: no findings and no summary, so there is no reading "
                   "(fix the tool before reading its result; not waivable)", owner, detail + r["tail"][-15:]), r
    if r["exit"] != 0:
        return bad(cid, f"{name} failed", owner, detail + r["tail"][-15:]), r
    return ok(cid, f"{name} passed", owner, detail), r


def _junit_path(ctx):
    """Where the test runner writes its JUnit report.

    **Outside the project.** It used to be `<run-dir>/gates/junit.xml`, inside the
    repository being checked: a report full of test ids, which a project's own
    secret-scanning test then read as committable content and failed on (parametrize
    ids of the form `scrypt$16384$8$1$...`). A gate must not change what the suite it
    runs sees.
    """
    key = hashlib.sha256(str(ctx.project.resolve()).encode()).hexdigest()[:12]
    out = pathlib.Path(tempfile.gettempdir()) / "claude-gates" / key
    out.mkdir(parents=True, exist_ok=True)
    return out / f"{ctx.gdir.parent.name}-junit.xml"


def _test_run(ctx, cmd, command="test"):
    """(result, time it was first produced or None). The suite is the slowest reading a gate takes; a
    green run on the same code with the same command within `test_reuse_minutes` is reused, not
    repeated. Documents and the run dirs' books are not code: a handoff, a report or the code map
    edited since does not repeat the suite. A red one is always re-run: the fix may have been outside
    the tree. One entry per command (`test`, `fe_test`)."""
    books = run_dir_globs(ctx)
    tree = sorted((k, v) for k, v in ctx.snapshot().items() if not ctx.is_doc(k) and not glob_match(k, books))
    sig = hashlib.sha256(json.dumps([cmd, ctx.cfg.get("junit"), tree]).encode()).hexdigest()
    cache = ctx.gdir / "tests-cache.json"
    hits = read_json(cache) or {}
    hit = hits.get(command)
    if (isinstance(hit, dict) and hit.get("sig") == sig
            and time.time() - hit["epoch"] < 60 * ctx.cfg.get("test_reuse_minutes", 30)):
        return hit["result"], hit["time"]
    junit = _junit_path(ctx)
    r = runner.run_tests(cmd, ctx.project, ctx.cfg["timeout_seconds"], ctx.log(command),
                         junit if command == "test" else junit.with_name(f"{command}-{junit.name}"),
                         ctx.cfg.get("junit"))
    c = r["counts"]
    green = r["exit"] == 0 and not (c and (c["failed"] or c["errors"]))
    hits = {k: v for k, v in hits.items() if isinstance(v, dict) and "sig" in v and k != command}
    if green:
        hits[command] = {"sig": sig, "time": utc_now(), "epoch": time.time(),
                         "result": {k: v for k, v in r.items() if k != "output"}}
    write_json(cache, hits)
    return r, None


def _tests(ctx, owner, baseline=None, command="test"):
    """The suite, read against the baseline. `command` names the configured command to run: `test`,
    or `fe_test` where a project gives the frontend its own (its totals are not the baseline's, so
    only `test` is compared with the baseline's counts)."""
    cmd = ctx.cmd(command)
    if not cmd:
        return bad("CMD.test", f"No {command} command configured, and it is required", "user"), None
    if ctx.dry:
        return na("CMD.test", DRY, owner), None
    r, reused = _test_run(ctx, cmd, command)
    c = r["counts"]
    detail = [f"$ {r['cmd']} -> exit {r['exit']} ({r['seconds']}s), log: {r['log']}",
              f"counts: {c if c is not None else 'not parsed'}", f"per-test results: {r['junit_note']}"]
    if reused:
        detail.insert(0, f"reused the run of {reused}, not run now: same code and command (test_reuse_minutes); "
                         "anything outside the tree (a service, a model, a port) may differ")
    if r["exit"] != 0 and c is None and not r.get("started", True):
        return bad("TOOL.test", "tests did not run: the command did not start or printed nothing "
                   "(fix the runner before reading a result; not waivable)", owner, detail + r["tail"][-15:]), r
    problems = []
    if r["exit"] != 0 or (c and (c["failed"] or c["errors"])):
        problems.append("tests are red")
        detail += [f"failed: {t}" for t in r["failed_tests"][:20]] or r["tail"][-15:]
    if baseline and c and baseline.get("counts") and command == "test":
        b = baseline["counts"]
        if runner.total(c) < runner.total(b):
            problems.append(f"test total fell from {runner.total(b)} to {runner.total(c)}")
        skipped_now, skipped_then = c["skipped"] + c["xfailed"], b["skipped"] + b["xfailed"]
        if skipped_now > skipped_then:
            problems.append(f"skipped/xfailed rose from {skipped_then} to {skipped_now}")
    if problems:
        res = bad("CMD.test", "; ".join(problems), owner, detail)
        # What a waiver must name (gate.py apply_waivers): the failing tests, and nothing else wrong.
        res["failed_tests"], res["other_problems"] = r["failed_tests"], [p for p in problems if p != "tests are red"]
        return res, r
    return ok("CMD.test", "tests green", owner, detail), r


RETIRED_TESTS = r"retired tests|退役的?测试|废弃的?测试"
PLAN_DOCS = ("plan.md", "03-detailed-design.md", "08-implementation-log.md")


def _retired_tests(ctx):
    """The text under every `Retired tests` heading, and of every `Retired tests:` line with the
    list below it, in the plan documents: tests removed with the code they covered."""
    out = []
    for name in PLAN_DOCS:
        text = ctx.doc(name) or ""
        hs = docs.headings(text)
        for i, (lvl, title, start, _) in enumerate(hs):
            if re.search(RETIRED_TESTS, title, re.I):
                out.append(text[start:next((st for l, _, st, _ in hs[i + 1:] if l <= lvl), len(text))])
        out += [m.group(0) for m in re.finditer(
            r"^[ \t]*(?:[-*+][ \t]+)?\**(?:%s)\**[ \t]*[:：].*(?:\n[ \t]*[-*+][ \t]+.*)*" % RETIRED_TESTS,
            docs.mask_code(text), re.I | re.M)]
    return "\n".join(out)


def _test_file_drift(ctx, baseline, owner, cid):
    files = snap.list_files(ctx.project)
    now = runner.test_file_stats(ctx.project, files, ctx.cfg)
    then = baseline.get("test_files", {})
    retired = _retired_tests(ctx)
    problems = []
    for f, s in then.items():
        cur = now.get(f)
        if f in retired and (cur is None or cur["tests"] < s["tests"]):
            pass  # removed with the code it covered, and the plan says so
        elif cur is None and s["tests"]:
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


MARK_HOW = ("the dispatch hook takes a role's mark when it is dispatched; by hand "
            "(`gate.py mark --role <agent>`) only to repair a run whose hook did not fire")


def _load_mark(ctx, role):
    m = read_json(ctx.gdir / f"snap-{role}.json")
    if m is None:
        raise ConfigError(f"no mark for {role}: {MARK_HOW}")
    return m


def _is_reviewer(role):
    """Review coordinators and panelists: their mark guards the tree, not a writer."""
    return role in ("be-reviewer", "fe-reviewer") or role.startswith(("be-review-", "fe-review-"))


def run_dir_globs(ctx):
    """Every run under the runs root, this one and the earlier ones: their documents and books (run
    logs, state, handoff) are nobody's production work, and hooks and the orchestrator write them
    while agents work."""
    return sorted({f"{ctx.runs_root}/**", f"{ctx.run_rel}/**"})


def _other_run(ctx, path):
    """A file of another run under the runs root: harness artifacts, never charged to a role of this run."""
    return glob_match(path, [f"{ctx.runs_root}/**"]) and not glob_match(path, [f"{ctx.run_rel}/**"])


def _latest_writer(ctx):
    marks = [read_json(p) for p in ctx.gdir.glob("snap-*.json")]
    marks = [m for m in marks if m and not _is_reviewer(m["role"])]
    if not marks:
        raise ConfigError(f"no writer mark: {MARK_HOW}")
    return max(marks, key=lambda m: m["time_ns"])


def _plan_text(ctx, role=None):
    """The documents that may name a file an engineer changes. A frontend run's backend-side queue
    rows name their files in 03-queue.md; a Standard change names its files in plan.md."""
    names = ("03-queue.md", "plan.md") if role == "fe-engineer" else (
        "03-detailed-design.md", "08-implementation-log.md", "03-queue.md", "plan.md")
    return "".join(ctx.doc(n) or "" for n in names)


# Analysts and architects write documents (the analyst also fixture candidates), never code or tests.
DOC_WRITERS = ("be-analyst", "be-architect")
BUILDERS = ("be-developer", "fe-engineer")


def _doc_writer_may(ctx, role, path):
    return ctx.is_doc(path) or (role == "be-analyst" and glob_match(path, [f"{_fx_cand(ctx)}/**"]))


# ---------- failures that outlive a re-dispatch ----------

ROLE_OPEN = "role-open.json"
CARRIED = " — carried from an earlier run"


def carry(ctx, cid, role, paths, before_snapshot, resolved=None):
    """The paths still failing check `cid`: `paths` (what this evaluation found against
    `before_snapshot`), and what an earlier evaluation found and nobody has undone since, suffixed
    CARRIED. Every dispatch takes a new snapshot, so without this ledger (<run>/gates/role-open.json)
    handing a failure back to its owner would clear it.

    A recorded path is resolved when the file is back to the hash it had in the snapshot it first
    failed against (gone again, if it did not exist then), or `resolved(path)` says so (ROLE.unplanned:
    the plan names it now). A resolved path is not returned even when `paths` holds it (a writer
    undoing its own change differs from its newer snapshot), and its record is dropped once `paths`
    no longer does.

    `*.tree-unchanged` (the tree held still while reviewers ran; `role` is the coordinator whose mark
    guards it): a builder dispatched since may change any file, and its changes are its role checks'
    to judge. So a record ends with the next builder dispatch after it (its log seq is kept with it),
    and nothing is recorded once a builder was dispatched after the reviewers' mark.

    Nothing is written when `ctx.dry`."""
    path_ = ctx.gdir / ROLE_OPEN
    ledger = read_json(path_) or []
    mine = {e["path"]: e for e in ledger if e["check"] == cid}
    tree = cid.endswith(".tree-unchanged")
    events = runlog.events(ctx.run / "run-log.jsonl") if tree else []
    now = max((ev.get("seq", 0) for ev in events), default=0)
    marked = max((ev.get("seq", 0) for ev in events if ev.get("event") == "mark" and ev.get("role") == role),
                 default=0)

    def built_after(seq):
        return any(ev.get("event") == "dispatch" and ev.get("agent") in BUILDERS and ev.get("seq", 0) > seq
                   for ev in events)
    ended = {p for p, e in mine.items() if tree and built_after(e.get("seq", now))}
    fresh, done = [], set()
    for p, e in mine.items():
        f = ctx.project / p
        if (snap.file_sha(f) if f.is_file() else None) == e["hash"] or (resolved and resolved(p)):
            done.add(p)
    if not (tree and built_after(marked)):
        fresh = [{"check": cid, "role": role, "path": p, "hash": before_snapshot.get(p), **({"seq": now} if tree else {})}
                 for p in paths if p not in mine or p in ended]
    kept = [e for e in ledger if e["check"] != cid
            or (e["path"] not in ended and (e["path"] not in done or e["path"] in paths))] + fresh
    if kept != ledger and not ctx.dry:
        write_json(path_, kept)
    return ([p for p in paths if p not in done or p in ended]
            + sorted(f"{p}{CARRIED}" for p in mine if p not in done | ended and p not in paths))


def _role_result(ctx, cid, role, paths, before, fail, passed, resolved=None):
    """One role check with what it carries; a carried path is owed by the role it was recorded for."""
    open_ = carry(ctx, cid, role, paths, before, resolved)
    if not open_:
        return ok(cid, passed, role)
    owners = {e["role"] for e in read_json(ctx.gdir / ROLE_OPEN) or [] if e["check"] == cid
              and f"{e['path']}{CARRIED}" in open_}
    return bad(cid, fail, "+".join(sorted(owners | {role})), open_)


def _carried_only(ctx, res):
    """Role failures recorded for a check this evaluation did not make (another role was dispatched
    since): still failing, owed by the role recorded."""
    ledger = read_json(ctx.gdir / ROLE_OPEN) or []
    seen, plan = {r["id"] for r in res}, _plan_text(ctx)
    out = []
    for cid in sorted({e["check"] for e in ledger if e["check"].startswith("ROLE.")} - seen):
        roles = sorted({e["role"] for e in ledger if e["check"] == cid})
        open_ = carry(ctx, cid, roles[0], [], {},
                      (lambda p: _mentioned(p, plan)) if cid == "ROLE.unplanned" else None)
        if open_:
            out.append(bad(cid, "Changes an earlier dispatch made outside its role are still in the tree",
                           "+".join(roles), open_))
    return out


CONTROL_MSG = "gate and team configuration is the orchestrator's"


def _split_control(ctx, d):
    """(the diff without control files, the control files changed)."""
    control = [p for p in snap.changed(d) if ctx.is_control(p)]
    return {k: [p for p in v if p not in control] for k, v in d.items()}, control


def _role_rules(ctx, role, d):
    """What `role` may not have changed among the changes `d` (a snap.diff, control files left out):
    [(check id, the paths at fault, failure message, pass message, resolved)], [] for a role without
    rules. `resolved(path)` says a recorded path is settled now (ROLE.unplanned: the plan names it)."""
    ch = snap.changed(d)
    if role in BUILDERS:
        plan = _plan_text(ctx, role)
        tests = [p for p in d["modified"] + d["deleted"] if ctx.is_test(p)]
        unplanned = [p for p in ch if not ctx.is_test(p) and not ctx.is_doc(p) and not _mentioned(p, plan)]
        rules = [("ROLE.tests", tests, f"{role} modified or deleted existing tests",
                  f"No existing test changed by {role}", None)]
        if role == "be-developer":
            fe = [p for p in ch if glob_match(p, ctx.cfg["frontend_globs"])]
            return [("ROLE.frontend", fe, "be-developer changed frontend files (PLAYBOOK §3C)",
                     "No frontend file changed by be-developer", None), *rules,
                    ("ROLE.unplanned", unplanned, "Changed files named in none of 03-detailed-design.md, "
                     "08-implementation-log.md, 03-queue.md, plan.md (log the deviation or get a design amendment)",
                     "Every changed file is planned or logged", lambda p: _mentioned(p, plan))]
        return [*rules, ("ROLE.unplanned", unplanned, "Changed files not named in 03-queue.md (a row or § Scaffold) "
                         "or plan.md", "Every changed file is named in a queue row or the plan",
                         lambda p: _mentioned(p, plan))]
    if role in ("be-tester", "fe-tester"):
        return [("ROLE.tester-scope", [p for p in ch if not ctx.is_test(p) and not ctx.is_doc(p)],
                 f"{role} changed non-test files", f"{role} changed only tests and documents", None)]
    if role in ("fe-ux", "fe-ui"):
        return [("ROLE.designer-scope", [p for p in ch if not glob_match(p, [f"{ctx.run_rel}/**"])],
                 f"{role} changed files outside {ctx.run_rel}/", f"{role} changed only design documents", None)]
    if role in DOC_WRITERS:
        what = "documents and fixture candidates" if role == "be-analyst" else "documents"
        return [("ROLE.doc-scope", [p for p in ch if not _doc_writer_may(ctx, role, p)],
                 f"{role} changed files other than {what}", f"{role} changed only {what}", None)]
    return []


def role_checks(ctx):
    """Role rules for the most recently marked writer, on exactly its own changes since its mark.
    Only a writer in the run's tree has a mark; one in a worktree is judged when it is landed
    (`role_paths`). A failure stays until it is undone (`carry`)."""
    if ctx.dry:
        return [na("ROLE.changes", DRY, "orchestrator")], []
    try:
        m = _latest_writer(ctx)
    except ConfigError:
        writers = [ev for ev in _events(ctx) if ev.get("event") == "dispatch" and ev.get("agent") in runlog.WRITERS]
        if not writers or not all(ev.get("isolated") or ev.get("worktree") for ev in writers):
            raise
        return [ok("ROLE.changes", "Every writer of this run worked in a worktree: judged when landed "
                   "(`gate.py land`)", "orchestrator")], []
    role, before = m["role"], m["snapshot"]
    d = snap.diff(before, ctx.snapshot())
    # Fixtures are the backend roles' and the user's (`fixtures-approve` moves them while a frontend
    # role is out): never charged to a frontend role.
    fixtures = [f"{_fx_dir(ctx)}/**", f"{_fx_cand(ctx)}/**"] if role.startswith("fe-") else []
    d = {k: [p for p in v if not _other_run(ctx, p) and not glob_match(p, fixtures)] for k, v in d.items()}
    every = snap.changed(d)
    d, control = _split_control(ctx, d)
    res = [_role_result(ctx, cid, role, paths, before, fail, passed, resolved)
           for cid, paths, fail, passed, resolved in _role_rules(ctx, role, d)]
    res = res or [na("ROLE.none", f"No role rules for {role}", role)]
    res.append(_role_result(ctx, "ROLE.control", role, control, before,
                            f"{role} changed control files: {CONTROL_MSG}", "No control file changed"))
    return res + _carried_only(ctx, res), every


def role_paths(ctx, role, paths):
    """Of `paths` (everything one dispatch of `role` changed, as `gate.py land` reads it from the
    writer's worktree), those the role may not change: what its ROLE.* checks fail on, control files,
    and the run's books that only the gates write (the run log, gates/**). [] when all are its own.
    A test counts as existing, so as modified, when the commit `ctx.project` is on holds it."""
    books = [p for p in paths if glob_match(p, [f"{ctx.run_rel}/run-log.jsonl", f"{ctx.run_rel}/gates/**"])]
    paths = [p for p in dict.fromkeys(paths)
             if not _other_run(ctx, p) and not glob_match(p, ctx.cfg.get("volatile_globs", []))]
    tests = [p for p in paths if ctx.is_test(p)]
    if ctx.git and tests:
        held = set(snap.git(ctx.project, "ls-tree", "-r", "-z", "--name-only", "HEAD", "--", *tests).stdout.split("\0"))
    else:
        held = {p for p in tests if (ctx.project / p).is_file()}
    d, control = _split_control(ctx, {"added": [p for p in paths if p not in held],
                                      "modified": [p for p in paths if p in held], "deleted": []})
    return sorted({*books, *control, *(p for _, found, *_ in _role_rules(ctx, role, d) for p in found)})


def forgive(ctx, paths):
    """After a worktree's work is merged into the run's tree: every writer's mark takes the landed
    paths as they are now, so the next role check does not charge them to the role that holds the
    mark. A reviewer's mark is left alone: it guards the tree while reviewers read it, and a merge
    then is a change under them."""
    skip = ctx.unsnapped()
    paths = [p for p in paths if not glob_match(p, skip) and not snap.skipped(p, tracked=True)]
    for f in sorted(ctx.gdir.glob("snap-*.json")):
        m = read_json(f)
        if not isinstance(m, dict) or not isinstance(m.get("snapshot"), dict) or _is_reviewer(str(m.get("role"))):
            continue
        now = dict(m["snapshot"])
        for p in paths:
            if (ctx.project / p).is_file():
                now[p] = snap.file_sha(ctx.project / p)
            else:
                now.pop(p, None)
        if now != m["snapshot"]:
            write_json(f, {**m, "snapshot": now})


def role_if(ctx, role):
    """Role rules when `role` is the most recently marked writer; nothing otherwise."""
    if ctx.dry:
        return role_checks(ctx)[0]
    try:
        latest = _latest_writer(ctx)
    except ConfigError:
        return []
    return role_checks(ctx)[0] if latest["role"] == role else []


def _baseline(ctx):
    b = read_json(ctx.gdir / "baseline.json")
    if b is None:
        raise ConfigError("no baseline: run `gate.py baseline` before the run's first code writer is dispatched")
    return b


def _mentioned(path, text):
    return path in text or pathlib.PurePath(path).name in text


# ---------- run log ----------

def _events(ctx):
    return runlog.events(ctx.run / "run-log.jsonl")


def _team_dispatches(ctx, events, team="be"):
    """The dispatches of one team (`runlog.team_of`): both teams log into the one run log, and each
    numbers its own steps, so a trail reads only its own team's."""
    scope = (read_json(ctx.run / "state.json") or {}).get("scope")
    return [e for e in events if e.get("event") == "dispatch" and runlog.team_of(e.get("agent") or "", scope) == team]


def log_valid(ctx):
    path = ctx.run / "run-log.jsonl"
    if not path.exists():
        return bad("LOG.valid", "No run log: log every dispatch and return (`gate.py log dispatch …`)",
                   "orchestrator")
    found = runlog.problems(path)
    return (bad("LOG.valid", "Run log invalid or tampered", "orchestrator", found) if found
            else ok("LOG.valid", "Run log intact", "orchestrator"))


def demo(ctx):
    """Constitution §1: the goal's real entry point captured before the work and after it
    (ORCHESTRATOR.md § Demo). One demo per run, whichever teams work in it."""
    probs = capture.demo_problems(ctx, ctx.run, runlog.events(ctx.run / "run-log.jsonl"))
    return (bad("DEMO", "No before/after evidence of the goal at its real entry point", "orchestrator", probs)
            if probs else ok("DEMO", f"Before and after in {ctx.run_rel}/evidence/demo-*", "orchestrator"))


CODEMAP = "docs/codemap.md"
CODEMAP_DIR = "docs/codemap"
BACKTICK = re.compile(r"`([^`\s]+)`")
CODE_READERS = ("be-analyst", "be-architect", "be-developer", "be-tester", "fe-engineer", "fe-tester")


def _looks_like_path(ctx, p):
    """A backticked token the map means as a path: it has a `/` and its first segment is in the
    project root (`src/x/`, `calc/core.py`). Bare names, symbols, routes, commands and word pairs
    (`core.py`, `useAuth`, `/api/x`, `input/output`) are not checked."""
    return ("/" in p and "*" not in p and not p.startswith("/")
            and (ctx.project / p.split("/")[0]).exists())


def _map_problems(ctx, text, cap):
    """Dead paths and the line cap of one code-map file. `<file>:<symbol>` is read as its file."""
    tokens = {re.split(r"[:#(]", p)[0] for p in BACKTICK.findall(text)}
    gone = sorted({t.rstrip("/") for t in tokens if _looks_like_path(ctx, t)} - {""})
    lines = len(text.splitlines())
    return ([f"{p}: no such path" for p in gone if not (ctx.project / p).exists()]
            + ([f"{lines} lines, cap {cap}"] if lines > cap else []))


def _handoff_key(heading):
    """The role a handoff section belongs to. `orchestrator for <agent> #n` (written for an agent
    that died) is its own key: neither the orchestrator's section nor that agent's."""
    words = heading.split("·")[0].split()
    if not words:
        return "?"
    return " ".join(words[:3]) if words[:2] == ["orchestrator", "for"] and len(words) > 2 else words[0]


def context_files(ctx):
    """Constitution §8: the code map agents read first, and a handoff that holds only the current
    state, one section per role (route/HANDOFF.md §1, §7). The map is owed by the writer that reads
    code and was dispatched last (in the run's tree or in a worktree); designers and reviewers never
    write outside their own files. The map may point to per-module files docs/codemap/<name>.md: each
    is held to the same cap and the same path check."""
    owner = next((ev["agent"] for ev in reversed(_events(ctx))
                  if ev.get("event") == "dispatch" and ev.get("agent") in CODE_READERS), None)
    budget = {"codemap_lines": 200, "handoff_section_lines": 20, **ctx.cfg.get("doc_budgets", {})}
    text, res = docs.read(ctx.project / CODEMAP), []
    if owner is None:
        res.append(na("CTX.codemap", f"{CODEMAP} is checked once a role that reads code has worked", "orchestrator"))
    elif text is None:
        res.append(bad("CTX.codemap", f"{CODEMAP} missing: the next writer creates it (route/HANDOFF.md §7)", owner))
    else:
        problems = _map_problems(ctx, text, budget["codemap_lines"])
        for f in sorted((ctx.project / CODEMAP_DIR).glob("*.md")):
            problems += [f"{CODEMAP_DIR}/{f.name}: {x}"
                         for x in _map_problems(ctx, docs.read(f) or "", budget["codemap_lines"])]
        res.append(bad("CTX.codemap", f"{CODEMAP} out of date or too long (route/HANDOFF.md §7)", owner, problems)
                   if problems else ok("CTX.codemap", f"{CODEMAP} paths exist, within its cap", owner))
    text = ctx.doc("handoff.md")
    if text is None:
        res.append(na("CTX.handoff", "No handoff.md in this run dir yet", "orchestrator"))
        return res
    sections, cur = {}, None
    for line in text.splitlines():
        if line.startswith("## "):
            cur = _handoff_key(line[3:])
            sections.setdefault(cur, []).append(0)
        elif cur and line.strip():
            sections[cur][-1] += 1
    cap = budget["handoff_section_lines"]
    problems = [f"{r}: {len(n)} sections, keep only the latest" for r, n in sections.items() if len(n) > 1]
    problems += [f"{r}: {max(n)} lines, cap {cap}" for r, n in sections.items() if max(n) > cap]
    res.append(bad("CTX.handoff", "handoff.md must hold one current section per role (route/HANDOFF.md §1)",
                   "orchestrator", problems) if problems
               else ok("CTX.handoff", f"handoff.md: {len(sections)} current sections", "orchestrator"))
    return res


def control_files(ctx):
    """The gates' own books and configuration are the orchestrator's: an agent that changed one while
    it was out (the return hook lists them as `control_changed`) leaves every gate red until the
    orchestrator has restored the file and the user has waived what is settled."""
    found = [f"#{ev.get('seq')} {ev.get('agent')}: {p}" for ev in runlog.events(ctx.run / "run-log.jsonl")
             if ev.get("event") == "return" for p in ev.get("control_changed") or []]
    return [bad("CTRL.files", "Gate books or configuration changed while an agent was out: restore what "
                "the agent changed, then ask the user to waive this record (`gate.py waive`)",
                "orchestrator", found) if found
            else ok("CTRL.files", "No agent changed gate books or configuration", "orchestrator")]


def _trail_common(events):
    """Every dispatch returned; every writer mark was followed by a dispatch of its role before the
    next gate run. Several marks may precede their dispatches (two hooks racing), and a mark taken
    again before its dispatch (by hand, then by the hook) is not a mark without one."""
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
                if e["event"] == "gate":
                    break
                if e["event"] == "dispatch" and e["agent"] == ev["role"]:
                    dispatched = True
                    break
            if not dispatched:
                problems.append(f"#{ev['seq']}: mark for {ev['role']} not followed by its dispatch")
    return problems


def _prototype_first(ctx, events, design_phases):
    """Full-development runs: the user confirms a prototype before the backend design
    (Constitution §2.7). `design_phases` are backend steps: only backend dispatches are read."""
    if (read_json(ctx.run / "state.json") or {}).get("tier") != "full":
        return []
    proto = next((e["seq"] for e in events if e["event"] == "human" and e["stop"] == "Prototype"
                  and e["decision"] == "approved"), None)
    design = next((e["seq"] for e in _team_dispatches(ctx, events) if str(e["phase"]) in design_phases), None)
    if proto is None:
        return ["no approved Prototype stop in the log"]
    if design is not None and design < proto:
        return [f"design dispatched (#{design}) before the Prototype was approved (#{proto})"]
    return []


def _log_trail(ctx, design_phases=("2",)):
    """Backend trail: the common checks, then the Plan approved before build and (full tier) the
    Prototype approved before design (`design_phases`), read from the backend team's dispatches.
    The Frontend team has its own trail (frontend._trail) over its own."""
    events = _events(ctx)
    owner, problems = "orchestrator", _trail_common(events)
    plan = next((e["seq"] for e in events if e["event"] == "human" and e["stop"] == "Plan"
                 and e["decision"] == "approved"), None)
    # Phase 1b prototype dispatches are throwaway work and may precede the Plan (route/PROTOTYPE.md).
    build = next((e["seq"] for e in _team_dispatches(ctx, events)
                  if e["agent"] in BUILDERS and str(e["phase"]) != "1b"), None)
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
    res += role_if(ctx, owner)
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
    known = known_reqs(ctx, reqs)
    bad_serves = [f"{d}: serves {sorted(v['serves']) or 'nothing'}" for d, v in des.items()
                  if not v["serves"] or not v["serves"] <= known]
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
    events = runlog.events(ctx.run / "run-log.jsonl")
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

def _work_since_baseline(ctx):
    """Writers dispatched after the last `baseline` gate run, as `#seq agent`."""
    events = runlog.events(ctx.run / "run-log.jsonl")
    last = max((i for i, ev in enumerate(events) if ev.get("event") == "gate" and ev.get("gate") == "baseline"),
               default=None)
    if last is None:
        return []
    return [f"#{ev.get('seq')} {ev['agent']}" for ev in events[last + 1:]
            if ev.get("event") == "dispatch" and not _is_reviewer(ev.get("agent") or "")]


def baseline(ctx):
    since = _work_since_baseline(ctx) if (ctx.gdir / "baseline.json").exists() and not ctx.dry else []
    if since and not ctx.rebaseline:
        raise ConfigError(f"a baseline exists and work has begun since ({', '.join(since[:5])}): a new one "
                          "would take the tree as it is now for the start, and hide every test removed or "
                          "skipped and every file changed since. If the user agreed to start over from this "
                          "tree, run `baseline --rebaseline`")
    res = []
    if ctx.git:
        dirty = [p for p in snap.dirty_paths(ctx.project)
                 if not glob_match(p, [*run_dir_globs(ctx), ".claude/**",
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
    if not ctx.dry:
        write_json(ctx.gdir / "baseline.json", data)
    return res, {"head": data["head"], "counts": data["counts"]}


def mark(ctx, role):
    if ctx.dry:
        return [na("MARK", DRY, "orchestrator")], {}
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


def _scan(ctx, base, run_diff, owner="be-developer"):
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
    return [bad("P4.secrets", "Possible secret in new code", owner, hits_s) if hits_s else
            ok("P4.secrets", "No secret patterns in new code", owner),
            bad("P4.personal-paths", "Absolute personal path in new code", owner, hits_p) if hits_p else
            ok("P4.personal-paths", "No absolute personal paths in new code", owner)]


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
    known = known_reqs(ctx, reqs)
    bad_tc = [f"{t}: verifies {sorted(v['verifies']) or 'nothing'}, mode {v['mode']}" for t, v in tcs.items()
              if not v["verifies"] or not v["verifies"] <= known or v["mode"] is None]
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
    """{FX: {REQ, ...}} for the active REQs of this round.

    One fixture may serve several REQs, so the value is the whole set of
    declaring REQs. It used to be a single REQ picked by iterating
    `active_reqs()`, which is a set: with more than one declarer the winner
    moved with the process hash seed, and PLAN.meta could not be stably green.
    """
    reqs = _reqs(ctx)
    out: dict[str, set[str]] = {}
    for r in docs.active_reqs(reqs):
        for fx in (reqs[r]["fixtures"] or []):
            out.setdefault(fx, set()).add(r)
    return out


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
    problems += [f"{fx} ({', '.join(sorted(r))}): declared but never approved at Plan"
                 for fx, r in _declared_fx(ctx).items() if fx not in man["cases"]]
    # The manifest holds the hashes the files are compared with: it is itself compared with the hash
    # the approval left in the run log, which no writer's edit of both can follow.
    locked = _last_approval(ctx, "manifest_sha")
    f = base / "APPROVED.json"
    if locked and (not f.exists() or _sha(f) != locked["manifest_sha"]):
        problems.append(f"APPROVED.json: {'changed' if f.exists() else 'missing'} since the approval logged "
                        f"at #{locked.get('seq')}")
    return (bad(cid, "Approved fixtures changed or missing (re-lock: the user's yes, or --because a newer decision)",
                owner, problems)
            if problems else ok(cid, f"{len(man['cases'])} approved fixtures intact", owner))


def _last_approval(ctx, key):
    """The run log's last `approve` event that carries `key`, or None."""
    return next((ev for ev in reversed(runlog.events(ctx.run / "run-log.jsonl"))
                 if ev.get("event") == "approve" and ev.get(key) is not None), None)


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
    if ctx.dry:
        res += role_checks(ctx)[0]
    else:
        marks = [read_json(p) for p in ctx.gdir.glob("snap-*.json")]
        if any(m and not _is_reviewer(m["role"]) for m in marks):
            res += role_checks(ctx)[0]
    man, cand = _manifest(ctx), ctx.project / _fx_cand(ctx)
    declared = _declared_fx(ctx)
    missing_in, missing_out, bad_meta, to_approve = [], [], [], []
    sheet = _plan_summary(ctx) + ["## Fixtures", "",
             "Approve, edit or reject each case. Approved cases become the answers every later test must match.",
             ""]
    for fx, req_set in sorted(declared.items()):
        req = ", ".join(sorted(req_set))
        d = cand / fx
        if not d.exists() and fx in man["cases"]:
            continue  # approved in an earlier round, unchanged
        ins, exps = sorted(d.glob("input*")), sorted(d.glob("expected*"))
        meta = read_json(d / "meta.json", {}) if d.exists() else {}
        if not ins:
            missing_in.append(f"{fx} ({req}): no {_fx_cand(ctx)}/{fx}/input.*")
        if not exps:
            missing_out.append(f"{fx} ({req}): no {_fx_cand(ctx)}/{fx}/expected.*")
        if d.exists() and (meta.get("req") not in req_set or not _valid_compare(meta.get("compare"))
                           or not meta.get("source")):
            bad_meta.append(f"{fx}: meta.json needs req in {{{req}}}, source, compare in "
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
    if not ctx.dry:
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


def approve_fixtures(ctx, by, reapprove, because=None):
    """Lock the candidates the user approved at Plan, or re-lock answers a newer decision replaced
    (`because`: whose words, when; Constitution §5). Never run otherwise."""
    plan = read_json(ctx.gdir / "p2-latest.json")
    if not plan or plan["overall"] != PASS:
        raise ConfigError("`p2` has not passed; run it and get the user's approval first")
    man, base, cand = _manifest(ctx), ctx.project / _fx_dir(ctx), ctx.project / _fx_cand(ctx)
    todo = plan["data"]["to_approve"]
    blocked = [fx for fx in todo if fx in man["cases"] and fx not in reapprove]
    if blocked:
        raise ConfigError(f"{blocked} change already-approved answers; pass --reapprove {' '.join(blocked)} "
                          "after the user has seen the difference, or with --because naming the newer decision "
                          "that replaces them")
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
                            "approved_by": by, "date": date, "files": files, **({"because": because} if because else {}),
                            "history": (prev.get("history", []) + [{k: prev[k] for k in ("date", "approved_by", "files")}])
                            if prev else []}
        shutil.rmtree(src)
    write_json(base / "APPROVED.json", man)
    res = ok("PLAN.approve", f"Locked {len(todo)} fixtures, approved by {by} on {date}", "orchestrator", todo)
    # For the `approve` event: what was locked, and the scope the user approved with it.
    res["manifest_sha"] = _sha(base / "APPROVED.json")
    res["active_reqs"] = sorted(docs.active_reqs(_reqs(ctx)))
    return [res], {}


def _fixture_use(ctx, cases, why="no per-test report"):
    """Every approved fixture is referenced by a test (tagged FX-nnn) that passes in this run. `why`:
    the reason there are no per-test results (`cases` is None), with what to configure."""
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
        return na("P5.fixtures-used", f"Fixtures referenced; whether their tests pass is not read: {why}",
                  "be-tester"), {}
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
        res[-1]["failed_tests"] = [t for t, st in observed.items() if st != "passed"]
    else:
        res.append(na("P5.tc-results", f"No per-test results in this run: {runner.no_cases(r)}", "be-tester"))

    reported = docs.report_results(ctx.doc("05-test-report.md"))
    missing = [f"{t}: no verdict" for t in tcs if t not in reported]
    missing += [f"{t}: rows disagree ({v[10:]}); keep one current verdict per TC" for t, v in sorted(reported.items())
                if v.startswith("conflict")]
    res.append(bad("P5.report-complete", "TCs without one pass/fail/blocked verdict in 05-test-report.md",
                   "be-tester", missing) if missing else
               ok("P5.report-complete", "Every TC has a verdict in the report", "be-tester"))
    false_pass = [f"{t}: reported pass, observed {observed[t]}" for t, v in reported.items()
                  if v == "pass" and observed.get(t) not in (None, "passed")]
    unseen = sorted(t for t, v in reported.items() if v == "pass" and tcs.get(t, {}).get("mode") == "automated"
                    and t not in observed)
    res.append(bad("P5.report-honest", "Report claims passes this run did not observe (Constitution §2.3)",
                   "be-tester", false_pass) if false_pass else
               na("P5.report-honest", "Reported passes could not be compared: this run observed no result for "
                  f"them ({runner.no_cases(r)})", "be-tester", unseen) if unseen and not observed else
               ok("P5.report-honest", "Reported passes match observed results", "be-tester",
                  [f"not observed this run: {t}" for t in unseen]))
    res.append(_fixture_integrity(ctx, "P5.fixtures", "be-tester"))
    use, fx_observed = _fixture_use(ctx, r.get("cases") if r else None, runner.no_cases(r))
    res.append(use)
    return res, {"tc_observed": observed, "tc_reported": reported, "fx_observed": fx_observed,
                 "counts": r["counts"] if r else None}


# ---------- Phase 6: review ----------

def _panel_check(ctx):
    """Two or more panelists leave candidates someone must merge and try to disprove: `be-reviewer`,
    dispatched after them. One panelist is the sole reviewer and needs no coordinator. The review
    read is that of the current build: the dispatches since the last be-developer dispatch."""
    owner, events = "orchestrator", runlog.events(ctx.run / "run-log.jsonl")
    built = max((i for i, e in enumerate(events) if e.get("event") == "dispatch"
                 and e.get("agent") == "be-developer"), default=-1)
    out = [(i, e["agent"]) for i, e in enumerate(events[built + 1:]) if e.get("event") == "dispatch"]
    panel = sorted({a for _, a in out if a.startswith("be-review-")})
    last = max((i for i, a in out if a.startswith("be-review-")), default=-1)
    merged = any(a == "be-reviewer" and i > last for i, a in out)
    if len(panel) > 1 and not merged:
        return bad("P6.panel", f"{len(panel)} panelists ran and no be-reviewer merged their candidates after "
                   "them (backend PLAYBOOK Phase 6)", owner, panel)
    return ok("P6.panel", "No panel to merge" if not panel else f"Panel: {', '.join(panel)}"
              + (", the sole reviewer" if len(panel) == 1 and not merged else ", merged by be-reviewer"), owner)


def phase6(ctx):
    owner = "orchestrator"
    if ctx.dry:
        tree = na("P6.tree-unchanged", DRY, owner)
    else:
        before = _load_mark(ctx, "be-reviewer")["snapshot"]
        d = snap.diff(before, ctx.snapshot())
        changed = carry(ctx, "P6.tree-unchanged", "be-reviewer",
                        [p for p in snap.changed(d) if not glob_match(p, run_dir_globs(ctx))], before)
        tree = (bad("P6.tree-unchanged", "Files changed while reviewers ran (backend PLAYBOOK §4.4)", owner, changed)
                if changed else ok("P6.tree-unchanged", "Tree unchanged during review", owner))
    res = [state(ctx), tree, _panel_check(ctx), upstream(ctx, ["06-review-report.md"], owner)]
    if res[-1]["status"] == FAIL:
        return res, {}
    reqs = known_reqs(ctx, _reqs(ctx))
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

def open_findings(found):
    """`FND (severity): status …` for every blocker or major that is not closed (`finding_closed`)."""
    return [f"{k} ({v['severity']}): {finding_status(v.get('status'))}" for k, v in found.items()
            if v.get("severity") in ("blocker", "major") and not finding_closed(v.get("status"))]


def _scope_check(ctx, reqs):
    """What the user approved at Plan is still being delivered: a REQ leaves scope by being marked
    retired (a decision someone made and wrote down), never by moving below the cut line or vanishing."""
    owner, locked = "orchestrator", _last_approval(ctx, "active_reqs")
    if locked is None:
        return ok("P7.scope", "No approval in the run log records the scope (a run begun before it did)", owner)
    active = docs.active_reqs(reqs)
    left = [f"{r}: {'no longer in 01-requirements.md' if r not in reqs else 'no longer above the cut line'}"
            for r in sorted(locked["active_reqs"]) if r not in active and not (r in reqs and reqs[r]["retired"])]
    return (bad("P7.scope", "REQs left scope after Plan without the user's decision (Constitution §5.1): "
                "restore each, or mark it retired on the user's word", owner, left) if left
            else ok("P7.scope", f"Every REQ approved at Plan (#{locked.get('seq')}) is active or retired", owner))


def phase7(ctx):
    owner = "orchestrator"
    res = [state(ctx), upstream(ctx, ["07-acceptance.md"], owner)]
    latest = {p: read_json(ctx.gdir / f"{p}-latest.json") for p in ("p1", "p2", "p4", "p5", "p6")}
    problems = [f"{p}: {'never run' if r is None else r['overall']}" for p, r in latest.items()
                if r is None or r["overall"] != PASS]
    if latest["p4"] and latest["p5"] and latest["p5"]["time"] < latest["p4"]["time"]:
        problems.append("p5 is older than the last p4: tests were not re-verified after the last code change")
    res.append(bad("P7.gates", "Earlier gates not green", owner, problems) if problems else
               ok("P7.gates", "All earlier gates green", owner))

    reqs = _reqs(ctx)
    des = docs.designs(ctx.doc("03-detailed-design.md") or "")
    tcs = docs.testcases(ctx.doc("04-test-plan.md") or "")
    p5 = (latest["p5"] or {}).get("data", {})
    # Observed results come from p5's test run; reported verdicts from the report as it is now.
    observed = p5.get("tc_observed", {})
    reported = docs.report_results(ctx.doc("05-test-report.md")) or p5.get("tc_reported", {})
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
    if not ctx.dry:
        (ctx.gdir / "traceability.md").parent.mkdir(parents=True, exist_ok=True)
        (ctx.gdir / "traceability.md").write_text(matrix, encoding="utf-8")
    res.append(bad("P7.matrix", "Active REQs not verified end to end", owner, gaps) if gaps else
               ok("P7.matrix", f"{len(rows)} active REQs verified; matrix in {ctx.run_rel}/gates/traceability.md",
                  owner))
    res.append(_scope_check(ctx, reqs))
    open_f = open_findings(docs.findings(ctx.doc("06-review-report.md")))
    res.append(bad("P7.open-findings", "Blocker/major findings still open", owner, open_f) if open_f else
               ok("P7.open-findings", "No open blocker or major finding", owner))
    res.append(_log_trail(ctx))
    res.append(demo(ctx))
    return res, {"not_machine_checked": [
        "Constitution §6.6: report states what the user must do to make it live",
        "Constitution §6.7: user accepted at Acceptance, with date"]}


PHASES = {"p1": phase1, "p2": phase2, "baseline": baseline, "p4": phase4,
          "p5": phase5, "p6": phase6, "p7": phase7}
