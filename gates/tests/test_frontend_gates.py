#!/usr/bin/env python3
"""Regression matrix for the frontend gates (fe-*): red on each defect, green on innocent work.
Run: python3 tests/test_frontend_gates.py"""
import json
import pathlib
import subprocess
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from test_gates import GATE, PY, Base, sh  # noqa: E402

BRIEF = """# Brief — Duplicate upload message

## 0. Understanding
- **Asked:** "tell them it is a duplicate"
- **Means:** a duplicate upload shows why and links to the original
- **Ambiguities:** none

## 1. User and surface
- **Named user:** office admin uploading contracts daily
- **Surface:** browser

## 2. Tasks
| Task | What the user does | Success looks like | Frequency | Source |
|---|---|---|---|---|
| T-001 | Uploads an existing file | opens the original in one click | weekly | "tell them it is a duplicate" |

## 3. Scope
- **Cut line (above):** T-001
- **Non-goals:** merging duplicates
"""

STRUCTURE = """# Structure

## 1. Pages
| Page | Job | Serves | Form | Why |
|---|---|---|---|---|
| PAGE-001 | Upload one file | T-001 | form | one decision |

## 3. Flows
### FLOW-001 — Upload a duplicate
- **Serves:** T-001
- **Success:** 1. Choose 2. Upload 3. See notice
- **Failure:** network error, Retry
- **Cancel:** back to empty form
- **Recovery:** Retry keeps the file
- **Boundary:** over 20 MB rejected first
"""

SPEC = """# Specification

## 1. Tokens
| Semantic token | Primitive | Value | Use |
|---|---|---|---|
| `color-status-warning` | `amber-700` | #B45309 | notice |

## 2. Components
### CMP-001 — Result notice
- **States:** default · focus · empty
- **Sizes and limits:** 60 chars then truncate

## 3. Pages
### PAGE-001 — Upload
- **Goal:** upload one file · **Serves:** T-001

| State | What renders | Copy |
|---|---|---|
| loading | bar | Uploading |
| empty | picker | — |
| success | notice | Uploaded |
| error | notice | Failed |
| permission-denied | notice | Ask an admin |

- **Accept:** AC-001 — a duplicate shows the notice and a link
"""

CONTRACT = """# Contract
## 1. Capabilities
| # | Capability | Status | Source | Needed by | Backend DES |
|---|---|---|---|---|---|
| C-01 | duplicate detection | verified | docs/backend/03-detailed-design.md DES-002 | PAGE-001 | DES-002 |
"""

FINDINGS = """# Findings

## Captured / not captured
- **Not captured:** narrow screen

## Findings
### F-001 — Raw 409 shown
- **Priority:** P1
- **Side:** frontend
- **Task damaged:** T-001 — admin re-uploads
- **Evidence:** `evidence/audit/dup.dom.html` (observed)
- **Recommendation:** map 409 to the notice
- **Owner:** fe-engineer · **Status:** open
"""

QUEUE = """# Queue

### Q-001 — Duplicate notice
- **Spec:** 03-spec.md PAGE-001 AC-001
- **Files:** `web/notice.html`
- **Observable:** an amber notice reads "Already uploaded" with a link to the original
- **Priority:** P1
- **Side:** frontend
- **Acceptance:** AC-001
- **Depends on:** none
- **Status:** queued
"""

VERIFY = """# Verification

- Evidence: `evidence/verify-1/manifest.md`

## Verdicts
| Row | Verdict | Evidence | Note |
|---|---|---|---|
| Q-001 | done | `Q-001-dup@80x24.stdout` · duplicate · 80x24 | matches |
"""

TERMINAL_PLAN = {"surface": "terminal", "captures": [
    {"id": "Q-001-dup", "row": "Q-001", "state": "duplicate", "command": "cat web/notice.html"}]}

FE_STATE = {"harness_version": "5.1.0", "mode": "new", "feature": "dup", "status": "in_progress",
            "current_phase": 1, "phases": [], "models": {}}


