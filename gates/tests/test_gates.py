#!/usr/bin/env python3
"""Regression matrix for gate.py: every check must go red on its defect and stay green on
innocent work. Run: python3 tests/test_gates.py"""
import json
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
import unittest

GATE = pathlib.Path(__file__).resolve().parent.parent / "gate.py"
PY = sys.executable

REQS = """# Requirements

## 0. Understanding
- **Asked:** "a calculator that adds and subtracts"
- **Means:** two pure functions
- **Ambiguities:** none

## 2. Scope
### 2.2 Non-goals
- No export.

## 4. Functional requirements
### REQ-001 — add numbers
- **Cut:** above
- **Fixtures:** FX-001
- **Source:** "adds"
- Given two ints, When add is called, Then it returns their sum
### REQ-002 — subtract
- **Cut:** above
- **Fixtures:** n/a — covered by the arithmetic identity test
- **Source:** "subtracts"
- Given two ints, When sub is called, Then it returns the difference
### REQ-003 — multiply later
- **Cut:** below
- **Source:** "maybe multiply one day"
- Given x, When later, Then later

## 8. Assumptions
| # | Assumption | Status |
|---|---|---|
| A1 | ints only | [verified] |

## 9. Open questions
| # | Question | Default |
|---|---|---|
| Q1 | overflow? | ignore |
"""

ARCH = """# Architecture
line
line
line
## 3. Components
calc module serves REQ-001 REQ-002
## 7. Alternatives considered
### Alternative A — class
### Alternative B — script
## 8. Risk register
| Risk | Mitigation |
|---|---|
| none | none |
"""

DESIGN = """# Detailed design
## 1. Layout
calc/core.py
calc/__init__.py
## 2. Modules
### DES-001 — calc/core.py add
- **Serves:** REQ-001
- **Side:** backend
### DES-002 — calc/core.py sub
- **Serves:** REQ-002
- **Side:** backend
filler
filler
"""

PLAN = """# Test plan
line
line
### TC-001 — add
- **Verifies:** REQ-001
- **Mode:** automated
### TC-002 — sub
- **Verifies:** REQ-002
- **Mode:** automated
line
line
"""

REPORT = """# Test report
line
line
## 3. Results by case
| TC | REQ | Result | Evidence |
|---|---|---|---|
| TC-001 | REQ-001 | pass | pytest |
| TC-002 | REQ-002 | pass | pytest |
line
line
line
"""

TESTS = '''from calc.core import add, sub


def test_existing():
    assert add(1, 1) == 2
'''

NEW_TESTS = '''import json
import pathlib

from calc.core import add, sub

FX = pathlib.Path(__file__).parent / "fixtures" / "approved" / "FX-001"


# TC-001 FX-001
def test_add():
    args = json.loads((FX / "input.json").read_text())["args"]
    assert add(*args) == json.loads((FX / "expected.json").read_text())["result"]


def test_sub():
    """TC-002"""
    assert sub(5, 3) == 2
'''

STATE = {"harness_version": "2.4.0", "feature": "calc", "status": "in_progress", "current_phase": 1,
         "phases": [], "models": {}, "loops": {}}


def sh(cwd, *cmd):
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)


class Project:
    def __init__(self):
        self.root = pathlib.Path(tempfile.mkdtemp(prefix="gatetest-"))
        self.run = self.root / "docs" / "backend"
        self.write("calc/__init__.py", "")
        self.write("calc/core.py", "def add(a, b):\n    return a + b\n\n\ndef sub(a, b):\n    return a - b\n")
        self.write("tests/test_calc.py", TESTS)
        self.write("pytest.ini", "[pytest]\npythonpath = .\n")
        self.write("requirements.txt", "requests==2.0\n")
        self.write(".gitignore", "__pycache__/\n.pytest_cache/\n")
        self.write(".claude/gates.json", json.dumps({
            "commands": {"build": f"{PY} -m compileall -q calc", "lint": None, "typecheck": None,
                         "test": f"{PY} -m pytest -q -p no:cacheprovider"},
            "confirmed": True, "confirmed_on": "2026-09-23"}))
        self.write("docs/backend/state.json", json.dumps(STATE))
        for n, t in (("01-requirements.md", REQS), ("02-architecture.md", ARCH),
                     ("03-detailed-design.md", DESIGN)):
            self.write(f"docs/backend/{n}", t)
        sh(self.root, "git", "init", "-q")
        sh(self.root, "git", "-c", "user.email=t@t", "-c", "user.name=t", "add", "-A")
        sh(self.root, "git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "init")
        self.log("dispatch", "--agent", "be-analyst", "--model", "opus", "--step", "1", "--note", "requirements")
        self.log("return", "--agent", "be-analyst", "--step", "1", "--status", "ok", "--note", "3 REQs")

    def log(self, *args):
        r = subprocess.run([PY, str(GATE), "log", *args, "--project", str(self.root)], capture_output=True, text=True)
        return r.returncode, r.stdout + r.stderr

    def dispatch(self, role):
        """mark, then log the dispatch and its return, as the orchestrator does."""
        self.gate("mark", "--role", role)
        self.log("dispatch", "--agent", role, "--model", "opus", "--step", "x", "--note", "work")
        self.log("return", "--agent", role, "--step", "x", "--status", "ok", "--note", "done")

    def events(self):
        p = self.run / "run-log.jsonl"
        return [json.loads(l) for l in p.read_text().splitlines()] if p.exists() else []

    def write(self, rel, text):
        p = self.root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text)

    def read(self, rel):
        return (self.root / rel).read_text()

    def gate(self, *args):
        r = subprocess.run([PY, str(GATE), *args, "--project", str(self.root)], capture_output=True, text=True)
        rep = None
        if args[0] not in ("mark", "profile", "log", "timeline", "fixtures-approve"):
            p = self.run / "gates" / f"{args[0]}-latest.json"
            rep = json.loads(p.read_text()) if p.exists() else None
        return r.returncode, r.stdout + r.stderr, rep

    def status(self, rep, cid):
        return next(c["status"] for c in rep["checks"] if c["id"] == cid)

    def draft_fixture(self, expected=5):
        self.write("tests/fixtures/candidates/FX-001/input.json", '{"args": [2, 3]}')
        self.write("tests/fixtures/candidates/FX-001/expected.json", json.dumps({"result": expected}))
        self.write("tests/fixtures/candidates/FX-001/meta.json",
                   json.dumps({"req": "REQ-001", "source": "user sample row 7", "compare": "exact"}))

    def approve(self):
        self.draft_fixture()
        assert self.gate("p2")[0] == 0, self.gate("p2")[1]
        self.log("human", "--stop", "Plan", "--decision", "approved", "--by", "user", "--note", "plan ok")
        assert self.gate("fixtures-approve", "--by", "user")[0] == 0

    def to_p4(self):
        """Fixtures approved at GF, baseline, developer marked; test plan present."""
        self.approve()
        assert self.gate("baseline")[0] == 0, self.gate("baseline")[1]
        self.write("docs/backend/04-test-plan.md", PLAN)
        self.dispatch("be-developer")

    def to_p5(self):
        self.to_p4()
        assert self.gate("p4")[0] == 0
        self.dispatch("be-tester")
        self.write("tests/test_new.py", NEW_TESTS)
        self.write("docs/backend/05-test-report.md", REPORT)

    def close(self):
        shutil.rmtree(self.root, ignore_errors=True)


