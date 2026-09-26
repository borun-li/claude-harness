"""Frontend team gates (PLAYBOOK §3D in ~/.claude/frontend). Reuses the backend helpers."""
import hashlib
import re

from . import capture, checks, docs, registry, runner, snap
from .common import FAIL, PASS, WAIVED, ConfigError, bad, na, ok, read_json, utc_now, write_json

STATES = ("loading", "empty", "success", "error", "permission")
HEX = re.compile(r"#[0-9A-Fa-f]{6}\b|#[0-9A-Fa-f]{3}\b")


def state(ctx):
    s = read_json(ctx.run / "state.json")
    if s is None:
        return bad("ALL.state", "state.json missing", "orchestrator")
    missing = [k for k in ("harness_version", "mode", "feature", "status", "current_phase", "phases", "models")
               if k not in s]
    return (bad("ALL.state", "state.json does not match the schema (PLAYBOOK §8)", "orchestrator", missing)
            if missing else ok("ALL.state", "state.json valid", "orchestrator"))


def _need(ctx, name, owner):
    text = ctx.doc(name)
    if not docs.nontrivial(text, ctx.cfg["min_doc_lines"]):
        return None, bad("ALL.upstream", f"{ctx.run_rel}/{name} missing or near-empty", owner)
    return text, ok("ALL.upstream", f"{name} present", owner)


def _blocks(text, prefix):
    return {k: v[0] for k, v in docs.id_blocks(text or "", prefix).items()}


def _task_rows(text):
    """{T-id: {column header: cell}} from the brief's tasks table."""
    out, header = {}, None
    for line in (text or "").splitlines():
        s = line.strip()
        if not s.startswith("|"):
            header = None
            continue
        cells = [c.strip() for c in s.strip("|").split("|")]
        if all(re.fullmatch(r":?-{2,}:?", c) for c in cells if c):
            continue
        if header is None:
            header = [c.lower() for c in cells]
        elif cells and re.fullmatch(r"T-\d+", cells[0]):
            out[cells[0]] = dict(zip(header, cells))
    return out


def _tasks(ctx):
    text = ctx.doc("01-brief.md") or ""
    tasks = set()
    for row in docs.table_rows(text):
        tasks |= {c for c in row[:1] if re.fullmatch(r"T-\d+", c)}
    above = docs.ids_in(docs.field(text, "Cut line (above)") or "", "T")
    return tasks, above & tasks if above else tasks


def _role_if(ctx, role):
    """Role rules when `role` is the most recent dispatch; nothing otherwise."""
    try:
        latest = checks._latest_writer(ctx)
    except ConfigError:
        return []
    return checks.role_checks(ctx)[0] if latest["role"] == role else []


def _prose(ctx, cid, text, owner):
    return checks._prose_check(ctx, cid, text or "", owner)


def _latest_ok(ctx, gates):
    out = []
    for g in gates:
        r = read_json(ctx.gdir / f"{g}-latest.json")
        if r is None or r["overall"] not in (PASS, WAIVED):
            out.append(f"{g}: {'never run' if r is None else r['overall']}")
    return out


# ---------- design phases ----------

def brief(ctx):
    owner = "fe-critic"
    text, up = _need(ctx, "01-brief.md", owner)
    res = [state(ctx), up]
    if text is None:
        return res, {}
    und = re.search(r"^#{1,6}\s+\W*0?\.?\s*(understanding|理解)", docs.mask_code(text), re.I | re.M)
    res.append(ok("FE1.understanding", "§0 Understanding present", owner) if und
               else bad("FE1.understanding", "No `## 0. Understanding` section", owner))
    user, surface = docs.field(text, "Named user"), docs.field(text, "Surface")
    res.append(ok("FE1.user", f"Named user: {user}", owner) if user
               else bad("FE1.user", "No named user (PLAYBOOK §1D)", owner))
    res.append(ok("FE1.surface", f"Surface: {surface}", owner) if surface and "|" not in surface
               else bad("FE1.surface", "Surface not chosen (PLAYBOOK §1C)", owner))
    tasks, active = _tasks(ctx)
    res.append(bad("FE1.tasks", "No `T-nnn` tasks in the tasks table", owner) if not tasks else
               bad("FE1.tasks", "Cut line names no task above the line", owner) if not active else
               ok("FE1.tasks", f"{len(tasks)} tasks, {len(active)} above the cut line", owner))
    rows = _task_rows(text)
    no_src = [t for t, r in rows.items() if not docs._source("**Source:** " + r.get("source", ""))]
    res.append(bad("FE1.source", "Tasks whose Source neither quotes the user nor cites an artifact", owner, no_src)
               if no_src else ok("FE1.source", "Every task traces to the user's words or an artifact", owner))
    res.append(ok("FE1.non-goals", "Non-goals stated", owner) if docs.field(text, "Non-goals")
               else bad("FE1.non-goals", "Non-goals missing", owner))
    res.append(_prose(ctx, "FE1.prose", text, owner))
    return res, {"active_tasks": sorted(active)}


