#!/usr/bin/env python3
"""PreToolUse(Bash): the git / gh guard of a harness session. ``--role orchestrator|agent``.

**Why a hook and not a sentence.** An agent that knows the rule still reaches for
``git checkout --`` or ``git stash`` to undo its own change, and wipes other agents' uncommitted
work with it; or pushes with ``--force`` to get done. A rule held by structure beats one held by
a sentence.

**Two tests.**
1. Scope = what you typed. A command that rewrites the tree or the index from git's memory
   (checkout/restore of paths, reset, clean, stash, apply -R, rm …) is denied to everyone: it
   touches more than the paths you named, and the rest is someone's uncommitted work.
2. Forcing and rewriting history are denied to everyone (push --force, branch -D, rebase,
   commit --amend, gh pr merge …): they are the user's.

**Roles.** Git writes belong to the orchestrator (the main session; the run commands call this
hook with ``--role orchestrator``), and only the ones on its list: stage and commit by path,
create a branch, change to an existing one on a clean tree, ``pull --ff-only``, fetch, push the
run's branch, ``branch -d``, worktree add/remove, tag, draft PR. A git write that is not on the
list is denied. Sub-agents (``--role agent``, from the agent files) read only, in a worktree of
their own too. Push and PR act outside the machine and also need ``"git": {"push": true}`` in the
project's ``.claude/gates.json``, set by the user.

**A writer's work is landed, not committed by hand.** ``gate.py land`` commits what a returned
writer changed and merges an agent's worktree into the run's branch; it calls git itself, so
nothing here has to allow it. What is left to the orchestrator's own ``git add`` / ``git commit``
is what it wrote itself. The denials below say so where a hand-made commit or merge was tried.

**Gates belong to the orchestrator.** A sub-agent may not run the harness's ``gate.py``: it
writes the run's ledger (marks, rounds, approvals, fixture locks). The one exception is
``gate.py check …``, the read-only self-check. Reading gate.py is not running it, and a project's
own ``gate.py`` is not the harness's.

**Against mistakes, not against intent.** The guard reads the command line; a determined bypass
(a command built from variables, git called inside a script) gets through. The default branch is
protected by server-side rules. Without ``--role`` the role is agent (the strictest).
"""
from __future__ import annotations

import json
import os
import pathlib
import re
import subprocess
import sys

sys.dont_write_bytecode = True  # no __pycache__ next to the user's own hooks
from shell_commands import QUOTED, command_words, commands, name  # noqa: E402

ROLE = "orchestrator" if sys.argv[1:3] == ["--role", "orchestrator"] else "agent"
HERE = pathlib.Path(__file__).resolve().parent
GATE = HERE.parent / "gates" / "gate.py"


# ---------------------------------------------------------------------------
# Repository state (what cannot be determined is not allowed)
# ---------------------------------------------------------------------------
def _git(d: str, *args: str) -> tuple[int, str]:
    try:
        r = subprocess.run(["git", "-C", d, *args], capture_output=True, text=True, timeout=10)
    except Exception:
        return 1, ""
    return r.returncode, r.stdout.strip()


def is_clean(d: str) -> bool:
    code, out = _git(d, "status", "--porcelain")
    return code == 0 and out == ""


def is_local_branch(d: str, branch: str) -> bool:
    return _git(d, "rev-parse", "--verify", "--quiet", f"refs/heads/{branch}")[0] == 0


def current_branch(d: str) -> str | None:
    code, out = _git(d, "symbolic-ref", "--short", "-q", "HEAD")
    return out if code == 0 and out else None


def default_branches(d: str) -> set[str]:
    names = {"main", "master"}
    code, out = _git(d, "symbolic-ref", "--short", "-q", "refs/remotes/origin/HEAD")
    if code == 0 and "/" in out:
        names.add(out.split("/", 1)[1])
    return names


