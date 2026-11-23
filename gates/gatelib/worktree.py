"""Parallel writers in git worktrees: where an isolated agent works, what it changed, and how its
work gets onto the run's branch.

An agent dispatched with `isolation: "worktree"` works in `<project>/.claude/worktrees/agent-<id>`
on branch `worktree-agent-<id>`. It never commits; `land` commits its work, merges the run's branch
into the worktree, collapses the result into one commit on top of the run's branch (the worktree's
branch is private; the run's branch gets one commit per landing and no merge commit) and
fast-forwards the run's branch to it. The run's branch is whatever the main checkout
(`ctx.project`) is on. Nothing here writes the run log: `gate.py` appends what these functions
return.

    main_root(cwd) -> Path | None            the main checkout of the repository `cwd` is in
    path_of(project, agent_id) -> Path | None  the agent's worktree, when it exists
    base_setting(project, home=None) -> bool  whether Claude Code starts worktrees from the local HEAD
    setup(project, links=()) -> dict          write that setting and exclude the worktrees from
                                              `git status`; returns the `worktree` block written
    dirty_ok(ctx) -> [paths]                  uncommitted changes an isolated agent would not see
    refresh(ctx, wt) -> None                  fast-forward an idle worktree to the run's branch
    changes(ctx, wt) -> dict                  {"added", "modified", "deleted", "files", "paths"}
    land(ctx, log, dispatch, ret, tree_paths=None) -> dict
    line(events, result) -> str               the one stdout line of a `land` result
    listing(ctx, events) -> [dict]            the worktrees and their state
    clean(ctx, events) -> [paths]             remove the landed ones

`wt` is a worktree as an absolute path or relative to the project.

`land(ctx, log, dispatch, ret, tree_paths=None)`: `log` is the run log's path (read only),
`dispatch` and `ret` the dispatch event and its return event. The dispatch is an isolated one when
it carries `isolated` or `worktree`, or its return carries `worktree`; its worktree is the return's
`worktree`, else the dispatch's, else the one of the return's `agent_id`. Any other dispatch is an
in-tree writer, and `tree_paths` are the project-relative paths it added, modified or deleted since
its mark (None: only the run dir is staged). Returns the fields of the `land` event:

    {"agent", "dispatch": <seq>, "result": "merged" | "committed" | "empty" | "conflict" | "refused",
     "commit": <sha, merged/committed>, "files": <count, merged/committed>,
     "paths": <at most 20 files at fault, conflict/refused>, "note": <one line>,
     "owner": <who acts on a conflict or a refusal: the agent type, or "orchestrator">}

A key without a value is left out. An isolated dispatch that carries `head` (the run's branch when
it went out) and is not a continuation is refused when its worktree does not descend from that
commit. A worktree whose author is out in it again (an open dispatch names it by `worktree` or
`agent_id`) is refused until that one returns: its files are half-written. An agent cannot run
`git add`, so a conflict counts as resolved when none of its files holds a marker line any more; one
without markers (a binary file, one side deleted) is taken as resolved with what the worktree holds
on the next `land`: its author was named the paths.
"""
import json
import os
import pathlib
import re
import subprocess
import tempfile
import time

from . import checks, runlog, snap
from .common import ConfigError, glob_match

ROOT = ".claude/worktrees"
LOCAL_SETTINGS = ".claude/settings.local.json"  # the client rewrites it at any time: no one's change
MARKER = re.compile(rb"^(?:<<<<<<< |>>>>>>> )", re.M)
BASE_NOTE = ("this worktree did not start from the run's branch (worktree.baseRef is not in effect: "
             "restart the session); dispatch its work again")


def _git(cwd, *args, data=None):
    """git in `cwd`; every path it is given is a literal path, never a pattern."""
    return subprocess.run(["git", "-C", str(cwd), *args], input=data, capture_output=True, text=True,
                          env={**os.environ, "GIT_LITERAL_PATHSPECS": "1"})


def _out(cwd, *args):
    r = _git(cwd, *args)
    return r.stdout.strip() if r.returncode == 0 and r.stdout.strip() else None


