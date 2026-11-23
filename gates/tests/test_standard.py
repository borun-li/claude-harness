#!/usr/bin/env python3
"""The Standard change tier (route/STANDARD.md): `std-build` and `std-accept` on a tiny git project.
A whole run passes, in-process and through gate.py; every STD.* check goes red on its defect.
Run: python3 -m pytest tests/test_standard.py -q"""
import json
import pathlib
import subprocess
import sys
import unittest

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE))

import test_checks_v10 as v10  # noqa: E402  (the project fixture)
from gatelib import capture, checks, standard  # noqa: E402

GATE = HERE.parent / "gate.py"
PY = sys.executable
PHASES = {**checks.PHASES, **standard.PHASES}
STATE = dict(v10.STATE, tier="standard", goal={"change": "calc multiplies", "check": "run the tests"})
PLAN = """# Plan — multiply

## Change
`calc` gains `mul(a, b)`.

## Files
| Path | Change | Side |
|---|---|---|
| `calc/core.py` | add `mul` | backend |

## Checks
| CHK | Shows | How |
|---|---|---|
| CHK-001 | 3 times 4 is 12 | test `test_mul` |

## Retired tests
none

## Risks and assumptions
- ints only
"""
MUL = v10.CORE + "\n\ndef mul(a, b):\n    return a * b\n"
TEST_MUL = "from calc.core import mul\n\n\n# CHK-001\ndef test_mul():\n    assert mul(3, 4) == 12\n"
REVIEW = """# Review
## Findings
| ID | Severity | Lens | Where | REQ | Claim |
|---|---|---|---|---|---|
| FND-001 | major | behaviour | calc/core.py:9 | none | mul accepts strings |
### FND-001 — mul accepts strings
- **Scenario:** mul("a", 3) returns "aaa"
- **Status:** {status}
"""
DEMO_PLAN = {"surface": "terminal", "captures": [{"id": "D-1", "command": "ls tests"}]}


class Run(v10.Proj):
    """A Standard run, driven in-process the way gate.py and its hooks drive it."""
    def __init__(self, run="docs/runs/calc", scope="backend"):
        super().__init__(run, PHASES)
        self.write(f"{run}/state.json", json.dumps(dict(STATE, scope=scope)))
        self.write(f"{run}/demo-plan.json", json.dumps(DEMO_PLAN))

    def demo(self, kind):
        entries, _ = capture.demo(self.ctx, kind)
        self.log("capture", round=f"demo-{kind}", captures=len(entries))

    def planned(self, plan=PLAN, engineer="be-developer"):
        """Kickoff and step 1: the demo's before, the baseline, the engineer's plan, the user's yes."""
        self.demo("before")
        assert self.gate("baseline")["CMD.test"]["status"] == "pass"
        self.out(engineer, "1")
        self.write(f"{self.run_rel}/plan.md", plan)
        self.back(engineer, "1")
        self.log("human", stop="Plan", decision="approved", by="user", note="plan ok")

    def built(self, plan=PLAN):
        """Step 2: the engineer builds what the plan names."""
        self.planned(plan)
        self.out("be-developer", "2")
        self.write("calc/core.py", MUL)
        self.back("be-developer", "2")

    def tested(self):
        """Step 3: the tester writes the plan's checks; std-build is green."""
        self.built()
        self.out("be-tester", "3")
        self.write("tests/test_mul.py", TEST_MUL)
        self.back("be-tester", "3")
        res = self.gate("std-build")
        assert all(r["status"] != "fail" for r in res.values()), res
        return res

    def reviewed(self, status="fixed in round 1"):
        """Step 4: one reviewer, its findings filed; the demo's after."""
        self.tested()
        checks.mark(self.ctx, "be-reviewer")
        self.log("mark", role="be-reviewer")
        self.log("dispatch", agent="be-review-behavior", model="opus", phase="4", note="sole reviewer")
        self.log("return", agent="be-review-behavior", phase="4", status="ok", note="1 finding")
        self.write(f"{self.run_rel}/review.md", REVIEW.format(status=status))
        self.demo("after")


class Base(unittest.TestCase):
    def setUp(self):
        self.p = Run()
        self.ctx = self.p.ctx

    def tearDown(self):
        self.p.close()

    def build(self):
        return {r["id"]: r for r in standard.build(self.ctx)[0]}

    def accept(self):
        return {r["id"]: r for r in standard.accept(self.ctx)[0]}


