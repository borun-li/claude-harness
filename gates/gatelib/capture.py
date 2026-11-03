"""Evidence capture for the frontend gates: the plan, the capture run, and the manifest.

The plan (`<run-dir>/capture-plan.json`) lists what must be captured; `gate.py capture` produces it
into `<run-dir>/evidence/verify-<round>/` with `manifest.json` and `manifest.md`. Every entry records
the instrument, the time and a fingerprint of the source tree, so evidence older than the build shows.
"""
import hashlib
import json
import os
import pathlib
import shutil
import subprocess
import tempfile

from . import snap
from .common import ConfigError, read_json, utc_now, write_json

HERE = pathlib.Path(__file__).resolve().parent.parent
SURFACES = ("web", "terminal", "manual")
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"


def plan_path(ctx):
    return ctx.run / "capture-plan.json"


def load_plan(ctx):
    plan = read_json(plan_path(ctx))
    if plan is None:
        raise ConfigError(f"no {ctx.run_rel}/capture-plan.json (PLAYBOOK §3H)")
    return plan


def source_fingerprint(ctx):
    """Hash of every non-doc, non-test file: changes whenever the product itself changes."""
    items = sorted((p, h) for p, h in ctx.snapshot().items() if not ctx.is_doc(p) and not ctx.is_test(p))
    return hashlib.sha256(json.dumps(items).encode()).hexdigest()[:16]


def plan_problems(plan, rows):
    """Problems with a capture plan against the queue rows that must be verified."""
    probs = []
    surface = plan.get("surface")
    if surface not in SURFACES:
        probs.append(f"surface {surface!r} not one of {SURFACES}")
    caps = plan.get("captures", [])
    if surface == "web":
        if not plan.get("base_url"):
            probs.append("web plan needs base_url")
        if not plan.get("sizes"):
            probs.append("web plan needs sizes (every size the spec commits to)")
        for s in plan.get("sizes") or []:
            if not (isinstance(s, dict) and s.get("name") and isinstance(s.get("width"), int)
                    and isinstance(s.get("height"), int)):
                probs.append(f"size {s!r} must be {{\"name\": ..., \"width\": <int>, \"height\": <int>}}")
    ids = [c.get("id") for c in caps]
    probs += [f"duplicate capture id {i}" for i in sorted({i for i in ids if ids.count(i) > 1})]
    for c in caps:
        need = {"web": ("id", "row", "state", "url"), "terminal": ("id", "row", "state", "command"),
                "manual": ("id", "row", "state", "instrument", "files")}.get(surface, ("id", "row", "state"))
        probs += [f"{c.get('id', '?')}: missing {k}" for k in need if not c.get(k)]
    covered = {c.get("row") for c in caps}
    probs += [f"{r}: no capture planned" for r in rows if r not in covered]
    return probs


