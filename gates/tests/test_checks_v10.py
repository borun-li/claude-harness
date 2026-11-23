#!/usr/bin/env python3
"""Checks of gatelib/checks.py and gatelib/snap.py, called in-process on a tiny git project: what a
failure must survive, what a status means, whose the control files are, when the suite is re-run.
Run: python3 -m pytest tests/test_checks_v10.py -q"""
import json
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
import time
import unittest

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from gatelib import checks, runlog, snap  # noqa: E402
from gatelib.common import ConfigError  # noqa: E402

PY = sys.executable
CORE = "def add(a, b):\n    return a + b\n\n\ndef sub(a, b):\n    return a - b\n"
TESTS = "from calc.core import add\n\n\ndef test_existing():\n    assert add(1, 1) == 2\n"
STATE = {"harness_version": "10.0.0", "feature": "calc", "status": "in_progress", "current_phase": 1,
         "tier": "small", "scope": "backend",
         "phases": [], "models": {}, "goal": {"change": "add and sub return results", "check": "run calc"}}
REQS = """# Requirements
### REQ-001 — add
- **Cut:** above
- **Fixtures:** FX-001
- **Source:** "adds"
- Given two ints, When add is called, Then it returns their sum
### REQ-002 — subtract
- **Cut:** above
- **Fixtures:** n/a — covered by unit tests
- **Source:** "subtracts"
- Given two ints, When sub is called, Then it returns the difference
"""


def git(root, *args):
    return subprocess.run(["git", "-c", "user.email=t@t", "-c", "user.name=t", *args], cwd=root,
                          capture_output=True, text=True)


def config(root):
    cfg = json.loads((HERE.parent / "config.json").read_text())
    cfg.pop("_comment", None)
    cfg.update(json.loads((root / ".claude" / "gates.json").read_text()))
    return cfg


class Proj:
    """A committed project with one module, one test and an open run in `run`."""
    def __init__(self, run="docs/runs/calc", phases=None):
        self.root = pathlib.Path(tempfile.mkdtemp(prefix="gatev10-")).resolve()
        self.run_rel, self.phases = run, phases or checks.PHASES
        self.write("calc/__init__.py", "")
        self.write("calc/core.py", CORE)
        self.write("tests/test_calc.py", TESTS)
        self.write("pytest.ini", "[pytest]\npythonpath = .\n")
        self.write(".gitignore", "__pycache__/\n.pytest_cache/\n")
        self.write("docs/codemap.md", "# Code map\n## `calc/`\nEntry: `calc/core.py:add`\n")
        self.write(".claude/gates.json", json.dumps({
            "commands": {"build": None, "lint": None, "typecheck": None,
                         "test": f"{PY} -m pytest -q -p no:cacheprovider"},
            "confirmed": True, "confirmed_on": "2026-01-01"}))
        self.write(f"{run}/state.json", json.dumps(STATE))
        git(self.root, "init", "-q")
        git(self.root, "add", "-A")
        git(self.root, "commit", "-qm", "init")
        self.ctx = checks.Ctx(self.root, run, config(self.root))
        self.logfile = self.ctx.run / "run-log.jsonl"

    def write(self, rel, text):
        p = self.root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")

    def read(self, rel):
        return (self.root / rel).read_text(encoding="utf-8")

    def log(self, event, **fields):
        return runlog.append(self.logfile, event, **fields)

    def out(self, role, step="4"):
        """What the dispatch hook does: the role's mark, then its dispatch."""
        checks.mark(self.ctx, role)
        self.log("mark", role=role)
        return self.log("dispatch", agent=role, model="opus", phase=step, note="work")

    def back(self, role, step="4", **extra):
        return self.log("return", agent=role, phase=step, status="ok", note="done", **extra)

    def dispatch(self, role, step="4"):
        self.out(role, step)
        self.back(role, step)

    def gate(self, name):
        """What gate.py does around a phase: run it, keep the latest report, log the gate event."""
        res, _ = self.phases[name](self.ctx)
        overall = "fail" if any(r["status"] == "fail" for r in res) else "pass"
        (self.ctx.gdir / f"{name}-latest.json").parent.mkdir(parents=True, exist_ok=True)
        (self.ctx.gdir / f"{name}-latest.json").write_text(json.dumps({"overall": overall, "checks": res}))
        self.log("gate", gate=name, overall=overall)
        return {r["id"]: r for r in res}

    def roles(self):
        return {r["id"]: r for r in checks.role_checks(self.ctx)[0]}

    def close(self):
        shutil.rmtree(self.root, ignore_errors=True)
        shutil.rmtree(snap.cache_path(self.root).parent, ignore_errors=True)


class Base(unittest.TestCase):
    def setUp(self):
        self.p = Proj()
        self.ctx = self.p.ctx

    def tearDown(self):
        self.p.close()


