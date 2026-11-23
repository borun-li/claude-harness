#!/usr/bin/env python3
"""16.0.0, the backend checks: one run under the runs root, one state schema, a trail per team in
one log, role rules shared by the gates and `land`, and no walk into another checkout.
Run: python3 -m pytest tests/test_checks_v16.py -q"""
import inspect
import json
import pathlib
import shutil
import sys
import tempfile
import unittest

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE))

import test_checks_v10 as v10  # noqa: E402  (the project fixture)
from gatelib import checks, snap, standard  # noqa: E402

RUN = "docs/runs/calc"
STATE = v10.STATE


class Base(unittest.TestCase):
    def setUp(self):
        self.p = v10.Proj()
        self.ctx = self.p.ctx

    def tearDown(self):
        self.p.close()

    def state(self, **over):
        self.p.write(f"{RUN}/state.json", json.dumps({k: v for k, v in dict(STATE, **over).items() if v is not None}))
        return checks.state(self.ctx)


class RunsRoot(Base):
    """§1.1: every run is `<runs root>/<slug>/`; there is no team's run dir."""
    def test_one_root_and_no_team_dirs(self):
        self.assertEqual(checks.runs_root(self.p.root), "docs/runs")
        self.assertEqual(self.ctx.runs_root, "docs/runs")
        for gone in ("RUN_DIRS", "run_dirs", "_other_team"):
            self.assertFalse(hasattr(checks, gone), gone)
        self.assertFalse(hasattr(self.ctx, "run_dirs"))

    def test_root_is_read_from_the_harness_config(self):
        self.p.write(".claude/harness.json", json.dumps({"artifacts": {"run_dir": "/work/runs/"}}))
        self.assertEqual(checks.runs_root(self.p.root), "work/runs")
        self.p.write(".claude/harness.json", json.dumps({"artifacts": {}}))
        self.assertEqual(checks.runs_root(self.p.root), "docs/runs")

    def test_an_earlier_runs_documents_are_no_ones_production_work(self):
        """Dirt in any run under the root does not block the baseline, repeat the suite or count as a
        change under the reviewers."""
        self.p.write("docs/runs/earlier/01-requirements.md", "### REQ-001 — earlier\n")
        self.p.write("docs/runs/earlier/handoff.md", "x\n")
        res = self.p.gate("baseline")
        self.assertEqual(res["BASE.clean-tree"]["status"], "pass", res["BASE.clean-tree"])
        self.p.write(f"{RUN}/06-review-report.md", "# Review\n" + "line\n" * 12)
        self.p.dispatch("be-reviewer", "6")
        self.p.write("docs/runs/earlier/handoff.md", "edited while reviewers read\n")
        res = {r["id"]: r for r in checks.phase6(self.ctx)[0]}
        self.assertEqual(res["P6.tree-unchanged"]["status"], "pass", res["P6.tree-unchanged"])
        self.p.write("calc/core.py", v10.CORE + "\n# edit\n")
        res = {r["id"]: r for r in checks.phase6(self.ctx)[0]}
        self.assertEqual(res["P6.tree-unchanged"]["details"], ["calc/core.py"])

    def test_ids_continue_across_the_runs_under_the_root(self):
        self.p.write("docs/runs/earlier/04-test-plan.md", "### TC-001 — x\n\n### TC-007 — y\n")
        self.p.write("docs/elsewhere/r0/04-test-plan.md", "### TC-050 — not a run\n")
        self.assertEqual(checks.ids_in_other_runs(self.ctx, ("04-test-plan.md",), "TC"),
                         {"TC-001": "docs/runs/earlier", "TC-007": "docs/runs/earlier"})
        res = checks.unique_ids_check(self.ctx, "P4.tc-ids", {"TC-007": {}}, ("04-test-plan.md",), "TC", "be-tester")
        self.assertEqual(res["status"], "fail")
        self.assertIn("continue from TC-008", res["message"])