class FrontBase(Base):
    def setUp(self):
        super().setUp()
        p = self.p
        p.fe = p.root / "docs" / "frontend"
        p.write("docs/frontend/state.json", json.dumps(FE_STATE))
        for n, t in (("01-brief.md", BRIEF), ("02-structure.md", STRUCTURE), ("03-spec.md", SPEC),
                     ("04-findings.md", FINDINGS)):
            p.write(f"docs/frontend/{n}", t + "\n".join(["filler"] * 8) + "\n")
        p.write("docs/frontend/evidence/audit/dup.dom.html", "<p>409</p>")
        p.write("contracts/FRONTEND_BACKEND_CONTRACT.md", CONTRACT)
        self.fe_log("dispatch", "--agent", "fe-critic", "--model", "opus", "--step", "1", "--note", "brief")
        self.fe_log("return", "--agent", "fe-critic", "--step", "1", "--status", "ok", "--note", "brief")

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

    def fe_dispatch(self, role):
        subprocess.run([PY, str(GATE), "mark", "--role", role, "--team", "frontend", "--project", str(self.p.root)],
                       capture_output=True, text=True)
        self.fe_log("dispatch", "--agent", role, "--model", "opus", "--step", "x", "--note", "work")
        self.fe_log("return", "--agent", role, "--step", "x", "--status", "ok", "--note", "done")

    def st(self, rep, cid):
        return self.p.status(rep, cid)

    def to_build(self):
        """Design gates green, queue approved at Plan, baseline, fe-engineer dispatched."""
        s = json.loads(self.p.read("docs/frontend/state.json"))
        s["mode"] = "implement"
        self.p.write("docs/frontend/state.json", json.dumps(s))
        self.p.write("docs/frontend/05-queue.md", QUEUE + "\n".join(["filler"] * 8) + "\n")
        assert self.fe("fe-queue")[0] == 0, self.fe("fe-queue")[1]
        assert self.fe("fe-plan")[0] == 0, self.fe("fe-plan")[1]
        self.fe_log("human", "--stop", "Plan", "--decision", "approved", "--by", "user", "--note", "ok")
        assert self.fe("fe-approve", "--by", "user")[0] == 0
        r = subprocess.run([PY, str(GATE), "baseline", "--team", "frontend", "--project", str(self.p.root)],
                           capture_output=True, text=True)
        assert r.returncode == 0, r.stdout + r.stderr
        self.fe_dispatch("fe-engineer")


