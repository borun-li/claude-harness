"""Append-only, hash-chained run log: who did what, when, with what result, approved by whom.

The chain shows an accidental edit, removal or reordering; it has no key and no anchor outside the
file, so it does not prove that nobody rewrote the log on purpose.

Optional fields beyond REQUIRED: a `dispatch` may carry `redo` (its redo round), `items` (the ids
of its brief's `Only:` line), `continued` and `agent_id` (a continuation), `figma_left`, `brief`
(sha1 of its prompt), `isolated` (true: the agent works in a git worktree of its own), `head` (the
run's branch when an isolated agent was dispatched) and `worktree` (project-relative; a continued
isolated author's); a `return` may carry `dispatch` (the seq of the dispatch it closes),
`agent_id`, `worktree` (project-relative, when the agent ran in one that still exists), `seconds`,
`changed` ({"added", "modified", "deleted", "files"}), `visible`, `context`, `out_tokens`,
`control_changed`, `report`, `figma_calls`; a `land` its `commit`, `files` (count), `paths` (at
most 20: the files at fault of a conflict or a refusal) and `note`; a `waive` its `tests`,
`details` (the failure lines it covers) and `sig`; an `approve` its `manifest_sha`, `active_reqs`.
"""
import datetime
import fcntl
import hashlib
import json

from .common import ConfigError, utc_now

REQUIRED = {
    "dispatch": ("agent", "model", "phase", "note"),
    "return": ("agent", "phase", "status", "note"),
    "human": ("stop", "decision", "by", "note"),
    "decision": ("agent", "note"),
    "gate": ("gate", "overall"),
    "mark": ("role",),
    "approve": ("by", "fixtures"),
    "capture": ("round", "captures"),
    "waive": ("check", "gate", "by", "reason"),  # the user's waiver of one failing check at one gate
    "land": ("agent", "dispatch", "result"),  # a returned writer's work put on the run's branch, or why not
    "void": ("voids", "by", "note"),  # the log is append-only: a wrong entry is voided, never edited
}
VOIDABLE = ("dispatch", "return", "human", "decision", "mark", "waive", "land")
LANDED = ("merged", "committed", "empty")  # `land` results after which a dispatch's work is on the run's branch
ALLOWED = {"status": {"ok", "blocked", "failed"},
           "stop": {"Prototype", "Plan", "Acceptance", "conditional", "UX", "UI", "Budget"},
           "decision": {"approved", "changes", "rejected", "answered"},
           "result": {*LANDED, "conflict", "refused"}}
# Roles whose changes the gates attribute: a writer in the run's tree is marked (snapshot) at its
# dispatch, and every writer's return is landed (`gate.py land`).
WRITERS = {"be-analyst", "be-architect", "be-developer", "be-tester",
           "fe-ux", "fe-ui", "fe-engineer", "fe-tester"}
GENESIS = "0" * 64
# json leaves these raw with ensure_ascii=False, and they end a line for str.splitlines() and for
# many tools: escaped, one event stays one line whoever reads it.
LINE_BREAKS = {"\u2028": "\\u2028", "\u2029": "\\u2029", "\u0085": "\\u0085"}


def _digest(line):
    return hashlib.sha256(line.encode("utf-8")).hexdigest()


def read(path):
    """[(raw line, parsed event)]; raises ConfigError on a line that is not JSON. Lines end at "\\n"
    only: a log written before the escaping may hold a raw U+2028 inside a note."""
    if not path.exists():
        return []
    out = []
    for n, raw in enumerate(path.read_text(encoding="utf-8").split("\n"), 1):
        if raw.strip():
            try:
                out.append((raw, json.loads(raw)))
            except ValueError:
                raise ConfigError(f"{path}:{n} is not JSON")
    return out


def events(path):
    """The log's events as the gates count them: voided entries and the voids themselves left out."""
    evs = [ev for _, ev in read(path)]
    gone = {ev.get("voids") for ev in evs if ev.get("event") == "void"}
    return [ev for ev in evs if ev.get("event") != "void" and ev.get("seq") not in gone]