class Base(unittest.TestCase):
    def setUp(self):
        self.p = Project()

    def tearDown(self):
        self.p.close()


class DocGates(Base):
    def test_p1_green(self):
        code, out, rep = self.p.gate("p1")
        self.assertEqual(code, 0, out)
        self.assertEqual(rep["data"]["active_reqs"], ["REQ-001", "REQ-002"])

    def test_p1_missing_gwt_cut_duplicate(self):
        t = REQS.replace("- Given two ints, When sub is called, Then it returns the difference\n", "")
        t = t.replace("### REQ-001 — add numbers\n- **Cut:** above\n", "### REQ-001 — add numbers\n")
        t = t.replace("### REQ-003", "### REQ-002")
        self.p.write("docs/backend/01-requirements.md", t)
        code, out, rep = self.p.gate("p1")
        self.assertEqual(code, 1)
        for cid in ("P1.acceptance", "P1.cut-line", "P1.req-ids"):
            self.assertEqual(self.p.status(rep, cid), "fail", cid)

    def test_p1_chinese_doc(self):
        t = ("# 需求\n## 0. 理解\n- 要一个加法\n## 非目标\n- 不导出\n## 功能需求\n### REQ-001 — 加法\n- **Cut:** above\n- **Fixtures:** n/a — 纯函数\n- **Source:** 「加法」\n"
             "- 给定两个整数，当调用 add，则返回和\n## 假设\n- 只有整数 [verified]\n## 待决问题\n- 无\n"
             "填充\n填充\n填充\n")
        self.p.write("docs/backend/01-requirements.md", t)
        code, out, _ = self.p.gate("p1")
        self.assertEqual(code, 0, out)

    def test_retired_req_exempt(self):
        t = REQS.replace("### REQ-002 — subtract\n- **Cut:** above\n- Given two ints, When sub is called, "
                         "Then it returns the difference\n", "### REQ-002 — subtract (retired)\n")
        self.p.write("docs/backend/01-requirements.md", t)
        self.assertEqual(self.p.gate("p1")[0], 0)

    def test_p2_green_and_uncovered(self):
        self.p.draft_fixture()
        self.assertEqual(self.p.gate("p2")[0], 0)
        self.p.write("docs/backend/02-architecture.md", ARCH.replace("REQ-002", ""))
        code, _, rep = self.p.gate("p2")
        self.assertEqual(code, 1)
        self.assertEqual(self.p.status(rep, "P2.coverage"), "fail")

    def test_p2_detailed_design_defects(self):
        self.p.draft_fixture()
        self.assertEqual(self.p.gate("p2")[0], 0)
        d = DESIGN.replace("- **Serves:** REQ-002\n- **Side:** backend\n", "- **Serves:** REQ-009\n")
        d += "### DES-003 — ui\n- **Serves:** REQ-001\n- **Side:** frontend\n"
        self.p.write("docs/backend/03-detailed-design.md", d)
        code, _, rep = self.p.gate("p2")
        self.assertEqual(code, 1)
        for cid in ("P3.serves", "P3.side", "P3.req-claimed", "P3.contract"):
            self.assertEqual(self.p.status(rep, cid), "fail", cid)
        self.assertEqual(self.p.status(rep, "P2.coverage"), "pass")
        self.p.write("contracts/FRONTEND_BACKEND_CONTRACT.md", "DES-003 shape")
        self.assertEqual(self.p.status(self.p.gate("p2")[2], "P3.contract"), "pass")

    def test_p2_needs_fixture_answers(self):
        """The merged design gate also requires every declared fixture's expected output (be-analyst)."""
        code, _, rep = self.p.gate("p2")
        self.assertEqual(code, 1)
        self.assertEqual(self.p.status(rep, "PLAN.inputs"), "fail")
        self.assertEqual(rep["fail_by_owner"], {"be-analyst": ["PLAN.inputs", "PLAN.expected"]})
        self.assertEqual(self.p.status(rep, "P2.coverage"), "pass")
        self.assertEqual(sum(c["id"] == "ALL.state" for c in rep["checks"]), 1)

    def test_old_gate_names_are_gone(self):
        self.assertEqual(self.p.gate("p3")[0], 2)
        self.assertEqual(self.p.gate("plan")[0], 2)

    def test_increment_section_is_read_and_retired_items_exempt(self):
        """PLAYBOOK §3B: an increment appends new items; a replaced item is retired in place."""
        t = REQS.replace("### REQ-002 — subtract\n", "### REQ-002 — subtract (retired, increment 2)\n")
        t += ("\n## Increment 2 — 2026-11-02\n### REQ-004 — subtract, saturating at zero\n- **Cut:** above\n"
              "- **Fixtures:** n/a — covered by unit tests\n- **Source:** \"never negative\"\n"
              "- Given 1 and 2, When sub is called, Then it returns 0\n")
        self.p.write("docs/backend/01-requirements.md", t)
        code, out, rep = self.p.gate("p1")
        self.assertEqual(code, 0, out)
        self.assertIn("REQ-004", rep["data"]["active_reqs"])
        self.assertNotIn("REQ-002", rep["data"]["active_reqs"])
        t2 = t.replace("### REQ-004", "### REQ-001")  # reusing an id is caught
        self.p.write("docs/backend/01-requirements.md", t2)
        self.assertEqual(self.p.status(self.p.gate("p1")[2], "P1.req-ids"), "fail")

    def test_missing_state(self):
        (self.p.run / "state.json").unlink()
        code, _, rep = self.p.gate("p1")
        self.assertEqual(self.p.status(rep, "ALL.state"), "fail")