class State(Base):
    """§1.3: one schema, one validator, for every gate of both teams."""
    def test_scope_and_tier_are_required(self):
        self.assertEqual(self.state()["status"], "pass")
        for key in ("scope", "tier"):
            res = self.state(**{key: None})
            self.assertEqual((res["status"], res["details"]), ("fail", [f"missing key: {key}"]))

    def test_values(self):
        for key, good, bad_ in (("scope", ("backend", "frontend", "cross-stack"), "both"),
                                ("tier", ("small", "standard", "prototype", "full"), "medium"),
                                ("status", ("in_progress", "blocked", "accepted", "abandoned", "prototype_confirmed"),
                                 "done"),
                                ("risk", ("normal", "high"), "medium")):
            for v in good:
                self.assertEqual(self.state(**{key: v})["status"], "pass", (key, v))
            self.assertEqual(self.state(**{key: bad_})["status"], "fail", (key, bad_))

    def test_the_step_says_where_the_run_is_not_the_status(self):
        for old in ("prototyping", "building", "verifying", "fix_capped"):
            self.assertEqual(self.state(status=old)["status"], "fail", old)
        for step in (3, "3b", "fe-build"):
            self.assertEqual(self.state(current_phase=step)["status"], "pass", step)

    def test_design_keys_are_read_only_where_an_interface_is_designed(self):
        bad_design = {"design": "sketch", "design_stops": 5}
        self.assertEqual(self.state(scope="backend", tier="full", **bad_design)["status"], "pass")
        self.assertEqual(self.state(scope="frontend", tier="small", **bad_design)["status"], "pass")
        for scope in ("frontend", "cross-stack"):
            for tier in ("prototype", "full"):
                res = self.state(scope=scope, tier=tier, **bad_design)
                self.assertEqual(res["status"], "fail", (scope, tier))
                self.assertEqual(len(res["details"]), 2, res["details"])
        self.assertEqual(self.state(scope="cross-stack", tier="full", design="new", design_stops=2)["status"], "pass")
        self.assertEqual(self.state(scope="cross-stack", tier="full", design="external", design_stops=0)["status"], "pass")
        self.assertEqual(self.state(scope="cross-stack", tier="full", design="external", design_stops=1)["status"], "fail")

    def test_not_an_object(self):
        self.p.write(f"{RUN}/state.json", "[]")
        self.assertEqual(checks.state(self.ctx)["status"], "fail")


class TrailPerTeam(Base):
    """§1.3: both teams log into one run log; the backend trail reads the backend team's dispatches."""
    def work(self, agent, step):
        self.p.log("dispatch", agent=agent, model="opus", phase=step, note="work")
        self.p.log("return", agent=agent, phase=step, status="ok", note="done")

    def stop(self, name):
        self.p.log("human", stop=name, decision="approved", by="user", note="yes")

    def test_frontend_steps_do_not_collide_with_backend_steps(self):
        self.state(tier="full", scope="cross-stack")
        self.work("fe-ux", "2")             # the frontend's step 2, before the Prototype stop
        self.work("fe-engineer", "3")       # a runnable prototype, before the Plan
        self.stop("Prototype")
        self.work("be-architect", "2")
        self.stop("Plan")
        self.work("be-developer", "4")
        res = checks._log_trail(self.ctx)
        self.assertEqual(res["status"], "pass", res["details"])
        res = {r["id"]: r for r in checks.phase2(self.ctx)[0]}
        self.assertEqual(res["P2.prototype-first"]["status"], "pass", res["P2.prototype-first"])

    def test_backend_order_is_still_held(self):
        self.state(tier="full", scope="cross-stack")
        self.work("be-architect", "2")
        self.work("be-developer", "4")
        self.stop("Prototype")
        self.stop("Plan")
        details = " ".join(checks._log_trail(self.ctx)["details"])
        self.assertIn("before the Prototype was approved", details)
        self.assertIn("before the Plan was approved", details)

    def test_team_of_a_dispatch_follows_the_runs_scope(self):
        self.work("be-analyst", "0")
        self.work("fe-engineer", "3")
        events = checks._events(self.ctx)
        team = lambda t: [e["agent"] for e in checks._team_dispatches(self.ctx, events, t)]
        self.assertEqual((team("be"), team("fe")), (["be-analyst"], ["fe-engineer"]))
        self.state(scope="frontend")
        self.assertEqual((team("be"), team("fe")), ([], ["be-analyst", "fe-engineer"]))

    def test_an_unreturned_dispatch_of_either_team_is_everyones_problem(self):
        self.state(scope="cross-stack")
        self.stop("Plan")
        self.p.log("dispatch", agent="fe-ui", model="opus", phase="2", note="never returns")
        self.assertIn("fe-ui: 1 dispatch(es) never returned", checks._log_trail(self.ctx)["details"])


