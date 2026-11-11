#!/usr/bin/env python3
"""PreToolUse(Bash) —— harness 会话里的 git / gh 守卫。``--role orchestrator|agent``。

**为什么是钩子而不是一句提示。** 代理知道规则，也仍会为了「撤掉自己刚才的改动」
顺手用 `git checkout --`、`git stash`，连带抹掉别人未提交的活；或者为了交差顺手
`git push --force`。一条由结构承载的约束，强过一条由句子承载的约束。

**判据只有两条。**
1. 作用域 = 你亲手打出的东西。按 git 的记忆重写整棵树或整块索引的命令
   （checkout/restore 路径、reset、clean、stash、apply -R、rm……）谁都不许：
   它碰到的比你说出名字的多，多出来的就是别人未提交的活。
2. 强制和改写历史的操作谁都不许（push --force、branch -D、rebase、commit --amend、
   gh pr merge……）：它们会破坏代码库，留给人。

**角色。** git 写操作只归协调者（主会话，由 run 命令的 frontmatter 以
``--role orchestrator`` 调用）：开分支、换到已有分支（工作区干净时）、按路径提交、
推本轮分支、开草稿 PR。子代理（agent frontmatter，``--role agent``）只读。
推送和 PR 是对外动作，还要项目 ``.claude/gates.json`` 里有用户设的 ``"git": {"push": true}``。

**这是防失误，不是防恶意。** 它靠解析命令行；刻意绕过（变量拼命令、脚本里调 git）
拦不住。main 的最终保护是服务器端规则。没有 ``--role`` 时按 agent 处理（最严）。
"""
import json
import os
import re
import subprocess
import sys

ROLE = "orchestrator" if sys.argv[1:3] == ["--role", "orchestrator"] else "agent"

# ---------------------------------------------------------------------------
# 把数据从命令里剔掉
# ---------------------------------------------------------------------------
QUOTED = "__quoted__"
_HEREDOC = re.compile(r"<<-?\s*[\"\']?(\w+)[\"\']?")
_SHELL_C = re.compile(r"\b(?:bash|sh|zsh)\s+(?:-\w+\s+)*-c\s+(['\"])(.*?)\1|\beval\s+(['\"])(.*?)\3", re.S)


def strip_data(command: str) -> str:
    """剔掉 heredoc 体和引号内的整段，只留真正会被执行的部分。

    ``grep -rn 'git checkout' docs/`` 与 ``cat > PLAYBOOK.md <<'EOF' … git stash … EOF``
    都没有跑任何 git。一个会对写文档的人开火的守卫，第二天就会被关掉。
    """
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
    # 引号段换成占位词而不是空白：``git -C "<dir>" reset`` 剔空后若把 reset 当成目录，
    # 真正的子命令就漏掉了。占位词让参数位置不变、目录「查不清」。
    text = re.sub(r"'[^']*'", f" {QUOTED} ", text)
    text = re.sub(r'"[^"]*"', f" {QUOTED} ", text)
    # 重定向不是参数：``git push … 2>&1``、``> out.txt``
    text = re.sub(r"\d*>&\d*|&>>?\s*\S+|\d*>>?\s*\S+|\d*<\s*\S+", " ", text)
    return text


def shell_payloads(command: str, depth: int = 0) -> list[str]:
    """``bash -c "…"`` / ``eval '…'`` 引号里的是命令，不是数据：单独再查一遍。"""
    found = []
    for m in _SHELL_C.finditer(command):
        inner = m.group(2) if m.group(2) is not None else m.group(4)
        found.append(inner)
        if depth < 2:
            found += shell_payloads(inner, depth + 1)
    return found


# ---------------------------------------------------------------------------
# 查仓库状态（查不清就按「不放行」处理）
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


def is_local_branch(d: str, name: str) -> bool:
    return _git(d, "rev-parse", "--verify", "--quiet", f"refs/heads/{name}")[0] == 0


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
# 拆命令
# ---------------------------------------------------------------------------
_SPLIT = re.compile(r"&&|\|\||[;|&\n()`]|\$\(")
_GIT_GLOBAL_WITH_ARG = {"-C", "-c", "--git-dir", "--work-tree", "--namespace", "--exec-path"}