class Baseline(Base):
    def test_dirty_tree_blocks(self):
        self.p.write("calc/core.py", self.p.read("calc/core.py") + "\n# user wip\n")
        code, _, rep = self.p.gate("baseline")
        self.assertEqual(self.p.status(rep, "BASE.clean-tree"), "fail")

    def test_run_dir_dirt_is_fine(self):
        self.p.write("docs/backend/notes.md", "x")
        code, out, _ = self.p.gate("baseline")
        self.assertEqual(code, 0, out)

    def test_prototype_dir_is_fine(self):
        # route/PROTOTYPE.md keeps the throwaway prototype in prototype/, often uncommitted
        self.p.write("prototype/README.md", "throwaway, not product code")
        code, out, _ = self.p.gate("baseline")
        self.assertEqual(code, 0, out)

    def test_red_baseline_blocks(self):
        self.p.write("calc/core.py", "def add(a, b):\n    return 0\n\n\ndef sub(a, b):\n    return a - b\n")
        sh(self.p.root, "git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qam", "red")
        code, _, rep = self.p.gate("baseline")
        self.assertEqual(self.p.status(rep, "CMD.test"), "fail")

    def test_unconfirmed_profile_is_config_error(self):
        cfg = json.loads(self.p.read(".claude/gates.json"))
        cfg["confirmed"] = False
        self.p.write(".claude/gates.json", json.dumps(cfg))
        self.assertEqual(self.p.gate("p1")[0], 2)


class BuildGate(Base):
    def setUp(self):
        super().setUp()
        self.p.to_p4()

    def test_innocent_change_green(self):
        self.p.write("calc/core.py", self.p.read("calc/core.py") + "\n\ndef mul(a, b):\n    return a * b\n")
        code, out, _ = self.p.gate("p4")
        self.assertEqual(code, 0, out)

    def test_frontend_file(self):
        self.p.write("calc/templates/page.html", "<p>")
        self.assertEqual(self.p.status(self.p.gate("p4")[2], "ROLE.frontend"), "fail")

    def test_existing_test_modified(self):
        self.p.write("tests/test_calc.py", TESTS + "\n# tweak\n")
        self.assertEqual(self.p.status(self.p.gate("p4")[2], "ROLE.tests"), "fail")

    def test_unplanned_file_then_logged(self):
        self.p.write("calc/extra.py", "X = 1\n")
        self.assertEqual(self.p.status(self.p.gate("p4")[2], "ROLE.unplanned"), "fail")
        self.p.write("docs/backend/08-implementation-log.md", "added calc/extra.py because ...")
        self.assertEqual(self.p.status(self.p.gate("p4")[2], "ROLE.unplanned"), "pass")

    def test_queue_row_counts_as_plan(self):
        # a frontend run's Side: backend queue row names its files in 03-queue.md
        self.p.write("calc/extra.py", "X = 1\n")
        self.p.write("docs/backend/03-queue.md", "### Q-001\n- **Side:** backend\n- **Files:** calc/extra.py\n")
        self.assertEqual(self.p.status(self.p.gate("p4")[2], "ROLE.unplanned"), "pass")

    def test_secret_and_personal_path(self):
        self.p.write("calc/core.py", self.p.read("calc/core.py") +
                     '\nAPI_KEY = "abcdefghijklmnop1234"\nDATA = "/Users/alice/data.csv"\n')
        rep = self.p.gate("p4")[2]
        self.assertEqual(self.p.status(rep, "P4.secrets"), "fail")
        self.assertEqual(self.p.status(rep, "P4.personal-paths"), "fail")

    def test_preexisting_path_not_flagged(self):
        # only lines added since the baseline commit are scanned
        self.p.write("calc/core.py", self.p.read("calc/core.py") + "\n\ndef mul(a, b):\n    return a * b\n")
        self.assertEqual(self.p.status(self.p.gate("p4")[2], "P4.personal-paths"), "pass")

    def test_new_dependency_needs_design(self):
        self.p.write("requirements.txt", "requests==2.0\nnumpy>=1.0\n")
        self.p.write("docs/backend/08-implementation-log.md", "requirements.txt changed")
        rep = self.p.gate("p4")[2]
        self.assertEqual(self.p.status(rep, "P4.dependencies"), "fail")
        self.p.write("docs/backend/03-detailed-design.md", DESIGN + "Dependency: numpy\n")
        self.assertEqual(self.p.status(self.p.gate("p4")[2], "P4.dependencies"), "pass")

    def test_red_tests(self):
        self.p.write("calc/core.py", "def add(a, b):\n    return 0\n\n\ndef sub(a, b):\n    return a - b\n")
        self.assertEqual(self.p.status(self.p.gate("p4")[2], "CMD.test"), "fail")

    def test_build_failure(self):
        self.p.write("calc/core.py", "def add(a, b)\n    return a\n")
        self.assertEqual(self.p.status(self.p.gate("p4")[2], "CMD.build"), "fail")

    def test_plan_defects(self):
        self.p.write("docs/backend/04-test-plan.md", PLAN.replace("- **Verifies:** REQ-002\n", "")
                     .replace("- **Mode:** automated\nline", "line"))
        rep = self.p.gate("p4")[2]
        self.assertEqual(self.p.status(rep, "P4.plan-cases"), "fail")
        self.assertEqual(self.p.status(rep, "P4.plan-coverage"), "fail")


