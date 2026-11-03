"""Frontend team gates (PLAYBOOK §3D in ~/.claude/frontend, 7.0). Reuses the backend helpers.

Phases: 0 product (be-analyst, frontend-only runs) · 1 UX (fe-ux) · 2 UI (fe-ui), scaffold, feasibility
and queue (fe-engineer) · UI stop · 3 build · 4 verify (fe-tester) and review (panel + fe-reviewer) ·
Acceptance · 5 after launch."""
import hashlib
import re

from . import capture, checks, docs, registry, runlog, runner, snap
from .common import FAIL, PASS, WAIVED, ConfigError, bad, na, ok, read_json, utc_now, write_json

STATES = ("loading", "empty", "success", "error", "permission")
EXTRA_STATES = ("offline", "partial")
HEX = re.compile(r"#[0-9A-Fa-f]{6}\b|#[0-9A-Fa-f]{3}\b")
NA = re.compile(r"^\s*n/?a\b", re.I)
PANEL = ("fe-review-experience", "fe-review-accessibility", "fe-review-integration")
UX_FLOW_FIELDS = ("Serves", "Steps", "Success", "Failure", "Cancel", "Recovery", "Boundary")
ROW_FIELDS = ("Page", "Frame", "States", "REQ", "Files", "Observable", "Acceptance", "Depends on", "Status")


def _state_json(ctx):
    return read_json(ctx.run / "state.json") or {}


def state(ctx):
    s = read_json(ctx.run / "state.json")
    if s is None:
        return bad("ALL.state", "state.json missing", "orchestrator")
    missing = [k for k in ("harness_version", "feature", "status", "current_phase", "phases", "models", "tier")
               if k not in s]
    if "tier" in s and s["tier"] not in ("small", "prototype", "full"):
        missing.append(f"tier must be small|prototype|full, got {s['tier']!r}")
    if "risk" in s and s["risk"] not in ("normal", "high"):
        missing.append(f"risk must be normal|high, got {s['risk']!r}")
    if "design_stops" in s and s["design_stops"] not in (1, 2):
        missing.append(f"design_stops must be 1 or 2, got {s['design_stops']!r}")
    return (bad("ALL.state", "state.json does not match the schema (PLAYBOOK §8)", "orchestrator", missing)
            if missing else ok("ALL.state", "state.json valid", "orchestrator"))


def _need(ctx, name, owner):
    text = ctx.doc(name)
    if not docs.nontrivial(text, ctx.cfg["min_doc_lines"]):
        return None, bad("ALL.upstream", f"{ctx.run_rel}/{name} missing or near-empty", owner)
    return text, ok("ALL.upstream", f"{name} present", owner)


def _blocks(text, prefix):
    return {k: v[0] for k, v in docs.id_blocks(text or "", prefix).items()}


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


def _table(text, prefix):
    """{ID: [cells]} for table rows whose first cell is PREFIX-nnn."""
    return {r[0]: r for r in docs.table_rows(text or "") if r and re.fullmatch(rf"{prefix}-\d+", r[0])}


# ---------- requirements (Phase 0, or the Backend team's Phase 1) ----------

def _req_rel(ctx):
    return _state_json(ctx).get("requirements") or f"{ctx.run_rel}/00-requirements.md"


def _reqs(ctx):
    """(all REQ ids, active REQs a person uses). Frontend-only runs tag them [interface]; when no REQ is
    tagged, every active REQ counts."""
    reqs = docs.requirements(docs.read(ctx.project / _req_rel(ctx)) or "")
    active = docs.active_reqs(reqs)
    iface = {r for r in active if reqs[r]["interface"]}
    return set(reqs), (iface or active)


def product(ctx):
    owner = "be-analyst"
    res, data = checks.phase1(ctx, name="00-requirements.md")
    res[0] = state(ctx)  # this team's state.json schema
    _, iface = _reqs(ctx)
    if res[1]["status"] != FAIL:
        res.append(ok("FE0.interface", f"{len(iface)} active REQs a person uses", owner, sorted(iface)) if iface
                   else bad("FE0.interface", "No active REQ above the cut line", owner))
    return res, data


# ---------- Phase 1: UX ----------

def _ux_pages(ctx):
    return _table(ctx.doc("01-ux.md"), "PAGE")


def _page_states(block):
    """{state: "n/a" | "yes"} from a page block's state table."""
    out = {}
    for r in docs.table_rows(block or ""):
        key = (r[0] if r else "").lower().split(" ")[0]
        if key in STATES + EXTRA_STATES:
            rest = [c for c in r[1:] if c]
            out[key] = "n/a" if not rest or NA.match(rest[0]) else "yes"
    return out