def segments(text: str, cwd: str):
    """逐段给出 (tokens, 这一段的目录)。``cd x`` 改变后面各段的目录；目录查不清为 None。"""
    d: str | None = cwd
    for seg in _SPLIT.split(text):
        toks = seg.split()
        if not toks:
            continue
        if toks[0] == "cd":
            if len(toks) < 2:
                d = os.path.expanduser("~")
            else:
                nd = os.path.expanduser(toks[1])
                base = d or cwd
                nd = nd if os.path.isabs(nd) else os.path.join(base, nd)
                d = nd if toks[1] != QUOTED and os.path.isdir(nd) else None
            continue
        yield toks, d


def find_tool(toks: list[str], name: str) -> int | None:
    for i, t in enumerate(toks):
        if t == name or t.endswith("/" + name):
            return i
    return None


def parse_git(toks: list[str], i: int, d: str | None):
    """git 之后：全局选项 → 子命令 → 参数。``-C <dir>`` 改变目录（被引号剔空则查不清）。"""
    j = i + 1
    while j < len(toks) and toks[j].startswith("-"):
        opt = toks[j]
        if opt in _GIT_GLOBAL_WITH_ARG:
            if j + 1 >= len(toks):
                return None, [], None
            if opt == "-C":
                nd = os.path.expanduser(toks[j + 1])
                nd = nd if os.path.isabs(nd) else os.path.join(d or os.getcwd(), nd)
                d = nd if toks[j + 1] != QUOTED and os.path.isdir(nd) else None
            j += 2
        else:
            j += 1
    if j >= len(toks):
        return None, [], d
    return toks[j], toks[j + 1:], d


def flags_and_args(args: list[str]) -> tuple[list[str], list[str]]:
    return [a for a in args if a.startswith("-")], [a for a in args if not a.startswith("-")]


def has_short(flags: list[str], letter: str) -> bool:
    """单字母短选项，含合写（``-am``、``-df``）。"""
    return any(re.fullmatch(r"-[A-Za-z]+", f) and letter in f[1:] for f in flags)


# ---------------------------------------------------------------------------
# 规则
# ---------------------------------------------------------------------------
ORCH_ONLY = "git 写操作只归协调者。在返回里写明要提交、建分支或推送什么，由协调者来做。"
RESTORE = ("这条命令的作用域是 git 认为的整棵树或整块索引，不是你打出来的路径；"
           "两者之差 = 别人尚未提交的活。")
FORCE = "强制或改写历史的操作会破坏代码库，留给人。"
NO_SWITCH = ("推送和 PR 是对外动作，要用户在项目 .claude/gates.json 里设 "
             "\"git\": {\"push\": true}。没有就停下来问用户。")

READ_ONLY = {"status", "diff", "log", "show", "ls-files", "ls-tree", "rev-parse", "blame", "grep",
             "archive", "cat-file", "describe", "shortlog", "merge-base", "rev-list", "show-ref",
             "for-each-ref", "name-rev", "check-ignore", "check-attr", "count-objects", "version",
             "help", "var", "whatchanged", "range-diff", "cherry", "show-branch", "difftool",
             "init", "clone"}  # init/clone 只造新东西


def restore_rules(sub: str, args: list[str]) -> str | None:
    """判据 1 与 2 里两种角色都不许的。"""
    flags, pos = flags_and_args(args)
    if sub in ("restore", "reset", "clean", "rm", "revert", "rebase", "filter-branch",
               "filter-repo", "update-ref", "update-index", "replace"):
        alt = {"restore": "git show HEAD:<路径> > <路径>",
               "reset": "改之前先 cp 一份；撤就 cp 回来，再用 cmp 证明逐字节相同",
               "clean": "把你自己造的文件按名字 rm 掉",
               "rm": "普通 rm；要不要从索引里去掉，提交时按路径 add 决定"}.get(sub)
        return (RESTORE + (f"\n改用：{alt}" if alt else "")) if sub in ("restore", "reset", "clean", "rm") \
            else FORCE
    if sub == "stash" and not (pos[:1] in (["list"], ["show"])):
        return RESTORE + "\n改用：git worktree add <临时目录> HEAD —— 基线在别处展开，你的工作区不动"
    if sub == "apply" and ("-R" in flags or "--reverse" in flags):
        return RESTORE + "\n改用：cp 回来 + cmp 证明；diff 是对 HEAD 算的，会连别人的活一起撤"
    if sub == "worktree" and pos[:1] == ["remove"] and ("--force" in flags or has_short(flags, "f")):
        return "先处理掉那个 worktree 里的改动，再用不带 --force 的 git worktree remove"
    if sub == "pull" and ("--rebase" in flags or has_short(flags, "r") or "--force" in flags):
        return FORCE
    if sub == "reflog" and pos[:1] in (["expire"], ["delete"]):
        return FORCE
    return None