class OneOfEverything(Base):
    """§1.4: one baseline and one demo per run."""
    def test_demo_is_the_runs_own(self):
        self.assertEqual(list(inspect.signature(checks.demo).parameters), ["ctx"])
        res = checks.demo(self.ctx)
        self.assertEqual((res["id"], res["status"]), ("DEMO", "fail"))

    def test_no_baseline_names_no_team(self):
        with self.assertRaises(v10.ConfigError) as e:
            checks._baseline(self.ctx)
        self.assertIn("before the run's first code writer", str(e.exception))
        self.assertNotIn("Phase 4", str(e.exception))

    def test_second_baseline_after_work_is_refused_whichever_team_worked(self):
        self.p.gate("baseline")
        self.p.dispatch("fe-engineer", "3")
        with self.assertRaises(v10.ConfigError):
            checks.baseline(self.ctx)
        self.ctx.rebaseline = True
        self.assertEqual(checks.baseline(self.ctx)[0][0]["id"], "BASE.clean-tree")


class RolePaths(Base):
    """§3.5: `land` asks the same judgement the ROLE.* checks make, on one writer's exact changes."""
    def setUp(self):
        super().setUp()
        self.p.write(f"{RUN}/03-detailed-design.md", "# Design\ncalc/core.py\ncalc/parser.py\n")
        self.p.write(f"{RUN}/03-queue.md", "### Q-001\n- **Files:** web/cart.tsx\n")
        self.p.write("server.log", "x\n")

    def bad(self, role, *paths):
        return checks.role_paths(self.ctx, role, list(paths))

    def test_developer(self):
        mine = ("calc/core.py", "calc/parser.py", "tests/test_parser.py", "docs/codemap.md", f"{RUN}/handoff.md",
                "server.log")
        self.assertEqual(self.bad("be-developer", *mine), [])
        self.assertEqual(self.bad("be-developer", *mine, "calc/extra.py", "calc/templates/page.html",
                                  "tests/test_calc.py", ".claude/gates.json"),
                         [".claude/gates.json", "calc/extra.py", "calc/templates/page.html", "tests/test_calc.py"])

    def test_an_existing_test_is_one_the_commit_holds(self):
        self.p.write("tests/test_untracked.py", "def test_x():\n    assert True\n")
        self.assertEqual(self.bad("be-developer", "tests/test_untracked.py", "tests/test_new.py"), [])
        self.assertEqual(self.bad("fe-engineer", "tests/test_calc.py"), ["tests/test_calc.py"])
        self.assertEqual(self.bad("be-tester", "tests/test_calc.py"), [])   # a tester may rewrite a test

    def test_other_roles(self):
        self.assertEqual(self.bad("be-tester", "tests/test_new.py", "docs/notes.md", "calc/core.py"), ["calc/core.py"])
        self.assertEqual(self.bad("fe-tester", "web/cart.test.tsx", "web/cart.tsx"), ["web/cart.tsx"])
        self.assertEqual(self.bad("fe-engineer", "web/cart.tsx", "web/cart.test.tsx", "web/other.tsx"), ["web/other.tsx"])
        self.assertEqual(self.bad("fe-ux", f"{RUN}/01-ux.md", "docs/runs/earlier/01-ux.md", "docs/codemap.md",
                                  "web/cart.tsx"), ["docs/codemap.md", "web/cart.tsx"])
        self.assertEqual(self.bad("be-architect", f"{RUN}/02-architecture.md", "calc/core.py",
                                  "tests/fixtures/candidates/FX-001/input.json"),
                         ["calc/core.py", "tests/fixtures/candidates/FX-001/input.json"])
        self.assertEqual(self.bad("be-analyst", f"{RUN}/01-requirements.md",
                                  "tests/fixtures/candidates/FX-001/input.json",
                                  "tests/fixtures/approved/FX-001/expected.json"),
                         ["tests/fixtures/approved/FX-001/expected.json"])

    def test_the_gates_books_and_control_files_are_no_writers(self):
        books = [f"{RUN}/run-log.jsonl", f"{RUN}/gates/baseline.json", f"{RUN}/gates/logs/x.log", ".claude/harness.json"]
        for role in ("be-developer", "be-tester", "fe-engineer", "fe-ux", "be-analyst", "general-purpose"):
            self.assertEqual(self.bad(role, *books, f"{RUN}/handoff.md"), sorted(books), role)

    def test_same_judgement_as_the_gate(self):
        """One change set, judged in the tree by the role checks and from a list by role_paths."""
        changes = {"calc/core.py": v10.CORE + "\n# edit\n", "calc/extra.py": "X = 1\n",
                   "calc/static/app.css": "a{}\n", "tests/test_calc.py": v10.TESTS + "\n# edit\n",
                   "tests/test_new.py": "def test_new():\n    assert True\n", ".claude/gates.json": "{}\n",
                   "docs/notes.md": "x\n"}
        before = self.p.read(".claude/gates.json")
        for role in ("be-developer", "be-tester", "fe-engineer", "fe-ui", "be-architect"):
            with self.subTest(role=role):
                self.p.close()
                self.p = v10.Proj()
                self.ctx = self.p.ctx
                self.p.write(f"{RUN}/03-detailed-design.md", "# Design\ncalc/core.py\n")
                self.p.dispatch(role)
                for rel, text in changes.items():
                    self.p.write(rel, text)
                at_gate = sorted({d for r in self.p.roles().values() if r["status"] == "fail" for d in r["details"]})
                self.p.write(".claude/gates.json", before)  # the gate config the judgement itself runs under
                self.assertEqual(checks.role_paths(self.ctx, role, list(changes)), at_gate)
                self.assertTrue(at_gate)