class WholeRun(Base):
    def test_exports_the_two_gates(self):
        self.assertEqual(sorted(standard.PHASES), ["std-accept", "std-build"])

    def test_passing_run_end_to_end(self):
        self.p.built()
        first = self.p.gate("std-build")           # after the build: green, the checks' tests still owed
        self.assertEqual([i for i, r in first.items() if r["status"] == "fail"], [])
        self.assertEqual(first["STD.checks"]["status"], "unavailable")
        for cid in ("ALL.state", "STD.plan", "ROLE.unplanned", "ROLE.control", "STD.dependencies", "P4.secrets",
                    "CMD.test", "STD.test-drift"):
            self.assertEqual(first[cid]["status"], "pass", cid)
        self.p.out("be-tester", "3")
        self.p.write("tests/test_mul.py", TEST_MUL)
        self.p.back("be-tester", "3")
        second = self.p.gate("std-build")
        self.assertEqual({r["status"] for r in second.values()} - {"pass", "unavailable"}, set())
        self.assertEqual((second["STD.checks"]["status"], second["STD.checks"]["owner"]), ("pass", "be-tester"))
        self.assertEqual(second["ROLE.tester-scope"]["status"], "pass")
        checks.mark(self.ctx, "be-reviewer")
        self.p.log("mark", role="be-reviewer")
        self.p.log("dispatch", agent="be-review-behavior", model="opus", phase="4", note="sole reviewer")
        self.p.log("return", agent="be-review-behavior", phase="4", status="ok", note="no blocker")
        self.p.write("docs/runs/calc/review.md", REVIEW.format(status="accepted as-is"))
        self.p.demo("after")
        last = self.p.gate("std-accept")
        self.assertEqual({i: r["status"] for i, r in last.items()},
                         {"ALL.state": "pass", "STD.gates": "pass", "STD.findings": "pass", "LOG.trail": "pass",
                          "DEMO": "pass"}, last)

    def test_frontend_only_run_charges_the_frontend_engineer(self):
        q = Run(scope="frontend")
        try:
            self.assertEqual(standard._engineer(q.ctx), "fe-engineer")
            q.planned(PLAN, engineer="fe-engineer")
            q.out("fe-engineer", "2")
            q.write("calc/core.py", MUL)
            q.write("calc/helper.py", "X = 1\n")
            q.back("fe-engineer", "2")
            res = {r["id"]: r for r in standard.build(q.ctx)[0]}
            self.assertEqual((res["ROLE.unplanned"]["status"], res["ROLE.unplanned"]["details"]),
                             ("fail", ["calc/helper.py"]))
            self.assertEqual(res["STD.plan"]["owner"], "fe-engineer")
            q.write("docs/runs/calc/plan.md", PLAN.replace("| backend |", "| backend |\n| `calc/helper.py` | new | backend |"))
            self.assertEqual({r["id"]: r for r in standard.build(q.ctx)[0]}["ROLE.unplanned"]["status"], "pass")
        finally:
            q.close()


class ThroughGatePy(unittest.TestCase):
    """The same run through the command line: gate.py knows both gates and logs them."""
    def setUp(self):
        self.p = Run()

    def tearDown(self):
        self.p.close()

    def gate(self, *args):
        r = subprocess.run([PY, str(GATE), *args, "--project", str(self.p.root)], capture_output=True, text=True)
        return r.returncode, r.stdout + r.stderr

    def agent(self, agent, step, mark=None):
        if mark:
            self.assertEqual(self.gate("mark", "--role", mark)[0], 0)
        self.assertEqual(self.gate("log", "dispatch", "--agent", agent, "--model", "opus", "--step", step,
                                   "--note", "work")[0], 0)

    def back(self, agent, step):
        self.assertEqual(self.gate("log", "return", "--agent", agent, "--step", step, "--status", "ok",
                                   "--note", "done")[0], 0)
        code, out = self.gate("land")
        self.assertEqual(code, 0, out)

    def test_passing_run(self):
        code, out = self.gate("demo", "before")
        self.assertEqual(code, 0, out)
        code, out = self.gate("baseline")
        self.assertEqual(code, 0, out)
        self.agent("be-developer", "1", mark="be-developer")
        self.p.write("docs/runs/calc/plan.md", PLAN)
        self.back("be-developer", "1")
        self.assertEqual(self.gate("log", "human", "--stop", "Plan", "--decision", "approved", "--by", "user",
                                   "--note", "plan ok")[0], 0)
        self.agent("be-developer", "2", mark="be-developer")
        self.p.write("calc/core.py", MUL)
        self.p.write("docs/runs/calc/handoff.md", "## be-developer #1 · 2 · round 1 · t\nTask: mul\n")
        self.back("be-developer", "2")
        code, out = self.gate("std-build")
        self.assertEqual(code, 0, out)
        self.agent("be-tester", "3", mark="be-tester")
        self.p.write("tests/test_mul.py", TEST_MUL)
        self.back("be-tester", "3")
        code, out = self.gate("std-build")
        self.assertEqual(code, 0, out)
        self.assertIn("[PASS] STD.checks", out)
        self.agent("be-review-behavior", "4", mark="be-reviewer")
        self.back("be-review-behavior", "4")
        self.p.write("docs/runs/calc/review.md", REVIEW.format(status="fixed in round 1"))
        self.assertEqual(self.gate("std-accept")[0], 1)  # no demo after yet
        code, out = self.gate("demo", "after")
        self.assertEqual(code, 0, out)
        code, out = self.gate("std-accept")
        self.assertEqual(code, 0, out)
        for cid in ("STD.gates", "STD.findings", "LOG.trail", "DEMO"):
            self.assertIn(f"[PASS] {cid}", out)


