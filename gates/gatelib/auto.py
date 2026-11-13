"""The run log written by hooks, not by memory: what a dispatch or a return says about itself.

`hooks/run-log.py` hands Claude Code's hook payloads to `gate.py auto dispatch|return`; these
helpers read the brief's first line, the agent's final report and its model.
"""
import json
import pathlib
import re
import tempfile

HARNESS = re.compile(r"^(be|fe)-")
# Roles whose changes the gates attribute (a writer's mark is its snapshot).
WRITERS = {"be-analyst", "be-architect", "be-developer", "be-tester",
           "fe-ux", "fe-ui", "fe-engineer", "fe-tester"}
COORDINATORS = {"be": "be-reviewer", "fe": "fe-reviewer"}
FIRST_LINE = "You are <agent> #<n> — step <s>, round <r>."


def team(agent):
    return "backend" if agent.startswith("be-") else "frontend"


def coordinator(agent):
    """The review coordinator whose mark guards the tree for this reviewer, or None."""
    if agent in COORDINATORS.values() or agent.startswith(("be-review-", "fe-review-")):
        return COORDINATORS[agent[:2]]
    return None


def parse_brief(text):
    """(step, round, figma budget left) from a brief (route/HANDOFF.md §3); None where absent."""
    head = next((l for l in (text or "").splitlines() if l.strip()), "")
    step = re.search(r"\bstep\s+([0-9][0-9A-Za-z]*)", head)
    rnd = re.search(r"\bround\s+(\d+)", head)
    budget = re.search(r"^\s*Budget:\s*(\d+)", text or "", re.M)
    return (step.group(1) if step else None, int(rnd.group(1)) if rnd else None,
            int(budget.group(1)) if budget else None)


def _kept(agent_id):
    return pathlib.Path(tempfile.gettempdir()) / "harness-reports" / f"{re.sub(r'[^A-Za-z0-9_-]', '', agent_id)}.txt"


def keep_report(agent_id, text):
    """At the handback: the report, for the return logged when the agent stops."""
    if agent_id and text:
        _kept(agent_id).parent.mkdir(parents=True, exist_ok=True)
        _kept(agent_id).write_text(str(text), encoding="utf-8")


def take_report(agent_id, transcript):
    """The report kept at the handback (then dropped, so a continued agent's next one is fresh), else
    the transcript's."""
    kept = _kept(agent_id) if agent_id else None
    if kept and kept.is_file():
        text = kept.read_text(encoding="utf-8")
        kept.unlink(missing_ok=True)
        return text
    return report_text(transcript)


def report_text(transcript):
    """The agent's final report: its last handback, else its last text."""
    last = ""
    try:
        lines = pathlib.Path(transcript).read_text(encoding="utf-8").splitlines()
    except Exception:
        return last
    for line in lines:
        try:
            msg = json.loads(line).get("message") or {}
        except Exception:
            continue
        if msg.get("role") != "assistant" or not isinstance(msg.get("content"), list):
            continue
        for c in msg["content"]:
            if c.get("type") == "tool_use" and c.get("name") == "SubagentHandback":
                last = str((c.get("input") or {}).get("message", ""))
            elif c.get("type") == "text" and c.get("text", "").strip():
                last = c["text"]
    return last


EMPTY = re.compile(r"^(\[\s*\]|none|n/a|-|—)?\s*(#.*)?$", re.I)


def parse_report(text):
    """(status, figma calls, note) from an output contract. Blocked when it says so."""
    status = "ok"
    for m in re.finditer(r"^\s*(blocked_on|blocked|status)\s*:\s*(.*)$", text, re.M | re.I):
        key, val = m.group(1).lower(), m.group(2).strip()
        if (key == "status" and val.lower().startswith("blocked")) or (key != "status" and not EMPTY.match(val)):
            status = "blocked"
    figma = re.search(r"^\s*figma_calls:\s*(\d+)", text, re.M)
    handoff = re.search(r"^\s*handoff:\s*(.+)$", text, re.M)
    first = next((l.strip() for l in text.splitlines() if l.strip()), "")
    note = (handoff.group(1) if handoff else first or "returned without a report").strip()
    return status, int(figma.group(1)) if figma else None, note[:200]


def agent_model(agents_dir, agent):
    """The `model:` in the agent's own file, used when the dispatch names none."""
    try:
        text = (pathlib.Path(agents_dir) / f"{agent}.md").read_text(encoding="utf-8")
    except Exception:
        return "default"
    m = re.search(r"^model:\s*(\S+)", text.split("\n---", 1)[0], re.M)
    return m.group(1) if m else "default"


def open_dispatches(events):
    """{agent: [step of each dispatch not yet returned, oldest first]}."""
    out = {}
    for ev in events:
        if ev.get("event") == "dispatch":
            out.setdefault(ev["agent"], []).append(ev.get("phase"))
        elif ev.get("event") == "return" and out.get(ev.get("agent")):
            out[ev["agent"]].pop(0)
    return {a: s for a, s in out.items() if s}
