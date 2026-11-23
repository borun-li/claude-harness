#!/usr/bin/env python3
"""gate.py 10.0: one round counter, waivers and control files in the run log, the return record,
the read-only commands (check, status, stats), exit codes and config layers.
Run: python3 -m pytest tests/test_cli_v10.py -q"""
import hashlib
import io
import json
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from unittest import mock

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from test_gates import GATE, PLAN, PY, REQS, STATE, Base  # noqa: E402

sys.path.insert(0, str(GATE.parent))
import gate  # noqa: E402
from gatelib import auto, common, runlog  # noqa: E402

NO_CUT = REQS.replace("- **Cut:** above\n- **Fixtures:** FX-001", "- **Fixtures:** FX-001")


def tree_hash(root):
    """Every file and directory under `root`, .git included: equal before and after means nothing was written."""
    h = hashlib.sha256()
    for p in sorted(pathlib.Path(root).rglob("*")):
        h.update(p.relative_to(root).as_posix().encode())
        if p.is_file():
            h.update(p.read_bytes())
    return h.hexdigest()


class Cli(Base):
    """A project plus the hooks' way into gate.py, with its own temp dir for what the hooks keep outside the project."""
    def setUp(self):
        super().setUp()
        self.tmp = pathlib.Path(tempfile.mkdtemp(prefix="gatetmp-")).resolve()
        self.env = {**os.environ, "TMPDIR": str(self.tmp)}
        self.cmd("land")  # whatever the fixture's writers left: every test starts with nothing to land

    def tearDown(self):
        super().tearDown()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def cmd(self, *args):
        r = subprocess.run([PY, str(GATE), *args, "--project", str(self.p.root)], capture_output=True, text=True,
                           env=self.env)
        return r.returncode, r.stdout, r.stderr

    def auto(self, event, payload):
        payload = {"cwd": str(self.p.root), **payload}
        r = subprocess.run([PY, str(GATE), "auto", event, "--project", str(self.p.root)],
                           input=json.dumps(payload), capture_output=True, text=True, env=self.env)
        return r.returncode, r.stdout + r.stderr

    def dispatch(self, agent, step="4", rnd=1, only=None, **extra):
        prompt = f"You are {agent} #1 — step {step}, round {rnd}.\nTask: build the add function\n"
        prompt += f"Only: {only}\n" if only else ""
        payload = {k: extra.pop(k) for k in ("cwd",) if k in extra}
        return self.auto("dispatch", {"hook_event_name": "PreToolUse", "tool_name": "Agent", **payload,
                                      "tool_input": {"subagent_type": agent, "prompt": prompt, **extra}})

    def give_back(self, agent, report="done", usage=(), land=True, **extra):
        """The agent's return, by the hook; then its work is landed, as the orchestrator does."""
        t = self.tmp / f"transcript-{agent}.jsonl"
        lines = [{"message": {"id": i, "role": "assistant", "usage": u, "content": [{"type": "text", "text": "…"}]}}
                 for i, u in usage]
        lines.append({"message": {"role": "assistant", "content": [
            {"type": "tool_use", "name": "SubagentHandback", "input": {"message": report}}]}})
        t.write_text("".join(json.dumps(l) + "\n" for l in lines))
        r = self.auto("return", {"hook_event_name": "SubagentStop", "agent_type": agent,
                                 "agent_transcript_path": str(t), **extra})
        if land:
            self.cmd("land")
        return r

    def last(self, kind=None):
        return next(e for e in reversed(self.p.events()) if kind is None or e["event"] == kind)

    def kept_control(self):
        return list((self.tmp / "harness-control").glob("*/*.json"))


# ---------- M1: one round counter, from the run log ----------

