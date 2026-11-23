#!/usr/bin/env python3
"""The hooks run on Python 3.9, the oldest interpreter install.sh accepts (the macOS system python).
Run: ``python3 <this file>``; the exit code is the result.

A hook that fails to start exits 1, which Claude Code treats as a hook error and not as a denial:
the guard would be off without anyone noticing. So every file here must parse as 3.9, must not
evaluate a ``X | None`` annotation at run time, and, where ``/usr/bin/python3`` exists, each hook
is executed with it.
"""
import ast
import json
import os
import pathlib
import subprocess
import sys

HERE = pathlib.Path(__file__).resolve().parent
SYSTEM_PYTHON = "/usr/bin/python3"
# hook → (arguments, stdin, the decision expected on stdout or None for no output)
RUNS = {
    "no-tree-restoring-git.py": (["--role", "agent"], {"tool_name": "Bash", "tool_input": {"command": "git stash"}}, "deny"),
    "no-foreign-process-kill.py": ([], {"tool_name": "Bash", "tool_input": {"command": "pkill node"}}, "deny"),
    "no-agent-continuation.py": ([], {"tool_name": "SendMessage", "tool_input": {"to": "nobody"},
                                      "transcript_path": "/nonexistent/session.jsonl"}, None),
    "run-log.py": (["return"], {"cwd": "/nonexistent", "hook_event_name": "SubagentStop",
                                "agent_type": "be-developer"}, None),
}


def union_annotations(tree):
    """Annotations written ``X | Y``: evaluated at definition time unless annotations are deferred."""
    notes = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            args = node.args
            notes += [a.annotation for a in args.posonlyargs + args.args + args.kwonlyargs + [args.vararg, args.kwarg]
                      if a is not None and a.annotation is not None] + ([node.returns] if node.returns else [])
        elif isinstance(node, ast.AnnAssign):
            notes.append(node.annotation)
    return [n for note in notes for n in ast.walk(note) if isinstance(n, ast.BinOp) and isinstance(n.op, ast.BitOr)]


def main() -> int:
    failures = cases = 0

    def ok(label, cond, detail=""):
        nonlocal failures, cases
        cases += 1
        if not cond:
            failures += 1
            print("FAIL", label, detail)

    files = sorted(HERE.glob("*.py"))
    ok("every hook this test runs exists", all((HERE / n).is_file() for n in RUNS))
    for path in files:
        source = path.read_text()
        try:
            tree = ast.parse(source, feature_version=(3, 9))
        except SyntaxError as e:
            ok("%s parses as Python 3.9" % path.name, False, str(e))
            continue
        deferred = any(isinstance(n, ast.ImportFrom) and n.module == "__future__"
                       and any(a.name == "annotations" for a in n.names) for n in tree.body)
        ok("%s: no `X | Y` annotation evaluated at run time" % path.name, deferred or not union_annotations(tree))

    if not os.access(SYSTEM_PYTHON, os.X_OK):
        print("note: no %s here; the hooks were not executed with it" % SYSTEM_PYTHON)
    else:
        version = subprocess.run([SYSTEM_PYTHON, "--version"], capture_output=True, text=True).stdout.strip()
        for path in files:  # the interpreter's own parser, without writing a .pyc
            p = subprocess.run([SYSTEM_PYTHON, "-c", "import ast, sys; ast.parse(open(sys.argv[1]).read())", str(path)],
                               capture_output=True, text=True)
            ok("%s parses with %s" % (path.name, version), p.returncode == 0, p.stderr[-300:])
        for hook, (args, payload, want) in RUNS.items():
            p = subprocess.run([SYSTEM_PYTHON, str(HERE / hook), *args], input=json.dumps(payload),
                               capture_output=True, text=True)
            out = p.stdout.strip()
            decision = json.loads(out).get("hookSpecificOutput", {}).get("permissionDecision") if out else None
            ok("%s runs with %s" % (hook, version), p.returncode == 0 and "Traceback" not in p.stderr and decision == want,
               "exit %s, decision %s\n%s" % (p.returncode, decision, p.stderr[-300:]))

    print("%d cases, %d failures" % (cases, failures))
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
