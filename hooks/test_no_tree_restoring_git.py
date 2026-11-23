#!/usr/bin/env python3
"""Regression matrix of ``no-tree-restoring-git.py``. Run: ``python3 <this file>``; the exit code is the result.

Two halves by role: the orchestrator (``--role orchestrator``) runs the git writes on its list
(branch, commit by path, push the run's branch, draft PR); a sub-agent (``--role agent``, also
the default) reads only, in a worktree of its own too. Neither may rewrite the tree, force, or
rewrite history. A writer's work reaches the run's branch through ``gate.py land``: the denials of
a hand-made commit or merge say so.

**The ALLOW cases matter as much as the DENY cases.** A guard that fires on
``grep -rn 'git checkout' docs/`` looks foolish the first time someone looks the rule up, and is
switched off.
"""
from __future__ import annotations

import json
import os
import pathlib
import subprocess
import sys
import tempfile

HOOK = pathlib.Path(__file__).with_name("no-tree-restoring-git.py")
ROOT = HOOK.resolve().parent.parent  # the harness root: its gates/gate.py is the harness's gate
D, A = True, False  # deny / allow

# (command, orchestrator, sub-agent): cases that do not depend on a repository's state
CASES: list[tuple[str, bool, bool]] = [
    # -- denied to both: rewrites the tree --
    ("git checkout -- review/views.py", D, D),
    ("git checkout -q -- review/views.py", D, D),
    ("git checkout tests/x.docx", D, D),
    ("git restore --staged f.py", D, D),
    ("git reset --hard HEAD", D, D),
    ("git clean -fd", D, D),
    ("git rm --cached f", D, D),
    ("git stash push -u", D, D),
    ("git stash", D, D),
    ("git apply -R /tmp/round1.diff", D, D),
    ("git worktree remove --force /tmp/base", D, D),
    # -- denied to both: force, rewriting history --
    ("git branch -D old", D, D),
    ("git branch -df old", D, D),
    ("git branch --delete --force old", D, D),
    ("git switch -C x", D, D),
    ("git checkout -B x", D, D),
    ("git switch -f main", D, D),
    ("git switch --discard-changes main", D, D),
    ("git revert HEAD", D, D),
    ("git rebase main", D, D),
    ("git pull --rebase", D, D),
    ("git commit --amend -m x", D, D),
    ("git commit --no-verify -m x", D, D),
    ("git commit -am x", D, D),
    ("git push --force", D, D),
    ("git push -f origin x", D, D),
    ("git push --force-with-lease origin x", D, D),
    ("git push origin +x", D, D),
    ("git push origin x:main", D, D),
    ("git push origin --delete x", D, D),
    ("git push --tags", D, D),
    ("gh pr merge 27", D, D),
    ("gh pr merge 27 --squash", D, D),
    ("gh pr checkout 27", D, D),                       # changes branch
    ("gh repo delete x", D, D),
    ("gh api -X DELETE repos/o/r/git/refs/heads/x", D, D),
    ("gh api repos/o/r/pulls/1/merge -X PUT", D, D),
    ("gh api repos/o/r/issues -f title=x", D, D),      # -f implies POST
    # -- the orchestrator may, a sub-agent may not --
    ("git switch -c feature/x", A, D),
    ("git checkout -b feature/x", A, D),
    ("git checkout -q -b feature/x", A, D),
    ("git branch feature/x", A, D),
    ("git branch -d old", A, D),
    ("git add review/views.py tests/test_x.py", A, D),
    ("git commit -m x", A, D),
    ("git commit -q -F - <<'EOF'\nmsg with git push --force inside\nEOF", A, D),
    ('git commit -m "$(cat <<\'EOF\'\nFix it; don\'t git stash (ever)\nEOF\n)"', A, D),  # the message is data
    ("git fetch -q origin", A, D),
    ("git pull --ff-only", A, D),
    ("git merge --ff-only origin/main", A, D),
    # -- not the orchestrator either: stage by path --
    ("git add -A", D, D),
    ("git add .", D, D),
    ("git add -u", D, D),
    ("git add -f ignored.log", D, D),
    ("git add -A && git commit -m x", D, D),
    ("git checkout -b x origin/main", D, D),           # a start point = another commit
    ("git switch --detach HEAD~1", D, D),
    # -- allowed to both: reads and the approved alternatives --
    ("git status --short", A, A),
    ("git diff --stat", A, A),
    ("git log --oneline -5", A, A),
    ("git ls-files", A, A),
    ("git stash list", A, A),
    ("git stash show -p", A, A),
    ("git branch", A, A),
    ("git branch -a", A, A),
    ("git branch --show-current", A, A),
    ("git branch --list 'feat*'", A, A),
    ("git remote -v", A, A),
    ("git config --get user.name", A, A),
    ("git show HEAD:review/views.py > review/views.py", A, A),
    ("git archive HEAD | tar -x -C /tmp/base", A, A),
    ("git worktree add /tmp/base HEAD", A, A),
    ("git worktree remove /tmp/base", A, A),
    ("git -c core.pager=cat log -1", A, A),
    ("gh pr view 27", A, A),
    ("gh pr list --state open", A, A),
    ("gh pr checks 27", A, A),
    ("gh api repos/o/r/pulls", A, A),
    ("gh api -X GET search/issues -f q=x", A, A),
    # -- data is not a command --
    ("grep -rn 'git checkout' docs/", A, A),
    ('grep -rn "git push --force" ~/.claude/', A, A),
    ("cat > d.md <<'EOF'\nnever git checkout -- or git stash\nEOF", A, A),
    ("cat > d.md <<'EOF'\nbody\nEOF\ngit reset --hard", D, D),  # a real command after the heredoc
    # -- forms that used to slip through --
    ('bash -c "git push --force"', D, D),
    ("sh -c 'git reset --hard'", D, D),
    ("eval 'git stash'", D, D),
    ('git -C "some dir" reset --hard', D, D),          # a quoted directory must not hide the subcommand
    ("echo hi && git reset --hard", D, D),
    ("ls; git clean -fd", D, D),
    ("git status 2>/dev/null; git stash", D, D),       # a redirection does not swallow the separator
    ("git status >/dev/null 2>&1 && git reset --hard", D, D),
    ("git diff > /tmp/x.diff; git clean -fd", D, D),
    ("bash -lc 'git stash'", D, D),
    ("bash -ic 'git stash'", D, D),
    ('zsh -lic "git reset --hard"', D, D),
    ('OUT="$(git stash)"', D, D),                       # substitution inside double quotes is code
    ('echo "saved: `git stash`"', D, D),
    ("X=$(git stash)", D, D),
    ('bash -c "echo $(git stash)"', D, D),
    ("if ! git diff --quiet; then git stash; fi", D, D),
    ("time git stash", D, D),
    ("env GIT_PAGER=cat git clean -fd", D, D),
    ("git ls-files | xargs git checkout --", D, D),
    ("find . -name '*.orig' -exec git clean -f {} \\;", D, D),
    ("# don't lose this\ngit stash", D, D),             # a quote in a comment hides nothing
    ("cat <<'EOF' > notes.md; git stash\nbody\nEOF", D, D),  # the rest of a heredoc's line is code
    # -- the orchestrator's git writes are a list; what is not on it is denied --
    ("git merge feature", D, D),
    ("git merge --no-ff feature", D, D),
    ("git pull", D, D),
    ("git pull origin main", D, D),
    ("git checkout-index -a -f", D, D),
    ("git read-tree HEAD", D, D),
    ("git cherry-pick abc123", D, D),
    ("git am fix.patch", D, D),
    ("git mv a.py b.py", D, D),
    ("git gc", D, D),
    ("git update-ref refs/heads/x HEAD", D, D),
    ("git filter-branch --all", D, D),
    ("git remote add origin https://example.com/x.git", D, D),
    ("git config user.name x", D, D),
    ("git tag -f v1", D, D),
    ("git fetch -f origin", D, D),
    ("git fetch origin +main:main", D, D),
    ("git worktree add -B tmp /tmp/base HEAD", D, D),
    ("git worktree lock /tmp/base", D, D),
    ("git tag v1", A, D),
    ("git fetch --prune", A, D),
    ("git pull --ff-only origin main", A, D),
    # -- a sub-agent writes neither the index nor a branch --
    ("git apply --index /tmp/fix.diff", A, D),
    ("git apply --cached /tmp/fix.diff", A, D),
    ("git worktree add -b tmp /tmp/base HEAD", A, D),
    ("git worktree add /tmp/base", A, D),               # no commit named: a branch named after the dir
    ("git apply /tmp/fix.diff", A, A),
    ("git worktree add --detach /tmp/base", A, A),
    ("git ls-remote origin", A, A),
    ("git diff-tree --no-commit-id -r HEAD", A, A),
    # -- git and gh count only where a command stands --
    ("grep -rn git docs/", A, A),
    ("which git gh", A, A),
    ("echo git", A, A),
    ("echo git stash", A, A),
    ("command -v git", A, A),
    ("ls .git && cat .git/HEAD", A, A),
    ("pip show gitpython | grep -i git", A, A),
    # -- the gates are the orchestrator's; a sub-agent runs only `gate.py check` --
    ("python3 ~/.claude/gates/gate.py p4 --project .", A, D),
    ('python3 "$HOME/.claude/gates/gate.py" mark --role be-developer', A, D),
    ("python3 ${HOME}/.claude/gates/gate.py p2 --project .", A, D),
    ("~/.claude/gates/gate.py p2 --project .", A, D),
    ('bash -c "python3 ~/.claude/gates/gate.py p5"', A, D),
    ("uv run python ~/.claude/gates/gate.py p5", A, D),
    ("time python3 -u ~/.claude/gates/gate.py p5", A, D),
    ('OUT="$(python3 ~/.claude/gates/gate.py p5)"', A, D),
    ("python3 ~/.claude/gates/gate.py check p2 --project .", A, A),
    ('python3 "$HOME/.claude/gates/gate.py" check fe-ux --project .', A, A),
    ("python3 ~/.claude/gates/gate.py land --project .", A, D),
    ("python3 ~/.claude/gates/gate.py worktrees --clean --project .", A, D),
    ("python3 ~/.claude/gates/gate.py check p2 --project . && python3 ~/.claude/gates/gate.py p2 --project .", A, D),
    ("python3 ~/.claude/gates/gate.py check p2; python3 ~/.claude/gates/gate.py mark --role be-developer", A, D),
    ("python3 ~/.claude/gates/gate.py --project . check p2", A, D),  # exactly `gate.py check …`
    ("cat ~/.claude/gates/gate.py", A, A),                  # reading the source is not running it
    ("grep -n gate.py README.md", A, A),
    ("cat > d.md <<'EOF'\npython3 gate.py p4\nEOF", A, A),
    ("python3 src/gate.py --all", A, A),                    # a project's own gate.py
    ("src/gate.py", A, A),
    ("python3 gate.py p4", A, A),
    ("", A, A),
]