class Rounds(Cli):
    def test_a_check_gate_never_returns_3_and_keeps_no_counter(self):
        codes = []
        for word in ("Say", "Tell", "Ask", "Beg"):  # four failures, each on a different tree
            self.p.write("docs/runs/calc/01-requirements.md", REQS.replace("Given", word))
            codes.append(self.p.gate("p1")[0])
        self.assertEqual(codes, [1, 1, 1, 1])
        self.assertFalse((self.p.run / "gates" / "attempts.json").exists())
        code, out, rep = self.p.gate("p1")
        self.assertIn("owners to fix", out)
        self.assertNotIn("LOOP CAP", out)
        self.assertNotIn("fix round", out)
        self.assertEqual({"escalate", "consecutive_failures", "failed_runs"} & set(rep), set())

    def test_a_redo_is_counted_whatever_round_the_brief_claims(self):
        """The same agent type, the same step, the same items, the earlier one returned: a redo."""
        self.assertEqual(self.dispatch("be-developer")[0], 0)
        self.assertNotIn("redo", self.last("dispatch"))
        self.give_back("be-developer")
        code, out = self.dispatch("be-developer")               # the brief still says round 1
        self.assertEqual(code, 0, out)
        self.assertIn("counted as redo round 1 of 2", out)      # a note, not a refusal
        self.assertEqual(self.last("dispatch")["redo"], 1)
        self.give_back("be-developer")
        self.assertEqual(self.dispatch("be-developer")[0], 0)
        self.give_back("be-developer")
        code, out = self.dispatch("be-developer")
        self.assertEqual(code, 2)
        self.assertIn("ROUND CAP", out)
        self.assertEqual(self.p.log("human", "--stop", "conditional", "--decision", "approved", "--step", "4",
                                    "--by", "user", "--note", "one more pass")[0], 0)
        self.assertEqual(self.dispatch("be-developer")[0], 0)   # the user's yes is read by the same counter
        self.assertEqual(self.last("dispatch")["redo"], 3)

    def test_rounds_are_counted_per_item(self):
        for only in ("Q-1", "Q-2"):  # two rows of one queue, each built once
            self.assertEqual(self.dispatch("fe-engineer", step="3", only=only)[0], 0)
            self.assertEqual(self.last("dispatch")["items"], [only])
            self.assertNotIn("redo", self.last("dispatch"))
            self.give_back("fe-engineer")
        for _ in range(2):
            self.assertEqual(self.dispatch("fe-engineer", step="3", only="Q-1")[0], 0)
            self.give_back("fe-engineer")
        code, out = self.dispatch("fe-engineer", step="3", only="Q-1, Q-2")
        self.assertEqual(code, 2)
        self.assertIn("fe-engineer at step 3 on Q-1 has used 2 of 2 rounds", out)
        self.assertEqual(self.dispatch("fe-engineer", step="3", only="Q-2", rnd=2)[0], 0)  # Q-2 has its own rounds
        code, out, _ = self.cmd("timeline")
        self.assertIn("step 3 fe-engineer Q-1 2/2", out)
        self.assertIn("step 3 fe-engineer Q-2 1/2", out)
        self.assertIn("step 3 fe-engineer Q-1 2/2", self.cmd("status")[1])

    def test_what_is_not_a_redo(self):
        d = lambda seq, items=None, agent="fe-engineer", step="3": {
            "seq": seq, "event": "dispatch", "agent": agent, "phase": step, **({"items": items} if items else {})}
        r = lambda seq, status="ok", agent="fe-engineer": {"seq": seq, "event": "return", "agent": agent, "status": status}
        g = lambda seq, overall: {"seq": seq, "event": "gate", "gate": "fe-build", "overall": overall}
        redo = lambda events, items=(), step="3": auto.is_redo(events, "fe-engineer", step, list(items))
        self.assertFalse(redo([]))
        self.assertFalse(redo([d(1)]))                                   # still out: a parallel dispatch
        self.assertTrue(redo([d(1), r(2)]))                              # neither names items
        self.assertFalse(redo([d(1), r(2, "blocked")]))                  # blocked: the round goes on
        self.assertFalse(redo([d(1), r(2)], step="4"))                   # another step
        self.assertFalse(redo([d(1, agent="fe-tester"), r(2, agent="fe-tester")]))
        self.assertFalse(redo([d(1, ["Q-1"]), r(2)], ["Q-2"]))           # other items
        self.assertFalse(redo([d(1), r(2)], ["Q-2"]))                    # the scaffold, then a row
        self.assertTrue(redo([d(1, ["Q-1", "Q-2"]), r(2)], ["Q-2"]))     # overlap, no gate passed
        self.assertTrue(redo([d(1, ["Q-1", "Q-2"]), r(2), g(3, "fail")], ["Q-2"]))
        self.assertFalse(redo([d(1, ["Q-1", "Q-2"]), r(2), g(3, "pass")], ["Q-2", "Q-3"]))  # the next piece of work
        self.assertTrue(redo([d(1, ["Q-1"]), r(2), g(3, "pass")], ["Q-1"]))  # the same items again

    def test_log_dispatch_redo_by_hand_takes_items_and_returns_3_over_the_cap(self):
        def redo(*items):
            r = self.p.log("dispatch", "--agent", "be-developer", "--model", "opus", "--step", "6", "--note", "fix",
                           "--redo", "--items", *items)
            if r[0] == 0:
                self.p.log("return", "--agent", "be-developer", "--step", "6", "--status", "ok", "--note", "fixed")
            return r
        self.assertEqual([redo("FND-001")[0], redo("FND-001")[0]], [0, 0])
        self.assertEqual(self.last("dispatch")["items"], ["FND-001"])
        code, out = redo("FND-001", "FND-002")
        self.assertEqual(code, 3, out)
        self.assertIn("on FND-001", out)
        self.assertEqual(redo("FND-002")[0], 0)

    def test_items_of_a_brief(self):
        self.assertEqual(auto.brief_items("You are x.\nOnly: TC-014, FND-003 and Q-5; Q-5 again\nRead: REQ-001"),
                         ["TC-014", "FND-003", "Q-5"])
        self.assertEqual(auto.brief_items("Task: REQ-001\n"), [])


# ---------- M4, M7: the log itself ----------