def _z(text):
    return [p for p in text.split("\0") if p]


def _why(r):
    return (r.stderr or r.stdout).strip()[-200:]


def _need(r, what):
    if r.returncode != 0:
        raise ConfigError(f"{what}: {_why(r)}")
    return r


def _abs(ctx, wt):
    wt = pathlib.Path(wt)
    return wt if wt.is_absolute() else ctx.project / wt


def _rel(ctx, wt):
    try:
        return pathlib.Path(wt).resolve().relative_to(ctx.project).as_posix()
    except ValueError:
        return str(wt)


# ---------- where ----------

def main_root(cwd):
    """The main checkout of the repository `cwd` is in, also from inside one of its worktrees; None
    outside git, and where the repository's git dir is not a `.git` directory (a submodule, a bare
    repository)."""
    cwd = pathlib.Path(cwd or ".")
    common = _out(cwd, "rev-parse", "--path-format=absolute", "--git-common-dir") if cwd.is_dir() else None
    common = pathlib.Path(common) if common else None
    return common.parent.resolve() if common is not None and common.name == ".git" else None


def path_of(project, agent_id):
    """`<project>/.claude/worktrees/agent-<agent_id>` when that directory exists."""
    name = re.sub(r"[^A-Za-z0-9_.-]", "", str(agent_id or ""))
    wt = pathlib.Path(project) / ROOT / f"agent-{name}"
    return wt if name and wt.is_dir() else None


def _is_worktree(ctx, wt):
    """Whether `wt` is a checkout of its own. In a plain directory inside the project, git would
    act on the main checkout instead."""
    top = _out(wt, "rev-parse", "--show-toplevel") if pathlib.Path(wt).is_dir() else None
    return bool(top) and pathlib.Path(top).resolve() == pathlib.Path(wt).resolve() != ctx.project


def _branch(tree):
    """(what to merge the tree's HEAD by, its sha): the full branch ref, or the sha when detached."""
    sha = _out(tree, "rev-parse", "HEAD")
    name = _out(tree, "symbolic-ref", "-q", "HEAD")
    return name or sha, sha


# ---------- the setting that makes a worktree start from the run's branch ----------

def _settings(path):
    try:
        data = json.loads(pathlib.Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def base_setting(project, home=None):
    """Whether `worktree.baseRef` is "head", so a worktree starts from the session's HEAD and not
    from the remote's default branch. The first of the project's settings.local.json, its
    settings.json and the user's `~/.claude/settings.json` that sets the key decides, as in Claude Code."""
    home = pathlib.Path(home) if home else pathlib.Path.home()
    project = pathlib.Path(project)
    for f in (project / LOCAL_SETTINGS, project / ".claude" / "settings.json", home / ".claude" / "settings.json"):
        block = _settings(f).get("worktree")
        if isinstance(block, dict) and "baseRef" in block:
            return block["baseRef"] == "head"
    return False


def setup(project, links=()):
    """Merge `{"worktree": {"baseRef": "head", "symlinkDirectories": [...]}}` into
    `<project>/.claude/settings.json`, creating it; every other key stays, `links` are added to the
    directories already listed. Also keeps `.claude/worktrees/` out of `git status` (`_exclude`).
    Returns the `worktree` block as written."""
    path = pathlib.Path(project) / ".claude" / "settings.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    except ValueError as e:
        raise ConfigError(f"{path} is not JSON ({e}): repair it first; nothing was written")
    if not isinstance(data, dict) or not isinstance(data.get("worktree", {}), dict):
        raise ConfigError(f"{path}: the file and its `worktree` key must be JSON objects; nothing was written")
    block = dict(data.get("worktree") or {})
    block["baseRef"] = "head"
    had = block.get("symlinkDirectories")
    dirs = list(dict.fromkeys([*(had if isinstance(had, list) else []), *(str(d).strip("/") for d in links)]))
    if dirs:
        block["symlinkDirectories"] = dirs
    data["worktree"] = block
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    _exclude(project)
    return block


def _exclude(project):
    """Keep the worktrees out of `git status`: one line in the repository's own `info/exclude`
    (local to the clone; nothing tracked changes)."""
    common = _out(project, "rev-parse", "--path-format=absolute", "--git-common-dir")
    if not common:
        return
    path = pathlib.Path(common) / "info" / "exclude"
    text = path.read_text(encoding="utf-8") if path.is_file() else ""
    if f"{ROOT}/" not in [ln.strip() for ln in text.splitlines()]:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text + ("" if not text or text.endswith("\n") else "\n") + f"{ROOT}/\n", encoding="utf-8")


