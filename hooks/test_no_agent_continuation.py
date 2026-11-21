#!/usr/bin/env python3
"""``no-agent-continuation.py`` 的回归矩阵。跑法：``python3 <本文件>``，退出码即结果。

**放行用例和拦截用例同等重要。** 这个钩子挂在每一次 SendMessage 上；它要是拦了
与本 harness 无关的代理、还在运行的代理，或第一次（合规的）续用，就会被关掉。
"""
import json
import pathlib
import subprocess
import sys
import tempfile

HOOK = pathlib.Path(__file__).with_name("no-agent-continuation.py")


def run(transcript: pathlib.Path, to: str, tool: str = "SendMessage", cwd: str = "/nonexistent") -> bool:
    out = subprocess.run(
        [sys.executable, str(HOOK)],
        input=json.dumps({"tool_name": tool, "transcript_path": str(transcript), "cwd": cwd,
                          "tool_input": {"to": to, "message": "x"}}),
        capture_output=True, text=True, check=True,
    ).stdout.strip()
    return bool(out) and json.loads(out)["hookSpecificOutput"]["permissionDecision"] == "deny"


def main() -> int:
    failures = cases = 0

    def expect(label, got, want_deny):
        nonlocal failures, cases
        cases += 1
        if got != want_deny:
            failures += 1
            print("FAIL %s: want=%s got=%s" % (label, "DENY" if want_deny else "ALLOW",
                                              "DENY" if got else "ALLOW"))

    with tempfile.TemporaryDirectory() as d:
        transcript = pathlib.Path(d) / "session.jsonl"
        transcript.write_text("")
        sub = pathlib.Path(d) / "session" / "subagents"
        sub.mkdir(parents=True)
        metas = {
            "a1": {"agentType": "be-tester", "finished": True},
            "a2": {"agentType": "fe-engineer", "finished": False},
            "a3": {"agentType": "Explore", "finished": True},
            "a4": {"agentType": "fe-critic", "finished": True, "name": "critic-1"},
            "a5": {"agentType": "be-developer", "finished": True},
            "a6": {"agentType": "fe-ux", "finished": True},
            "a7": {"agentType": "be-architect", "finished": True},
        }
        for aid, meta in metas.items():
            (sub / f"agent-{aid}.meta.json").write_text(json.dumps(meta))

        def usage(aid, *sizes):
            (sub / f"agent-{aid}.jsonl").write_text("".join(json.dumps({"type": "assistant", "message": {
                "usage": {"input_tokens": 2, "cache_creation_input_tokens": 0, "cache_read_input_tokens": s}}})
                + "\n" for s in sizes))

        # 作者（be-tester 写测试）：续用到 loops.max_rounds（2）次为止，第三次拒绝
        expect("author be-tester first continuation", run(transcript, "a1"), False)
        expect("author be-tester second continuation", run(transcript, "a1"), False)
        expect("author be-tester third continuation", run(transcript, "a1"), True)
        # 作者的上下文：看最后一次请求，不看峰值；超过 continue_max_context 拒绝
        usage("a5", 250000, 90000)
        expect("author with small last context", run(transcript, "a5"), False)
        usage("a6", 90000, 210000)
        expect("author over the context limit", run(transcript, "a6"), True)
        # 项目覆盖 loops：上限 1 次
        proj = pathlib.Path(d) / "proj"
        (proj / ".claude").mkdir(parents=True)
        (proj / ".claude" / "backend.json").write_text(json.dumps(
            {"loops": {"max_rounds": 1, "continue_max_context": 200000}}))
        expect("project cap first", run(transcript, "a7", cwd=str(proj)), False)
        expect("project cap second", run(transcript, "a7", cwd=str(proj)), True)
        # 仍在运行的代理：同一轮内补一句话，不记账
        expect("running fe-engineer", run(transcript, "a2"), False)
        expect("running fe-engineer again", run(transcript, "a2"), False)
        # 非本 harness 的代理一律不管
        expect("Explore", run(transcript, "a3"), False)
        expect("Explore again", run(transcript, "a3"), False)
        # 评判者（非作者）：只为带回答案续用一次；按名字寻址，带 [ref] 后缀
        expect("named judge first", run(transcript, "critic-1 [3fa9c1]"), False)
        expect("named judge second", run(transcript, "critic-1"), True)
        # 查不到的目标、main、非 SendMessage 工具
        expect("unknown agent", run(transcript, "zzz"), False)
        expect("main", run(transcript, "main"), False)
        expect("other tool", run(transcript, "a1", tool="Bash"), False)

        # 在一个进行中的 run 里：放行的续用当场记进运行日志（PreToolUse，此时 meta 还是 finished）
        proj2 = pathlib.Path(d) / "proj2"
        (proj2 / "docs" / "backend").mkdir(parents=True)
        (proj2 / "docs" / "backend" / "state.json").write_text(json.dumps({"status": "in_progress", "goal": {}}))
        (sub / "agent-a8.meta.json").write_text(json.dumps({"agentType": "be-developer", "finished": True}))

        def cont(msg):
            return subprocess.run([sys.executable, str(HOOK)], capture_output=True, text=True, check=True, input=json.dumps({
                "hook_event_name": "PreToolUse", "tool_name": "SendMessage", "transcript_path": str(transcript),
                "cwd": str(proj2), "tool_input": {"to": "a8", "message": msg}})).stdout.strip()

        out = cont("You are be-developer #1 — step 4, round 2.\nOnly: TC-001")
        log = proj2 / "docs" / "backend" / "run-log.jsonl"
        evs = [json.loads(l) for l in log.read_text().splitlines()] if log.exists() else []
        expect("continuation in a run: allowed", bool(out), False)
        cases += 1
        if not (evs and evs[-1]["event"] == "dispatch" and evs[-1].get("continued") and evs[-1].get("redo") == 1):
            failures += 1
            print("FAIL continuation in a run: not logged as a continued round", evs[-1:] if evs else evs)
        out = cont("Please fix it.")  # no step: an answer to a blocked agent, same step
        expect("continuation without step: allowed", bool(out) and "deny" in out, False)
        # 轮次用满（另一个 be-developer 已在第 4 步做了一轮返工）：run-log 拒绝，续用账本不记
        (sub / "agent-a9.meta.json").write_text(json.dumps({"agentType": "be-developer", "finished": True}))
        gate = HOOK.parent.parent / "gates" / "gate.py"
        done = ["return", "--status", "ok", "--note", "x"]  # a8's two continued rounds returned
        for ev in (done, done, ["dispatch", "--model", "opus", "--note", "fix", "--redo"], done):
            subprocess.run([sys.executable, str(gate), "log", ev[0], "--agent", "be-developer", "--step", "4", *ev[1:],
                            "--project", str(proj2)], capture_output=True, check=True)
        out = subprocess.run([sys.executable, str(HOOK)], capture_output=True, text=True, check=True, input=json.dumps({
            "hook_event_name": "PreToolUse", "tool_name": "SendMessage", "transcript_path": str(transcript),
            "cwd": str(proj2), "tool_input": {"to": "a9", "message": "You are be-developer #2 — step 4, round 3."}})).stdout
        expect("continuation past the round cap: run-log denies", "ROUND CAP" in out, True)
        expect("denied continuation not counted", (sub / "agent-a9.continuations").exists(), False)

    # 读不懂的输入
    out = subprocess.run([sys.executable, str(HOOK)], input="not json",
                         capture_output=True, text=True, check=True).stdout.strip()
    expect("bad input", bool(out), False)

    print("%d cases, %d failures" % (cases, failures))
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
