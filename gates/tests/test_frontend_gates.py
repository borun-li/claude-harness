#!/usr/bin/env python3
"""Regression matrix for the frontend gates (fe-*, 7.0): red on each defect, green on innocent work.
Run: python3 tests/test_frontend_gates.py"""
import hashlib
import json
import os
import pathlib
import subprocess
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from test_gates import GATE, PY, Base, sh  # noqa: E402

FILL = "\n".join(["filler"] * 8) + "\n"

REQS = """# Requirements — Duplicate upload message

## 0. Understanding
- **Asked:** "tell them it is a duplicate"
- **Means:** a duplicate upload shows why and links to the original
- **Ambiguities:** none

## 1. Requirements
### REQ-001 — Duplicate notice [interface]
- **Cut:** above
- **Behaviour:** a duplicate upload shows a notice with a link to the original
- **Accept:** Given file X stored, When X is uploaded, Then the user reads it already exists and can open it
- **Source:** "tell them it is a duplicate"
- **Fixtures:** n/a — frontend run

## 2. Non-goals
- merging duplicates
"""

UX = """# UX — Duplicate upload message

- **Named user:** office admin uploading contracts daily
- **Surface:** web

## 1. Pages
| Page | Job | Serves | Form — why |
|---|---|---|---|
| PAGE-001 | Upload one file | REQ-001 | form — one decision |

## 3. Flows
### FLOW-001 — Upload a duplicate
- **Serves:** REQ-001
- **Steps:** 1. Choose 2. Upload 3. See notice
- **Success:** the original opens
- **Failure:** network error, Retry
- **Cancel:** back to empty form
- **Recovery:** Retry keeps the file
- **Boundary:** over 20 MB rejected first

## 4. Page details
### PAGE-001 — Upload
| State | User sees | Words | Can do next |
|---|---|---|---|
| loading | bar | Uploading | Cancel |
| empty | picker | Choose a file | choose |
| success | notice | Uploaded | open |
| error | amber notice | Already uploaded | open original |
| permission | n/a — every admin can upload | | |

- **Wireframe:** https://www.figma.com/design/AbCdEfGhIjKlMnOpQrStUv/Upload?node-id=5-1

```text
[ picker ] [ Upload ]
[ notice ]
```
"""

UI = """# UI — Duplicate upload message

- **Figma file:** https://www.figma.com/design/AbCdEfGhIjKlMnOpQrStUv/Upload

## 1. Design plan
### Palette
| Name | Hex | Role |
|---|---|---|
| Ink | #1F2328 | text |
| Paper | #FFFFFF | surface |
| Line | #D0D7DE | borders |
| Caution | #9A6700 | notice |

### Type
| Role | Typeface | Size |
|---|---|---|
| Body | Inter | 14 |

### Layout
- one column

### Principles
- answer where the action was

## 2. Self-check
| Read like a default | Replaced by | Why |
|---|---|---|
| corner toast | inline notice | the eye is on the picker |

## 3. Tokens
| Token | Layer | Value | Use |
|---|---|---|---|
| color.notice | semantic | #9A6700 | notice |

## 4. Components
### CMP-001 — Notice
- **States:** default, focus

## 5. Frames
| Frame | Page | State | Size | Figma |
|---|---|---|---|---|
| FRAME-001 | PAGE-001 | error | 1440 | https://www.figma.com/design/AbCdEfGhIjKlMnOpQrStUv/Upload?node-id=1-2 |
"""

CONTRACT = """# Contract
## 1. Capabilities
| # | Capability | Status | Source | Needed by | Backend DES |
|---|---|---|---|---|---|
| C-01 | duplicate detection | verified | docs/backend/03-detailed-design.md DES-002 | PAGE-001 | DES-002 |
"""

QUEUE = """# Queue

## Scaffold
| File | What it does |
|---|---|
| `web/api.js` | maps 409 to duplicate |

### Q-001 — Duplicate notice
- **Page:** PAGE-001
- **Frame:** FRAME-001
- **States:** loading, empty, success, error
- **REQ:** REQ-001
- **Files:** `web/notice.html`
- **Observable:** an amber notice reads "Already uploaded" with a link to the original
- **Acceptance:** notice text and link match at 1440 and 375
- **Priority:** P1
- **Side:** frontend
- **Depends on:** none
- **Status:** queued
"""

FEEDBACK = """# Feedback

## Design feedback
| DFB | Raised by | To | Item | Reason and evidence | Decision | Decided by | Needs user | User decision |
|---|---|---|---|---|---|---|---|---|
| DFB-001 | fe-engineer | fe-ui | FRAME-001 | too wide at 375 | accepted — link on its own line | fe-ui #2 | no | — |
"""

VERIFY = """# Verification

- Evidence: `evidence/verify-1/manifest.md`

## Verdicts
| Row | Verdict | Evidence | Note |
|---|---|---|---|
| Q-001 | done | `Q-001-dup@80x24.stdout` · duplicate · 80x24 | matches |
"""

REVIEW = """# Review

- Panelists run: fe-review-experience — accessibility and integration not needed (PLAYBOOK §6)

## 2. Findings
| ID | Severity | Panelist | Where | Ref | Claim |
|---|---|---|---|---|---|
| FND-001 | minor | experience | web/notice.html:1 | PAGE-001 error | icon 1px off |

### FND-001 — icon 1px off
- **Scenario:** the admin sees a slightly misaligned icon
- **Status:** deferred
"""

TERMINAL_PLAN = {"surface": "terminal", "captures": [
    {"id": "Q-001-dup", "row": "Q-001", "state": "duplicate", "command": "cat web/notice.html"}]}

FE_STATE = {"harness_version": "7.0.0", "feature": "dup", "status": "in_progress", "tier": "full",
            "risk": "normal", "design_stops": 2, "current_phase": 1, "phases": [], "models": {},
            "goal": {"change": "the list page shows rows", "check": "open the list page"}}

DOCS = (("00-requirements.md", REQS), ("01-ux.md", UX), ("02-ui.md", UI), ("06-feedback.md", FEEDBACK))