def problems(path):
    """Schema and hash-chain problems; empty list means the log is intact."""
    found, prev, seen = [], GENESIS, set()
    for i, (raw, ev) in enumerate(read(path), 1):
        kind = ev.get("event")
        if kind not in REQUIRED:
            found.append(f"line {i}: unknown event {kind!r}")
        else:
            found += [f"line {i} ({kind}): missing {k}" for k in REQUIRED[kind] if ev.get(k) in (None, "")]
            found += [f"line {i} ({kind}): {k}={ev[k]!r} not in {sorted(v)}" for k, v in ALLOWED.items()
                      if k in ev and k in REQUIRED[kind] and ev[k] not in v]
            if kind == "void" and ev.get("voids") not in seen:
                found.append(f"line {i} (void): voids #{ev.get('voids')}, which is not an earlier voidable entry")
        if kind in VOIDABLE:
            seen.add(ev.get("seq"))
        if ev.get("prev") != prev or ev.get("seq") != i:
            found.append(f"line {i}: chain broken (edited, removed or reordered)")
        prev = _digest(raw)
    return found


def append(path, event, **fields):
    """Append one event. A field given as a function is called with the event's seq, under the
    lock (a file named after the entry is written then, by whoever knows the seq first)."""
    if event not in REQUIRED:
        raise ConfigError(f"unknown event {event!r}; one of {sorted(REQUIRED)}")
    missing = [k for k in REQUIRED[event] if fields.get(k) in (None, "")]
    if missing:
        raise ConfigError(f"{event} needs {missing}")
    for k, allowed in ALLOWED.items():
        if k in REQUIRED[event] and fields[k] not in allowed:
            raise ConfigError(f"{event}: {k} must be one of {sorted(allowed)}")
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        fcntl.flock(f, fcntl.LOCK_EX)  # hooks of parallel dispatches append at the same moment
        rows = read(path)
        seq = len(rows) + 1
        fields = {k: v(seq) if callable(v) else v for k, v in fields.items()}
        ev = {"seq": seq, "ts": utc_now(), "event": event,
              **{k: v for k, v in fields.items() if v not in (None, "")},
              "prev": _digest(rows[-1][0]) if rows else GENESIS}
        line = json.dumps(ev, ensure_ascii=False, sort_keys=False)
        for ch, escaped in LINE_BREAKS.items():
            line = line.replace(ch, escaped)
        f.write(line + "\n")
    return ev


def round_keys(step, agent, items=()):
    """What a redo is counted against: (step, agent, item) for each item its brief names, else
    (step, agent, "*"). Rows of one build queue, or findings of one review, each get their own rounds."""
    return [(str(step), agent, str(i)) for i in (items or ["*"])]


def rounds(path):
    """({(step, agent, item): redo rounds used}, {step: extra caps the user granted})."""
    used, granted = {}, {}
    for ev in events(path):
        if ev.get("event") == "dispatch" and ev.get("redo"):
            for key in round_keys(ev.get("phase"), ev.get("agent"), ev.get("items")):
                used[key] = used.get(key, 0) + 1
        elif (ev.get("event") == "human" and ev.get("stop") == "conditional"
              and ev.get("decision") == "approved" and ev.get("phase") is not None):
            granted[str(ev["phase"])] = granted.get(str(ev["phase"]), 0) + 1
    return used, granted


def dispatches(events):
    """[{"dispatch": event, "return": event or None}] in dispatch order. A return closes the open
    dispatch of its agent type it names (`dispatch`), else the oldest."""
    rows, open_ = [], {}
    for ev in events:
        if ev.get("event") == "dispatch":
            rows.append({"dispatch": ev, "return": None})
            open_.setdefault(ev.get("agent"), []).append(rows[-1])
        elif ev.get("event") == "return" and open_.get(ev.get("agent")):
            waiting = open_[ev["agent"]]
            row = next((r for r in waiting if r["dispatch"].get("seq") == ev.get("dispatch")), waiting[0])
            waiting.remove(row)
            row["return"] = ev
    return rows