def ux(ctx):
    owner = "fe-ux"
    text, up = _need(ctx, "01-ux.md", owner)
    res = [state(ctx), up] + _role_if(ctx, "fe-ux")
    if text is None:
        return res, {}
    user, surface = docs.field(text, "Named user"), docs.field(text, "Surface")
    res.append(ok("FE1.user", f"Named user: {user}", owner) if user
               else bad("FE1.user", "No named user (PLAYBOOK §1D)", owner))
    res.append(ok("FE1.surface", f"Surface: {surface}", owner) if surface and "|" not in surface
               else bad("FE1.surface", "Surface not chosen (PLAYBOOK §1C)", owner))
    known, active = _reqs(ctx)
    pages = {p: docs.ids_in(" ".join(r), "REQ") for p, r in _ux_pages(ctx).items()}
    bad_pages = [f"{p}: serves {sorted(s) or 'nothing'}" for p, s in pages.items() if not s or not s <= known]
    res.append(bad("FE1.pages", "No `PAGE-nnn` rows in the pages table", owner) if not pages else
               bad("FE1.pages", "Pages that serve no known REQ", owner, bad_pages) if bad_pages else
               ok("FE1.pages", f"{len(pages)} pages, each serving a REQ", owner))
    served = set().union(*pages.values()) if pages else set()
    unserved = sorted(active - served)
    res.append(bad("FE1.coverage", f"Active REQs in {_req_rel(ctx)} with no page", owner, unserved) if unserved
               else ok("FE1.coverage", f"{len(active)} active REQs each served by a page", owner))
    flows = _blocks(text, "FLOW")
    incomplete = [f"{f}: missing {[k for k in UX_FLOW_FIELDS if not docs.field(b, k)]}"
                  for f, b in flows.items() if not all(docs.field(b, k) for k in UX_FLOW_FIELDS)]
    res.append(bad("FE1.flows", "No `### FLOW-nnn` blocks", owner) if not flows else
               bad("FE1.flows", "Flows without steps or every path", owner, incomplete) if incomplete else
               ok("FE1.flows", f"{len(flows)} flows with steps, success, failure, cancel, recovery, boundary", owner))
    details = _blocks(text, "PAGE")
    gaps, no_wire = [], []
    for p in pages:
        b = details.get(p)
        if b is None:
            gaps.append(f"{p}: no `### {p}` detail block")
            continue
        st = _page_states(b)
        lacking = [s for s in STATES if s not in st]
        if lacking:
            gaps.append(f"{p}: state rows missing {lacking}")
        if "```" not in b:
            no_wire.append(p)
    res.append(bad("FE1.states", "Pages without a full state table", owner, gaps) if gaps
               else ok("FE1.states", "Every page states loading, empty, success, error, permission", owner))
    res.append(bad("FE1.wireframes", "Pages without an ASCII wireframe (fenced block)", owner, no_wire) if no_wire
               else ok("FE1.wireframes", "Every page has a wireframe", owner))
    res.append(checks._length_check(ctx, "FE1.flow-length", [(f, docs.words(b)) for f, b in flows.items()],
                                    "fe_flow_words", owner, "FLOW"))
    res.append(checks._length_check(ctx, "FE1.page-length", [(p, docs.words(b)) for p, b in details.items()],
                                    "fe_page_words", owner, "PAGE block"))
    res.append(_prose(ctx, "FE1.prose", text, owner))
    return res, {"pages": sorted(pages), "flows": sorted(flows)}


# ---------- Phase 2: UI ----------

def _surface(ctx):
    return (docs.field(ctx.doc("01-ux.md") or "", "Surface") or _state_json(ctx).get("delivery_surface") or "").lower()


def _canvasless(ctx):
    return any(w in _surface(ctx) for w in ("terminal", "cli"))


def _ui_frames(ctx):
    return _table(ctx.doc("02-ui.md"), "FRAME")


def _figma(ctx, owner):
    """Figma calls logged on returns vs. the run budget (PLAYBOOK §1E)."""
    s = _state_json(ctx)
    budget = (s.get("figma") or {}).get("budget")
    events = [ev for _, ev in runlog.read(ctx.run / "run-log.jsonl")]
    used = sum(int(ev.get("figma_calls") or 0) for ev in events if ev["event"] == "return")
    if budget is None:
        return (na("FE.figma", f"No Figma budget set; {used} calls logged", owner) if not used else
                bad("FE.figma", f"{used} Figma calls logged but state.json figma.budget is unset", "orchestrator"))
    raised = any(ev["event"] == "human" and ev["stop"] == "Budget" and ev["decision"] == "approved" for ev in events)
    if used > budget and not raised:
        return bad("FE.figma", f"{used} Figma calls exceed the run budget {budget} without the user's yes "
                   "(`log human --stop Budget`)", "orchestrator")
    return ok("FE.figma", f"{used} of {budget} Figma calls used" + (" (raised by the user)" if raised else ""), owner)


