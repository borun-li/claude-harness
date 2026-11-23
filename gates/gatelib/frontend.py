"""Frontend team gates (PLAYBOOK §3D in ~/.claude/frontend). Reuses the backend helpers. A run is one
directory (`checks.runs_root`): in a cross-stack run this team's documents sit beside the Backend
team's, and every gate here reads the run's own requirements, log, baseline and demo.

Phases: 0 product (be-analyst, frontend-only runs) · 1 UX (fe-ux), or 1E intake of an external design
(fe-ux, fe-ui) · 2 UI (fe-ui), scaffold, feasibility and queue (fe-engineer) · UI stop · 2b runnable
prototype (fe-engineer) · Prototype stop · 3 build · 4 verify (fe-tester) and review (panel +
fe-reviewer) · Acceptance · 5 after launch."""
import hashlib
import re

from . import capture, checks, docs, registry, runlog, runner, snap, taste
from .common import FAIL, PASS, ConfigError, bad, harness_cfg, na, ok, read_json, utc_now, write_json

STATES = ("loading", "empty", "success", "error", "permission")
EXTRA_STATES = ("offline", "partial")
HEX = re.compile(r"#[0-9A-Fa-f]{6}\b|#[0-9A-Fa-f]{3}\b")
# A node link, with the id as Figma writes it in a URL (`12-34`), in its API (`12:34`) or encoded (`12%3A34`).
FIGMA_NODE = re.compile(r"figma\.com/(design|file)/[\w-]+.*node-id=\d+(?:[-:]|%3A)\d+", re.I)
NA = re.compile(r"^\s*n/?a\b", re.I)
PANEL = ("fe-review-experience", "fe-review-accessibility", "fe-review-integration")
UX_FLOW_FIELDS = ("Serves", "Steps", "Success", "Failure", "Cancel", "Recovery", "Boundary")
ROW_FIELDS = ("Page", "Frame", "States", "REQ", "Files", "Observable", "Acceptance", "Depends on", "Status")


def _state_json(ctx):
    return read_json(ctx.run / "state.json") or {}


def _need(ctx, name, owner):
    text = ctx.doc(name)
    if not docs.nontrivial(text, ctx.cfg["min_doc_lines"]):
        return None, bad("ALL.upstream", f"{ctx.run_rel}/{name} missing or near-empty", owner)
    return text, ok("ALL.upstream", f"{name} present", owner)


def _blocks(text, prefix):
    return {k: v[0] for k, v in docs.id_blocks(text or "", prefix).items()}


_role_if = checks.role_if


def _prose(ctx, cid, text, owner):
    return checks._prose_check(ctx, cid, text or "", owner)


def _latest_ok(ctx, gates):
    out = []
    for g in gates:
        r = read_json(ctx.gdir / f"{g}-latest.json")
        if r is None or r["overall"] != PASS:
            out.append(f"{g}: {'never run' if r is None else r['overall']}")
    return out


def _table(text, prefix):
    """{ID: [cells]} for table rows whose first cell is PREFIX-nnn."""
    return {r[0]: r for r in docs.table_rows(text or "") if r and re.fullmatch(rf"{prefix}-\d+", r[0])}


# ---------- requirements (the Backend team's Phase 1, or Phase 0 of a frontend-only run) ----------

def _req_name(ctx):
    return next((n for n in checks.REQ_FILES if (ctx.run / n).exists()), "00-requirements.md")


def _reqs(ctx):
    """(all REQ ids, active REQs a person uses). Frontend-only runs tag them [interface]; when no REQ is
    tagged, every active REQ counts."""
    reqs = docs.requirements(ctx.doc(_req_name(ctx)) or "")
    active = docs.active_reqs(reqs)
    iface = {r for r in active if reqs[r]["interface"]}
    return checks.known_reqs(ctx, reqs), (iface or active)


