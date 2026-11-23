#!/usr/bin/env python3
"""Harness 16.0, one run: the frontend gates read the run's own requirements, log and demo. In a
cross-stack run this team's documents sit beside the Backend team's, in one directory with one log.
Run: python3 -m pytest tests/test_frontend_v16.py -q"""
import json
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from test_frontend_gates import FILL, QUEUE, REQS, RUN, TERMINAL_PLAN, VERIFY, FrontBase  # noqa: E402
from test_frontend_v15 import ctx_of  # noqa: E402
from test_gates import ARCH, DESIGN, GATE  # noqa: E402

sys.path.insert(0, str(GATE.parent))
from gatelib import frontend, registry  # noqa: E402

REQ_2 = """
### REQ-002 — Bulk upload [interface]
- **Cut:** above
- **Behaviour:** many files at once
- **Accept:** Given ten files, When uploaded, Then each shows its result
- **Source:** "bulk"
- **Fixtures:** n/a — no stored data
"""


class CrossStack(FrontBase):
    """Both teams' documents in the one run dir: the requirements are the Backend team's 01-requirements.md."""
    DESIGN_GATES = ("fe-ux", "fe-ui", "fe-queue", "fe-plan")  # no 00-requirements.md: no fe-product

    def setUp(self):
        super().setUp()
        (self.p.fe / "00-requirements.md").rename(self.p.fe / "01-requirements.md")
        self.set_state(scope="cross-stack")
        self.p.write(f"{RUN}/02-architecture.md", ARCH)
        self.p.write(f"{RUN}/03-detailed-design.md", DESIGN)
        self.p.write(f"{RUN}/03-queue.md", QUEUE + FILL)

    def test_design_gates_read_the_runs_requirements(self):
        for g in self.DESIGN_GATES:
            code, out, _ = self.fe(g)
            self.assertEqual(code, 0, f"{g}: {out}")
        self.p.write(f"{RUN}/01-requirements.md", REQS + REQ_2 + FILL)
        hit = next(c for c in self.fe("fe-ux")[2]["checks"] if c["id"] == "FE1.coverage")
        self.assertEqual((hit["status"], hit["details"]), ("fail", ["REQ-002"]))
        self.assertIn("01-requirements.md", hit["message"])

    def test_each_team_writes_its_own_sheet_and_matrix(self):
        for name in ("plan-review.md", "traceability.md"):
            self.p.write(f"{RUN}/gates/{name}", "the Backend team's\n")
        for g in ("fe-ux", "fe-ui", "fe-queue"):
            self.fe(g)
        code, out, rep = self.fe("fe-plan")
        self.assertEqual(code, 0, out)
        self.assertEqual(rep["data"]["review_sheet"], f"{RUN}/gates/fe-plan-review.md")
        self.assertIn("| Q-001 | P1 |", (self.p.fe / "gates" / "fe-plan-review.md").read_text())
        frontend._matrix(ctx_of(self.p.root), {"Q-001": "done"})
        self.assertIn("| REQ-001 |", (self.p.fe / "gates" / "fe-traceability.md").read_text())
        for name in ("plan-review.md", "traceability.md"):
            self.assertEqual((self.p.fe / "gates" / name).read_text(), "the Backend team's\n")

    def test_a_cross_stack_run_is_accepted_on_its_own_log_and_demo(self):
        # The Backend team's step 3, before any design stop: not this team's build (LOG.trail).
        self.fe_dispatch("be-developer", step="3")
        self.to_build()
        self.p.write("web/notice.html", '<p class="warn">Already uploaded</p>')
        code, out, _ = self.fe("fe-build")
        self.assertEqual(code, 0, out)
        self.p.write(f"{RUN}/03-queue.md",
                     self.p.read(f"{RUN}/03-queue.md").replace("**Status:** queued", "**Status:** done"))
        self.p.write(f"{RUN}/capture-plan.json", json.dumps(TERMINAL_PLAN))
        assert self.capture()[0] == 0
        self.fe_dispatch("fe-tester", step="4")
        self.p.write(f"{RUN}/04-verification.md", VERIFY + FILL)
        code, out, _ = self.fe("fe-verify")
        self.assertEqual(code, 0, out)
        code, out, _ = self.review_ok()
        self.assertEqual(code, 0, out)
        assert self.fe_demo("after")[0] == 0
        code, out, rep = self.fe("fe-accept")
        self.assertEqual(code, 0, out)
        self.assertEqual((self.st(rep, "LOG.trail"), self.st(rep, "FEA.matrix")), ("pass", "pass"))
        demo = next(c for c in rep["checks"] if c["id"] == "DEMO")
        self.assertEqual(demo["status"], "pass")
        self.assertIn(RUN, demo["message"])