def structure(ctx):
    owner = "fe-designer"
    text, up = _need(ctx, "02-structure.md", owner)
    res = [state(ctx), up] + _role_if(ctx, "fe-designer")
    if text is None:
        return res, {}
    tasks, active = _tasks(ctx)
    pages = {}
    for row in docs.table_rows(text):
        if row and re.fullmatch(r"PAGE-\d+", row[0]):
            pages[row[0]] = docs.ids_in(" ".join(row), "T")
    bad_pages = [f"{p}: serves {sorted(t) or 'nothing'}" for p, t in pages.items() if not t or not t <= tasks]
    res.append(bad("FE3.pages", "No `PAGE-nnn` rows in the page table", owner) if not pages else
               bad("FE3.pages", "Pages without a valid task", owner, bad_pages) if bad_pages else
               ok("FE3.pages", f"{len(pages)} pages, each serving a task", owner))
    served = set().union(*pages.values()) if pages else set()
    unserved = sorted(active - served)
    res.append(bad("FE3.coverage", "Tasks above the cut line with no page", owner, unserved) if unserved
               else ok("FE3.coverage", "Every active task has a page", owner))
    flows = _blocks(text, "FLOW")
    incomplete = [f"{f}: missing {[k for k in ('Serves', 'Success', 'Failure', 'Cancel', 'Recovery', 'Boundary') if not docs.field(b, k)]}"
                  for f, b in flows.items()
                  if not all(docs.field(b, k) for k in ("Serves", "Success", "Failure", "Cancel", "Recovery", "Boundary"))]
    res.append(bad("FE3.flows", "No `### FLOW-nnn` blocks", owner) if not flows else
               bad("FE3.flows", "Flows without every path", owner, incomplete) if incomplete else
               ok("FE3.flows", f"{len(flows)} flows with success, failure, cancel, recovery, boundary", owner))
    res.append(checks._length_check(ctx, "FE3.flow-length", [(f, docs.words(b)) for f, b in flows.items()],
                                    "fe_flow_words", owner, "FLOW"))
    res.append(_prose(ctx, "FE3.prose", text, owner))
    return res, {"pages": sorted(pages)}


