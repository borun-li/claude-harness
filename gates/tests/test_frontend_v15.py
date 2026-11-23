#!/usr/bin/env python3
"""Frontend 15.0 / backend 10.0: parsers that accept correct documents, capture plans that cover what the
documents promise, runners without per-test results, and the review, demo and build rules that changed.
Run: python3 -m pytest tests/test_frontend_v15.py -q"""
import json
import pathlib
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from test_frontend_gates import FILL, QUEUE, REVIEW, RUN, TERMINAL_PLAN, UI, UX, VERIFY, FrontBase  # noqa: E402
from test_gates import GATE, PY, Base  # noqa: E402

sys.path.insert(0, str(GATE.parent))
from gatelib import capture, checks, docs, frontend, profile, runner  # noqa: E402

STATES = ("loading", "empty", "success", "error")


def ctx_of(root, run=RUN):
    """A gate context on a test project, for checks called in process."""
    cfg = json.loads((GATE.parent / "config.json").read_text())
    cfg.update({k: v for k, v in json.loads((root / ".claude" / "gates.json").read_text()).items()
                if not k.startswith("_")})
    return checks.Ctx(root, run, cfg)


def tree(root):
    return sorted(p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file() and ".git/" not in p.as_posix())


# ---------- M2: correct documents are read as written ----------

class Parsers(unittest.TestCase):
    def test_report_verdict_is_read_through_case_emphasis_and_marks(self):
        rows = "\n".join(f"| TC-{n:03d} | REQ-001 | {cell} | pytest |" for n, cell in enumerate(
            ["pass", "Passed", "**PASS**", "`fail`", "✅ pass", "❌ FAILED", "⚠️ blocked", "✓ passed", "✗ fail"], 1))
        got = docs.report_results("| TC | REQ | Result | Evidence |\n|---|---|---|---|\n" + rows)
        self.assertEqual([got[f"TC-{n:03d}"] for n in range(1, 10)],
                         ["pass", "pass", "pass", "fail", "pass", "fail", "blocked", "pass", "fail"])

    def test_a_cell_with_two_verdicts_or_other_words_is_no_verdict(self):
        table = "| TC | REQ | Result |\n|---|---|---|\n"
        for cell in ("pass / fail", "pass or blocked", "not passed", "passing", "see log"):
            self.assertEqual(docs.report_results(table + f"| TC-001 | REQ-001 | {cell} |"), {}, cell)

    def test_mode_is_read_from_its_field(self):
        tc = "### TC-001 — export\n- **Verifies:** REQ-001\n- **Level:** e2e   **Mode:** {mode}\n- **Steps:** {steps}\n"
        mode = lambda **kw: docs.testcases(tc.format(**kw))["TC-001"]["mode"]
        self.assertEqual(mode(mode="manual", steps="was automated before the redesign"), "manual")
        self.assertEqual(mode(mode="automated", steps="replaces the manual check"), "automated")
        self.assertEqual(mode(mode="manual (not automated: needs a real printer)", steps="print"), "manual")
        # no Mode field: the block is read, as before
        self.assertEqual(docs.testcases("### TC-001 — x\n- **Verifies:** REQ-001\nautomated by pytest\n")["TC-001"]["mode"],
                         "automated")

    def test_a_path_a_url_and_a_code_span_are_one_word_each(self):
        self.assertEqual(docs.words("see docs/runs/dup/evidence/verify-1/Q-3-1440.png now"), 3)
        self.assertEqual(docs.words("open https://example.com/a/b?c=d first"), 3)
        self.assertEqual(docs.words("run `gate.py capture --round 1` then"), 3)
        self.assertEqual(docs.words("plain five words right here"), 5)
        self.assertEqual(docs.words("```\ncode is not counted\n```\nafter it"), 2)
        long = " ".join(["word"] * 45) + " " + " ".join(["docs/runs/dup/evidence/verify-1/Q-3-1440.png"] * 3)
        self.assertEqual(docs.prose_units(long)[0][1], 48)

    def test_figma_node_id_forms(self):
        url = "https://www.figma.com/design/AbCdEfGhIjKlMnOpQrStUv/Upload?node-id="
        for node in ("12-34", "12:34", "12%3A34", "12%3a34"):
            self.assertTrue(frontend.FIGMA_NODE.search(url + node), node)
        for node in ("", "12", "abc"):
            self.assertFalse(frontend.FIGMA_NODE.search(url + node), node)

    def test_issue_numbers_and_words_are_not_colours(self):
        prose = "Fixes #123 and #456789, from the #decade review; see [states](#add) and PR #12."
        self.assertEqual(frontend._raw_colours(prose), [])

    def test_colour_values_are_still_colours(self):
        self.assertEqual(frontend._raw_colours("Use #FF0000 for errors."), ["#FF0000"])
        self.assertEqual(frontend._raw_colours("white (#fff) on a #cccccc rule"), ["#cccccc", "#fff"])
        self.assertEqual(frontend._raw_colours("The notice is `#123` on `#decade`."), ["#123", "#decade"])
        self.assertEqual(frontend._raw_colours("- border: 1px solid #ccc; background-color: #fafafa"),
                         ["#ccc", "#fafafa"])
        self.assertEqual(frontend._raw_colours("| Ink on Paper | 4.5:1 | #1F2328 on #FFFFFF |"), ["#1F2328", "#FFFFFF"])