def team_of(agent, scope):
    """The team a dispatch belongs to, where a check needs one: `fe` for an `fe-*` agent and for any
    agent of a run whose scope is `frontend`; else `be`."""
    return "fe" if str(agent).startswith("fe-") or scope == "frontend" else "be"


def in_tree_out(events):
    """The writer dispatches still out in the run's tree (not isolated), oldest first."""
    return [r["dispatch"] for r in dispatches(events)
            if r["return"] is None and r["dispatch"].get("agent") in WRITERS and not r["dispatch"].get("isolated")]


def unlanded(events):
    """The writer dispatches that have returned (not `failed`) and whose work is not on the run's
    branch yet: no `land` with result merged, committed or empty after that return. Oldest return first."""
    landed = {}
    for ev in events:
        if ev.get("event") == "land" and ev.get("result") in LANDED:
            landed[ev.get("dispatch")] = ev.get("seq", 0)
    rows = [r for r in dispatches(events)
            if r["dispatch"].get("agent") in WRITERS and r["return"] is not None
            and r["return"].get("status") != "failed"
            and landed.get(r["dispatch"].get("seq"), -1) < r["return"].get("seq", 0)]
    return [r["dispatch"] for r in sorted(rows, key=lambda r: r["return"].get("seq", 0))]


def seconds_between(start, end):
    """Whole seconds from one log timestamp to another; None when either cannot be read."""
    try:
        a, b = (datetime.datetime.strptime(t, "%Y-%m-%dT%H:%M:%SZ") for t in (start, end))
    except (TypeError, ValueError):
        return None
    return max(0, int((b - a).total_seconds()))


def when(ts):
    """`YYYY-MM-DD HH:MM:SS` of a log timestamp: a run that crosses midnight still reads in order."""
    return str(ts or "")[:19].replace("T", " ")


def change_summary(changed):
    """`+2 ~3 -0 files` of a return's `changed`; "" when it has none."""
    if not isinstance(changed, dict):
        return ""
    return f"+{changed.get('added', 0)} ~{changed.get('modified', 0)} -{changed.get('deleted', 0)} files"


def timeline(path):
    """Markdown timeline of the log."""
    lines = ["# Run log", "", "| # | Time (UTC) | Event | Who | What | Result |", "|---|---|---|---|---|---|"]
    rows = [ev for _, ev in read(path)]
    gone = {ev.get("voids") for ev in rows if ev.get("event") == "void"}
    for ev in rows:
        k = ev["event"]
        who = ev.get("agent") or ev.get("role") or ev.get("by") or ("gate" if k == "gate" else "")
        what = {"gate": ev.get("gate"), "human": f"{ev.get('stop')} stop", "mark": "snapshot",
                "void": f"voids #{ev.get('voids')}",
                "capture": f"evidence round {ev.get('round')}, {ev.get('captures')} captures",
                "waive": f"waives {ev.get('check')} at {ev.get('gate')}: {ev.get('reason')}",
                "land": " · ".join(x for x in (f"lands #{ev.get('dispatch')}", str(ev.get("commit") or "")[:7],
                                                 ", ".join(ev.get("paths") or [])) if x),
                "approve": ", ".join(ev.get("fixtures", []))}.get(k, "")
        what = " · ".join(x for x in (what, f"phase {ev['phase']}" if ev.get("phase") else "",
                                      f"round {ev['redo']}" if ev.get("redo") else "",
                                      ", ".join(ev.get("items") or []), ev.get("model", ""),
                                      "isolated" if ev.get("isolated") else "", ev.get("note", ""),
                                      change_summary(ev.get("changed")),
                                      f"visible: {ev['visible']}" if ev.get("visible") else "",
                                      "control files changed: " + ", ".join(ev["control_changed"])
                                      if ev.get("control_changed") else "") if x)
        result = ev.get("overall") or ev.get("status") or ev.get("decision") or ev.get("result") or ""
        if ev["seq"] in gone:
            result = f"~~{result or k}~~ voided"
        fails = ev.get("fails")
        if fails:
            result += " — " + "; ".join(f"{o}: {', '.join(ids)}" for o, ids in fails.items())
        lines.append(f"| {ev['seq']} | {when(ev['ts'])} | {k} | {who} | {what.replace('|', '/')} | {result} |")
    return "\n".join(lines) + "\n"