def push_allowed(d: str) -> bool:
    code, top = _git(d, "rev-parse", "--show-toplevel")
    if code != 0 or not top:
        return False
    try:
        cfg = json.load(open(os.path.join(top, ".claude", "gates.json")))
    except Exception:
        return False
    return isinstance(cfg.get("git"), dict) and cfg["git"].get("push") is True


# ---------------------------------------------------------------------------
# Commands and the directory each runs in
# ---------------------------------------------------------------------------
_GIT_GLOBAL_WITH_ARG = {"-C", "-c", "--git-dir", "--work-tree", "--namespace", "--exec-path"}


def _resolve(word: str, base: str | None) -> str | None:
    """The directory a ``cd`` / ``-C`` argument names; None when it cannot be determined."""
    if word == QUOTED:
        return None
    path = os.path.expanduser(word)
    if not os.path.isabs(path):
        if base is None:
            return None
        path = os.path.join(base, path)
    return path if os.path.isdir(path) else None


def segments(command: str, cwd: str):
    """Each simple command with its directory. ``cd x`` moves the commands after it in the same
    subshell or substitution; a directory that cannot be determined is None."""
    dirs: dict = {}

    def here(scope):
        if scope not in dirs:
            dirs[scope] = here(scope[:-1]) if len(scope) > 1 else cwd
        return dirs[scope]

    for words, scope in commands(command):
        d = here(scope)
        first = command_words(words)[:1]
        if first and name(words[first[0]]) == "cd":
            args = words[first[0] + 1:]
            dirs[scope] = _resolve(args[0], d) if args else os.path.expanduser("~")
            continue
        yield words, d


def parse_git(toks: list[str], i: int, d: str | None):
    """After ``git``: global options → subcommand → arguments. ``-C <dir>`` changes the directory."""
    j = i + 1
    while j < len(toks) and toks[j].startswith("-"):
        opt = toks[j]
        if opt in _GIT_GLOBAL_WITH_ARG:
            if j + 1 >= len(toks):
                return None, [], None
            if opt == "-C":
                d = _resolve(toks[j + 1], d or os.getcwd())
            j += 2
        else:
            j += 1
    if j >= len(toks):
        return None, [], d
    return toks[j], toks[j + 1:], d


def flags_and_args(args: list[str]) -> tuple[list[str], list[str]]:
    return [a for a in args if a.startswith("-")], [a for a in args if not a.startswith("-")]


def has_short(flags: list[str], letter: str) -> bool:
    """A one-letter option, combined forms included (``-am``, ``-df``)."""
    return any(re.fullmatch(r"-[A-Za-z]+", f) and letter in f[1:] for f in flags)


# ---------------------------------------------------------------------------
# Rules
# ---------------------------------------------------------------------------
ORCH_ONLY = ("A sub-agent runs no git write, in a worktree of its own either: once you return, the "
             "orchestrator's `gate.py land` commits what you changed and merges it into the run's branch. "
             "Leave your changes in the files, and say in your return what else is needed (a branch, a push).")
LAND = "A returned writer's work is committed and merged by `gate.py land`, not by hand."
RESTORE = ("This command's scope is the tree or index as git sees it, not the paths you typed; "
           "the difference is other agents' uncommitted work.")
FORCE = "Forcing or rewriting history can destroy work; it is the user's."
MERGE = ("Merging is the user's, on the host, after review; an agent's worktree is merged into the run's "
         "branch by `gate.py land`. To bring a branch up to date: `git pull --ff-only`.")
NO_SWITCH = ("Push and PR act outside this machine: the user sets \"git\": {\"push\": true} in the "
             "project's .claude/gates.json. Without it, stop and ask the user.")
UNKNOWN_DIR = "The directory cannot be determined, so this is not allowed."