class DesignDocs(FrontBase):
    def test_ui_accepts_issue_numbers_and_encoded_node_ids(self):
        ui = UI.replace("?node-id=1-2", "?node-id=1%3A2") + "\nFixes #123, raised in the #decade review.\n"
        self.p.write("docs/runs/dup/02-ui.md", ui + FILL)
        rep = self.fe("fe-ui")[2]
        self.assertEqual((self.st(rep, "FE2.tokens"), self.st(rep, "FE2.frames")), ("pass", "pass"))

    def test_ui_still_refuses_a_colour_outside_the_tables(self):
        self.p.write("docs/runs/dup/02-ui.md", UI + "\nThe notice border is `#123`.\n" + FILL)
        self.assertIn("#123", self.details(self.fe("fe-ui")[2], "FE2.tokens"))

    def test_ux_wireframe_with_an_encoded_node_id(self):
        self.p.write("docs/runs/dup/01-ux.md", UX.replace("?node-id=5-1", "?node-id=5%3A1") + FILL)
        self.assertEqual(self.st(self.fe("fe-ux")[2], "FE1.wireframes"), "pass")


# ---------- shared setup: a built row, captured and judged ----------

FULL_PLAN = {"surface": "terminal", "captures": [
    {"id": f"Q-001-{s}", "row": "Q-001", "state": s, "command": "cat web/notice.html"} for s in STATES]}


class Built(FrontBase):
    def setUp(self):
        super().setUp()
        self.to_build()
        self.p.write("web/notice.html", '<p class="warn">Already uploaded</p>')

    def mark_reviewers(self):
        self.mark("fe-reviewer")

    def dispatch(self, agent, step="4"):
        self.fe_log("dispatch", "--agent", agent, "--model", "opus", "--step", step, "--note", "review")
        self.fe_log("return", "--agent", agent, "--step", step, "--status", "ok", "--note", "done")

    def verified(self, extra=""):
        assert self.fe("fe-build")[0] == 0
        self.p.write("docs/runs/dup/03-queue.md",
                     self.p.read("docs/runs/dup/03-queue.md").replace("**Status:** queued", "**Status:** done"))
        self.p.write("docs/runs/dup/capture-plan.json", json.dumps(TERMINAL_PLAN))
        assert self.capture()[0] == 0
        self.fe_dispatch("fe-tester", step="4")
        self.p.write("docs/runs/dup/04-verification.md", VERIFY + extra + FILL)

    def set_cmd(self, **cmds):
        g = json.loads(self.p.read(".claude/gates.json"))
        g["commands"].update(cmds)
        self.p.write(".claude/gates.json", json.dumps(g))