class FrontBase(Base):
    def setUp(self):
        super().setUp()
        p = self.p
        p.fe = p.root / "docs" / "frontend"
        p.write("docs/frontend/state.json", json.dumps(FE_STATE))
        for n, t in DOCS:
            p.write(f"docs/frontend/{n}", t + FILL)
        p.write("contracts/FRONTEND_BACKEND_CONTRACT.md", CONTRACT)
        self.fe_log("dispatch", "--agent", "fe-ux", "--model", "opus", "--step", "1", "--note", "ux")
        self.fe_log("return", "--agent", "fe-ux", "--step", "1", "--status", "ok", "--note", "ux")

    def fe(self, *args):
        r = subprocess.run([PY, str(GATE), *args, "--project", str(self.p.root)], capture_output=True, text=True)
        rp = self.p.fe / "gates" / f"{args[0]}-latest.json"
        return r.returncode, r.stdout + r.stderr, (json.loads(rp.read_text()) if rp.exists() else None)

    def capture(self, round_no="1"):
        r = subprocess.run([PY, str(GATE), "capture", "--round", round_no, "--project", str(self.p.root)],
                           capture_output=True, text=True)
        return r.returncode, r.stdout + r.stderr

    def fe_log(self, *args):
        return subprocess.run([PY, str(GATE), "log", *args, "--team", "frontend", "--project", str(self.p.root)],
                              capture_output=True, text=True).returncode

    def fe_dispatch(self, role, step="x", figma=None):
        subprocess.run([PY, str(GATE), "mark", "--role", role, "--team", "frontend", "--project", str(self.p.root)],
                       capture_output=True, text=True)
        budget = (json.loads(self.p.read("docs/frontend/state.json")).get("figma") or {}).get("budget")
        left = ["--figma-left", str(budget)] if budget is not None and role in ("fe-ui", "fe-engineer") else []
        self.fe_log("dispatch", "--agent", role, "--model", "opus", "--step", step, "--note", "work", *left)
        extra = ["--figma-calls", str(figma)] if figma is not None else []
        self.fe_log("return", "--agent", role, "--step", step, "--status", "ok", "--note", "done", *extra)

    def st(self, rep, cid):
        return self.p.status(rep, cid)

    def details(self, rep, cid):
        return " ".join(next(c for c in rep["checks"] if c["id"] == cid)["details"])

    def set_state(self, **kw):
        s = json.loads(self.p.read("docs/frontend/state.json"))
        s.update(kw)
        self.p.write("docs/frontend/state.json", json.dumps(s))

    def export_frames(self):
        self.p.write("docs/frontend/evidence/design/FRAME-001.png", "PNG-bytes-of-the-confirmed-frame")

    def to_build(self):
        """Design gates green, UX and UI confirmed, frames exported, queue approved, baseline, build dispatched."""
        self.p.write("docs/frontend/03-queue.md", QUEUE + FILL)
        for g in ("fe-product", "fe-ux", "fe-ui", "fe-queue", "fe-plan"):
            code, out, _ = self.fe(g)
            assert code == 0, f"{g}: {out}"
        self.fe_log("human", "--stop", "UX", "--decision", "approved", "--by", "user", "--note", "ok")
        self.fe_log("human", "--stop", "UI", "--decision", "approved", "--by", "user", "--note", "ok")
        self.export_frames()
        code, out, _ = self.fe("fe-approve", "--by", "user")
        assert code == 0, out
        r = subprocess.run([PY, str(GATE), "baseline", "--team", "frontend", "--project", str(self.p.root)],
                           capture_output=True, text=True)
        assert r.returncode == 0, r.stdout + r.stderr
        self.fe_dispatch("fe-engineer", step="3")

    def review_ok(self, text=REVIEW):
        subprocess.run([PY, str(GATE), "mark", "--role", "fe-reviewer", "--team", "frontend",
                        "--project", str(self.p.root)], capture_output=True, text=True)
        self.p.write("docs/frontend/05-review.md", text + FILL)
        return self.fe("fe-review")


class DesignGates(FrontBase):
    def test_all_design_gates_green(self):
        self.p.write("docs/frontend/03-queue.md", QUEUE + FILL)
        for g in ("fe-product", "fe-ux", "fe-ui", "fe-queue", "fe-plan"):
            code, out, _ = self.fe(g)
            self.assertEqual(code, 0, f"{g}: {out}")
        sheet = (self.p.fe / "gates" / "plan-review.md").read_text()
        for needle in ("| Q-001 | P1 | FRAME-001 | an amber notice", "| DFB-001 | accepted", "node-id=1-2"):
            self.assertIn(needle, sheet)

    def test_state_needs_the_users_goal(self):
        self.p.write("docs/frontend/state.json", json.dumps({k: v for k, v in FE_STATE.items() if k != "goal"}))
        self.assertEqual(self.st(self.fe("fe-product")[2], "ALL.state"), "fail")

    def test_frontend_round_cap_reads_frontend_config(self):
        self.p.write(".claude/frontend.json", json.dumps({"loops": {"max_rounds": 1}}))
        args = ("dispatch", "--agent", "fe-ui", "--model", "opus", "--step", "2", "--note", "revise", "--redo")
        self.assertEqual([self.fe_log(*args) for _ in range(2)], [0, 3])

    def test_product_needs_an_active_req(self):
        self.p.write("docs/frontend/00-requirements.md", REQS.replace("- **Cut:** above", "- **Cut:** below") + FILL)
        self.assertEqual(self.st(self.fe("fe-product")[2], "FE0.interface"), "fail")

    def test_ux_defects(self):
        t = UX.replace("office admin uploading contracts daily", "{one concrete user}")
        t = t.replace("| PAGE-001 | Upload one file | REQ-001 |", "| PAGE-001 | Upload one file | REQ-009 |")
        t = t.replace("- **Steps:** 1. Choose 2. Upload 3. See notice\n", "")
        t = t.replace("| permission | n/a — every admin can upload | | |\n", "").replace("?node-id=5-1", "")
        self.p.write("docs/frontend/01-ux.md", t + FILL)
        rep = self.fe("fe-ux")[2]
        for cid in ("FE1.user", "FE1.pages", "FE1.coverage", "FE1.flows", "FE1.states", "FE1.wireframes"):
            self.assertEqual(self.st(rep, cid), "fail", cid)

    def test_wireframe_medium_follows_the_ux_stop(self):
        text_only = UX.replace("- **Wireframe:** https://www.figma.com/design/AbCdEfGhIjKlMnOpQrStUv/Upload?node-id=5-1\n", "")
        self.p.write("docs/frontend/01-ux.md", text_only + FILL)
        self.assertEqual(self.st(self.fe("fe-ux")[2], "FE1.wireframes"), "fail")  # two stops, web: Figma
        self.set_state(design_stops=1)
        self.assertEqual(self.st(self.fe("fe-ux")[2], "FE1.wireframes"), "pass")  # no UX stop: text will do
        self.set_state(design_stops=2)
        self.p.write("docs/frontend/01-ux.md", text_only.replace("- **Surface:** web", "- **Surface:** terminal") + FILL)
        self.assertEqual(self.st(self.fe("fe-ux")[2], "FE1.wireframes"), "pass")  # no canvas: text mockup

    def test_ux_long_flow(self):
        self.p.write("docs/frontend/01-ux.md", UX.replace("- **Cancel:** back to empty form",
                     "- **Cancel:** " + " ".join(["w"] * 90)) + FILL)
        self.assertEqual(self.st(self.fe("fe-ux")[2], "FE1.flow-length"), "fail")

    def test_ui_defects(self):
        t = UI.replace("| Caution | #9A6700 | notice |\n", "").replace("| corner toast | inline notice | the eye is on the picker |\n", "")
        t = t.replace("- **States:** default, focus", "- **States:** default") + "\nUse #FF0000 for errors.\n"
        t = t.replace("?node-id=1-2", "")
        self.p.write("docs/frontend/02-ui.md", t + FILL)
        rep = self.fe("fe-ui")[2]
        for cid in ("FE2.plan", "FE2.self-check", "FE2.tokens", "FE2.components", "FE2.frames"):
            self.assertEqual(self.st(rep, cid), "fail", cid)

    def test_every_page_needs_a_frame(self):
        self.p.write("docs/frontend/01-ux.md", UX.replace("| PAGE-001 | Upload one file | REQ-001 | form — one decision |",
                     "| PAGE-001 | Upload one file | REQ-001 | form — one decision |\n| PAGE-002 | History | REQ-001 | list — scan |") + FILL)
        self.assertIn("PAGE-002: no frame", self.details(self.fe("fe-ui")[2], "FE2.frames"))

    def test_terminal_surface_uses_mockups(self):
        self.p.write("docs/frontend/01-ux.md", UX.replace("- **Surface:** web", "- **Surface:** terminal") + FILL)
        ui = UI.replace("https://www.figma.com/design/AbCdEfGhIjKlMnOpQrStUv/Upload?node-id=1-2", "mockup §6")
        self.p.write("docs/frontend/02-ui.md", ui.replace("- **Figma file:** https://www.figma.com/design/AbCdEfGhIjKlMnOpQrStUv/Upload\n", "") + FILL)
        self.assertEqual(self.st(self.fe("fe-ui")[2], "FE2.frames"), "pass")

    def test_queue_defects(self):
        t = QUEUE.replace("- **Priority:** P1\n", "").replace("- **Frame:** FRAME-001", "- **Frame:** FRAME-009")
        t = t.replace("- **States:** loading, empty, success, error", "- **States:** success")
        self.p.write("docs/frontend/03-queue.md", t + FILL)
        self.p.write("contracts/FRONTEND_BACKEND_CONTRACT.md", CONTRACT.replace("| verified |", "| maybe |"))
        self.p.write("docs/frontend/06-feedback.md", FEEDBACK.replace("accepted — link on its own line", "pending") + FILL)
        rep = self.fe("fe-queue")[2]
        rows = self.details(rep, "FE2.rows")
        for needle in ("priority must be", "frame names no FRAME-nnn"):
            self.assertIn(needle, rows)
        cov = self.details(rep, "FE2.coverage")
        self.assertIn("PAGE-001: states ['empty', 'error', 'loading']", cov)
        self.assertIn("FRAME-001: no row builds it", cov)
        for cid in ("FE2.contract", "FE2.feedback"):
            self.assertEqual(self.st(rep, cid), "fail", cid)

    def test_ux_writing_code_is_out_of_scope(self):
        self.fe_dispatch("fe-ux", step="1")
        self.p.write("web/app.css", "body{}")
        self.assertEqual(self.st(self.fe("fe-ux")[2], "ROLE.designer-scope"), "fail")

    def test_ui_writing_its_docs_is_fine(self):
        self.fe_dispatch("fe-ui", step="2")
        self.p.write("docs/frontend/02-ui.md", UI + FILL + "more\n")
        self.assertEqual(self.st(self.fe("fe-ui")[2], "ROLE.designer-scope"), "pass")

    def test_backend_fixtures_written_meanwhile_are_not_charged_to_ui(self):
        """be-analyst writes fixtures while fe-ui is the latest mark: not charged to fe-ui (ROLE.designer-scope)."""
        self.fe_dispatch("fe-ui", step="2")
        self.p.write("tests/fixtures/candidates/FX-001/input.json", "{}")
        self.p.write("docs/backend/03-detailed-design.md", "backend design in progress")
        self.assertEqual(self.st(self.fe("fe-ui")[2], "ROLE.designer-scope"), "pass")