def ui(ctx):
    owner = "fe-ui"
    text, up = _need(ctx, "02-ui.md", owner)
    res = [state(ctx), up] + _role_if(ctx, "fe-ui")
    if text is None:
        return res, {}
    plan = checks._section(text, [r"design plan", r"设计计划"]) or ""
    palette = checks._section(plan, [r"palette", r"配色"]) or ""
    hexes = set(HEX.findall(palette))
    lacking = [k for k, pats in (("Type", [r"\btype", r"字体"]), ("Layout", [r"layout", r"布局"]),
                                 ("Principles", [r"principles?", r"原则"]))
               if not checks._section(plan, pats)]
    res.append(bad("FE2.plan", "No `## Design plan` section", owner) if not plan else
               bad("FE2.plan", f"Palette has {len(hexes)} colours (4–6 named hex values)", owner)
               if not 4 <= len(hexes) <= 6 else
               bad("FE2.plan", "Design plan lacks sections", owner, lacking) if lacking else
               ok("FE2.plan", f"Design plan: {len(hexes)} colours, type, layout, principles", owner))
    check = checks._section(text, [r"self-check", r"自查"]) or ""
    filled = [r for r in docs.table_rows(check) if any(c for c in r)] or \
        [ln for ln in check.splitlines()[1:] if ln.strip().startswith("-") and len(ln.strip()) > 3]
    res.append(ok("FE2.self-check", "Self-check written", owner) if filled
               else bad("FE2.self-check", "Self-check empty: what read like a default, and what replaced it", owner))
    tokens = checks._section(text, [r"tokens?", r"令牌"]) or ""
    body = docs.mask_code(text.replace(tokens, "").replace(plan, ""))
    inline = sorted(set(HEX.findall(body)))
    res.append(bad("FE2.tokens", "Colour values outside the plan and tokens tables", owner, inline) if inline
               else ok("FE2.tokens", "Colours only in the plan and tokens tables", owner))
    comps = _blocks(text, "CMP")
    no_focus = [c for c, b in comps.items() if "focus" not in (docs.field(b, "States") or "").lower()]
    res.append(bad("FE2.components", "Components without a focus state", owner, no_focus) if no_focus
               else ok("FE2.components", f"{len(comps)} components, each with a focus state", owner))
    pages, frames = set(_ux_pages(ctx)), _ui_frames(ctx)
    canvasless = _canvasless(ctx)
    probs = [f"{p}: no frame" for p in sorted(pages - {r[1] for r in frames.values() if len(r) > 1})]
    for f, r in frames.items():
        if len(r) < 5:
            probs.append(f"{f}: needs Page, State, Size, Figma")
            continue
        if r[1] not in pages:
            probs.append(f"{f}: page {r[1]!r} is not in 01-ux.md")
        link = r[4]
        if canvasless:
            if not re.search(r"mockup|§", link, re.I):
                probs.append(f"{f}: terminal surface — point to the text mockup")
        elif not re.search(r"figma\.com/(design|file)/[\w-]+.*node-id=\d+[-:]\d+", link):
            probs.append(f"{f}: Figma cell is not a node link (`…?node-id=12-34`)")
    if not canvasless and not (docs.field(text, "Figma file") or "").startswith("http"):
        probs.append("**Figma file:** missing")
    res.append(bad("FE2.frames", "No `FRAME-nnn` rows", owner) if not frames else
               bad("FE2.frames", "Frames incomplete", owner, probs) if probs else
               ok("FE2.frames", f"{len(frames)} frames; every UX page has one", owner))
    res.append(_figma(ctx, owner))
    res.append(_prose(ctx, "FE2.prose", text, owner))
    return res, {"frames": sorted(frames)}


# ---------- Phase 2: queue ----------

def _queue_rows(ctx):
    return _blocks(ctx.doc("03-queue.md") or "", "Q")


def _row_states(b):
    v = (docs.field(b, "States") or "").lower()
    return {s for s in STATES + EXTRA_STATES if re.search(rf"\b{s}\b", v)}


def _row_digest(b):
    key = "\n".join(docs.field(b, k) or "" for k in ("Page", "Frame", "States", "Observable", "Acceptance"))
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


def _feedback(ctx):
    """[{dfb, decision, by, needs_user, user}] from 06-feedback.md § Design feedback."""
    out = []
    for r in docs.table_rows(ctx.doc("06-feedback.md") or ""):
        if r and re.fullmatch(r"DFB-\d+", r[0]) and len(r) >= 9:
            out.append({"dfb": r[0], "decision": r[5].lower(), "by": r[6], "needs_user": r[7].lower(),
                        "user": r[8]})
    return out