class Evidence(Built):
    def test_a_file_named_in_a_sentence_is_not_evidence(self):
        self.verified("\nThe dependency is listed in `package.json`; styles come from `web/notice.html`.\n")
        rep = self.fe("fe-verify")[2]
        self.assertEqual(self.st(rep, "FE4.evidence"), "pass", self.details(rep, "FE4.evidence"))

    def test_a_cited_capture_must_exist(self):
        self.verified("\nAlso `Q-001-gone@80x24.stdout`, `evidence/verify-1/missing.png` and `FRAME-009.png`.\n")
        d = self.details(self.fe("fe-verify")[2], "FE4.evidence")
        for name in ("Q-001-gone@80x24.stdout", "evidence/verify-1/missing.png", "FRAME-009.png"):
            self.assertIn(name, d)

    def test_evidence_cited_by_path_or_frame_is_found(self):
        self.verified("\nSee `evidence/verify-1/Q-001-dup@80x24.stderr` beside `FRAME-001.png`.\n")
        self.assertEqual(self.st(self.fe("fe-verify")[2], "FE4.evidence"), "pass")


# ---------- M10: the capture plan covers every row, state and size ----------

class CapturePlan(Built):
    def plan(self, plan):
        self.p.write("docs/runs/dup/capture-plan.json", json.dumps(plan))
        code, _, rep = self.fe("fe-capture-plan")
        return code, self.details(rep, "FE4.capture-plan")

    def web(self, widths, states=STATES):
        return {"surface": "web", "base_url": "http://127.0.0.1:1",
                "sizes": [{"name": str(w), "width": w, "height": 900} for w in widths],
                "captures": [{"id": f"c-{s}", "row": "Q-001", "state": s, "url": "/"} for s in states]}

    def test_terminal_plan_needs_every_state_of_a_row(self):
        code, d = self.plan(TERMINAL_PLAN)  # one capture, state "duplicate"
        self.assertEqual(code, 1)
        self.assertIn("Q-001: no capture for empty, error, loading, success", d)
        self.assertEqual(self.plan(FULL_PLAN)[0], 0)

    def test_web_plan_needs_every_state_at_every_configured_width(self):
        code, d = self.plan(self.web((1440, 375), ("loading", "empty", "success")))
        self.assertEqual(code, 1)
        self.assertIn("sizes: none 768 wide", d)
        self.assertIn("Q-001: no capture for empty@768, error, loading@768, success@768", d)
        self.assertEqual(self.plan(self.web((1440, 768, 375)))[0], 0)

    def test_viewports_come_from_the_projects_harness_config(self):
        self.p.write(".claude/harness.json", json.dumps({"viewports": [1280]}))
        self.assertEqual(self.plan(self.web((1280,)))[0], 0)
        self.assertIn("none 1280 wide", self.plan(self.web((1440, 768, 375)))[1])

    def test_a_state_may_carry_more_words(self):
        plan = json.loads(json.dumps(FULL_PLAN))
        plan["captures"][3]["state"] = "error — duplicate upload"
        self.assertEqual(self.plan(plan)[0], 0)

    def test_source_that_matches_no_file_fails(self):
        code, d = self.plan({**FULL_PLAN, "source": ["wbe/**"]})
        self.assertEqual(code, 1)
        self.assertIn("matches no file", d)
        self.assertEqual(self.plan({**FULL_PLAN, "source": ["web/**"]})[0], 0)


