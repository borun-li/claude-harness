#!/usr/bin/env python3
"""安全钩子只在 harness 会话里生效。跑法：``python3 <本文件>``，退出码即结果。

钩子写在 agent 和命令文件开头的 frontmatter 里，不写进全局 settings.json：
- 每个 be-* / fe-* agent 带 git（``--role agent``，只读）和停进程两个钩子（subagent 只认自己文件里的钩子）；
- 开启或恢复一次 run 的命令带全部三个钩子，git 钩子是 ``--role orchestrator``，调用后对本会话的主线程生效；
- install.sh 删掉旧版本写进 settings.json 的全局条目，别的设置不动。
"""
import json
import pathlib
import re
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parent.parent
GIT = 'python3 "$HOME/.claude/hooks/no-tree-restoring-git.py"'  # 旧版本写进 settings.json 的形式
GIT_AGENT = GIT + " --role agent"
GIT_ORCH = GIT + " --role orchestrator"
KILL = 'python3 "$HOME/.claude/hooks/no-foreign-process-kill.py"'
CONT = 'python3 "$HOME/.claude/hooks/no-agent-continuation.py"'
RUN_COMMANDS = ["route", "backend", "frontend", "backend-resume", "frontend-resume"]


def frontmatter(path: pathlib.Path) -> str:
    lines = path.read_text().split("\n")
    return "\n".join(lines[1:lines.index("---", 1)])


def hooked(fm: str, matcher: str) -> set:
    """matcher 段下登记的命令。"""
    m = re.search(r"- matcher: %s\n((?:\s{6,}.*\n?)*)" % re.escape(matcher), fm + "\n")
    return set(re.findall(r"command: (.+)", m.group(1))) if m else set()


def cleanup(settings: dict) -> dict:
    """跑 install.sh 里清理 settings.json 的那段 Python。"""
    script = (ROOT / "install.sh").read_text()
    code = re.search(r"python3 - \"\$dest/settings.json\" <<'EOF'\n(.*?)\nEOF\n", script, re.S).group(1)
    with tempfile.TemporaryDirectory() as d:
        path = pathlib.Path(d) / "settings.json"
        path.write_text(json.dumps(settings))
        subprocess.run([sys.executable, "-c", code, str(path)], check=True, capture_output=True)
        return json.loads(path.read_text())


def main() -> int:
    failures = 0

    def expect(label, ok):
        nonlocal failures
        if not ok:
            failures += 1
            print("FAIL", label)

    agents = sorted((ROOT / "agents").glob("*.md"))
    expect("16 agents", len(agents) == 16)
    for p in agents:
        expect(p.name, hooked(frontmatter(p), "Bash") == {GIT_AGENT, KILL})
    for n in RUN_COMMANDS:
        fm = frontmatter(ROOT / "commands" / f"{n}.md")
        expect(n + " Bash", hooked(fm, "Bash") == {GIT_ORCH, KILL})
        expect(n + " SendMessage", hooked(fm, "SendMessage") == {CONT})

    def entry(matcher, cmd):
        return {"matcher": matcher, "hooks": [{"type": "command", "command": cmd}]}

    other = entry("Bash", "my-own-hook.sh")
    got = cleanup({"model": "x", "hooks": {"PreToolUse": [
        entry("Bash", GIT), entry("Bash", KILL), entry("SendMessage", CONT), other],
        "Stop": [other]}})
    expect("old entries removed, others kept",
           got == {"model": "x", "hooks": {"PreToolUse": [other], "Stop": [other]}})
    got = cleanup({"model": "x", "hooks": {"PreToolUse": [entry("Bash", GIT)]}})
    expect("empty hooks key dropped", got == {"model": "x"})
    mixed = {"matcher": "Bash", "hooks": [{"type": "command", "command": GIT},
                                           {"type": "command", "command": "mine"}]}
    got = cleanup({"hooks": {"PreToolUse": [mixed]}})
    expect("shared entry keeps the user's hook",
           got == {"hooks": {"PreToolUse": [{"matcher": "Bash",
                                             "hooks": [{"type": "command", "command": "mine"}]}]}})
    untouched = {"hooks": {"PreToolUse": [other]}}
    expect("nothing to remove", cleanup(untouched) == untouched)

    print("%d cases, %d failures" % (1 + len(agents) + 2 * len(RUN_COMMANDS) + 4, failures))
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