def _contract(ctx, owner):
    contract = docs.read(ctx.project / ctx.cfg.get("contract", "contracts/FRONTEND_BACKEND_CONTRACT.md"))
    if contract is None:
        return bad("FE2.contract", "contracts/FRONTEND_BACKEND_CONTRACT.md missing", owner)
    rows = [r for r in docs.table_rows(contract) if r and re.fullmatch(r"C-\d+", r[0])]
    bad_rows = [f"{r[0]}: status {r[2] if len(r) > 2 else '?'}" for r in rows
                if len(r) < 4 or r[2].lower() not in ("verified", "unverified", "new")
                or (r[2].lower() == "verified" and not r[3])]
    return (bad("FE2.contract", "Capabilities not marked verified (with source), unverified or new",
                owner, bad_rows) if bad_rows
            else ok("FE2.contract", f"{len(rows)} capabilities, each ruled", owner))


def queue(ctx):
    owner = "fe-engineer"
    text, up = _need(ctx, "03-queue.md", owner)
    res = [state(ctx), up]
    if text is None:
        return res, {}
    known, _ = _reqs(ctx)
    ux_text = ctx.doc("01-ux.md") or ""
    pages, details = set(_ux_pages(ctx)), _blocks(ux_text, "PAGE")
    frames = set(_ui_frames(ctx))
    rows = _queue_rows(ctx)
    probs = []
    for q, b in rows.items():
        probs += [f"{q}: {k} missing" for k in ROW_FIELDS if not docs.field(b, k)]
        if docs.field(b, "Priority") not in ("P1", "P2", "P3"):
            probs.append(f"{q}: priority must be P1, P2 or P3")
        if (docs.field(b, "Side") or "").split(" ")[0].lower() not in ("frontend", "backend", "both"):
            probs.append(f"{q}: side {docs.field(b, 'Side')!r}")
        pg = docs.ids_in(docs.field(b, "Page") or "", "PAGE")
        if not pg or pg - pages:
            probs.append(f"{q}: page names no PAGE-nnn in 01-ux.md")
        fr = docs.field(b, "Frame") or ""
        if not NA.match(fr) and (not docs.ids_in(fr, "FRAME") or docs.ids_in(fr, "FRAME") - frames):
            probs.append(f"{q}: frame names no FRAME-nnn in 02-ui.md (or `n/a — <reason>`)")
        rq = docs.ids_in(docs.field(b, "REQ") or "", "REQ")
        if not rq or rq - known:
            probs.append(f"{q}: REQ names no known REQ-nnn")
    res.append(bad("FE2.rows", "No `### Q-nnn` rows", owner) if not rows else
               bad("FE2.rows", "Queue rows incomplete", owner, probs) if probs else
               ok("FE2.rows", f"{len(rows)} rows complete", owner))
    res.append(checks._length_check(ctx, "FE2.row-length", [(q, docs.words(b)) for q, b in rows.items()],
                                    "fe_row_words", owner, "queue row"))
    gaps = []
    for p in sorted(pages):
        mine = [b for b in rows.values() if p in docs.ids_in(docs.field(b, "Page") or "", "PAGE")]
        if not mine:
            gaps.append(f"{p}: no row")
            continue
        need = {s for s, v in _page_states(details.get(p)).items() if v == "yes"}
        got = set().union(*(_row_states(b) for b in mine))
        if need - got:
            gaps.append(f"{p}: states {sorted(need - got)} delivered by no row")
    used = set().union(*(docs.ids_in(docs.field(b, "Frame") or "", "FRAME") for b in rows.values())) if rows else set()
    gaps += [f"{f}: no row builds it" for f in sorted(frames - used)]
    res.append(bad("FE2.coverage", "Pages, states or frames no row delivers", owner, gaps) if gaps
               else ok("FE2.coverage", "Every page, state row and frame is delivered by a row", owner))
    res.append(_contract(ctx, owner))
    pending = [f"{d['dfb']}: {d['decision'] or 'no decision'}" for d in _feedback(ctx)
               if not re.match(r"(accepted|rejected)", d["decision"]) or not d["by"] or d["by"] in ("—", "-")]
    res.append(bad("FE2.feedback", "Design feedback without a decision (PLAYBOOK §3A)", owner, pending) if pending
               else ok("FE2.feedback", f"{len(_feedback(ctx))} design-feedback items decided", owner))
    return res, {"rows": sorted(rows)}


# ---------- UI stop: review sheet, approval ----------