class CarriedFailures(Base):
    """S6: a new dispatch takes a new snapshot; what failed before it is still failing."""
    def test_unplanned_file_outlives_the_redispatch_until_the_plan_names_it(self):
        self.p.gate("baseline")
        self.p.write("docs/runs/calc/03-detailed-design.md", "# Design\n" + "calc/core.py\n" * 12)
        self.p.write("docs/runs/calc/04-test-plan.md", "# Test plan\n" + "line\n" * 12)
        self.p.dispatch("be-developer")
        self.p.write("calc/extra.py", "X = 1\n")
        first = self.p.gate("p4")["ROLE.unplanned"]
        self.assertEqual((first["status"], first["details"]), ("fail", ["calc/extra.py"]))
        self.p.dispatch("be-developer")  # handed back: the hook marks again, the file is now "already there"
        again = self.p.gate("p4")["ROLE.unplanned"]
        self.assertEqual(again["status"], "fail")
        self.assertEqual(again["details"], ["calc/extra.py — carried from an earlier run"])
        self.assertEqual(again["owner"], "be-developer")
        self.p.write("docs/runs/calc/08-implementation-log.md", "Added calc/extra.py: the parser needs it.\n")
        self.assertEqual(self.p.gate("p4")["ROLE.unplanned"]["status"], "pass")
        self.assertEqual(json.loads((self.ctx.gdir / "role-open.json").read_text()), [])

    def test_modified_test_outlives_the_redispatch_until_it_is_reverted(self):
        self.p.dispatch("be-developer")
        self.p.write("tests/test_calc.py", TESTS + "\n# loosened\n")
        self.assertEqual(self.p.roles()["ROLE.tests"]["details"], ["tests/test_calc.py"])
        self.p.dispatch("be-developer")
        self.assertEqual(self.p.roles()["ROLE.tests"]["details"],
                         ["tests/test_calc.py — carried from an earlier run"])
        self.p.write("tests/test_calc.py", TESTS)  # undone: differs from the newer snapshot, not from the first
        self.assertEqual(self.p.roles()["ROLE.tests"]["status"], "pass")
        self.assertEqual(self.p.roles()["ROLE.tests"]["status"], "pass")  # and stays so on a second look
        self.p.write("tests/test_calc.py", TESTS + "\n# loosened again\n")
        self.assertEqual(self.p.roles()["ROLE.tests"]["status"], "fail")

    def test_unplanned_file_deleted_again_is_resolved(self):
        self.p.dispatch("be-developer")
        self.p.write("calc/extra.py", "X = 1\n")
        self.assertEqual(self.p.roles()["ROLE.unplanned"]["status"], "fail")
        self.p.dispatch("be-developer")
        (self.p.root / "calc/extra.py").unlink()
        self.assertEqual(self.p.roles()["ROLE.unplanned"]["status"], "pass")

    def test_another_role_dispatched_next_does_not_clear_it(self):
        self.p.dispatch("be-developer")
        self.p.write("calc/templates/page.html", "<p>")
        self.p.write("docs/runs/calc/08-implementation-log.md", "calc/templates/page.html\n")
        self.assertEqual(self.p.roles()["ROLE.frontend"]["status"], "fail")
        self.p.dispatch("be-tester")
        res = self.p.roles()
        self.assertEqual(res["ROLE.tester-scope"]["status"], "pass")
        self.assertEqual((res["ROLE.frontend"]["status"], res["ROLE.frontend"]["owner"]), ("fail", "be-developer"))
        self.assertEqual(res["ROLE.frontend"]["details"], ["calc/templates/page.html — carried from an earlier run"])
        (self.p.root / "calc/templates/page.html").unlink()
        self.assertNotIn("ROLE.frontend", self.p.roles())

    def test_carried_path_is_owed_by_the_role_it_was_recorded_for(self):
        self.p.dispatch("be-developer")
        self.p.write("calc/extra.py", "X = 1\n")
        self.assertEqual(self.p.roles()["ROLE.unplanned"]["owner"], "be-developer")
        self.p.dispatch("fe-engineer")
        self.p.write("calc/more.py", "Y = 1\n")
        got = self.p.roles()["ROLE.unplanned"]
        self.assertEqual(got["details"], ["calc/more.py", "calc/extra.py — carried from an earlier run"])
        self.assertEqual(got["owner"], "be-developer+fe-engineer")

    def test_tree_changed_during_review_outlives_a_new_reviewer_mark(self):
        self.p.dispatch("be-reviewer", "6")
        self.p.write("calc/core.py", CORE + "\n# edited during review\n")
        tree = lambda: next(r for r in checks.phase6(self.ctx)[0] if r["id"] == "P6.tree-unchanged")
        self.assertEqual(tree()["details"], ["calc/core.py"])
        self.p.dispatch("be-reviewer", "6")
        self.assertEqual(tree()["details"], ["calc/core.py — carried from an earlier run"])
        self.p.write("calc/core.py", CORE)
        self.assertEqual(tree()["status"], "pass")

    def tree(self):
        return next(r for r in checks.phase6(self.ctx)[0] if r["id"] == "P6.tree-unchanged")

    def test_tree_unchanged_record_ends_with_the_next_build(self):
        """A builder dispatched since may edit the file for good: it never returns to its recorded hash."""
        self.p.dispatch("be-reviewer", "6")
        self.p.write("calc/core.py", CORE + "\n# edited during review\n")
        self.assertEqual(self.tree()["status"], "fail")
        self.p.dispatch("be-reviewer", "6")
        self.assertEqual(self.tree()["details"], ["calc/core.py — carried from an earlier run"])
        self.p.dispatch("be-developer")
        self.p.write("calc/core.py", CORE + "\n\ndef mul(a, b):\n    return a * b\n")
        self.p.dispatch("be-reviewer", "6")
        self.assertEqual(self.tree()["status"], "pass")
        self.assertEqual(json.loads((self.ctx.gdir / "role-open.json").read_text()), [])

    def test_a_builders_change_after_the_review_is_not_recorded(self):
        self.p.dispatch("be-reviewer", "6")
        self.p.dispatch("be-developer")
        self.p.write("calc/core.py", CORE + "\n# the fix\n")
        self.assertEqual(self.tree()["details"], ["calc/core.py"])  # p6 before the re-review: stale, and says so
        self.assertFalse((self.ctx.gdir / "role-open.json").exists())
        self.p.dispatch("be-reviewer", "6")
        self.assertEqual(self.tree()["status"], "pass")
        self.p.write("calc/core.py", CORE + "\n# edited during the second review\n")
        self.assertEqual(self.tree()["status"], "fail")
        self.p.dispatch("be-reviewer", "6")
        self.assertEqual(self.tree()["details"], ["calc/core.py — carried from an earlier run"])

    def test_carry_reports_and_records(self):
        """The helper frontend.py calls for FE4.tree-unchanged."""
        self.assertEqual(checks.carry(self.ctx, "X.check", "fe-reviewer", ["calc/core.py", "new.txt"],
                                      {"calc/core.py": "0" * 40}), ["calc/core.py", "new.txt"])
        rows = json.loads((self.ctx.gdir / "role-open.json").read_text())
        self.assertEqual(rows, [{"check": "X.check", "role": "fe-reviewer", "path": "calc/core.py", "hash": "0" * 40},
                                {"check": "X.check", "role": "fe-reviewer", "path": "new.txt", "hash": None}])
        # new.txt does not exist, as when it was recorded: resolved. calc/core.py is not back to its hash.
        self.assertEqual(checks.carry(self.ctx, "X.check", "fe-reviewer", [], {}),
                         ["calc/core.py — carried from an earlier run"])
        self.assertEqual(checks.carry(self.ctx, "Y.other", "fe-reviewer", [], {}), [])
        self.assertEqual(checks.carry(self.ctx, "X.check", "fe-reviewer", [], {}, resolved=lambda p: True), [])
        self.assertEqual(json.loads((self.ctx.gdir / "role-open.json").read_text()), [])

    def test_dry_run_records_nothing(self):
        self.ctx.dry = True
        self.assertEqual(checks.carry(self.ctx, "X.check", "be-developer", ["calc/core.py"], {}), ["calc/core.py"])
        self.assertFalse((self.ctx.gdir / "role-open.json").exists())


