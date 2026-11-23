#!/usr/bin/env python3
"""Regression matrix of ``no-agent-continuation.py``. Run: ``python3 <this file>``; the exit code is the result.

**The ALLOW cases matter as much as the DENY cases.** This hook sits on every SendMessage; if it
denied an agent outside this harness, an agent still running, or an author's fix round, it would
be switched off.
"""
import json
import pathlib
import shutil
import subprocess
import sys
import tempfile

HOOK = pathlib.Path(__file__).with_name("no-agent-continuation.py")


def output(transcript, to, tool="SendMessage", cwd="/nonexistent", hook=HOOK, message="x"):
    return subprocess.run(
        [sys.executable, str(hook)],
        input=json.dumps({"hook_event_name": "PreToolUse", "tool_name": tool, "transcript_path": str(transcript),
                          "cwd": str(cwd), "tool_input": {"to": to, "message": message}}),
        capture_output=True, text=True, check=True,
    ).stdout.strip()


def reason(out):
    """The denial text, or "" when the call was allowed."""
    spec = json.loads(out).get("hookSpecificOutput", {}) if out else {}
    return spec.get("permissionDecisionReason", "") if spec.get("permissionDecision") == "deny" else ""


def run(transcript, to, **kw):
    return bool(reason(output(transcript, to, **kw)))


