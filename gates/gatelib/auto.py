"""The run log written by hooks, not by memory: what a dispatch or a return says about itself.

`hooks/run-log.py` hands Claude Code's hook payloads to `gate.py auto dispatch|return`; these
helpers read the brief's first line and items, the agent's final report, its transcript and its
model, and keep the hashes of the run's control files while an agent is out.
"""
import hashlib
import json
import pathlib
import re
import tempfile

from . import runlog

HARNESS = re.compile(r"^(be|fe)-")
COORDINATORS = {"be": "be-reviewer", "fe": "fe-reviewer"}
FIRST_LINE = "You are <agent> #<n> — step <s>, round <r>."
ITEM = re.compile(r"\b[A-Z]{1,5}-\d+\b")  # Q-3, FND-002, TC-014, CHK-001, REQ-007, DES-004, DFB-002


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


def brief_items(text):
    """The item ids on a brief's `Only:` line, in order, each once; [] when it names none."""
    only = re.search(r"^\s*Only:\s*(.+)$", text or "", re.M)
    return list(dict.fromkeys(ITEM.findall(only.group(1)))) if only else []


def brief_hash(text):
    """sha1 of a prompt with its whitespace normalised: what pairs a return with its own dispatch
    when several agents of one type are out."""
    return hashlib.sha1(" ".join(str(text or "").split()).encode("utf-8")).hexdigest()


def _integrating(events, agent, step):
    """Whether the latest `land` of this agent type at this step that merged or met a conflict met a
    conflict: its author is still finishing the integration of that round."""
    phase = {ev.get("seq"): str(ev.get("phase")) for ev in events if ev.get("event") == "dispatch"}
    results = [ev.get("result") for ev in events
               if ev.get("event") == "land" and ev.get("agent") == agent
               and ev.get("result") in ("conflict", "merged") and phase.get(ev.get("dispatch")) == str(step)]
    return bool(results) and results[-1] == "conflict"


def is_redo(events, agent, step, items):
    """Whether a dispatch of `agent` at `step` on `items` redoes work, whatever round its brief claims.

    It does when an agent of the same type was already dispatched at this step and has returned,
    and that dispatch's items overlap these (neither naming any counts as overlap). Three things are
    not a redo: the earlier agent returned `blocked` (it did not finish its round; the next one
    continues it), its `land` met a conflict that no merge has followed (the author is finishing
    the integration of its round), and the item lists differ while the latest gate run since that
    dispatch passed (the earlier items are done; this is the next piece of work, such as the next
    queue rows)."""
    if _integrating(events, agent, step):
        return False
    items = set(items or ())
    for row in runlog.dispatches(events):
        d, ret = row["dispatch"], row["return"]
        if d.get("agent") != agent or str(d.get("phase")) != str(step) or ret is None or ret.get("status") == "blocked":
            continue
        earlier = set(d.get("items") or ())
        if not (earlier & items or not (earlier or items)):
            continue
        gates = [ev.get("overall") for ev in events if ev.get("event") == "gate" and ev.get("seq", 0) > d.get("seq", 0)]
        if earlier == items or not gates or gates[-1] != "pass":
            return True
    return False


def _clean(name):
    return re.sub(r"[^A-Za-z0-9_.-]", "_", str(name))


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


def drop_report(agent_id):
    """A return that is logged nowhere leaves no kept report behind."""
    if agent_id:
        _kept(str(agent_id)).unlink(missing_ok=True)


def _messages(transcript, role="assistant"):
    """The messages of one role in a transcript, one per line that holds one; [] when unreadable."""
    try:
        lines = pathlib.Path(transcript).read_text(encoding="utf-8").split("\n")
    except Exception:
        return []
    out = []
    for line in lines:
        try:
            msg = json.loads(line).get("message") or {}
        except Exception:
            continue
        if msg.get("role") == role:
            out.append(msg)
    return out


def first_prompt(transcript):
    """The first user message of an agent's transcript (the brief it was dispatched with); "" when
    the transcript cannot be read or holds none."""
    for msg in _messages(transcript, "user")[:1]:
        c = msg.get("content")
        return c if isinstance(c, str) else "".join(
            str(x.get("text", "")) for x in c or [] if isinstance(x, dict) and x.get("type") == "text")
    return ""


def report_text(transcript):
    """The agent's final report: its last handback, else its last text."""
    last = ""
    for msg in _messages(transcript):
        for c in msg["content"] if isinstance(msg.get("content"), list) else []:
            if c.get("type") == "tool_use" and c.get("name") == "SubagentHandback":
                last = str((c.get("input") or {}).get("message", ""))
            elif c.get("type") == "text" and c.get("text", "").strip():
                last = c["text"]
    return last