READ_ONLY = {"status", "diff", "log", "show", "ls-files", "ls-tree", "rev-parse", "blame", "grep",
             "archive", "cat-file", "describe", "shortlog", "merge-base", "rev-list", "show-ref",
             "for-each-ref", "name-rev", "check-ignore", "check-attr", "count-objects", "version",
             "help", "var", "whatchanged", "range-diff", "cherry", "show-branch", "difftool",
             "ls-remote", "diff-tree", "diff-index", "diff-files", "fsck", "verify-commit",
             "verify-tag", "format-patch", "merge-tree", "annotate", "check-ref-format",
             "init", "clone"}  # init / clone only create something new


def not_listed(sub: str) -> str:
    return (f"`git {sub}` is not on the orchestrator's list: add, commit, switch -c / checkout -b, "
            "switch <existing branch>, pull --ff-only, fetch, push, branch -d, worktree add/remove, "
            "tag, and every read.")


def restore_rules(sub: str, args: list[str]) -> str | None:
    """What tests 1 and 2 deny to both roles."""
    flags, pos = flags_and_args(args)
    if sub in ("restore", "reset", "clean", "rm", "checkout-index", "read-tree"):
        alt = {"restore": "git show HEAD:<path> > <path>",
               "reset": "copy the file before you change it; to undo, copy it back and prove it with cmp",
               "clean": "rm the files you created, by name",
               "rm": "plain rm; whether it leaves the index is decided by the paths staged at commit"}.get(sub)
        return RESTORE + (f"\nInstead: {alt}" if alt else "")
    if sub in ("revert", "rebase", "filter-branch", "filter-repo", "update-ref", "update-index", "replace"):
        return FORCE
    if sub == "stash" and not (pos[:1] in (["list"], ["show"])):
        return RESTORE + "\nInstead: git worktree add <temp dir> HEAD (the baseline elsewhere, your tree untouched)"
    if sub == "apply" and ("-R" in flags or "--reverse" in flags):
        return RESTORE + "\nInstead: copy the file back and prove it with cmp; the diff was taken against HEAD"
    if sub == "worktree" and pos[:1] == ["remove"] and ("--force" in flags or has_short(flags, "f")):
        return ("Land that worktree's work first (`gate.py land`), then `gate.py worktrees --clean`, or "
                "`git worktree remove` without --force.")
    if sub == "worktree" and pos[:1] == ["add"] and ("--force" in flags or has_short(flags, "f")
                                                     or has_short(flags, "B")):
        return FORCE
    if sub == "pull" and ("--rebase" in flags or has_short(flags, "r") or "--force" in flags):
        return FORCE
    if sub == "reflog" and pos[:1] in (["expire"], ["delete"]):
        return FORCE
    return None


def switch_rules(sub: str, args: list[str], d: str | None) -> str | None:
    """The orchestrator's switch / checkout: a new branch at any time; an existing branch on a
    clean tree; nothing else."""
    flags, pos = flags_and_args(args)
    quiet = {"-q", "--quiet"}
    create = {"switch": {"-c", "--create"}, "checkout": {"-b"}}[sub]
    other = [f for f in flags if f not in quiet and f not in create]
    if "--" not in args and not other and len(pos) == 1:
        if any(f in create for f in flags):
            return None  # a new branch at HEAD: the tree is not touched
        branch = pos[0]
        if d is None:
            return UNKNOWN_DIR
        if not is_local_branch(d, branch):
            return RESTORE + f"\n{branch} is not a local branch. To restore a path: git show HEAD:<path> > <path>"
        if not is_clean(d):
            return (f"The tree in {d} is not clean (git status --porcelain prints something). Changing "
                    "branch needs a clean tree: wait for the writer to return, land the returned writers "
                    "(`gate.py land`), and commit what you wrote yourself by path.")
        return None
    if any(f in ("-C", "-B", "-f", "--force", "--discard-changes", "--orphan", "--detach", "--merge", "-m")
           for f in flags):
        return FORCE
    return (RESTORE + "\nNew branch: `git switch -c <name>` / `git checkout -b <name>` (no start point). "
            "Existing branch: `git switch <branch>`.")