class Log(Cli):
    def test_a_mark_can_be_voided(self):
        self.assertEqual(self.p.gate("mark", "--role", "be-tester")[0], 0)
        seq = self.last("mark")["seq"]
        code, out = self.p.log("void", "--seq", str(seq), "--by", "orchestrator", "--note", "marked by hand, then by the hook")
        self.assertEqual(code, 0, out)
        self.assertNotIn(seq, [e["seq"] for e in runlog.events(self.p.run / "run-log.jsonl")])
        self.assertIn("repair only", gate.__doc__.split("gate.py mark --role")[1][:80])  # the hook takes the marks

    def test_line_separators_in_a_note_keep_one_event_on_one_line(self):
        note = "pasted\u2028from a page\u2029with\u0085breaks"
        self.assertEqual(self.p.log("decision", "--agent", "be-architect", "--note", note)[0], 0)
        log = self.p.run / "run-log.jsonl"
        text = log.read_text(encoding="utf-8")
        self.assertEqual(len(text.splitlines()), len(text.rstrip("\n").split("\n")))
        self.assertEqual(runlog.events(log)[-1]["note"], note)
        self.assertEqual(self.p.log("decision", "--agent", "be-architect", "--note", "the next entry")[0], 0)
        self.assertEqual(runlog.problems(log), [])

    def test_a_log_that_already_holds_a_raw_separator_still_loads(self):
        log = self.tmp / "run-log.jsonl"
        ev = {"seq": 1, "ts": "2026-01-01T00:00:00Z", "event": "decision", "agent": "be-architect",
              "note": "old\u2028entry", "prev": runlog.GENESIS}
        log.write_text(json.dumps(ev, ensure_ascii=False) + "\n", encoding="utf-8")
        self.assertEqual(len(log.read_text(encoding="utf-8").splitlines()), 2)  # what used to break the reader
        self.assertEqual(runlog.problems(log), [])
        runlog.append(log, "decision", agent="be-architect", note="after it")
        self.assertEqual([e["note"] for e in runlog.events(log)], ["old\u2028entry", "after it"])
        self.assertEqual(runlog.problems(log), [])

    def test_agent_id_on_returns_and_continuations(self):
        self.dispatch("be-developer")
        self.assertNotIn("agent_id", self.last("dispatch"))  # not known before the agent starts
        self.give_back("be-developer", agent_id="a1")
        self.assertEqual(self.last("return")["agent_id"], "a1")
        code, out = self.auto("dispatch", {"hook_event_name": "PreToolUse", "tool_name": "SendMessage",
                                           "harness_agent_type": "be-developer", "tool_input": {
                                               "to": "a1 [ref]", "message": "You are be-developer #1 — step 4, round 2."}})
        self.assertEqual(code, 0, out)
        ev = self.last("dispatch")
        self.assertEqual((ev["agent_id"], ev["continued"], ev["redo"]), ("a1", True, 1))

    def test_log_human_names_the_missing_flag(self):
        code, out = self.p.log("human", "--stop", "Plan", "--decision", "approved", "--note", "ok")
        self.assertEqual(code, 2)
        self.assertIn("--by", out)
        code, out = self.p.log("return", "--agent", "be-analyst", "--note", "x")
        self.assertEqual(code, 2)
        self.assertIn("--step --status", out)

    def test_approval_carries_what_was_locked(self):
        self.p.approve()
        ev = self.last("approve")
        self.assertRegex(ev["manifest_sha"], r"^[0-9a-f]{40,64}$")
        self.assertEqual(ev["active_reqs"], ["REQ-001", "REQ-002"])


# ---------- M5: the hooks find the project and never lose a return silently ----------

class Hooks(Cli):
    def test_a_session_in_a_subdirectory_still_finds_the_run(self):
        (self.p.root / "calc" / "deep").mkdir()
        sub = str(self.p.root / "calc" / "deep")
        self.assertEqual(self.dispatch("be-developer", cwd=sub)[0], 0)
        self.assertEqual(self.last()["event"], "dispatch")
        self.assertEqual(self.give_back("be-developer", cwd=sub, land=False)[0], 0)
        self.assertEqual(self.last()["event"], "return")

    def test_outside_git_the_cwd_is_the_project(self):
        shutil.rmtree(self.p.root / ".git")
        self.assertEqual(self.dispatch("be-developer")[0], 0)
        self.assertEqual(self.last()["event"], "dispatch")

    def test_a_return_whose_dispatch_was_never_logged_is_reported(self):
        n = len(self.p.events())
        kept = self.tmp / "harness-reports" / "a7.txt"  # what the handback hook kept for this agent
        kept.parent.mkdir()
        kept.write_text("tests written")
        code, out = self.give_back("be-tester", agent_id="a7")
        self.assertNotEqual(code, 0)
        self.assertEqual(len(out.strip().splitlines()), 1, out)
        for needle in ("never logged", "/route-resume", "by hand"):
            self.assertIn(needle, out)
        self.assertEqual(len(self.p.events()), n)
        self.assertFalse(kept.exists())  # the kept report does not pile up

    def test_no_open_run_no_message(self):
        self.p.write("docs/runs/calc/state.json", json.dumps(dict(STATE, status="abandoned")))
        self.assertEqual(self.give_back("be-tester"), (0, ""))
        n = len(self.p.events())
        self.assertEqual(self.dispatch("be-developer")[0], 0)  # an abandoned run is settled: nothing is logged
        self.assertEqual(len(self.p.events()), n)

    def test_two_open_runs_names_both_ways_out(self):
        self.p.write("docs/runs/feat2/state.json", json.dumps(STATE))
        code, out = self.dispatch("be-developer")
        self.assertEqual(code, 2)
        self.assertIn("accepted", out)
        self.assertIn("abandoned", out)

    def test_an_fe_agent_logs_into_the_one_run(self):
        self.assertEqual(self.dispatch("fe-engineer", step="2")[0], 0)
        self.assertEqual((self.last()["event"], self.last()["agent"]), ("dispatch", "fe-engineer"))
        self.give_back("fe-engineer", land=False)
        self.assertEqual(self.last()["event"], "return")

    def test_model_floor(self):
        self.p.write(".claude/harness.json", json.dumps({"models": {
            "_active_tier": "t", "tiers": {"t": {"fe-ux": "opus", "fe-engineer": "sonnet"}}, "floor": ["fe-ux"]}}))
        code, out = self.dispatch("fe-ux", step="1", model="sonnet")
        self.assertEqual(code, 2)
        self.assertIn("MODEL FLOOR", out)
        self.assertIn("opus", out)
        self.assertIn("models.floor", out)
        self.assertEqual(self.dispatch("fe-ux", step="1", model="claude-opus-4")[0], 0)
        self.give_back("fe-ux")
        self.assertEqual(self.dispatch("fe-engineer", step="2", model="haiku")[0], 0)  # no floor on this role
        self.give_back("fe-engineer")
        self.assertEqual(self.dispatch("fe-ux", step="1b")[0], 0)  # no model named: the agent file's own

    def test_blocked_zero_no_false_are_not_blocked(self):
        for line in ("blocked: 0", "blocked: no", "blocked: false", "blocked: False  # nothing", "blocked_on: []"):
            self.assertEqual(auto.parse_report(f"done\n{line}\n")[0], "ok", line)
        for line in ("blocked: yes", "blocked: no test data for REQ-2", "blocked_on: [DES-2 unclear]", "status: blocked"):
            self.assertEqual(auto.parse_report(f"done\n{line}\n")[0], "blocked", line)