def spec(ctx):
    owner = "fe-designer"
    text, up = _need(ctx, "03-spec.md", owner)
    res = [state(ctx), up] + _role_if(ctx, "fe-designer")
    if text is None:
        return res, {}
    structure_pages = set()
    for row in docs.table_rows(ctx.doc("02-structure.md") or ""):
        if row and re.fullmatch(r"PAGE-\d+", row[0]):
            structure_pages.add(row[0])
    pages = _blocks(text, "PAGE")
    missing = sorted(structure_pages - set(pages))
    res.append(bad("FE4.pages", "Structure pages with no spec block", owner, missing) if missing
               else ok("FE4.pages", f"{len(pages)} page specs", owner))
    gaps = []
    for pid, b in pages.items():
        low = b.lower()
        lacking = [s for s in STATES if s not in low]
        if lacking:
            gaps.append(f"{pid}: states missing {lacking}")
        if not docs.ids_in(b, "AC"):
            gaps.append(f"{pid}: no AC-nnn acceptance criterion")
    res.append(bad("FE4.states", "Page specs missing states or acceptance criteria", owner, gaps) if gaps
               else ok("FE4.states", "Every page states every state and has acceptance criteria", owner))
    comps = _blocks(text, "CMP")
    no_focus = [c for c, b in comps.items() if "focus" not in (docs.field(b, "States") or "").lower()]
    res.append(bad("FE4.components", "Components without a focus state", owner, no_focus) if no_focus
               else ok("FE4.components", f"{len(comps)} components with a focus state", owner))
    tokens = checks._section(text, [r"tokens?", r"令牌"]) or ""
    body = docs.mask_code(text.replace(tokens, ""))
    inline = sorted(set(HEX.findall(body)))
    res.append(bad("FE4.tokens", "Colour values inlined outside the tokens table", owner, inline) if inline
               else ok("FE4.tokens", "No colour value outside the tokens table", owner))
    contract = docs.read(ctx.project / ctx.cfg.get("contract", "contracts/FRONTEND_BACKEND_CONTRACT.md"))
    if contract is None:
        res.append(bad("FE4.contract", "contracts/FRONTEND_BACKEND_CONTRACT.md missing", owner))
    else:
        rows = [r for r in docs.table_rows(contract) if r and re.fullmatch(r"C-\d+", r[0])]
        bad_rows = [f"{r[0]}: status {r[2] if len(r) > 2 else '?'}" for r in rows
                    if len(r) < 4 or r[2].lower() not in ("verified", "unverified", "new")
                    or (r[2].lower() == "verified" and not r[3])]
        res.append(bad("FE4.contract", "Capabilities not marked verified (with source), unverified or new",
                       owner, bad_rows) if bad_rows
                   else ok("FE4.contract", f"{len(rows)} capabilities, each ruled", owner))
    res.append(checks._length_check(ctx, "FE4.page-length", [(p, docs.words(b)) for p, b in pages.items()],
                                    "fe_page_words", owner, "PAGE spec"))
    res.append(_prose(ctx, "FE4.prose", text, owner))
    return res, {"pages": sorted(pages)}


def findings(ctx):
    owner = "orchestrator"
    text, up = _need(ctx, "04-findings.md", owner)
    res = [state(ctx), up] + _role_if(ctx, "fe-critic")
    if text is None:
        return res, {}
    tasks, _ = _tasks(ctx)
    res.append(ok("FE5.captured", "Captured / not captured stated", owner)
               if re.search(r"not captured", text, re.I) else
               bad("FE5.captured", "No `Captured / not captured` section", owner))
    probs = []
    for fid, b in _blocks(text, "F").items():
        pr, side, task = docs.field(b, "Priority"), docs.field(b, "Side"), docs.field(b, "Task damaged")
        ev, own, st = docs.field(b, "Evidence"), docs.field(b, "Owner"), docs.field(b, "Status")
        if pr not in ("P1", "P2", "P3"):
            probs.append(f"{fid}: priority {pr!r}")
        if (side or "").lower() not in ("frontend", "backend", "cross-stack"):
            probs.append(f"{fid}: side {side!r}")
        if not docs.ids_in(task or "", "T") or not docs.ids_in(task, "T") <= tasks:
            probs.append(f"{fid}: task damaged {task!r} names no known T-nnn")
        if not ev or not re.search(r"observed|inferred", ev, re.I):
            probs.append(f"{fid}: evidence missing or not labelled observed/inferred")
        else:
            for path in re.findall(r"evidence/[\w./-]+", ev):
                if not (ctx.run / path).exists():
                    probs.append(f"{fid}: {path} does not exist")
        if not own or not st:
            probs.append(f"{fid}: owner or status missing")
    res.append(bad("FE5.findings", "Findings incomplete", owner, probs) if probs
               else ok("FE5.findings", "Every finding has priority, side, task, evidence, owner, status", owner))
    res.append(checks._length_check(ctx, "FE5.finding-length",
                                    [(f, docs.words(b)) for f, b in _blocks(text, "F").items()],
                                    "fe_finding_words", "fe-critic", "finding"))
    res.append(_prose(ctx, "FE5.prose", text, owner))
    return res, {}