class VerifyGate(Base):
    def setUp(self):
        super().setUp()
        self.p.to_p5()

    def test_green(self):
        code, out, rep = self.p.gate("p5")
        self.assertEqual(code, 0, out)
        self.assertEqual(rep["data"]["tc_observed"], {"TC-001": "passed", "TC-002": "passed"})

    def test_tester_edits_production(self):
        self.p.write("calc/core.py", self.p.read("calc/core.py") + "\n# tester\n")
        self.assertEqual(self.p.status(self.p.gate("p5")[2], "ROLE.tester-scope"), "fail")

    def test_false_pass_is_caught(self):
        self.p.write("tests/test_new.py", NEW_TESTS.replace("== 2", "== 99"))
        rep = self.p.gate("p5")[2]
        self.assertEqual(self.p.status(rep, "P5.tc-results"), "fail")
        self.assertEqual(self.p.status(rep, "P5.report-honest"), "fail")
        self.assertEqual(self.p.status(rep, "CMD.test"), "fail")

    def test_tc_missing_in_code_and_report(self):
        self.p.write("tests/test_new.py", NEW_TESTS.replace("# TC-001 FX-001\n", "# FX-001\n"))
        self.p.write("docs/backend/05-test-report.md", REPORT.replace("| TC-002 | REQ-002 | pass | pytest |\n", ""))
        rep = self.p.gate("p5")[2]
        self.assertEqual(self.p.status(rep, "P5.tc-in-code"), "fail")
        self.assertEqual(self.p.status(rep, "P5.report-complete"), "fail")

    def test_skip_added(self):
        self.p.write("tests/test_new.py", "import pytest\n" + NEW_TESTS.replace(
            "def test_sub", "@pytest.mark.skip\ndef test_sub"))
        rep = self.p.gate("p5")[2]
        self.assertEqual(self.p.status(rep, "P5.test-drift"), "fail")

    def test_fix_round_blames_the_fixer_not_the_tester(self):
        self.p.write("tests/test_new.py", NEW_TESTS.replace("assert sub(5, 3) == 2", "assert sub(5, 3) == 1"))
        self.assertEqual(self.p.gate("p5")[0], 1)
        self.p.dispatch("be-developer")          # fix round: developer changes code
        self.p.write("calc/core.py", self.p.read("calc/core.py").replace("return a - b", "return a - b - 1"))
        self.assertEqual(self.p.status(self.p.gate("p4")[2], "ROLE.unplanned"), "pass")
        code, out, rep = self.p.gate("p5")
        self.assertEqual(code, 0, out)
        self.assertEqual(self.p.status(rep, "ROLE.tests"), "pass")

    def test_existing_test_deleted(self):
        (self.p.root / "tests/test_calc.py").unlink()
        rep = self.p.gate("p5")[2]
        self.assertEqual(self.p.status(rep, "P5.test-drift"), "fail")

    def test_fixture_tampered(self):
        self.p.write("tests/fixtures/approved/FX-001/expected.json", '{"result": 6}')
        self.assertEqual(self.p.status(self.p.gate("p5")[2], "P5.fixtures"), "fail")

    def test_fixture_unused(self):
        unused = ("from calc.core import add, sub\n\n\n# TC-001\ndef test_add():\n    assert add(2, 3) == 5\n\n\n"
                  "def test_sub():\n    \"\"\"TC-002\"\"\"\n    assert sub(5, 3) == 2\n")
        self.p.write("tests/test_new.py", unused)
        rep = self.p.gate("p5")[2]
        self.assertEqual(self.p.status(rep, "P5.fixtures-used"), "fail")
        self.assertIn("FX-001: no test references it",
                      next(c for c in rep["checks"] if c["id"] == "P5.fixtures-used")["details"])

    def test_fixture_used_by_failing_test(self):
        self.p.write("tests/test_new.py", NEW_TESTS.replace('["result"]', '["result"] + 1'))
        self.assertEqual(self.p.status(self.p.gate("p5")[2], "P5.fixtures-used"), "fail")

    def test_fixture_green(self):
        rep = self.p.gate("p5")[2]
        self.assertEqual(self.p.status(rep, "P5.fixtures"), "pass")
        self.assertEqual(self.p.status(rep, "P5.fixtures-used"), "pass")
        self.assertEqual(rep["data"]["fx_observed"], {"FX-001": "passed"})

class ReviewAndAcceptance(Base):
    FINDINGS = """# Review
## 2. Findings
| ID | Severity | Lens | Where | REQ | Claim |
|---|---|---|---|---|---|
| FND-001 | major | correctness | calc/core.py:2 | REQ-001 | wrong |
### FND-001 — wrong
- **Scenario:** add(1,2) returns 0
- **Status:** {status}
filler
filler
filler
"""

    def setUp(self):
        super().setUp()
        self.p.to_p5()
        assert self.p.gate("p5")[0] == 0
        self.p.dispatch("be-reviewer")

    def test_p6_green_then_tree_changed(self):
        self.p.write("docs/backend/06-review-report.md", self.FINDINGS.format(status="open"))
        code, out, _ = self.p.gate("p6")
        self.assertEqual(code, 0, out)
        self.p.write("calc/core.py", self.p.read("calc/core.py") + "\n# reviewer edit\n")
        self.assertEqual(self.p.status(self.p.gate("p6")[2], "P6.tree-unchanged"), "fail")

    def test_p6_bad_anchor(self):
        self.p.write("docs/backend/06-review-report.md",
                     self.FINDINGS.format(status="open").replace("calc/core.py:2", "calc/core.py:999"))
        self.assertEqual(self.p.status(self.p.gate("p6")[2], "P6.findings"), "fail")

    def _p7(self, status):
        self.p.write("docs/backend/06-review-report.md", self.FINDINGS.format(status=status))
        assert self.p.gate("p6")[0] == 0
        for ph in ("p1", "p2"):
            assert self.p.gate(ph)[0] == 0, ph
        self.p.write("docs/backend/07-acceptance.md", "\n".join(["accepted"] * 12))
        return self.p.gate("p7")

    def test_full_tier_run_in_3_2_order(self):
        """Full development, 3.2.0 order: Prototype → Phase 2 → Plan → 4 → 5 → panel + coordinator → 7."""
        q = Project()
        try:
            q.write("docs/backend/state.json", json.dumps(dict(STATE, tier="full", risk="normal", prototype="built")))
            q.log("dispatch", "--agent", "fe-engineer", "--model", "sonnet", "--step", "1b", "--note", "prototype")
            q.log("return", "--agent", "fe-engineer", "--step", "1b", "--status", "ok", "--note", "runs")
            self.assertEqual(q.gate("p1")[0], 0)
            q.log("human", "--stop", "Prototype", "--decision", "approved", "--by", "user", "--note", "saw it")
            for agent in ("be-architect", "be-analyst"):
                q.log("dispatch", "--agent", agent, "--model", "opus", "--step", "2", "--note", "design")
                q.log("return", "--agent", agent, "--step", "2", "--status", "ok", "--note", "done")
            q.to_p5()
            assert q.gate("p5")[0] == 0
            q.gate("mark", "--role", "be-reviewer")
            for agent in ("be-review-behavior", "be-review-security", "be-reviewer"):
                q.log("dispatch", "--agent", agent, "--model", "opus", "--step", "6", "--note", "review")
                q.log("return", "--agent", agent, "--step", "6", "--status", "ok", "--note", "done")
            q.write("docs/backend/06-review-report.md", self.FINDINGS.format(status="fixed in round 1"))
            self.assertEqual(q.gate("p6")[0], 0, q.gate("p6")[1])
            q.write("docs/backend/07-acceptance.md", "\n".join(["accepted"] * 12))
            code, out, rep = q.gate("p7")
            self.assertEqual(code, 0, out)
            self.assertEqual(q.status(rep, "LOG.trail"), "pass")
        finally:
            q.close()

    def test_p7_open_major_blocks(self):
        code, _, rep = self._p7("open")
        self.assertEqual(self.p.status(rep, "P7.open-findings"), "fail")

    def test_p7_green(self):
        code, out, _ = self._p7("fixed in round 1")
        self.assertEqual(code, 0, out)
        self.assertIn("| REQ-001 | DES-001 | TC-001 passed | FX-001 passed | yes |",
                      (self.p.run / "gates" / "traceability.md").read_text())