class FindingStatus(unittest.TestCase):
    """S7: a status closes a finding only when it starts with a closing word."""
    def test_closed(self):
        for s in ("fixed", "Fixed in round 2", "fixed in round 1 — see TC-009", "**fixed in round 1**", "`resolved`",
                  "accepted as-is", "_accepted_", "已修复", "已解决", "已接受（用户同意）"):
            self.assertTrue(checks.finding_closed(s), s)

    def test_open(self):
        for s in ("not fixed — still returns 0", "unresolved", "unfixed", "open", "", None, "fixedish",
                  "open | fixed in round n | accepted as-is", "fixed | open", "to be fixed", "wontfix",
                  "acceptedly", "未修复"):
            self.assertFalse(checks.finding_closed(s), s)

    def test_open_findings_name_a_status_they_cannot_read(self):
        found = {"FND-001": {"severity": "major", "status": "not fixed — still returns 0"},
                 "FND-002": {"severity": "blocker", "status": "wontfix"},
                 "FND-003": {"severity": "major", "status": "open | fixed in round n | accepted as-is"},
                 "FND-004": {"severity": "major", "status": "fixed in round 2"},
                 "FND-005": {"severity": "minor", "status": "open"},
                 "FND-006": {"severity": "major", "status": None}}
        self.assertEqual(checks.open_findings(found), [
            "FND-001 (major): status 'not fixed — still returns 0'",
            "FND-002 (blocker): unrecognised status 'wontfix'",
            "FND-003 (major): status 'open | fixed in round n | accepted as-is'",
            "FND-006 (major): status None"])


class ControlFiles(Base):
    """S8: gate and team configuration is no writer's to change."""
    def test_claude_dir_is_control_not_document(self):
        self.assertFalse(self.ctx.is_doc(".claude/gates.json"))
        self.assertTrue(self.ctx.is_control(".claude/gates.json"))
        self.assertTrue(self.ctx.is_doc("docs/runs/calc/01-requirements.md"))

    def test_writer_changing_gate_config_fails_once_and_keeps_failing(self):
        self.p.dispatch("be-developer")
        self.assertEqual(self.p.roles()["ROLE.control"]["status"], "pass")
        before = self.p.read(".claude/gates.json")
        self.p.write(".claude/gates.json", before.replace("-m pytest -q", "-c \\\"print('5 passed')\\\" #"))
        res = self.p.roles()
        self.assertEqual((res["ROLE.control"]["status"], res["ROLE.control"]["owner"], res["ROLE.control"]["details"]),
                         ("fail", "be-developer", [".claude/gates.json"]))
        self.assertIn("the orchestrator's", res["ROLE.control"]["message"])
        self.assertEqual(res["ROLE.unplanned"]["status"], "pass")  # one failure per file
        self.p.dispatch("be-developer")
        self.assertEqual(self.p.roles()["ROLE.control"]["details"], [".claude/gates.json — carried from an earlier run"])
        self.p.write(".claude/gates.json", before)
        self.assertEqual(self.p.roles()["ROLE.control"]["status"], "pass")

    def test_every_role(self):
        self.p.dispatch("be-tester")
        self.p.write(".claude/harness.json", '{"loops": {"max_rounds": 99}}')
        res = self.p.roles()
        self.assertEqual(res["ROLE.control"]["status"], "fail")
        self.assertEqual(res["ROLE.tester-scope"]["status"], "pass")

    def test_books_changed_while_an_agent_was_out(self):
        self.assertEqual(checks.control_files(self.ctx)[0]["status"], "pass")
        self.p.out("be-developer")
        ev = self.p.back("be-developer", control_changed=["docs/runs/calc/gates/tests-cache.json", ".claude/gates.json"])
        self.p.dispatch("be-tester")
        (res,) = checks.control_files(self.ctx)
        self.assertEqual((res["id"], res["status"], res["owner"]), ("CTRL.files", "fail", "orchestrator"))
        self.assertEqual(res["details"], [f"#{ev['seq']} be-developer: docs/runs/calc/gates/tests-cache.json",
                                          f"#{ev['seq']} be-developer: .claude/gates.json"])