# ---------- what a tree holds ----------

def _foreign_link(tree, rel):
    """A symlink that leads out of the tree: a dependency directory linked from the main checkout
    (`symlinkDirectories`). An ignore pattern written `name/` does not cover the link."""
    p = pathlib.Path(tree) / rel
    if not p.is_symlink():
        return False
    try:
        p.resolve().relative_to(pathlib.Path(tree).resolve())
    except ValueError:
        return True
    return False


def _untracked(tree):
    """Untracked, not ignored files that are someone's work: no cache or dependency directory
    (a `build/` or `dist/` may be new source, so it counts), no linked dependency directory, not
    the client's local settings."""
    loose = [p.rstrip("/") for p in _z(_git(tree, "ls-files", "-o", "--exclude-standard", "-z").stdout)]
    return [p for p in loose
            if p != LOCAL_SETTINGS and not snap.skipped(p, tracked=True) and not _foreign_link(tree, p)]


def _status(tree, untracked="no"):
    """The paths `git status` reports as changed in the index or the tree."""
    out = _git(tree, "status", "--porcelain", "-z", "--no-renames", f"--untracked-files={untracked}").stdout
    return [e[3:] for e in out.split("\0") if len(e) > 3]


def _merging(tree):
    return _git(tree, "rev-parse", "-q", "--verify", "MERGE_HEAD").returncode == 0


def _unmerged(tree):
    return sorted(_z(_git(tree, "diff", "--name-only", "--diff-filter=U", "-z").stdout))


def dirty_ok(ctx):
    """[] when an isolated agent may start from the last commit; else the main checkout's
    uncommitted paths it would not see. The run's bookkeeping (the log and its rendering run-log.md,
    state.json, gates/, logs/, stats.md), the worktrees, the client's local settings and
    `volatile_globs` are no one's work:
    the orchestrator rewrites state.json after every transition, and no writer needs its latest copy."""
    if not ctx.git:
        return []
    r = ctx.run_rel
    fine = [f"{r}/run-log.jsonl", f"{r}/run-log.md", f"{r}/state.json", f"{r}/gates/**", f"{r}/logs/**",
            f"{r}/stats.md", f"{ROOT}/**", LOCAL_SETTINGS, *ctx.cfg.get("volatile_globs", [])]
    return sorted(p for p in dict.fromkeys(_status(ctx.project, "all")) if not glob_match(p, fine))


def refresh(ctx, wt):
    """Before an isolated author is continued: fast-forward its worktree to the run's branch when it
    has no uncommitted change and no merge in progress; otherwise it is left as it is."""
    wt = _abs(ctx, wt)
    if not _is_worktree(ctx, wt) or _merging(wt) or _status(wt) or _untracked(wt):
        return
    _git(wt, "merge", "-q", "--ff-only", _branch(ctx.project)[0])


def _base(ctx, wt):
    """What a worktree's changes are measured against: the merge-base of its HEAD with the run's
    branch; during a merge of the run's branch, the commit being merged."""
    if _merging(wt):
        return "MERGE_HEAD"
    tip = _branch(ctx.project)[1]
    return _out(wt, "merge-base", "HEAD", tip) or tip


