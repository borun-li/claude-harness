#!/usr/bin/env python3
"""run-log.py: dispatches and returns are logged by a hook, not from memory. Run: ``python3 <this file>``;
the exit code is the result.

The logic itself (marks, the log, the round cap, writers and worktrees) is tested in gates/tests; this
tests the hook layer only: a refusal is a PreToolUse deny, a return never blocks, unreadable input
is harmless, nothing is logged outside a run, the payload's cwd alone says which project.
"""
import json
import pathlib
import subprocess
import sys
import tempfile

HOOK = pathlib.Path(__file__).resolve().parent / "run-log.py"
GATE = HOOK.parent.parent / "gates" / "gate.py"
RUN = pathlib.Path("docs") / "runs" / "demo"


def run(mode, payload):
    raw = payload if isinstance(payload, str) else json.dumps(payload)
    # run from a directory that is no project: only the payload's cwd may say where the run is
    p = subprocess.run([sys.executable, str(HOOK), mode], input=raw, capture_output=True, text=True,
                       cwd=tempfile.gettempdir())
    return p.returncode, p.stdout


def main() -> int:
    failures = cases = 0

    def expect(label, ok):
        nonlocal failures, cases
        cases += 1
        if not ok:
            failures += 1
            print("FAIL", label)

    with tempfile.TemporaryDirectory() as d:
        root = pathlib.Path(d)
        run_dir = root / RUN
        run_dir.mkdir(parents=True)
        (run_dir / "state.json").write_text(json.dumps({"status": "in_progress", "goal": {}}))

        def agent(prompt, kind="be-developer"):
            return {"cwd": d, "hook_event_name": "PreToolUse", "tool_name": "Agent",
                    "tool_input": {"subagent_type": kind, "prompt": prompt, "model": "sonnet"}}

        def events():
            log = run_dir / "run-log.jsonl"
            return [json.loads(l) for l in log.read_text().splitlines()] if log.exists() else []

        code, out = run("dispatch", agent("Build it."))
        deny = json.loads(out)["hookSpecificOutput"] if out.strip() else {}
        expect("no step → deny", code == 0 and deny.get("permissionDecision") == "deny"
               and "step" in deny.get("permissionDecisionReason", ""))
        expect("denied dispatch not logged", events() == [])

        code, out = run("dispatch", agent("You are be-developer #1 — step 4, round 1.\nTask: build"))
        expect("dispatch allowed silently", code == 0 and out.strip() == "")
        expect("mark and dispatch logged", [e["event"] for e in events()] == ["mark", "dispatch"])

        code, out = run("dispatch", agent("You are general-purpose #1 — step 4, round 1.", "general-purpose"))
        expect("other agents untouched", code == 0 and out.strip() == "" and len(events()) == 2)

        transcript = root / "t.jsonl"
        transcript.write_text(json.dumps({"message": {"role": "assistant", "content": [
            {"type": "text", "text": "files_changed: [a.py]\nhandoff: be-developer #1"}]}}) + "\n")
        code, out = run("return", {"cwd": d, "hook_event_name": "SubagentStop", "agent_type": "be-developer",
                                   "agent_transcript_path": str(transcript)})
        expect("return logged, never blocks", code == 0 and out.strip() == "" and events()[-1]["event"] == "return")

        code, out = run("dispatch", agent("You are be-developer #2 — step 4, round 2.\nTask: fix"))
        why = (json.loads(out)["hookSpecificOutput"] if out.strip() else {}).get("permissionDecisionReason", "")
        expect("a second writer before the first is landed → deny, naming `gate.py land`",
               "gate.py land" in why and events()[-1]["event"] == "return")
        landed = subprocess.run([sys.executable, str(GATE), "land", "--project", d], capture_output=True, text=True)
        expect("the orchestrator lands the return", landed.returncode == 0 and events()[-1]["event"] == "land")
        code, out = run("dispatch", agent("You are be-developer #2 — step 4, round 2.\nTask: fix"))
        expect("once landed, the next writer is dispatched", code == 0 and out.strip() == ""
               and events()[-1]["event"] == "dispatch")
        run("report", {"cwd": d, "hook_event_name": "PreToolUse", "tool_name": "SubagentHandback",
                       "agent_id": "a9", "tool_input": {"message": "blocked_on: [DES-2 unclear]\nhandoff: kept"}})
        code, out = run("return", {"cwd": d, "hook_event_name": "SubagentStop", "agent_type": "be-developer",
                                   "agent_id": "a9", "agent_transcript_path": str(root / "not-written-yet.jsonl")})
        last = events()[-1]
        expect("report kept at the handback is used", (last["status"], last["note"]) == ("blocked", "kept"))

        code, out = run("return", "not json")
        expect("unreadable input is harmless", code == 0 and out.strip() == "")

        (run_dir / "state.json").write_text(json.dumps({"status": "accepted"}))
        n = len(events())
        run("dispatch", agent("You are be-developer #2 — step 4, round 2."))
        expect("settled run: nothing logged", len(events()) == n)

    with tempfile.TemporaryDirectory() as d:  # the log cannot be written: say so, never stay silent
        (pathlib.Path(d) / RUN).mkdir(parents=True)
        (pathlib.Path(d) / RUN / "state.json").write_text(json.dumps({"status": "in_progress"}))
        (pathlib.Path(d) / RUN / "run-log.jsonl").mkdir()
        code, out = run("dispatch", {"cwd": d, "hook_event_name": "PreToolUse", "tool_name": "Agent", "tool_input": {
            "subagent_type": "be-tester", "prompt": "You are be-tester #1 — step 4, round 1."}})
        o = json.loads(out) if out.strip() else {}
        expect("unlogged dispatch: allowed, reported to user and orchestrator",
               code == 0 and "NOT written" in o.get("systemMessage", "")
               and "NOT written" in o.get("hookSpecificOutput", {}).get("additionalContext", "")
               and "permissionDecision" not in o.get("hookSpecificOutput", {}))

    # An isolated writer: dispatched from the main checkout, returning from inside its worktree,
    # landed by the orchestrator. A real repository and a real `git worktree add`.
    with tempfile.TemporaryDirectory() as d:
        root = pathlib.Path(d).resolve() / "proj"
        files = {RUN / "state.json": json.dumps({"status": "in_progress", "goal": {}}),
                 RUN / "plan.md": "Files: `src/a.py`\n", pathlib.Path("src/a.py"): "A = 1\n",
                 pathlib.Path(".claude/settings.json"): json.dumps({"worktree": {"baseRef": "head"}})}
        for rel, text in files.items():
            (root / rel).parent.mkdir(parents=True, exist_ok=True)
            (root / rel).write_text(text)

        def git(*args, cwd=root):
            return subprocess.run(["git", "-c", "user.email=t@t", "-c", "user.name=t", "-c", "commit.gpgsign=false",
                                   *args], cwd=cwd, capture_output=True, text=True, check=True).stdout.strip()

        git("init", "-q", "-b", "main")
        git("config", "user.email", "t@t")
        git("config", "user.name", "t")
        git("add", "-A")
        git("commit", "-qm", "init")

        def events():
            log = root / RUN / "run-log.jsonl"
            return [json.loads(l) for l in log.read_text().splitlines()] if log.exists() else []

        code, out = run("dispatch", {"cwd": str(root / "src"), "hook_event_name": "PreToolUse", "tool_name": "Agent",
                                     "tool_input": {"subagent_type": "be-developer", "model": "sonnet", "isolation": "worktree",
                                                    "prompt": "You are be-developer #1 — step 4, round 1.\nTask: build a"}})
        evs = events()
        expect("isolated dispatch: allowed, logged as isolated with the run's head, no mark",
               code == 0 and out.strip() == "" and [e["event"] for e in evs] == ["dispatch"]
               and evs[0].get("isolated") is True and evs[0].get("head") == git("rev-parse", "HEAD"))
        wt = root / ".claude" / "worktrees" / "agent-w1"
        git("worktree", "add", "-q", str(wt), "-b", "worktree-agent-w1")
        (wt / "src" / "a.py").write_text("A = 2\n")
        transcript = pathlib.Path(d) / "t.jsonl"
        transcript.write_text(json.dumps({"message": {"role": "assistant", "content": [
            {"type": "text", "text": "files_changed: [src/a.py]\nhandoff: be-developer #1"}]}}) + "\n")
        code, out = run("return", {"cwd": str(wt / "src"), "hook_event_name": "SubagentStop", "agent_type": "be-developer",
                                   "agent_id": "w1", "agent_transcript_path": str(transcript)})
        last = events()[-1] if events() else {}
        expect("a return fired inside the worktree is logged in the main checkout's run, with its worktree",
               code == 0 and out.strip() == "" and last.get("event") == "return"
               and last.get("worktree") == ".claude/worktrees/agent-w1" and (last.get("changed") or {}).get("modified") == 1)
        expect("nothing was logged inside the worktree", not (wt / RUN / "run-log.jsonl").exists())
        landed = subprocess.run([sys.executable, str(GATE), "land", "--project", str(root)], capture_output=True, text=True)
        expect("land merges the worktree's work into the run's branch",
               landed.returncode == 0 and "merged" in landed.stdout and (root / "src" / "a.py").read_text() == "A = 2\n"
               and git("log", "-1", "--format=%s").startswith("be-developer #1 · step 4 · build a")
               and events()[-1].get("result") == "merged")

    print("%d cases, %d failures" % (cases, failures))
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