def switch_rules(sub: str, args: list[str], d: str | None) -> str | None:
    """协调者的 switch / checkout：新建分支随时可以；换到已有分支要工作区干净；其余一律不许。"""
    flags, pos = flags_and_args(args)
    quiet = {"-q", "--quiet"}
    create = {"switch": {"-c", "--create"}, "checkout": {"-b"}}[sub]
    other = [f for f in flags if f not in quiet and f not in create]
    if "--" not in args and not other and len(pos) == 1:
        if any(f in create for f in flags):
            return None  # 在 HEAD 上新建分支：不动工作区
        name = pos[0]
        if d is None:
            return "目录查不清，不放行换分支。"
        if not is_local_branch(d, name):
            return (RESTORE + f"\n{name} 不是本地分支；恢复路径改用 git show HEAD:<路径> > <路径>")
        if not is_clean(d):
            return (f"{d} 的工作区不干净（git status --porcelain 非空）。只有完全干净时才放行换分支："
                    "先按路径提交，或等写入代理返回。")
        return None
    if any(f in ("-C", "-B", "-f", "--force", "--discard-changes", "--orphan", "--detach", "--merge", "-m")
           for f in flags):
        return FORCE
    return (RESTORE + "\n新建分支只认 `git switch -c <名>` / `git checkout -b <名>`（不带起点）；"
            "换分支只认 `git switch <已有分支>`。")


def branch_rules(args: list[str]) -> str | None:
    flags, pos = flags_and_args(args)
    listing = {"--list", "-l", "-a", "--all", "-r", "--remotes", "-v", "-vv", "--verbose",
               "--show-current", "--contains", "--merged", "--no-merged", "--sort", "--format",
               "--points-at", "--color", "--no-color", "--column", "--no-column"}
    if all(f.split("=")[0] in listing for f in flags) and (not pos or any(
            f.split("=")[0] in ("--list", "-l", "--contains", "--merged", "--no-merged", "--points-at",
                                "--sort", "--format") for f in flags)):
        return None  # 列表
    if ROLE != "orchestrator":
        return ORCH_ONLY
    if "-D" in flags or "--force" in flags or has_short(flags, "f") or has_short(flags, "D") \
            or "-M" in flags or "-C" in flags:
        return FORCE + "\n删未合并的分支交给人；git branch -d 会自己拒绝未合并的分支，可以用。"
    if flags in ([], ["-q"]) and len(pos) == 1:
        return None  # 在 HEAD 上建分支
    if all(f in ("-d", "--delete") for f in flags) and flags and pos:
        return None  # git 自己拒绝删未合并的分支
    return "只认 `git branch <名>`（在 HEAD 上建）和 `git branch -d <名>`。"


def add_rules(args: list[str]) -> str | None:
    flags, pos = flags_and_args(args)
    if any(f in ("-A", "--all", "-u", "--update", "-f", "--force", "--no-ignore-removal") for f in flags) \
            or has_short(flags, "A") or has_short(flags, "u") or has_short(flags, "f"):
        return "按路径暂存：git add <你改的文件>。-A / -u / -f 会把别人未提交的活一起卷进去。"
    if any(p in (".", "./", ":/", ":", "*", "-") for p in pos) or not pos:
        return "按路径暂存：git add <你改的文件>。`.` 是整棵树，会把别人未提交的活一起卷进去。"
    return None


def commit_rules(args: list[str]) -> str | None:
    flags, _ = flags_and_args(args)
    if "--amend" in flags:
        return FORCE + "\n改上一个提交 = 改写历史；新开一个提交。"
    if "--no-verify" in flags or has_short(flags, "n"):
        return "跳过项目的提交钩子 = 放松检查（Constitution §4.5）。"
    if "--all" in flags or has_short(flags, "a"):
        return "commit -a 会把别人未提交的改动一起提交；先 git add <路径> 再提交。"
    return None


def push_rules(args: list[str], d: str | None) -> str | None:
    flags, pos = flags_and_args(args)
    ok_flags = {"-u", "--set-upstream", "-q", "--quiet", "-v", "--verbose"}
    if any(f not in ok_flags for f in flags) or len(pos) > 2:
        return FORCE + "\n只认 `git push [-u] [origin] [<本轮分支>]`：不带 --force / --delete / --tags / --all。"
    if d is None:
        return "目录查不清，不放行推送。"
    if not push_allowed(d):
        return NO_SWITCH
    ref = pos[1] if len(pos) == 2 else "HEAD"
    if "+" in ref or ":" in ref:
        return FORCE + "\n只推本轮分支本身，不带 + 或 :。"
    branch = current_branch(d) if ref == "HEAD" else ref
    if branch is None:
        return "当前不在分支上（detached HEAD），不放行推送。"
    if branch in default_branches(d):
        return f"不推 {branch}。改动走「分支 → PR → 用户合并」。"
    return None


