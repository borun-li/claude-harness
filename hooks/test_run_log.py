#!/usr/bin/env python3
"""run-log.py：派工与返回由钩子记，不靠记性。跑法：``python3 <本文件>``，退出码即结果。

逻辑本身（标记、日志、轮次上限、并发写入者）在 gates/tests 里测；这里只测钩子这一层：
拒绝时输出 PreToolUse 的 deny、返回永不阻塞、读不懂的输入不出错、不在 run 里什么都不记。
"""
import json
import pathlib
import subprocess
import sys
import tempfile

HOOK = pathlib.Path(__file__).resolve().parent / "run-log.py"


def run(mode, payload):
    raw = payload if isinstance(payload, str) else json.dumps(payload)
    p = subprocess.run([sys.executable, str(HOOK), mode], input=raw, capture_output=True, text=True)
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
        run_dir = root / "docs" / "backend"
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

        run("dispatch", agent("You are be-developer #2 — step 4, round 2.\nTask: fix"))
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

    print("%d cases, %d failures" % (cases, failures))
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