# ---------- S5.1: the return says what the agent changed ----------

class ReturnRecord(Cli):
    REPORT = ("files_changed: [calc/core.py, calc/extra.py]\nuser_visible: `calc add` prints the sum on one line\n"
              "blocked_on: []\nhandoff: be-developer #1 · 4 · round 1\n")

    def work(self):
        self.assertEqual(self.dispatch("be-developer")[0], 0)
        self.p.write("calc/core.py", self.p.read("calc/core.py") + "\n# one more line\n")
        self.p.write("calc/extra.py", "A = 1\nB = 2\n")
        (self.p.root / "requirements.txt").unlink()

    def test_changes_time_tokens_and_the_saved_report(self):
        self.work()
        usage = [("m1", {"input_tokens": 10, "cache_creation_input_tokens": 5, "cache_read_input_tokens": 100,
                         "output_tokens": 7}),
                 ("m1", {"input_tokens": 10, "cache_creation_input_tokens": 5, "cache_read_input_tokens": 100,
                         "output_tokens": 7}),  # the same request, written as a second line
                 ("m2", {"input_tokens": 20, "cache_creation_input_tokens": 0, "cache_read_input_tokens": 300,
                         "output_tokens": 30})]
        self.assertEqual(self.give_back("be-developer", self.REPORT, usage=usage, agent_id="a1")[0], 0)
        ev = self.last("return")
        self.assertEqual(ev["changed"], {"added": 1, "modified": 1, "deleted": 1, "files": [
            "calc/extra.py (+2/-0)", "calc/core.py (+2/-0)", "requirements.txt (+0/-1)"]})
        self.assertEqual(ev["visible"], "`calc add` prints the sum on one line")
        self.assertEqual((ev["context"], ev["out_tokens"]), (320, 37))
        self.assertIsInstance(ev["seconds"], int)
        self.assertEqual(ev["report"], f"docs/runs/calc/logs/returns/{ev['seq']}-be-developer.md")
        self.assertEqual(self.p.read(ev["report"]), self.REPORT)
        self.assertEqual((ev["status"], ev["note"]), ("ok", "be-developer #1 · 4 · round 1"))

    def test_timeline_shows_the_date_the_changes_and_the_visible_effect(self):
        self.work()
        self.give_back("be-developer", self.REPORT)
        out = self.cmd("timeline")[1]
        row = next(l for l in out.splitlines() if "| return | be-developer |" in l)
        self.assertRegex(row, r"\| \d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2} \|")
        self.assertIn("+1 ~1 -1 files", row)
        self.assertIn("visible: `calc add` prints the sum on one line", row)

    def test_non_writers_and_projects_outside_git(self):
        self.dispatch("be-review-security", step="6")
        self.give_back("be-review-security", "candidates: none")
        self.assertNotIn("changed", self.last("return"))
        shutil.rmtree(self.p.root / ".git")
        self.work()
        self.give_back("be-developer", self.REPORT)
        ch = self.last("return")["changed"]
        self.assertEqual((ch["added"], ch["modified"], ch["deleted"]), (1, 1, 1))
        self.assertEqual(ch["files"], ["calc/extra.py", "calc/core.py", "requirements.txt"])  # no counts without git

    def test_a_broken_detail_still_logs_the_plain_return(self):
        self.work()
        (self.p.run / "gates" / "snap-be-developer.json").write_text("{ not json")
        code, out = self.give_back("be-developer", self.REPORT)
        self.assertEqual(code, 0, out)
        ev = self.last("return")
        self.assertNotIn("changed", ev)
        self.assertEqual((ev["status"], ev["visible"]), ("ok", "`calc add` prints the sum on one line"))

    def test_an_agent_that_ends_without_a_report(self):
        self.dispatch("be-developer")
        code, _ = self.auto("return", {"hook_event_name": "SubagentStop", "agent_type": "be-developer",
                                       "agent_transcript_path": str(self.tmp / "missing.jsonl")})
        self.assertEqual(code, 0)
        ev = self.last("return")
        self.assertEqual((ev["status"], ev["note"]), ("failed", "ended without a report"))
        self.assertNotIn("report", ev)
        self.assertNotIn("context", ev)


# ---------- S8: waivers and control files ----------