class TestReuse(Base):
    """M3: the suite is re-run when code changes, not when a document does."""
    def detail(self, command="test"):
        res, _ = checks._tests(self.ctx, "be-developer", command=command)
        self.assertEqual(res["status"], "pass", res)
        return " ".join(res["details"])

    def test_documents_and_run_dir_books_do_not_repeat_the_suite(self):
        self.assertNotIn("reused", self.detail())
        self.p.write("docs/runs/calc/handoff.md", "## be-developer #1 · 4 · round 1 · t\nTask: x\n")
        self.p.write("docs/runs/calc/05-test-report.md", "# Report\n")
        self.p.write("docs/codemap.md", self.p.read("docs/codemap.md") + "Traps: none\n")
        self.p.write("README.md", "# calc\n")
        self.p.write("docs/runs/earlier/run-log.jsonl", "")
        self.assertIn("reused the run of", self.detail())
        self.p.write("calc/core.py", CORE + "\n# changed\n")
        self.assertNotIn("reused", self.detail())
        self.p.write(".claude/gates.json", self.p.read(".claude/gates.json").replace("2026-01-01", "2026-01-02"))
        self.assertNotIn("reused", self.detail())  # the configuration the suite runs under is not a document

    def test_one_entry_per_command(self):
        self.ctx.cfg["commands"]["fe_test"] = f"{PY} -m pytest -q -p no:cacheprovider tests/test_calc.py"
        self.assertNotIn("reused", self.detail())
        self.assertNotIn("reused", self.detail("fe_test"))
        self.assertIn("tests/test_calc.py", self.detail("fe_test"))
        self.assertIn("reused", self.detail())
        self.assertIn("reused", self.detail("fe_test"))
        self.assertEqual(sorted(json.loads((self.ctx.gdir / "tests-cache.json").read_text())), ["fe_test", "test"])
        self.ctx.cfg["commands"]["fe_test"] = f"{PY} -c \"import sys; sys.exit(1)\""
        self.assertEqual(checks._tests(self.ctx, "fe-engineer", command="fe_test")[0]["status"], "fail")
        self.assertEqual(sorted(json.loads((self.ctx.gdir / "tests-cache.json").read_text())), ["test"])

    def test_fe_test_is_not_measured_against_the_whole_suites_baseline(self):
        self.ctx.cfg["commands"]["fe_test"] = f"{PY} -m pytest -q -p no:cacheprovider tests/test_calc.py"
        self.p.write("tests/test_more.py", "def test_more():\n    assert True\n")
        base = {"counts": {"passed": 2, "failed": 0, "errors": 0, "skipped": 0, "xfailed": 0}}
        self.assertEqual(checks._tests(self.ctx, "fe-engineer", base, command="fe_test")[0]["status"], "pass")
        (self.p.root / "tests/test_more.py").unlink()
        res = checks._tests(self.ctx, "be-developer", base)[0]
        self.assertEqual(res["status"], "fail")
        self.assertIn("test total fell from 2 to 1", res["message"])


class HashCache(unittest.TestCase):
    """M3: unchanged files are not hashed again, and a changed file is never read from the cache."""
    def setUp(self):
        self.root = pathlib.Path(tempfile.mkdtemp(prefix="gatev10-snap-")).resolve()
        self.hashed = []
        self.real = snap.file_sha
        snap.file_sha = lambda path: (self.hashed.append(pathlib.Path(path).name), self.real(path))[1]

    def tearDown(self):
        snap.file_sha = self.real
        shutil.rmtree(self.root, ignore_errors=True)
        shutil.rmtree(snap.cache_path(self.root).parent, ignore_errors=True)

    def put(self, name, text, age):
        """Write `name` with an mtime `age` seconds in the past."""
        f = self.root / name
        f.write_text(text)
        t = time.time_ns() - int(age * 1e9)
        os.utime(f, ns=(t, t))
        return f

    def shot(self, **kw):
        self.hashed.clear()
        return snap.snapshot(self.root, [], **kw)

    def test_unchanged_files_are_read_from_the_cache(self):
        self.put("a.txt", "one", 60)
        self.put("b.txt", "two", 50)
        first = self.shot()
        self.assertEqual(sorted(self.hashed), ["a.txt", "b.txt"])
        self.assertEqual(self.shot(), first)
        self.assertEqual(self.hashed, [])
        self.assertNotIn(self.root, snap.cache_path(self.root).parents)  # outside the project

    def test_same_size_change_is_seen_when_mtime_changes(self):
        f = self.put("a.txt", "one", 60)
        first = self.shot()
        self.put("a.txt", "two", 30)  # same size, other content, newer mtime
        self.assertEqual(f.stat().st_size, 3)
        second = self.shot()
        self.assertEqual(self.hashed, ["a.txt"])
        self.assertNotEqual(second["a.txt"], first["a.txt"])
        self.assertEqual(second["a.txt"], self.real(f))
        self.assertEqual(self.shot(), second)  # and the new hash is what the cache holds now
        self.assertEqual(self.hashed, [])

    def test_changed_mtime_alone_is_hashed_again_never_served_stale(self):
        self.put("a.txt", "one", 60)
        first = self.shot()
        self.put("a.txt", "one", 40)
        self.assertEqual(self.shot(), first)
        self.assertEqual(self.hashed, ["a.txt"])

    def test_a_file_just_written_is_not_cached(self):
        """It may change again within the same timestamp: same size, same mtime, other content."""
        f = self.put("a.txt", "one", 0)
        st = f.stat()
        first = self.shot()
        f.write_text("two")
        os.utime(f, ns=(st.st_atime_ns, st.st_mtime_ns))
        self.assertNotEqual(self.shot()["a.txt"], first["a.txt"])

    def test_unreadable_cache_and_dry_snapshot(self):
        self.put("a.txt", "one", 60)
        self.shot(write_cache=False)
        self.assertFalse(snap.cache_path(self.root).exists())
        first = self.shot()
        snap.cache_path(self.root).write_text("{not json")
        self.assertEqual(self.shot(), first)
        self.assertEqual(self.hashed, ["a.txt"])


