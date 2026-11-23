"""Working-tree snapshots, so every change can be attributed to one dispatch."""
import hashlib
import json
import os
import pathlib
import subprocess
import tempfile
import time

from .common import glob_match

# Tool output and caches, never anyone's work: skipped by name anywhere in a path, also in a git
# repository whose .gitignore misses them.
WALK_SKIP = {".git", "node_modules", ".venv", "venv", "__pycache__", ".mypy_cache",
             ".pytest_cache", ".ruff_cache", ".tox", "dist", "build", ".next", ".turbo",
             "coverage", "htmlcov", ".nyc_output", "target", ".DS_Store", ".coverage"}
# Where Claude Code keeps the git worktrees of isolated agents: other checkouts of this same project,
# never part of this tree, tracked or not.
WORKTREES = ".claude/worktrees"
# A file modified this recently may change again within the same timestamp; its hash is not cached.
RACY_NS = 2_000_000_000


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
        if len(entry) > 3 and not in_worktrees(entry[3:]):
            paths.append(entry[3:])
    return paths


def in_worktrees(rel):
    return f"{rel}/".startswith(f"{WORKTREES}/")


AMBIGUOUS = {"build", "dist", "target", "coverage"}  # tool output, or a source package of that name


def skipped(rel, tracked=False):
    names = WALK_SKIP - AMBIGUOUS if tracked else WALK_SKIP
    return in_worktrees(rel) or any(part in names for part in rel.split("/"))


def list_files(project):
    project = pathlib.Path(project)
    if is_git(project):
        # A tracked directory called `build`, `dist`, `target` or `coverage` may be the project's own
        # source (`src/build/`): those names are skipped only for untracked files.
        tracked = git(project, "ls-files", "-c", "-z").stdout.split("\0")
        loose = git(project, "ls-files", "-o", "--exclude-standard", "-z").stdout.split("\0")
        return sorted(p for p in {*(q for q in tracked if not skipped(q, tracked=True)),
                                  *(q for q in loose if not skipped(q))}
                      if p and (project / p).is_file())
    files = []
    for root, dirs, names in os.walk(project):
        here = pathlib.Path(root).relative_to(project)
        dirs[:] = [d for d in dirs if d not in WALK_SKIP and (here / d).as_posix() != WORKTREES]
        for n in names:
            if n not in WALK_SKIP:
                files.append((pathlib.Path(root) / n).relative_to(project).as_posix())
    return sorted(files)


def file_sha(path):
    h = hashlib.sha1()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def cache_path(project):
    """The hash cache of a project: outside it, so it is no one's change and no test of the project sees it."""
    key = hashlib.sha256(str(pathlib.Path(project).resolve()).encode()).hexdigest()[:12]
    return pathlib.Path(tempfile.gettempdir()) / "claude-gates" / key / "sha-cache.json"


def _load_cache(path):
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def snapshot(project, exclude_globs, write_cache=True):
    """{path: sha1} of the tree. A file whose size and mtime are those of its cached entry is not
    hashed again; any other file is. `write_cache=False` leaves the cache file as it is."""
    project = pathlib.Path(project)
    cpath = cache_path(project)
    old, now = _load_cache(cpath), time.time_ns()
    files = list_files(project)
    new, snap = {rel: old[rel] for rel in files if rel in old}, {}
    for rel in files:
        if glob_match(rel, exclude_globs):
            continue
        try:
            st = os.stat(project / rel)
            hit = old.get(rel)
            if isinstance(hit, list) and len(hit) == 3 and hit[:2] == [st.st_size, st.st_mtime_ns]:
                sha = hit[2]
            else:
                sha = file_sha(project / rel)
        except OSError:  # gone between the listing and the read
            new.pop(rel, None)
            continue
        snap[rel] = sha
        if now - st.st_mtime_ns > RACY_NS:
            new[rel] = [st.st_size, st.st_mtime_ns, sha]
        else:
            new.pop(rel, None)
    if write_cache and new != old:
        try:
            cpath.parent.mkdir(parents=True, exist_ok=True)
            tmp = cpath.with_name(f"{cpath.name}.{os.getpid()}.tmp")
            tmp.write_text(json.dumps(new), encoding="utf-8")
            os.replace(tmp, cpath)  # two hooks may snapshot at the same moment: never a half-written file
        except OSError:
            pass
    return snap


def diff(before, after):
    added = sorted(set(after) - set(before))
    deleted = sorted(set(before) - set(after))
    modified = sorted(p for p in set(before) & set(after) if before[p] != after[p])
    return {"added": added, "modified": modified, "deleted": deleted}


def changed(d):
    return d["added"] + d["modified"] + d["deleted"]
