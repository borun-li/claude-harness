#!/usr/bin/env python3
"""PreToolUse(Bash) —— 拦下会「按 git 的记忆重写工作区」的命令。

**为什么是钩子而不是一句提示。** 代理知道这条规则，也仍会为了「撤掉自己刚才的改动」
顺手用 `git checkout --`、`git apply -R`、`git stash`，连带抹掉别人未提交的活。

harness 的原则（~/.claude/ORCHESTRATOR.md，Boundaries）：
「一条由结构承载的约束，强过一条由句子承载的约束」。
这个文件就是把那句话用在这条禁令上。

**被拦下的命令有一个共同点，而不是「危险」这么笼统**：
它们的作用域是 **git 认为的整棵树或整块索引**，而调用者心里想的是**自己刚碰过的
那几行**。两者之差就是别人未提交的活。放行的替代命令全部满足
「作用域 = 你在命令行里亲手打出的那个路径」。
"""
import json
import os
import re
import subprocess
import sys

# 每条 = (正则, 你本来想做的事, 该用什么)
RULES: list[tuple[str, str, str]] = [
    (r"\bgit\s+(?:-[^\s]+\s+)*checkout\b(?!(?:\s+(?:-q|--quiet))*\s+-b\b)",
     "把某个路径恢复成 git 里的样子",
     "git show HEAD:<路径> > <路径>   # 作用域就是你打出的那一个路径"),
    (r"\bgit\s+(?:-[^\s]+\s+)*restore\b",
     "同上",
     "git show HEAD:<路径> > <路径>"),
    (r"\bgit\s+(?:-[^\s]+\s+)*switch\b",
     "换分支",
     "别换。你的活在当前分支上；要干净基线用 git worktree add <临时目录>"),
    # ``stash list`` / ``stash show`` 只读 —— 排除掉，理由见文件末尾的注记
    (r"\bgit\s+(?:-[^\s]+\s+)*stash\b(?!\s+(?:list|show)\b)",
     "临时挪开工作区去量一个干净基线",
     "git worktree add /tmp/base HEAD  或  git archive HEAD | tar -x -C /tmp/base\n"
     "     —— 基线在别处展开，你的工作区一个字节都不动"),
    (r"\bgit\s+(?:-[^\s]+\s+)*reset\b",
     "撤掉刚才的改动",
     "改之前先 cp 一份；撤就 cp 回来，再用 cmp 证明逐字节相同"),
    (r"\bgit\s+(?:-[^\s]+\s+)*clean\b",
     "删掉多余的未跟踪文件",
     "把你自己造的文件按名字 rm 掉。git clean 删的是「git 不认得的」，\n"
     "     那里面有别人还没 add 的新文件"),
    (r"\bgit\s+(?:-[^\s]+\s+)*apply\b[^|;&]*(?:\s-R\b|\s--reverse\b)",
     "逆向打回自己刚才的补丁",
     "逆向 sed / cp 回来 + cmp 证明；diff 是对 HEAD 算的，它会连别人的活一起撤"),
    (r"\bgit\s+(?:-[^\s]+\s+)*revert\b",
     "撤一个提交",
     "这是历史改写，交给人。先把你的发现报上去"),
    (r"\bgit\s+(?:-[^\s]+\s+)*rm\b",
     "删一个被跟踪的文件",
     "普通 rm；要不要从索引里去掉，交给人在提交时决定"),
    (r"\bgit\s+(?:-[^\s]+\s+)*branch\s+(?:-[^\s]*\s+)*-[dD]\b",
     "删分支",
     "交给人"),
    # ``worktree remove`` **不带 --force** 时对脏工作树会自己拒绝，且作用域就是
    # 你打出的那个路径 —— 满足本文件的判据，因此放行。只拦 --force。
    (r"\bgit\s+(?:-[^\s]+\s+)*worktree\s+remove\b[^|;&]*(?:\s--force\b|\s-f\b)",
     "强删一个还有改动的 worktree",
     "先把那个 worktree 里的改动处理掉，再用不带 --force 的 git worktree remove"),
]


_HEREDOC = re.compile(r"<<-?\s*[\"\']?(\w+)[\"\']?")


def strip_data(command: str) -> str:
    """把**数据**从命令里剔掉，只留下真正会被执行的部分。

    两类假阳性：``grep -rn 'git checkout' docs/`` 找这条禁令
    自己的出处，以及 ``cat > PLAYBOOK.md <<'EOF' … git stash … EOF`` 把禁令写进
    文档。**两者都没有跑任何 git。** 一个会对写文档的人开火的守卫，
    第二天就会被关掉，所以它必须分得清命令和字符串。
    """
    # 1) heredoc 体：从 <<MARKER 那一行的行尾，到单独成行的 MARKER
    lines, out, marker = command.split("\n"), [], None
    for line in lines:
        if marker is not None:
            if line.strip() == marker:
                marker = None
            continue
        m = _HEREDOC.search(line)
        out.append(line[: m.start()] if m else line)
        if m:
            marker = m.group(1)
    text = "\n".join(out)
    # 2) 引号内的整段
    text = re.sub(r"'[^']*'", " ", text)
    text = re.sub(r'"[^"]*"', " ", text)
    return text