class LoopAndWaiver(Base):
    def test_loop_cap_exit_3(self):
        self.p.write("docs/backend/01-requirements.md", REQS.replace("Given", "Say"))
        codes = [self.p.gate("p1")[0] for _ in range(4)]
        self.assertEqual(codes, [1, 1, 1, 3])
        self.p.write("docs/backend/01-requirements.md", REQS)
        self.assertEqual(self.p.gate("p1")[0], 0)
        self.p.write("docs/backend/01-requirements.md", REQS.replace("Given", "Say"))
        self.assertEqual(self.p.gate("p1")[0], 1)  # counter reset after a pass

    def test_waiver(self):
        self.p.write("docs/backend/01-requirements.md", REQS.replace("- **Cut:** above\n- **Fixtures:** FX-001", "- **Fixtures:** FX-001"))
        self.assertEqual(self.p.gate("p1")[0], 1)
        self.p.write("docs/backend/gates/waivers.json", json.dumps(
            [{"check": "P1.cut-line", "reason": "tiny round", "approved_by": "user", "date": "2026-09-23"}]))
        code, _, rep = self.p.gate("p1")
        self.assertEqual(code, 0)
        self.assertEqual(self.p.status(rep, "P1.cut-line"), "waived")

    def test_waiver_without_approver_ignored(self):
        self.p.write("docs/backend/01-requirements.md", REQS.replace("- **Cut:** above\n- **Fixtures:** FX-001", "- **Fixtures:** FX-001"))
        self.p.write("docs/backend/gates/waivers.json", json.dumps([{"check": "P1.cut-line"}]))
        self.assertEqual(self.p.gate("p1")[0], 1)


class Fixtures(Base):
    def test_p1_requires_declaration(self):
        self.p.write("docs/backend/01-requirements.md", REQS.replace("- **Fixtures:** FX-001\n", ""))
        self.assertEqual(self.p.status(self.p.gate("p1")[2], "P1.fixtures"), "fail")
        self.p.write("docs/backend/01-requirements.md", REQS.replace("n/a — covered by the arithmetic identity test",
                                                                     "n/a"))
        self.assertEqual(self.p.status(self.p.gate("p1")[2], "P1.fixtures"), "fail")

    def test_plan_missing_expected_and_meta(self):
        self.p.write("tests/fixtures/candidates/FX-001/input.json", '{"args": [2, 3]}')
        code, _, rep = self.p.gate("p2")
        self.assertEqual(code, 1)
        self.assertEqual(self.p.status(rep, "PLAN.expected"), "fail")
        self.assertEqual(self.p.status(rep, "PLAN.meta"), "fail")
        self.assertEqual(rep["fail_by_owner"], {"be-analyst": ["PLAN.expected", "PLAN.meta"]})

    def test_plan_green_writes_review_sheet(self):
        self.p.draft_fixture()
        code, out, rep = self.p.gate("p2")
        self.assertEqual(code, 0, out)
        sheet = (self.p.run / "gates" / "plan-review.md").read_text()
        self.assertIn("## FX-001 — REQ-001", sheet)
        self.assertIn('{"args": [2, 3]}', sheet)

    def test_approve_needs_green_gf_and_approver(self):
        self.assertEqual(self.p.gate("fixtures-approve", "--by", "user")[0], 2)
        self.p.draft_fixture()
        self.p.gate("p2")
        self.assertEqual(self.p.gate("fixtures-approve")[0], 2)
        self.assertEqual(self.p.gate("fixtures-approve", "--by", "user")[0], 0)
        man = json.loads(self.p.read("tests/fixtures/approved/APPROVED.json"))
        case = man["cases"]["FX-001"]
        self.assertEqual((case["req"], case["approved_by"], sorted(case["files"])),
                         ("REQ-001", "user", ["expected.json", "input.json", "meta.json"]))
        self.assertFalse((self.p.root / "tests/fixtures/candidates/FX-001").exists())

    def test_reapproval_is_explicit_and_keeps_history(self):
        self.p.approve()
        self.p.draft_fixture(expected=6)
        self.assertEqual(self.p.gate("p2")[0], 0)
        self.assertIn("RE-APPROVAL", (self.p.run / "gates" / "plan-review.md").read_text())
        self.assertEqual(self.p.gate("fixtures-approve", "--by", "user")[0], 2)
        self.assertEqual(self.p.gate("fixtures-approve", "--by", "user", "--reapprove", "FX-001")[0], 0)
        case = json.loads(self.p.read("tests/fixtures/approved/APPROVED.json"))["cases"]["FX-001"]
        self.assertEqual(len(case["history"]), 1)

    def test_unapproved_declared_fixture_blocks_p4(self):
        assert self.p.gate("baseline")[0] == 0
        self.p.write("docs/backend/04-test-plan.md", PLAN)
        self.p.dispatch("be-developer")
        self.assertEqual(self.p.status(self.p.gate("p4")[2], "P4.fixtures"), "fail")

    def test_developer_edits_approved_fixture(self):
        self.p.to_p4()
        self.p.write("tests/fixtures/approved/FX-001/expected.json", '{"result": 99}')
        rep = self.p.gate("p4")[2]
        self.assertEqual(self.p.status(rep, "P4.fixtures"), "fail")
        self.assertEqual(self.p.status(rep, "ROLE.tests"), "fail")

    def test_run_outputs_do_not_dirty_baseline(self):
        self.p.write("contracts/FRONTEND_BACKEND_CONTRACT.md", "seam")
        self.p.approve()
        self.assertEqual(self.p.status(self.p.gate("baseline")[2], "BASE.clean-tree"), "pass")