def main() -> int:
    failures = cases = 0

    def expect(label, got, want_deny):
        nonlocal failures, cases
        cases += 1
        if got != want_deny:
            failures += 1
            print("FAIL %s: want=%s got=%s" % (label, "DENY" if want_deny else "ALLOW",
                                              "DENY" if got else "ALLOW"))

    def true(label, ok):
        nonlocal failures, cases
        cases += 1
        if not ok:
            failures += 1
            print("FAIL", label)

    with tempfile.TemporaryDirectory() as d:
        transcript = pathlib.Path(d) / "session.jsonl"
        transcript.write_text("")
        sub = pathlib.Path(d) / "session" / "subagents"
        sub.mkdir(parents=True)

        def agent(aid, kind, finished=True, **more):
            (sub / f"agent-{aid}.meta.json").write_text(json.dumps({"agentType": kind, "finished": finished, **more}))

        def usage(aid, *sizes):
            (sub / f"agent-{aid}.jsonl").write_text("".join(json.dumps({"type": "assistant", "message": {
                "usage": {"input_tokens": 2, "cache_creation_input_tokens": 0, "cache_read_input_tokens": s}}})
                + "\n" for s in sizes))

        # An author (be-tester writes the tests): continued round after round; the round cap is the
        # run log's, not a count kept here.
        agent("a1", "be-tester")
        for n in range(1, 5):
            expect("author be-tester continuation %d" % n, run(transcript, "a1"), False)
        true("an author has no continuation counter", not (sub / "agent-a1.continuations").exists())
        # An author's context: the last request counts, not the peak.
        agent("a5", "be-developer")
        usage("a5", 250000, 90000)
        expect("author with a small last context", run(transcript, "a5"), False)
        agent("a6", "fe-ux")
        usage("a6", 90000, 210000)
        why = reason(output(transcript, "a6"))
        true("author over the context limit: denied, in English, with the size and what to do",
             "Constitution §8.1" in why and "210002 tokens" in why and "loops.continue_max_context" in why
             and "Start a fresh fe-ux" in why)
        # The project overrides the limit.
        proj = pathlib.Path(d) / "proj"
        (proj / ".claude").mkdir(parents=True)
        (proj / ".claude" / "harness.json").write_text(json.dumps({"loops": {"continue_max_context": 50000}}))
        expect("project limit, over it", run(transcript, "a5", cwd=proj), True)
        # A size that cannot be read is unknown, not 0: allowed, whatever the limit.
        (proj / ".claude" / "harness.json").write_text(json.dumps({"loops": {"continue_max_context": -1}}))
        agent("a7", "be-architect")
        expect("no transcript: size unknown", run(transcript, "a7", cwd=proj), False)
        (sub / "agent-a7.jsonl").write_text('{"message": {"usage": \n')
        expect("unreadable transcript: size unknown", run(transcript, "a7", cwd=proj), False)
        usage("a7", 10)
        true("a size that was read is never reported as unknown",
             "12 tokens" in reason(output(transcript, "a7", cwd=proj)))
        # An agent still running: a word within its round, never counted.
        agent("a2", "fe-engineer", finished=False)
        expect("running fe-engineer", run(transcript, "a2"), False)
        expect("running fe-engineer again", run(transcript, "a2"), False)
        # Agents outside this harness are not this hook's business.
        agent("a3", "Explore")
        expect("Explore", run(transcript, "a3"), False)
        expect("Explore again", run(transcript, "a3"), False)
        # A judge (not an author): continued once, to receive an answer; addressed by name, with a [ref].
        agent("a4", "fe-critic", name="critic-1")
        expect("named judge first", run(transcript, "critic-1 [3fa9c1]"), False)
        why = reason(output(transcript, "critic-1"))
        true("named judge second: denied, a judge is fresh every round", "continued once already" in why)
        # A target that is not found, main, a tool other than SendMessage.
        expect("unknown agent", run(transcript, "zzz"), False)
        expect("main", run(transcript, "main"), False)
        expect("other tool", run(transcript, "a1", tool="Bash"), False)

        # Inside a run: an allowed continuation is written to the run log at once (PreToolUse,
        # while the meta file still says finished).
        proj2 = pathlib.Path(d) / "proj2"
        run_dir = proj2 / "docs" / "runs" / "demo"
        run_dir.mkdir(parents=True)
        (run_dir / "state.json").write_text(json.dumps({"status": "in_progress", "goal": {}}))
        gate = HOOK.parent.parent / "gates" / "gate.py"

        def log_by_hand(agent_type, step, *ev):
            subprocess.run([sys.executable, str(gate), "log", ev[0], "--agent", agent_type, "--step", step, *ev[1:],
                            "--project", str(proj2)], capture_output=True, check=True)

        def returned_and_landed():  # a writer's round is over once its return is on the run's branch
            log_by_hand("be-developer", "4", *done)
            subprocess.run([sys.executable, str(gate), "land", "--project", str(proj2)], capture_output=True, check=True)

        done = ["return", "--status", "ok", "--note", "x"]
        agent("a8", "be-developer")
        out = output(transcript, "a8", cwd=proj2, message="You are be-developer #1 — step 4, round 2.\nOnly: TC-001")
        log = run_dir / "run-log.jsonl"
        evs = [json.loads(line) for line in log.read_text().split("\n") if line] if log.exists() else []
        expect("continuation in a run: allowed", bool(out), False)
        true("continuation in a run: logged as a continued round",
             bool(evs) and evs[-1]["event"] == "dispatch" and evs[-1].get("continued") and evs[-1].get("redo") == 1)
        why = reason(output(transcript, "a8", cwd=proj2, message="Please fix it."))
        true("a second writer in the run's tree while the first is out: the run log's refusal is relayed",
             "one writer in the run's tree" in why)
        returned_and_landed()
        out = output(transcript, "a8", cwd=proj2, message="Please fix it.")  # no step: an answer, same step
        expect("continuation without a step: allowed", bool(reason(out)), False)
        # The rounds of TC-001 are used up (another be-developer redid it at step 4): the run log
        # refuses, the hook relays the refusal.
        agent("a9", "be-developer")
        returned_and_landed()
        log_by_hand("be-developer", "4", "dispatch", "--model", "opus", "--note", "fix", "--redo", "--items", "TC-001")
        returned_and_landed()
        why = reason(output(transcript, "a9", cwd=proj2,
                            message="You are be-developer #2 — step 4, round 3.\nOnly: TC-001"))
        true("continuation past the round cap: the run log's refusal is relayed", "ROUND CAP" in why)
        # A judge the run log refuses has not used its one continuation.
        agent("j1", "be-reviewer")
        for ev in (["dispatch", "--model", "opus", "--note", "review"], done,
                   ["dispatch", "--model", "opus", "--note", "again", "--redo"], done,
                   ["dispatch", "--model", "opus", "--note", "again", "--redo"], done):
            log_by_hand("be-reviewer", "5", *ev)
        why = reason(output(transcript, "j1", cwd=proj2, message="You are be-reviewer #1 — step 5, round 4."))
        true("refused judge: the run log's refusal is relayed", "ROUND CAP" in why)
        true("refused judge not counted", not (sub / "agent-j1.continuations").exists())

    # The three layers of the one harness config, in a harness root of their own: the harness
    # default, the user's own defaults (harness-local), the project.
    with tempfile.TemporaryDirectory() as d:
        root = pathlib.Path(d) / "harness"
        for part in ("hooks", "harness", "backend", "harness-local"):
            (root / part).mkdir(parents=True)
        hook = pathlib.Path(shutil.copy(HOOK, root / "hooks"))
        transcript = pathlib.Path(d) / "session.jsonl"
        transcript.write_text("")
        sub = pathlib.Path(d) / "session" / "subagents"
        sub.mkdir(parents=True)
        (sub / "agent-b1.meta.json").write_text(json.dumps({"agentType": "be-developer", "finished": True}))
        (sub / "agent-b1.jsonl").write_text(json.dumps({"message": {"usage": {"input_tokens": 100000}}}) + "\n")
        proj = pathlib.Path(d) / "proj"
        (proj / ".claude").mkdir(parents=True)

        def layers(default, local=None, project=None):
            for path, value in ((root / "harness" / "config.json", default),
                                (root / "harness-local" / "config.json", local),
                                (proj / ".claude" / "harness.json", project)):
                if value is None:
                    path.unlink() if path.exists() else None
                else:
                    path.write_text(json.dumps({"loops": {"continue_max_context": value}}))
            return run(transcript, "b1", cwd=proj, hook=hook)

        expect("harness default above the size", layers(150000), False)
        expect("harness default below the size", layers(50000), True)
        expect("the user's own default overrides the harness default", layers(50000, local=150000), False)
        expect("the user's own default, below the size", layers(150000, local=50000), True)
        expect("the project overrides both", layers(50000, local=50000, project=150000), False)
        expect("the project, below the size", layers(150000, local=150000, project=50000), True)
        # The per-team files of the layout before 16.0.0 are not read any more.
        for old in (root / "backend" / "config.json", root / "harness-local" / "backend.json",
                    proj / ".claude" / "backend.json"):
            old.write_text(json.dumps({"loops": {"continue_max_context": 50000}}))
        expect("a per-team config file is not read", layers(150000), False)
        # A layer that sets another key of `loops` keeps the limit of the layer below.
        layers(50000)
        (proj / ".claude" / "harness.json").write_text(json.dumps({"loops": {"max_rounds": 3}}))
        expect("a layer without the key keeps the one below", run(transcript, "b1", cwd=proj, hook=hook), True)

    # Unreadable input.
    out = subprocess.run([sys.executable, str(HOOK)], input="not json",
                         capture_output=True, text=True, check=True).stdout.strip()
    expect("bad input", bool(out), False)

    print("%d cases, %d failures" % (cases, failures))
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
