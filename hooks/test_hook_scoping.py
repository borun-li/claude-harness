#!/usr/bin/env python3
"""The safety hooks act only in harness sessions. Run: ``python3 <this file>``; the exit code is the result.

The hooks are declared in the frontmatter of the agent and command files, not in the global settings.json:
- every be-* / fe-* agent carries the git hook (``--role agent``, read only) and the process hook, and
  logs its return when it stops (a sub-agent runs only the hooks in its own file);
- a command that starts or resumes a run carries the git hook (``--role orchestrator``), the process
  hook and the continuation hook, and logs dispatches and continuations; from that call on they act
  on the session's main thread;
- install.sh removes the global entries earlier versions wrote into settings.json and leaves the
  other settings alone.
"""
import json
import pathlib
import re
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parent.parent
GIT = 'python3 "$HOME/.claude/hooks/no-tree-restoring-git.py"'  # the form earlier versions wrote into settings.json
GIT_AGENT = GIT + " --role agent"
GIT_ORCH = GIT + " --role orchestrator"
KILL = 'python3 "$HOME/.claude/hooks/no-foreign-process-kill.py"'
CONT = 'python3 "$HOME/.claude/hooks/no-agent-continuation.py"'
RUNLOG = 'python3 "$HOME/.claude/hooks/run-log.py"'
RUN_COMMANDS = ["route", "route-resume"]  # the commands that start or resume a run


def frontmatter(path: pathlib.Path) -> str:
    lines = path.read_text().split("\n")
    return "\n".join(lines[1:lines.index("---", 1)])


def event(fm: str, name: str) -> str:
    """The block under one event (PreToolUse, PostToolUse, Stop)."""
    m = re.search(r"^  %s:\n((?:\s{4,}.*\n?)*)" % name, fm + "\n", re.M)
    return m.group(1) if m else ""


def hooked(fm: str, matcher: str, ev: str = "PreToolUse") -> set:
    """The commands under a matcher of that event; with matcher None, every command of the event."""
    block = event(fm, ev)
    if matcher is not None:
        m = re.search(r"- matcher: %s\n((?:\s{6,}.*\n?)*)" % re.escape(matcher), block)
        block = m.group(1) if m else ""
    return set(re.findall(r"command: (.+)", block))


def cleanup(settings: dict) -> dict:
    """Run the Python in install.sh that cleans settings.json."""
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
        fm = frontmatter(p)
        expect(p.name, hooked(fm, "Bash") == {GIT_AGENT, KILL})
        expect(p.name + " handback", hooked(fm, "SubagentHandback") == {RUNLOG + " report"})
        expect(p.name + " Stop", hooked(fm, None, "Stop") == {RUNLOG + " return"})
    for n in RUN_COMMANDS:
        fm = frontmatter(ROOT / "commands" / f"{n}.md")
        expect(n + " Bash", hooked(fm, "Bash") == {GIT_ORCH, KILL})
        expect(n + " SendMessage", hooked(fm, "SendMessage") == {CONT})
        expect(n + " Agent", hooked(fm, "Agent") == {RUNLOG + " dispatch"})
        expect(n + " no PostToolUse", hooked(fm, "SendMessage", "PostToolUse") == set())  # logged by CONT

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

    print("%d cases, %d failures" % (1 + 3 * len(agents) + 4 * len(RUN_COMMANDS) + 4, failures))
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
