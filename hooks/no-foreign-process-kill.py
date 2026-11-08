#!/usr/bin/env python3
"""PreToolUse(Bash) —— 拦下「按名字、模式或端口」选中进程再停掉的命令。

**来由。** 一次真实运行里，一个只读的审查代理为了收掉自己起的实例，跑了
``pkill -f "^./guide$"``，同时停掉了 3 个不是它启动的进程（可能是预览、别的代理的实例
或用户自己的服务器）。Constitution §4.6 早就写着「用户的会话、服务器和端口不能碰」，
规则本身没有拦住它 —— 所以这里用结构来承载（~/.claude/ORCHESTRATOR.md，Boundaries）。

**判据只有一条，和 no-tree-restoring-git.py 相同：调用者能不能把要碰的东西全部说出名字。**
PID 是名字：``kill 38236`` 只碰你点名的那一个。程序名、命令行模式、端口不是名字：
它们选中的是「所有长得像的」，其中有别人的。所以：

- 拦：``pkill`` / ``killall``；``fuser -k`` / ``kill-port``；同一条命令里先查
  （``pgrep`` / ``pidof`` / ``lsof`` / ``ps``）再 ``kill``；``kill 0``、``kill -1``、
  负 PID（整组进程）。
- 放：``kill <pid>``、``kill $!``、``kill "$VAR"``、``kill %1``、
  ``kill $(cat <pid 文件>)``；只查不杀；字符串和 heredoc 里出现的这些词。

管不住包在脚本或代码里的调用（``python -c "os.kill(…)"``、一个内含 pkill 的 .sh）。
这个钩子防的是顺手写出的习惯命令，不是存心绕过；兜底的是 Constitution §4.6。
"""
import json
import re
import sys

_HEREDOC = re.compile(r"<<-?\s*[\"\']?(\w+)[\"\']?")

# 命令位置：行首或分隔符之后，可带几个透传前缀（sudo、xargs -r、timeout 5 …）
_CMD = (r"(?:^|[;&|\n(`]|\$\()\s*"
        r"(?:(?:sudo|nohup|exec|command|time|env(?:\s+\w+=\S*)*|xargs(?:\s+-\S+)*|timeout\s+\S+)\s+)*")

_BY_NAME = re.compile(_CMD + r"(?:pkill|killall)\b")
_BY_PORT = re.compile(_CMD + r"(?:fuser\b[^;&|\n]*\s-\w*k|(?:npx\s+(?:-y\s+)?)?kill-port\b)")
# `ps -p <pid>` 查的是点名的那一个，不算按名字查
_LOOKUP = re.compile(_CMD + r"(?:pgrep|pidof|lsof|ps(?!\s+-p\b))\b")
_KILL = re.compile(_CMD + r"kill\b([^;&|\n)`]*)")


def strip_data(command: str) -> str:
    """剔掉 heredoc 体和引号内的整段，只留真正会被执行的部分（同 no-tree-restoring-git.py）。"""
    out, marker = [], None
    for line in command.split("\n"):
        if marker is not None:
            if line.strip() == marker:
                marker = None
            continue
        m = _HEREDOC.search(line)
        out.append(line[: m.start()] if m else line)
        if m:
            marker = m.group(1)
    text = "\n".join(out)
    text = re.sub(r"'[^']*'", " ", text)
    return re.sub(r'"[^"]*"', " ", text)


def _whole_group(args: str) -> bool:
    """kill 的目标里有 0、-1 或负 PID：停的是一整组进程。"""
    tokens, signal_seen, after_dashes = args.split(), False, False
    i = 0
    while i < len(tokens):
        t = tokens[i]
        if after_dashes:
            if re.fullmatch(r"-?\d+", t) and int(t) <= 0:
                return True
        elif t == "--":
            after_dashes = True
        elif t in ("-s", "-n"):
            signal_seen = True
            i += 1
        elif t.startswith("-") and not signal_seen:
            signal_seen = True          # 第一个 -X 是信号（-9、-TERM、-l）
        elif re.fullmatch(r"-?\d+", t) and int(t) <= 0:
            return True                 # 信号之后的 -N，或 0
        i += 1
    return False


def reason(command: str) -> str | None:
    c = strip_data(command)
    if _BY_NAME.search(c):
        return "按程序名或命令行模式停进程（pkill / killall）"
    if _BY_PORT.search(c):
        return "按端口或文件停进程（fuser -k / kill-port）"
    kills = list(_KILL.finditer(c))
    if kills and _LOOKUP.search(c):
        return "同一条命令里先查进程（pgrep / pidof / lsof / ps）再 kill"
    if any(_whole_group(k.group(1)) for k in kills):
        return "kill 0、-1 或负 PID：停的是一整组进程"
    return None


MESSAGE = (
    "这条命令{what}，选中的不一定是你启动的。\n"
    "本仓出过事故：一个审查 agent 用 pkill 停掉了 3 个不是它启动的进程（Constitution §4.6）。\n\n"
    "改用：启动时记下 PID ——  <命令> & echo $! > <项目外的临时目录>/<名字>.pid\n"
    "      结束时只停它 ——    kill $(cat <项目外的临时目录>/<名字>.pid)\n"
    "不是你启动的进程：不要停，报告给 orchestrator。确实需要，说出来让人来跑（在提示里打 `! <命令>`），"
    "不要绕过。"
)


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0  # 读不懂就不拦 —— 钩子不该成为新的故障源
    if payload.get("tool_name") != "Bash":
        return 0
    what = reason(str(payload.get("tool_input", {}).get("command", "")))
    if what:
        print(json.dumps({"hookSpecificOutput": {
            "hookEventName": "PreToolUse", "permissionDecision": "deny",
            "permissionDecisionReason": MESSAGE.format(what=what)}}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