class TerminalExit(Built):
    def entry(self, **capture_fields):
        self.p.write("docs/runs/dup/capture-plan.json", json.dumps({"surface": "terminal", "captures": [
            {"id": "q", "row": "Q-001", "state": "error", "command": "echo refused; exit 3", **capture_fields}]}))
        n = str(len(list((self.p.fe / "evidence").glob("verify-*"))) + 1)
        code, _ = self.capture(n)
        return code, json.loads((self.p.fe / "evidence" / f"verify-{n}" / "manifest.json").read_text())["entries"][0]

    def test_non_zero_exit_fails_the_capture_unless_expected(self):
        code, e = self.entry()
        self.assertEqual((code, e["exit"], e["ok"]), (1, 3, False))
        self.assertIn("exit 3, expected 0", e["error"])
        code, e = self.entry(expect_exit=3)
        self.assertEqual((code, e["exit"], e["ok"]), (0, 3, True))
        code, e = self.entry(expect_exit=2)
        self.assertEqual((code, e["ok"]), (1, False))

    def test_a_failed_capture_fails_the_evidence(self):
        assert self.fe("fe-build")[0] == 0
        self.entry()
        self.fe_dispatch("fe-tester", step="4")
        self.p.write("docs/runs/dup/04-verification.md", VERIFY + FILL)
        self.assertIn("exit 3, expected 0", self.details(self.fe("fe-verify")[2], "FE4.capture"))


# ---------- review: S6, S7, the sole reviewer ----------

class Review(Built):
    def setUp(self):
        super().setUp()
        self.verified()

    def review(self, text=REVIEW):
        self.p.write("docs/runs/dup/05-review.md", text + FILL)
        return self.fe("fe-review")

    def test_a_change_made_during_review_outlives_a_new_mark(self):
        """S6: re-dispatching the reviewers takes a new mark; the change they made is still there."""
        self.mark_reviewers()
        self.p.write("web/notice.html", "<p>reviewer fix</p>")
        self.assertEqual(self.st(self.review()[2], "FE4.tree-unchanged"), "fail")
        self.mark_reviewers()
        rep = self.review()[2]
        self.assertEqual(self.st(rep, "FE4.tree-unchanged"), "fail")
        self.assertIn("web/notice.html", self.details(rep, "FE4.tree-unchanged"))
        self.p.write("web/notice.html", '<p class="warn">Already uploaded</p>')
        self.assertEqual(self.st(self.review()[2], "FE4.tree-unchanged"), "pass")

    def open_blocking(self, status):
        self.mark_reviewers()
        return self.review(REVIEW.replace("| FND-001 | minor |", "| FND-001 | major |").replace(
            "- **Status:** deferred", f"- **Status:** {status}"))[2]["data"]["open_blocking"]

    def test_not_fixed_is_open(self):
        """S7: only a status that starts with a closing word closes a finding."""
        for status in ("not fixed — still shows the old notice", "unresolved", "open | fixed in round n | accepted as-is"):
            self.assertEqual(self.open_blocking(status), ["FND-001"], status)
        for status in ("fixed in round 2", "accepted as-is (user, 2026-11-20)", "Resolved"):
            self.assertEqual(self.open_blocking(status), [], status)

    SOLE = REVIEW.replace("- Panelists run: fe-review-experience — accessibility and integration not needed "
                          "(PLAYBOOK §6)\n", "- Round: 1\n")

    def test_one_panelist_needs_no_coordinator(self):
        """The orchestrator files the sole panelist's review as 05-review.md; no fe-reviewer runs."""
        self.mark_reviewers()
        self.dispatch("fe-review-experience")
        code, out, rep = self.review(self.SOLE)
        self.assertEqual(code, 0, out)
        self.assertEqual(self.st(rep, "FE4.panel"), "pass")
        self.assertEqual(next(c for c in rep["checks"] if c["id"] == "FE4.findings")["owner"], "fe-review-experience")

    def test_the_sole_panelist_still_has_to_be_the_panel_the_risk_needs(self):
        self.set_state(risk="high")
        self.mark_reviewers()
        self.dispatch("fe-review-experience")
        self.assertIn("fe-review-accessibility", self.details(self.review(self.SOLE)[2], "FE4.panel"))

    def test_two_panelists_need_the_coordinator(self):
        self.mark_reviewers()
        self.dispatch("fe-review-experience")
        self.dispatch("fe-review-integration")
        rep = self.review()[2]
        self.assertEqual(self.st(rep, "FE4.panel"), "fail")
        self.assertIn("no fe-reviewer", next(c for c in rep["checks"] if c["id"] == "FE4.panel")["message"])
        self.dispatch("fe-reviewer")
        rep = self.review()[2]
        self.assertEqual(self.st(rep, "FE4.panel"), "pass")
        self.assertEqual(next(c for c in rep["checks"] if c["id"] == "FE4.findings")["owner"], "fe-reviewer")

    def test_the_panel_is_the_one_that_reviewed_this_build(self):
        """An earlier round's panel does not count against a later round's single re-check."""
        self.mark_reviewers()
        self.dispatch("fe-review-experience")
        self.dispatch("fe-review-integration")
        self.dispatch("fe-reviewer")
        self.fe_dispatch("fe-engineer", step="3")
        self.mark_reviewers()
        self.dispatch("fe-review-experience")
        self.assertEqual(self.st(self.review(self.SOLE)[2], "FE4.panel"), "pass")

    def test_accept_with_a_sole_reviewer(self):
        assert self.fe("fe-verify")[0] == 0
        self.mark_reviewers()
        self.dispatch("fe-review-experience")
        assert self.review(self.SOLE)[0] == 0
        assert self.fe_demo("after")[0] == 0
        code, out, rep = self.fe("fe-accept")
        self.assertEqual(code, 0, out)
        self.assertEqual(self.st(rep, "LOG.trail"), "pass")