class DesignGates(FrontBase):
    def test_all_design_gates_green(self):
        for g in ("fe-brief", "fe-structure", "fe-spec", "fe-findings"):
            code, out, _ = self.fe(g)
            self.assertEqual(code, 0, f"{g}: {out}")

    def test_brief_defects(self):
        t = BRIEF.replace("office admin uploading contracts daily", "{one concrete role}")
        t = t.replace("- **Surface:** browser", "- **Surface:** browser | native app").replace("T-001 |", "X |", 1)
        self.p.write("docs/frontend/01-brief.md", t + "\n".join(["filler"] * 8))
        rep = self.fe("fe-brief")[2]
        for cid in ("FE1.user", "FE1.surface", "FE1.tasks"):
            self.assertEqual(self.st(rep, cid), "fail", cid)

    def test_structure_uncovered_task_and_incomplete_flow(self):
        t = STRUCTURE.replace("| PAGE-001 | Upload one file | T-001 |", "| PAGE-001 | Upload one file | T-009 |")
        t = t.replace("- **Recovery:** Retry keeps the file\n", "")
        self.p.write("docs/frontend/02-structure.md", t + "\n".join(["filler"] * 8))
        rep = self.fe("fe-structure")[2]
        for cid in ("FE3.pages", "FE3.coverage", "FE3.flows"):
            self.assertEqual(self.st(rep, cid), "fail", cid)

    def test_spec_defects(self):
        t = SPEC.replace("| permission-denied | notice | Ask an admin |\n", "").replace("default · focus · empty",
                                                                                        "default · empty")
        t = t.replace("- **Accept:** AC-001", "- **Accept:** see flow") + "\nUse #FF0000 for errors.\n"
        self.p.write("docs/frontend/03-spec.md", t + "\n".join(["filler"] * 8))
        self.p.write("contracts/FRONTEND_BACKEND_CONTRACT.md", CONTRACT.replace("| verified |", "| maybe |"))
        rep = self.fe("fe-spec")[2]
        for cid in ("FE4.states", "FE4.components", "FE4.tokens", "FE4.contract"):
            self.assertEqual(self.st(rep, cid), "fail", cid)

    def test_findings_defects(self):
        t = FINDINGS.replace("- **Priority:** P1", "- **Priority:** high").replace("(observed)", "")
        t = t.replace("dup.dom.html", "missing.html")
        self.p.write("docs/frontend/04-findings.md", t + "\n".join(["filler"] * 8))
        rep = self.fe("fe-findings")[2]
        details = " ".join(next(c for c in rep["checks"] if c["id"] == "FE5.findings")["details"])
        self.assertIn("priority 'high'", details)
        self.assertIn("not labelled observed/inferred", details)

    def test_findings_evidence_must_exist(self):
        self.p.write("docs/frontend/04-findings.md",
                     FINDINGS.replace("dup.dom.html", "missing.html") + "\n".join(["filler"] * 8))
        rep = self.fe("fe-findings")[2]
        self.assertIn("does not exist", " ".join(next(c for c in rep["checks"] if c["id"] == "FE5.findings")["details"]))

    def test_critic_is_read_only(self):
        self.fe_dispatch("fe-critic")
        self.p.write("web/notice.html", "<p>edited by critic</p>")
        self.assertEqual(self.st(self.fe("fe-findings")[2], "ROLE.read-only"), "fail")

    def test_designer_scope(self):
        self.fe_dispatch("fe-designer")
        self.p.write("web/app.css", "body{}")
        self.assertEqual(self.st(self.fe("fe-spec")[2], "ROLE.designer-scope"), "fail")

    def test_designer_writing_docs_is_fine(self):
        self.fe_dispatch("fe-designer")
        self.p.write("docs/frontend/03-spec.md", SPEC + "\n".join(["filler"] * 9))
        self.assertEqual(self.st(self.fe("fe-spec")[2], "ROLE.designer-scope"), "pass")

class Baseline(FrontBase):
    def test_other_teams_run_dir_is_not_user_work(self):
        self.p.write("docs/backend/01-requirements.md", "backend run in progress")
        r = subprocess.run([PY, str(GATE), "baseline", "--team", "frontend", "--project", str(self.p.root)],
                           capture_output=True, text=True)
        self.assertNotIn("[FAIL] BASE.clean-tree", r.stdout)

    def test_user_code_is_still_protected(self):
        self.p.write("calc/core.py", self.p.read("calc/core.py") + "\n# user wip\n")
        r = subprocess.run([PY, str(GATE), "baseline", "--team", "frontend", "--project", str(self.p.root)],
                           capture_output=True, text=True)
        self.assertIn("[FAIL] BASE.clean-tree", r.stdout)