def run_hook(command: str, role: str | None, cwd: str | None = None, tool: str = "Bash") -> str:
    payload = {"tool_name": tool, "tool_input": {"command": command}}
    if cwd:
        payload["cwd"] = cwd
    args = [sys.executable, str(HOOK)] + (["--role", role] if role else [])
    return subprocess.run(args, input=json.dumps(payload), capture_output=True, text=True,
                          check=True, cwd=cwd or tempfile.gettempdir()).stdout.strip()


def denies(command: str, role: str | None, cwd: str | None = None) -> bool:
    out = run_hook(command, role, cwd)
    return bool(out) and json.loads(out)["hookSpecificOutput"]["permissionDecision"] == "deny"


def git(d, *args):
    subprocess.run(["git", "-C", d, "-c", "user.name=t", "-c", "user.email=t@t", *args],
                   check=True, capture_output=True)


def make_repo(path, branch="main", push=None, dirty=False, extra_branch="feature"):
    git(os.path.dirname(path), "init", "-q", "-b", "main", path)
    if push is not None:
        os.makedirs(os.path.join(path, ".claude"))
        with open(os.path.join(path, ".claude", "gates.json"), "w") as f:
            json.dump({"git": {"push": push}}, f)
        git(path, "add", ".claude/gates.json")
    git(path, "commit", "-q", "--allow-empty", "-m", "init")
    git(path, "branch", extra_branch)
    if branch != "main":
        git(path, "switch", "-q", branch)
    if dirty:
        open(os.path.join(path, "new.txt"), "w").close()  # untracked counts as dirty
    return path


