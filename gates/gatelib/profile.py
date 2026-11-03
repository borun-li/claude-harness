"""Detect a project's build/lint/typecheck/test commands for .claude/gates.json."""
import json
import pathlib
import re


def _exists(p, *names):
    return any((p / n).exists() for n in names)


def _python(p):
    py = ".venv/bin/python" if (p / ".venv/bin/python").exists() else "python3"
    pyproject = (p / "pyproject.toml").read_text(errors="replace") if (p / "pyproject.toml").exists() else ""
    # -f: without it compileall trusts a .pyc whose recorded source mtime matches to the second,
    # so code edited within the same second (or restored with its old mtime) passes unbuilt.
    cmds = {"build": f"{py} -m compileall -f -q -x '(\\.venv|venv|node_modules|\\.git)' .",
            "lint": None, "typecheck": None, "test": None}
    if "[tool.ruff" in pyproject or _exists(p, "ruff.toml", ".ruff.toml"):
        cmds["lint"] = "ruff check ."
    elif _exists(p, ".flake8"):
        cmds["lint"] = f"{py} -m flake8"
    if "[tool.mypy" in pyproject or _exists(p, "mypy.ini", ".mypy.ini"):
        cmds["typecheck"] = f"{py} -m mypy ."
    elif _exists(p, "pyrightconfig.json") or "[tool.pyright" in pyproject:
        cmds["typecheck"] = "pyright"
    if "[tool.pytest" in pyproject or _exists(p, "pytest.ini", "conftest.py", "tests", "test"):
        cmds["test"] = f"{py} -m pytest -q"
    return cmds


def _node(p):
    pkg = json.loads((p / "package.json").read_text())
    scripts = pkg.get("scripts", {})
    runner = "pnpm" if (p / "pnpm-lock.yaml").exists() else "yarn" if (p / "yarn.lock").exists() else "npm run"
    pick = lambda *names: next((f"{runner} {n}" for n in names if n in scripts), None)
    cmds = {"build": pick("build"), "lint": pick("lint"),
            "typecheck": pick("typecheck", "type-check", "tsc"), "test": pick("test")}
    if cmds["typecheck"] is None and (p / "tsconfig.json").exists():
        cmds["typecheck"] = "npx tsc --noEmit"
    return cmds


def _make(p):
    targets = set(re.findall(r"^([A-Za-z][\w-]*):", (p / "Makefile").read_text(errors="replace"), re.M))
    return {k: (f"make {k}" if k in targets else None) for k in ("build", "lint", "typecheck", "test")}


def detect(project):
    p = pathlib.Path(project)
    if (p / "package.json").exists():
        stack, cmds = "node", _node(p)
    elif (p / "go.mod").exists():
        stack, cmds = "go", {"build": "go build ./...", "lint": "go vet ./...", "typecheck": None,
                             "test": "go test ./..."}
    elif (p / "Cargo.toml").exists():
        stack, cmds = "rust", {"build": "cargo build", "lint": "cargo clippy", "typecheck": None,
                               "test": "cargo test"}
    elif _exists(p, "pyproject.toml", "setup.py", "setup.cfg") or list(p.glob("requirements*.txt")):
        stack, cmds = "python", _python(p)
    elif (p / "Makefile").exists():
        stack, cmds = "make", _make(p)
    elif any(p.glob("*.py")) or any(p.glob("*/*.py")):
        stack, cmds = "python", _python(p)
    else:
        stack, cmds = "unknown", dict.fromkeys(("build", "lint", "typecheck", "test"))
    if (p / "Makefile").exists() and stack != "make":
        for k, v in _make(p).items():
            cmds[k] = cmds[k] or v
    return {"stack": stack, "commands": cmds, "confirmed": False,
            "confirmed_on": None,
            "_note": "Draft from gate.py profile. Edit, then set confirmed true and confirmed_on "
                     "once the user approves. Any key from ~/.claude/gates/config.json may be "
                     "overridden here (frontend_globs, test_globs, ...)."}