class Trail(Base):
    """M4: the hook marks; a mark taken twice before its dispatch is not a mark without one."""
    def trail(self, *events):
        evs = [dict(seq=i, **({"event": e[0], "role": e[1]} if e[0] == "mark" else
                               {"event": e[0], "agent": e[1]} if e[0] in ("dispatch", "return") else {"event": "gate"}))
               for i, e in enumerate(events, 1)]
        return checks._trail_common(evs)

    def test_mark_by_hand_then_by_the_hook(self):
        a = "be-developer"
        self.assertEqual(self.trail(("mark", a), ("mark", a), ("dispatch", a), ("return", a), ("gate",)), [])
        self.assertEqual(self.trail(("mark", "be-tester"), ("mark", a), ("mark", "be-tester"), ("dispatch", "be-tester"),
                                    ("dispatch", a), ("return", a), ("return", "be-tester")), [])

    def test_mark_with_no_dispatch_before_the_next_gate_or_the_end(self):
        a = "be-developer"
        self.assertEqual(self.trail(("mark", a), ("gate",), ("dispatch", a), ("return", a)),
                         ["#1: mark for be-developer not followed by its dispatch"])
        self.assertEqual(self.trail(("mark", a), ("dispatch", a), ("return", a), ("mark", a)),
                         ["#4: mark for be-developer not followed by its dispatch"])

    def test_missing_mark_says_who_takes_marks(self):
        for call in (lambda: checks._load_mark(self.ctx, "be-reviewer"), lambda: checks._latest_writer(self.ctx)):
            with self.assertRaises(ConfigError) as e:
                call()
            self.assertIn("dispatch hook", str(e.exception))
            self.assertIn("only to repair", str(e.exception))


class Panel(Base):
    """Two or more panelists need the coordinator after them; one is the sole reviewer."""
    def out(self, agent):
        self.p.log("dispatch", agent=agent, model="opus", phase="6", note="review")
        self.p.log("return", agent=agent, phase="6", status="ok", note="done")

    def panel(self):
        res = checks._panel_check(self.ctx)
        self.assertEqual((res["id"], res["owner"]), ("P6.panel", "orchestrator"))
        return res

    def test_one_panelist_needs_no_coordinator(self):
        self.assertEqual(self.panel()["status"], "pass")
        self.out("be-review-behavior")
        self.assertEqual((self.panel()["status"], self.panel()["message"]),
                         ("pass", "Panel: be-review-behavior, the sole reviewer"))

    def test_two_panelists_need_the_coordinator_after_them(self):
        self.out("be-reviewer")  # before the panel: it merged nothing
        self.out("be-review-behavior")
        self.out("be-review-security")
        res = self.panel()
        self.assertEqual((res["status"], res["details"]), ("fail", ["be-review-behavior", "be-review-security"]))
        self.out("be-reviewer")
        self.assertEqual(self.panel()["status"], "pass")

    def test_only_the_review_of_the_current_build_counts(self):
        self.out("be-review-behavior")
        self.out("be-review-security")
        self.p.dispatch("be-developer")       # the fix
        self.out("be-reviewer")               # re-checks the fixed findings
        self.assertEqual(self.panel()["status"], "pass")
        self.out("be-review-behavior")
        self.out("be-review-reliability")
        self.assertEqual(self.panel()["status"], "fail")

    def test_p6_runs_it(self):
        self.p.dispatch("be-reviewer", "6")
        self.assertIn("P6.panel", [r["id"] for r in checks.phase6(self.ctx)[0]])


