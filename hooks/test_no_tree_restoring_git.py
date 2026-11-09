#!/usr/bin/env python3
"""``no-tree-restoring-git.py`` 的回归矩阵。跑法：``python3 <本文件>``，退出码即结果。

前半是代理「撤掉自己改动」时常用、却会连带抹掉别人活的命令
（`git checkout --` / `git apply -R` / `git stash`），外加同族的 reset / clean / restore。

**后半的 ALLOW 同样重要，而且更容易被忽略。** 一个会对
``grep -rn 'git checkout' docs/`` 开火的守卫，会在第一次有人查这条禁令的出处时
显得愚蠢，然后被关掉。**守卫的假阳性率决定它能活多久**，所以这些用例和拦截
用例是同一等级的验收项，不是补充。
"""
import json
import os
import pathlib
import subprocess
import sys
import tempfile

HOOK = pathlib.Path(__file__).with_name("no-tree-restoring-git.py")

CASES: list[tuple[str, bool]] = [
    # —— 撤改动的常见写法 ——
    ("git checkout -- review/views.py", True),          # 连同别人未提交的改动一起恢复
    ("git apply -R /tmp/round1.diff", True),            # diff 对 HEAD 算，连别人的活一起撤
    ("git checkout tests/corpus/synthetic/x.docx", True),
    ("git stash push -u", True),
    ("git stash pop", True),
    # 只读：拦了它们守卫就会被关掉
    ("git stash list", False),
    ("git stash show -p", False),
    # —— 同族 ——
    ("git reset --hard HEAD", True),
    ("git clean -fd", True),
    ("cd /x && git restore --staged f.py", True),
    ("git rm --cached f", True),
    ("git branch -D old", True),
    ("git switch main", True),
    ("echo hi && git checkout main", True),             # 藏在复合命令里
    # —— 只读，必须放行 ——
    ("git status --short", False),
    ("git diff --stat", False),
    ("git log --oneline -5", False),
    ("git ls-files", False),
    # —— 认可的替代路径，必须放行 ——
    ("git show HEAD:review/views.py > review/views.py", False),
    ("git archive HEAD | tar -x -C /tmp/base", False),
    ("git worktree add /tmp/base HEAD", False),
    # 自建的临时 worktree 要清得掉，否则这条替代路径没人会用第二次
    ("git worktree remove /tmp/base", False),
    ("git worktree remove --force /tmp/base", True),
    ("git checkout -b feature/x", False),
    ("git checkout -q -b feature/x origin/main", False),  # 新建分支必须放行
    ("git checkout --quiet -b feature/x", False),
    ("git checkout -q -- review/views.py", True),
    ("git checkout -B feature/x", True),
    ("git add -A && git commit -m x", False),
    # —— 假阳性：命令里出现的是字符串，不是命令 ——
    ("grep -rn 'git checkout' docs/", False),
    ('grep -rn "git stash" ~/.claude/', False),
    ("cat > d.md <<'EOF'\n禁止 git checkout -- 与 git stash\nEOF", False),
    # —— 但 heredoc 之后的真命令仍要拦 ——
    ("cat > d.md <<'EOF'\n正文\nEOF\ngit reset --hard", True),
    # —— 非 Bash 工具与空命令 ——
    ("", False),
]


def denies(command: str, cwd: str | None = None) -> bool:
    payload = {"tool_name": "Bash", "tool_input": {"command": command}}
    if cwd:
        payload["cwd"] = cwd
    out = subprocess.run(
        [sys.executable, str(HOOK)], input=json.dumps(payload),
        capture_output=True, text=True, check=True, cwd=cwd or tempfile.gettempdir(),
    ).stdout.strip()
    if not out:
        return False
    return json.loads(out)["hookSpecificOutput"]["permissionDecision"] == "deny"


def main() -> int:
    failures = 0
    for command, want_deny in CASES:
        got = denies(command)
        if got != want_deny:
            failures += 1
            print("FAIL want=%s got=%s  %r"
                  % ("DENY" if want_deny else "ALLOW",
                     "DENY" if got else "ALLOW", command))
    # —— 唯一的换分支例外：干净工作区切回 main——
    with tempfile.TemporaryDirectory() as tmp:
        clean, dirty, plain = (os.path.join(tmp, n) for n in ("clean", "dirty", "plain"))
        os.mkdir(plain)
        for d in (clean, dirty):
            subprocess.run(["git", "init", "-q", "-b", "main", d], check=True)
            subprocess.run(["git", "-C", d, "-c", "user.name=t", "-c", "user.email=t@t",
                            "commit", "-q", "--allow-empty", "-m", "init"], check=True)
        open(os.path.join(dirty, "new.txt"), "w").close()  # 未跟踪也算脏
        cwd_cases = [
            ("git checkout main", clean, False),
            ("git switch main", clean, False),
            ("git checkout -q main && git pull", clean, False),
            ("git -C %s checkout main" % clean, plain, False),
            ("cd %s && git checkout main && git pull --ff-only" % clean, plain, False),
            ("git checkout main", dirty, True),
            ("git switch main", dirty, True),
            ("cd %s && git checkout main" % dirty, clean, True),
            ("git checkout main", plain, True),                  # 不是仓库：查不清
            ("git checkout develop", clean, True),               # 只认 main
            ("git checkout main -- f.py", clean, True),          # 恢复路径，不是换分支
            ("git checkout main f.py", clean, True),
            ("git switch -c x", clean, True),
            ("git checkout main && git reset --hard", clean, True),  # 其余规则照拦
        ]
        for command, cwd, want_deny in cwd_cases:
            got = denies(command, cwd)
            if got != want_deny:
                failures += 1
                print("FAIL want=%s got=%s  %r @ %s" % ("DENY" if want_deny else "ALLOW",
                      "DENY" if got else "ALLOW", command, os.path.basename(cwd)))
    failures_extra = len(cwd_cases)
    # 非 Bash 工具一律不管
    out = subprocess.run(
        [sys.executable, str(HOOK)],
        input=json.dumps({"tool_name": "Edit", "tool_input": {"command": "git stash"}}),
        capture_output=True, text=True, check=True).stdout.strip()
    if out:
        failures += 1
        print("FAIL 非 Bash 工具被拦了")
    print("%d cases, %d failures" % (len(CASES) + 1 + failures_extra, failures))
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
