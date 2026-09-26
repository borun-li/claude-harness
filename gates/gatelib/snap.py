"""Working-tree snapshots, so every change can be attributed to one dispatch."""
import hashlib
import os
import pathlib
import subprocess

from .common import glob_match

WALK_SKIP = {".git", "node_modules", ".venv", "venv", "__pycache__", ".mypy_cache",
             ".pytest_cache", ".ruff_cache", ".tox", "dist", "build"}


def git(project, *args):
    return subprocess.run(["git", "-C", str(project), *args], capture_output=True, text=True)


def is_git(project):
    r = git(project, "rev-parse", "--is-inside-work-tree")
    return r.returncode == 0 and r.stdout.strip() == "true"


def head(project):
    r = git(project, "rev-parse", "HEAD")
    return r.stdout.strip() if r.returncode == 0 else None


def dirty_paths(project):
    r = git(project, "status", "--porcelain", "-z", "--untracked-files=all")
    paths = []
    for entry in r.stdout.split("\0"):
        if len(entry) > 3:
            paths.append(entry[3:])
    return paths


def list_files(project):
    project = pathlib.Path(project)
    if is_git(project):
        r = git(project, "ls-files", "-co", "--exclude-standard", "-z")
        return sorted(p for p in r.stdout.split("\0") if p and (project / p).is_file())
    files = []
    for root, dirs, names in os.walk(project):
        dirs[:] = [d for d in dirs if d not in WALK_SKIP]
        for n in names:
            files.append(str((pathlib.Path(root) / n).relative_to(project)))
    return sorted(files)


def snapshot(project, exclude_globs):
    project = pathlib.Path(project)
    snap = {}
    for rel in list_files(project):
        if glob_match(rel, exclude_globs):
            continue
        h = hashlib.sha1()
        with open(project / rel, "rb") as f:
            for chunk in iter(lambda: f.read(1 << 16), b""):
                h.update(chunk)
        snap[rel] = h.hexdigest()
    return snap


def diff(before, after):
    added = sorted(set(after) - set(before))
    deleted = sorted(set(before) - set(after))
    modified = sorted(p for p in set(before) & set(after) if before[p] != after[p])
    return {"added": added, "modified": modified, "deleted": deleted}


def changed(d):
    return d["added"] + d["modified"] + d["deleted"]