class Clarity(Base):
    def test_code_comment_does_not_split_a_design_item(self):
        d = DESIGN.replace("- **Serves:** REQ-001\n- **Side:** backend\n",
                           "- **Serves:** REQ-001\n```python\n# a comment, not a heading\ndef add(a, b): ...\n```\n"
                           "- **Side:** backend\n")
        self.p.write("docs/backend/03-detailed-design.md", d)
        code, out, rep = self.p.gate("p2")
        self.assertEqual(self.p.status(rep, "P3.side"), "pass", out)

    def test_missing_understanding_and_source(self):
        t = REQS.replace("## 0. Understanding", "## 0. Background").replace('- **Source:** "adds"\n', "")
        self.p.write("docs/backend/01-requirements.md", t)
        rep = self.p.gate("p1")[2]
        self.assertEqual(self.p.status(rep, "P1.understanding"), "fail")
        self.assertEqual(self.p.status(rep, "P1.source"), "fail")

    def test_unfilled_placeholder_is_not_a_source(self):
        for ph in ('{"the user\'s words"}', '<"the user\'s words">'):
            self.p.write("docs/backend/01-requirements.md", REQS.replace('- **Source:** "adds"', f"- **Source:** {ph}"))
            self.assertEqual(self.p.status(self.p.gate("p1")[2], "P1.source"), "fail", ph)

    def test_source_citing_an_artifact_passes(self):
        t = REQS.replace('- **Source:** "adds"', "- **Source:** brief.md §2")
        self.p.write("docs/backend/01-requirements.md", t)
        self.assertEqual(self.p.status(self.p.gate("p1")[2], "P1.source"), "pass")

    def test_long_requirement_and_paragraph(self):
        filler = " ".join(["word"] * 70)
        t = REQS.replace('- **Source:** "adds"', f'- **Source:** "adds"\n- **Note:** {filler}')
        self.p.write("docs/backend/01-requirements.md", t)
        rep = self.p.gate("p1")[2]
        self.assertEqual(self.p.status(rep, "P1.req-length"), "fail")
        self.assertEqual(self.p.status(rep, "P1.prose"), "fail")

    def test_chinese_counts_toward_length(self):
        t = REQS.replace('- **Source:** "adds"', '- **Source:** "adds"\n- **备注：** ' + "很长的中文说明" * 20)
        self.p.write("docs/backend/01-requirements.md", t)
        self.assertEqual(self.p.status(self.p.gate("p1")[2], "P1.req-length"), "fail")

    def test_tables_do_not_count_as_prose(self):
        rows = "\n".join(f"| R{i} | " + " ".join(["risk"] * 30) + " | fix |" for i in range(40))
        self.p.write("docs/backend/02-architecture.md", ARCH + "\n| Risk | Why | Fix |\n|---|---|---|\n" + rows + "\n")
        rep = self.p.gate("p2")[2]
        self.assertEqual(self.p.status(rep, "P2.length"), "pass")
        self.assertEqual(self.p.status(rep, "P2.prose"), "pass")

    def test_long_design_item(self):
        d = DESIGN.replace("- **Side:** backend\n### DES-002", "- **Side:** backend\n- **Behaviour:** "
                           + " ".join(["step"] * 130) + "\n### DES-002")
        self.p.write("docs/backend/03-detailed-design.md", d)
        self.assertEqual(self.p.status(self.p.gate("p2")[2], "P3.des-length"), "fail")

    def test_plan_sheet_without_fixtures(self):
        t = REQS.replace("- **Fixtures:** FX-001", "- **Fixtures:** n/a — pure function")
        self.p.write("docs/backend/01-requirements.md", t)
        self.p.write("docs/backend/02-architecture.md", ARCH + "## 4. Decisions\n| Decision | Chosen |\n|---|---|\n| store | none |\n")
        code, out, _ = self.p.gate("p2")
        self.assertEqual(code, 0, out)
        sheet = (self.p.run / "gates" / "plan-review.md").read_text()
        for needle in ("| REQ-001 — add numbers | above |", "## Non-goals", "- No export.", "| store | none |",
                       "_No fixtures this round._"):
            self.assertIn(needle, sheet)


class TemplateExamples(Base):
    """The examples agents imitate must pass the gates they are written for."""
    EXAMPLES = GATE.parent.parent / "backend" / "templates" / "examples"

    def test_examples_pass_doc_gates(self):
        if not self.EXAMPLES.is_dir():
            self.skipTest(f"{self.EXAMPLES} not installed next to the gates")
        for n in ("01-requirements", "02-architecture", "03-detailed-design"):
            self.p.write(f"docs/backend/{n}.md", (self.EXAMPLES / f"{n}.example.md").read_text())
        self.assertEqual(self.p.gate("p1")[0], 0)
        rep = self.p.gate("p2")[2]  # fixture files are not part of the examples: judge the document checks only
        docs_failing = [c["id"] for c in rep["checks"] if c["id"].startswith(("P2.", "P3.")) and c["status"] == "fail"]
        self.assertEqual(docs_failing, [])