class FigmaBudget(FrontBase):
    def test_calls_within_and_over_budget(self):
        self.set_state(figma={"budget": 10})
        self.fe_dispatch("fe-ui", step="2", figma=8)
        rep = self.fe("fe-ui")[2]
        self.assertEqual(self.st(rep, "FE.figma"), "pass")
        self.assertIn("8 of 10", next(c for c in rep["checks"] if c["id"] == "FE.figma")["message"])
        self.fe_dispatch("fe-ui", step="2", figma=5)
        self.assertEqual(self.st(self.fe("fe-ui")[2], "FE.figma"), "fail")
        self.fe_log("human", "--stop", "Budget", "--decision", "approved", "--by", "user", "--note", "raise to 20")
        self.assertEqual(self.st(self.fe("fe-ui")[2], "FE.figma"), "pass")

    def test_calls_without_a_budget(self):
        self.fe_dispatch("fe-ui", step="2", figma=3)
        self.assertEqual(self.st(self.fe("fe-ui")[2], "FE.figma"), "fail")


class Approval(FrontBase):
    def test_approve_needs_green_plan(self):
        self.p.write("docs/frontend/03-queue.md", QUEUE)
        self.assertEqual(self.fe("fe-approve", "--by", "user")[0], 2)

    def test_approve_needs_frame_exports(self):
        self.p.write("docs/frontend/03-queue.md", QUEUE + FILL)
        for g in ("fe-product", "fe-ux", "fe-ui", "fe-queue", "fe-plan"):
            self.fe(g)
        code, out, _ = self.fe("fe-approve", "--by", "user")
        self.assertEqual(code, 2)
        self.assertIn("FRAME-001", out)
        self.export_frames()
        self.assertEqual(self.fe("fe-approve", "--by", "user")[0], 0)
        approved = json.loads((self.p.fe / "gates" / "observables-approved.json").read_text())
        self.assertEqual((sorted(approved["rows"]), sorted(approved["frames"])), (["Q-001"], ["FRAME-001"]))

    def test_scaffold_build_before_approval(self):
        r = subprocess.run([PY, str(GATE), "baseline", "--team", "frontend", "--project", str(self.p.root)],
                           capture_output=True, text=True)
        assert r.returncode == 0, r.stdout
        self.p.write("docs/frontend/03-queue.md", "# Queue\n\n## Scaffold\n| File | What |\n|---|---|\n| `web/api.js` | maps 409 |\n" + FILL)
        self.fe_dispatch("fe-engineer", step="2")
        self.p.write("web/api.js", "export const dup = 409;\n")
        rep = self.fe("fe-build")[2]
        self.assertEqual(self.st(rep, "FE.observables"), "unavailable")
        self.assertEqual(self.st(rep, "ROLE.unplanned"), "pass")
        self.set_state(design_stops=1)  # nothing approved yet: no product code before the UI stop
        self.assertIn("web/api.js", self.details(self.fe("fe-build")[2], "FE.observables"))