class PlanCheck(Base):
    def test_missing_plan(self):
        self.p.demo("before")
        self.p.gate("baseline")
        self.p.dispatch("be-developer", "1")
        res = self.build()["STD.plan"]
        self.assertEqual((res["status"], res["owner"]), ("fail", "be-developer"))
        self.assertIn("plan.md missing", res["message"])

    def test_plan_without_files_or_checks(self):
        empty = PLAN.replace("| `calc/core.py` | add `mul` | backend |\n", "").replace(
            "| CHK-001 | 3 times 4 is 12 | test `test_mul` |\n", "| <CHK> | <what it proves> | test |\n")
        self.p.planned(empty)
        self.assertEqual(self.build()["STD.plan"]["details"],
                         ["§ Files: no table row names a path", "§ Checks: no table row starts with a CHK-nnn id"])
        self.p.write("docs/runs/calc/plan.md", PLAN)
        self.assertEqual(self.build()["STD.plan"]["status"], "pass")


class ChecksCheck(Base):
    TWO = PLAN.replace("| CHK-001 | 3 times 4 is 12 | test `test_mul` |",
                       "| CHK-001 | 3 times 4 is 12 | test `test_mul` |\n| CHK-002 | {shows} | {how} |")

    def test_check_no_test_carries(self):
        self.p.tested()
        self.p.write("docs/runs/calc/plan.md", self.TWO.format(shows="0 times n is 0", how="test"))
        res = self.build()["STD.checks"]
        self.assertEqual((res["status"], res["owner"], res["details"]),
                         ("fail", "be-tester", ["CHK-002: no test carries this id"]))
        self.p.write("tests/test_mul.py", TEST_MUL + "\n\ndef test_zero():\n    \"\"\"CHK-002\"\"\"\n    assert mul(0, 9) == 0\n")
        self.assertEqual(self.build()["STD.checks"]["status"], "pass")

    def test_manual_check_needs_its_evidence(self):
        self.p.tested()
        self.p.write("docs/runs/calc/plan.md", self.TWO.format(shows="the help text names mul",
                                                             how="manual: `evidence/help.txt`"))
        res = self.build()["STD.checks"]
        self.assertEqual((res["status"], res["owner"]), ("fail", "orchestrator"))
        self.assertEqual(res["details"], ["CHK-002: manual evidence evidence/help.txt does not exist"])
        self.p.write("docs/runs/calc/evidence/help.txt", "mul(a, b)\n")
        self.assertEqual(self.build()["STD.checks"]["status"], "pass")

    def test_before_a_tester_has_worked_it_is_not_checked_and_acceptance_waits(self):
        self.p.built()
        res = self.p.gate("std-build")["STD.checks"]
        self.assertEqual((res["status"], res["details"]), ("unavailable", ["CHK-001: no test carries this id"]))
        got = self.accept()["STD.gates"]
        self.assertEqual(got["status"], "fail")
        self.assertIn("STD.checks: not checked at the last std-build", got["details"][0])