class RunLog(Base):
    def test_every_gate_needs_the_log(self):
        (self.p.run / "run-log.jsonl").unlink()
        self.assertEqual(self.p.status(self.p.gate("p1")[2], "LOG.valid"), "fail")

    def test_gates_append_their_own_events(self):
        self.p.gate("p1")
        self.p.dispatch("be-tester")
        kinds = [e["event"] for e in self.p.events()]
        self.assertEqual(kinds, ["dispatch", "return", "gate", "mark", "dispatch", "return"])
        self.assertEqual(self.p.events()[2]["gate"], "p1")

    def test_tampering_breaks_the_chain(self):
        self.p.gate("p1")
        p = self.p.run / "run-log.jsonl"
        lines = p.read_text().splitlines()
        p.write_text("\n".join([lines[0].replace("requirements", "something else")] + lines[1:]) + "\n")
        rep = self.p.gate("p1")[2]
        self.assertEqual(self.p.status(rep, "LOG.valid"), "fail")
        p.write_text("\n".join(lines[1:]) + "\n")  # deleting a line also breaks it
        self.assertEqual(self.p.status(self.p.gate("p1")[2], "LOG.valid"), "fail")

    def test_log_rejects_incomplete_or_forged_events(self):
        self.assertEqual(self.p.log("dispatch", "--agent", "be-developer")[0], 2)
        self.assertEqual(self.p.log("return", "--agent", "be-analyst", "--step", "1", "--status", "fine",
                                    "--note", "x")[0], 2)
        self.assertEqual(self.p.log("gate", "--note", "forged pass")[0], 2)
        self.assertEqual(self.p.log("human", "--stop", "Plan", "--decision", "approved", "--by", "user",
                                    "--note", "ok")[0], 0)

    def test_log_and_timeline_need_no_profile(self):
        # route/PROTOTYPE.md logs the Prototype tier before any gate profile exists
        (self.p.root / ".claude" / "gates.json").unlink()
        self.assertEqual(self.p.log("dispatch", "--agent", "be-developer", "--model", "opus", "--step", "1b",
                                    "--note", "prototype")[0], 0)
        r = subprocess.run([PY, str(GATE), "timeline", "--project", str(self.p.root)],
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.p.gate("p1")[0], 2)

    def test_timeline(self):
        self.p.gate("p1")
        code, out = self.p.log("decision", "--agent", "be-architect", "--note", "chose SQLite: matches existing stack")
        self.assertEqual(code, 0)
        r = subprocess.run([PY, str(GATE), "timeline", "--project", str(self.p.root)], capture_output=True, text=True)
        md = (self.p.run / "run-log.md").read_text()
        self.assertIn("| 1 |", md)
        self.assertIn("be-analyst", md)
        self.assertIn("p1", md)
        self.assertIn("chose SQLite", md)

    def test_trail_catches_build_before_plan_and_missing_return(self):
        self.p.log("dispatch", "--agent", "be-developer", "--model", "opus", "--step", "4", "--note", "early")
        self.p.approve()
        self.p.log("dispatch", "--agent", "be-tester", "--model", "sonnet", "--step", "5", "--note", "never returns")
        import importlib
        sys.path.insert(0, str(GATE.parent))
        checks = importlib.import_module("gatelib.checks")
        ctx = checks.Ctx(self.p.root, "docs/backend", {"test_globs": [], "doc_globs": []})
        r = checks._log_trail(ctx)
        self.assertEqual(r["status"], "fail")
        joined = " ".join(r["details"])
        self.assertIn("before the Plan was approved", joined)
        self.assertIn("be-tester: 1 dispatch(es) never returned", joined)

    def _trail(self):
        import importlib
        sys.path.insert(0, str(GATE.parent))
        checks = importlib.import_module("gatelib.checks")
        return checks._log_trail(checks.Ctx(self.p.root, "docs/backend", {"test_globs": [], "doc_globs": []}))

    def _tier(self, tier):
        st = dict(STATE, tier=tier)
        self.p.write("docs/backend/state.json", json.dumps(st))

    def test_prototype_dispatch_may_precede_plan(self):
        self._tier("full")
        self.p.log("dispatch", "--agent", "fe-engineer", "--model", "sonnet", "--step", "1b", "--note", "prototype")
        self.p.log("return", "--agent", "fe-engineer", "--step", "1b", "--status", "ok", "--note", "runs")
        self.p.log("human", "--stop", "Prototype", "--decision", "approved", "--by", "user", "--note", "saw it")
        self.p.log("dispatch", "--agent", "be-architect", "--model", "opus", "--step", "2", "--note", "design")
        self.p.log("return", "--agent", "be-architect", "--step", "2", "--status", "ok", "--note", "done")
        self.p.approve()
        r = self._trail()
        self.assertEqual(r["status"], "pass", r.get("details"))

    def test_full_tier_needs_prototype_before_design(self):
        for step in ("2", "3"):  # Phase 2 since 3.2.0; Phase 3 in older runs
            with self.subTest(step=step):
                self.p.close()
                self.p = Project()
                self._tier("full")
                self.p.log("dispatch", "--agent", "be-architect", "--model", "opus", "--step", step, "--note", "design")
                self.p.log("return", "--agent", "be-architect", "--step", step, "--status", "ok", "--note", "done")
                self.p.log("human", "--stop", "Prototype", "--decision", "approved", "--by", "user", "--note", "late")
                self.p.approve()
                r = self._trail()
                self.assertEqual(r["status"], "fail")
                self.assertIn("before the Prototype was approved", " ".join(r["details"]))

    def test_reused_prototype_logged_at_kickoff_passes(self):
        self._tier("full")
        self.p.log("human", "--stop", "Prototype", "--decision", "approved", "--by", "user",
                   "--note", "reused docs/backend/01b-prototype.md, confirmed 2026-10-30")
        self.p.log("dispatch", "--agent", "be-architect", "--model", "opus", "--step", "2", "--note", "design")
        self.p.log("return", "--agent", "be-architect", "--step", "2", "--status", "ok", "--note", "done")
        self.p.approve()
        self.assertEqual(self._trail()["status"], "pass")

    def test_panelist_marks_are_reviewer_marks(self):
        self.p.gate("mark", "--role", "be-reviewer")
        for a in ("be-review-behavior", "be-review-security"):
            self.p.log("dispatch", "--agent", a, "--model", "opus", "--step", "6", "--note", "panel")
            self.p.log("return", "--agent", a, "--step", "6", "--status", "ok", "--note", "findings")
        self.p.gate("mark", "--role", "be-review-reliability")  # a panelist's own mark: also exempt
        self.p.approve()
        self.assertEqual(self._trail()["status"], "pass", self._trail().get("details"))

    def test_full_tier_without_prototype_fails_and_old_runs_unaffected(self):
        self.p.approve()
        self.assertEqual(self._trail()["status"], "pass")  # no tier key: runs before 2.8.0
        self._tier("full")
        r = self._trail()
        self.assertEqual(r["status"], "fail")
        self.assertIn("no approved Prototype stop", " ".join(r["details"]))

    def test_state_rejects_unknown_tier(self):
        self._tier("huge")
        code, out, rep = self.p.gate("p1")
        self.assertEqual(self.p.status(rep, "ALL.state"), "fail")

    def test_state_risk_values(self):
        for risk, want in (("high", "pass"), ("normal", "pass"), ("medium", "fail")):
            self.p.write("docs/backend/state.json", json.dumps(dict(STATE, risk=risk)))
            self.assertEqual(self.p.status(self.p.gate("p1")[2], "ALL.state"), want, risk)