class BuildVerifyAccept(FrontBase):
    def setUp(self):
        super().setUp()
        self.to_build()

    def build_notice(self):
        self.p.write("web/notice.html", '<p class="warn">Already uploaded</p>')

    def test_build_green(self):
        self.build_notice()
        code, out, _ = self.fe("fe-build")
        self.assertEqual(code, 0, out)

    def test_build_unplanned_file_and_test_edit(self):
        self.p.write("web/other.html", "<p>")
        self.p.write("tests/test_calc.py", self.p.read("tests/test_calc.py") + "\n# tweak\n")
        rep = self.fe("fe-build")[2]
        self.assertEqual(self.st(rep, "ROLE.unplanned"), "fail")
        self.assertEqual(self.st(rep, "ROLE.tests"), "fail")

    def test_observable_or_frame_changed_after_approval(self):
        self.p.write("docs/frontend/03-queue.md",
                     self.p.read("docs/frontend/03-queue.md").replace("Already uploaded", "Duplicate"))
        self.build_notice()
        self.assertEqual(self.st(self.fe("fe-build")[2], "FE.observables"), "fail")
        self.p.write("docs/frontend/03-queue.md", QUEUE + FILL)
        self.assertEqual(self.st(self.fe("fe-build")[2], "FE.observables"), "pass")
        self.p.write("docs/frontend/evidence/design/FRAME-001.png", "redrawn after approval")
        self.assertIn("FRAME-001", self.details(self.fe("fe-build")[2], "FE.observables"))

    def _verify_setup(self, verdict="done", manifest=True):
        self.build_notice()
        assert self.fe("fe-build")[0] == 0
        self.p.write("docs/frontend/03-queue.md",
                     self.p.read("docs/frontend/03-queue.md").replace("**Status:** queued", "**Status:** done"))
        self.p.write("docs/frontend/capture-plan.json", json.dumps(TERMINAL_PLAN))
        if manifest:
            assert self.capture()[0] == 0
        self.fe_dispatch("fe-tester", step="4")
        self.p.write("docs/frontend/04-verification.md",
                     VERIFY.replace("| Q-001 | done |", f"| Q-001 | {verdict} |") + FILL)

    def test_verify_review_and_accept(self):
        self._verify_setup()
        code, out, _ = self.fe("fe-verify")
        self.assertEqual(code, 0, out)
        code, out, _ = self.review_ok()
        self.assertEqual(code, 0, out)
        code, out, rep = self.fe("fe-accept")
        self.assertEqual(code, 0, out)
        self.assertIn("| REQ-001 | FLOW-001 | PAGE-001 | Q-001 done | yes |",
                      (self.p.fe / "gates" / "traceability.md").read_text())

    def test_accept_needs_review(self):
        self._verify_setup()
        self.fe("fe-verify")
        self.assertIn("fe-review: never run", self.details(self.fe("fe-accept")[2], "FEA.gates"))

    def test_open_major_blocks_acceptance(self):
        self._verify_setup()
        self.fe("fe-verify")
        self.review_ok(REVIEW.replace("| FND-001 | minor |", "| FND-001 | major |").replace("deferred", "open"))
        self.assertEqual(self.st(self.fe("fe-accept")[2], "FEA.findings"), "fail")

    def test_review_defects(self):
        self._verify_setup()
        self.set_state(risk="high")
        bad = REVIEW.replace("web/notice.html:1", "web/nowhere.html:3").replace(
            "- **Scenario:** the admin sees a slightly misaligned icon\n", "")
        subprocess.run([PY, str(GATE), "mark", "--role", "fe-reviewer", "--team", "frontend",
                        "--project", str(self.p.root)], capture_output=True, text=True)
        self.p.write("web/notice.html", "<p>reviewer fix</p>")
        self.p.write("docs/frontend/05-review.md", bad + FILL)
        rep = self.fe("fe-review")[2]
        for cid in ("FE4.tree-unchanged", "FE4.panel", "FE4.findings"):
            self.assertEqual(self.st(rep, cid), "fail", cid)
        f = self.details(rep, "FE4.findings")
        self.assertIn("does not exist", f)
        self.assertIn("no failure scenario", f)

    def test_tester_writing_tests_beside_the_panel(self):
        self._verify_setup()
        subprocess.run([PY, str(GATE), "mark", "--role", "fe-reviewer", "--team", "frontend",
                        "--project", str(self.p.root)], capture_output=True, text=True)
        self.p.write("tests/test_rows.py", "def test_notice():\n    \"\"\"Q-001\"\"\"\n    assert True\n")
        self.p.write("docs/frontend/05-review.md", REVIEW + FILL)
        self.assertEqual(self.st(self.fe("fe-review")[2], "FE4.tree-unchanged"), "pass")

    def test_review_where_can_be_evidence(self):
        self._verify_setup()
        code, out, rep = self.review_ok(REVIEW.replace("web/notice.html:1", "evidence/verify-1/Q-001-dup@80x24.stdout"))
        self.assertEqual(self.st(rep, "FE4.findings"), "pass", out)

    def test_needs_user_feedback_without_decision(self):
        self._verify_setup()
        self.fe("fe-verify")
        self.review_ok()
        self.p.write("docs/frontend/06-feedback.md", FEEDBACK.replace("| no | — |", "| yes | — |") + FILL)
        self.assertEqual(self.st(self.fe("fe-accept")[2], "FEA.feedback"), "fail")

    def test_not_observable_is_not_done(self):
        self._verify_setup("not observable")
        self.assertEqual(self.fe("fe-verify")[0], 0)
        self.assertEqual(self.st(self.fe("fe-accept")[2], "FEA.rows"), "fail")

    def test_bad_verdict_and_missing_manifest(self):
        self._verify_setup("looks fine", manifest=False)
        rep = self.fe("fe-verify")[2]
        self.assertEqual(self.st(rep, "FE4.verdicts"), "fail")
        self.assertEqual(self.st(rep, "FE4.evidence"), "fail")

    def test_row_tagged_test_must_pass(self):
        self._verify_setup()
        self.p.write("tests/test_rows.py", "def test_notice():\n    \"\"\"Q-001\"\"\"\n    assert 1 == 2\n")
        rep = self.fe("fe-verify")[2]
        self.assertEqual(self.st(rep, "FE4.row-tests"), "fail")
        # different length: Python's bytecode cache keys on mtime + size, and both writes share a second
        self.p.write("tests/test_rows.py", "def test_notice():\n    \"\"\"Q-001\"\"\"\n    assert 1 == 1  # fixed\n")
        self.assertEqual(self.st(self.fe("fe-verify")[2], "FE4.row-tests"), "pass")

    def test_new_npm_dependency_needs_the_queue(self):
        self.p.write("package.json", '{"dependencies": {"left-pad": "1.3.0"}}')
        q = self.p.read("docs/frontend/03-queue.md").replace("`web/notice.html`", "`web/notice.html`, `package.json`")
        self.p.write("docs/frontend/03-queue.md", q)
        self.assertEqual(self.st(self.fe("fe-build")[2], "FE3.dependencies"), "fail")
        self.p.write("docs/frontend/03-queue.md", q.replace("## Scaffold", "## Dependencies\n| left-pad | 1.3.0 | padding |\n\n## Scaffold"))
        self.assertEqual(self.st(self.fe("fe-build")[2], "FE3.dependencies"), "pass")

    def test_matrix_gap_caught(self):
        self._verify_setup()
        self.fe("fe-verify")
        self.review_ok()
        self.p.write("docs/frontend/00-requirements.md", REQS + """
### REQ-002 — Bulk upload [interface]
- **Cut:** above
- **Behaviour:** many files at once
- **Accept:** Given ten files, When uploaded, Then each shows its result
- **Source:** "bulk"
- **Fixtures:** n/a — frontend run
""" + FILL)
        self.assertIn("REQ-002", self.details(self.fe("fe-accept")[2], "FEA.matrix"))

    def test_tester_edits_production(self):
        self._verify_setup()
        self.p.write("web/notice.html", "<p>tester fix</p>")
        self.assertEqual(self.st(self.fe("fe-verify")[2], "ROLE.tester-scope"), "fail")