def _kinds(ctx, wt):
    """{path: "added" | "modified" | "deleted"} of everything in the worktree that differs from its
    base, committed or not, plus its untracked files; `volatile_globs` are no one's change."""
    names = _z(_need(_git(wt, "diff", "--name-status", "--no-renames", "-z", _base(ctx, wt)),
                     f"cannot read the changes in {_rel(ctx, wt)}").stdout)
    kinds = {p: {"A": "added", "D": "deleted"}.get(k[:1], "modified") for k, p in zip(names[::2], names[1::2])}
    for p in _untracked(wt):
        kinds.setdefault(p, "added")
    skip = [LOCAL_SETTINGS, *ctx.cfg.get("volatile_globs", [])]
    return {p: k for p, k in kinds.items() if not glob_match(p, skip)}


def changes(ctx, wt):
    """What an isolated writer changed, in the shape of `writer_changes`: counts, `files` as
    `path (+a/-b)` (at most 20), and `paths`, every changed path."""
    wt = _abs(ctx, wt)
    if not _is_worktree(ctx, wt):
        raise ConfigError(f"{_rel(ctx, wt)} is not a git worktree of this project")
    kinds = _kinds(ctx, wt)
    by = {k: sorted(p for p, kind in kinds.items() if kind == k) for k in ("added", "modified", "deleted")}
    paths = by["added"] + by["modified"] + by["deleted"]
    shown, lines = paths[:20], {}
    if shown:
        r = _git(wt, "diff", "--numstat", "--no-renames", "-z", _base(ctx, wt), "--", *shown)
        for row in _z(r.stdout) if r.returncode == 0 else []:
            cells = row.split("\t", 2)
            if len(cells) == 3 and cells[0].isdigit() and cells[1].isdigit():
                lines[cells[2]] = (int(cells[0]), int(cells[1]))
        for p in shown:
            if p not in lines and (wt / p).is_file():
                try:
                    lines[p] = (len((wt / p).read_text(encoding="utf-8").splitlines()), 0)
                except (UnicodeDecodeError, OSError):
                    continue
    return {"added": len(by["added"]), "modified": len(by["modified"]), "deleted": len(by["deleted"]),
            "files": [f"{p} (+{lines[p][0]}/-{lines[p][1]})" if p in lines else p for p in shown],
            "paths": paths}


# ---------- landing ----------

def ordinal(events, dispatch):
    """The `#<n>` of a dispatch among its agent type; a continuation keeps its agent's."""
    n, by_id = 0, {}
    for row in runlog.dispatches(events):
        d, r = row["dispatch"], row["return"]
        if d.get("agent") != dispatch.get("agent"):
            continue
        if d.get("continued"):
            k = by_id.get(d.get("agent_id")) or max(n, 1)
        else:
            n += 1
            k = n
        for aid in (d.get("agent_id"), (r or {}).get("agent_id")):
            if aid:
                by_id[aid] = k
        if d.get("seq") == dispatch.get("seq"):
            return k
    return max(n, 1)


def _message(events, dispatch):
    task = " ".join(str(dispatch.get("note") or "").split())
    msg = f"{dispatch.get('agent')} #{ordinal(events, dispatch)} · step {dispatch.get('phase')}"
    return (f"{msg} · {task}" if task else msg)[:72].rstrip(" ·")


def _stage(tree, paths):
    """`git add -A` for exactly `paths`. A path git cannot take is left out: one that is gone and
    was never tracked, one that is ignored."""
    tree = pathlib.Path(tree)
    gone = [p for p in paths if not os.path.lexists(tree / p)]
    tracked = set(_z(_git(tree, "ls-files", "-z").stdout)) if gone else set()
    keep = [p for p in dict.fromkeys(paths) if p not in gone or p in tracked]
    if keep:
        ignored = set(_z(_git(tree, "check-ignore", "-z", "--stdin", data="\0".join(keep) + "\0").stdout))
        keep = [p for p in keep if p not in ignored]
    if keep:
        _need(_git(tree, "add", "-A", "--pathspec-from-file=-", "--pathspec-file-nul", data="\0".join(keep) + "\0"),
              f"git add failed in {tree}")


def _commit(tree, *args):
    return _git(tree, "commit", "-q", *args)