class JsRunners(unittest.TestCase):
    """JUnit for JS runners, without needing node: detection, flags, stale reports, title mapping."""

    def setUp(self):
        sys.path.insert(0, str(GATE.parent))
        from gatelib import checks, runner  # noqa
        self.runner, self.checks = runner, checks
        self.d = pathlib.Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.d, ignore_errors=True)

    def pkg(self, scripts):
        (self.d / "package.json").write_text(json.dumps({"scripts": scripts}))

    def test_detects_runner_behind_package_scripts(self):
        self.pkg({"test": "vitest run", "e2e": "playwright test", "unit": "jest --ci"})
        r = self.runner.js_runner
        self.assertEqual(r(self.d, "npm run test"), ("vitest", True))
        self.assertEqual(r(self.d, "pnpm e2e"), ("playwright", True))
        self.assertEqual(r(self.d, "yarn unit"), ("jest", True))
        self.assertEqual(r(self.d, "npx vitest run"), ("vitest", False))
        self.assertEqual(r(self.d, "python3 -m pytest")[0], None)

    def test_flags_and_jest_without_reporter(self):
        self.pkg({"test": "vitest run", "unit": "jest"})
        cmd, env, pattern, _ = self.runner.junit_plan("npm run test", self.d, self.d / "j.xml")
        self.assertIn("-- --reporter=default --reporter=junit --outputFile.junit=", cmd)
        cmd, env, pattern, note = self.runner.junit_plan("npm run unit", self.d, self.d / "j.xml")
        self.assertEqual((cmd, pattern), ("npm run unit", None))
        self.assertIn("counts only", note)
        (self.d / "node_modules" / "jest-junit").mkdir(parents=True)
        cmd, env, pattern, _ = self.runner.junit_plan("npm run unit", self.d, self.d / "j.xml")
        self.assertEqual(env["JEST_JUNIT_OUTPUT_FILE"], str(self.d / "j.xml"))

    def test_configured_report_and_stale_report_ignored(self):
        rep = self.d / "reports"
        rep.mkdir()
        xml = '<testsuite><testcase classname="a" name="TC-001 ok"/></testsuite>'
        (rep / "old.xml").write_text(xml)
        os.utime(rep / "old.xml", (1, 1))
        r = self.runner.run_tests("true", self.d, 30, self.d / "log", self.d / "j.xml", "reports/*.xml")
        self.assertIsNone(r["cases"])
        self.assertIn("no report was written", r["junit_note"])
        r = self.runner.run_tests(f"echo '{xml}' > reports/new.xml", self.d, 30, self.d / "log",
                                  self.d / "j.xml", "reports/*.xml")
        self.assertEqual(r["cases"], [("a", "TC-001 ok", "passed")])

    def test_js_title_and_comment_tags(self):
        (self.d / "tests").mkdir()
        (self.d / "tests" / "a.test.ts").write_text(
            "describe('u', () => {\n  it('TC-001 adds', () => {})\n  // FX-001\n  test(\"shows notice\", () => {})\n})\n")
        cfg = {"test_globs": ["tests/**"]}
        locs = {**self.runner.tc_locations(self.d, ["tests/a.test.ts"], cfg),
                **self.runner.tc_locations(self.d, ["tests/a.test.ts"], cfg, prefix="FX")}
        cases = [("tests/a.test.ts", "u > TC-001 adds", "passed"), ("tests/a.test.ts", "u > shows notice", "failed")]
        self.assertEqual(self.checks._observed_ids(locs, dict.fromkeys(locs), cases),
                         {"TC-001": "passed", "FX-001": "failed"})

    def test_vitest_summary_fallback(self):
        c = self.runner.parse_counts(" Test Files  1 failed (1)\n      Tests  1 failed | 2 passed (3)\n")
        self.assertEqual((c["failed"], c["passed"]), (1, 2))


class Profile(unittest.TestCase):
    def test_detect_python(self):
        d = pathlib.Path(tempfile.mkdtemp())
        try:
            (d / "pyproject.toml").write_text("[tool.ruff]\n[tool.mypy]\n")
            (d / "tests").mkdir()
            r = subprocess.run([PY, str(GATE), "profile", "--project", str(d)], capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stderr)
            cfg = json.loads((d / ".claude/gates.json").read_text())
            self.assertEqual(cfg["commands"]["lint"], "ruff check .")
            self.assertIn("mypy", cfg["commands"]["typecheck"])
            self.assertIn("pytest", cfg["commands"]["test"])
            self.assertFalse(cfg["confirmed"])
        finally:
            shutil.rmtree(d)


if __name__ == "__main__":
    os.environ.setdefault("PYTHONDONTWRITEBYTECODE", "1")
    res = unittest.main(exit=False, verbosity=1).result
    print(f"{res.testsRun} cases, {len(res.failures) + len(res.errors)} failures")
    sys.exit(0 if res.wasSuccessful() else 1)