def duration(seconds):
    if seconds is None:
        return "–"
    h, rest = divmod(int(seconds), 3600)
    m, s = divmod(rest, 60)
    return f"{h}h {m:02d}m" if h else f"{m}m {s:02d}s" if m else f"{s}s"


def stats(path):
    """Markdown cost sheet of a run, from its log alone: each dispatch (time, tokens, result) and
    the totals — redo rounds, time with an agent out, time waiting on the user, gate failures."""
    evs = events(path)
    lines = ["# Run stats", "", "| # | Agent | Step | Round | Time | Context | Out tokens | Result |",
             "|---|---|---|---|---|---|---|---|"]
    rows, agent_seconds = dispatches(evs), 0
    for r in rows:
        d, ret = r["dispatch"], r["return"] or {}
        secs = ret.get("seconds")
        if secs is None and ret:
            secs = seconds_between(d.get("ts"), ret.get("ts"))
        agent_seconds += secs or 0
        cell = lambda v: "–" if v is None else str(v)
        lines.append(f"| {d['seq']} | {d.get('agent')} | {d.get('phase')} | "
                     f"{'redo ' + str(d['redo']) if d.get('redo') else 'first'} | {duration(secs)} | "
                     f"{cell(ret.get('context'))} | {cell(ret.get('out_tokens'))} | {ret.get('status') or 'out'} |")
    busy = idle = out = 0
    since = prev = None
    for ev in evs:
        ts = ev.get("ts")
        if ev.get("event") == "human" and not out and prev:
            idle += seconds_between(prev, ts) or 0
        if ev.get("event") == "dispatch":
            since, out = (ts if not out else since), out + 1
        elif ev.get("event") == "return" and out:
            out -= 1
            if not out:
                busy += seconds_between(since, ts) or 0
        prev = ts
    if out and evs:  # agents still out: busy up to the last entry
        busy += seconds_between(since, evs[-1].get("ts")) or 0
    gates = [ev for ev in evs if ev.get("event") == "gate"]
    by_owner, by_prefix = {}, {}
    for ev in gates:
        for owner, ids in (ev.get("fails") or {}).items():
            by_owner[owner] = by_owner.get(owner, 0) + len(ids)
            for i in ids:
                by_prefix[i.split(".")[0]] = by_prefix.get(i.split(".")[0], 0) + 1
    tally = lambda d: " · ".join(f"{k} {n}" for k, n in sorted(d.items(), key=lambda kv: (-kv[1], kv[0]))) or "none"
    total = lambda key: sum((r["return"] or {}).get(key) or 0 for r in rows)
    lines += ["", "## Totals", "",
              f"- Dispatches: {len(rows)}, of them redo rounds: {sum(1 for r in rows if r['dispatch'].get('redo'))}",
              f"- An agent out: {duration(busy)} (agent time added up: {duration(agent_seconds)})",
              f"- Waiting on the user: {duration(idle)} (no agent out, until a `human` entry)",
              f"- Out tokens: {total('out_tokens')}",
              f"- Gate runs: {len(gates)}, failed: {sum(1 for ev in gates if ev.get('overall') == 'fail')}",
              f"- Failed checks by owner: {tally(by_owner)}",
              f"- Failed checks by kind: {tally(by_prefix)}"]
    return "\n".join(lines) + "\n"