def _union(wt, rel):
    """Resolve one conflicted text file by keeping both sides' lines; False when it is not that
    kind of conflict (one side deleted it, a binary file, a link)."""
    stages = {}
    for row in _z(_git(wt, "ls-files", "-u", "-z", "--", rel).stdout):
        mode, sha, stage = row.split("\t", 1)[0].split()
        stages[stage] = (mode, sha)
    if not all(s in stages and stages[s][0].startswith("100") for s in ("2", "3")):
        return False
    with tempfile.TemporaryDirectory() as d:
        files = []
        for name, stage in (("ours", "2"), ("base", "1"), ("theirs", "3")):
            blob = subprocess.run(["git", "-C", str(wt), "cat-file", "blob", stages[stage][1]],
                                  capture_output=True).stdout if stage in stages else b""
            files.append(os.path.join(d, name))
            pathlib.Path(files[-1]).write_bytes(blob)
        r = subprocess.run(["git", "merge-file", "--union", "-p", *files], capture_output=True)
    if r.returncode != 0:
        return False
    (wt / rel).parent.mkdir(parents=True, exist_ok=True)
    (wt / rel).write_bytes(r.stdout)
    return _git(wt, "add", "--", rel).returncode == 0


def _met(events, wt, own):
    """The landed agents whose commits the worktree's own work does not hold yet."""
    names = []
    for ev in events:
        if ev.get("event") == "land" and ev.get("result") in ("merged", "committed") and ev.get("commit") \
                and _git(wt, "merge-base", "--is-ancestor", ev["commit"], own).returncode != 0:
            d = next((x for x in events if x.get("event") == "dispatch" and x.get("seq") == ev.get("dispatch")),
                     {"agent": ev.get("agent")})
            names.append(f"{ev.get('agent')} #{ordinal(events, d)}")
    return list(dict.fromkeys(names))


def _result(dispatch, result, **fields):
    return {"agent": dispatch.get("agent"), "dispatch": dispatch.get("seq"), "result": result,
            **{k: v for k, v in fields.items() if v not in (None, "", [])}}


def _land_tree(ctx, dispatch, tree_paths, msg):
    skip = [f"{ROOT}/**", *ctx.cfg.get("volatile_globs", [])]
    _stage(ctx.project, [*(p for p in tree_paths or [] if not glob_match(p, skip)), ctx.run_rel])
    staged = _z(_git(ctx.project, "diff", "--cached", "--name-only", "-z").stdout)
    if not staged:
        return _result(dispatch, "empty")
    r = _commit(ctx.project, "-m", msg)
    if r.returncode != 0:
        return _result(dispatch, "refused", owner="orchestrator",
                       note=f"git commit failed: {_why(r)}")
    return _result(dispatch, "committed", commit=_branch(ctx.project)[1], files=len(staged))