def plan(ctx):
    owner = "orchestrator"
    res = [state(ctx)]
    need = ["fe-ux", "fe-ui", "fe-queue"]
    if (ctx.run / "00-requirements.md").exists():
        need.insert(0, "fe-product")
    red = _latest_ok(ctx, need)
    res.append(bad("FEP.gates", "Earlier gates not green", owner, red) if red
               else ok("FEP.gates", f"{', '.join(need)} green", owner))
    ui_text = ctx.doc("02-ui.md") or ""
    sheet = ["# UI review", "", "Confirm the frames in Figma and the queue below, or say what to change.",
             "Nothing outside § Scaffold is built before you do.", "",
             f"Figma file: {docs.field(ui_text, 'Figma file') or 'n/a (text mockups)'}", ""]
    sheet += ["## Pages", "", "| Page | Job |", "|---|---|",
              *(f"| {p} | {r[1] if len(r) > 1 else ''} |" for p, r in _ux_pages(ctx).items()), ""]
    sheet += ["## Frames", "", "| Frame | Page | State | Size | Link |", "|---|---|---|---|---|",
              *(f"| {' | '.join((r + [''] * 5)[:5])} |" for r in _ui_frames(ctx).values()), ""]
    fb = _feedback(ctx)
    if fb:
        sheet += ["## Design feedback decided", "", "| DFB | Decision | By | Needs you |", "|---|---|---|---|",
                  *(f"| {d['dfb']} | {d['decision']} | {d['by']} | {d['needs_user']} |" for d in fb), ""]
    rows = _queue_rows(ctx)
    clash = registry.conflicts(ctx, rows)
    if clash:
        reg = registry.active(registry.load(ctx))
        sheet += ["## Approved results this round may change", "",
                  "Keep each, or retire it (`fe-approve --retire OBS-nnn`) if the new design replaces it.", "",
                  "| Approved | Observable | Touched by |", "|---|---|---|",
                  *(f"| {k} | {reg[k]['observable']} | {', '.join(v)} |" for k, v in sorted(clash.items())), ""]
    sheet += ["## Queue — expected results you approve", "", "| Row | Priority | Frame | Observable |",
              "|---|---|---|---|",
              *(f"| {q} | {docs.field(b, 'Priority')} | {docs.field(b, 'Frame')} | {docs.field(b, 'Observable')} |"
                for q, b in rows.items()), ""]
    (ctx.gdir / "plan-review.md").parent.mkdir(parents=True, exist_ok=True)
    (ctx.gdir / "plan-review.md").write_text("\n".join(sheet) + "\n", encoding="utf-8")
    return res, {"review_sheet": f"{ctx.run_rel}/gates/plan-review.md", "rows": sorted(rows), "may_change": clash}


def _exports(ctx):
    """{FRAME: sha256 of evidence/design/FRAME-nnn.png | None}; empty for canvasless surfaces."""
    if _canvasless(ctx):
        return {}
    out = {}
    for f in _ui_frames(ctx):
        p = ctx.run / "evidence" / "design" / f"{f}.png"
        out[f] = hashlib.sha256(p.read_bytes()).hexdigest() if p.is_file() and p.stat().st_size else None
    return out


def approve(ctx, by, retire=()):
    """Lock each queue row and each frame export. Only after the user's yes at the UI stop."""
    p = read_json(ctx.gdir / "fe-plan-latest.json")
    if not p or p["overall"] != PASS:
        raise ConfigError("`fe-plan` has not passed; run it and get the user's confirmation first")
    exports = _exports(ctx)
    missing = sorted(f for f, h in exports.items() if h is None)
    if missing:
        raise ConfigError(f"frame exports missing: {missing} — save each as "
                          f"{ctx.run_rel}/evidence/design/FRAME-nnn.png (PLAYBOOK §3H.4)")
    rows = _queue_rows(ctx)
    locked = {q: _row_digest(b) for q, b in rows.items()}
    write_json(ctx.gdir / "observables-approved.json",
               {"approved_by": by, "date": utc_now()[:10], "rows": locked, "frames": exports})
    if retire:
        registry.retire(ctx, by, retire)
    return [ok("FEP.approve", f"Locked {len(locked)} observables and {len(exports)} frame exports, approved by {by}",
               "orchestrator", sorted(locked))], {}


def _observables(ctx, owner):
    approved = read_json(ctx.gdir / "observables-approved.json")
    if approved is None:
        return bad("FE.observables", "No approved observables: run the UI stop and `fe-approve`", "orchestrator")
    rows = _queue_rows(ctx)
    probs = [f"{q}: changed since approval on {approved['date']}" for q, h in approved["rows"].items()
             if q in rows and _row_digest(rows[q]) != h]
    probs += [f"{q}: never approved" for q in rows if q not in approved["rows"]]
    probs += [f"{q}: approved row removed" for q in approved["rows"] if q not in rows]
    now = _exports(ctx)
    probs += [f"{f}: frame export changed since approval" for f, h in (approved.get("frames") or {}).items()
              if now.get(f) != h]
    return (bad("FE.observables", "Approved observables or frames changed (only the user re-approves)", owner, probs)
            if probs else ok("FE.observables", f"{len(rows)} approved observables intact", owner))