class Forgive(Base):
    """§3.5: paths merged from a worktree are not charged to the writer whose mark is in the tree."""
    def test_landed_paths_leave_the_marks_of_writers(self):
        self.p.dispatch("be-tester")
        self.p.write("calc/core.py", v10.CORE + "\n# merged from a worktree\n")
        self.p.write("calc/new.py", "X = 1\n")
        (self.p.root / "calc/__init__.py").unlink()
        landed = ["calc/core.py", "calc/new.py", "calc/__init__.py"]
        self.assertEqual(sorted(self.p.roles()["ROLE.tester-scope"]["details"]), sorted(landed))
        (self.ctx.gdir / checks.ROLE_OPEN).unlink()   # what the failing evaluation recorded
        checks.forgive(self.ctx, landed)
        self.assertEqual(self.p.roles()["ROLE.tester-scope"]["status"], "pass")
        mark = checks._load_mark(self.ctx, "be-tester")
        self.assertEqual(mark["snapshot"]["calc/new.py"], snap.file_sha(self.p.root / "calc/new.py"))
        self.assertNotIn("calc/__init__.py", mark["snapshot"])
        self.assertEqual(mark["role"], "be-tester")
        # what the tester changes after that is its own again
        self.p.write("calc/core.py", v10.CORE + "\n# the tester's edit\n")
        self.assertEqual(self.p.roles()["ROLE.tester-scope"]["details"], ["calc/core.py"])

    def test_other_paths_stay_charged(self):
        self.p.dispatch("be-tester")
        self.p.write("calc/core.py", v10.CORE + "\n# merged\n")
        self.p.write("calc/sneaked.py", "X = 1\n")
        checks.forgive(self.ctx, ["calc/core.py"])
        self.assertEqual(self.p.roles()["ROLE.tester-scope"]["details"], ["calc/sneaked.py"])

    def test_a_merge_under_the_reviewers_is_still_a_change(self):
        self.p.write(f"{RUN}/06-review-report.md", "# Review\n" + "line\n" * 12)
        self.p.dispatch("be-reviewer", "6")
        self.p.write("calc/core.py", v10.CORE + "\n# merged while they read\n")
        checks.forgive(self.ctx, ["calc/core.py"])
        res = {r["id"]: r for r in checks.phase6(self.ctx)[0]}
        self.assertEqual(res["P6.tree-unchanged"]["details"], ["calc/core.py"])

    def test_what_no_snapshot_holds_is_not_put_into_one(self):
        self.p.dispatch("be-tester")
        for rel in (f"{RUN}/gates/p4-latest.json", "server.log", "node_modules/x/index.js"):
            self.p.write(rel, "x\n")
        checks.forgive(self.ctx, [f"{RUN}/gates/p4-latest.json", "server.log", "node_modules/x/index.js"])
        held = checks._load_mark(self.ctx, "be-tester")["snapshot"]
        self.assertEqual([k for k in held if "gates/" in k or k.endswith(".log") or "node_modules" in k], [])
        self.assertEqual(self.p.roles()["ROLE.tester-scope"]["status"], "pass")

    def test_no_marks_is_fine(self):
        checks.forgive(self.ctx, ["calc/core.py"])
        self.assertEqual(list(self.ctx.gdir.glob("snap-*.json")), [])


