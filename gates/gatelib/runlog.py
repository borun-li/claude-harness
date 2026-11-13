"""Append-only, hash-chained run log: who did what, when, with what result, approved by whom."""
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
}
ALLOWED = {"status": {"ok", "blocked", "failed"},
           "stop": {"Prototype", "Plan", "Acceptance", "conditional", "UX", "UI", "Budget"},
           "decision": {"approved", "changes", "rejected", "answered"}}
GENESIS = "0" * 64


def _digest(line):
    return hashlib.sha256(line.encode("utf-8")).hexdigest()


def read(path):
    """[(raw line, parsed event)]; raises ConfigError on a line that is not JSON."""
    if not path.exists():
        return []
    out = []
    for n, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if raw.strip():
            try:
                out.append((raw, json.loads(raw)))
            except ValueError:
                raise ConfigError(f"{path}:{n} is not JSON")
    return out


def problems(path):
    """Schema and hash-chain problems; empty list means the log is intact."""
    found, prev = [], GENESIS
    for i, (raw, ev) in enumerate(read(path), 1):
        kind = ev.get("event")
        if kind not in REQUIRED:
            found.append(f"line {i}: unknown event {kind!r}")
        else:
            found += [f"line {i} ({kind}): missing {k}" for k in REQUIRED[kind] if ev.get(k) in (None, "")]
            found += [f"line {i} ({kind}): {k}={ev[k]!r} not in {sorted(v)}" for k, v in ALLOWED.items()
                      if kind in ("return", "human") and k in ev and k in REQUIRED[kind] and ev[k] not in v]
        if ev.get("prev") != prev or ev.get("seq") != i:
            found.append(f"line {i}: chain broken (edited, removed or reordered)")
        prev = _digest(raw)
    return found


def append(path, event, **fields):
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
        ev = {"seq": len(rows) + 1, "ts": utc_now(), "event": event,
              **{k: v for k, v in fields.items() if v not in (None, "")},
              "prev": _digest(rows[-1][0]) if rows else GENESIS}
        f.write(json.dumps(ev, ensure_ascii=False, sort_keys=False) + "\n")
    return ev


def rounds(path):
    """({(step, agent): redo rounds used}, {step: extra caps the user granted})."""
    used, granted = {}, {}
    for _, ev in read(path):
        if ev.get("event") == "dispatch" and ev.get("redo"):
            key = (str(ev.get("phase")), ev.get("agent"))
            used[key] = used.get(key, 0) + 1
        elif (ev.get("event") == "human" and ev.get("stop") == "conditional"
              and ev.get("decision") == "approved" and ev.get("phase") is not None):
            granted[str(ev["phase"])] = granted.get(str(ev["phase"]), 0) + 1
    return used, granted


def timeline(path):
    """Markdown timeline of the log."""
    lines = ["# Run log", "", "| # | Time (UTC) | Event | Who | What | Result |", "|---|---|---|---|---|---|"]
    for _, ev in read(path):
        k = ev["event"]
        who = ev.get("agent") or ev.get("role") or ev.get("by") or ("gate" if k == "gate" else "")
        what = {"gate": ev.get("gate"), "human": f"{ev.get('stop')} stop", "mark": "snapshot",
                "capture": f"evidence round {ev.get('round')}, {ev.get('captures')} captures",
                "approve": ", ".join(ev.get("fixtures", []))}.get(k, "")
        what = " · ".join(x for x in (what, f"phase {ev['phase']}" if ev.get("phase") else "",
                                      f"round {ev['redo']}" if ev.get("redo") else "", ev.get("model", ""),
                                      ev.get("note", "")) if x)
        result = ev.get("overall") or ev.get("status") or ev.get("decision") or ""
        fails = ev.get("fails")
        if fails:
            result += " — " + "; ".join(f"{o}: {', '.join(ids)}" for o, ids in fails.items())
        lines.append(f"| {ev['seq']} | {ev['ts'][11:19]} | {k} | {who} | {what.replace('|', '/')} | {result} |")
    return "\n".join(lines) + "\n"
