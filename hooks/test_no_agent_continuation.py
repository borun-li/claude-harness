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


def run(transcript: pathlib.Path, to: str, tool: str = "SendMessage") -> bool:
    out = subprocess.run(
        [sys.executable, str(HOOK)],
        input=json.dumps({"tool_name": tool, "transcript_path": str(transcript),
                          "tool_input": {"to": to, "message": "x"}}),
        capture_output=True, text=True, check=True,
    ).stdout.strip()
    return bool(out) and json.loads(out)["hookSpecificOutput"]["permissionDecision"] == "deny"


def main() -> int:
    failures = 0

    def expect(label, got, want_deny):
        nonlocal failures
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
        }
        for aid, meta in metas.items():
            (sub / f"agent-{aid}.meta.json").write_text(json.dumps(meta))

        # 已返回的 be-tester：第一次续用放行（§8.1 例外），第二次起拒绝
        expect("be-tester first continuation", run(transcript, "a1"), False)
        expect("be-tester second continuation", run(transcript, "a1"), True)
        expect("be-tester third continuation", run(transcript, "a1"), True)
        # 仍在运行的代理：同一轮内补一句话，不记账
        expect("running fe-engineer", run(transcript, "a2"), False)
        expect("running fe-engineer again", run(transcript, "a2"), False)
        # 非本 harness 的代理一律不管
        expect("Explore", run(transcript, "a3"), False)
        expect("Explore again", run(transcript, "a3"), False)
        # 按名字寻址，带 [ref] 后缀
        expect("named fe-critic first", run(transcript, "critic-1 [3fa9c1]"), False)
        expect("named fe-critic second", run(transcript, "critic-1"), True)
        # 查不到的目标、main、非 SendMessage 工具
        expect("unknown agent", run(transcript, "zzz"), False)
        expect("main", run(transcript, "main"), False)
        expect("other tool", run(transcript, "a1", tool="Bash"), False)

    # 读不懂的输入
    out = subprocess.run([sys.executable, str(HOOK)], input="not json",
                         capture_output=True, text=True, check=True).stdout.strip()
    expect("bad input", bool(out), False)

    print("13 cases, %d failures" % failures)
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