def main() -> int:
    failures, total = 0, 0

    def check(label, got, want):
        nonlocal failures, total
        total += 1
        if got != want:
            failures += 1
            print("FAIL want=%s got=%s  %s" % ("DENY" if want else "ALLOW", "DENY" if got else "ALLOW", label))

    for command, orch, agent in CASES:
        check("[orch] %r" % command, denies(command, "orchestrator"), orch)
        check("[agent] %r" % command, denies(command, "agent"), agent)
        check("[no role] %r" % command, denies(command, None), agent)  # the default is agent

    with tempfile.TemporaryDirectory() as tmp:
        clean = make_repo(os.path.join(tmp, "clean"))
        dirty = make_repo(os.path.join(tmp, "dirty"), dirty=True)
        plain = os.path.join(tmp, "plain")
        os.mkdir(plain)
        on_feat = make_repo(os.path.join(tmp, "on_feat"), branch="feature", push=True)
        on_main = make_repo(os.path.join(tmp, "on_main"), push=True)
        no_sw = make_repo(os.path.join(tmp, "no_sw"), branch="feature")
        sw_off = make_repo(os.path.join(tmp, "sw_off"), branch="feature", push=False)
        # (command, directory, orchestrator denied?); a sub-agent is denied every one of these
        cwd_cases = [
            # to an existing branch: any branch, on a clean tree
            ("git switch main", clean, A),
            ("git checkout feature", clean, A),
            ("git checkout -q main && git pull --ff-only", clean, A),
            ("git -C %s switch feature" % clean, plain, A),
            ("cd %s && git switch main && git pull --ff-only" % clean, plain, A),
            ("git switch main", dirty, D),
            ("git checkout feature", dirty, D),
            ("cd %s && git switch main" % dirty, clean, D),
            ("git switch main", plain, D),                       # not a repository: cannot be determined
            ("git checkout nosuchbranch", clean, D),             # not a local branch = restoring a path
            ("git checkout main -- f.py", clean, D),
            ("git checkout main f.py", clean, D),
            ("git switch main && git reset --hard", clean, D),   # the other rules still apply
            # a new branch does not need a clean tree
            ("git switch -c x", dirty, A),
            # push: needs the switch, never the default branch
            ("git push -u origin feature", on_feat, A),
            ("git push -u origin feature 2>&1 | tail -2", on_feat, A),
            ("git push", on_feat, A),
            ("git push origin HEAD", on_feat, A),
            ("git push", on_main, D),                            # the current branch is main
            ("git push origin main", on_feat, D),
            ("git push origin master", on_feat, D),
            ("git push -u origin feature", no_sw, D),            # no switch in gates.json
            ("git push -u origin feature", sw_off, D),           # the switch is false
            ("git push", plain, D),
            # PR: needs the switch, opens as a draft
            ("gh pr create --draft --title x --body-file - <<'EOF'\nbody\nEOF", on_feat, A),
            ("gh pr create -d --fill", on_feat, A),
            ("gh pr create --title x --body y", on_feat, D),     # not a draft
            ("gh pr create --draft --fill", no_sw, D),
            ("gh pr ready 27", on_feat, A),
            ("gh pr ready 27", no_sw, D),
            ("gh pr edit 27 --add-label x", on_feat, A),
        ]
        for command, cwd, orch in cwd_cases:
            name = os.path.basename(cwd)
            check("[orch] %r @ %s" % (command, name), denies(command, "orchestrator", cwd), orch)
            check("[agent] %r @ %s" % (command, name), denies(command, "agent", cwd), D)
        # a read is allowed to both roles in any directory
        for cwd in (clean, dirty, plain):
            for role in ("orchestrator", "agent"):
                check("[%s] status @ %s" % (role, os.path.basename(cwd)), denies("git status", role, cwd), A)

        # the harness's gate.py by location: (command, directory, sub-agent denied?)
        own = os.path.join(tmp, "own")
        os.makedirs(os.path.join(own, "gates"))
        for f in ("gate.py", os.path.join("gates", "gate.py")):
            open(os.path.join(own, f), "w").close()
        gate_cases = [
            ("cd gates && python3 -u gate.py p1", str(ROOT), D),
            ('bash -c "python3 gate.py p5"', str(ROOT / "gates"), D),
            ("python3 gates/gate.py mark --role be-developer", str(ROOT), D),
            ("python3 %s p4 --project ." % (ROOT / "gates" / "gate.py"), plain, D),
            ("python3 gates/gate.py check p1 --project .", str(ROOT), A),
            ("python3 gate.py p4", own, A),                      # a project's own files of the same name
            ("python3 gates/gate.py p4", own, A),
            ("cd gates && python3 gate.py p4", own, A),
        ]
        for command, cwd, agent in gate_cases:
            where = os.path.basename(cwd)
            check("[orch] %r @ %s" % (command, where), denies(command, "orchestrator", cwd), A)
            check("[agent] %r @ %s" % (command, where), denies(command, "agent", cwd), agent)
        # a `cd` inside a subshell or a substitution does not move the commands after it
        check("[orch] cd in a subshell", denies("(cd %s && git status); git switch main" % dirty, "orchestrator", clean), A)
        check("[orch] cd in a substitution",
              denies('H="$(cd %s && git rev-parse HEAD)"; git switch main' % clean, "orchestrator", dirty), D)

        # An isolated sub-agent works in a worktree of the run's repository: it reads, and writes
        # nothing through git; the orchestrator does not merge its branch by hand either.
        wt = os.path.join(clean, ".claude", "worktrees", "agent-w1")
        git(clean, "worktree", "add", "-q", wt, "-b", "worktree-agent-w1")
        for command in ("git add src/a.py", "git commit -m mine", "git merge main", "git merge --ff-only main",
                        "git switch main", "git branch -d worktree-agent-w1",
                        "git -C %s merge --ff-only worktree-agent-w1" % clean,
                        "python3 %s land --project %s" % (ROOT / "gates" / "gate.py", clean)):
            check("[agent] %r @ worktree" % command, denies(command, "agent", wt), D)
        for command in ("git status --short", "git diff main", "git log --oneline -3", "git merge-base HEAD main",
                        "python3 %s check p4 --project ." % (ROOT / "gates" / "gate.py")):
            check("[agent] %r @ worktree" % command, denies(command, "agent", wt), A)
        for command in ("git merge worktree-agent-w1", "git merge --no-ff worktree-agent-w1",
                        "git -C %s merge main" % wt, "git worktree remove --force %s" % wt):
            check("[orch] %r" % command, denies(command, "orchestrator", clean), D)

    def why(command, role):
        out = run_hook(command, role)
        return json.loads(out)["hookSpecificOutput"]["permissionDecisionReason"] if out else ""

    # a hand-made commit or merge of a writer's work is pointed to `gate.py land`
    for command, role in (("git commit -m x", "agent"), ("git add src/a.py", "agent"), ("git add -A", "orchestrator"),
                          ("git add .", "orchestrator"), ("git commit -am x", "orchestrator"),
                          ("git merge worktree-agent-w1", "orchestrator"),
                          ("git worktree remove --force .claude/worktrees/agent-w1", "orchestrator")):
        check("[%s] %r names `gate.py land`" % (role, command), "gate.py land" in why(command, role), True)
    check("no denial mentions another team", any("other team" in why(c, r) for c, _, _ in CASES for r in
                                                 ("orchestrator", "agent")), False)
    # the gate denial tells a sub-agent what it may run instead
    text = json.loads(run_hook("python3 ~/.claude/gates/gate.py p4", "agent"))["hookSpecificOutput"]
    check("gate denial names `gate.py check`", "gate.py check" in text["permissionDecisionReason"], True)
    # other tools are not this hook's business
    check("non-Bash tool", bool(run_hook("git stash", "agent", tool="Edit")), A)
    print("%d cases, %d failures" % (total, failures))
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
