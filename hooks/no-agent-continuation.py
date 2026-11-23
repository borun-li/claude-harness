#!/usr/bin/env python3
"""PreToolUse(SendMessage): a be-* / fe-* agent that has returned is continued only per Constitution §8.1.

**Why a hook and not a sentence.** An agent continued round after round carries a growing
context; a fresh agent has to read the code again from the start. §8.1 draws the line between
the two, and this file is the structure that holds it.

**The test.** SendMessage's ``to`` is an agent name or agentId and says nothing of the role.
Claude Code writes ``<transcript dir>/subagents/agent-<id>.meta.json`` (``agentType``,
``finished``) for each sub-agent, next to its transcript ``agent-<id>.jsonl``. From those:

- The target is not be-* / fe-* (or is not found) → allowed. The hook covers this harness's teams only.
- The target is still running (``finished`` is not true) → allowed. A word to a live agent
  within its round is not a continuation.
- The target is an **author** (a role that writes the work being redone, ``AUTHORS``) → allowed
  for a fix round, a revision or its role's next step on the same work, while its last request
  carried at most ``loops.continue_max_context`` tokens (the harness config: ``harness/config.json``,
  then ``harness-local/config.json``, then the project's ``.claude/harness.json``). What it has read
  it need not read again.
  The number of rounds is not counted here: the run log refuses a redo past ``loops.max_rounds``
  when the continuation is logged.
- The target is a **judge** (a reviewer, ``fe-tester``) → allowed once: it was blocked on a
  question and gets the answer within its round. A judgement is always made by a fresh agent.

An allowed continuation is handed to ``run-log.py dispatch`` here, to be written to the run log;
what that refuses is refused.

Unreadable input or a missing file → allowed: a hook must not become a new source of failure.
"""
import json
import pathlib
import re
import subprocess
import sys

HARNESS_TYPE = re.compile(r"^(be|fe)-")
AUTHORS = {"be-analyst", "be-architect", "be-developer", "be-tester", "fe-ux", "fe-ui", "fe-engineer"}
HERE = pathlib.Path(__file__).resolve().parent

REASON = (
    "Constitution §8.1: this {kind} has returned and {why}. Do not continue it.\n"
    "Start a fresh {kind} (Agent tool, subagent_type={kind}) with a brief per "
    "~/.claude/route/HANDOFF.md §3: which {kind} and round, the task, the items, evidence paths, "
    "the reading list (code map and file:line) and known traps. What the last round learned is "
    "in the handoff and the code map, not in its context."
)


def loops(cwd):
    """``loops`` of the harness config: the harness default, then the user's own defaults, then the
    project's. The layers and order of ``gatelib.common.harness_cfg``, read here without importing
    it: this hook starts with the standard library alone."""
    out = {"continue_max_context": 200000}
    for f in (HERE.parent / "harness" / "config.json",
              HERE.parent / "harness-local" / "config.json",
              pathlib.Path(cwd or ".") / ".claude" / "harness.json"):
        try:
            out.update(json.loads(f.read_text()).get("loops") or {})
        except Exception:
            continue
    return out


def last_context(transcript):
    """Tokens the agent's last request sent to the model (input + cache write + cache read);
    None when the transcript cannot be read or holds no usage, so the size is unknown."""
    size = None
    try:
        for line in transcript.read_text().split("\n"):
            u = (json.loads(line).get("message") or {}).get("usage") if '"usage"' in line else None
            if u:
                size = sum(u.get(k, 0) for k in
                           ("input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens"))
    except Exception:
        return None
    return size


def find_meta(subagents: pathlib.Path, to: str):
    """``to`` is an agentId or an agent name: try both."""
    direct = subagents / f"agent-{to}.meta.json"
    if direct.is_file():
        return direct
    for meta in subagents.glob("agent-*.meta.json"):
        try:
            if json.loads(meta.read_text()).get("name") == to:
                return meta
        except Exception:
            continue
    return None


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0
    if payload.get("tool_name") != "SendMessage":
        return 0
    to = str(payload.get("tool_input", {}).get("to", "")).strip()
    to = re.sub(r"\s*\[[^\]]*\]$", "", to)  # drop a trailing " [ref]"
    transcript = payload.get("transcript_path")
    if not to or to == "main" or not transcript:
        return 0
    subagents = pathlib.Path(transcript).with_suffix("") / "subagents"
    meta_path = find_meta(subagents, to)
    if meta_path is None:
        return 0
    try:
        meta = json.loads(meta_path.read_text())
    except Exception:
        return 0
    kind = str(meta.get("agentType", ""))
    if not HARNESS_TYPE.match(kind) or meta.get("finished") is not True:
        return 0
    author = kind in AUTHORS
    ledger = meta_path.with_name(meta_path.name.replace(".meta.json", ".continuations"))  # judges only
    used = 0
    why = None
    if author:
        try:
            limit = int(loops(payload.get("cwd"))["continue_max_context"])
        except Exception:
            limit = None
        size = last_context(meta_path.with_name(meta_path.name.replace(".meta.json", ".jsonl")))
        if size is not None and limit is not None and size > limit:  # an unknown size is not a size of 0
            why = f"its last request carried {size} tokens of context (loops.continue_max_context = {limit})"
    else:
        try:
            used = int(ledger.read_text().strip() or 0) if ledger.exists() else 0
        except Exception:
            used = 0
        if used >= 1:
            why = "it has been continued once already; a judge is fresh every round"
    if why:
        print(json.dumps({
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": REASON.format(kind=kind, why=why),
            }
        }))
        return 0
    # An allowed continuation is a dispatch too. The meta file still says finished here, so the
    # role is known; by PostToolUse the agent is running again and the continuation would go
    # unlogged. What run-log refuses (a redo past the round cap, a second writer in the run's tree,
    # an isolated author whose worktree is gone) is refused.
    out = log_dispatch({**payload, "harness_agent_type": kind})
    if (out.get("hookSpecificOutput") or {}).get("permissionDecision") == "deny":
        print(json.dumps(out))
        return 0
    if not author:
        try:
            ledger.write_text(str(used + 1))
        except Exception:
            pass
    if out:
        print(json.dumps(out))
    return 0


def log_dispatch(payload) -> dict:
    """Hand the payload to ``run-log.py dispatch``; its JSON output, or {} when it printed none."""
    try:
        p = subprocess.run([sys.executable, str(HERE / "run-log.py"), "dispatch"], input=json.dumps(payload),
                           capture_output=True, text=True, timeout=150)
        return json.loads(p.stdout) if p.stdout.strip() else {}
    except Exception as e:
        msg = f"run-log: this continuation was NOT written to the run log ({e}). Log it by hand: gate.py log dispatch …"
        return {"systemMessage": msg, "hookSpecificOutput": {"hookEventName": "PreToolUse", "additionalContext": msg}}


if __name__ == "__main__":
    sys.exit(main())
