#!/usr/bin/env python3
"""``no-foreign-process-kill.py`` 的回归矩阵。跑法：``python3 <本文件>``，退出码即结果。

第一条是真实事故的原命令。ALLOW 一半和 DENY 一半同等重要：按 PID 收掉自己起的进程
是正路，拦了它，代理就只剩绕过这一条路。
"""
import json
import pathlib
import subprocess
import sys

HOOK = pathlib.Path(__file__).with_name("no-foreign-process-kill.py")

CASES: list[tuple[str, bool]] = [
    # —— 真实事故 ——
    ('pkill -f "^./guide$"', True),
    # —— 按名字或模式 ——
    ("killall node", True),
    ("pkill guide", True),
    ("sudo pkill -9 python", True),
    ("npm run build && pkill -f vite", True),
    # —— 按端口或文件 ——
    ("fuser -k 3000/tcp", True),
    ("fuser -n tcp -k 3000", True),
    ("npx kill-port 3000", True),
    ("npx -y kill-port 3000 8080", True),
    # —— 先查再杀 ——
    ("kill $(pgrep guide)", True),
    ("kill -9 `lsof -ti:3000`", True),
    ("lsof -ti:3000 | xargs kill", True),
    ("lsof -ti:3000 | xargs -r kill -9", True),
    ("pgrep -f guide | xargs kill", True),
    ("P=$(pidof guide); kill $P", True),
    ("ps aux | grep guide | awk '{print $2}' | xargs kill", True),
    # —— 整组或全部 ——
    ("kill 0", True),
    ("kill -9 -1", True),
    ("kill -- -1234", True),
    ("kill -s TERM -1234", True),
    # —— 按 PID，必须放行 ——
    ("kill 38236", False),
    ("kill -TERM 38236", False),
    ("kill -9 38236 38237", False),
    ("kill $!", False),
    ('kill "$SERVER_PID"', False),
    ("kill $SERVER_PID", False),
    ("kill %1", False),
    ("kill $(cat /tmp/x/preview.pid)", False),
    ("./guide & echo $! > /tmp/x/guide.pid", False),
    ("kill -l", False),
    ("ps -p $PID >/dev/null && kill $PID", False),   # 先确认自己的进程还在
    ("kill -0 $PID && kill $PID", False),
    # —— 只查不杀 ——
    ("ps aux | grep guide", False),
    ("pgrep -l guide", False),
    ("lsof -i :3000", False),
    # —— 字符串，不是命令 ——
    ("grep -rn pkill docs/", False),
    ("grep -rn 'pkill -f' hooks/", False),
    ('echo "use kill $(pgrep x) never"', False),
    ("cat > d.md <<'EOF'\n不要 pkill，也不要 lsof -ti | xargs kill\nEOF", False),
    ("git log --grep killall", False),
    # —— heredoc 之后的真命令仍要拦 ——
    ("cat > d.md <<'EOF'\n正文\nEOF\npkill guide", True),
    ("", False),
]


def denies(command: str) -> bool:
    payload = {"tool_name": "Bash", "tool_input": {"command": command}}
    out = subprocess.run([sys.executable, str(HOOK)], input=json.dumps(payload),
                         capture_output=True, text=True, check=True).stdout.strip()
    return bool(out) and json.loads(out)["hookSpecificOutput"]["permissionDecision"] == "deny"


def main() -> int:
    failures = 0
    for command, want in CASES:
        got = denies(command)
        if got != want:
            failures += 1
            print("FAIL want=%s got=%s  %r" % ("DENY" if want else "ALLOW", "DENY" if got else "ALLOW", command))
    out = subprocess.run([sys.executable, str(HOOK)],
                         input=json.dumps({"tool_name": "Edit", "tool_input": {"command": "pkill x"}}),
                         capture_output=True, text=True, check=True).stdout.strip()
    if out:
        failures += 1
        print("FAIL 非 Bash 工具被拦了")
    print("%d cases, %d failures" % (len(CASES) + 1, failures))
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
