#!/usr/bin/env python3
"""Regression matrix of ``no-foreign-process-kill.py``. Run: ``python3 <this file>``; the exit code is the result.

The ALLOW half matters as much as the DENY half: stopping the process you started, by PID, is
the right way; deny that and the only way left to an agent is around the hook.
"""
from __future__ import annotations

import json
import pathlib
import subprocess
import sys

HOOK = pathlib.Path(__file__).with_name("no-foreign-process-kill.py")

CASES: list[tuple[str, bool]] = [
    # -- by command-line pattern --
    ('pkill -f "^./server$"', True),
    # -- by name or pattern --
    ("killall node", True),
    ("pkill guide", True),
    ("sudo pkill -9 python", True),
    ("npm run build && pkill -f vite", True),
    # -- by port or file --
    ("fuser -k 3000/tcp", True),
    ("fuser -n tcp -k 3000", True),
    ("npx kill-port 3000", True),
    ("npx -y kill-port 3000 8080", True),
    # -- look up, then kill --
    ("kill $(pgrep guide)", True),
    ("kill -9 `lsof -ti:3000`", True),
    ("lsof -ti:3000 | xargs kill", True),
    ("lsof -ti:3000 | xargs -r kill -9", True),
    ("pgrep -f guide | xargs kill", True),
    ("P=$(pidof guide); kill $P", True),
    ("ps aux | grep guide | awk '{print $2}' | xargs kill", True),
    # -- a whole group, or everything --
    ("kill 0", True),
    ("kill -9 -1", True),
    ("kill -- -1234", True),
    ("kill -s TERM -1234", True),
    # -- by PID: must be allowed --
    ("kill 38236", False),
    ("kill -TERM 38236", False),
    ("kill -9 38236 38237", False),
    ("kill $!", False),
    ('kill "$SERVER_PID"', False),
    ("kill $SERVER_PID", False),
    ("kill %1", False),
    ("kill $(cat /tmp/x/preview.pid)", False),
    ("./server & echo $! > /tmp/x/server.pid", False),
    ("kill -l", False),
    ("ps -p $PID >/dev/null && kill $PID", False),   # checks that its own process is still there
    ("kill -0 $PID && kill $PID", False),
    # -- a lookup without a kill --
    ("ps aux | grep guide", False),
    ("pgrep -l guide", False),
    ("lsof -i :3000", False),
    # -- a string, not a command --
    ("grep -rn pkill docs/", False),
    ("grep -rn 'pkill -f' hooks/", False),
    ('echo "use kill $(pgrep x) never"', False),
    ("cat > d.md <<'EOF'\nnever pkill, never lsof -ti | xargs kill\nEOF", False),
    ("git log --grep killall", False),
    # -- a real command after a heredoc is still denied --
    ("cat > d.md <<'EOF'\nbody\nEOF\npkill guide", True),
    # -- code inside double quotes, and code handed to a shell --
    ('kill "$(pgrep node)"', True),
    ('kill -9 "`pidof guide`"', True),
    ('PID="$(lsof -ti:3000)"; kill "$PID"', True),
    ('bash -c "pkill -f vite"', True),
    ("bash -lc 'killall node'", True),
    ("sh -c 'kill $(pgrep guide)'", True),
    ("ls 2>/dev/null; pkill guide", True),               # a redirection does not swallow the separator
    ('kill "$(cat /tmp/x/preview.pid)"', False),
    ('echo "started $(date)"; kill $SERVER_PID', False),
    ('bash -c "kill $SERVER_PID"', False),
    ("which pkill killall", False),
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
        print("FAIL a tool other than Bash was denied")
    print("%d cases, %d failures" % (len(CASES) + 1, failures))
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
