"""Running project commands and reading test results."""
import glob
import json
import os
import pathlib
import re
import subprocess
import time
import xml.etree.ElementTree as ET

from .common import glob_match


def run(cmd, cwd, timeout, log_path, env=None):
    t0 = time.time()
    try:
        p = subprocess.run(cmd, shell=True, cwd=str(cwd), capture_output=True, text=True,
                           timeout=timeout, executable="/bin/bash", env={**os.environ, **(env or {})})
        code, out = p.returncode, (p.stdout or "") + (p.stderr or "")
    except subprocess.TimeoutExpired as e:
        code, out = 124, ((e.stdout or b"").decode(errors="replace") if isinstance(e.stdout, bytes)
                          else (e.stdout or "")) + f"\n[gate] timed out after {timeout}s"
    log_path = pathlib.Path(log_path)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text(f"$ {cmd}\n{out}\nexit {code}\n", encoding="utf-8")
    return {"cmd": cmd, "exit": code, "seconds": round(time.time() - t0, 1),
            "tail": out.splitlines()[-30:], "log": str(log_path), "output": out}


_KEYS = {"passed": "passed", "failed": "failed", "error": "errors", "errors": "errors",
         "skipped": "skipped", "xfailed": "xfailed", "xpassed": "xpassed"}


def parse_counts(output):
    """Counts from pytest or jest summaries; None if no summary is recognised."""
    lines = output.splitlines()
    for line in reversed(lines):  # pytest: "3 failed, 10 passed, 2 skipped in 1.2s"
        if re.search(r"\b\d+ (passed|failed|errors?)\b", line) and re.search(r"\bin [\d.]+s\b", line):
            c = dict.fromkeys(set(_KEYS.values()), 0)
            for n, k in re.findall(r"(\d+) (passed|failed|errors?|skipped|xfailed|xpassed)\b", line):
                c[_KEYS[k]] += int(n)
            return c
    for line in reversed(lines):  # vitest: " Tests  1 failed | 2 passed | 1 skipped (4)"
        if re.match(r"\s*Tests\s+\d+ (passed|failed|skipped)", line) and "|" in line or \
                re.match(r"\s*Tests\s+\d+ (passed|failed|skipped) \(\d+\)", line):
            c = dict.fromkeys(set(_KEYS.values()), 0)
            for n, k in re.findall(r"(\d+) (passed|failed|skipped)\b", line):
                c[_KEYS[k]] += int(n)
            return c
    for line in reversed(lines):  # jest: "Tests:  1 failed, 2 skipped, 10 passed, 13 total"
        if line.strip().startswith("Tests:"):
            c = dict.fromkeys(set(_KEYS.values()), 0)
            for n, k in re.findall(r"(\d+) (passed|failed|skipped)\b", line):
                c[_KEYS[k]] += int(n)
            return c
    return None


# A lint or type checker that ran prints findings or a summary; one that did not prints neither.
_RAN = re.compile(r"^Found \d+ errors?|^Success: no issues|^All checks passed|\d+ errors?, \d+ warnings?|"
                  r"\u2716 \d+ problems?|error TS\d+:|^[^\s:]+:\d+(:\d+)?:\s|-->\s+\S+:\d+:\d+", re.M)
_STOPPED = re.compile(r"errors prevented further checking|command not found|No such file or directory", re.I)


def did_not_run(r):
    """True when a failing lint or type check produced no reading: it crashed, or was never found."""
    out = r["output"]
    return r["exit"] != 0 and (r["exit"] in (124, 126, 127) or bool(_STOPPED.search(out)) or not _RAN.search(out))


def junit(paths):
    """[(classname, name, status)] from one or more JUnit XML files, or None if there are none."""
    paths = [pathlib.Path(p) for p in ([paths] if isinstance(paths, (str, pathlib.Path)) else paths)]
    paths = [p for p in paths if p.exists()]
    if not paths:
        return None
    cases = []
    for tc in (t for p in paths for t in ET.parse(p).getroot().iter("testcase")):
        tags = {child.tag for child in tc}
        status = ("failed" if "failure" in tags else "errors" if "error" in tags
                  else "skipped" if "skipped" in tags else "passed")
        cases.append((tc.get("classname", ""), tc.get("name", ""), status))
    return cases


def counts_from_junit(cases):
    c = dict.fromkeys(set(_KEYS.values()), 0)
    for _, _, s in cases:
        c[s] += 1
    return c


def total(c):
    return sum(c.get(k, 0) for k in ("passed", "failed", "errors", "skipped", "xfailed", "xpassed"))


JS_RUNNERS = ("vitest", "playwright", "jest")