def _queue_rows(ctx):
    return _blocks(ctx.doc("05-queue.md") or "", "Q")


def _row_digest(b):
    key = "\n".join(docs.field(b, k) or "" for k in ("Spec", "Observable", "Acceptance"))
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


def queue(ctx):
    owner = "orchestrator"
    text, up = _need(ctx, "05-queue.md", owner)
    res = [state(ctx), up]
    if text is None:
        return res, {}
    spec_text = ctx.doc("03-spec.md") or ""
    pages, acs = docs.ids_in(spec_text, "PAGE"), docs.ids_in(spec_text, "AC")
    probs = []
    rows = _queue_rows(ctx)
    for q, b in rows.items():
        for k in ("Spec", "Files", "Observable", "Depends on", "Status"):
            if not docs.field(b, k):
                probs.append(f"{q}: {k} missing")
        if docs.field(b, "Priority") not in ("P1", "P2", "P3"):
            probs.append(f"{q}: ungraded (fe-critic grades before dispatch)")
        if (docs.field(b, "Side") or "").split(" ")[0].lower() not in ("frontend", "backend", "both"):
            probs.append(f"{q}: side {docs.field(b, 'Side')!r}")
        ref = docs.ids_in(docs.field(b, "Spec") or "", "PAGE")
        if ref - pages or not ref:
            probs.append(f"{q}: spec clause names no known PAGE-nnn")
        ac = docs.ids_in(docs.field(b, "Acceptance") or "", "AC")
        if not ac or ac - acs:
            probs.append(f"{q}: acceptance names no known AC-nnn")
    res.append(checks._length_check(ctx, "FE6.row-length", [(q, docs.words(b)) for q, b in rows.items()],
                                    "fe_row_words", owner, "queue row"))
    res.append(bad("FE6.rows", "No `### Q-nnn` rows", owner) if not rows else
               bad("FE6.rows", "Queue rows incomplete", owner, probs) if probs else
               ok("FE6.rows", f"{len(rows)} rows complete and graded", owner))
    return res, {"rows": sorted(rows)}


# ---------- plan, approval ----------

def plan(ctx):
    owner = "orchestrator"
    res = [state(ctx)]
    s = read_json(ctx.run / "state.json") or {}
    implementing = s.get("mode") == "implement"
    need = ["fe-queue"] if implementing else ["fe-brief", "fe-structure", "fe-spec"]
    if not implementing and (ctx.run / "04-findings.md").exists():
        need.append("fe-findings")
    red = _latest_ok(ctx, need)
    res.append(bad("FEP.gates", "Earlier gates not green", owner, red) if red
               else ok("FEP.gates", f"{', '.join(need)} green", owner))
    sheet = ["# Plan review", "", "Approve, or say what to change. Nothing is built before you do.", ""]
    brief_text = ctx.doc("01-brief.md") or ""
    sheet += ["## Scope", "", *(line for line in brief_text.splitlines()
                                 if re.match(r"- \*\*(Asked|Means|Named user|Cut line|Non-goals)", line)), ""]
    pages = [r for r in docs.table_rows(ctx.doc("02-structure.md") or "") if r and r[0].startswith("PAGE-")]
    sheet += ["## Pages", "", "| Page | Job |", "|---|---|", *(f"| {r[0]} | {r[1]} |" for r in pages), ""]
    open_p1 = [f"- {fid}: {b.splitlines()[0].lstrip('# ').split('—', 1)[-1].strip()}"
               for fid, b in _blocks(ctx.doc("04-findings.md"), "F").items()
               if docs.field(b, "Priority") == "P1" and not checks.FIX_STATUS.search(docs.field(b, "Status") or "")]
    sheet += ["## Open P1 findings", "", *(open_p1 or ["- none"]), ""]
    rows = _queue_rows(ctx)
    clash = registry.conflicts(ctx, rows)
    if clash:
        reg = registry.active(registry.load(ctx))
        sheet += ["## Approved results this round may change", "",
                  "Keep each, or retire it (`fe-approve --retire OBS-nnn`) if the new design replaces it.", "",
                  "| Approved | Observable | Touched by |", "|---|---|---|",
                  *(f"| {k} | {reg[k]['observable']} | {', '.join(v)} |" for k, v in sorted(clash.items())), ""]
    if rows:
        sheet += ["## Queue — expected results you approve", "", "| Row | Priority | Observable |", "|---|---|---|",
                  *(f"| {q} | {docs.field(b, 'Priority')} | {docs.field(b, 'Observable')} |" for q, b in rows.items()), ""]
    (ctx.gdir / "plan-review.md").parent.mkdir(parents=True, exist_ok=True)
    (ctx.gdir / "plan-review.md").write_text("\n".join(sheet) + "\n", encoding="utf-8")
    return res, {"review_sheet": f"{ctx.run_rel}/gates/plan-review.md", "rows": sorted(rows), "may_change": clash}