class Waivers(Cli):
    def fail_p1(self):
        self.p.write("docs/runs/calc/01-requirements.md", NO_CUT)
        code, _, rep = self.p.gate("p1")
        self.assertEqual((code, self.p.status(rep, "P1.cut-line")), (1, "fail"))

    def waive(self, check="P1.cut-line", gate_name="p1", *extra):
        return self.cmd("waive", "--check", check, "--gate", gate_name, "--by", "user", "--reason", "tiny round", *extra)

    def test_a_waiver_needs_a_failure_the_user_has_seen(self):
        code, _, err = self.waive()
        self.assertEqual(code, 2)                      # no report yet
        self.assertIn("not failing", err)
        self.assertEqual(self.p.gate("p1")[0], 0)
        self.assertEqual(self.waive()[0], 2)           # the check passes
        self.assertEqual(self.cmd("waive", "--check", "P1.cut-line", "--gate", "p1")[0], 2)  # no --by, no --reason
        self.assertNotIn("waive", [e["event"] for e in self.p.events()])

    def test_waived_until_a_new_failure_line_appears(self):
        self.fail_p1()
        code, out, err = self.waive()
        self.assertEqual(code, 0, err)
        ev = self.last("waive")
        self.assertEqual((ev["check"], ev["gate"], ev["by"], ev["reason"]), ("P1.cut-line", "p1", "user", "tiny round"))
        self.assertEqual(ev["sig"], hashlib.sha256("\n".join(sorted(ev["details"])).encode()).hexdigest())
        code, out, rep = self.p.gate("p1")
        self.assertEqual((code, self.p.status(rep, "P1.cut-line")), (0, "waived"))
        self.assertEqual(self.p.gate("p1")[0], 0)      # the waiver's own note is not a new line
        self.p.write("docs/runs/calc/01-requirements.md", NO_CUT.replace(
            "### REQ-002 — subtract\n- **Cut:** above\n", "### REQ-002 — subtract\n"))
        code, out, rep = self.p.gate("p1")
        self.assertEqual((code, self.p.status(rep, "P1.cut-line")), (1, "fail"))
        self.assertIn("does not apply: new since the waiver", out)
        self.assertIn("REQ-002", out.split("does not apply")[1].splitlines()[0])
        self.assertEqual(self.waive()[0], 0)           # the user waives what the check now reports
        self.assertEqual(self.p.gate("p1")[0], 0)

    def test_a_waiver_belongs_to_one_gate_and_can_be_voided(self):
        bad = lambda: [{"id": "ROLE.unplanned", "status": "fail", "owner": "be-developer", "message": "m",
                        "details": ["a.py"]}]
        w = {"seq": 9, "ts": "2026-11-21T10:00:00Z", "event": "waive", "check": "ROLE.unplanned", "gate": "p4",
             "by": "user", "reason": "r", "details": ["a.py", "b.py"]}
        for gate_name, expected in (("p4", "waived"), ("p5", "fail")):
            res = bad()
            gate.apply_waivers(res, [w], gate_name)
            self.assertEqual(res[0]["status"], expected, gate_name)
        self.fail_p1()
        self.waive()
        self.assertEqual(self.p.log("void", "--seq", str(self.last("waive")["seq"]), "--by", "user",
                                    "--note", "the user took it back")[0], 0)
        self.assertEqual(self.p.gate("p1")[0], 1)

    def test_what_can_never_be_waived(self):
        for cid in ("TOOL.test", "LOG.valid", "CTRL.waivers-file"):
            code, _, err = self.waive(cid)
            self.assertEqual(code, 2, cid)
            self.assertIn("cannot be waived", err)
            res = [{"id": cid, "status": "fail", "owner": "o", "message": "m", "details": []}]
            gate.apply_waivers(res, [{"seq": 1, "ts": "", "event": "waive", "check": cid, "gate": "p1", "by": "u",
                                      "reason": "r"}], "p1")
            self.assertEqual(res[0]["status"], "fail", cid)

    def test_a_waivers_json_is_refused_not_read(self):
        self.fail_p1()
        self.p.write("docs/runs/calc/gates/waivers.json", json.dumps(
            [{"check": "P1.cut-line", "reason": "tiny round", "approved_by": "user", "date": "2026-09-23"}]))
        code, out, rep = self.p.gate("p1")
        self.assertEqual(code, 1)
        self.assertEqual(self.p.status(rep, "P1.cut-line"), "fail")
        self.assertEqual(self.p.status(rep, "CTRL.waivers-file"), "fail")
        self.assertIn("gate.py waive", out)
        self.assertEqual(rep["fail_by_owner"]["orchestrator"], ["CTRL.waivers-file"])

    def test_failing_tests_are_waived_by_name(self):
        self.p.to_p4()
        self.p.write("tests/test_red.py", "def test_red_one():\n    assert False\n")
        self.assertEqual(self.p.gate("p4")[0], 1)
        code, _, err = self.waive("CMD.test", "p4")
        self.assertEqual(code, 2)
        self.assertIn("--tests", err)
        self.assertEqual(self.waive("CMD.test", "p4", "--tests", "test_red_one")[0], 0)
        self.assertEqual(self.p.status(self.p.gate("p4")[2], "CMD.test"), "waived")
        self.p.write("tests/test_red.py", "def test_red_one():\n    assert False\n\n\ndef test_red_two():\n    assert False\n")
        rep = self.p.gate("p4")[2]
        self.assertEqual(self.p.status(rep, "CMD.test"), "fail")
        self.assertIn("test_red_two", " ".join(next(c for c in rep["checks"] if c["id"] == "CMD.test")["details"]))