def branch_rules(args: list[str]) -> str | None:
    flags, pos = flags_and_args(args)
    listing = {"--list", "-l", "-a", "--all", "-r", "--remotes", "-v", "-vv", "--verbose",
               "--show-current", "--contains", "--merged", "--no-merged", "--sort", "--format",
               "--points-at", "--color", "--no-color", "--column", "--no-column"}
    if all(f.split("=")[0] in listing for f in flags) and (not pos or any(
            f.split("=")[0] in ("--list", "-l", "--contains", "--merged", "--no-merged", "--points-at",
                                "--sort", "--format") for f in flags)):
        return None  # a listing
    if ROLE != "orchestrator":
        return ORCH_ONLY
    if "-D" in flags or "--force" in flags or has_short(flags, "f") or has_short(flags, "D") \
            or "-M" in flags or "-C" in flags:
        return FORCE + "\nAn unmerged branch is the user's to delete; `git branch -d` refuses one by itself."
    if flags in ([], ["-q"]) and len(pos) == 1:
        return None  # a new branch at HEAD
    if all(f in ("-d", "--delete") for f in flags) and flags and pos:
        return None  # git refuses to delete an unmerged branch
    return "Only `git branch <name>` (at HEAD) and `git branch -d <name>`."


def add_rules(args: list[str]) -> str | None:
    flags, pos = flags_and_args(args)
    if any(f in ("-A", "--all", "-u", "--update", "-f", "--force", "--no-ignore-removal") for f in flags) \
            or has_short(flags, "A") or has_short(flags, "u") or has_short(flags, "f"):
        return ("Stage by path: git add <the files you wrote>. -A / -u / -f take other agents' uncommitted "
                "work too. " + LAND)
    if any(p in (".", "./", ":/", ":", "*", "-") for p in pos) or not pos:
        return ("Stage by path: git add <the files you wrote>. `.` is the whole tree, other agents' work "
                "included. " + LAND)
    return None


def commit_rules(args: list[str]) -> str | None:
    flags, _ = flags_and_args(args)
    if "--amend" in flags:
        return FORCE + "\nAmending rewrites the last commit; make a new one."
    if "--no-verify" in flags or has_short(flags, "n"):
        return "Skipping the project's commit hooks relaxes a check (Constitution §4.5)."
    if "--all" in flags or has_short(flags, "a"):
        return "commit -a commits other agents' uncommitted changes too: git add <paths>, then commit. " + LAND
    return None


def push_rules(args: list[str], d: str | None) -> str | None:
    flags, pos = flags_and_args(args)
    ok_flags = {"-u", "--set-upstream", "-q", "--quiet", "-v", "--verbose"}
    if any(f not in ok_flags for f in flags) or len(pos) > 2:
        return FORCE + "\nOnly `git push [-u] [origin] [<the run's branch>]`: no --force / --delete / --tags / --all."
    if d is None:
        return UNKNOWN_DIR
    if not push_allowed(d):
        return NO_SWITCH
    ref = pos[1] if len(pos) == 2 else "HEAD"
    if "+" in ref or ":" in ref:
        return FORCE + "\nPush the run's branch itself, without + or :."
    branch = current_branch(d) if ref == "HEAD" else ref
    if branch is None:
        return "Not on a branch (detached HEAD): no push."
    if branch in default_branches(d):
        return f"No push to {branch}. A change goes branch → PR → merged by the user."
    return None


def worktree_rules(args: list[str]) -> str | None:
    """A worktree lays the baseline out elsewhere. Creating a branch with it is a git write."""
    flags, pos = flags_and_args(args)
    verb = pos[:1]
    if verb == ["list"]:
        return None
    if verb == ["add"]:
        new_branch = has_short(flags, "b") or "--orphan" in flags or \
            (len(pos) < 3 and "--detach" not in flags and not has_short(flags, "d"))  # no commit: a branch named after the dir
        return ORCH_ONLY + "\nFor a baseline: git worktree add <temp dir> HEAD" \
            if new_branch and ROLE != "orchestrator" else None
    if verb in (["remove"], ["prune"]):
        return None
    return ORCH_ONLY if ROLE != "orchestrator" else not_listed("worktree " + " ".join(verb))


