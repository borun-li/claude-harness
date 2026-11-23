"""Shared result model, time, JSON and glob helpers."""
import datetime
import functools
import json
import pathlib
import re

PASS, FAIL, UNAVAILABLE, WAIVED = "pass", "fail", "unavailable", "waived"
# The harness root holds `gates/`, `hooks/` and `harness/` (the repository, or an install).
HARNESS_ROOT = pathlib.Path(__file__).resolve().parents[2]


class ConfigError(Exception):
    """Usage or configuration problem: exit 2, not a gate failure."""


def result(check_id, status, message, owner, details=None):
    return {"id": check_id, "status": status, "message": message, "owner": owner,
            "details": list(details or [])}


def ok(check_id, message, owner, details=None):
    return result(check_id, PASS, message, owner, details)


def bad(check_id, message, owner, details=None):
    return result(check_id, FAIL, message, owner, details)


def na(check_id, message, owner, details=None):
    return result(check_id, UNAVAILABLE, message, owner, details)


def utc_now():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def stamp():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def read_json(path, default=None):
    p = pathlib.Path(path)
    if not p.exists():
        return default
    return json.loads(p.read_text(encoding="utf-8"))


def write_json(path, data):
    p = pathlib.Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def merge(base, over, depth=1):
    """`base` with `over` on top. A dict value is merged into the dict it overrides, `depth` levels
    deep, so a project that sets one budget or one command keeps the others; any other value
    replaces. `_comment` keys are left out."""
    out = dict(base)
    for k, v in over.items():
        if k.startswith("_comment"):
            continue
        if depth > 0 and isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = merge(out[k], v, depth - 1)
        else:
            out[k] = v
    return out


def harness_cfg(project):
    """The harness config from its three layers: the harness default (`harness/config.json`, replaced
    on install), the user's own defaults (`harness-local/config.json`, which install never touches),
    then the project's `.claude/harness.json`. Each layer's top-level keys override the one before;
    a dict is merged key by key two levels deep, so a layer that sets `loops.max_rounds` or
    `models._active_tier` keeps the rest of that block."""
    cfg = {}
    for p in (HARNESS_ROOT / "harness" / "config.json", HARNESS_ROOT / "harness-local" / "config.json",
              pathlib.Path(project) / ".claude" / "harness.json"):
        try:
            layer = read_json(p)
        except ValueError as e:
            raise ConfigError(f"{p} is not JSON ({e})")
        cfg = merge(cfg, layer, depth=2) if isinstance(layer, dict) else cfg
    return cfg


@functools.lru_cache(maxsize=None)
def _glob_rx(glob):
    out, i = "", 0
    while i < len(glob):
        if glob.startswith("**/", i):
            out, i = out + "(?:.*/)?", i + 3
        elif glob.startswith("**", i):
            out, i = out + ".*", i + 2
        elif glob[i] == "*":
            out, i = out + "[^/]*", i + 1
        elif glob[i] == "?":
            out, i = out + "[^/]", i + 1
        else:
            out, i = out + re.escape(glob[i]), i + 1
    return re.compile(out + r"\Z")


def glob_match(path, globs):
    return any(_glob_rx(g).match(path) for g in globs)