class Locks(Base):
    """M8: what was approved or measured is compared with what the run log holds."""
    def approve(self):
        self.p.write("docs/runs/calc/01-requirements.md", REQS)
        cand = "tests/fixtures/candidates/FX-001"
        self.p.write(f"{cand}/input.json", '{"args": [2, 3]}')
        self.p.write(f"{cand}/expected.json", '{"result": 5}')
        self.p.write(f"{cand}/meta.json", json.dumps({"req": "REQ-001", "source": "sample", "compare": "exact"}))
        self.p.write("docs/runs/calc/gates/p2-latest.json", json.dumps({"overall": "pass", "data": {"to_approve": ["FX-001"]}}))
        (res,), _ = checks.approve_fixtures(self.ctx, "user", set())
        return res

    def test_approval_reports_the_manifest_hash_and_the_scope(self):
        res = self.approve()
        manifest = self.p.root / "tests/fixtures/approved/APPROVED.json"
        self.assertEqual(res["manifest_sha"], checks._sha(manifest))
        self.assertEqual(res["active_reqs"], ["REQ-001", "REQ-002"])

    def tamper(self):
        """Change an approved answer and the hash the manifest holds for it."""
        self.p.write("tests/fixtures/approved/FX-001/expected.json", '{"result": 6}')
        manifest = self.p.root / "tests/fixtures/approved/APPROVED.json"
        man = json.loads(manifest.read_text())
        man["cases"]["FX-001"]["files"]["expected.json"] = checks._sha(self.p.root / "tests/fixtures/approved/FX-001/expected.json")
        manifest.write_text(json.dumps(man))

    def test_manifest_edited_with_its_fixture_is_caught_from_the_log(self):
        res = self.approve()
        ev = self.p.log("approve", by="user", fixtures=res["details"], manifest_sha=res["manifest_sha"],
                        active_reqs=res["active_reqs"])
        self.p.log("approve", by="user", fixtures=["Q-001"])  # another kind of approval: carries no manifest
        self.assertEqual(checks._fixture_integrity(self.ctx, "P4.fixtures", "be-developer")["status"], "pass")
        self.tamper()
        got = checks._fixture_integrity(self.ctx, "P4.fixtures", "be-developer")
        self.assertEqual(got["status"], "fail")
        self.assertEqual(got["details"], [f"APPROVED.json: changed since the approval logged at #{ev['seq']}"])

    def test_without_a_logged_hash_the_manifest_is_trusted_as_before(self):
        res = self.approve()
        self.p.log("approve", by="user", fixtures=res["details"])
        self.tamper()
        self.assertEqual(checks._fixture_integrity(self.ctx, "P4.fixtures", "be-developer")["status"], "pass")

    def scope(self, text):
        self.p.write("docs/runs/calc/01-requirements.md", text)
        return checks._scope_check(self.ctx, checks._reqs(self.ctx))

    def test_req_leaves_scope_only_by_being_retired(self):
        self.assertEqual(self.scope(REQS)["status"], "pass")  # no approval logged: nothing to compare
        self.p.log("approve", by="user", fixtures=["FX-001"], manifest_sha="x", active_reqs=["REQ-001", "REQ-002"])
        self.assertEqual(self.scope(REQS)["status"], "pass")
        below = REQS.replace("### REQ-002 — subtract\n- **Cut:** above", "### REQ-002 — subtract\n- **Cut:** below")
        got = self.scope(below)
        self.assertEqual((got["id"], got["status"], got["owner"]), ("P7.scope", "fail", "orchestrator"))
        self.assertEqual(got["details"], ["REQ-002: no longer above the cut line"])
        self.assertIn("Constitution §5.1", got["message"])
        self.assertEqual(self.scope(REQS.split("### REQ-002")[0])["details"], ["REQ-002: no longer in 01-requirements.md"])
        self.assertEqual(self.scope(REQS.replace("### REQ-002 — subtract", "### REQ-002 — subtract (retired)"))["status"],
                         "pass")

    def test_p7_runs_the_scope_check(self):
        self.p.write("docs/runs/calc/01-requirements.md", REQS)
        self.p.write("docs/runs/calc/07-acceptance.md", "accepted\n" * 12)
        self.assertIn("P7.scope", [r["id"] for r in checks.phase7(self.ctx)[0]])

    def test_baseline_is_not_replaced_once_work_has_begun(self):
        self.p.gate("baseline")
        self.p.gate("baseline")  # nothing dispatched since: taking it again loses nothing
        self.p.dispatch("be-reviewer", "6")  # a reviewer writes nothing
        self.p.gate("baseline")
        self.p.dispatch("be-developer")
        self.p.write("calc/extra.py", "X = 1\n")
        kept = (self.ctx.gdir / "baseline.json").read_text()
        with self.assertRaises(ConfigError) as e:
            checks.baseline(self.ctx)
        self.assertIn("--rebaseline", str(e.exception))
        self.assertIn("be-developer", str(e.exception))
        self.assertEqual((self.ctx.gdir / "baseline.json").read_text(), kept)
        self.assertNotIn("calc/extra.py", json.loads(kept)["snapshot"])
        self.ctx.rebaseline = True
        checks.baseline(self.ctx)
        self.assertIn("calc/extra.py", json.loads((self.ctx.gdir / "baseline.json").read_text())["snapshot"])