class Trail(FrontBase):
    def _accept_ready(self):
        self.p.write("docs/frontend/03-queue.md", QUEUE + FILL)
        for g in ("fe-product", "fe-ux", "fe-ui", "fe-queue", "fe-plan"):
            self.fe(g)

    def test_build_before_ui_stop(self):
        self._accept_ready()
        self.fe_log("human", "--stop", "UX", "--decision", "approved", "--by", "user", "--note", "ok")
        self.fe_dispatch("fe-engineer", step="3")
        self.fe_log("human", "--stop", "UI", "--decision", "approved", "--by", "user", "--note", "ok")
        self.assertIn("before the UI was approved", self.details(self.fe("fe-accept")[2], "LOG.trail"))

    def test_ui_before_ux_stop_in_two_stop_runs(self):
        self._accept_ready()
        self.fe_dispatch("fe-ui", step="2")
        self.fe_log("human", "--stop", "UX", "--decision", "approved", "--by", "user", "--note", "ok")
        self.fe_log("human", "--stop", "UI", "--decision", "approved", "--by", "user", "--note", "ok")
        self.assertIn("fe-ui dispatched", self.details(self.fe("fe-accept")[2], "LOG.trail"))
        self.set_state(design_stops=1)
        self.assertNotIn("fe-ui dispatched", self.details(self.fe("fe-accept")[2], "LOG.trail"))

    def test_scaffold_may_precede_ui_stop(self):
        self._accept_ready()
        self.fe_log("human", "--stop", "UX", "--decision", "approved", "--by", "user", "--note", "ok")
        self.fe_dispatch("fe-engineer", step="2")
        self.fe_log("human", "--stop", "UI", "--decision", "approved", "--by", "user", "--note", "ok")
        self.assertEqual(self.st(self.fe("fe-accept")[2], "LOG.trail"), "pass")


UX_INTAKE = """# UX — Duplicate upload message (intake of the confirmed design)

- **Named user:** office admin uploading contracts daily
- **Surface:** web

## 1. Pages
| Page | Job | Serves | Form — why |
|---|---|---|---|
| PAGE-001 | Upload one file | REQ-001 | form — as drawn in the confirmed design |

## 4. Page details
### PAGE-001 — Upload
| State | User sees | Words | Can do next |
|---|---|---|---|
| loading | not drawn: bar under the picker | Uploading | Cancel |
| empty | as drawn | Choose a file | choose |
| success | as drawn | Uploaded | open |
| error | as drawn | Already uploaded | open original |
| permission | n/a — every admin can upload | | |

## 5. Open in the design
- Narrow size not drawn: stack picker above the button (recommended).
"""

UI_INTAKE = """# UI — Duplicate upload message (intake of the confirmed design)

- **Figma file:** https://www.figma.com/design/AbCdEfGhIjKlMnOpQrStUv/Upload

## 3. Tokens
| Token | Layer | Value | Use |
|---|---|---|---|
| color.notice | semantic | #9A6700 | notice |

## 4. Components
### CMP-001 — Notice
- **States:** default, focus

## 5. Frames
| Frame | Page | State | Size | Figma |
|---|---|---|---|---|
| FRAME-001 | PAGE-001 | error | 1440 | https://www.figma.com/design/AbCdEfGhIjKlMnOpQrStUv/Upload?node-id=1-2 |
"""


class ExternalDesign(FrontBase):
    """8.0: a design the user confirmed outside the harness is taken in, not rewritten."""
    def setUp(self):
        super().setUp()
        self.p.write("docs/frontend/01-ux.md", UX_INTAKE + FILL)
        self.p.write("docs/frontend/02-ui.md", UI_INTAKE + FILL)

    def test_intake_forms_pass_only_for_an_external_design(self):
        rep = self.fe("fe-ux")[2]
        self.assertEqual((self.st(rep, "FE1.flows"), self.st(rep, "FE1.wireframes")), ("fail", "fail"))
        rep = self.fe("fe-ui")[2]
        self.assertEqual((self.st(rep, "FE2.plan"), self.st(rep, "FE2.self-check")), ("fail", "fail"))
        self.set_state(design="external", design_stops=0)
        code, out, rep = self.fe("fe-ux")
        self.assertEqual(code, 0, out)
        self.assertEqual(self.st(rep, "FE1.flows"), "unavailable")
        code, out, _ = self.fe("fe-ui")
        self.assertEqual(code, 0, out)

    def test_intake_still_needs_every_state_and_frame(self):
        self.set_state(design="external", design_stops=0)
        self.p.write("docs/frontend/01-ux.md", UX_INTAKE.replace("| permission | n/a — every admin can upload | | |\n", "") + FILL)
        self.assertEqual(self.st(self.fe("fe-ux")[2], "FE1.states"), "fail")
        self.p.write("docs/frontend/02-ui.md", UI_INTAKE.split("## 5. Frames")[0] + FILL)
        self.assertEqual(self.st(self.fe("fe-ui")[2], "FE2.frames"), "fail")

    def _baseline(self):
        r = subprocess.run([PY, str(GATE), "baseline", "--team", "frontend", "--project", str(self.p.root)],
                           capture_output=True, text=True)
        assert r.returncode == 0, r.stdout + r.stderr

    def test_prototype_code_allowed_once_the_design_is_confirmed(self):
        self.set_state(design="external", design_stops=0)
        self._baseline()
        self.p.write("docs/frontend/03-queue.md", "# Queue\n\n## Scaffold\n| File | What |\n|---|---|\n| `web/app.js` | prototype |\n" + FILL)
        self.fe_dispatch("fe-engineer", step="2b")
        self.p.write("web/app.js", "export const fake = [];\n")
        self.assertEqual(self.st(self.fe("fe-build")[2], "FE.observables"), "fail")
        self.fe_log("human", "--stop", "UI", "--decision", "approved", "--by", "user", "--note", "external, confirmed")
        self.assertEqual(self.st(self.fe("fe-build")[2], "FE.observables"), "unavailable")


class PrototypeTrail(FrontBase):
    """8.0: design approved → prototype (2b) → Prototype approved → build (3)."""
    def setUp(self):
        super().setUp()
        self.set_state(harness_version="8.0.0", design_stops=1)
        self.p.write("docs/frontend/03-queue.md", QUEUE + FILL)
        for g in ("fe-product", "fe-ux", "fe-ui", "fe-queue", "fe-plan"):
            self.fe(g)

    def trail(self):
        return self.details(self.fe("fe-accept")[2], "LOG.trail")

    def ui(self):
        self.fe_log("human", "--stop", "UI", "--decision", "approved", "--by", "user", "--note", "ok")

    def proto_ok(self):
        self.fe_log("human", "--stop", "Prototype", "--decision", "approved", "--by", "user", "--note", "ok")

    def test_in_order(self):
        self.ui()
        self.fe_dispatch("fe-engineer", step="2b")
        self.proto_ok()
        self.fe_dispatch("fe-engineer", step="3")
        self.assertEqual(self.st(self.fe("fe-accept")[2], "LOG.trail"), "pass")

    def test_no_prototype_stop(self):
        self.ui()
        self.fe_dispatch("fe-engineer", step="3")
        self.assertIn("no approved Prototype stop", self.trail())

    def test_build_before_prototype_stop(self):
        self.ui()
        self.fe_dispatch("fe-engineer", step="3")
        self.proto_ok()
        self.assertIn("before the Prototype was approved", self.trail())

    def test_prototype_before_design_approved(self):
        self.fe_dispatch("fe-engineer", step="2b")
        self.ui()
        self.proto_ok()
        self.assertIn("prototype dispatched", self.trail())

    def test_runs_before_8_0_are_not_charged(self):
        self.set_state(harness_version="7.2.6")
        self.ui()
        self.fe_dispatch("fe-engineer", step="3")
        self.assertNotIn("Prototype", self.trail())