# ---------- Phase 3: build ----------

def build(ctx):
    base = checks._baseline(ctx)
    run_diff = snap.diff(base["snapshot"], ctx.snapshot())
    res = [state(ctx)]
    roles, changed = checks.role_checks(ctx)
    res += roles
    res += checks._scan(ctx, base, run_diff)
    res.append(checks._dependency_check(ctx, base, run_diff, "03-queue.md", "fe-engineer", "FE3.dependencies"))
    for name in ("build", "lint", "typecheck"):
        res.append(checks._command_check(ctx, name, "fe-engineer")[0])
    t, r = checks._tests(ctx, "fe-engineer", base)
    approved = (ctx.gdir / "observables-approved.json").exists()
    one_stop = _state_json(ctx).get("design_stops") == 1
    code = [p for p in changed if not ctx.is_doc(p) and not ctx.is_test(p)]
    early = (bad("FE.observables", "One-stop run: no product code before the UI stop (Constitution §4.2; "
                 "PLAYBOOK Phase 2)", "orchestrator", code) if one_stop and code
             else na("FE.observables", "Before the UI stop: scaffold only", "fe-engineer"))
    res += [t, checks._test_file_drift(ctx, base, "fe-engineer", "FE3.test-drift"),
            _observables(ctx, "fe-engineer") if approved else early,
            registry.regression(ctx, r, "fe-engineer")]
    return res, {"writer_changed": changed, "counts": r["counts"] if r else None}


# ---------- Phase 4: verify, review ----------

def verify(ctx):
    base = checks._baseline(ctx)
    owner = "fe-tester"
    text, up = _need(ctx, "04-verification.md", owner)
    res = [state(ctx), up]
    res += checks.role_checks(ctx)[0]
    t, r = checks._tests(ctx, "fe-engineer", base)
    res += [t, checks._test_file_drift(ctx, base, owner, "FE4.test-drift"), _observables(ctx, "orchestrator")]
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
    res.append(bad("FE4.verdicts", "Rows without exactly one valid verdict", owner, probs) if probs
               else ok("FE4.verdicts", f"{len(verdicts)} rows with one verdict each", owner))
    manifest = re.search(r"evidence/verify-[\w.-]+/manifest\.md", text)
    if not manifest or not (ctx.run / manifest.group(0)).exists():
        res.append(bad("FE4.evidence", "Evidence manifest missing (the orchestrator captures, §3H)", "orchestrator"))
    else:
        cited = set(re.findall(r"`([\w.@-]+\.(?:html|json|txt|png|jpg|xml|log|yml|stdout|stderr))`", text))
        folder = (ctx.run / manifest.group(0)).parent
        absent = sorted(c for c in cited if not (folder / c).exists() and not (ctx.run / "evidence" / "design" / c).exists())
        res.append(bad("FE4.evidence", "Cited evidence files not in the capture folder", "orchestrator", absent)
                   if absent else ok("FE4.evidence", f"Manifest present; {len(cited)} cited files exist", owner))
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
        return res + [bad("FE4.capture-plan", str(e), owner)], {}
    probs = capture.plan_problems(plan, _rows_to_verify(ctx) + sorted(registry.capture_entries(ctx)))
    surface = _surface(ctx)
    if plan.get("surface") == "web" and surface and "browser" not in surface and "web" not in surface:
        probs.append(f"plan surface web, 01-ux.md says {surface!r}")
    res.append(bad("FE4.capture-plan", "Capture plan incomplete (PLAYBOOK §3H)", owner, probs) if probs
               else ok("FE4.capture-plan", f"{len(plan['captures'])} captures cover every row to verify", owner))
    return res, {}


def _capture_check(ctx, text):
    m = re.search(r"evidence/verify-([\w.-]+)/manifest\.md", text or "")
    if not m:
        return bad("FE4.capture", "04-verification.md names no evidence round", "orchestrator")
    try:
        plan = capture.load_plan(ctx)
    except ConfigError as e:
        return bad("FE4.capture", str(e), "orchestrator")
    build = read_json(ctx.gdir / "fe-build-latest.json")
    probs = capture.evidence_problems(ctx, ctx.run / "evidence" / f"verify-{m.group(1)}", plan,
                                      build["time"] if build else None)
    return (bad("FE4.capture", "Evidence incomplete, failed or stale: recapture (`gate.py capture`)",
                "orchestrator", probs) if probs
            else ok("FE4.capture", f"Round {m.group(1)}: every planned capture present, fresh and non-empty",
                    "orchestrator"))