# ---------- fe-build: the frontend's own suite, who owns a secret ----------

class Build(Built):
    def test_fe_build_runs_fe_test_and_fe_verify_the_whole_suite(self):
        self.p.write("tests/test_fe.py", "def test_notice():\n    assert True\n")
        self.p.write("tests/test_api.py", "def test_api():\n    assert 1 == 2\n")
        rep = self.fe("fe-build")[2]
        self.assertEqual(self.st(rep, "CMD.test"), "fail")  # no fe_test: the whole suite
        self.set_cmd(fe_test=f"{PY} -m pytest -q -p no:cacheprovider tests/test_fe.py")
        rep = self.fe("fe-build")[2]
        self.assertEqual(self.st(rep, "CMD.test"), "pass", self.details(rep, "CMD.test"))
        self.assertIn("tests/test_fe.py", self.details(rep, "CMD.test"))
        self.p.write("docs/runs/dup/capture-plan.json", json.dumps(TERMINAL_PLAN))
        assert self.capture()[0] == 0
        self.fe_dispatch("fe-tester", step="4")
        self.p.write("docs/runs/dup/04-verification.md", VERIFY + FILL)
        self.assertEqual(self.st(self.fe("fe-verify")[2], "CMD.test"), "fail")

    def test_a_secret_found_by_fe_build_is_the_frontend_engineers(self):
        self.p.write("web/notice.html", '<script>const api_key = "abcdefghijklmnop1234"</script>')
        rep = self.fe("fe-build")[2]
        hit = next(c for c in rep["checks"] if c["id"] == "P4.secrets")
        self.assertEqual((hit["status"], hit["owner"]), ("fail", "fe-engineer"))
        self.assertIn("web/notice.html", " ".join(hit["details"]))


# ---------- ctx.dry: `gate.py check` runs nothing and writes nothing ----------