def approve(ctx, by, retire=()):
    """Lock each queue row's spec, observable and acceptance. Only after the user's yes."""
    p = read_json(ctx.gdir / "fe-plan-latest.json")
    if not p or p["overall"] != PASS:
        raise ConfigError("`fe-plan` has not passed; run it and get the user's approval first")
    rows = _queue_rows(ctx)
    locked = {q: _row_digest(b) for q, b in rows.items()}
    write_json(ctx.gdir / "observables-approved.json", {"approved_by": by, "date": utc_now()[:10], "rows": locked})
    if retire:
        registry.retire(ctx, by, retire)
    return [ok("FEP.approve", f"Locked {len(locked)} observables, approved by {by}", "orchestrator",
               sorted(locked))], {}


def _observables(ctx, owner):
    approved = read_json(ctx.gdir / "observables-approved.json")
    if approved is None:
        return bad("FE.observables", "No approved observables: run the Plan stop and `fe-approve`", "orchestrator")
    rows = _queue_rows(ctx)
    probs = [f"{q}: changed since approval on {approved['date']}" for q, h in approved["rows"].items()
             if q in rows and _row_digest(rows[q]) != h]
    probs += [f"{q}: never approved" for q in rows if q not in approved["rows"]]
    probs += [f"{q}: approved row removed" for q in approved["rows"] if q not in rows]
    return (bad("FE.observables", "Approved observables changed (only the user re-approves)", owner, probs)
            if probs else ok("FE.observables", f"{len(rows)} approved observables intact", owner))


# ---------- build, verify, accept ----------

def build(ctx):
    base = checks._baseline(ctx)
    run_diff = snap.diff(base["snapshot"], ctx.snapshot())
    res = [state(ctx)]
    roles, changed = checks.role_checks(ctx)
    res += roles
    res += checks._scan(ctx, base, run_diff)
    res.append(checks._dependency_check(ctx, base, run_diff, "03-spec.md", "fe-engineer", "FE7.dependencies"))
    for name in ("build", "lint", "typecheck"):
        res.append(checks._command_check(ctx, name, "fe-engineer")[0])
    t, r = checks._tests(ctx, "fe-engineer", base)
    res += [t, checks._test_file_drift(ctx, base, "fe-engineer", "FE7.test-drift"),
            _observables(ctx, "fe-engineer"), registry.regression(ctx, r, "fe-engineer")]
    return res, {"writer_changed": changed, "counts": r["counts"] if r else None}