class Parity(FrontBase):
    """Checks the backend already had: task source, item length, dependencies, traceability."""

    def test_task_without_source(self):
        self.p.write("docs/frontend/01-brief.md", BRIEF.replace('| "tell them it is a duplicate" |', "| {user's words} |")
                     + "\n".join(["filler"] * 8))
        self.assertEqual(self.st(self.fe("fe-brief")[2], "FE1.source"), "fail")

    def test_long_page_flow_and_finding(self):
        long = " ".join(["word"] * 210)
        self.p.write("docs/frontend/03-spec.md", SPEC.replace("- **Goal:** upload one file", f"- **Goal:** {long}")
                     + "\n".join(["filler"] * 8))
        self.assertEqual(self.st(self.fe("fe-spec")[2], "FE4.page-length"), "fail")
        self.p.write("docs/frontend/02-structure.md", STRUCTURE.replace("- **Cancel:** back to empty form",
                     "- **Cancel:** " + " ".join(["w"] * 90)) + "\n".join(["filler"] * 8))
        self.assertEqual(self.st(self.fe("fe-structure")[2], "FE3.flow-length"), "fail")
        self.p.write("docs/frontend/04-findings.md", FINDINGS.replace("- **Recommendation:** map 409 to the notice",
                     "- **Recommendation:** " + " ".join(["w"] * 90)) + "\n".join(["filler"] * 8))
        self.assertEqual(self.st(self.fe("fe-findings")[2], "FE5.finding-length"), "fail")


class QueueAndPlan(FrontBase):
    def test_queue_defects(self):
        t = QUEUE.replace("- **Priority:** P1\n", "").replace("PAGE-001 AC-001", "PAGE-009").replace(
            "- **Acceptance:** AC-001", "- **Acceptance:** AC-777")
        self.p.write("docs/frontend/05-queue.md", t + "\n".join(["filler"] * 8))
        rep = self.fe("fe-queue")[2]
        details = " ".join(next(c for c in rep["checks"] if c["id"] == "FE6.rows")["details"])
        for needle in ("ungraded", "names no known PAGE", "names no known AC"):
            self.assertIn(needle, details)

    def test_plan_sheet_and_approval(self):
        self.to_build()
        sheet = (self.p.fe / "gates" / "plan-review.md").read_text()
        self.assertIn("| Q-001 | P1 | an amber notice", sheet)
        self.assertIn("Named user", sheet)
        approved = json.loads((self.p.fe / "gates" / "observables-approved.json").read_text())
        self.assertEqual((approved["approved_by"], sorted(approved["rows"])), ("user", ["Q-001"]))

    def test_approve_needs_green_plan(self):
        self.p.write("docs/frontend/05-queue.md", QUEUE)
        self.assertEqual(self.fe("fe-approve", "--by", "user")[0], 2)


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

    def test_observable_changed_after_approval(self):
        self.p.write("docs/frontend/05-queue.md",
                     self.p.read("docs/frontend/05-queue.md").replace("Already uploaded", "Duplicate"))
        self.build_notice()
        self.assertEqual(self.st(self.fe("fe-build")[2], "FE.observables"), "fail")

    def _verify_setup(self, verdict="done", manifest=True):
        self.build_notice()
        assert self.fe("fe-build")[0] == 0
        self.p.write("docs/frontend/05-queue.md",
                     self.p.read("docs/frontend/05-queue.md").replace("**Status:** queued", "**Status:** done"))
        self.p.write("docs/frontend/capture-plan.json", json.dumps(TERMINAL_PLAN))
        if manifest:
            assert self.capture()[0] == 0
        self.fe_dispatch("fe-tester")
        self.p.write("docs/frontend/06-verification.md",
                     VERIFY.replace("| Q-001 | done |", f"| Q-001 | {verdict} |") + "\n".join(["filler"] * 8))

    def test_verify_green_and_accept(self):
        self._verify_setup()
        code, out, _ = self.fe("fe-verify")
        self.assertEqual(code, 0, out)
        code, out, rep = self.fe("fe-accept")
        self.assertEqual(code, 0, out)

    def test_not_observable_is_not_done(self):
        self._verify_setup("not observable")
        self.assertEqual(self.fe("fe-verify")[0], 0)
        self.assertEqual(self.st(self.fe("fe-accept")[2], "FEA.rows"), "fail")

    def test_bad_verdict_and_missing_manifest(self):
        self._verify_setup("looks fine", manifest=False)
        rep = self.fe("fe-verify")[2]
        self.assertEqual(self.st(rep, "FE8.verdicts"), "fail")
        self.assertEqual(self.st(rep, "FE8.evidence"), "fail")

    def test_row_tagged_test_must_pass(self):
        self._verify_setup()
        self.p.write("tests/test_rows.py", "def test_notice():\n    \"\"\"Q-001\"\"\"\n    assert 1 == 2\n")
        rep = self.fe("fe-verify")[2]
        self.assertEqual(self.st(rep, "FE8.row-tests"), "fail")
        # different length: Python's bytecode cache keys on mtime + size, and both writes share a second
        self.p.write("tests/test_rows.py", "def test_notice():\n    \"\"\"Q-001\"\"\"\n    assert 1 == 1  # fixed\n")
        self.assertEqual(self.st(self.fe("fe-verify")[2], "FE8.row-tests"), "pass")

    def test_new_npm_dependency_needs_the_spec(self):
        self.p.write("package.json", '{"dependencies": {"left-pad": "1.3.0"}}')
        self.p.write("docs/frontend/05-queue.md", self.p.read("docs/frontend/05-queue.md").replace(
            "`web/notice.html`", "`web/notice.html`, `package.json`"))
        rep = self.fe("fe-build")[2]
        self.assertEqual(self.st(rep, "FE7.dependencies"), "fail")
        self.p.write("docs/frontend/03-spec.md", self.p.read("docs/frontend/03-spec.md") + "\n## 7. Dependencies\n| left-pad | 1.3.0 | padding |\n")
        self.assertEqual(self.st(self.fe("fe-build")[2], "FE7.dependencies"), "pass")

    def test_matrix_written_and_gap_caught(self):
        self._verify_setup()
        self.assertEqual(self.fe("fe-verify")[0], 0)
        code, out, rep = self.fe("fe-accept")
        self.assertEqual(self.st(rep, "FEA.matrix"), "pass", out)
        self.assertIn("| T-001 | PAGE-001 | Q-001 done | yes |", (self.p.fe / "gates" / "traceability.md").read_text())
        self.p.write("docs/frontend/01-brief.md", BRIEF.replace("| T-001 | Uploads", "| T-002 | Bulk upload | many | x | monthly | \"bulk\" |\n| T-001 | Uploads")
                     .replace("- **Cut line (above):** T-001", "- **Cut line (above):** T-001, T-002") + "\n".join(["filler"] * 8))
        rep = self.fe("fe-accept")[2]
        self.assertIn("T-002", " ".join(next(c for c in rep["checks"] if c["id"] == "FEA.matrix")["details"]))

    def test_tester_edits_production(self):
        self._verify_setup()
        self.p.write("web/notice.html", "<p>tester fix</p>")
        self.assertEqual(self.st(self.fe("fe-verify")[2], "ROLE.tester-scope"), "fail")