class BuildChecks(Base):
    def test_file_the_plan_does_not_name(self):
        self.p.built()
        self.p.write("calc/extra.py", "X = 1\n")
        res = self.build()["ROLE.unplanned"]
        self.assertEqual((res["status"], res["details"]), ("fail", ["calc/extra.py"]))
        self.p.write("docs/runs/calc/plan.md", PLAN.replace("| backend |", "| backend |\n| `calc/extra.py` | new, "
                                                          "the parser needs it | backend |"))
        self.assertEqual(self.build()["ROLE.unplanned"]["status"], "pass")

    def test_dependency_the_plan_does_not_name(self):
        self.p.built()
        self.p.write("requirements.txt", "requests==2.0\n")
        res = self.build()["STD.dependencies"]
        self.assertEqual(res["status"], "fail")
        self.assertEqual(res["details"], ["requirements.txt: new dependency `requests` not named in plan.md"])
        self.p.write("docs/runs/calc/plan.md", PLAN + "- adds requests for the HTTP call\n")
        self.assertEqual(self.build()["STD.dependencies"]["status"], "pass")

    def test_test_removed_unless_the_plan_retires_it(self):
        self.p.built()
        (self.p.root / "tests/test_calc.py").unlink()
        res = self.build()["STD.test-drift"]
        self.assertEqual((res["status"], res["details"]), ("fail", ["tests/test_calc.py: deleted (1 tests)"]))
        self.p.write("docs/runs/calc/plan.md", PLAN.replace("## Retired tests\nnone", "## Retired tests\n- tests/test_calc.py"))
        self.assertEqual(self.build()["STD.test-drift"]["status"], "pass")

    def test_red_suite_goes_to_the_engineer(self):
        self.p.built()
        self.p.write("calc/core.py", MUL.replace("return a + b", "return a - b"))
        res = self.build()["CMD.test"]
        self.assertEqual((res["status"], res["owner"]), ("fail", "be-developer"))


class GatesCheck(Base):
    def gates(self):
        return self.accept()["STD.gates"]

    def test_never_run(self):
        self.p.built()
        self.assertEqual((self.gates()["status"], self.gates()["message"]), ("fail", "std-build has never run"))

    def test_last_run_red(self):
        self.p.tested()
        self.p.write("calc/extra.py", "X = 1\n")
        self.assertEqual(self.p.gate("std-build")["ROLE.tester-scope"]["status"], "fail")  # the tester went last
        self.assertIn("std-build fail", self.gates()["details"][0])

    def test_writer_dispatched_since(self):
        self.p.tested()
        self.assertEqual(self.gates()["status"], "pass")
        ev = self.p.out("be-developer", "2")
        self.p.back("be-developer", "2")
        self.assertEqual(self.gates()["details"], [f"#{ev['seq']}: be-developer dispatched after the last std-build"])
        self.p.gate("std-build")
        self.p.log("dispatch", agent="be-review-behavior", model="opus", phase="4", note="a reviewer is no writer")
        self.p.log("return", agent="be-review-behavior", phase="4", status="ok", note="done")
        self.assertEqual(self.gates()["status"], "pass")


class FindingsCheck(Base):
    def findings(self, status):
        self.p.write("docs/runs/calc/review.md", REVIEW.format(status=status))
        return self.accept()["STD.findings"]

    def test_no_review(self):
        self.p.tested()
        res = self.accept()["STD.findings"]
        self.assertEqual(res["status"], "fail")
        self.assertIn("review.md missing", res["message"])

    def test_open_major(self):
        self.p.tested()
        self.assertEqual(self.findings("open")["details"], ["FND-001 (major): status 'open'"])
        self.assertEqual(self.findings("not fixed — still accepts strings")["status"], "fail")
        self.assertEqual(self.findings("later")["details"], ["FND-001 (major): unrecognised status 'later'"])
        self.assertEqual(self.findings("fixed in round 1")["status"], "pass")
        self.p.write("docs/runs/calc/review.md", REVIEW.format(status="open").replace("| major |", "| minor |"))
        self.assertEqual(self.accept()["STD.findings"]["status"], "pass")


class TrailAndDemo(Base):
    def test_build_before_the_plan_is_approved(self):
        self.p.demo("before")
        self.p.gate("baseline")
        self.p.dispatch("be-developer", "1")      # planning needs no approval
        first = self.p.out("be-developer", "2")
        self.p.back("be-developer", "2")
        res = self.accept()["LOG.trail"]
        self.assertEqual((res["status"], res["details"]), ("fail", ["no approved Plan stop in the log"]))
        plan = self.p.log("human", stop="Plan", decision="approved", by="user", note="late")
        self.assertEqual(self.accept()["LOG.trail"]["details"],
                         [f"engineer dispatched to build (#{first['seq']}) before the Plan was approved (#{plan['seq']})"])

    def test_dispatch_never_returned(self):
        self.p.reviewed()
        self.assertEqual(self.accept()["LOG.trail"]["status"], "pass")
        self.p.log("dispatch", agent="be-review-security", model="opus", phase="4", note="second reviewer")
        self.assertEqual(self.accept()["LOG.trail"]["details"], ["be-review-security: 1 dispatch(es) never returned"])

    def test_demo_needs_its_after(self):
        self.p.tested()
        res = self.accept()["DEMO"]
        self.assertEqual(res["status"], "fail")
        self.assertIn("no after", " ".join(res["details"]))
        self.p.demo("after")
        self.assertEqual(self.accept()["DEMO"]["status"], "pass")


if __name__ == "__main__":
    unittest.main()