def _row_tests(ctx, r):
    """Tests tagged with a queue row id (Q-###) must pass in this run."""
    locs = runner.tc_locations(ctx.project, checks._test_code(ctx), ctx.cfg, prefix="Q")
    if not locs:
        return na("FE4.row-tests", "No test is tagged with a queue row id", "fe-tester"), {}
    if not r or r.get("cases") is None:
        return na("FE4.row-tests", f"{len(locs)} rows tagged; pass status needs a JUnit report", "fe-tester"), {}
    seen = checks._observed_ids(locs, dict.fromkeys(locs), r["cases"])
    red = [f"{q}: {st}" for q, st in sorted(seen.items()) if st != "passed"]
    return (bad("FE4.row-tests", "Row-tagged tests not passing in this run", "fe-engineer", red) if red
            else ok("FE4.row-tests", f"{len(seen)} row-tagged tests passed", "fe-tester")), seen


def _where_exists(ctx, where):
    w = (where or "").strip().strip("`")
    m = re.fullmatch(r"([^:\s]+):(\d+)(?:-\d+)?", w)
    if m:
        p = ctx.project / m.group(1)
        if not p.is_file():
            return f"{m.group(1)} does not exist"
        if int(m.group(2)) > len(p.read_text(encoding="utf-8", errors="replace").splitlines()):
            return f"line {m.group(2)} beyond end of {m.group(1)}"
        return None
    if w and ((ctx.run / w).is_file() or (ctx.project / w).is_file()):
        return None
    return f"where {where!r} is neither path:line nor an existing file"


def _panel_expected(ctx):
    risk = _state_json(ctx).get("risk", "normal")
    return set(PANEL) if risk == "high" else {"fe-review-experience"}


def review(ctx):
    owner = "orchestrator"
    before = checks._load_mark(ctx, "fe-reviewer")["snapshot"]
    d = snap.diff(before, ctx.snapshot())
    # fe-tester runs beside the panel and writes tests; its scope is checked by fe-verify (ROLE.tester-scope).
    changed = [p for p in snap.changed(d)
               if not checks.glob_match(p, [f"{ctx.run_rel}/**"]) and not ctx.is_test(p)]
    res = [state(ctx),
           bad("FE4.tree-unchanged", "Files changed while reviewers ran (PLAYBOOK §4.4)", owner, changed)
           if changed else ok("FE4.tree-unchanged", "Tree unchanged during review", owner)]
    text, up = _need(ctx, "05-review.md", "fe-reviewer")
    res.append(up)
    if text is None:
        return res, {}
    head = "\n".join(text.splitlines()[:12])
    named = {p for p in PANEL if p in head}
    lacking = sorted(_panel_expected(ctx) - named)
    res.append(bad("FE4.panel", "Panel smaller than PLAYBOOK §6 requires for this risk", "orchestrator", lacking)
               if lacking else ok("FE4.panel", f"Panel: {', '.join(sorted(named))}", "orchestrator"))
    problems = []
    found = docs.findings(text)
    for fid, f in found.items():
        if f.get("severity") not in ("blocker", "major", "minor"):
            problems.append(f"{fid}: severity {f.get('severity')!r}")
        miss = _where_exists(ctx, f.get("where"))
        if miss:
            problems.append(f"{fid}: {miss}")
        if not (f.get("req") or "").strip():
            problems.append(f"{fid}: no UX, contract or WCAG reference")
        if not f.get("scenario"):
            problems.append(f"{fid}: no failure scenario")
    res.append(bad("FE4.findings", "Findings fail the format or point at nothing", "fe-reviewer", problems)
               if problems else ok("FE4.findings", f"{len(found)} findings well-formed and anchored", "fe-reviewer"))
    open_ = sorted(fid for fid, f in found.items()
                   if f.get("severity") in ("blocker", "major") and not checks.FIX_STATUS.search(f.get("status") or ""))
    return res, {"open_blocking": open_}


# ---------- Acceptance ----------

def _matrix(ctx, verdicts):
    """REQ → flow → page → queue row → verdict; every active REQ must end in a row verified done."""
    _, active = _reqs(ctx)
    ux_text = ctx.doc("01-ux.md") or ""
    flows = {f: docs.ids_in(docs.field(b, "Serves") or "", "REQ") for f, b in _blocks(ux_text, "FLOW").items()}
    pages = {p: docs.ids_in(" ".join(r), "REQ") for p, r in _ux_pages(ctx).items()}
    rows = _queue_rows(ctx)
    lines, gaps = ["| REQ | Flows | Pages | Rows (verdict) | Delivered |", "|---|---|---|---|---|"], []
    for req in sorted(active):
        fs = sorted(f for f, rs in flows.items() if req in rs)
        qs = sorted(q for q, b in rows.items() if req in docs.ids_in(docs.field(b, "REQ") or "", "REQ"))
        ps = sorted(p for p, rs in pages.items() if req in rs)
        cells = [f"{q} {verdicts.get(q, 'no verdict')}" for q in qs]
        done = bool(qs) and any(verdicts.get(q) == "done" for q in qs)
        lines.append(f"| {req} | {', '.join(fs) or '—'} | {', '.join(ps) or '—'} | {', '.join(cells) or '—'} | "
                     f"{'yes' if done else 'NO'} |")
        if not done:
            gaps.append(f"{req}: rows {cells or 'none'}")
    (ctx.gdir / "traceability.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return (bad("FEA.matrix", "Active REQs not delivered by a verified row", "orchestrator", gaps) if gaps
            else ok("FEA.matrix", f"{len(active)} active REQs delivered; matrix in {ctx.run_rel}/gates/traceability.md",
                    "orchestrator"))