def git_decision(sub: str | None, args: list[str], d: str | None) -> str | None:
    if sub is None or sub in READ_ONLY:
        return None
    reason = restore_rules(sub, args)
    if reason:
        return reason
    flags, pos = flags_and_args(args)
    if sub == "stash" or (sub == "worktree" and pos[:1] in (["add"], ["list"], ["remove"], ["prune"])) \
            or (sub == "apply"):
        return None  # 只读的 stash；worktree 在别处展开基线；正向 apply 打的是你点名的补丁
    if sub == "branch":
        return branch_rules(args)
    if sub in ("tag", "remote", "config", "symbolic-ref", "reflog", "notes", "submodule"):
        # 列表 / 读取形式两种角色都放行，其余是写
        reading = (not pos and all(f in ("-l", "--list", "-v", "--get", "--get-all", "--show-origin",
                                         "--get-regexp", "--local", "-n") for f in flags)) or \
                  (sub == "remote" and pos[:1] in (["get-url"], ["show"])) or \
                  (sub == "config" and any(f in ("--get", "--get-all", "--list", "-l", "--get-regexp")
                                           for f in flags)) or \
                  (sub == "symbolic-ref" and len(pos) == 1) or \
                  (sub == "reflog" and pos[:1] in ([], ["show"])) or \
                  (sub == "notes" and pos[:1] in ([], ["list"], ["show"])) or \
                  (sub == "submodule" and pos[:1] in ([], ["status"]))
        return None if reading else (ORCH_ONLY if ROLE != "orchestrator" else
                                     (FORCE if sub in ("tag", "notes") and has_short(flags, "f") else None))
    if ROLE != "orchestrator":
        return ORCH_ONLY
    if sub in ("switch", "checkout"):
        return switch_rules(sub, args, d)
    if sub == "add":
        return add_rules(args)
    if sub == "commit":
        return commit_rules(args)
    if sub == "push":
        return push_rules(args, d)
    return None  # fetch / pull --ff-only / merge 等：协调者可以


# —— gh：只放行列出的子命令，其余交给人 ——
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
        return None if method == "GET" else "gh api 只放行读取（GET）；写操作交给人。"
    if (group, sub) in GH_READ or (group, "*") in GH_READ:
        return None
    if (group, sub) in GH_ORCH:
        if ROLE != "orchestrator":
            return ORCH_ONLY
        if d is None:
            return "目录查不清，不放行。"
        if not push_allowed(d):
            return NO_SWITCH
        if sub == "create" and not ({"--draft", "-d"} & set(args)):
            return "PR 先开草稿：gh pr create --draft …，验收时再 gh pr ready。"
        return None
    if (group, sub) == ("pr", "merge"):
        return "合并留给用户，在 GitHub 上审过再合。"
    return f"gh {group} {sub if sub != '*' else ''} 不在放行表里；需要的话说出来让人跑。".replace("  ", " ")


FOOTER = ("\n\n只读的 git 一律放行：status / diff / log / show / ls-files / archive / worktree add。\n"
          "如果你确实需要被拦的那一条，**说出来让人来跑**（在提示里打 `! <命令>`），不要绕过。")


def decide(command: str, cwd: str) -> str | None:
    for cmd in [command, *shell_payloads(command)]:
        for toks, d in segments(strip_data(cmd), cwd):
            i = find_tool(toks, "git")
            if i is not None:
                sub, args, gd = parse_git(toks, i, d)
                reason = git_decision(sub, args, gd)
                if reason:
                    return reason
            i = find_tool(toks, "gh")
            if i is not None:
                reason = gh_decision(toks[i + 1:], d)
                if reason:
                    return reason
    return None


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0  # 读不懂就不拦 —— 钩子不该成为新的故障源
    if payload.get("tool_name") != "Bash":
        return 0
    command = str(payload.get("tool_input", {}).get("command", ""))
    reason = decide(command, str(payload.get("cwd") or os.getcwd()))
    if reason:
        print(json.dumps({"hookSpecificOutput": {
            "hookEventName": "PreToolUse", "permissionDecision": "deny",
            "permissionDecisionReason": f"[{ROLE}] {reason}{FOOTER}"}}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
