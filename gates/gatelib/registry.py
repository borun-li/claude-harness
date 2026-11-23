"""Project-level registry of approved observables (frontend PLAYBOOK §3I).

Rows the user accepted become `OBS-###` entries in `docs/observables.json`. Each is guarded
from then on by the test that proved it (kind `test`) or by a planned re-capture (kind `capture`).
Only the user adds (`fe-promote`) or retires (`fe-approve --retire`) entries, or the orchestrator
retires one a newer decision replaces (`--because`); every entry is hashed.
"""
import hashlib
import json

from . import capture, checks, docs, runner
from .common import PASS, ConfigError, bad, na, ok, read_json, utc_now, write_json


def path(ctx):
    return ctx.project / ctx.cfg.get("observables_registry", "docs/observables.json")


def load(ctx):
    return read_json(path(ctx), {"entries": {}, "history": []})


def _digest(entry):
    body = {k: v for k, v in entry.items() if k != "hash"}
    return hashlib.sha256(json.dumps(body, sort_keys=True).encode()).hexdigest()


def active(reg):
    return {k: v for k, v in reg["entries"].items() if not v.get("retired")}


def _tampered(reg):
    return [f"{k}: edited outside fe-promote / fe-approve" for k, v in reg["entries"].items()
            if v.get("hash") != _digest(v)]


def promote(ctx, by, exclude, rows_fn):
    acc = read_json(ctx.gdir / "fe-accept-latest.json")
    ver = read_json(ctx.gdir / "fe-verify-latest.json")
    if not acc or acc["overall"] != PASS or not ver:
        raise ConfigError("`fe-accept` has not passed; promote only after the user's Acceptance")
    reg = load(ctx)
    if _tampered(reg):
        raise ConfigError(f"registry tampered: {_tampered(reg)}")
    verdicts, row_tests = ver["data"].get("verdicts", {}), ver["data"].get("row_tests", {})
    locs = runner.tc_locations(ctx.project, checks._test_code(ctx), ctx.cfg, prefix="Q")
    try:
        plan = capture.load_plan(ctx)
    except ConfigError:
        plan = {"captures": []}
    rows, refused, added = rows_fn(ctx), [], []
    n = max([int(k.split("-")[1]) for k in reg["entries"]] or [0])
    for q, block in sorted(rows.items()):
        if verdicts.get(q) != "done" or q in exclude:
            continue
        caps = [c for c in plan.get("captures", []) if c.get("row") == q]
        if locs.get(q) and row_tests.get(q) == "passed":
            # A test whose name the parser cannot read (Go, Rust, Java …) is guarded by its row id,
            # which the passing JUnit case carries in its name.
            named = [{"file": f, "name": name} for f, name in locs[q] if name]
            tagged = [{"file": f, "tag": q} for f in sorted({f for f, name in locs[q] if not name})]
            guard = {"kind": "test", "tests": named + tagged}
        elif caps:
            guard = {"kind": "capture", "capture": {"surface": plan.get("surface"), "base_url": plan.get("base_url"),
                                                     "sizes": plan.get("sizes"), "spec": caps[0]}}
        else:
            refused.append(f"{q}: no passing test tagged {q} and no planned capture")
            continue
        n += 1
        oid = f"OBS-{n:03d}"
        entry = {"id": oid, "source": f"{ctx.run_rel}#{q}", "observable": docs.field(block, "Observable"),
                 "pages": sorted(docs.ids_in(docs.field(block, "Page") or docs.field(block, "Spec") or "", "PAGE")),
                 "approved_by": by, "date": utc_now()[:10], **guard}
        entry["hash"] = _digest(entry)
        reg["entries"][oid] = entry
        added.append(f"{oid} ← {q}")
    if refused:
        raise ConfigError(f"cannot promote: {refused}; tag a passing test or plan a capture, or --exclude the row")
    reg["history"].append({"event": "promote", "by": by, "date": utc_now()[:10], "added": added})
    write_json(path(ctx), reg)
    return added


def retire(ctx, by, ids, because=None):
    reg = load(ctx)
    missing = [i for i in ids if i not in active(reg)]
    if missing:
        raise ConfigError(f"not active registry entries: {missing}")
    for i in ids:
        e = reg["entries"][i]
        e.update({"retired": True, "retired_by": by, "retired_on": utc_now()[:10]}, **({"because": because} if because else {}))
        e["hash"] = _digest(e)
    reg["history"].append({"event": "retire", "by": by, "date": utc_now()[:10], "retired": list(ids),
                           **({"because": because} if because else {})})
    write_json(path(ctx), reg)


def _guards(entry):
    """(named tests, row tags) that guard an entry."""
    tests = entry.get("tests") or []
    return [(t["file"], t["name"]) for t in tests if t.get("name")], [t["tag"] for t in tests if t.get("tag")]


def regression(ctx, r, owner, partial=False):
    """Every active `test` entry's tests still exist and pass in this run. `partial`: the run was the
    frontend's own suite (`commands.fe_test`), so a guard it did not execute is left to `fe-verify`,
    which runs the whole suite."""
    reg = load(ctx)
    probs = _tampered(reg)
    tests = {k: v for k, v in active(reg).items() if v["kind"] == "test"}
    if not reg["entries"]:
        return na("FE.regression", "No approved observables registered yet", owner)
    if ctx.dry:
        return na("FE.regression", checks.DRY, owner)
    left = []
    if tests and (not r or r.get("cases") is None):
        probs.append(f"{len(tests)} registered tests, but whether they pass is not read: {runner.no_cases(r)}")
    elif tests:
        probs += [f"{k}: {t['file']} missing" for k, v in tests.items() for t in v.get("tests") or []
                  if not (ctx.project / t["file"]).exists()]
        for k, v in sorted(tests.items()):
            named, tags = _guards(v)
            if not named and not tags:
                probs.append(f"{k} ({v['observable']}): no guarding test recorded")
                continue
            seen = list(checks._observed_ids({k: named}, [k], r["cases"]).values()) if named else []
            seen += list(checks._observed_ids({}, tags, r["cases"]).values())
            st = ("failed" if "failed" in seen else "not-executed" if "not-executed" in seen else "passed")
            if st == "not-executed" and partial:
                left.append(f"{k}: not run by fe_test; fe-verify runs it")
            elif st != "passed":
                how = f", guarded by row id {', '.join(tags)}" if tags and not named else ""
                probs.append(f"{k} ({v['observable']}): {st}{how}")
    return (bad("FE.regression", "Approved observables regressed (only the user retires one)", owner, probs)
            if probs else ok("FE.regression", f"{len(tests) - len(left)} registered observables still hold", owner, left))


def capture_entries(ctx):
    return {k: v for k, v in active(load(ctx)).items() if v["kind"] == "capture"}


def conflicts(ctx, rows):
    """{OBS: [Q…]} for approved observables on pages this round's rows touch."""
    out = {}
    for oid, e in active(load(ctx)).items():
        hit = [q for q, b in rows.items() if set(e["pages"]) & docs.ids_in(docs.field(b, "Page") or docs.field(b, "Spec") or "", "PAGE")]
        if hit:
            out[oid] = hit
    return out
