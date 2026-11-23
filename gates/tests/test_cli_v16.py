#!/usr/bin/env python3
"""gate.py 16.0: one run (which run, the earlier layout refused, one config), the run-log events of
landing, where a dispatched writer works, returns from worktrees, `land`, `worktrees`, the busy rule.
Run: python3 -m pytest tests/test_cli_v16.py -q"""
import hashlib
import json
import pathlib
import subprocess
import sys
import unittest
from unittest import mock

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from test_gates import GATE, PY, RUN, STATE  # noqa: E402
from test_cli_v10 import NO_CUT, Cli  # noqa: E402

sys.path.insert(0, str(GATE.parent))
import gate  # noqa: E402
from gatelib import auto, common, runlog  # noqa: E402
from gatelib.common import ConfigError  # noqa: E402

CORE = "calc/core.py"


class Run(Cli):
    """A project with one open run, a home of its own for Claude Code's settings, and the worktrees
    Claude Code would make for isolated agents."""
    def setUp(self):
        super().setUp()
        (self.tmp / "home").mkdir()
        self.env["HOME"] = str(self.tmp / "home")
        with open(self.p.root / ".git" / "info" / "exclude", "a") as f:
            f.write(".claude/worktrees/\n")

    def git(self, *args, cwd=None):
        r = subprocess.run(["git", "-C", str(cwd or self.p.root), *args], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        return r.stdout.strip()

    def commit(self, msg="bookkeeping"):
        self.git("add", "-A")
        self.git("commit", "-qm", msg)

    def isolation(self):
        """Once per project: the base setting, committed with whatever else the tree holds."""
        self.assertEqual(self.cmd("worktrees", "--setup")[0], 0)
        self.commit("worktree setting")

    def out(self, agent, task="build it", step="4", rnd=1, isolated=True, **extra):
        """A dispatch through the hook: (exit code, output, the prompt sent)."""
        prompt = f"You are {agent} #1 — step {step}, round {rnd}.\nTask: {task}\n"
        ti = {"subagent_type": agent, "prompt": prompt, **({"isolation": "worktree"} if isolated else {}), **extra}
        code, out = self.auto("dispatch", {"hook_event_name": "PreToolUse", "tool_name": "Agent", "tool_input": ti})
        return code, out, prompt

    def worktree(self, agent_id):
        rel = f".claude/worktrees/agent-{agent_id}"
        self.git("worktree", "add", "-q", rel, "-b", f"worktree-agent-{agent_id}")
        return self.p.root / rel

    def back(self, agent, agent_id=None, prompt=None, report="done", cwd=None):
        """A return through the hook, from an agent whose transcript starts with `prompt`."""
        t = self.tmp / f"transcript-{agent}-{agent_id}.jsonl"
        lines = [{"message": {"role": "user", "content": prompt}}] if prompt else []
        lines.append({"message": {"role": "assistant", "content": [
            {"type": "tool_use", "name": "SubagentHandback", "input": {"message": report}}]}})
        t.write_text("".join(json.dumps(l) + "\n" for l in lines))
        return self.auto("return", {"hook_event_name": "SubagentStop", "agent_type": agent, "agent_id": agent_id,
                                    "agent_transcript_path": str(t), **({"cwd": str(cwd)} if cwd else {})})

    def more(self, agent_id, to="fe-engineer", message="You are {a} #1 — step 4, round 2."):
        return self.auto("dispatch", {"hook_event_name": "PreToolUse", "tool_name": "SendMessage",
                                      "harness_agent_type": to,
                                      "tool_input": {"to": agent_id, "message": message.format(a=to)}})

    def edit(self, wt, rel, text):
        (wt / rel).parent.mkdir(parents=True, exist_ok=True)
        (wt / rel).write_text(text)

    def state(self, **over):
        self.p.write(f"{RUN}/state.json", json.dumps(dict(STATE, **over)))


# ---------- §1.2: which run ----------

class WhichRun(Run):
    def test_no_open_run_and_several(self):
        self.state(status="prototype_confirmed")
        code, _, err = self.cmd("status")
        self.assertEqual(code, 2)
        self.assertIn("no open run under docs/runs", err)
        for slug in ("a", "b"):
            self.p.write(f"docs/runs/{slug}/state.json", json.dumps(STATE))
        code, _, err = self.cmd("status")
        self.assertEqual(code, 2)
        for needle in ("docs/runs/a", "docs/runs/b", "pass --run <slug>", "settle the finished one"):
            self.assertIn(needle, err)
        code, out, _ = self.cmd("status", "--run", "b")
        self.assertEqual(code, 0)
        self.assertIn("docs/runs/b: tier", out)
        self.assertEqual(self.cmd("log", "decision", "--agent", "be-architect", "--note", "x", "--run", "a")[0], 0)
        self.assertTrue((self.p.root / "docs/runs/a/run-log.jsonl").is_file())

    def test_a_settled_run_is_read_with_run_and_not_gated(self):
        self.state(status="accepted")
        for command in ("status", "stats", "timeline"):
            self.assertEqual(self.cmd(command, "--run", "calc")[0], 0, command)
        code, _, err = self.cmd("p1", "--run", "calc")
        self.assertEqual(code, 2)
        self.assertIn("docs/runs/calc is settled (accepted)", err)
        self.assertEqual(self.cmd("log", "decision", "--agent", "be-architect", "--note", "x", "--run", "calc")[0], 2)

    def test_the_team_and_run_dir_flags_are_gone(self):
        for flags in (("--team", "backend"), ("--run-dir", RUN)):
            code, _, err = self.cmd("status", *flags)
            self.assertEqual(code, 2, flags)
            self.assertIn("unrecognized arguments", err)
        self.assertIn("unrecognized arguments", self.cmd(
            "log", "dispatch", "--agent", "be-tester", "--model", "opus", "--step", "5", "--note", "x", "--parallel")[2])
        for gone in ("--team", "--run-dir", "--parallel", "docs/backend", "docs/frontend", "other team"):
            self.assertNotIn(gone, gate.__doc__)
        for said in ("--run <slug>", "gate.py land", "gate.py worktrees", "isolation: \"worktree\""):
            self.assertIn(said, gate.__doc__)

    def test_files_of_the_earlier_layout_are_refused_with_the_fix(self):
        self.assertEqual(self.out("be-developer", isolated=False)[0], 0)  # out before the files appear
        self.p.write(".claude/backend.json", "{}")
        self.p.write("docs/frontend/state.json", json.dumps({"status": "building"}))
        self.p.write("docs/backend/old/state.json", json.dumps({"status": "accepted"}))  # history: left alone
        self.p.write("docs/frontend/observables.json", "{}")
        code, _, err = self.cmd("status")
        self.assertEqual(code, 2)
        self.assertEqual(len(err.strip().splitlines()), 1, err)
        for needle in (".claude/backend.json", ".claude/harness.json", "`models`", "docs/frontend/state.json",
                       "started by an earlier harness version", "abandoned",
                       "git mv docs/frontend/observables.json docs/observables.json"):
            self.assertIn(needle, err)
        self.assertNotIn("docs/backend/old", err)
        n = len(self.p.events())
        code, out = self.dispatch("be-review-security", step="6")  # the dispatch hook refuses the same way
        self.assertEqual(code, 2)
        self.assertIn("earlier harness layout", out)
        self.assertEqual(len(self.p.events()), n)
        self.assertEqual(self.back("be-developer")[0], 0)  # a return is never lost to it
        self.assertEqual(self.last()["event"], "return")
        (self.p.root / ".claude/backend.json").unlink()
        self.p.write("docs/frontend/state.json", json.dumps({"status": "abandoned"}))
        self.p.write("docs/observables.json", "{}")
        self.assertEqual(self.cmd("status")[0], 0)


# ---------- §2: one config ----------

class HarnessConfig(Run):
    def test_three_layers_and_a_layer_that_sets_one_key_keeps_the_block(self):
        home = self.tmp / "harness"
        put = lambda rel, data: ((home / rel).parent.mkdir(parents=True, exist_ok=True),
                                 (home / rel).write_text(json.dumps(data)))
        with mock.patch.object(common, "HARNESS_ROOT", home):
            self.assertEqual(common.harness_cfg(self.p.root), {})
            put("harness/config.json", {
                "_comment": "defaults", "viewports": [1440, 375],
                "models": {"_active_tier": "quality", "tiers": {"quality": {"fe-ux": "opus"}}, "floor": ["fe-ux"]},
                "loops": {"max_rounds": 2, "continue_max_context": 150000}})
            put("harness-local/config.json", {"loops": {"max_rounds": 4}})
            self.p.write(".claude/harness.json", json.dumps({"models": {"_active_tier": "economy"}, "viewports": [375]}))
            cfg = common.harness_cfg(self.p.root)
            self.assertEqual(cfg["loops"], {"max_rounds": 4, "continue_max_context": 150000})
            self.assertEqual(cfg["models"]["_active_tier"], "economy")       # the project's tier is in force
            self.assertEqual(cfg["models"]["tiers"], {"quality": {"fe-ux": "opus"}})
            self.assertEqual(cfg["viewports"], [375])                         # a list is replaced
            self.assertNotIn("_comment", cfg)
            self.p.write(".claude/harness.json", "{ not json")
            with self.assertRaises(ConfigError) as e:
                common.harness_cfg(self.p.root)
            self.assertIn("harness.json", str(e.exception))

    def test_the_harness_ships_one_config(self):
        cfg = common.harness_cfg(self.p.root)
        self.assertIn(cfg["models"]["_active_tier"], cfg["models"]["tiers"])
        self.assertIsInstance(cfg["models"]["floor"], list)
        self.assertEqual(gate.loop_cap(self.p.root), cfg["loops"]["max_rounds"])
        self.assertFalse(hasattr(gate, "team_cfg"))

    def test_the_floor_is_the_active_tiers_model_or_the_one_the_run_gives(self):
        self.p.write(".claude/harness.json", json.dumps({"models": {
            "_active_tier": "t", "tiers": {"t": {"fe-ux": "sonnet"}}, "floor": ["fe-ux"]}}))
        code, out, _ = self.out("fe-ux", step="1", isolated=False, model="haiku")
        self.assertEqual(code, 2)
        self.assertIn("runs on sonnet or stronger (models.floor in the harness config)", out)
        self.state(models={"fe-ux": "opus"})  # the user raised it for this run
        code, out, _ = self.out("fe-ux", step="1", isolated=False, model="sonnet")
        self.assertEqual(code, 2)
        self.assertIn("runs on opus or stronger", out)
        self.assertEqual(self.out("fe-ux", step="1", isolated=False, model="opus")[0], 0)

    def test_figma_lines_follow_the_runs_budget_not_a_team(self):
        code, out, _ = self.out("fe-ui", step="2", isolated=False)   # no budget in the state: no line asked
        self.assertEqual(code, 0, out)
        self.assertNotIn("figma_left", self.last("dispatch"))
        self.back("fe-ui", report="done\nfigma_calls: 3\n")
        self.assertEqual(self.last("return")["figma_calls"], 3)       # what the agent reported is kept
        self.cmd("land")
        self.state(figma={"budget": 40})
        code, out, _ = self.out("fe-ui", step="2", isolated=False)
        self.assertEqual(code, 2)
        self.assertIn("Budget: <Figma calls left of 40>", out)
        prompt = "You are fe-ui #2 — step 2b, round 1.\nTask: frames\nBudget: 37\n"
        self.assertEqual(self.auto("dispatch", {"tool_name": "Agent", "tool_input": {
            "subagent_type": "fe-ui", "prompt": prompt}})[0], 0)
        self.assertEqual(self.last("dispatch")["figma_left"], 37)
        self.back("fe-ui")
        self.assertEqual(self.last("return")["figma_calls"], 0)
        code, _, err = self.cmd("log", "dispatch", "--agent", "fe-ux", "--model", "opus", "--step", "1", "--note", "x")
        self.assertEqual(code, 2)
        self.assertIn("--figma-left", err)


# ---------- §1.3, §3.2: the log ----------

def d(seq, agent="be-developer", step="4", **more):
    return {"seq": seq, "event": "dispatch", "agent": agent, "phase": step, **more}


def r(seq, agent="be-developer", status="ok", **more):
    return {"seq": seq, "event": "return", "agent": agent, "status": status, **more}


def landed(seq, dispatch, result, agent="be-developer"):
    return {"seq": seq, "event": "land", "agent": agent, "dispatch": dispatch, "result": result}


class LogEvents(unittest.TestCase):
    def test_team_of(self):
        for agent, scope, team in (("fe-engineer", "backend", "fe"), ("fe-ux", "cross-stack", "fe"),
                                   ("be-analyst", "frontend", "fe"), ("be-analyst", "cross-stack", "be"),
                                   ("be-developer", "backend", "be"), ("be-developer", None, "be")):
            self.assertEqual(runlog.team_of(agent, scope), team, (agent, scope))

    def test_a_return_closes_the_dispatch_it_names_else_the_oldest(self):
        rows = runlog.dispatches([d(1), d(2), r(3, dispatch=2), r(4)])
        self.assertEqual([(x["dispatch"]["seq"], x["return"]["seq"]) for x in rows], [(1, 4), (2, 3)])
        rows = runlog.dispatches([d(1), d(2), r(3)])
        self.assertEqual([(x["dispatch"]["seq"], (x["return"] or {}).get("seq")) for x in rows], [(1, 3), (2, None)])

    def test_unlanded(self):
        seqs = lambda events: [x["seq"] for x in runlog.unlanded(events)]
        self.assertEqual(seqs([d(1)]), [])                                       # still out
        self.assertEqual(seqs([d(1), r(2)]), [1])
        self.assertEqual(seqs([d(1), r(2, status="blocked")]), [1])              # what it wrote is landed too
        self.assertEqual(seqs([d(1), r(2, status="failed")]), [])
        self.assertEqual(seqs([d(1, agent="be-reviewer"), r(2, agent="be-reviewer")]), [])  # not a writer
        for result in ("merged", "committed", "empty"):
            self.assertEqual(seqs([d(1), r(2), landed(3, 1, result)]), [], result)
        for result in ("conflict", "refused"):
            self.assertEqual(seqs([d(1), r(2), landed(3, 1, result)]), [1], result)
        self.assertEqual(seqs([d(1), r(2), landed(3, 1, "conflict"), landed(4, 1, "merged")]), [])
        self.assertEqual(seqs([d(1), d(2, isolated=True), r(3, dispatch=2), r(4), landed(5, 1, "committed")]), [2])
        self.assertEqual(seqs([d(1), d(2), r(3, dispatch=2), r(4, dispatch=1)]), [2, 1])    # oldest return first

    def test_who_is_out_in_the_runs_tree(self):
        out = lambda events: [x["seq"] for x in runlog.in_tree_out(events)]
        self.assertEqual(out([d(1), d(2, isolated=True), d(3, agent="be-reviewer")]), [1])
        self.assertEqual(out([d(1), r(2)]), [])

    def test_a_land_is_an_event_of_the_log(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            log = pathlib.Path(tmp) / "run-log.jsonl"
            runlog.append(log, "dispatch", agent="be-developer", model="opus", phase="4", note="x")
            with self.assertRaises(ConfigError):
                runlog.append(log, "land", agent="be-developer", dispatch=1, result="done")
            with self.assertRaises(ConfigError):
                runlog.append(log, "land", agent="be-developer", result="merged")
            ev = runlog.append(log, "land", agent="be-developer", dispatch=1, result="conflict",
                               paths=["src/a.ts"], note="met fe-engineer #1")
            self.assertEqual(runlog.problems(log), [])
            self.assertIn("land", runlog.VOIDABLE)
            row = next(l for l in runlog.timeline(log).splitlines() if "| land |" in l)
            for needle in ("be-developer", "lands #1", "src/a.ts", "conflict"):
                self.assertIn(needle, row)
            runlog.append(log, "void", voids=ev["seq"], by="orchestrator", note="wrong")
            self.assertEqual(runlog.problems(log), [])
            self.assertNotIn("land", [e["event"] for e in runlog.events(log)])

    def test_finishing_a_conflict_is_not_a_redo(self):
        redo = lambda events, agent="be-developer", step="4": auto.is_redo(events, agent, step, [])
        self.assertTrue(redo([d(1), r(2)]))
        self.assertTrue(redo([d(1), r(2), landed(3, 1, "merged")]))
        self.assertFalse(redo([d(1), r(2), landed(3, 1, "conflict")]))           # the round is not finished
        self.assertFalse(redo([d(1), r(2), landed(3, 1, "conflict"), landed(4, 1, "refused")]))
        self.assertTrue(redo([d(1), r(2), landed(3, 1, "conflict"), d(4), r(5), landed(6, 1, "merged")]))
        self.assertTrue(redo([d(1), r(2), landed(3, 1, "conflict")], step="5") is False)  # nothing at step 5 at all
        other = [d(1), r(2), d(3, agent="fe-engineer"), r(4, agent="fe-engineer"), landed(5, 3, "conflict", "fe-engineer")]
        self.assertTrue(redo(other))                                             # another type's conflict
        self.assertFalse(redo(other, agent="fe-engineer"))

    def test_the_brief_hash_ignores_whitespace(self):
        self.assertEqual(auto.brief_hash("You are x.\n\nTask:  a\n"), auto.brief_hash(" You are x. Task: a"))
        self.assertEqual(auto.brief_hash("a b"), hashlib.sha1(b"a b").hexdigest())
        self.assertNotEqual(auto.brief_hash("Only: Q-1"), auto.brief_hash("Only: Q-2"))


# ---------- §3.3: where a dispatched agent works ----------

class Where(Run):
    def test_one_writer_in_the_runs_tree_at_a_time(self):
        self.assertEqual(self.out("be-developer", isolated=False)[0], 0)
        self.assertEqual(self.last("mark")["role"], "be-developer")
        code, out, _ = self.out("be-tester", step="5", isolated=False)
        self.assertEqual(code, 2)
        for needle in ("one writer in the run's tree at a time", "be-developer (out)", "isolation: \"worktree\""):
            self.assertIn(needle, out)
        self.assertEqual(self.out("be-review-security", step="6", isolated=False)[0], 0)  # readers are not writers
        self.back("be-developer")
        code, out, _ = self.out("be-tester", step="5", isolated=False)
        self.assertEqual(code, 2)
        self.assertIn("be-developer (returned, not landed)", out)
        self.assertIn("gate.py land", out)
        self.assertEqual(self.cmd("land")[0], 0)
        self.assertEqual(self.out("be-tester", step="5", isolated=False)[0], 0)

    def test_an_isolated_writer_needs_the_base_setting_and_a_committed_tree(self):
        code, out, _ = self.out("fe-engineer")
        self.assertEqual(code, 2)
        self.assertIn("would start from the remote's default branch", out)
        self.assertIn("gate.py worktrees --setup", out)
        code, shown, _ = self.cmd("worktrees", "--setup")
        self.assertEqual(code, 0)
        self.assertIn('"baseRef": "head"', shown)
        self.p.write("calc/half.py", "X = 1\n")
        code, out, _ = self.out("fe-engineer")
        self.assertEqual(code, 2)
        self.assertIn("starts from the last commit: land or commit these first", out)
        self.assertIn(".claude/settings.json", out)
        self.assertIn("calc/half.py", out)
        self.assertNotIn("run-log.jsonl", out)  # the run's own books are no one's uncommitted work
        self.commit()
        n = len(self.p.events())
        code, out, prompt = self.out("fe-engineer")
        self.assertEqual(code, 0, out)
        ev = self.last()
        self.assertEqual((ev["event"], ev["isolated"], ev["head"]), ("dispatch", True, self.git("rev-parse", "HEAD")))
        self.assertEqual(ev["brief"], auto.brief_hash(prompt))
        self.assertEqual(len(self.p.events()), n + 1)  # no mark: nothing of the run's tree is its to change
        self.assertFalse((self.p.run / "gates" / "snap-fe-engineer.json").exists())

    def test_isolated_writers_are_out_together_and_keep_no_gate_waiting(self):
        self.isolation()
        self.assertEqual(self.out("fe-engineer", task="Q-1")[0], 0)
        self.assertEqual(self.out("fe-engineer", task="Q-2")[0], 0)   # two of one type
        self.assertEqual(self.out("be-developer")[0], 0)
        code, out, _ = self.p.gate("p1")
        self.assertEqual(code, 0, out)
        code, out, _ = self.out("be-tester", step="5", isolated=False)
        self.assertEqual(code, 2)
        self.assertIn("fe-engineer (out, isolated)", out)
        status = self.cmd("status")[1]
        self.assertEqual(status.count("· a worktree of its own · since"), 3)

    def test_an_isolated_writer_waits_for_the_one_in_the_tree(self):
        self.isolation()
        self.assertEqual(self.out("be-developer", isolated=False)[0], 0)
        code, out, _ = self.out("fe-engineer")
        self.assertEqual(code, 2)
        self.assertIn("a writer is out in the run's tree (be-developer · step 4)", out)

    def test_reviewers_are_never_isolated(self):
        self.isolation()
        for agent in ("be-review-security", "fe-reviewer"):
            code, out, _ = self.out(agent, step="6")
            self.assertEqual(code, 2, agent)
            self.assertIn("reviewers read the run's tree", out)

    def test_a_continued_isolated_author_goes_on_in_its_refreshed_worktree(self):
        self.isolation()
        self.assertEqual(self.out("be-developer")[0], 0)
        wt = self.worktree("w1")
        self.edit(wt, CORE, self.p.read(CORE) + "\n# w1\n")
        self.assertEqual(self.back("be-developer", "w1")[0], 0)
        self.assertEqual(self.cmd("land")[0], 0)
        self.p.write("calc/__init__.py", "# moved on\n")
        self.commit("the run's branch moves on")
        n = len(self.p.events())
        code, out = self.more("w1", to="be-developer")
        self.assertEqual(code, 0, out)
        ev = self.last("dispatch")
        self.assertEqual((ev["continued"], ev["isolated"], ev["worktree"], ev["agent_id"]),
                         (True, True, ".claude/worktrees/agent-w1", "w1"))
        self.assertEqual(len(self.p.events()), n + 1)  # no mark
        self.assertEqual(self.git("rev-parse", "HEAD", cwd=wt), self.git("rev-parse", "HEAD"))
        self.back("be-developer", "w1")
        self.assertEqual(self.last("return")["dispatch"], ev["seq"])
        self.assertEqual(self.cmd("land")[0], 0)
        self.git("worktree", "remove", "--force", str(wt))
        code, out = self.more("w1", to="be-developer")
        self.assertEqual(code, 2)
        self.assertIn("its worktree is gone: dispatch a fresh agent", out)

    def test_by_hand_an_isolated_dispatch_and_the_worktree_of_its_return(self):
        log = lambda *more: self.cmd("log", "dispatch", "--agent", "fe-engineer", "--model", "sonnet", "--step", "3",
                                     "--note", "by hand", *more)
        self.assertEqual(log("--isolated")[0], 0)
        self.assertTrue(self.last("dispatch")["isolated"])
        code, _, err = log()
        self.assertEqual(code, 2)
        self.assertIn("--isolated", err)
        self.assertEqual(log("--isolated")[0], 0)  # agents of one type out together, each in its own worktree
        wt = self.worktree("w9")
        ret = ("log", "return", "--agent", "fe-engineer", "--step", "3", "--status", "ok", "--note", "done")
        self.assertEqual(self.cmd(*ret, "--worktree", "nowhere")[0], 2)
        self.assertEqual(self.cmd(*ret, "--worktree", str(wt.relative_to(self.p.root)))[0], 0)
        self.assertEqual(self.last("return")["worktree"], ".claude/worktrees/agent-w9")
        code, _, err = self.cmd("log", "land", "--agent", "fe-engineer")
        self.assertEqual(code, 2)
        self.assertIn("written by the gates themselves", err)


# ---------- §3.4: returns ----------

class Returns(Run):
    def test_a_return_from_inside_a_worktree_finds_the_run_and_what_the_agent_changed(self):
        self.isolation()
        self.assertEqual(self.out("be-developer")[0], 0)
        wt = self.worktree("w1")
        self.edit(wt, CORE, self.p.read(CORE) + "\n# its work\n")
        self.edit(wt, "calc/extra.py", "A = 1\nB = 2\n")
        code, out = self.back("be-developer", "w1", report="user_visible: none\nhandoff: done", cwd=wt / "calc")
        self.assertEqual(code, 0, out)
        ev = self.last()
        self.assertEqual((ev["event"], ev["worktree"], ev["agent_id"]), ("return", ".claude/worktrees/agent-w1", "w1"))
        self.assertEqual(ev["changed"], {"added": 1, "modified": 1, "deleted": 0,
                                         "files": ["calc/extra.py (+2/-0)", "calc/core.py (+2/-0)"]})
        self.assertTrue((self.p.root / ev["report"]).is_file())                 # kept in the run's tree
        self.assertEqual(self.git("status", "--porcelain", "--", RUN, cwd=wt), "")  # nothing logged in the worktree
        self.assertIn("be-developer · step 4 · .claude/worktrees/agent-w1", self.cmd("status")[1])

    def test_the_cwd_is_the_worktree_when_no_directory_carries_the_agents_id(self):
        self.isolation()
        self.assertEqual(self.out("be-developer")[0], 0)
        self.git("worktree", "add", "-q", ".claude/worktrees/named-otherwise", "-b", "other")
        wt = self.p.root / ".claude/worktrees/named-otherwise"
        self.edit(wt, CORE, self.p.read(CORE) + "\n# its work\n")
        self.assertEqual(self.back("be-developer", "w1", cwd=wt)[0], 0)
        self.assertEqual(self.last("return")["worktree"], ".claude/worktrees/named-otherwise")
        self.cmd("land")
        self.assertEqual(self.out("be-developer", isolated=False)[0], 0)  # an in-tree writer's cwd is no worktree
        self.back("be-developer", "w2", cwd=wt)
        self.assertNotIn("worktree", self.last("return"))

    def test_an_isolated_agent_that_changed_nothing_leaves_no_worktree(self):
        self.isolation()
        self.assertEqual(self.out("be-developer")[0], 0)
        self.assertEqual(self.back("be-developer", "w1")[0], 0)
        ev = self.last("return")
        self.assertNotIn("worktree", ev)
        self.assertEqual(ev["changed"], {"added": 0, "modified": 0, "deleted": 0, "files": []})
        code, out, _ = self.cmd("land")
        self.assertEqual((code, self.last("land")["result"]), (0, "empty"), out)
        code, out = self.more("w1", to="be-developer")   # nowhere left to go on
        self.assertEqual(code, 2)
        self.assertIn("its worktree is gone: dispatch a fresh agent", out)

    def test_the_stop_events_own_message_is_the_report_when_no_transcript_can_be_read(self):
        self.assertEqual(self.out("be-developer", task="build the add function", isolated=False)[0], 0)
        self.p.write(CORE, self.p.read(CORE) + "\n# its work\n")
        report = "user_visible: `calc add` prints the sum\nblocked_on: []\nhandoff: be-developer #1 · 4 · round 1\n"
        code, out = self.auto("return", {"hook_event_name": "SubagentStop", "agent_type": "be-developer",
                                         "agent_transcript_path": str(self.tmp / "missing.jsonl"),
                                         "last_assistant_message": report})
        self.assertEqual(code, 0, out)
        ev = self.last("return")
        self.assertEqual((ev["status"], ev["note"], ev["visible"]),
                         ("ok", "be-developer #1 · 4 · round 1", "`calc add` prints the sum"))
        self.assertEqual(self.p.read(ev["report"]), report)
        self.assertEqual(ev["changed"]["modified"], 1)
        self.assertNotIn("context", ev)                 # no transcript: no usage, and nothing made up
        self.assertEqual([x["seq"] for x in runlog.unlanded(self.p.events())], [ev["dispatch"]])
        code, shown, err = self.cmd("land")
        self.assertEqual(code, 0, shown + err)
        self.assertIn("be-developer #1 · committed", shown)
        self.assertEqual(self.git("status", "--porcelain", "--", "calc"), "")

    def test_two_of_a_type_each_close_their_own_dispatch(self):
        self.isolation()
        _, _, first = self.out("fe-engineer", task="Q-1")
        _, _, second = self.out("fe-engineer", task="Q-2")
        seq = {ev["note"]: ev["seq"] for ev in self.p.events() if ev["event"] == "dispatch"}
        self.assertEqual(self.back("fe-engineer", "w2", prompt=second)[0], 0)   # the later one is back first
        self.assertEqual(self.last("return")["dispatch"], seq["Q-2"])
        rows = {x["dispatch"]["seq"]: x["return"] for x in runlog.dispatches(self.p.events())}
        self.assertIsNone(rows[seq["Q-1"]])
        self.assertEqual(self.back("fe-engineer", "w1", prompt=first)[0], 0)
        self.assertEqual(self.last("return")["dispatch"], seq["Q-1"])
        self.out("fe-engineer", task="Q-3")
        self.out("fe-engineer", task="Q-4")
        self.back("fe-engineer", "w3", prompt="a brief no dispatch was sent")
        self.assertEqual(self.last("return")["dispatch"], seq_of(self, "Q-3"))  # no match: the oldest, as before


def seq_of(case, note):
    return next(ev["seq"] for ev in case.p.events() if ev["event"] == "dispatch" and ev["note"] == note)


# ---------- §3.5, §3.6: land, worktrees, the busy rule ----------

class Land(Run):
    def test_an_in_tree_writer_is_committed_and_gates_wait_until_then(self):
        self.assertEqual(self.out("be-developer", task="build the add function", isolated=False)[0], 0)
        self.assertEqual(self.p.gate("p1")[0], 4)
        self.p.write(CORE, self.p.read(CORE) + "\n# more\n")
        self.p.write("calc/extra.py", "A = 1\n")
        self.back("be-developer")
        code, out, _ = self.p.gate("p1")
        self.assertEqual(code, 4)
        self.assertIn("returned and not landed: be-developer · step 4", out)
        self.assertIn("gate.py land", out)
        self.assertIn("be-developer · step 4 · in tree", self.cmd("status")[1].split("Returned, not landed")[1])
        for command in ("status", "stats", "timeline"):  # never busy
            self.assertEqual(self.cmd(command)[0], 0, command)
        self.assertEqual(self.cmd("check", "p1")[0], 0)
        code, out, err = self.cmd("land")
        self.assertEqual(code, 0, out + err)
        self.assertRegex(out.strip(), r"^\[land\] be-developer #1 · committed [0-9a-f]{7} · \d+ files$")
        ev = self.last("land")
        dispatch = seq_of(self, "build the add function")
        self.assertEqual((ev["agent"], ev["dispatch"], ev["result"], ev["commit"]),
                         ("be-developer", dispatch, "committed", self.git("rev-parse", "HEAD")))
        self.assertEqual(self.git("log", "-1", "--format=%s"), "be-developer #1 · step 4 · build the add function")
        self.assertEqual(self.git("status", "--porcelain", "--", "calc"), "")
        self.assertEqual(self.cmd("land"), (0, "[land] nothing to land\n", ""))
        self.assertEqual(self.p.gate("p1")[0], 0)
        self.assertIn("Returned, not landed (`gate.py land`):\n  none", self.cmd("status")[1])

    def test_land_waits_only_for_a_writer_out_in_the_tree(self):
        self.isolation()
        self.assertEqual(self.out("fe-engineer")[0], 0)
        self.assertEqual(self.cmd("land")[0], 0)        # an isolated writer out keeps nothing waiting
        self.back("fe-engineer", "w1")
        self.cmd("land")
        self.assertEqual(self.out("be-developer", isolated=False)[0], 0)
        code, _, err = self.cmd("land")
        self.assertEqual(code, 4)
        self.assertIn("BUSY: a writer is out in the run's tree (be-developer · step 4)", err)

    def two(self, first, second):
        """Two isolated be-developers back from their worktrees, each with its own version of calc/core.py."""
        self.isolation()
        self.out("be-developer", task="one")
        self.out("be-developer", task="two")
        for aid, task, text in (("w1", "one", first), ("w2", "two", second)):
            wt = self.worktree(aid)
            self.edit(wt, CORE, text)
            self.assertEqual(self.back("be-developer", aid, prompt=f"You are be-developer #1 — step 4, round 1.\nTask: {task}\n")[0], 0)

    def test_isolated_writers_are_merged_one_by_one(self):
        core = self.p.read(CORE)
        self.two("# top\n" + core, core + "\n# bottom\n")
        code, out, _ = self.cmd("land", "--seq", str(seq_of(self, "two")))
        self.assertEqual(code, 0, out)
        self.assertRegex(out.strip(), r"^\[land\] be-developer #2 · merged [0-9a-f]{7} · 1 files$")
        self.assertEqual([x["seq"] for x in runlog.unlanded(self.p.events())], [seq_of(self, "one")])
        code, out, _ = self.cmd("land", "--agent", "fe-engineer")
        self.assertEqual((code, out), (0, "[land] nothing to land\n"))
        code, out, _ = self.cmd("land", "--agent", "be-developer")
        self.assertEqual(code, 0, out)
        self.assertIn("be-developer #1 · merged", out)
        self.assertEqual(self.p.read(CORE), "# top\n" + core + "\n# bottom\n")
        self.assertEqual(self.last("land")["commit"], self.git("rev-parse", "HEAD"))
        listed = self.cmd("worktrees")[1]
        for aid in ("w1", "w2"):
            self.assertIn(f".claude/worktrees/agent-{aid} · be-developer · landed", listed)
        code, out, _ = self.cmd("worktrees", "--clean")
        self.assertEqual(code, 0)
        self.assertIn("removed: .claude/worktrees/agent-w1, .claude/worktrees/agent-w2", out)
        self.assertFalse((self.p.root / ".claude/worktrees/agent-w1").exists())
        self.assertIn("[worktrees] none", self.cmd("worktrees")[1])

    def test_a_conflict_is_its_authors_to_finish_and_exits_1(self):
        core = self.p.read(CORE)
        self.two(core.replace("a + b", "b + a"), core.replace("a + b", "sum((a, b))"))
        code, out, _ = self.cmd("land")
        self.assertEqual(code, 1, out)
        first, second = out.strip().splitlines()
        self.assertIn("be-developer #1 · merged", first)
        self.assertIn("be-developer #2 · conflict: calc/core.py (met be-developer #1) · owner: be-developer", second)
        ev = self.last("land")
        self.assertEqual((ev["result"], ev["paths"], ev["dispatch"]), ("conflict", [CORE], seq_of(self, "two")))
        self.assertIn("last land: conflict (calc/core.py)", self.cmd("status")[1])
        self.assertIn(".claude/worktrees/agent-w2 · be-developer · conflict", self.cmd("worktrees")[1])
        self.assertEqual(self.p.gate("p1")[0], 4)       # its work is not on the run's branch yet
        code, out = self.more("w2", to="be-developer", message="You are {a} #2 — step 4, round 1.\nTask: two")
        self.assertEqual(code, 0, out)
        self.assertNotIn("redo", self.last("dispatch"))  # finishing its round, not redoing it
        wt = self.p.root / ".claude/worktrees/agent-w2"
        self.edit(wt, CORE, core.replace("a + b", "sum((b, a))"))
        self.back("be-developer", "w2")
        code, out, _ = self.cmd("land")
        self.assertEqual(code, 0, out)
        self.assertIn("merged", out)
        self.assertIn("sum((b, a))", self.p.read(CORE))
        self.assertEqual(runlog.unlanded(self.p.events()), [])

    def test_a_role_refusal_commits_nothing_and_exits_1(self):
        self.isolation()
        self.out("be-developer")
        wt = self.worktree("w1")
        self.edit(wt, f"{RUN}/gates/p4-latest.json", '{"overall": "pass"}')   # a forged report
        self.back("be-developer", "w1")
        head = self.git("rev-parse", "HEAD")
        code, out, _ = self.cmd("land")
        self.assertEqual(code, 1, out)
        self.assertIn(f"refused: {RUN}/gates/p4-latest.json", out)
        self.assertIn("owner: be-developer", out)
        self.assertEqual(self.git("rev-parse", "HEAD"), head)
        self.assertEqual((self.last("land")["result"], self.last("land")["owner"]), ("refused", "be-developer"))

    def test_outside_git_a_land_records_that_there_is_nothing_to_commit(self):
        import shutil
        shutil.rmtree(self.p.root / ".git")
        self.assertEqual(self.out("be-developer", isolated=False)[0], 0)
        self.back("be-developer")
        code, out, err = self.cmd("land")
        self.assertEqual(code, 0, out + err)
        self.assertEqual(self.last("land")["result"], "empty")
        self.assertIn("not a git repository", out)
        self.assertEqual(self.p.gate("p1")[0], 0)


class Worktrees(Run):
    def test_setup_needs_no_run_and_keeps_what_the_settings_hold(self):
        self.state(status="accepted")
        self.p.write(".claude/settings.json", json.dumps({"permissions": {"allow": ["Bash(ls:*)"]},
                                                          "worktree": {"symlinkDirectories": ["node_modules"]}}))
        code, out, err = self.cmd("worktrees", "--setup", "--link", ".venv", "node_modules")
        self.assertEqual(code, 0, err)
        self.assertIn("Restart the session", out)
        settings = json.loads(self.p.read(".claude/settings.json"))
        self.assertEqual(settings["permissions"], {"allow": ["Bash(ls:*)"]})
        self.assertEqual(settings["worktree"], {"symlinkDirectories": ["node_modules", ".venv"], "baseRef": "head"})

    def test_a_setting_written_while_an_agent_is_out_is_not_the_agents(self):
        self.assertEqual(self.out("be-review-security", step="6", isolated=False)[0], 0)
        self.assertEqual(self.cmd("worktrees", "--setup")[0], 0)
        self.back("be-review-security", report="candidates: none")
        self.assertNotIn("control_changed", self.last("return"))

    def test_check_runs_inside_a_worktree_on_its_own_documents(self):
        self.isolation()
        self.out("be-analyst", step="1", rnd=2)
        wt = self.worktree("w1")
        self.edit(wt, f"{RUN}/01-requirements.md", NO_CUT)
        r = subprocess.run([PY, str(GATE), "check", "p1", "--project", str(wt)], capture_output=True, text=True,
                           env=self.env)
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("[FAIL] P1.cut-line", r.stdout)
        self.assertEqual(self.cmd("check", "p1")[0], 0)  # the run's tree still holds the document as it was
        self.assertEqual(self.git("status", "--porcelain", cwd=wt), f"M {RUN}/01-requirements.md")  # nothing written

    def test_status_names_the_scope_and_the_roles_it_takes(self):
        self.state(scope="cross-stack")
        out = self.cmd("status")[1]
        self.assertIn("docs/runs/calc: tier small · scope cross-stack · step 1 · in_progress", out)
        for role in ("be-developer: #1", "fe-engineer: #1", "be-analyst: #2"):
            self.assertIn(role, out)
        self.state(scope="frontend")
        roles = self.cmd("status")[1].split("Next ordinal")[1]
        self.assertIn("fe-ux: #1", roles)
        self.assertIn("be-analyst: #2", roles)       # seen in this run
        self.assertNotIn("be-developer", roles)


if __name__ == "__main__":
    unittest.main()