class MarkOrder(FrontBase):
    def test_marks_before_their_dispatches_are_fine_until_a_gate(self):
        g = lambda *a: subprocess.run([PY, str(GATE), *a, "--team", "frontend", "--project", str(self.p.root)],
                                      capture_output=True, text=True)
        g("mark", "--role", "fe-tester")
        g("mark", "--role", "fe-engineer")
        for role in ("fe-tester", "fe-engineer"):
            self.fe_log("dispatch", "--agent", role, "--model", "opus", "--step", "3", "--note", "w")
            self.fe_log("return", "--agent", role, "--step", "3", "--status", "ok", "--note", "d")
        self.assertNotIn("not followed by its dispatch", self.details(self.fe("fe-accept")[2], "LOG.trail"))
        g("mark", "--role", "fe-engineer")
        self.fe("fe-ux")
        self.fe_log("dispatch", "--agent", "fe-engineer", "--model", "opus", "--step", "3", "--note", "w")
        self.fe_log("return", "--agent", "fe-engineer", "--step", "3", "--status", "ok", "--note", "d")
        self.assertIn("not followed by its dispatch", self.details(self.fe("fe-accept")[2], "LOG.trail"))


class CrossTeamSerial(FrontBase):
    def be_log(self, *args):
        return subprocess.run([PY, str(GATE), "log", *args, "--project", str(self.p.root)],
                              capture_output=True, text=True).returncode

    def mark(self):
        return subprocess.run([PY, str(GATE), "mark", "--role", "fe-engineer", "--team", "frontend",
                               "--project", str(self.p.root)], capture_output=True, text=True)

    def test_mark_and_gates_wait_for_the_other_teams_writer(self):
        self.p.write("docs/backend/state.json", json.dumps({"status": "in_progress"}))
        self.be_log("dispatch", "--agent", "be-developer", "--model", "sonnet", "--step", "4", "--note", "build")
        r = self.mark()
        self.assertEqual(r.returncode, 4, r.stdout + r.stderr)
        self.assertIn("be-developer", r.stderr)
        self.assertEqual(self.fe("fe-ux")[0], 4)
        self.assertEqual(self.fe_log("dispatch", "--agent", "fe-ux", "--model", "opus", "--step", "1",
                                     "--note", "logging is never blocked"), 0)
        self.be_log("return", "--agent", "be-developer", "--step", "4", "--status", "ok", "--note", "done")
        self.assertEqual(self.mark().returncode, 0)

    def test_reviewers_and_settled_runs_do_not_block(self):
        self.p.write("docs/backend/state.json", json.dumps({"status": "in_progress"}))
        self.be_log("dispatch", "--agent", "be-review-security", "--model", "opus", "--step", "6", "--note", "r")
        self.assertEqual(self.mark().returncode, 0)
        self.be_log("dispatch", "--agent", "be-developer", "--model", "sonnet", "--step", "4", "--note", "lost")
        self.p.write("docs/backend/state.json", json.dumps({"status": "accepted"}))
        self.assertEqual(self.mark().returncode, 0)


class FigmaLeft(FrontBase):
    def test_dispatch_of_a_figma_role_needs_the_calls_left(self):
        self.set_state(figma={"budget": 40})
        self.assertEqual(self.fe_log("dispatch", "--agent", "fe-ui", "--model", "opus", "--step", "2", "--note", "w"), 2)
        self.assertEqual(self.fe_log("dispatch", "--agent", "fe-ui", "--model", "opus", "--step", "2", "--note", "w",
                                     "--figma-left", "40"), 0)
        self.assertEqual(self.fe_log("dispatch", "--agent", "fe-ux", "--model", "opus", "--step", "1", "--note", "w"), 2)
        self.assertEqual(self.fe_log("dispatch", "--agent", "fe-tester", "--model", "opus", "--step", "4", "--note", "w"), 0)
        self.set_state(figma={"budget": None})
        self.assertEqual(self.fe_log("dispatch", "--agent", "fe-engineer", "--model", "opus", "--step", "2", "--note", "w"), 0)


class RunDir(FrontBase):
    def test_project_artifacts_run_dir(self):
        # .claude/frontend.json overrides artifacts.run_dir, as frontend/config.json is shaped
        self.p.write(".claude/frontend.json", json.dumps({"artifacts": {"run_dir": "docs/ui2"}}))
        self.fe_log("decision", "--agent", "fe-ux", "--note", "x")
        self.assertTrue((self.p.root / "docs/ui2/run-log.jsonl").exists())


class ChromeLookup(unittest.TestCase):
    def test_linux_chrome_on_path(self):
        # install.sh accepts google-chrome on PATH; capture must find it too
        import importlib
        from unittest import mock
        sys.path.insert(0, str(GATE.parent))
        capture = importlib.import_module("gatelib.capture")
        with mock.patch.dict(os.environ, {}, clear=False) as env, \
                mock.patch.object(capture, "CHROME", "/nonexistent/Google Chrome"), \
                mock.patch.object(capture.shutil, "which",
                                  lambda n: "/usr/bin/google-chrome" if n == "google-chrome" else None):
            env.pop("CHROME_PATH", None)
            self.assertEqual(capture.find_chrome(), "/usr/bin/google-chrome")
            env["CHROME_PATH"] = "/opt/chrome"
            self.assertEqual(capture.find_chrome(), "/opt/chrome")