def run(ctx, round_no):
    plan = load_plan(ctx)
    out = ctx.run / "evidence" / f"verify-{round_no}"
    if out.exists() and any(out.iterdir()):
        raise ConfigError(f"{out.relative_to(ctx.project)} is not empty: use a new round number, never overwrite evidence")
    out.mkdir(parents=True, exist_ok=True)
    surface = plan["surface"]
    if surface == "web":
        entries = _web(plan, out)
    elif surface == "terminal":
        entries = _terminal(ctx, plan, out)
    else:
        entries = _manual(ctx, plan, out)
    stamp = {"time": utc_now(), "fingerprint": source_fingerprint(ctx), "surface": surface}
    for e in entries:
        e.update(stamp)
    write_json(out / "manifest.json", {"round": round_no, **stamp, "entries": entries})
    lines = [f"# Evidence — round {round_no}", "",
             f"- Captured {stamp['time']} · surface {surface} · source fingerprint `{stamp['fingerprint']}`", "",
             "| Capture | Row | State | Size | Instrument | Files | OK |", "|---|---|---|---|---|---|---|"]
    for e in entries:
        lines.append(f"| {e['id']} | {e['row']} | {e['state']} | {e.get('size', '—')} | {e['instrument']} | "
                     f"{', '.join(f'`{f}`' for f in e['files'].values())} | {'yes' if e['ok'] else 'NO: ' + e.get('error', '')} |")
    (out / "manifest.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return entries, out


def _web(plan, out):
    chrome = os.environ.get("CHROME_PATH", CHROME)
    script = HERE / "capture" / "capture_web.mjs"
    if not (HERE / "node_modules" / "playwright-core").exists():
        raise ConfigError("playwright-core is not installed in ~/.claude/gates (run `npm install` there)")
    if not pathlib.Path(chrome).exists():
        raise ConfigError(f"Chrome not found at {chrome}; set CHROME_PATH")
    job = {"base_url": plan["base_url"].rstrip("/"), "sizes": plan["sizes"], "captures": plan["captures"],
           "out_dir": str(out), "chrome": chrome}
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
        json.dump(job, f)
    try:
        p = subprocess.run(["node", str(script), f.name], capture_output=True, text=True, cwd=str(HERE), timeout=900)
    finally:
        os.unlink(f.name)
    if p.returncode != 0:
        raise ConfigError(f"web capture failed: {(p.stderr or p.stdout).strip().splitlines()[-1:]}")
    entries = json.loads(p.stdout)
    for e in entries:
        e["instrument"] = "playwright-core + Chrome: DOM, computed styles, ARIA snapshot, screenshot"
    return entries


def _terminal(ctx, plan, out):
    entries = []
    for c in plan["captures"]:
        cols, lines = int(c.get("columns", 80)), int(c.get("lines", 24))
        env = {**os.environ, "COLUMNS": str(cols), "LINES": str(lines), "TERM": "xterm-256color"}
        p = subprocess.run(c["command"], shell=True, cwd=str(ctx.project), capture_output=True, env=env,
                           timeout=int(c.get("timeout", 120)), executable="/bin/bash")
        stem = f"{c['id']}@{cols}x{lines}"
        (out / f"{stem}.stdout").write_bytes(p.stdout)
        (out / f"{stem}.stderr").write_bytes(p.stderr)
        entries.append({"id": c["id"], "row": c["row"], "state": c["state"], "size": f"{cols}x{lines}",
                        "command": c["command"], "exit": p.returncode, "ok": True,
                        "files": {"stdout": f"{stem}.stdout", "stderr": f"{stem}.stderr"},
                        "instrument": f"subprocess, raw bytes, COLUMNS={cols} LINES={lines}"})
    return entries


def _manual(ctx, plan, out):
    """Captures made by hand in the surface's own inspector: copied in and stamped, never trusted blind."""
    entries = []
    for c in plan["captures"]:
        files, missing = {}, []
        for f in c["files"]:
            src = ctx.project / f
            if src.is_file() and src.stat().st_size > 0:
                shutil.copy2(src, out / src.name)
                files[src.suffix.lstrip(".") or src.name] = src.name
            else:
                missing.append(f)
        entries.append({"id": c["id"], "row": c["row"], "state": c["state"], "size": c.get("size", "—"),
                        "instrument": c["instrument"], "files": files, "ok": not missing,
                        **({"error": f"missing or empty: {missing}"} if missing else {})})
    return entries


def evidence_problems(ctx, round_dir, plan, build_time):
    """Problems with a captured round: coverage, failures, empty files, and staleness."""
    manifest = read_json(round_dir / "manifest.json")
    if manifest is None:
        return ["manifest.json missing: capture with `gate.py capture`, not by hand"]
    probs = []
    got = {(e["id"], e.get("size")) for e in manifest["entries"]}
    sizes = [s["name"] for s in plan.get("sizes", [])] if plan.get("surface") == "web" else [None]
    for c in plan.get("captures", []):
        if plan.get("surface") == "web":
            probs += [f"{c['id']}@{s}: not captured" for s in sizes if (c["id"], s) not in got]
        elif not any(i == c["id"] for i, _ in got):
            probs.append(f"{c['id']}: not captured")
    for e in manifest["entries"]:
        if not e.get("ok"):
            probs.append(f"{e['id']}@{e.get('size')}: capture failed ({e.get('error', '?')})")
        files = e.get("files", {})
        size = {k: (round_dir / f).stat().st_size if (round_dir / f).is_file() else None for k, f in files.items()}
        probs += [f"{files[k]}: missing" for k, n in size.items() if n is None]
        probs += [f"{files[k]}: empty" for k, n in size.items() if n == 0 and k not in ("stdout", "stderr")]
        if "stdout" in size and not (size.get("stdout") or size.get("stderr")):
            probs.append(f"{e['id']}@{e.get('size')}: no output on stdout or stderr")
    if build_time and manifest["time"] < build_time:
        probs.append(f"captured {manifest['time']}, before the last fe-build {build_time}")
    if manifest["fingerprint"] != source_fingerprint(ctx):
        probs.append("the product's source changed after capture: recapture")
    return probs
