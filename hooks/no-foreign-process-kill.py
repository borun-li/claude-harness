#!/usr/bin/env python3
"""PreToolUse(Bash): deny a command that picks processes by name, pattern or port and stops them.

**Why a hook and not a sentence.** An agent closing the instance it started tends to write
``pkill -f "^./server$"``, and stops the preview, another agent's instance or the user's own
server with it. Constitution §4.6 says the user's sessions, servers and ports are not touched;
this is the structure that holds it (~/.claude/ORCHESTRATOR.md, Boundaries).

**One test, the same as no-tree-restoring-git.py: can the caller name everything it touches?**
A PID is a name: ``kill 38236`` touches the one process you named. A program name, a command-line
pattern or a port is not: it selects everything that looks alike, and some of that is not yours.

- Denied: ``pkill`` / ``killall``; ``fuser -k`` / ``kill-port``; a lookup (``pgrep`` / ``pidof``
  / ``lsof`` / ``ps``) and a ``kill`` in the same command line; ``kill 0``, ``kill -1`` and
  negative PIDs (a whole process group).
- Allowed: ``kill <pid>``, ``kill $!``, ``kill "$VAR"``, ``kill %1``,
  ``kill $(cat <pid file>)``; a lookup without a kill; these words inside strings and heredocs.

A call wrapped in a script or in code (``python -c "os.kill(…)"``, a .sh that runs pkill) gets
through. The hook guards against the habitual command, not against intent; Constitution §4.6 is
the backstop.
"""
from __future__ import annotations

import json
import re
import sys

sys.dont_write_bytecode = True  # no __pycache__ next to the user's own hooks
from shell_commands import command_words, commands, name  # noqa: E402

_LOOKUPS = {"pgrep", "pidof", "lsof"}


def _whole_group(args: list) -> bool:
    """A target of 0, -1 or a negative PID: kill stops a whole group of processes."""
    signal_seen = after_dashes = False
    i = 0
    while i < len(args):
        t = args[i]
        if after_dashes:
            if re.fullmatch(r"-?\d+", t) and int(t) <= 0:
                return True
        elif t == "--":
            after_dashes = True
        elif t in ("-s", "-n"):
            signal_seen = True
            i += 1
        elif t.startswith("-") and not signal_seen:
            signal_seen = True          # the first -X is the signal (-9, -TERM, -l)
        elif re.fullmatch(r"-?\d+", t) and int(t) <= 0:
            return True                 # -N after the signal, or 0
        i += 1
    return False


def reason(command: str) -> str | None:
    """Why the command is denied. Every simple command counts, wherever it stands: after a
    separator, inside ``$(…)`` or double quotes, or handed to ``bash -c``."""
    calls = [(name(words[k]), words[k + 1:]) for words, _ in commands(command) for k in command_words(words)]
    kills = [args for tool, args in calls if tool == "kill"]
    lookup = False
    for tool, args in calls:
        if tool in ("pkill", "killall"):
            return "stops processes by program name or command-line pattern (pkill / killall)"
        if tool == "fuser" and any(re.match(r"-\w*k", a) for a in args) or tool == "kill-port" \
                or tool == "npx" and [a for a in args if not a.startswith("-")][:1] == ["kill-port"]:
            return "stops processes by port or file (fuser -k / kill-port)"
        # `ps -p <pid>` looks up the one process you named
        lookup = lookup or tool in _LOOKUPS or (tool == "ps" and args[:1] != ["-p"])
    if kills and lookup:
        return "looks processes up (pgrep / pidof / lsof / ps) and kills in the same command line"
    if any(_whole_group(args) for args in kills):
        return "runs kill 0, -1 or a negative PID, which stops a whole process group"
    return None


MESSAGE = (
    "This command {what}; what it selects is not only what you started.\n"
    "Other processes (the preview, other agents, the user's servers) are not touched (Constitution §4.6).\n\n"
    "Instead: record the PID at start:  <command> & echo $! > <temp dir outside the project>/<name>.pid\n"
    "         stop only that one:       kill $(cat <temp dir outside the project>/<name>.pid)\n"
    "A process you did not start: leave it and report it to the orchestrator. If it must be stopped, "
    "say so and let the user run it (`! <command>` in the prompt). Do not work around this."
)


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0  # unreadable input is not denied: a hook must not become a new source of failure
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