def verify(ctx):
    base = checks._baseline(ctx)
    owner = "fe-tester"
    text, up = _need(ctx, "06-verification.md", owner)
    res = [state(ctx), up]
    res += checks.role_checks(ctx)[0]
    t, r = checks._tests(ctx, "fe-engineer", base)
    res += [t, checks._test_file_drift(ctx, base, owner, "FE8.test-drift"), _observables(ctx, "orchestrator")]
    row_res, row_seen = _row_tests(ctx, r)
    res += [row_res, registry.regression(ctx, r, "fe-engineer"), _capture_check(ctx, text)]
    if text is None:
        return res, {}
    verdicts = {}
    for row in docs.table_rows(text):
        if row and re.fullmatch(r"(?:Q|OBS)-\d+", row[0]) and len(row) > 1:
            verdicts.setdefault(row[0], []).append(row[1].lower().strip())
    rows = _queue_rows(ctx)
    built = [q for q, b in rows.items() if (docs.field(b, "Status") or "").lower().startswith("done")]
    probs = [f"{q}: no verdict" for q in built if q not in verdicts]
    probs += [f"{q}: {len(v)} verdicts" for q, v in verdicts.items() if len(v) > 1]
    probs += [f"{q}: verdict {v[0]!r} not one of done / not done / not observable" for q, v in verdicts.items()
              if v[0] not in ("done", "not done", "not observable")]
    res.append(bad("FE8.verdicts", "Rows without exactly one valid verdict", owner, probs) if probs
               else ok("FE8.verdicts", f"{len(verdicts)} rows with one verdict each", owner))
    manifest = re.search(r"evidence/verify-[\w.-]+/manifest\.md", text)
    if not manifest or not (ctx.run / manifest.group(0)).exists():
        res.append(bad("FE8.evidence", "Evidence manifest missing (the orchestrator captures, §1C)", "orchestrator"))
    else:
        cited = set(re.findall(r"`([\w.@-]+\.(?:html|json|txt|png|jpg|xml|log|yml|stdout|stderr))`", text))
        folder = (ctx.run / manifest.group(0)).parent
        absent = sorted(c for c in cited if not (folder / c).exists())
        res.append(bad("FE8.evidence", "Cited evidence files not in the capture folder", "orchestrator", absent)
                   if absent else ok("FE8.evidence", f"Manifest present; {len(cited)} cited files exist", owner))
    captured = registry.capture_entries(ctx)
    unjudged = [f"{k}: {verdicts.get(k, ['no verdict'])[0]}" for k in captured if verdicts.get(k, [None])[0] != "done"]
    if captured:
        res.append(bad("FE.regression-captures", "Registered capture-guarded observables not re-verified done",
                       "fe-tester", unjudged) if unjudged
                   else ok("FE.regression-captures", f"{len(captured)} capture-guarded observables re-verified", "fe-tester"))
    return res, {"verdicts": {q: v[0] for q, v in verdicts.items()}, "row_tests": row_seen}


def _rows_to_verify(ctx):
    return sorted(q for q, b in _queue_rows(ctx).items()
                  if not (docs.field(b, "Status") or "").lower().startswith(("blocked", "skipped")))


def capture_plan(ctx):
    owner = "orchestrator"
    res = [state(ctx)]
    try:
        plan = capture.load_plan(ctx)
    except ConfigError as e:
        return res + [bad("FE8.capture-plan", str(e), owner)], {}
    probs = capture.plan_problems(plan, _rows_to_verify(ctx) + sorted(registry.capture_entries(ctx)))
    brief_surface = (docs.field(ctx.doc("01-brief.md") or "", "Surface") or "").lower()
    if plan.get("surface") == "web" and brief_surface and "browser" not in brief_surface and "web" not in brief_surface:
        probs.append(f"plan surface web, brief says {brief_surface!r}")
    res.append(bad("FE8.capture-plan", "Capture plan incomplete (PLAYBOOK §3H)", owner, probs) if probs
               else ok("FE8.capture-plan", f"{len(plan['captures'])} captures cover every row to verify", owner))
    return res, {}


def _capture_check(ctx, text):
    m = re.search(r"evidence/verify-([\w.-]+)/manifest\.md", text or "")
    if not m:
        return bad("FE8.capture", "06-verification.md names no evidence round", "orchestrator")
    try:
        plan = capture.load_plan(ctx)
    except ConfigError as e:
        return bad("FE8.capture", str(e), "orchestrator")
    build = read_json(ctx.gdir / "fe-build-latest.json")
    probs = capture.evidence_problems(ctx, ctx.run / "evidence" / f"verify-{m.group(1)}", plan,
                                      build["time"] if build else None)
    return (bad("FE8.capture", "Evidence incomplete, failed or stale: recapture (`gate.py capture`)",
                "orchestrator", probs) if probs
            else ok("FE8.capture", f"Round {m.group(1)}: every planned capture present, fresh and non-empty",
                    "orchestrator"))