class ExistingCode(Base):
    """S3: tests retired with their code, tool output in the tree, run dirs a project moved."""
    def test_drift_ignores_tests_the_plan_retires(self):
        self.p.write("tests/test_old.py", "def test_a():\n    assert True\n\n\ndef test_b():\n    assert True\n")
        base = self.p.gate("baseline") and json.loads((self.ctx.gdir / "baseline.json").read_text())
        drift = lambda: checks._test_file_drift(self.ctx, base, "be-developer", "P4.test-drift")
        (self.p.root / "tests/test_old.py").unlink()
        self.p.write("tests/test_calc.py", "from calc.core import add\n")
        self.assertEqual(drift()["details"], ["tests/test_calc.py: tests 1 -> 0", "tests/test_old.py: deleted (2 tests)"])
        self.p.write("docs/runs/calc/plan.md", "# Plan\n## Retired tests\n- `tests/test_old.py`: covered the removed "
                     "exporter\n## Risks and assumptions\n- tests/test_calc.py is touched\n")
        self.assertEqual(drift()["details"], ["tests/test_calc.py: tests 1 -> 0"])
        self.p.write("docs/runs/calc/08-implementation-log.md", "# Log\nRetired tests: tests/test_calc.py\n")
        self.assertEqual(drift()["status"], "pass")

    def test_a_retired_path_does_not_excuse_new_skips(self):
        base = self.p.gate("baseline") and json.loads((self.ctx.gdir / "baseline.json").read_text())
        self.p.write("docs/runs/calc/03-detailed-design.md", "## 9. Retired tests\ntests/test_calc.py\n")
        self.p.write("tests/test_calc.py", "import pytest\n" + TESTS.replace("def test", "@pytest.mark.skip\ndef test"))
        got = checks._test_file_drift(self.ctx, base, "be-developer", "P4.test-drift")
        self.assertEqual(got["details"], ["tests/test_calc.py: skip markers 0 -> 1"])

    def test_tool_output_is_skipped_in_a_git_tree_too(self):
        for rel in ("coverage/index.html", "web/.next/cache.bin", "svc/target/debug/app", "htmlcov/index.html",
                    ".nyc_output/x.json", ".turbo/log", ".DS_Store", "calc/.DS_Store", ".coverage", "calc/keep.py"):
            self.p.write(rel, "x")
        files = snap.list_files(self.p.root)  # untracked, as when a .gitignore misses them
        self.assertIn("calc/keep.py", files)
        self.assertEqual([f for f in files if snap.skipped(f)], [])
        self.assertEqual([f for f in files if "coverage" in f or "target" in f or "DS_Store" in f], [])
        # Tracked: names that are always tool output stay out; a tracked `build/` or `target/` may be
        # the project's own source and is kept.
        self.p.write("src/build/steps.py", "x")
        git(self.p.root, "add", "-A")
        files = snap.list_files(self.p.root)
        self.assertIn("src/build/steps.py", files)
        self.assertIn("svc/target/debug/app", files)
        self.assertEqual([f for f in files if ".next" in f or "htmlcov" in f or "DS_Store" in f
                          or ".nyc_output" in f or ".turbo" in f or f.endswith(".coverage")], [])
        self.assertEqual(sorted(k for k in self.ctx.snapshot() if k.startswith("calc/")),
                         ["calc/__init__.py", "calc/core.py", "calc/keep.py"])

    def test_runs_root_follows_the_projects_configuration(self):
        self.assertEqual(checks.runs_root(self.p.root), "docs/runs")
        self.assertEqual(checks.run_dir_globs(self.ctx), ["docs/runs/**", "docs/runs/calc/**"])
        self.p.write(".claude/harness.json", json.dumps({"artifacts": {"run_dir": "work/runs/"}, "loops": {"max_rounds": 3}}))
        self.assertEqual(checks.runs_root(self.p.root), "work/runs")
        ctx = checks.Ctx(self.p.root, "work/runs/feat2", self.ctx.cfg)
        self.assertEqual(checks.run_dir_globs(ctx), ["work/runs/**", "work/runs/feat2/**"])
        # ids of the other runs under the moved root are known project-wide
        self.p.write("work/runs/r1/01-requirements.md", "### REQ-090 — earlier\n")
        self.assertEqual(checks.ids_in_other_runs(ctx, checks.REQ_FILES, "REQ"), {"REQ-090": "work/runs/r1"})


class NoPerTestResults(Base):
    """A runner that leaves no per-test report: the checks that need one say what to configure."""
    def test_p5_names_the_junit_setting(self):
        self.p.gate("baseline")
        self.p.write("docs/runs/calc/01-requirements.md", REQS.replace("FX-001", "n/a — unit tests"))
        self.p.write("docs/runs/calc/04-test-plan.md", "# Test plan\n### TC-001 — add\n- **Verifies:** REQ-001\n"
                     "- **Mode:** automated\n" + "line\n" * 8)
        self.p.write("docs/runs/calc/05-test-report.md", "# Report\n| TC | Result |\n|---|---|\n| TC-001 | pass |\n"
                     + "line\n" * 8)
        self.p.write("tests/fixtures/approved/APPROVED.json", json.dumps({"cases": {"FX-009": {
            "date": "2026-01-01", "files": {}}}}))
        self.p.write("tests/test_fx.py", "def test_fx():\n    \"\"\"TC-001 FX-009\"\"\"\n    assert True\n")
        self.p.dispatch("be-tester", "5")
        self.ctx.cfg["commands"]["test"] = "echo 'ok  example.com/orders 0.01s'"
        res = {r["id"]: r for r in checks.phase5(self.ctx)[0]}
        for cid in ("P5.tc-results", "P5.fixtures-used", "P5.report-honest"):
            self.assertEqual(res[cid]["status"], "unavailable", cid)
            self.assertIn('set "junit"', res[cid]["message"], cid)