class Capture(FrontBase):
    def setUp(self):
        super().setUp()
        self.to_build()
        self.p.write("web/notice.html", '<p class="warn">Already uploaded</p>')
        assert self.fe("fe-build")[0] == 0

    def test_plan_gate(self):
        self.assertEqual(self.st(self.fe("fe-capture-plan")[2], "FE8.capture-plan"), "fail")  # no plan
        self.p.write("docs/frontend/capture-plan.json", json.dumps({"surface": "web", "captures": [
            {"id": "c1", "row": "Q-009", "state": "dup", "url": "/"}]}))
        details = " ".join(next(c for c in self.fe("fe-capture-plan")[2]["checks"]
                                if c["id"] == "FE8.capture-plan")["details"])
        for needle in ("base_url", "sizes", "Q-001: no capture planned"):
            self.assertIn(needle, details)
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
        self.p.write("docs/frontend/06-verification.md", VERIFY + "\n".join(["filler"] * 8))
        self.assertEqual(self.st(self.fe("fe-verify")[2], "FE8.capture"), "pass")
        self.p.write("web/notice.html", '<p class="warn">Changed after capture</p>')
        rep = self.fe("fe-verify")[2]
        self.assertIn("source changed after capture",
                      " ".join(next(c for c in rep["checks"] if c["id"] == "FE8.capture")["details"]))

    def test_capture_before_build_is_stale(self):
        self.p.write("docs/frontend/capture-plan.json", json.dumps(TERMINAL_PLAN))
        self.capture()
        import time
        time.sleep(1.1)
        assert self.fe("fe-build")[0] == 0
        self.fe_dispatch("fe-tester")
        self.p.write("docs/frontend/06-verification.md", VERIFY + "\n".join(["filler"] * 8))
        details = " ".join(next(c for c in self.fe("fe-verify")[2]["checks"] if c["id"] == "FE8.capture")["details"])
        self.assertIn("before the last fe-build", details)

    def test_terminal_capture_with_no_output_fails(self):
        self.p.write("docs/frontend/capture-plan.json", json.dumps({"surface": "terminal", "captures": [
            {"id": "q", "row": "Q-001", "state": "dup", "command": "true"}]}))
        self.capture()
        self.fe_dispatch("fe-tester")
        self.p.write("docs/frontend/06-verification.md", VERIFY + "\n".join(["filler"] * 8))
        details = " ".join(next(c for c in self.fe("fe-verify")[2]["checks"] if c["id"] == "FE8.capture")["details"])
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