class Capture(FrontBase):
    def setUp(self):
        super().setUp()
        self.to_build()
        self.p.write("web/notice.html", '<p class="warn">Already uploaded</p>')
        assert self.fe("fe-build")[0] == 0

    def test_plan_gate(self):
        self.assertEqual(self.st(self.fe("fe-capture-plan")[2], "FE4.capture-plan"), "fail")  # no plan
        self.p.write("docs/frontend/capture-plan.json", json.dumps({"surface": "web", "captures": [
            {"id": "c1", "row": "Q-009", "state": "dup", "url": "/"}]}))
        details = " ".join(next(c for c in self.fe("fe-capture-plan")[2]["checks"]
                                if c["id"] == "FE4.capture-plan")["details"])
        for needle in ("base_url", "sizes", "Q-001: no capture planned"):
            self.assertIn(needle, details)
        # bare widths from config `viewports` are not sizes (PLAYBOOK §3H)
        self.p.write("docs/frontend/capture-plan.json", json.dumps({"surface": "web", "base_url": "http://x",
                     "sizes": [1440, 375], "captures": [{"id": "c1", "row": "Q-001", "state": "dup", "url": "/"}]}))
        self.assertIn("must be", " ".join(next(c for c in self.fe("fe-capture-plan")[2]["checks"]
                                               if c["id"] == "FE4.capture-plan")["details"]))
        self.p.write("docs/frontend/capture-plan.json", json.dumps(TERMINAL_PLAN))
        self.assertEqual(self.fe("fe-capture-plan")[0], 0)

    def test_terminal_capture_writes_evidence_and_logs(self):
        self.p.write("docs/frontend/capture-plan.json", json.dumps(TERMINAL_PLAN))
        code, out = self.capture()
        self.assertEqual(code, 0, out)
        d = self.p.fe / "evidence" / "verify-1"
        self.assertIn("Already uploaded", (d / "Q-001-dup@80x24.stdout").read_text())
        m = json.loads((d / "manifest.json").read_text())
        self.assertEqual((m["surface"], len(m["entries"])), ("terminal", 1))
        events = [json.loads(l) for l in (self.p.fe / "run-log.jsonl").read_text().splitlines()]
        self.assertEqual(events[-1]["event"], "capture")
        self.assertEqual(self.capture()[0], 2)  # never overwrite a round

    def test_stale_evidence(self):
        self.p.write("docs/frontend/capture-plan.json", json.dumps(TERMINAL_PLAN))
        self.capture()
        self.fe_dispatch("fe-tester")
        self.p.write("docs/frontend/04-verification.md", VERIFY + "\n".join(["filler"] * 8))
        self.assertEqual(self.st(self.fe("fe-verify")[2], "FE4.capture"), "pass")
        self.p.write("web/notice.html", '<p class="warn">Changed after capture</p>')
        rep = self.fe("fe-verify")[2]
        self.assertIn("source changed after capture",
                      " ".join(next(c for c in rep["checks"] if c["id"] == "FE4.capture")["details"]))

    def test_capture_before_build_is_stale(self):
        self.p.write("docs/frontend/capture-plan.json", json.dumps(TERMINAL_PLAN))
        self.capture()
        import time
        time.sleep(1.1)
        assert self.fe("fe-build")[0] == 0
        self.fe_dispatch("fe-tester")
        self.p.write("docs/frontend/04-verification.md", VERIFY + "\n".join(["filler"] * 8))
        details = " ".join(next(c for c in self.fe("fe-verify")[2]["checks"] if c["id"] == "FE4.capture")["details"])
        self.assertIn("before the last fe-build", details)

    def test_terminal_capture_with_no_output_fails(self):
        self.p.write("docs/frontend/capture-plan.json", json.dumps({"surface": "terminal", "captures": [
            {"id": "q", "row": "Q-001", "state": "dup", "command": "true"}]}))
        self.capture()
        self.fe_dispatch("fe-tester")
        self.p.write("docs/frontend/04-verification.md", VERIFY + "\n".join(["filler"] * 8))
        details = " ".join(next(c for c in self.fe("fe-verify")[2]["checks"] if c["id"] == "FE4.capture")["details"])
        self.assertIn("no output on stdout or stderr", details)

    def test_manual_capture_missing_file(self):
        self.p.write("docs/frontend/capture-plan.json", json.dumps({"surface": "manual", "captures": [
            {"id": "m1", "row": "Q-001", "state": "dup", "instrument": "Xcode view debugger",
             "files": ["captures/tree.txt"]}]}))
        code, _ = self.capture()
        self.assertEqual(code, 1)
        self.p.write("captures/tree.txt", "UILabel 'Already uploaded'")
        code, _ = self.capture("2")
        self.assertEqual(code, 0)

    def test_web_capture_with_real_chrome(self):
        gates = GATE.parent
        chrome = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
        if not (gates / "node_modules" / "playwright-core").exists() or not pathlib.Path(chrome).exists():
            self.skipTest("playwright-core or Chrome not installed")
        import socket
        site = self.p.root / "site"
        site.mkdir()
        (site / "index.html").write_text(
            '<html><body><button id="go" onclick="document.getElementById(\'n\').hidden=false">Upload</button>'
            '<p id="n" class="warn" style="color: rgb(180, 83, 9)" hidden>Already uploaded</p></body></html>')
        s = socket.socket(); s.bind(("127.0.0.1", 0)); port = s.getsockname()[1]; s.close()
        srv = subprocess.Popen([PY, "-m", "http.server", str(port), "--bind", "127.0.0.1"], cwd=site,
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            import time
            time.sleep(0.8)
            self.p.write("docs/frontend/capture-plan.json", json.dumps({
                "surface": "web", "base_url": f"http://127.0.0.1:{port}",
                "sizes": [{"name": "desktop", "width": 1280, "height": 800}, {"name": "phone", "width": 390, "height": 844}],
                "captures": [{"id": "Q-001-dup", "row": "Q-001", "state": "duplicate", "url": "/index.html",
                              "steps": [{"action": "click", "selector": "#go"}, {"action": "waitFor", "selector": "#n"}],
                              "styles": {"selector": ".warn", "properties": ["color"]}}]}))
            code, out = self.capture()
            self.assertEqual(code, 0, out)
            d = self.p.fe / "evidence" / "verify-1"
            for size in ("desktop", "phone"):
                self.assertIn("Already uploaded", (d / f"Q-001-dup@{size}.dom.html").read_text())
                self.assertIn("rgb(180, 83, 9)", (d / f"Q-001-dup@{size}.styles.json").read_text())
                self.assertIn("Already uploaded", (d / f"Q-001-dup@{size}.aria.yml").read_text())
                self.assertGreater((d / f"Q-001-dup@{size}.png").stat().st_size, 1000)
        finally:
            srv.terminate()


class RowIds(FrontBase):
    """Tests carry Q ids project-wide, so a later round continues the numbering."""
    def test_earlier_round_id_is_refused_with_the_next_free_one(self):
        self.p.write("docs/frontend/03-queue.md", QUEUE + FILL)
        self.p.write("docs/frontend/old-round/03-queue.md", "### Q-001 — x\n\n### Q-007 — y\n")
        for g in ("fe-product", "fe-ux", "fe-ui"):
            self.fe(g)
        rep = self.fe("fe-queue")[2]
        self.assertEqual(self.st(rep, "FE2.row-ids"), "fail")
        self.assertIn("Q-001: already used in docs/frontend/old-round", self.details(rep, "FE2.row-ids"))
        self.assertIn("continue from Q-008", next(c for c in rep["checks"] if c["id"] == "FE2.row-ids")["message"])
        self.p.write("docs/frontend/03-queue.md", (QUEUE + FILL).replace("Q-001", "Q-008"))
        self.assertEqual(self.st(self.fe("fe-queue")[2], "FE2.row-ids"), "pass")

    def test_pre_7_queue_name_counts(self):
        self.p.write("docs/frontend/03-queue.md", QUEUE + FILL)
        self.p.write("docs/frontend/v6/05-queue.md", "### Q-001 — x\n")
        for g in ("fe-product", "fe-ux", "fe-ui"):
            self.fe(g)
        self.assertEqual(self.st(self.fe("fe-queue")[2], "FE2.row-ids"), "fail")


class Registry(FrontBase):
    """Accepted rows become OBS-### entries that later rounds must keep passing."""
    ROW_TEST = 'def test_notice():\n    """Q-001"""\n    assert open("web/notice.html").read().count("Already uploaded") == 1\n'

    def setUp(self):
        super().setUp()
        self.to_build()
        self.p.write("web/notice.html", '<p class="warn">Already uploaded</p>')
        assert self.fe("fe-build")[0] == 0
        self.p.write("docs/frontend/03-queue.md",
                     self.p.read("docs/frontend/03-queue.md").replace("**Status:** queued", "**Status:** done"))
        self.p.write("docs/frontend/capture-plan.json", json.dumps(TERMINAL_PLAN))
        assert self.capture()[0] == 0
        self.fe_dispatch("fe-tester")
        self.p.write("tests/test_rows.py", self.ROW_TEST)
        self.p.write("docs/frontend/04-verification.md", VERIFY + "\n".join(["filler"] * 8))

    def accept(self):
        code, out, _ = self.fe("fe-verify")
        assert code == 0, out
        code, out, _ = self.review_ok()
        assert code == 0, out
        code, out, _ = self.fe("fe-accept")
        assert code == 0, out

    def promote(self, *extra):
        r = subprocess.run([PY, str(GATE), "fe-promote", "--by", "user", *extra, "--project", str(self.p.root)],
                           capture_output=True, text=True)
        return r.returncode, r.stdout + r.stderr

    def reg(self):
        return json.loads(self.p.read("docs/frontend/observables.json"))

    def test_promote_needs_acceptance(self):
        self.assertEqual(self.promote()[0], 2)

    def test_promote_registers_test_guarded_entry(self):
        self.accept()
        code, out = self.promote()
        self.assertEqual(code, 0, out)
        e = self.reg()["entries"]["OBS-001"]
        self.assertEqual((e["kind"], e["tests"], e["pages"]), ("test", [{"file": "tests/test_rows.py", "name": "test_notice"}],
                                                              ["PAGE-001"]))

    def test_regression_caught_in_a_later_build(self):
        self.accept()
        self.promote()
        self.p.write("web/notice.html", '<p class="warn">Duplicate!</p>')
        rep = self.fe("fe-build")[2]
        self.assertEqual(self.st(rep, "FE.regression"), "fail")
        self.p.write("web/notice.html", '<p class="warn">Already uploaded</p>')
        (self.p.root / "tests/test_rows.py").unlink()
        details = " ".join(next(c for c in self.fe("fe-build")[2]["checks"] if c["id"] == "FE.regression")["details"])
        self.assertIn("tests/test_rows.py missing", details)

    def test_tampering_with_the_registry(self):
        self.accept()
        self.promote()
        reg = self.reg()
        reg["entries"]["OBS-001"]["observable"] = "anything"
        self.p.write("docs/frontend/observables.json", json.dumps(reg))
        details = " ".join(next(c for c in self.fe("fe-build")[2]["checks"] if c["id"] == "FE.regression")["details"])
        self.assertIn("edited outside", details)

    def test_row_without_guard_is_refused_unless_excluded(self):
        (self.p.root / "tests/test_rows.py").unlink()
        self.p.write("docs/frontend/capture-plan.json", json.dumps({"surface": "terminal", "captures": []}))
        self.accept()
        code, out = self.promote()
        self.assertEqual(code, 2)
        self.assertIn("no passing test tagged Q-001", out)
        self.assertEqual(self.promote("--exclude", "Q-001")[0], 0)

    def test_capture_guarded_entry_must_be_recaptured_and_judged(self):
        (self.p.root / "tests/test_rows.py").unlink()
        self.accept()
        self.assertEqual(self.promote()[0], 0)
        self.assertEqual(self.reg()["entries"]["OBS-001"]["kind"], "capture")
        details = " ".join(next(c for c in self.fe("fe-capture-plan")[2]["checks"]
                                if c["id"] == "FE4.capture-plan")["details"])
        self.assertIn("OBS-001: no capture planned", details)
        rep = self.fe("fe-verify")[2]
        self.assertEqual(self.st(rep, "FE.regression-captures"), "fail")
        self.p.write("docs/frontend/04-verification.md", self.p.read("docs/frontend/04-verification.md").replace(
            "| Q-001 | done |", "| OBS-001 | done | `Q-001-dup@80x24.stdout` · recheck | holds |\n| Q-001 | done |"))
        self.assertEqual(self.st(self.fe("fe-verify")[2], "FE.regression-captures"), "pass")

    # A test whose name the parser cannot read (as in Go, Rust, Java), whose JUnit case carries the
    # row id with an underscore after it, as Go subtest names do.
    UNNAMED_ROW_TEST = ('import pytest\nROW = "Q-001"\n\n\n'
                        '@pytest.mark.parametrize("page", ["web/notice.html"], ids=[ROW + "_notice"])\n'
                        'def test_notice(page):\n    assert open(page).read().count("Already uploaded") == 1\n')

    def test_unreadable_test_name_is_guarded_by_row_id(self):
        self.p.write("tests/test_rows.py", self.UNNAMED_ROW_TEST)
        self.accept()
        code, out = self.promote()
        self.assertEqual(code, 0, out)
        self.assertEqual(self.reg()["entries"]["OBS-001"]["tests"], [{"file": "tests/test_rows.py", "tag": "Q-001"}])
        self.assertEqual(self.st(self.fe("fe-build")[2], "FE.regression"), "pass")
        self.p.write("web/notice.html", '<p class="warn">Duplicate!</p>')
        self.assertEqual(self.st(self.fe("fe-build")[2], "FE.regression"), "fail")

    def test_older_entry_with_empty_tests_is_guarded_by_its_source_row(self):
        self.p.write("tests/test_rows.py", self.UNNAMED_ROW_TEST)
        self.accept()
        self.promote()
        reg = self.reg()
        old = {k: v for k, v in reg["entries"]["OBS-001"].items() if k != "hash"}
        old.update({"id": "OBS-002", "tests": [], "source": "docs/frontend#Q-001"})
        old["hash"] = hashlib.sha256(json.dumps(old, sort_keys=True).encode()).hexdigest()
        reg["entries"]["OBS-002"] = old
        self.p.write("docs/frontend/observables.json", json.dumps(reg))
        rep = self.fe("fe-build")[2]
        self.assertEqual(self.st(rep, "FE.regression"), "pass")
        self.assertIn("1 older entries guarded by their row id",
                      next(c for c in rep["checks"] if c["id"] == "FE.regression")["message"])
        self.p.write("web/notice.html", '<p class="warn">Duplicate!</p>')
        self.assertIn("OBS-002", self.details(self.fe("fe-build")[2], "FE.regression"))

    def test_plan_lists_and_retire_removes_conflicts(self):
        self.accept()
        self.promote()
        assert self.fe("fe-plan")[0] == 0
        sheet = (self.p.fe / "gates" / "plan-review.md").read_text()
        self.assertIn("| OBS-001 |", sheet)
        self.assertEqual(self.fe("fe-approve", "--by", "user", "--retire", "OBS-001")[0], 0)
        self.assertTrue(self.reg()["entries"]["OBS-001"]["retired"])
        self.p.write("web/notice.html", '<p class="warn">Redesigned</p>')
        self.assertEqual(self.st(self.fe("fe-build")[2], "FE.regression"), "pass")


class FrontendExamples(FrontBase):
    EXAMPLES = GATE.parent.parent / "frontend" / "templates" / "examples"

    def test_examples_pass_design_gates(self):
        if not self.EXAMPLES.is_dir():
            self.skipTest(f"{self.EXAMPLES} not installed next to the gates")
        self.set_state(design_stops=1)  # the example is a one-stop run: a text wireframe
        for n in ("00-requirements", "01-ux", "02-ui", "03-queue", "06-feedback"):
            self.p.write(f"docs/frontend/{n}.md", (self.EXAMPLES / f"{n}.example.md").read_text())
        for g in ("fe-product", "fe-ux", "fe-ui", "fe-queue"):
            code, out, _ = self.fe(g)
            self.assertEqual(code, 0, f"{g}: {out}")


if __name__ == "__main__":
    res = unittest.main(exit=False, verbosity=1).result
    print(f"{res.testsRun} cases, {len(res.failures) + len(res.errors)} failures")
    sys.exit(0 if res.wasSuccessful() else 1)