def _row_tests(ctx, r):
    """Tests tagged with a queue row id (Q-###) must pass in this run."""
    locs = runner.tc_locations(ctx.project, checks._test_code(ctx), ctx.cfg, prefix="Q")
    if not locs:
        return na("FE8.row-tests", "No test is tagged with a queue row id", "fe-tester"), {}
    if not r or r.get("cases") is None:
        return na("FE8.row-tests", f"{len(locs)} rows tagged; pass status needs a JUnit report", "fe-tester"), {}
    seen = checks._observed_ids(locs, dict.fromkeys(locs), r["cases"])
    red = [f"{q}: {st}" for q, st in sorted(seen.items()) if st != "passed"]
    return (bad("FE8.row-tests", "Row-tagged tests not passing in this run", "fe-engineer", red) if red
            else ok("FE8.row-tests", f"{len(seen)} row-tagged tests passed", "fe-tester")), seen


def _matrix(ctx, verdicts):
    """Task → page → queue row → verdict; every active task must end in a row verified done."""
    _, active = _tasks(ctx)
    pages = {r[0]: docs.ids_in(" ".join(r), "T") for r in docs.table_rows(ctx.doc("02-structure.md") or "")
             if r and re.fullmatch(r"PAGE-\d+", r[0])}
    rows = _queue_rows(ctx)
    lines, gaps = ["| Task | Pages | Rows (verdict) | Delivered |", "|---|---|---|---|"], []
    for t in sorted(active):
        ps = sorted(p for p, ts in pages.items() if t in ts)
        qs = sorted(q for q, b in rows.items() if docs.ids_in(docs.field(b, "Spec") or "", "PAGE") & set(ps))
        cells = [f"{q} {verdicts.get(q, 'no verdict')}" for q in qs]
        done = bool(qs) and any(verdicts.get(q) == "done" for q in qs)
        lines.append(f"| {t} | {', '.join(ps) or '—'} | {', '.join(cells) or '—'} | {'yes' if done else 'NO'} |")
        if not done:
            gaps.append(f"{t}: pages {ps or 'none'}, rows {cells or 'none'}")
    (ctx.gdir / "traceability.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return (bad("FEA.matrix", "Active tasks not delivered by a verified row", "orchestrator", gaps) if gaps
            else ok("FEA.matrix", f"{len(active)} active tasks delivered; matrix in {ctx.run_rel}/gates/traceability.md",
                    "orchestrator"))


def accept(ctx):
    owner = "orchestrator"
    res = [state(ctx)]
    red = _latest_ok(ctx, ["fe-build", "fe-verify"])
    b, v = read_json(ctx.gdir / "fe-build-latest.json"), read_json(ctx.gdir / "fe-verify-latest.json")
    if b and v and v["time"] < b["time"]:
        red.append("fe-verify is older than the last fe-build")
    res.append(bad("FEA.gates", "Build or verification gate not green", owner, red) if red
               else ok("FEA.gates", "fe-build and fe-verify green, in order", owner))
    verdicts = ((v or {}).get("data") or {}).get("verdicts", {})
    rows = _queue_rows(ctx)
    undone = [f"{q}: {verdicts.get(q, 'no verdict')}" for q, blk in rows.items()
              if not (docs.field(blk, "Status") or "").lower().startswith(("blocked", "skipped"))
              and verdicts.get(q) != "done"]
    res.append(bad("FEA.rows", "Rows not verified done (blocked or skipped rows must say why)", owner, undone)
               if undone else ok("FEA.rows", f"{len(rows)} rows done, blocked or skipped with a reason", owner))
    res.append(_matrix(ctx, verdicts))
    res.append(checks._log_trail(ctx))
    return res, {"not_machine_checked": ["Constitution §6.6: what the user must do to make it live",
                                         "Constitution §6.7: user accepted, with date"]}


PHASES = {"fe-brief": brief, "fe-structure": structure, "fe-spec": spec, "fe-findings": findings,
          "fe-queue": queue, "fe-plan": plan, "fe-build": build, "fe-capture-plan": capture_plan,
          "fe-verify": verify, "fe-accept": accept}