class Dry(Built):
    def ctx(self):
        ctx = ctx_of(self.p.root)
        ctx.dry = True
        return ctx

    def by_id(self, results):
        return {r["id"]: r for r in results}

    def test_no_phase_writes_or_runs_anything(self):
        self.verified()
        assert self.fe("fe-verify")[0] == 0
        self.mark_reviewers()
        self.p.write("docs/runs/dup/05-review.md", REVIEW + FILL)
        self.set_cmd(build="touch built.marker", lint="touch linted.marker", test="touch tested.marker")
        for name in ("fe-plan-review.md", "fe-traceability.md", "tests-cache.json", "role-open.json"):
            (self.p.fe / "gates" / name).unlink(missing_ok=True)
        before = tree(self.p.root)
        seen = {}
        for gate in ("fe-product", "fe-ux", "fe-ui", "fe-queue", "fe-plan", "fe-build", "fe-capture-plan",
                     "fe-verify", "fe-review", "fe-accept"):
            seen[gate] = self.by_id(frontend.PHASES[gate](self.ctx())[0])
        self.assertEqual(tree(self.p.root), before)
        why = checks.DRY
        self.assertEqual([seen["fe-build"][c]["message"] for c in ("CMD.build", "CMD.lint", "CMD.test")], [why] * 3)
        self.assertEqual(seen["fe-verify"]["CMD.test"]["message"], why)
        self.assertEqual(seen["fe-review"]["FE4.tree-unchanged"]["message"], why)
        self.assertEqual(seen["fe-accept"]["FEA.matrix"]["status"], "pass")
        self.assertFalse(any(r["status"] == "fail" for r in seen["fe-plan"].values()), seen["fe-plan"])

    def test_approve_locks_nothing(self):
        lock = self.p.fe / "gates" / "observables-approved.json"
        before = lock.read_text()
        self.p.write("docs/runs/dup/03-queue.md", self.p.read("docs/runs/dup/03-queue.md").replace("amber", "red"))
        res, _ = frontend.approve(self.ctx(), "user")
        self.assertEqual((res[0]["status"], lock.read_text()), ("unavailable", before))


# ---------- S3.5: a goal that preserves behaviour ----------

class PreserveDemo(Base):
    def demo(self):
        return next(c for c in self.p.gate("p7")[2]["checks"] if c["id"] == "DEMO")

    def test_identical_before_and_after_passes_only_for_a_preserve_goal(self):
        self.p.to_p5()
        assert self.p.demo("after")[0] == 0
        (self.p.run / "evidence" / "demo-before" / "D-1@80x24.stdout").write_bytes(
            (self.p.run / "evidence" / "demo-after" / "D-1@80x24.stdout").read_bytes())
        self.assertIn("byte-identical", " ".join(self.demo()["details"]))
        state = json.loads((self.p.run / "state.json").read_text())
        state["goal"]["kind"] = "preserve"
        (self.p.run / "state.json").write_text(json.dumps(state))
        self.assertEqual(self.demo()["status"], "pass")
        shutil.rmtree(self.p.run / "evidence" / "demo-after")  # everything else about DEMO stays
        self.assertIn("no after", " ".join(self.demo()["details"]))


# ---------- M9: runners the gates get no per-test results from ----------