class OneWriterInTheTree(Base):
    """§3.6: a mark is an in-tree writer's; nobody shares its charge."""
    def test_the_latest_marked_writer_is_judged_alone(self):
        self.p.out("be-developer")
        self.p.out("be-tester")          # logged by hand over the first: still no shared charge
        self.p.write("calc/core.py", v10.CORE + "\n# edit\n")
        self.p.back("be-developer")
        self.p.back("be-tester")
        res = self.p.roles()
        self.assertNotIn("ROLE.shared", res)
        self.assertEqual((res["ROLE.tester-scope"]["status"], res["ROLE.tester-scope"]["owner"]), ("fail", "be-tester"))
        for gone in ("_out_together", "_shared_check", "_intervals", "_may_change"):
            self.assertFalse(hasattr(checks, gone), gone)

    def test_a_run_whose_writers_all_worked_in_worktrees_has_no_mark_to_read(self):
        with self.assertRaises(v10.ConfigError):   # no writer at all: a gate run too early
            checks.role_checks(self.ctx)
        self.p.log("dispatch", agent="be-developer", model="opus", phase="4", note="isolated", isolated=True)
        self.p.log("return", agent="be-developer", phase="4", status="ok", note="done")
        res, changed = checks.role_checks(self.ctx)
        self.assertEqual([(r["id"], r["status"]) for r in res], [("ROLE.changes", "pass")])
        self.assertEqual(changed, [])
        self.p.log("dispatch", agent="be-tester", model="opus", phase="5", note="in the tree, hook did not fire")
        with self.assertRaises(v10.ConfigError) as e:
            checks.role_checks(self.ctx)
        self.assertIn("dispatch hook", str(e.exception))

    def test_another_runs_files_are_not_charged_to_a_role_of_this_run(self):
        self.p.dispatch("fe-ui", "2")
        self.p.write("docs/runs/earlier/02-ui.md", "an earlier run's document\n")
        self.p.write(f"{RUN}/02-ui.md", "this run's\n")
        res, changed = checks.role_checks(self.ctx)
        self.assertEqual({r["id"]: r["status"] for r in res}["ROLE.designer-scope"], "pass")
        self.assertNotIn("docs/runs/earlier/02-ui.md", changed)
        self.assertIn(f"{RUN}/02-ui.md", changed)

    def test_fixtures_locked_while_a_frontend_role_is_out_are_not_its_change(self):
        self.p.write("tests/fixtures/candidates/FX-001/input.json", "{}")
        self.p.dispatch("fe-ux", "1")
        shutil.move(str(self.p.root / "tests/fixtures/candidates/FX-001"), str(self.p.root / "tests/fixtures/approved/FX-001"))
        self.p.write("tests/fixtures/approved/APPROVED.json", "{}")
        self.assertEqual(self.p.roles()["ROLE.designer-scope"]["status"], "pass")
        self.p.write("calc/core.py", v10.CORE + "\n# edit\n")
        self.assertEqual(self.p.roles()["ROLE.designer-scope"]["details"], ["calc/core.py"])

    def test_code_map_is_owed_by_the_last_code_reader_dispatched_marked_or_not(self):
        owner = lambda: next(r for r in checks.context_files(self.ctx) if r["id"] == "CTX.codemap")
        self.assertEqual(owner()["status"], "unavailable")
        self.p.log("dispatch", agent="fe-engineer", model="opus", phase="3", note="in a worktree: no mark")
        self.p.write("docs/codemap.md", "# Code map\nEntry: `calc/gone.py`\n")
        self.assertEqual((owner()["status"], owner()["owner"]), ("fail", "fe-engineer"))