def _trail(ctx):
    """Frontend run-log trail (PLAYBOOK §3G)."""
    events = [ev for _, ev in runlog.read(ctx.run / "run-log.jsonl")]
    problems = checks._trail_common(events)

    def first(pred):
        return next((e["seq"] for e in events if pred(e)), None)

    def approved(stop):
        return first(lambda e: e["event"] == "human" and e["stop"] == stop and e["decision"] == "approved")

    ui_ok = approved("UI")
    build = first(lambda e: e["event"] == "dispatch" and e["agent"] in ("fe-engineer", "be-developer")
                  and str(e["phase"]) == "3")
    if ui_ok is None:
        problems.append("no approved UI stop in the log")
    elif build is not None and build < ui_ok:
        problems.append(f"Phase 3 build dispatched (#{build}) before the UI was approved (#{ui_ok})")
    if _state_json(ctx).get("design_stops", 2) == 2:
        ux_ok = approved("UX")
        ui_first = first(lambda e: e["event"] == "dispatch" and e["agent"] == "fe-ui")
        if ux_ok is None:
            problems.append("two-stop run: no approved UX stop in the log")
        elif ui_first is not None and ui_first < ux_ok:
            problems.append(f"fe-ui dispatched (#{ui_first}) before the UX was approved (#{ux_ok})")
    return (bad("LOG.trail", "Run log does not account for the run", "orchestrator", problems) if problems
            else ok("LOG.trail", f"{len(events)} events account for every dispatch and the design stops", "orchestrator"))


def accept(ctx):
    owner = "orchestrator"
    res = [state(ctx)]
    red = _latest_ok(ctx, ["fe-build", "fe-verify", "fe-review"])
    b = read_json(ctx.gdir / "fe-build-latest.json")
    v = read_json(ctx.gdir / "fe-verify-latest.json")
    rv = read_json(ctx.gdir / "fe-review-latest.json")
    for name, g in (("fe-verify", v), ("fe-review", rv)):
        if b and g and g["time"] < b["time"]:
            red.append(f"{name} is older than the last fe-build")
    res.append(bad("FEA.gates", "Build, verification or review gate not green", owner, red) if red
               else ok("FEA.gates", "fe-build, fe-verify and fe-review green, in order", owner))
    blocking = ((rv or {}).get("data") or {}).get("open_blocking", [])
    res.append(bad("FEA.findings", "Blocker or major findings still open", owner, blocking) if blocking
               else ok("FEA.findings", "No open blocker or major finding", owner))
    verdicts = ((v or {}).get("data") or {}).get("verdicts", {})
    rows = _queue_rows(ctx)
    undone = [f"{q}: {verdicts.get(q, 'no verdict')}" for q, blk in rows.items()
              if not (docs.field(blk, "Status") or "").lower().startswith(("blocked", "skipped"))
              and verdicts.get(q) != "done"]
    res.append(bad("FEA.rows", "Rows not verified done (blocked or skipped rows must say why)", owner, undone)
               if undone else ok("FEA.rows", f"{len(rows)} rows done, blocked or skipped with a reason", owner))
    res.append(_matrix(ctx, verdicts))
    waiting = [d["dfb"] for d in _feedback(ctx)
               if d["needs_user"].startswith("yes") and (not d["user"] or d["user"] in ("—", "-"))]
    res.append(bad("FEA.feedback", "Design feedback that needs the user has no user decision", owner, waiting)
               if waiting else ok("FEA.feedback", "Every DFB that needs the user carries their decision", owner))
    res.append(_figma(ctx, owner))
    res.append(_trail(ctx))
    return res, {"not_machine_checked": ["Constitution §6.6: what the user must do to make it live",
                                         "Constitution §6.7: user accepted, with date"]}


PHASES = {"fe-product": product, "fe-ux": ux, "fe-ui": ui, "fe-queue": queue, "fe-plan": plan,
          "fe-build": build, "fe-capture-plan": capture_plan, "fe-verify": verify, "fe-review": review,
          "fe-accept": accept}
