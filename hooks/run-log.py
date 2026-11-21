#!/usr/bin/env python3
"""Run log by hook: every dispatch and return of a be-*/fe-* agent is logged without being remembered.

    run-log.py dispatch   PreToolUse(Agent) in a run command's session; a continuation (SendMessage)
                          comes from no-agent-continuation.py once it allows it
    run-log.py report     PreToolUse(SubagentHandback) in every be-*/fe-* agent: keeps the report,
                          which the transcript may not hold yet when the agent stops
    run-log.py return     Stop in every be-*/fe-* agent file

It hands the payload to `gate.py auto`, which marks the writer, logs the event and enforces the
round cap. Outside an active run it does nothing. A dispatch it refuses (no step in the brief's
first line, round cap reached, the other team has a writer out) is denied with the reason; a
return never blocks the agent, and nothing here may break a session: an event it could not log is
reported as a system message, so it is logged by hand at once instead of being found missing later.
"""
import json
import pathlib
import subprocess
import sys

GATE = pathlib.Path(__file__).resolve().parent.parent / "gates" / "gate.py"
sys.path.insert(0, str(GATE.parent))


def main() -> int:
    mode = sys.argv[1] if len(sys.argv) > 1 else ""
    raw = sys.stdin.read()
    try:
        payload = json.loads(raw)
        cwd = payload.get("cwd") or "."
        if mode == "report":
            from gatelib import auto
            auto.keep_report(payload.get("agent_id"), (payload.get("tool_input") or {}).get("message"))
            return 0
        p = subprocess.run([sys.executable, str(GATE), "auto", mode, "--project", cwd],
                           input=raw, capture_output=True, text=True, timeout=120)
    except Exception as e:  # never the cause of a broken session, but never silent about an event
        if "payload" not in locals():  # not a hook payload at all: nothing to log
            print(f"run-log: {e}", file=sys.stderr)
            return 0
        return alert(mode, str(e), payload)
    if p.returncode == 2 and payload.get("hook_event_name") == "PreToolUse":
        print(json.dumps({"hookSpecificOutput": {
            "hookEventName": "PreToolUse", "permissionDecision": "deny",
            "permissionDecisionReason": p.stderr.strip() or "run-log refused the dispatch"}}))
    elif p.returncode != 0:
        return alert(mode, (p.stderr or p.stdout).strip()[-500:], payload)
    return 0


def alert(mode, error, payload):
    """The event went unlogged: say so to the user and, before a tool call, to the orchestrator, so it
    is logged by hand now instead of being found missing at a gate."""
    msg = (f"run-log: this {mode} was NOT written to the run log ({error}). Log it by hand: "
           f"gate.py log {mode} … (ORCHESTRATOR.md § Key information).")
    print(msg, file=sys.stderr)
    out = {"systemMessage": msg}
    if payload.get("hook_event_name") == "PreToolUse":
        out["hookSpecificOutput"] = {"hookEventName": "PreToolUse", "additionalContext": msg}
    print(json.dumps(out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