def git_decision(sub: str | None, args: list[str], d: str | None) -> str | None:
    if sub is None or sub in READ_ONLY:
        return None
    reason = restore_rules(sub, args)
    if reason:
        return reason
    flags, pos = flags_and_args(args)
    orchestrator = ROLE == "orchestrator"
    if sub == "stash":
        return None  # list / show; every other form was denied above
    if sub == "apply":  # a forward patch touches the files it names; --index / --cached also write the index
        to_index = any(f in ("--index", "--cached", "--3way", "-3") for f in flags)
        return ORCH_ONLY + "\nApply to the working tree only: git apply <patch>" \
            if to_index and not orchestrator else None
    if sub == "worktree":
        return worktree_rules(args)
    if sub == "branch":
        return branch_rules(args)
    if sub in ("tag", "remote", "config", "symbolic-ref", "reflog", "notes", "submodule"):
        # the listing and reading forms are allowed to both roles; the rest write
        reading = (not pos and all(f in ("-l", "--list", "-v", "--get", "--get-all", "--show-origin",
                                         "--get-regexp", "--local", "-n") for f in flags)) or \
                  (sub == "remote" and pos[:1] in (["get-url"], ["show"])) or \
                  (sub == "config" and any(f in ("--get", "--get-all", "--list", "-l", "--get-regexp")
                                           for f in flags)) or \
                  (sub == "symbolic-ref" and len(pos) == 1) or \
                  (sub == "reflog" and pos[:1] in ([], ["show"])) or \
                  (sub == "notes" and pos[:1] in ([], ["list"], ["show"])) or \
                  (sub == "submodule" and pos[:1] in ([], ["status"]))
        if reading:
            return None
        if not orchestrator:
            return ORCH_ONLY
        if sub == "tag":
            return FORCE if has_short(flags, "f") or "--force" in flags else None
        return not_listed(sub)
    if not orchestrator:
        return ORCH_ONLY
    if sub in ("switch", "checkout"):
        return switch_rules(sub, args, d)
    if sub == "add":
        return add_rules(args)
    if sub == "commit":
        return commit_rules(args)
    if sub == "push":
        return push_rules(args, d)
    if sub == "fetch":
        return FORCE if "--force" in flags or has_short(flags, "f") or any(p.startswith("+") for p in pos) else None
    if sub == "pull":
        return None if "--ff-only" in flags else "Only `git pull --ff-only`: any other pull can merge."
    if sub == "merge":  # a fast-forward moves the branch as `pull --ff-only` does; anything else merges
        return None if "--ff-only" in flags else MERGE
    return not_listed(sub)


# gh: only the listed subcommands; the rest is the user's
GH_READ = {("pr", "view"), ("pr", "list"), ("pr", "status"), ("pr", "diff"), ("pr", "checks"),
           ("issue", "view"), ("issue", "list"), ("issue", "status"), ("run", "view"), ("run", "list"),
           ("run", "watch"), ("repo", "view"), ("auth", "status"), ("release", "view"),
           ("release", "list"), ("workflow", "view"), ("workflow", "list"), ("search", "*"),
           ("status", "*"), ("browse", "*")}
GH_ORCH = {("pr", "create"), ("pr", "ready"), ("pr", "edit"), ("pr", "comment")}