class Runners(unittest.TestCase):
    def setUp(self):
        self.d = pathlib.Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.d, ignore_errors=True)

    def run_tests(self, cmd):
        return runner.run_tests(cmd, self.d, 30, self.d / "log", self.d / "j.xml")

    def test_started_tells_a_red_suite_from_a_command_that_never_ran(self):
        ran = self.run_tests("echo '--- FAIL: TestOrders (0.00s)'; echo 'FAIL'; exit 1")
        self.assertEqual((ran["started"], ran["counts"]), (True, None))
        self.assertFalse(self.run_tests("no-such-test-runner-xyz ./...")["started"])  # exit 127
        self.assertFalse(self.run_tests("exit 1")["started"])  # printed nothing
        self.assertTrue(self.run_tests("echo ok")["started"])

    def test_the_note_names_what_to_configure(self):
        for cmd, tool in (("go test ./...", "gotestsum"), ("cargo test", "cargo2junit"),
                          ("python3 -m unittest discover", "unittest-xml-reporting"),
                          ("npx mocha", "mocha-junit-reporter"), ("bundle exec rspec", "rspec_junit_formatter")):
            note = runner.junit_plan(cmd, self.d, "j.xml")[3]
            self.assertIn('"junit"', note, cmd)
            self.assertIn(tool, note, cmd)
        self.assertIn('"junit"', runner.junit_plan("make test", self.d, "j.xml")[3])

    def test_a_package_script_is_read_for_its_runner(self):
        (self.d / "package.json").write_text(json.dumps({"scripts": {"test": "mocha --recursive"}}))
        self.assertIn("mocha-junit-reporter", runner.junit_plan("npm run test", self.d, "j.xml")[3])

    def test_a_checker_that_ran_has_a_reading_whatever_it_prints(self):
        r = lambda out, code=1, started=True: {"exit": code, "output": out, "started": started}
        self.assertFalse(runner.did_not_run(r("3 offenses detected in 2 files")))
        self.assertFalse(runner.did_not_run(r("", 0)))
        self.assertTrue(runner.did_not_run(r("", 1, started=False)))
        self.assertTrue(runner.did_not_run(r("sh: rubocop: command not found")))
        self.assertTrue(runner.did_not_run(r("Found 1 error in 1 file (errors prevented further checking)", 2)))
        self.assertTrue(runner.did_not_run(r("half a report", 124)))

    def profile(self, files):
        for name, text in files.items():
            (self.d / name).write_text(text)
        return profile.detect(self.d)

    def test_profile_says_what_go_and_rust_need(self):
        p = self.profile({"go.mod": "module x\n"})
        self.assertEqual(p["commands"]["test"], "go test ./...")
        self.assertIn("gotestsum", p["_note"])
        self.assertIn('"junit"', p["_note"])
        (self.d / "go.mod").unlink()
        self.assertIn("cargo2junit", self.profile({"Cargo.toml": "[package]\n"})["_note"])

    def test_profile_says_what_mocha_and_a_makefile_need(self):
        self.assertIn("mocha-junit-reporter",
                      self.profile({"package.json": json.dumps({"scripts": {"test": "mocha"}})})["_note"])
        (self.d / "package.json").unlink()
        self.assertIn('"junit"', self.profile({"Makefile": "test:\n\tbundle exec rspec\n"})["_note"])

    def test_profile_adds_nothing_for_a_runner_with_per_test_results(self):
        self.assertNotIn("junit", self.profile({"pyproject.toml": "[tool.pytest.ini_options]\n"})["_note"])
        (self.d / "pyproject.toml").unlink()
        self.assertNotIn("junit", self.profile({"package.json": json.dumps({"scripts": {"test": "vitest run"}})})["_note"])


class NoPerTestResults(Built):
    GO = "echo 'ok  example.com/orders 0.01s'"

    def test_row_tests_say_what_to_configure(self):
        self.p.write("tests/test_rows.py", "def test_notice():\n    \"\"\"Q-001\"\"\"\n    assert True\n")
        r = runner.run_tests("echo 'ok  example.com/orders 0.01s' # go test ./...", self.p.root, 30,
                             self.p.root / "log.txt", self.p.root / "j.xml")
        (self.p.root / "log.txt").unlink()
        res, _ = frontend._row_tests(ctx_of(self.p.root), r)
        self.assertEqual(res["status"], "unavailable")
        for needle in ('"junit"', "gotestsum"):
            self.assertIn(needle, res["message"])

    def test_a_suite_that_ran_red_without_a_summary_is_a_red_result(self):
        """Needs the one-line change in checks._tests: TOOL.test only when the command did not start."""
        self.set_cmd(test="echo '--- FAIL: TestOrders (0.00s)'; echo 'FAIL example.com/orders'; exit 1")
        rep = self.fe("fe-build")[2]
        ids = [c["id"] for c in rep["checks"]]
        self.assertNotIn("TOOL.test", ids)
        self.assertEqual(self.st(rep, "CMD.test"), "fail")
        self.assertIn("no per-test report: set \"junit\"", self.details(rep, "CMD.test"))
        self.set_cmd(test="no-such-test-runner-xyz ./...")
        self.assertEqual(self.st(self.fe("fe-build")[2], "TOOL.test"), "fail")


if __name__ == "__main__":
    unittest.main(verbosity=1)