def product(ctx):
    owner = "be-analyst"
    res, data = checks.phase1(ctx, name="00-requirements.md")
    _, iface = _reqs(ctx)
    if res[1]["status"] != FAIL:
        res.append(ok("FE0.interface", f"{len(iface)} active REQs a person uses", owner, sorted(iface)) if iface
                   else bad("FE0.interface", "No active REQ above the cut line", owner))
    return res, data


# ---------- Phase 1: UX ----------

def _external(ctx):
    """A design the user confirmed outside the harness: intake forms of 01-ux.md / 02-ui.md (PLAYBOOK §2.5)."""
    return _state_json(ctx).get("design") == "external"


REQ_CELL = re.compile(r"(?:REQ-\d+[\s,;/、和与]*)+")


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
    res = [checks.state(ctx), up] + _role_if(ctx, "fe-ux")
    if text is None:
        return res, {}
    user, surface = docs.field(text, "Named user"), docs.field(text, "Surface")
    res.append(ok("FE1.user", f"Named user: {user}", owner) if user
               else bad("FE1.user", "No named user (PLAYBOOK §1D)", owner))
    res.append(ok("FE1.surface", f"Surface: {surface}", owner) if surface and "|" not in surface
               else bad("FE1.surface", "Surface not chosen (PLAYBOOK §1C)", owner))
    known, active = _reqs(ctx)
    # The REQ cell only (a cell of nothing but REQ ids): a REQ named in the page's job is not a claim.
    pages = {p: set().union(*[docs.ids_in(c, "REQ") for c in r[1:] if REQ_CELL.fullmatch(c)])
             for p, r in _ux_pages(ctx).items()}
    bad_pages = [f"{p}: serves {sorted(s) or 'nothing'}" for p, s in pages.items() if not s or not s <= known]
    res.append(bad("FE1.pages", "No `PAGE-nnn` rows in the pages table", owner) if not pages else
               bad("FE1.pages", "Pages that serve no known REQ", owner, bad_pages) if bad_pages else
               ok("FE1.pages", f"{len(pages)} pages, each serving a REQ", owner))
    served = set().union(*pages.values()) if pages else set()
    unserved = sorted(active - served)
    res.append(bad("FE1.coverage", f"Active REQs in {_req_name(ctx)} with no page", owner, unserved) if unserved
               else ok("FE1.coverage", f"{len(active)} active REQs each served by a page", owner))
    external = _external(ctx)
    flows = _blocks(text, "FLOW")
    incomplete = [f"{f}: missing {[k for k in UX_FLOW_FIELDS if not docs.field(b, k)]}"
                  for f, b in flows.items() if not all(docs.field(b, k) for k in UX_FLOW_FIELDS)]
    res.append(na("FE1.flows", "External design: the flows are what it shows (intake form)", owner)
               if external and not incomplete else
               bad("FE1.flows", "No `### FLOW-nnn` blocks", owner) if not flows else
               bad("FE1.flows", "Flows without steps or every path", owner, incomplete) if incomplete else
               ok("FE1.flows", f"{len(flows)} flows with steps, success, failure, cancel, recovery, boundary", owner))
    details = _blocks(text, "PAGE")
    # A UX stop shows the user Figma wireframes; with no UX stop, or no canvas, a text block will do.
    in_figma = _state_json(ctx).get("design_stops") == 2 and not _canvasless(ctx)
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
        if not external and not (FIGMA_NODE.search(docs.field(b, "Wireframe") or "") if in_figma else "```" in b):
            no_wire.append(p)
    res.append(bad("FE1.states", "Pages without a full state table", owner, gaps) if gaps
               else ok("FE1.states", "Every page states loading, empty, success, error, permission", owner))
    want = ("a Figma wireframe (`- **Wireframe:** …?node-id=12-34`), shown at the UX stop" if in_figma
            else "a text wireframe (fenced block)")
    res.append(bad("FE1.wireframes", f"Pages without {want}", owner, no_wire) if no_wire
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
    events = runlog.events(ctx.run / "run-log.jsonl")
    used = sum(int(ev.get("figma_calls") or 0) for ev in events if ev["event"] == "return")
    if budget is None:
        return (na("FE.figma", f"No Figma budget set; {used} calls logged", owner) if not used else
                bad("FE.figma", f"{used} Figma calls logged but state.json figma.budget is unset", "orchestrator"))
    raised = any(ev["event"] == "human" and ev["stop"] == "Budget" and ev["decision"] == "approved" for ev in events)
    if used > budget and not raised:
        return bad("FE.figma", f"{used} Figma calls exceed the run budget {budget} without the user's yes "
                   "(`log human --stop Budget`)", "orchestrator")
    return ok("FE.figma", f"{used} of {budget} Figma calls used" + (" (raised by the user)" if raised else ""), owner)


STYLE_VALUE = re.compile(r"(?:colou?r|background|border|outline|fill|stroke|shadow)[\w-]*\**\s*:[^;`\n]*$", re.I)


def _raw_colours(text):
    """The `#hex` tokens of `text` that are colour values (FE2.tokens: colours live in the palette and
    the tokens table). In an inline code span every one is. Outside code, digits alone are an issue
    or PR number (`#123`) and never a colour; anything else is one after a CSS-like `property:`, or
    when it does not read as a lowercase word (a vowel and a consonant: `#decade`, `#add`). So
    `Use #FF0000 for errors` and `white (#fff)` name colours, `the #decade review` does not."""
    out = set()
    for line in text.splitlines():
        spans = [m.span() for m in re.finditer(r"`[^`]*`", line)]
        for m in HEX.finditer(line):
            digits = m.group(0)[1:]
            in_code = any(a < m.start() < b for a, b in spans)
            word = re.fullmatch(r"[a-f]+", digits) and set(digits) & set("ae") and set(digits) & set("bcdf")
            if in_code or (not digits.isdigit() and (STYLE_VALUE.search(line[:m.start()]) or not word)):
                out.add(m.group(0))
    return sorted(out)


def ui(ctx):
    owner = "fe-ui"
    text, up = _need(ctx, "02-ui.md", owner)
    res = [checks.state(ctx), up] + _role_if(ctx, "fe-ui")
    if text is None:
        return res, {}
    external = _external(ctx)
    plan = checks._section(text, [r"design plan", r"设计计划"]) or ""
    palette = checks._section(plan, [r"palette", r"配色"]) or ""
    hexes = set(HEX.findall(palette))
    lacking = [k for k, pats in (("Type", [r"\btype", r"字体"]), ("Layout", [r"layout", r"布局"]),
                                 ("Principles", [r"principles?", r"原则"]))
               if not checks._section(plan, pats)]
    res.append(na("FE2.plan", "External design: decided before the run (intake form)", owner)
               if external and not plan else
               bad("FE2.plan", "No `## Design plan` section", owner) if not plan else
               bad("FE2.plan", f"Palette has {len(hexes)} colours (4–6 named hex values)", owner)
               if not 4 <= len(hexes) <= 6 else
               bad("FE2.plan", "Design plan lacks sections", owner, lacking) if lacking else
               ok("FE2.plan", f"Design plan: {len(hexes)} colours, type, layout, principles", owner))
    check = checks._section(text, [r"self-check", r"自查"]) or ""
    filled = [r for r in docs.table_rows(check) if any(c for c in r)] or \
        [ln for ln in check.splitlines()[1:] if ln.strip().startswith("-") and len(ln.strip()) > 3]
    res.append(ok("FE2.self-check", "Self-check written", owner) if filled
               else na("FE2.self-check", "External design: no self-check (intake form)", owner) if external
               else bad("FE2.self-check", "Self-check empty: what read like a default, and what replaced it", owner))
    tokens = checks._section(text, [r"tokens?", r"令牌"]) or ""
    body = docs.mask_code(text.replace(tokens, "").replace(plan, ""))
    inline = _raw_colours(body)
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
        elif not FIGMA_NODE.search(link):
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
    res = [checks.state(ctx), up]
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
    if rows:
        res.append(checks.unique_ids_check(ctx, "FE2.row-ids", rows, ("03-queue.md",), "Q", owner))
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


# ---------- Prototype stop: review sheet, approval ----------

# Both teams' gates write into the run's one `gates/`: the Backend team's `p2` and `p7` own
# `plan-review.md` and `traceability.md`.
PLAN_SHEET = "fe-plan-review.md"
MATRIX = "fe-traceability.md"


def plan(ctx):
    owner = "orchestrator"
    res = [checks.state(ctx)]
    need = ["fe-ux", "fe-ui", "fe-queue"]
    if (ctx.run / "00-requirements.md").exists():
        need.insert(0, "fe-product")
    red = _latest_ok(ctx, need)
    res.append(bad("FEP.gates", "Earlier gates not green", owner, red) if red
               else ok("FEP.gates", f"{', '.join(need)} green", owner))
    ui_text = ctx.doc("02-ui.md") or ""
    sheet = ["# Prototype review", "", "Try the prototype, then confirm the expected results below, or say "
             "what to change. Rows are built after you confirm.", "",
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
    if not ctx.dry:
        (ctx.gdir / PLAN_SHEET).parent.mkdir(parents=True, exist_ok=True)
        (ctx.gdir / PLAN_SHEET).write_text("\n".join(sheet) + "\n", encoding="utf-8")
    return res, {"review_sheet": f"{ctx.run_rel}/gates/{PLAN_SHEET}", "rows": sorted(rows), "may_change": clash}


def _exports(ctx):
    """{FRAME: sha256 of evidence/design/FRAME-nnn.png | None}; empty for canvasless surfaces."""
    if _canvasless(ctx):
        return {}
    out = {}
    for f in _ui_frames(ctx):
        p = ctx.run / "evidence" / "design" / f"{f}.png"
        out[f] = hashlib.sha256(p.read_bytes()).hexdigest() if p.is_file() and p.stat().st_size else None
    return out


def approve(ctx, by, retire=(), because=None):
    """Lock each queue row and each frame export: after the user's yes at the Prototype stop, or to
    re-lock what a newer decision replaced (`because`; Constitution §5)."""
    if ctx.dry:
        return [na("FEP.approve", checks.DRY, "orchestrator")], {}
    p = read_json(ctx.gdir / "fe-plan-latest.json")
    if not p or p["overall"] != PASS:
        raise ConfigError("`fe-plan` has not passed; run it and get the user's confirmation first")
    exports = _exports(ctx)
    missing = sorted(f for f, h in exports.items() if h is None)
    if missing:
        raise ConfigError(f"frame exports missing: {missing} — save each as "
                          f"{ctx.run_rel}/evidence/design/FRAME-nnn.png (PLAYBOOK §3H)")
    rows = _queue_rows(ctx)
    locked = {q: _row_digest(b) for q, b in rows.items()}
    write_json(ctx.gdir / "observables-approved.json",
               {"approved_by": by, "date": utc_now()[:10], "rows": locked, "frames": exports,
                **({"because": because} if because else {})})
    if retire:
        registry.retire(ctx, by, retire, because)
    return [ok("FEP.approve", f"Locked {len(locked)} observables and {len(exports)} frame exports, approved by {by}",
               "orchestrator", sorted(locked))], {}


def _observables(ctx, owner):
    approved = read_json(ctx.gdir / "observables-approved.json")
    if approved is None:
        return bad("FE.observables", "No approved observables: run the Prototype stop and `fe-approve`", "orchestrator")
    rows = _queue_rows(ctx)
    probs = [f"{q}: changed since approval on {approved['date']}" for q, h in approved["rows"].items()
             if q in rows and _row_digest(rows[q]) != h]
    probs += [f"{q}: never approved" for q in rows if q not in approved["rows"]]
    probs += [f"{q}: approved row removed" for q in approved["rows"] if q not in rows]
    now = _exports(ctx)
    probs += [f"{f}: frame export changed since approval" for f, h in (approved.get("frames") or {}).items()
              if now.get(f) != h]
    return (bad("FE.observables", "Approved observables or frames changed (re-lock: the user's yes, or --because "
                "a newer decision)", owner, probs)
            if probs else ok("FE.observables", f"{len(rows)} approved observables intact", owner))


# ---------- Phase 3: build ----------

def build(ctx):
    base = checks._baseline(ctx)
    run_diff = snap.diff(base["snapshot"], ctx.snapshot())
    res = [checks.state(ctx)]
    roles, changed = checks.role_checks(ctx)
    res += roles
    scan = checks._scan(ctx, base, run_diff)
    for hit in scan:  # at this team's build gate, what the scan finds is its engineer's
        hit["owner"] = "fe-engineer"
    res += scan
    res.append(checks._dependency_check(ctx, base, run_diff, "03-queue.md", "fe-engineer", "FE3.dependencies"))
    for name in ("build", "lint", "typecheck"):
        res.append(checks._command_check(ctx, name, "fe-engineer")[0])
    # A project may give the frontend its own suite (`commands.fe_test`); fe-verify runs the whole one.
    own = bool(ctx.cmd("fe_test"))
    t, r = checks._tests(ctx, "fe-engineer", base, command="fe_test" if own else "test")
    approved = (ctx.gdir / "observables-approved.json").exists()
    one_stop = _state_json(ctx).get("design_stops") in (0, 1)
    code = [p for p in changed if not ctx.is_doc(p) and not ctx.is_test(p)]
    ui_ok = any(ev["event"] == "human" and ev["stop"] == "UI" and ev["decision"] == "approved"
                for ev in runlog.events(ctx.run / "run-log.jsonl"))
    early = (bad("FE.observables", "No product code before the design is confirmed (Constitution §4.2; "
                 "PLAYBOOK Phase 2)", "orchestrator", code) if one_stop and code and not ui_ok
             else na("FE.observables", "Before the Prototype stop: scaffold and prototype only", "fe-engineer"))
    res += [t, checks._test_file_drift(ctx, base, "fe-engineer", "FE3.test-drift"),
            _observables(ctx, "fe-engineer") if approved else early,
            registry.regression(ctx, r, "fe-engineer", partial=own)]
    return res, {"writer_changed": changed, "counts": r["counts"] if r else None}


# ---------- Phase 4: verify, review ----------

def verify(ctx):
    base = checks._baseline(ctx)
    owner = "fe-tester"
    text, up = _need(ctx, "04-verification.md", owner)
    res = [checks.state(ctx), up]
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
    manifest, reported = _evidence_manifest(text), []
    if not manifest or not (ctx.run / manifest.group(0)).exists():
        res.append(bad("FE4.evidence", "Evidence manifest missing (the orchestrator captures, §3H)", "orchestrator"))
    else:
        cited, absent = _cited_evidence(ctx, text, (ctx.run / manifest.group(0)).parent)
        res.append(bad("FE4.evidence", "Cited evidence files not in the capture folder", "orchestrator", absent)
                   if absent else ok("FE4.evidence", f"Manifest present; {len(cited)} cited files exist", owner))
        # Reported, never failing: what the captured pages measure against the configured taste values.
        reported, pages, why = taste.notes(ctx, (ctx.run / manifest.group(0)).parent)
        if not why:
            res.append(ok("FE4.taste", f"Taste measures on {pages} captured pages: {len(reported)} to look at "
                                       "(reported, they fail nothing)", "fe-engineer", reported))
    captured = registry.capture_entries(ctx)
    unjudged = [f"{k}: {verdicts.get(k, ['no verdict'])[0]}" for k in captured if verdicts.get(k, [None])[0] != "done"]
    if captured:
        res.append(bad("FE.regression-captures", "Registered capture-guarded observables not re-verified done",
                       "fe-tester", unjudged) if unjudged
                   else ok("FE.regression-captures", f"{len(captured)} capture-guarded observables re-verified", "fe-tester"))
    return res, {"verdicts": {q: v[0] for q, v in verdicts.items()}, "row_tests": row_seen,
                 "reported": [f"FE4.taste: {n}" for n in reported]}


FILE_REF = re.compile(r"`((?:[\w.@-]+/)*[\w.@-]+\.(?:html|json|txt|png|jpg|xml|log|yml|stdout|stderr))`")


def _cited_evidence(ctx, text, folder):
    """(the backticked files 04-verification.md cites as evidence, those that do not exist). A file
    is evidence when its path is under an `evidence/` dir, or its name is a capture's: `<id>@<size>.*`,
    one the round's manifest lists or names by id, or one that starts with a row, observable or
    frame id. `package.json` in a sentence is neither."""
    entries = (read_json(folder / "manifest.json") or {}).get("entries", [])
    ids = {str(e.get("id")) for e in entries}
    listed = {f for e in entries for f in (e.get("files") or {}).values()}
    cited, absent = set(), []
    for ref in sorted(set(FILE_REF.findall(text))):
        name = ref.rsplit("/", 1)[-1]
        if "/" in ref:
            if "evidence/" not in ref:
                continue
            found = (ctx.run / ref).exists() or (ctx.project / ref).exists()
        elif ("@" in name or name in listed or re.match(r"(?:Q|OBS|FRAME)-\d+", name)
              or any(name.startswith((i + ".", i + "@")) for i in ids)):
            found = (folder / name).exists() or (ctx.run / "evidence" / "design" / name).exists()
        else:
            continue
        cited.add(ref)
        absent += [] if found else [ref]
    return cited, absent


def _rows_to_verify(ctx):
    return sorted(q for q, b in _queue_rows(ctx).items()
                  if not (docs.field(b, "Status") or "").lower().startswith(("blocked", "skipped")))


def capture_plan(ctx):
    owner = "orchestrator"
    res = [checks.state(ctx)]
    try:
        plan = capture.load_plan(ctx)
    except ConfigError as e:
        return res + [bad("FE4.capture-plan", str(e), owner)], {}
    rows, todo = _queue_rows(ctx), _rows_to_verify(ctx)
    viewports = [w for w in harness_cfg(ctx.project).get("viewports") or [] if isinstance(w, int)]
    probs = capture.plan_problems(plan, todo + sorted(registry.capture_entries(ctx)),
                                  {q: _row_states(rows[q]) for q in todo}, viewports, ctx.snapshot())
    surface = _surface(ctx)
    if plan.get("surface") == "web" and surface and "browser" not in surface and "web" not in surface:
        probs.append(f"plan surface web, 01-ux.md says {surface!r}")
    res.append(bad("FE4.capture-plan", "Capture plan incomplete (PLAYBOOK §3H)", owner, probs) if probs
               else ok("FE4.capture-plan", f"{len(plan['captures'])} captures cover every row to verify, in each "
                       "of its states and at every configured size", owner))
    return res, {}


MANIFEST = re.compile(r"evidence/verify-([\w.-]+)/manifest\.md")


def _evidence_manifest(text):
    """The round 04-verification.md is judged on: the one its header's `Evidence:` names, else the
    latest round it names (an earlier round mentioned in passing is not the evidence)."""
    head = re.search(r"Evidence\W{0,4}[ \t]*`?(evidence/verify-[\w.-]+/manifest\.md)", text or "")
    if head:
        return MANIFEST.search(text, head.start(1))
    found = list(MANIFEST.finditer(text or ""))
    key = lambda x: [int(n) if n.isdigit() else n for n in re.split(r"(\d+)", x.group(1))]
    return max(found, key=key) if found else None


def _capture_check(ctx, text):
    m = _evidence_manifest(text)
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
    if ctx.dry:
        return na("FE4.row-tests", checks.DRY, "fe-tester"), {}
    if not r or r.get("cases") is None:
        return na("FE4.row-tests", f"{len(locs)} rows tagged, but whether they pass is not read: "
                  f"{runner.no_cases(r)}", "fe-tester"), {}
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


def _review_round(ctx):
    """(panelists, coordinated) of the review of the current build: the panelists dispatched since
    this team's last builder dispatch, and whether `fe-reviewer` was."""
    events = runlog.events(ctx.run / "run-log.jsonl")
    built = max((e["seq"] for e in checks._team_dispatches(ctx, events, "fe")
                 if e["agent"] in ("fe-engineer", "be-developer")), default=-1)
    out = {e["agent"] for e in events if e["event"] == "dispatch" and e["seq"] > built}
    return sorted(out & set(PANEL)), "fe-reviewer" in out


def _tree_unchanged(ctx):
    owner = "orchestrator"
    if ctx.dry:
        return na("FE4.tree-unchanged", checks.DRY, owner)
    before = checks._load_mark(ctx, "fe-reviewer")["snapshot"]
    d = snap.diff(before, ctx.snapshot())
    # fe-tester runs beside the panel and writes tests; its scope is checked by fe-verify (ROLE.tester-scope).
    changed = [p for p in snap.changed(d)
               if not checks.glob_match(p, checks.run_dir_globs(ctx)) and not ctx.is_test(p)]
    # Every reviewer dispatch takes a new mark: a change stays a failure until it is undone (checks.carry).
    open_ = checks.carry(ctx, "FE4.tree-unchanged", "fe-reviewer", changed, before)
    return (bad("FE4.tree-unchanged", "Files changed while reviewers ran (PLAYBOOK §4.3)", owner, open_)
            if open_ else ok("FE4.tree-unchanged", "Tree unchanged during review", owner))


def review(ctx):
    res = [checks.state(ctx), _tree_unchanged(ctx)]
    # One panelist and no coordinator: the orchestrator files that panelist's review as 05-review.md.
    panel, coordinated = _review_round(ctx)
    sole = panel[0] if len(panel) == 1 and not coordinated else None
    author = sole or "fe-reviewer"
    text, up = _need(ctx, "05-review.md", author)
    res.append(up)
    if text is None:
        return res, {}
    head = "\n".join(text.splitlines()[:12])
    named = {p for p in PANEL if p in head} | ({sole} if sole else set())
    lacking = sorted(_panel_expected(ctx) - named)
    res.append(bad("FE4.panel", "Panel smaller than PLAYBOOK §6 requires for this risk", "orchestrator", lacking)
               if lacking else
               bad("FE4.panel", f"{len(panel)} panelists ran and no fe-reviewer merged their candidates "
                   "(PLAYBOOK Phase 4)", "orchestrator", panel) if len(panel) > 1 and not coordinated else
               ok("FE4.panel", f"Panel: {', '.join(sorted(named))}" + (", the sole reviewer" if sole else ""),
                  "orchestrator"))
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
    res.append(bad("FE4.findings", "Findings fail the format or point at nothing", author, problems)
               if problems else ok("FE4.findings", f"{len(found)} findings well-formed and anchored", author))
    open_ = sorted(fid for fid, f in found.items()
                   if f.get("severity") in ("blocker", "major") and not checks.finding_closed(f.get("status")))
    return res, {"open_blocking": open_}


# ---------- Acceptance ----------

def _matrix(ctx, verdicts):
    """REQ → flow → page → queue row → verdict; every active REQ must end in a row verified done."""
    _, active = _reqs(ctx)
    ux_text = ctx.doc("01-ux.md") or ""
    flows = {f: docs.ids_in(docs.field(b, "Serves") or "", "REQ") for f, b in _blocks(ux_text, "FLOW").items()}
    # The REQ cell only (a cell of nothing but REQ ids): a REQ named in the page's job is not a claim.
    pages = {p: set().union(*[docs.ids_in(c, "REQ") for c in r[1:] if REQ_CELL.fullmatch(c)])
             for p, r in _ux_pages(ctx).items()}
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
    if not ctx.dry:
        (ctx.gdir / MATRIX).parent.mkdir(parents=True, exist_ok=True)
        (ctx.gdir / MATRIX).write_text("\n".join(lines) + "\n", encoding="utf-8")
    return (bad("FEA.matrix", "Active REQs not delivered by a verified row", "orchestrator", gaps) if gaps
            else ok("FEA.matrix", f"{len(active)} active REQs delivered; matrix in {ctx.run_rel}/gates/{MATRIX}",
                    "orchestrator"))


def _trail(ctx):
    """Frontend run-log trail (PLAYBOOK §3G). Both teams log into the one run log and each numbers
    its own steps: the order of the design stops is read from this team's dispatches."""
    events = runlog.events(ctx.run / "run-log.jsonl")
    mine = checks._team_dispatches(ctx, events, "fe")
    problems = checks._trail_common(events)

    def first(pred, among=events):
        return next((e["seq"] for e in among if pred(e)), None)

    def approved(stop):
        return first(lambda e: e["event"] == "human" and e["stop"] == stop and e["decision"] == "approved")

    ui_ok = approved("UI")
    build = first(lambda e: e["agent"] in ("fe-engineer", "be-developer") and str(e["phase"]) == "3", mine)
    proto = first(lambda e: str(e["phase"]) == "2b", mine)
    if ui_ok is None:
        problems.append("no approved UI stop in the log (an external design logs it at kickoff)")
    else:
        if build is not None and build < ui_ok:
            problems.append(f"Phase 3 build dispatched (#{build}) before the UI was approved (#{ui_ok})")
        if proto is not None and proto < ui_ok:
            problems.append(f"prototype dispatched (#{proto}) before the design was approved (#{ui_ok})")
    # The user tries a running prototype before the build (Constitution §2.7).
    proto_ok = approved("Prototype")
    if proto_ok is None:
        problems.append("no approved Prototype stop in the log")
    elif build is not None and build < proto_ok:
        problems.append(f"Phase 3 build dispatched (#{build}) before the Prototype was approved (#{proto_ok})")
    if _state_json(ctx).get("design_stops", 2) == 2:
        ux_ok = approved("UX")
        ui_first = first(lambda e: e["agent"] == "fe-ui", mine)
        if ux_ok is None:
            problems.append("two-stop run: no approved UX stop in the log")
        elif ui_first is not None and ui_first < ux_ok:
            problems.append(f"fe-ui dispatched (#{ui_first}) before the UX was approved (#{ux_ok})")
    return (bad("LOG.trail", "Run log does not account for the run", "orchestrator", problems) if problems
            else ok("LOG.trail", f"{len(events)} events account for every dispatch and the design stops", "orchestrator"))


def accept(ctx):
    owner = "orchestrator"
    res = [checks.state(ctx)]
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
    res.append(checks.demo(ctx))
    return res, {"not_machine_checked": ["Constitution §6.6: what the user must do to make it live",
                                         "Constitution §6.7: user accepted, with date"]}


PHASES = {"fe-product": product, "fe-ux": ux, "fe-ui": ui, "fe-queue": queue, "fe-plan": plan,
          "fe-build": build, "fe-capture-plan": capture_plan, "fe-verify": verify, "fe-review": review,
          "fe-accept": accept}