def gh_decision(args: list[str], d: str | None) -> str | None:
    if not args:
        return None
    group = args[0]
    sub = args[1] if len(args) > 1 and not args[1].startswith("-") else "*"
    if group == "api":
        flags = args[1:]
        method = None
        for k, a in enumerate(flags):
            if a in ("-X", "--method") and k + 1 < len(flags):
                method = flags[k + 1].upper()
            elif a.startswith("--method="):
                method = a.split("=", 1)[1].upper()
        if method is None:
            method = "POST" if any(a in ("-f", "-F", "--field", "--raw-field", "--input")
                                   or a.startswith(("--field=", "--raw-field=", "--input="))
                                   for a in flags) else "GET"
        return None if method == "GET" else "gh api is allowed for reads (GET) only; a write is the user's."
    if (group, sub) in GH_READ or (group, "*") in GH_READ:
        return None
    if (group, sub) in GH_ORCH:
        if ROLE != "orchestrator":
            return ORCH_ONLY
        if d is None:
            return UNKNOWN_DIR
        if not push_allowed(d):
            return NO_SWITCH
        if sub == "create" and not ({"--draft", "-d"} & set(args)):
            return "Open the PR as a draft: gh pr create --draft …; mark it ready at Acceptance with gh pr ready."
        return None
    if (group, sub) == ("pr", "merge"):
        return "Merging is the user's, on the host, after review."
    return f"gh {group} {sub if sub != '*' else ''} is not on the allowed list.".replace("  ", " ")


FOOTER = ("\n\nEvery git read is allowed: status / diff / log / show / ls-files / archive / worktree add "
          "<temp dir> HEAD.\nIf you do need the denied command, say so and let the user run it "
          "(`! <command>` in the prompt). Do not work around this.")


# ---------------------------------------------------------------------------
# The harness's gate.py
# ---------------------------------------------------------------------------
GATE_DENIED = ("Only the orchestrator runs the gates: gate.py writes the run's ledger (marks, rounds, "
               "approvals), and a run by you would use up a fix round and upset the role checks. "
               "Return your result and evidence; the orchestrator runs the gate.\n"
               "To check your own documents before you return, run only "
               "`gate.py check <gate> --project <root>`: it is read-only. <root> is the root of the tree "
               "you work in, your worktree's when you have one.")
_PYTHON = re.compile(r"^python[\d.]*$")


def is_harness_gate(path: str, d: str | None) -> bool:
    """Is this path the harness's gate.py — not a project's own file of the same name?"""
    if os.path.basename(path) != "gate.py":
        return False
    if path.endswith(".claude/gates/gate.py"):  # ~/…, $HOME/…, an absolute path
        return True
    path = os.path.expanduser(os.path.expandvars(path))
    if not os.path.isabs(path):
        if d is None:
            return False
        path = os.path.join(d, path)
    return os.path.realpath(path) == os.path.realpath(GATE)


def gate_calls(command: str, cwd: str):
    """The arguments of every run of the harness's gate.py: as the command itself, or handed to python."""
    for words, d in segments(command, cwd):
        first = command_words(words)
        for i, w in enumerate(words):
            if is_harness_gate(w.raw, d) and (i in first or any(_PYTHON.match(name(x)) for x in words[:i])):
                yield words[i + 1:]


def decide(command: str, cwd: str) -> str | None:
    for words, d in segments(command, cwd):
        for k in command_words(words):  # git and gh count only where a command stands
            tool = name(words[k])
            if tool == "git":
                reason = git_decision(*parse_git(words, k, d))
            elif tool == "gh":
                reason = gh_decision(words[k + 1:], d)
            else:
                continue
            if reason:
                return reason
    return None


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0  # unreadable input is not denied: a hook must not become a new source of failure
    if payload.get("tool_name") != "Bash":
        return 0
    command = str(payload.get("tool_input", {}).get("command", ""))
    cwd = str(payload.get("cwd") or os.getcwd())
    if ROLE == "agent" and any(args[:1] != ["check"] for args in gate_calls(command, cwd)):
        print(json.dumps({"hookSpecificOutput": {
            "hookEventName": "PreToolUse", "permissionDecision": "deny",
            "permissionDecisionReason": f"[agent] {GATE_DENIED}"}}))
        return 0
    reason = decide(command, cwd)
    if reason:
        print(json.dumps({"hookSpecificOutput": {
            "hookEventName": "PreToolUse", "permissionDecision": "deny",
            "permissionDecisionReason": f"[{ROLE}] {reason}{FOOTER}"}}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