def js_runner(cwd, cmd):
    """(runner, via a package script) for a JS test command, looking inside `npm run x` scripts."""
    body, via_script = cmd, False
    m = re.match(r"\s*(?:npm run|npm|pnpm|yarn)\s+(?:run\s+)?([\w:.-]+)", cmd)
    pkg = pathlib.Path(cwd) / "package.json"
    if m and pkg.exists():
        try:
            body = json.loads(pkg.read_text()).get("scripts", {}).get(m.group(1), cmd)
            via_script = True
        except ValueError:
            pass
    return next((r for r in JS_RUNNERS if re.search(r"\b%s\b" % r, body)), None), via_script


def junit_plan(cmd, cwd, junit_path, configured=None):
    """(command, env, report glob or None, note) so the run leaves a JUnit report."""
    if configured:
        return cmd, {}, str(pathlib.Path(cwd) / configured), f"report from gates.json junit: {configured}"
    if "pytest" in cmd and "--junitxml" not in cmd:
        return f"{cmd} --junitxml={junit_path}", {}, str(junit_path), "pytest --junitxml"
    runner, via_script = js_runner(cwd, cmd)
    sep = " --" if via_script else ""
    if runner == "vitest":
        return (f"{cmd}{sep} --reporter=default --reporter=junit --outputFile.junit={junit_path}", {},
                str(junit_path), "vitest junit reporter")
    if runner == "playwright":
        return (f"{cmd}{sep} --reporter=list,junit",
                {"PLAYWRIGHT_JUNIT_OUTPUT_FILE": str(junit_path), "PLAYWRIGHT_JUNIT_OUTPUT_NAME": str(junit_path)},
                str(junit_path), "playwright junit reporter")
    if runner == "jest":
        if not (pathlib.Path(cwd) / "node_modules" / "jest-junit").exists():
            return cmd, {}, None, "jest without jest-junit: counts only (add jest-junit or gates.json junit)"
        return (f"{cmd}{sep} --reporters=default --reporters=jest-junit", {"JEST_JUNIT_OUTPUT_FILE": str(junit_path)},
                str(junit_path), "jest-junit reporter")
    return cmd, {}, None, "no per-test report (set gates.json junit to enable)"


def run_tests(cmd, cwd, timeout, log_path, junit_path, configured=None):
    """Run the test command so it leaves a JUnit report; read only reports written by this run."""
    pathlib.Path(junit_path).unlink(missing_ok=True)
    cmd, env, pattern, note = junit_plan(cmd, cwd, junit_path, configured)
    t0 = time.time() - 1
    r = run(cmd, cwd, timeout, log_path, env)
    fresh = [f for f in glob.glob(pattern, recursive=True) if os.path.getmtime(f) >= t0] if pattern else []
    cases = junit(fresh) if fresh else None
    r["cases"], r["junit_note"] = cases, note if fresh or not pattern else f"{note}: no report was written"
    r["counts"] = counts_from_junit(cases) if cases is not None else parse_counts(r["output"])
    r["failed_tests"] = sorted(f"{c}::{n}" for c, n, s in (cases or []) if s in ("failed", "errors"))
    return r


def test_file_stats(project, files, cfg):
    """Per test file: number of test definitions and skip markers."""
    defs = [re.compile(p, re.M) for p in cfg["test_def_patterns"]]
    skips = [re.compile(p, re.M) for p in cfg["skip_patterns"]]
    stats = {}
    for rel in files:
        if not glob_match(rel, cfg["test_globs"]):
            continue
        try:
            text = (pathlib.Path(project) / rel).read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        stats[rel] = {"tests": sum(len(r.findall(text)) for r in defs),
                      "skips": sum(len(r.findall(text)) for r in skips)}
    return stats


def tc_locations(project, files, cfg, prefix="TC"):
    """{ID: [(file, enclosing python test function or None)]} from test code, for TC- or FX- ids."""
    out = {}
    py = re.compile(r"^\s*(?:async\s+)?def\s+(test\w*)\s*\(")
    js = re.compile(r"\b(?:it|test)(?:\.only)?\s*\(\s*(['\"`])(.+?)\1")

    class Def:
        @staticmethod
        def match(line):
            m = py.match(line) or js.search(line)
            return m and (m.group(1) if m.re is py else m.group(2))
    fn = Def
    for rel in files:
        if not glob_match(rel, cfg["test_globs"]):
            continue
        try:
            lines = (pathlib.Path(project) / rel).read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            continue
        current = None
        for i, line in enumerate(lines):
            m = fn.match(line)
            if m:
                current = m
            tcs = re.findall(r"\b%s-\d+\b" % prefix, line)
            if not tcs:
                continue
            owner = current
            stripped = line.strip()
            if not m and (stripped.startswith(("#", "@", "//")) or current is None):
                # a tag in a comment or decorator right above a def belongs to that def
                for nxt in lines[i + 1:i + 4]:
                    m2 = fn.match(nxt)
                    if m2:
                        owner = m2
                        break
                    if nxt.strip() and not nxt.strip().startswith(("#", "@", "//")):
                        break
            for tc in tcs:
                out.setdefault(tc, []).append((rel, owner))
    return out