def land(ctx, log, dispatch, ret, tree_paths=None):
    """Put one returned writer's work on the run's branch (module docstring: arguments and result)."""
    ret = ret or {}
    events = runlog.events(pathlib.Path(log))
    agent, msg = dispatch.get("agent"), _message(events, dispatch)
    named = ret.get("worktree") or dispatch.get("worktree")
    if not (dispatch.get("isolated") or named):
        return _land_tree(ctx, dispatch, tree_paths, msg)
    wt = _abs(ctx, named) if named else path_of(ctx.project, ret.get("agent_id") or dispatch.get("agent_id"))
    if wt is None or not wt.is_dir():
        return _result(dispatch, "empty", note="no worktree: its agent left it unchanged")
    rel, aid = _rel(ctx, wt), ret.get("agent_id") or dispatch.get("agent_id")
    if not _is_worktree(ctx, wt):
        return _result(dispatch, "refused", owner="orchestrator", note=f"{rel} is not a git worktree of this project")
    still_out = [row["dispatch"] for row in runlog.dispatches(events) if row["return"] is None]
    if any(d.get("worktree") == rel or (aid and d.get("agent_id") == aid) for d in still_out):
        return _result(dispatch, "refused", owner="orchestrator",
                       note="its agent is out again in this worktree: land after it returns")
    run_ref, tip = _branch(ctx.project)
    own = _branch(wt)[1]

    def conflict(paths):
        met = _met(events, wt, own)
        return _result(dispatch, "conflict", paths=paths[:20], owner=agent,
                       note=f"met {', '.join(met)}" if met else None)

    def refused(owner, note, paths=()):
        return _result(dispatch, "refused", paths=list(paths)[:20], owner=owner, note=note)

    if _merging(wt):  # an earlier land left a conflict with its author
        left = [p for p in _unmerged(wt) if MARKER.search(_read(wt / p))]
        if left:
            return conflict(left)
        _stage(wt, [*_status(wt), *_untracked(wt)])
        r = _commit(wt, "--no-edit")
        if r.returncode != 0:
            return refused("orchestrator", f"git commit failed: {_why(r)}")
    else:
        head = dispatch.get("head")
        if head and not dispatch.get("continued") \
                and _git(wt, "merge-base", "--is-ancestor", head, "HEAD").returncode != 0:
            return refused("orchestrator", BASE_NOTE)
        mine = sorted(_kinds(ctx, wt))
        if not mine:
            return _result(dispatch, "empty")
        # The run's books are the orchestrator's and the gates': never a writer's, never union-merged.
        books = [f"{ctx.run_rel}/run-log.jsonl", f"{ctx.run_rel}/run-log.md", f"{ctx.run_rel}/state.json",
                 f"{ctx.run_rel}/gates/**", ".claude/*.json"]
        wrong = sorted({*(p for p in mine if glob_match(p, books)), *checks.role_paths(ctx, agent, mine)})
        if wrong:
            return refused(agent, "put these back, or have them planned", wrong)
        _stage(wt, mine)
        if _git(wt, "diff", "--cached", "--quiet").returncode != 0:
            r = _commit(wt, "-m", msg)
            if r.returncode != 0:
                return refused(agent, f"git commit failed: {_why(r)}")

    r = _git(wt, "merge", "-q", "--no-edit", run_ref)
    if r.returncode != 0:
        if not _merging(wt):
            return refused("orchestrator", f"git merge failed: {_why(r)}")
        union = [g.replace("<run>", ctx.run_rel) for g in (ctx.cfg.get("worktree") or {}).get("union_globs") or []]
        for p in _unmerged(wt):
            if glob_match(p, union):
                _union(wt, p)
        left = _unmerged(wt)
        if left:
            return conflict(left)
        r = _commit(wt, "--no-edit")
        if r.returncode != 0:
            return refused("orchestrator", f"git commit failed: {_why(r)}")

    new = _branch(wt)[1]
    if new == tip:
        return _result(dispatch, "empty")
    if (_out(wt, "rev-list", "--parents", "-1", "HEAD") or "").split()[1:] != [tip]:
        # One commit per landing: whatever the worktree's branch holds beyond the run's branch (its
        # agent's commit, the merge) becomes a single commit on top of it, with the merged tree.
        _need(_git(wt, "reset", "-q", "--soft", tip), f"git reset --soft failed in {rel}")
        if _git(wt, "diff", "--cached", "--quiet").returncode == 0:
            return _result(dispatch, "empty")  # its net change is what the run's branch already holds
        r = _commit(wt, "-m", msg)
        if r.returncode != 0:
            return refused(agent, f"git commit failed: {_why(r)}")
        new = _branch(wt)[1]
    r = _git(ctx.project, "merge", "-q", "--ff-only", new)
    landed = _z(_git(ctx.project, "diff", "--name-only", "--no-renames", "-z", tip, new).stdout)
    if r.returncode != 0:  # the worktree keeps its commit: the next land repeats only this step
        blocked = sorted(set(_status(ctx.project, "all")) & set(landed))
        return refused("orchestrator", "commit your bookkeeping first" if blocked
                       else f"git merge --ff-only failed: {_why(r)}", blocked)
    checks.forgive(ctx, landed)
    return _result(dispatch, "merged", commit=new, files=len(landed))


def _read(path):
    try:
        return path.read_bytes()
    except OSError:  # deleted by its author: no markers left
        return b""