class ControlFiles(Cli):
    def test_what_an_agent_changed_among_the_gates_books_is_on_its_return(self):
        self.assertEqual(self.p.gate("p1")[0], 0)
        self.assertEqual(self.dispatch("be-developer")[0], 0)
        self.assertEqual(len(self.kept_control()), 1)
        self.assertEqual(self.kept_control()[0].parent.parent, self.tmp / "harness-control")  # outside the project
        g = json.loads(self.p.read(".claude/gates.json"))
        g["commands"]["test"] = "echo '5 passed'"
        self.p.write(".claude/gates.json", json.dumps(g))                       # a forged test command
        self.p.write("docs/runs/calc/gates/p4-latest.json", '{"overall": "pass"}')  # a forged report
        rep = json.loads(self.p.read("docs/runs/calc/gates/p1-latest.json"))
        self.p.write("docs/runs/calc/gates/p1-latest.json", json.dumps(dict(rep, time="later")))
        self.p.write("docs/runs/calc/gates/logs/x.log", "a command's output")     # not a control file
        self.p.write("calc/core.py", self.p.read("calc/core.py") + "\n# its work\n")
        self.give_back("be-developer")
        self.assertEqual(self.last("return")["control_changed"],
                         [".claude/gates.json", "docs/runs/calc/gates/p1-latest.json", "docs/runs/calc/gates/p4-latest.json"])
        self.assertEqual(self.kept_control(), [])  # dropped at the return
        code, out, rep = self.p.gate("p1")  # every gate after it says so, until it is restored and waived
        self.assertEqual(code, 1, out)
        ctrl = next(c for c in rep["checks"] if c["id"] == "CTRL.files")
        self.assertEqual(ctrl["status"], "fail")
        self.assertIn(".claude/gates.json", " ".join(ctrl["details"]))

    def test_every_harness_agent_is_watched_and_a_clean_one_reports_nothing(self):
        self.dispatch("be-review-security", step="6")
        self.assertEqual(len(self.kept_control()), 1)
        self.give_back("be-review-security", "candidates: none")
        self.assertNotIn("control_changed", self.last("return"))
        self.assertEqual(self.kept_control(), [])
        self.assertEqual(self.p.status(self.p.gate("p1")[2], "CTRL.files"), "pass")

    def test_gate_pys_own_writes_while_an_agent_is_out_are_not_the_agents(self):
        self.dispatch("be-review-security", step="6")  # a reviewer out does not stop a check gate
        self.assertEqual(self.cmd("p1")[0], 0)         # writes p1-latest.json, p1-<utc>.json
        self.p.draft_fixture()
        self.assertEqual(self.cmd("p2")[0], 0)
        self.p.log("human", "--stop", "Plan", "--decision", "approved", "--by", "user", "--note", "plan ok")
        self.assertEqual(self.cmd("fixtures-approve", "--by", "user")[0], 0)
        self.give_back("be-review-security", "candidates: none")
        self.assertNotIn("control_changed", self.last("return"))

    def test_a_broken_profile_is_reported_not_a_lost_return(self):
        self.dispatch("be-developer")
        self.p.write(".claude/gates.json", "{ no longer json")
        self.p.write(".claude/settings.local.json", '{"permissions": {"allow": ["Bash(ls:*)"]}}')  # the client's own
        code, out = self.give_back("be-developer")
        self.assertEqual(code, 0, out)
        ev = self.last("return")
        self.assertEqual(ev["control_changed"], [".claude/gates.json"])
        self.assertNotIn("changed", ev)  # what could not be read is left out; the return is logged

    def test_a_return_logged_by_hand_is_checked_the_same_way(self):
        self.dispatch("be-developer")
        self.p.write("docs/runs/calc/gates/baseline.json", "{}")
        code, out, err = self.cmd("log", "return", "--agent", "be-developer", "--step", "4", "--status", "failed",
                                  "--note", "died; logged by hand")
        self.assertEqual(code, 0, err)
        self.assertEqual(self.last("return")["control_changed"], ["docs/runs/calc/gates/baseline.json"])
        self.assertEqual(self.kept_control(), [])
        self.dispatch("be-tester")
        self.assertEqual(len(self.kept_control()), 1)
        self.assertEqual(self.cmd("log", "void", "--seq", str(self.last("dispatch")["seq"]), "--by", "orchestrator",
                                  "--note", "never started")[0], 0)
        self.assertEqual(self.kept_control(), [])  # a voided dispatch leaves nothing behind


# ---------- CLI: check, status, stats ----------

