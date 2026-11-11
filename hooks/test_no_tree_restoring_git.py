#!/usr/bin/env python3
"""``no-tree-restoring-git.py`` 的回归矩阵。跑法：``python3 <本文件>``，退出码即结果。

按角色分两半：协调者（``--role orchestrator``）能开分支、按路径提交、推本轮分支、开草稿 PR；
子代理（``--role agent``，也是缺省）只读。两者都不许重写整棵树、强制、改写历史。

**ALLOW 用例和 DENY 用例同等重要。** 一个会对 ``grep -rn 'git checkout' docs/`` 开火的守卫，
会在第一次有人查这条禁令的出处时显得愚蠢，然后被关掉。
"""
import json
import os
import pathlib
import subprocess
import sys
import tempfile

HOOK = pathlib.Path(__file__).with_name("no-tree-restoring-git.py")
D, A = True, False  # deny / allow

# (命令, 协调者, 子代理) —— 不依赖仓库状态的
CASES: list[tuple[str, bool, bool]] = [
    # —— 两种角色都拦：重写整棵树 ——
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
    # —— 两种角色都拦：强制、改写历史 ——
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
    ("gh pr checkout 27", D, D),                       # 会换分支
    ("gh repo delete x", D, D),
    ("gh api -X DELETE repos/o/r/git/refs/heads/x", D, D),
    ("gh api repos/o/r/pulls/1/merge -X PUT", D, D),
    ("gh api repos/o/r/issues -f title=x", D, D),      # -f 隐含 POST
    # —— 协调者可以、子代理不行 ——
    ("git switch -c feature/x", A, D),
    ("git checkout -b feature/x", A, D),
    ("git checkout -q -b feature/x", A, D),
    ("git branch feature/x", A, D),
    ("git branch -d old", A, D),
    ("git add review/views.py tests/test_x.py", A, D),
    ("git commit -m x", A, D),
    ("git commit -q -F - <<'EOF'\nmsg with git push --force inside\nEOF", A, D),
    ("git fetch -q origin", A, D),
    ("git pull --ff-only", A, D),
    ("git merge --ff-only origin/main", A, D),
    # —— 协调者也不行：按路径暂存 ——
    ("git add -A", D, D),
    ("git add .", D, D),
    ("git add -u", D, D),
    ("git add -f ignored.log", D, D),
    ("git add -A && git commit -m x", D, D),
    ("git checkout -b x origin/main", D, D),           # 带起点 = 换到另一个提交
    ("git switch --detach HEAD~1", D, D),
    # —— 两种角色都放行：只读与认可的替代路径 ——
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
    # —— 数据不是命令 ——
    ("grep -rn 'git checkout' docs/", A, A),
    ('grep -rn "git push --force" ~/.claude/', A, A),
    ("cat > d.md <<'EOF'\n禁止 git checkout -- 与 git stash\nEOF", A, A),
    ("cat > d.md <<'EOF'\n正文\nEOF\ngit reset --hard", D, D),  # heredoc 之后的真命令照拦
    # —— 绕过写法 ——
    ('bash -c "git push --force"', D, D),
    ("sh -c 'git reset --hard'", D, D),
    ("eval 'git stash'", D, D),
    ('git -C "some dir" reset --hard', D, D),          # 引号目录不能让子命令漏掉
    ("echo hi && git reset --hard", D, D),
    ("ls; git clean -fd", D, D),
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
        open(os.path.join(path, "new.txt"), "w").close()  # 未跟踪也算脏
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
        check("[no role] %r" % command, denies(command, None), agent)  # 缺省 = agent

    with tempfile.TemporaryDirectory() as tmp:
        clean = make_repo(os.path.join(tmp, "clean"))
        dirty = make_repo(os.path.join(tmp, "dirty"), dirty=True)
        plain = os.path.join(tmp, "plain")
        os.mkdir(plain)
        on_feat = make_repo(os.path.join(tmp, "on_feat"), branch="feature", push=True)
        on_main = make_repo(os.path.join(tmp, "on_main"), push=True)
        no_sw = make_repo(os.path.join(tmp, "no_sw"), branch="feature")
        sw_off = make_repo(os.path.join(tmp, "sw_off"), branch="feature", push=False)
        # (命令, 目录, 协调者是否被拦)；子代理在这些用例上一律被拦（只读的除外，见末尾）
        cwd_cases = [
            # 换到已有分支：只要干净，任意分支
            ("git switch main", clean, A),
            ("git checkout feature", clean, A),
            ("git checkout -q main && git pull --ff-only", clean, A),
            ("git -C %s switch feature" % clean, plain, A),
            ("cd %s && git switch main && git pull --ff-only" % clean, plain, A),
            ("git switch main", dirty, D),
            ("git checkout feature", dirty, D),
            ("cd %s && git switch main" % dirty, clean, D),
            ("git switch main", plain, D),                       # 不是仓库：查不清
            ("git checkout nosuchbranch", clean, D),             # 不是本地分支 = 恢复路径
            ("git checkout main -- f.py", clean, D),
            ("git checkout main f.py", clean, D),
            ("git switch main && git reset --hard", clean, D),   # 其余规则照拦
            # 新建分支不看干净与否
            ("git switch -c x", dirty, A),
            # 推送：要开关、不推默认分支
            ("git push -u origin feature", on_feat, A),
            ("git push -u origin feature 2>&1 | tail -2", on_feat, A),
            ("git push", on_feat, A),
            ("git push origin HEAD", on_feat, A),
            ("git push", on_main, D),                            # 当前分支是 main
            ("git push origin main", on_feat, D),
            ("git push origin master", on_feat, D),
            ("git push -u origin feature", no_sw, D),            # 没有 gates.json 开关
            ("git push -u origin feature", sw_off, D),           # 开关为 false
            ("git push", plain, D),
            # PR：要开关、先开草稿
            ("gh pr create --draft --title x --body-file - <<'EOF'\nbody\nEOF", on_feat, A),
            ("gh pr create -d --fill", on_feat, A),
            ("gh pr create --title x --body y", on_feat, D),     # 不是草稿
            ("gh pr create --draft --fill", no_sw, D),
            ("gh pr ready 27", on_feat, A),
            ("gh pr ready 27", no_sw, D),
            ("gh pr edit 27 --add-label x", on_feat, A),
        ]
        for command, cwd, orch in cwd_cases:
            name = os.path.basename(cwd)
            check("[orch] %r @ %s" % (command, name), denies(command, "orchestrator", cwd), orch)
            check("[agent] %r @ %s" % (command, name), denies(command, "agent", cwd), D)
        # 只读在任何目录下两种角色都放行
        for cwd in (clean, dirty, plain):
            for role in ("orchestrator", "agent"):
                check("[%s] status @ %s" % (role, os.path.basename(cwd)), denies("git status", role, cwd), A)

    # 非 Bash 工具一律不管
    check("non-Bash tool", bool(run_hook("git stash", "agent", tool="Edit")), A)
    print("%d cases, %d failures" % (total, failures))
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