class ContextFiles(Base):
    """M2: the handoff's and the code map's rules as route/HANDOFF.md writes them."""
    def result(self, cid):
        return next(r for r in checks.context_files(self.ctx) if r["id"] == cid)

    def test_orchestrator_writing_for_a_dead_agent_has_its_own_section(self):
        self.p.write("docs/runs/calc/handoff.md", "## orchestrator · 4 · stop · t\nState: x\n"
                     "## orchestrator for be-developer #2 · 4 · round 1 · t\nTask: x\n"
                     "## be-developer #1 · 4 · round 1 · t\nTask: y\n")
        self.assertEqual(self.result("CTX.handoff")["status"], "pass")
        self.p.write("docs/runs/calc/handoff.md", self.p.read("docs/runs/calc/handoff.md")
                     + "## orchestrator for be-developer #3 · 4 · round 2 · t\nTask: z\n")
        self.assertEqual(self.result("CTX.handoff")["details"],
                         ["orchestrator for be-developer: 2 sections, keep only the latest"])

    def test_only_tokens_under_a_root_entry_are_paths(self):
        self.p.dispatch("be-developer")
        self.p.write("docs/codemap.md", "# Code map\n## `calc/`\nEntry: `calc/core.py:add` · `core.py` · `Node.js` · "
                     "`input/output` · `lib/` · `/api/sum` · `calc/*.py` · `package.json`\n")
        self.assertEqual(self.result("CTX.codemap")["status"], "pass")
        self.p.write("docs/codemap.md", "# Code map\nEntry: `calc/gone.py:f` · `calc/old/` · `tests/test_calc.py`\n")
        self.assertEqual(self.result("CTX.codemap")["details"], ["calc/gone.py: no such path", "calc/old: no such path"])

    def test_cap_is_per_file_and_module_files_are_checked_the_same_way(self):
        self.p.dispatch("be-developer")
        self.p.write("docs/codemap.md", "# Code map\nModules: `docs/codemap/calc.md`\n" + "x\n" * 150)
        self.p.write("docs/codemap/calc.md", "# calc\nEntry: `calc/core.py:add`\n" + "x\n" * 150)
        self.assertEqual(self.result("CTX.codemap")["status"], "pass")  # 304 lines in all, each file under 200
        self.p.write("docs/codemap/calc.md", "# calc\nEntry: `calc/gone.py`\n" + "x\n" * 199)
        self.assertEqual(self.result("CTX.codemap")["details"],
                         ["docs/codemap/calc.md: calc/gone.py: no such path", "docs/codemap/calc.md: 201 lines, cap 200"])
        self.p.write("docs/codemap.md", "# Code map\nModules: `docs/codemap/api.md`\n")
        (self.p.root / "docs/codemap/calc.md").unlink()
        self.assertEqual(self.result("CTX.codemap")["details"], ["docs/codemap/api.md: no such path"])


class State(Base):
    def state(self, **over):
        self.p.write("docs/runs/calc/state.json", json.dumps(dict(STATE, **over)))
        return checks.state(self.ctx)["status"]

    def test_standard_tier_and_abandoned_status(self):
        self.assertEqual(self.state(tier="standard"), "pass")
        self.assertEqual(self.state(status="abandoned"), "pass")
        self.assertEqual(self.state(tier="medium"), "fail")
        self.assertEqual(self.state(status="dropped"), "fail")


class Dry(Base):
    """`gate.py check`: no project command, no file written, no role snapshot read."""
    def files(self):
        cache = snap.cache_path(self.p.root)
        return sorted(str(f.relative_to(self.p.root)) for f in self.p.root.rglob("*")
                      if f.is_file() and ".git/" not in str(f)) + [cache.read_text() if cache.exists() else ""]

    def test_p4_reads_documents_and_runs_nothing(self):
        self.p.gate("baseline")
        self.p.write("docs/runs/calc/03-detailed-design.md", "# Design\n" + "calc/core.py\n" * 12)
        self.p.write("docs/runs/calc/04-test-plan.md", "# Test plan\n" + "line\n" * 12)
        self.p.dispatch("be-developer")
        self.p.write("calc/extra.py", "X = 1\n")
        self.ctx.cfg["commands"]["build"] = "touch built.flag"
        self.ctx.dry = True
        before = self.files()
        res = {r["id"]: r for r in checks.phase4(self.ctx)[0]}
        self.assertEqual(self.files(), before)
        for cid in ("ROLE.changes", "CMD.build", "CMD.test"):
            self.assertEqual((res[cid]["status"], res[cid]["message"]), ("unavailable", "not run by `check`"), cid)
        self.assertEqual(res["P4.plan-ids"]["status"], "fail")  # what a document says is still read
        self.assertNotIn("ROLE.unplanned", res)

    def test_no_phase_writes_in_a_dry_run(self):
        self.p.write("docs/runs/calc/01-requirements.md", REQS)
        self.p.write("docs/runs/calc/07-acceptance.md", "accepted\n" * 12)
        self.p.dispatch("be-reviewer", "6")
        self.p.dispatch("be-analyst", "1")
        self.ctx.dry = True
        before = self.files()
        for name in ("p1", "p2", "baseline", "p6", "p7"):
            res = {r["id"]: r for r in checks.PHASES[name](self.ctx)[0]}
            self.assertEqual(self.files(), before, name)
        self.assertEqual(checks.mark(self.ctx, "be-developer")[0][0]["status"], "unavailable")
        self.assertEqual(self.files(), before)
        self.assertEqual({r["id"]: r["status"] for r in checks.phase6(self.ctx)[0]}["P6.tree-unchanged"], "unavailable")
        self.assertEqual(checks.control_files(self.ctx)[0]["status"], "pass")
        self.assertEqual(self.files(), before)


if __name__ == "__main__":
    unittest.main()