class Check(Cli):
    def test_check_reads_only_never_waits_and_needs_no_profile(self):
        self.assertEqual(self.dispatch("be-analyst", step="1", rnd=2)[0], 0)  # this run has a writer out
        self.assertEqual(self.p.gate("p1")[0], 4)                             # so the gate itself waits
        (self.p.root / ".claude" / "gates.json").unlink()                     # and no profile
        before, n = tree_hash(self.p.root), len(self.p.events())
        code, out, err = self.cmd("check", "p1")
        self.assertEqual(code, 0, out + err)
        self.assertIn("[check] p1: PASS", out)
        self.p.write("docs/runs/calc/01-requirements.md", NO_CUT)
        self.p.write("docs/runs/calc/handoff.md", "## be-analyst #1 · t\nTask: a\n## be-analyst #2 · t\nTask: b\n")
        before = tree_hash(self.p.root)
        code, out, err = self.cmd("check", "p1")
        self.assertEqual(code, 1, out + err)
        self.assertIn("[FAIL] P1.cut-line", out)
        self.assertIn("REQ-001", out)                  # the details an author needs
        self.assertIn("[FAIL] CTX.handoff", out)       # the context files are always part of a check
        self.assertIn("[check] p1: FAIL", out)
        self.assertNotIn("[PASS]", out)
        self.assertEqual(tree_hash(self.p.root), before)
        self.assertEqual(len(self.p.events()), n)

    def test_check_of_a_gate_that_runs_commands_writes_nothing(self):
        self.p.to_p4()
        before = tree_hash(self.p.root)
        code, out, err = self.cmd("check", "p4")
        self.assertIn(code, (0, 1), out + err)
        self.assertIn("[check] p4:", out)
        self.assertEqual(tree_hash(self.p.root), before)

    def test_check_needs_a_gate(self):
        for args in (("check",), ("check", "nonsense")):
            code, _, err = self.cmd(*args)
            self.assertEqual(code, 2)
            self.assertIn("check needs a gate", err)

    def test_check_finds_the_one_open_run(self):
        self.p.write("docs/runs/calc/state.json", json.dumps(dict(STATE, status="accepted")))
        self.p.write("docs/runs/feat2/state.json", json.dumps(STATE))
        self.p.write("docs/runs/feat2/01-requirements.md", NO_CUT)
        code, out, _ = self.cmd("check", "p1")
        self.assertEqual(code, 1)
        self.assertIn("[FAIL] P1.cut-line", out)

    def test_context_files_are_checked_from_the_build_gates_on(self):
        self.p.write("docs/runs/calc/handoff.md", "## be-analyst #1 · t\nTask: a\n## be-analyst #2 · t\nTask: b\n")
        code, out, rep = self.p.gate("p1")
        self.assertEqual(code, 0, out)
        ids = [c["id"] for c in rep["checks"]]
        self.assertNotIn("CTX.handoff", ids)
        self.assertNotIn("CTX.codemap", ids)
        self.assertIn("LOG.valid", ids)                # on every gate, as before
        self.assertIn("CTRL.files", ids)
        self.p.to_p4()
        rep = self.p.gate("p4")[2]
        self.assertEqual(self.p.status(rep, "CTX.handoff"), "fail")
        self.assertIn("CTX.codemap", [c["id"] for c in rep["checks"]])

    def test_the_standard_tier_gates_are_gates(self):
        from gatelib import standard
        self.assertTrue(standard.PHASES)
        for name in standard.PHASES:
            self.assertIs(gate.PHASES[name], standard.PHASES[name])
            self.assertIn(name, gate.CONTEXT_GATES)


class StatusAndStats(Cli):
    def run_a_little(self):
        self.assertEqual(self.p.gate("p1")[0], 0)
        self.dispatch("be-developer", only="DES-001")
        self.p.write("calc/core.py", self.p.read("calc/core.py") + "\n# more\n")
        self.give_back("be-developer", "user_visible: none\nhandoff: be-developer #1")
        self.dispatch("be-developer", only="DES-001", rnd=2)
        self.p.write("calc/core.py", self.p.read("calc/core.py") + "\n# and more\n")
        self.give_back("be-developer", "user_visible: `calc add` prints the sum\nhandoff: be-developer #1")
        self.dispatch("be-tester")

    def test_status(self):
        self.run_a_little()
        before = tree_hash(self.p.root)
        (code, out, err) = self.cmd("status")
        self.assertEqual(code, 0, err)
        self.assertEqual(tree_hash(self.p.root), before)
        for needle in ("docs/runs/calc: tier small · scope backend · step 1 · in_progress",
                       "be-tester · step 4 · in tree · since 20",
                       "p1: pass",
                       "step 4 be-developer DES-001 1/2",
                       "be-developer · step 4 · +0 ~1 -0 files · visible: `calc add` prints the sum",
                       "be-developer: #3", "be-tester: #2", "be-analyst: #2"):
            self.assertIn(needle, out)
        self.assertNotIn("fe-", out.split("Next ordinal")[1])
        (self.p.root / ".claude" / "gates.json").unlink()
        self.assertEqual(self.cmd("status")[0], 0)     # no profile needed

    def test_status_of_a_named_run_and_of_no_run(self):
        self.p.write("docs/runs/ui/state.json", json.dumps(
            {"status": "accepted", "tier": "standard", "scope": "frontend", "current_phase": 2}))
        code, out, _ = self.cmd("status", "--run", "ui")
        self.assertEqual(code, 0)
        self.assertIn("docs/runs/ui: tier standard · scope frontend · step 2 · accepted", out)
        self.assertIn("Open dispatches:\n  none", out)
        self.assertIn("docs/runs/calc: tier", self.cmd("status")[1])   # the one open run, no --run needed
        code, out, _ = self.cmd("check", "p1")
        self.assertEqual((code, "[check] p1: PASS" in out), (0, True), out)
        code, _, err = self.cmd("status", "--run", "nope")
        self.assertEqual(code, 2)
        self.assertIn("no run docs/runs/nope", err)

    def test_stats_from_the_command(self):
        self.run_a_little()
        code, out, err = self.cmd("stats")
        self.assertEqual(code, 0, err)
        self.assertEqual(self.p.read("docs/runs/calc/stats.md"), out.rstrip("\n") + "\n")
        rows = [l for l in out.splitlines() if "| be-developer | 4 |" in l]
        self.assertEqual(len(rows), 2)
        self.assertIn("| first |", rows[0])
        self.assertIn("| redo 1 |", rows[1])
        self.assertIn("| out |", next(l for l in out.splitlines() if "| be-tester |" in l))
        self.assertIn("- Dispatches: 4, of them redo rounds: 1", out)
        self.assertIn("- Gate runs: 1, failed: 0", out)

    def test_stats_totals(self):
        log = self.tmp / "run-log.jsonl"
        t = lambda hhmm: f"2026-11-21T{hhmm}:00Z"
        evs = [{"event": "dispatch", "ts": t("10:00"), "agent": "be-developer", "phase": "4"},
               {"event": "return", "ts": t("10:10"), "agent": "be-developer", "phase": "4", "status": "ok",
                "seconds": 590, "context": 1000, "out_tokens": 50},
               {"event": "gate", "ts": t("10:11"), "gate": "p4", "overall": "fail",
                "fails": {"be-developer": ["ROLE.unplanned", "CMD.test"], "orchestrator": ["CTX.handoff"]}},
               {"event": "human", "ts": t("10:41"), "stop": "conditional", "decision": "approved", "by": "user"},
               {"event": "dispatch", "ts": t("10:42"), "agent": "be-developer", "phase": "4", "redo": 1},
               {"event": "human", "ts": t("10:44"), "stop": "conditional", "decision": "answered", "by": "user"},
               {"event": "return", "ts": t("10:47"), "agent": "be-developer", "phase": "4", "status": "blocked"},
               {"event": "gate", "ts": t("10:48"), "gate": "p4", "overall": "pass"}]
        log.write_text("".join(json.dumps(dict(e, seq=i)) + "\n" for i, e in enumerate(evs, 1)))
        out = runlog.stats(log)
        for needle in ("| 1 | be-developer | 4 | first | 9m 50s | 1000 | 50 | ok |",
                       "| 5 | be-developer | 4 | redo 1 | 5m 00s | – | – | blocked |",
                       "- Dispatches: 2, of them redo rounds: 1",
                       "- An agent out: 15m 00s (agent time added up: 14m 50s)",
                       "- Waiting on the user: 30m 00s",  # the answer given while an agent was out is not waiting
                       "- Gate runs: 2, failed: 1",
                       "- Failed checks by owner: be-developer 2 · orchestrator 1",
                       "- Failed checks by kind: CMD 1 · CTX 1 · ROLE 1"):
            self.assertIn(needle, out)