class Teams(FrontBase):
    """One log for both teams: the order of this team's steps is read from its own dispatches."""
    def stops(self):
        for stop in ("UX", "UI", "Prototype"):
            self.fe_log("human", "--stop", stop, "--decision", "approved", "--by", "user", "--note", "ok")

    def trail(self):
        return self.details(self.fe("fe-accept")[2], "LOG.trail")

    def test_the_builder_of_a_frontend_only_run_is_this_teams(self):
        self.fe_dispatch("be-developer", step="3")
        self.stops()
        self.assertIn("before the UI was approved", self.trail())
        self.set_state(scope="cross-stack")  # the same dispatch is the Backend team's step 3
        self.assertEqual(self.trail(), "")

    def test_a_backend_builder_does_not_restart_this_teams_review(self):
        for agent in ("fe-engineer", "fe-review-experience", "fe-review-integration", "fe-reviewer", "be-developer"):
            self.fe_log("dispatch", "--agent", agent, "--model", "opus", "--step", "4", "--note", "work")
            self.fe_log("return", "--agent", agent, "--step", "4", "--status", "ok", "--note", "done")
        ctx = ctx_of(self.p.root)
        self.assertEqual(frontend._review_round(ctx), ([], False))  # frontend-only: be-developer builds for this team
        self.set_state(scope="cross-stack")
        self.assertEqual(frontend._review_round(ctx), (["fe-review-experience", "fe-review-integration"], True))


class Requirements(FrontBase):
    def reqs(self):
        return sorted(frontend._reqs(ctx_of(self.p.root))[1])

    def test_a_frontend_only_run_reads_00_requirements(self):
        self.assertEqual(frontend._req_name(ctx_of(self.p.root)), "00-requirements.md")
        self.assertEqual(self.reqs(), ["REQ-001"])
        self.assertEqual(self.st(self.fe("fe-ux")[2], "FE1.coverage"), "pass")

    def test_01_requirements_is_read_when_the_run_has_it(self):
        self.p.write(f"{RUN}/01-requirements.md", REQS + REQ_2 + FILL)
        self.assertEqual(self.reqs(), ["REQ-001", "REQ-002"])
        self.assertEqual(self.details(self.fe("fe-ux")[2], "FE1.coverage"), "REQ-002")

    def test_a_pointer_in_state_json_is_not_followed(self):
        self.p.write("docs/elsewhere/01-requirements.md", REQS.replace("REQ-001", "REQ-009") + FILL)
        self.set_state(requirements="docs/elsewhere/01-requirements.md")
        self.assertEqual(self.reqs(), ["REQ-001"])


class State(FrontBase):
    def state(self):
        return next(c for c in self.fe("fe-ux")[2]["checks"] if c["id"] == "ALL.state")

    def test_design_values_are_checked_at_this_teams_gates(self):
        self.assertEqual(self.state()["status"], "pass")
        self.set_state(design_stops=3)
        self.assertIn("design_stops must be 1 or 2", " ".join(self.state()["details"]))
        self.set_state(design="external", design_stops=1)
        self.assertIn("design_stops must be 0", " ".join(self.state()["details"]))
        self.set_state(design="borrowed", design_stops=1)
        self.assertIn("design must be new|external|reused", " ".join(self.state()["details"]))


class RegistryPath(FrontBase):
    def test_the_registry_is_the_projects_not_a_teams(self):
        ctx = ctx_of(self.p.root)
        self.assertEqual(registry.path(ctx), ctx.project / "docs" / "observables.json")
        ctx.cfg["observables_registry"] = "design/approved.json"
        self.assertEqual(registry.path(ctx), ctx.project / "design" / "approved.json")


if __name__ == "__main__":
    unittest.main(verbosity=1)