# —— 唯一的换分支例外：工作区完全干净时切回 main ——
# 流程是「开分支 → 提交 → 推送 → PR → 合并」，合并后要回到 main。
# 干净的工作区里没有任何别人未提交的活，换分支丢不了东西，满足本文件的判据。
# 只认字面的 main（可带 -q/--quiet、git -C <dir>），且必须在钩子运行时查得到「干净」：
# `git status --porcelain` 为空（未跟踪文件也算脏）。目录查不清就不放行。
_TO_MAIN = re.compile(
    r"\bgit\s+(?:-C\s+(\S+)\s+)?(?:checkout|switch)(?:\s+(?:-q|--quiet))*\s+main(?=\s*(?:$|&&|;|\|\||\n))")
_CD = re.compile(r"(?:^|[;&|\n]\s*)cd\s+(\S+)")


def _target_dir(command: str, m: re.Match, cwd: str) -> str | None:
    if m.group(1):
        d = m.group(1)
    else:
        cds = [c for c in _CD.finditer(command) if c.end() <= m.start()]
        d = cds[-1].group(1) if cds else cwd
    if d in ("&&", ";", "||", "|"):
        return None  # 原路径在引号里被剔掉了，查不清
    d = os.path.expanduser(d)
    if not os.path.isabs(d):
        d = os.path.join(cwd, d)
    return d if os.path.isdir(d) else None


def _is_clean(d: str) -> bool:
    try:
        r = subprocess.run(["git", "-C", d, "status", "--porcelain"],
                           capture_output=True, text=True, timeout=10)
    except Exception:
        return False
    return r.returncode == 0 and r.stdout.strip() == ""


def exempt_back_to_main(command: str, cwd: str) -> tuple[str, str | None]:
    """把「干净工作区切回 main」从命令里抹掉；工作区脏时返回拒绝理由。"""
    for m in reversed(list(_TO_MAIN.finditer(command))):
        d = _target_dir(command, m, cwd)
        if d is None:
            continue  # 查不清就交给普通规则拦
        if not _is_clean(d):
            return command, (f"{d} 的工作区不干净（git status --porcelain 非空）。"
                             "只有完全干净时才放行切回 main：先提交或处理掉这些改动。")
        command = command[: m.start()] + " " * (m.end() - m.start()) + command[m.end():]
    return command, None


BANNER = (
    "这条命令的作用域是 git 认为的整棵树，不是你打出来的那个路径。\n"
    "两者之差 = 别人尚未提交的活（~/.claude/ORCHESTRATOR.md，Boundaries）。"
)


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0  # 读不懂就不拦 —— 钩子不该成为新的故障源
    if payload.get("tool_name") != "Bash":
        return 0
    command = strip_data(str(payload.get("tool_input", {}).get("command", "")))
    command, dirty = exempt_back_to_main(command, str(payload.get("cwd") or os.getcwd()))
    if dirty:
        print(json.dumps({"hookSpecificOutput": {
            "hookEventName": "PreToolUse", "permissionDecision": "deny",
            "permissionDecisionReason": dirty}}))
        return 0
    for pattern, intent, instead in RULES:
        if re.search(pattern, command):
            reason = (
                f"{BANNER}\n\n"
                f"你大概是想：{intent}\n"
                f"改用：{instead}\n\n"
                "只读的 git 一律放行：status / diff / log / show / ls-files / archive / worktree add。\n"
                "如果你确实需要被拦的那一条，**说出来让人来跑**（在提示里打 `! <命令>`），"
                "不要绕过。"
            )
            print(json.dumps({
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "deny",
                    "permissionDecisionReason": reason,
                }
            }))
            return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())


# ---------------------------------------------------------------------------
# 注记 · 只读子命令必须放行
#
# 只读的 stash 子命令什么都不碰，拦它就是假阳性。**守卫的假阳性率决定它能活
# 多久。** 一个连「列出 stash」都拦的守卫，第二天就会有人把它整个注释掉，
# 然后连真正危险的那几条也一起放行了。
#
# 判据没有变，仍然是那一条：**调用者能不能把它要碰的东西全部说出名字。**
# 只读子命令什么都不碰，所以它们从一开始就不该在这张表上。
# ---------------------------------------------------------------------------