# ---------- M16: config layers and exit codes ----------

class Config(Cli):
    def test_a_project_that_sets_one_budget_keeps_the_others(self):
        g = json.loads(self.p.read(".claude/gates.json"))
        self.p.write(".claude/gates.json", json.dumps(dict(g, doc_budgets={"prose_unit_words": 60})))
        code, out, rep = self.p.gate("p1")
        self.assertEqual(code, 0, out)
        cfg = gate.load_cfg(self.p.root)
        self.assertEqual(cfg["doc_budgets"]["prose_unit_words"], 60)
        self.assertEqual(cfg["doc_budgets"]["req_words"],
                         json.loads((GATE.parent / "config.json").read_text())["doc_budgets"]["req_words"])
        self.assertEqual(sorted(cfg["commands"]), ["build", "lint", "test", "typecheck"])

    def test_merge_goes_one_level_and_skips_comments(self):
        from gatelib.common import merge
        base = {"a": {"x": 1, "y": {"p": 1, "q": 2}}, "b": [1], "c": 1}
        self.assertEqual(merge(base, {"a": {"y": {"p": 9}}, "b": [2], "_comment": "no"}),
                         {"a": {"x": 1, "y": {"p": 9}}, "b": [2], "c": 1})
        self.assertEqual(merge(base, {"a": {"y": {"p": 9}}}, depth=2)["a"]["y"], {"p": 9, "q": 2})
        self.assertEqual(base["a"]["y"], {"p": 1, "q": 2})  # the base is not changed

    def test_loop_cap_reads_three_layers(self):
        home = self.tmp / "harness"
        write = lambda rel, cap: (home / rel).parent.mkdir(parents=True, exist_ok=True) or (home / rel).write_text(
            json.dumps({"loops": {"max_rounds": cap}}))
        with mock.patch.object(common, "HARNESS_ROOT", home):
            self.assertEqual(gate.loop_cap(self.p.root), 2)   # no layer says: the default
            write("harness/config.json", 3)
            self.assertEqual(gate.loop_cap(self.p.root), 3)
            write("harness-local/config.json", 4)            # the user's own default, kept across installs
            self.assertEqual(gate.loop_cap(self.p.root), 4)
            self.p.write(".claude/harness.json", json.dumps({"loops": {"max_rounds": 5}}))
            self.assertEqual(gate.loop_cap(self.p.root), 5)

    def test_a_crash_of_the_gate_is_exit_5_not_a_failed_check(self):
        def boom(ctx):
            raise KeyError("req_words")
        err = io.StringIO()
        with mock.patch.dict(gate.PHASES, {"p1": boom}), redirect_stderr(err), redirect_stdout(io.StringIO()), \
                mock.patch.object(sys, "argv", ["gate.py", "p1", "--project", str(self.p.root)]):
            self.assertEqual(gate.cli(), 5)
        self.assertIn("[gate] CRASH: KeyError: 'req_words'", err.getvalue())
        self.assertIn("Traceback", err.getvalue())
        self.assertNotIn("gate", [e["event"] for e in self.p.events()])  # no verdict was recorded
        self.assertEqual(self.p.gate("nonsense")[0], 2)     # usage stays 2

    def test_the_runs_root_comes_from_the_project(self):
        self.p.write(".claude/harness.json", json.dumps({"artifacts": {"run_dir": "work/runs"}}))
        self.p.write("work/runs/calc2/state.json", json.dumps(STATE))
        self.assertEqual(self.p.log("decision", "--agent", "be-architect", "--note", "x")[0], 0)
        self.assertTrue((self.p.root / "work/runs/calc2/run-log.jsonl").exists())
        self.assertEqual(self.dispatch("be-developer")[0], 0)   # the hooks look there too
        log = [json.loads(l) for l in self.p.read("work/runs/calc2/run-log.jsonl").split("\n") if l]
        self.assertEqual(log[-1]["event"], "dispatch")


if __name__ == "__main__":
    unittest.main()