def line(events, result):
    """`[land] fe-engineer #2 · merged a1b2c3d · 7 files` / `… · conflict: a.ts, b.ts (met be-developer #1)`."""
    d = next((ev for ev in events if ev.get("event") == "dispatch" and ev.get("seq") == result.get("dispatch")),
             {"agent": result.get("agent")})
    head = f"[land] {result.get('agent')} #{ordinal(events, d)} · {result['result']}"
    if result["result"] in ("merged", "committed"):
        return f"{head} {str(result.get('commit') or '')[:7]} · {result.get('files', 0)} files"
    paths = ", ".join(result.get("paths") or [])
    return head + (f": {paths}" if paths else "") + (f" ({result['note']})" if result.get("note") else "")


# ---------- listing and cleaning ----------

def listing(ctx, events):
    """The worktrees under `.claude/worktrees/agent-*`: `path`, `agent_id`, `agent` and `dispatch`
    (the latest dispatch the log ties to it, else None), `branch`, `locked`, `age` (seconds) and
    `state`, read from git: `out` (locked, or its dispatch has not returned), `conflict` (a merge
    in progress), `unlanded` (changes, or commits the run's branch does not hold), `landed`.
    An isolated agent tells no one its id before it returns: while one is out, a worktree the log
    does not know may be its own and is `out` too."""
    known, tip, unnamed = {}, _branch(ctx.project)[1], False
    for row in runlog.dispatches(events):
        d, r = row["dispatch"], row["return"] or {}
        unnamed = unnamed or bool(row["return"] is None and d.get("isolated") and not d.get("continued"))
        for key in (d.get("agent_id"), r.get("agent_id"), d.get("worktree"), r.get("worktree")):
            if key:
                known[str(key)] = row
    admin, cur = {}, None
    for text in _git(ctx.project, "worktree", "list", "--porcelain").stdout.splitlines():
        word, _, rest = text.partition(" ")
        if word == "worktree":
            cur = admin.setdefault(str(pathlib.Path(rest).resolve()), {})
        elif cur is not None and word in ("branch", "locked"):
            cur[word] = rest or True
    out = []
    for wt in sorted((ctx.project / ROOT).glob("agent-*")):
        if not _is_worktree(ctx, wt):
            continue
        rel, aid = _rel(ctx, wt), wt.name[len("agent-"):]
        row, info = known.get(aid) or known.get(rel), admin.get(str(wt.resolve()), {})
        locked = bool(info.get("locked"))
        if locked or (row is None and unnamed) or (row is not None and row["return"] is None):
            state = "out"
        elif _merging(wt):
            state = "conflict"
        elif _kinds(ctx, wt) or _git(wt, "merge-base", "--is-ancestor", "HEAD", tip).returncode != 0:
            state = "unlanded"
        else:
            state = "landed"
        try:
            age = int(time.time() - (wt / ".git").stat().st_mtime)
        except OSError:
            age = None
        out.append({"path": rel, "agent_id": aid, "agent": row["dispatch"].get("agent") if row else None,
                    "dispatch": row["dispatch"].get("seq") if row else None,
                    "branch": str(info.get("branch") or "").replace("refs/heads/", "") or None,
                    "locked": locked, "age": age, "state": state})
    return out


def clean(ctx, events):
    """Remove the landed worktrees that are not locked, and their branches; returns their paths.
    Git itself refuses a worktree with changes and a branch that is not merged."""
    removed = []
    for row in listing(ctx, events):
        if row["state"] != "landed" or row["locked"]:
            continue
        wt = ctx.project / row["path"]
        for p in _z(_git(wt, "ls-files", "-o", "--exclude-standard", "-z").stdout):
            if _foreign_link(wt, p.rstrip("/")):  # the link, never the directory it leads to
                (wt / p.rstrip("/")).unlink()
        if _git(ctx.project, "worktree", "remove", str(wt)).returncode != 0:
            continue
        if row["branch"]:
            _git(ctx.project, "branch", "-d", row["branch"])
        removed.append(row["path"])
    _git(ctx.project, "worktree", "prune")
    return removed