class Worktrees(Base):
    """§3.6: `.claude/worktrees/` holds other checkouts of the project; no snapshot or walk enters it."""
    INSIDE = ".claude/worktrees/agent-a1/calc/core.py"

    def test_untracked_copy(self):
        self.p.write(self.INSIDE, v10.CORE)
        self.p.write(".claude/worktrees/agent-a1/tests/test_calc.py", v10.TESTS)
        self.p.write(".claude/notes.txt", "x")
        self.assertEqual([f for f in snap.list_files(self.p.root) if "worktrees" in f], [])
        self.assertIn(".claude/notes.txt", snap.list_files(self.p.root))
        self.assertEqual([f for f in self.ctx.snapshot() if "worktrees" in f], [])
        self.assertEqual(snap.dirty_paths(self.p.root), [".claude/notes.txt"])
        res = self.p.gate("baseline")
        self.assertEqual(res["BASE.clean-tree"]["status"], "pass")
        self.assertEqual([f for f in json.loads((self.ctx.gdir / "baseline.json").read_text())["test_files"]
                          if "worktrees" in f], [])

    def test_tracked_by_mistake(self):
        self.p.write(self.INSIDE, v10.CORE)
        v10.git(self.p.root, "add", "-f", self.INSIDE)
        self.assertEqual([f for f in snap.list_files(self.p.root) if "worktrees" in f], [])
        self.assertEqual(snap.dirty_paths(self.p.root), [])

    def test_a_real_worktree(self):
        r = v10.git(self.p.root, "worktree", "add", "-q", "-b", "worktree-agent-a1", ".claude/worktrees/agent-a1")
        self.assertEqual(r.returncode, 0, r.stderr)
        (self.p.root / ".claude/worktrees/agent-a1/calc/extra.py").write_text("X = 1\n")
        self.p.dispatch("be-tester")
        (self.p.root / ".claude/worktrees/agent-a1/calc/core.py").write_text(v10.CORE + "\n# its own edit\n")
        self.assertEqual([f for f in self.ctx.snapshot() if "worktrees" in f], [])
        self.assertEqual(self.p.roles()["ROLE.tester-scope"]["status"], "pass")
        self.assertEqual(snap.dirty_paths(self.p.root), [f"{RUN}/gates/snap-be-tester.json", f"{RUN}/run-log.jsonl"])

    def test_outside_git(self):
        root = pathlib.Path(tempfile.mkdtemp(prefix="gatev16-"))
        try:
            for rel in ("calc/core.py", self.INSIDE, "pkg/.claude/worktrees/keep.py"):
                (root / rel).parent.mkdir(parents=True, exist_ok=True)
                (root / rel).write_text("x\n")
            self.assertEqual(snap.list_files(root), ["calc/core.py", "pkg/.claude/worktrees/keep.py"])
        finally:
            shutil.rmtree(root, ignore_errors=True)


class Config(unittest.TestCase):
    """§3.7: the gates config says which documents several writers add to."""
    def test_worktree_defaults(self):
        cfg = json.loads((HERE.parent / "config.json").read_text())
        self.assertEqual(cfg["worktree"]["union_globs"], ["<run>/**", "docs/codemap.md", "docs/codemap/**"])


class StandardEngineer(Base):
    """A Standard change is one run: who a build failure goes back to follows the run's scope."""
    def test_by_scope_until_an_engineer_is_dispatched(self):
        for scope, want in (("backend", "be-developer"), ("frontend", "fe-engineer"), ("cross-stack", "be-developer")):
            self.state(tier="standard", scope=scope)
            self.assertEqual(standard._engineer(self.ctx), want, scope)
        self.p.log("dispatch", agent="fe-engineer", model="opus", phase="2", note="build")
        self.assertEqual(standard._engineer(self.ctx), "fe-engineer")
        self.p.log("dispatch", agent="be-developer", model="opus", phase="2", note="build")
        self.assertEqual(standard._engineer(self.ctx), "be-developer")


if __name__ == "__main__":
    unittest.main()
