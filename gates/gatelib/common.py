"""Shared result model, time, JSON and glob helpers."""
import datetime
import functools
import json
import pathlib
import re

PASS, FAIL, UNAVAILABLE, WAIVED = "pass", "fail", "unavailable", "waived"


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