class Registry(FrontBase):
    """Accepted rows become OBS-### entries that later rounds must keep passing."""
    ROW_TEST = 'def test_notice():\n    """Q-001"""\n    assert open("web/notice.html").read().count("Already uploaded") == 1\n'

    def setUp(self):
        super().setUp()
        self.to_build()
        self.p.write("web/notice.html", '<p class="warn">Already uploaded</p>')
        assert self.fe("fe-build")[0] == 0
        self.p.write("docs/frontend/05-queue.md",
                     self.p.read("docs/frontend/05-queue.md").replace("**Status:** queued", "**Status:** done"))
        self.p.write("docs/frontend/capture-plan.json", json.dumps(TERMINAL_PLAN))
        assert self.capture()[0] == 0
        self.fe_dispatch("fe-tester")
        self.p.write("tests/test_rows.py", self.ROW_TEST)
        self.p.write("docs/frontend/06-verification.md", VERIFY + "\n".join(["filler"] * 8))

    def accept(self):
        code, out, _ = self.fe("fe-verify")
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
                                if c["id"] == "FE8.capture-plan")["details"])
        self.assertIn("OBS-001: no capture planned", details)
        rep = self.fe("fe-verify")[2]
        self.assertEqual(self.st(rep, "FE.regression-captures"), "fail")
        self.p.write("docs/frontend/06-verification.md", self.p.read("docs/frontend/06-verification.md").replace(
            "| Q-001 | done |", "| OBS-001 | done | `Q-001-dup@80x24.stdout` · recheck | holds |\n| Q-001 | done |"))
        self.assertEqual(self.st(self.fe("fe-verify")[2], "FE.regression-captures"), "pass")

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
        for n in ("01-brief", "02-structure", "03-spec", "04-findings"):
            self.p.write(f"docs/frontend/{n}.md", (self.EXAMPLES / f"{n}.example.md").read_text())
        self.p.write("docs/frontend/evidence/verify-1/duplicate.dom.html", "<p>409</p>")
        for g in ("fe-brief", "fe-structure", "fe-spec", "fe-findings"):
            code, out, _ = self.fe(g)
            self.assertEqual(code, 0, f"{g}: {out}")


if __name__ == "__main__":
    res = unittest.main(exit=False, verbosity=1).result
    print(f"{res.testsRun} cases, {len(res.failures) + len(res.errors)} failures")
    sys.exit(0 if res.wasSuccessful() else 1)