def usage(transcript):
    """(context, out_tokens) of an agent: the tokens its last request sent to the model (input, cache
    writes and cache reads) and the output tokens of all its requests; (None, None) when the
    transcript has no usage. A request written as several lines is counted once."""
    per_request, context = {}, None
    for n, msg in enumerate(_messages(transcript)):
        u = msg.get("usage")
        if not isinstance(u, dict):
            continue
        context = sum(int(u.get(k) or 0) for k in
                      ("input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens"))
        per_request[msg.get("id") or n] = int(u.get("output_tokens") or 0)
    return (context, sum(per_request.values())) if per_request else (None, None)


EMPTY = re.compile(r"^(\[\s*\]|none|n/a|no|false|0|-|—)?\s*(#.*)?$", re.I)


def parse_report(text):
    """(status, figma calls, note) from an output contract. Blocked when it says so: `blocked: 0`,
    `no`, `false`, `none` or an empty list is not."""
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


def visible(text):
    """The report's `user_visible:` line (what the user will see differently), at most 200 characters."""
    m = re.search(r"^\s*user_visible:\s*(.+)$", text or "", re.M | re.I)
    return m.group(1).strip()[:200] if m else None


def agent_model(agents_dir, agent):
    """The `model:` in the agent's own file, used when the dispatch names none."""
    try:
        text = (pathlib.Path(agents_dir) / f"{agent}.md").read_text(encoding="utf-8")
    except Exception:
        return "default"
    m = re.search(r"^model:\s*(\S+)", text.split("\n---", 1)[0], re.M)
    return m.group(1) if m else "default"


# ---------- control files ----------
# The files that decide what a gate reads and what it has already concluded. Agents never write
# them; the hooks hash them at each dispatch and again at the return, and keep the first hashes
# outside the project, where the agent's own tools are not pointed.

def control_set(project, run):
    """{project-relative path: sha1} of the run's control files: everything under `<run>/gates/`
    except the role snapshots and the command logs, and the project's `.claude/*.json` (those alone
    when `run` is None). `settings.local.json` is left out: the client rewrites it whenever the user
    allows a tool for good, also while an agent is out."""
    project, gates = pathlib.Path(project), pathlib.Path(run) / "gates" if run else None
    files = [p for p in gates.rglob("*") if p.is_file() and not p.name.startswith("snap-")
             and "logs" not in p.relative_to(gates).parts[:1]] if gates and gates.is_dir() else []
    files += [p for p in sorted((project / ".claude").glob("*.json")) if p.name != "settings.local.json"]
    out = {}
    for p in files:
        try:
            out[p.relative_to(project).as_posix()] = hashlib.sha1(p.read_bytes()).hexdigest()
        except (OSError, ValueError):
            continue
    return out


def _control_dir(project):
    return (pathlib.Path(tempfile.gettempdir()) / "harness-control"
            / hashlib.sha256(str(pathlib.Path(project).resolve()).encode()).hexdigest()[:16])


def _control_file(project, run_rel, agent, seq):
    return _control_dir(project) / f"{_clean(run_rel)}-{_clean(agent)}-{int(seq)}.json"


def keep_control(project, run, run_rel, agent, seq):
    """At a dispatch: the control files as they are now, for the comparison at its return."""
    path = _control_file(project, run_rel, agent, seq)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(control_set(project, run)), encoding="utf-8")


def take_control(project, run, run_rel, agent, seq):
    """At the return of the dispatch logged as #seq: the control files that changed, were added or
    were removed while the agent was out (sorted paths); None when nothing was kept for it."""
    path = _control_file(project, run_rel, agent, seq)
    try:
        before = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    path.unlink(missing_ok=True)
    now = control_set(project, run)
    return sorted(p for p in set(before) | set(now) if before.get(p) != now.get(p))


def control_out(project):
    """Whether any dispatch of this project has kept hashes waiting for its return."""
    d = _control_dir(project)
    return d.is_dir() and any(d.glob("*.json"))


def own_control_writes(project, run_rel, before, after):
    """`gate.py` itself wrote control files (a gate report, an approval, a profile) while agents
    were out: carry those paths' new state into the kept hashes, so the gate's own writes are not
    read as an agent's. `.claude/*.json` belongs to every run; a run's gates dir to its own
    dispatches (`run_rel` None: no run's)."""
    moved = [p for p in set(before) | set(after) if before.get(p) != after.get(p)]
    if not moved:
        return
    for kept in _control_dir(project).glob("*.json"):
        try:
            hashes = json.loads(kept.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        for p in moved:
            if p.startswith(".claude/") or (run_rel and kept.name.startswith(_clean(run_rel) + "-")):
                hashes.pop(p, None)
                if p in after:
                    hashes[p] = after[p]
        kept.write_text(json.dumps(hashes), encoding="utf-8")
