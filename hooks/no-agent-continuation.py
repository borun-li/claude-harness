#!/usr/bin/env python3
"""PreToolUse(SendMessage) —— 不许把一个已返回的 be-* / fe-* 代理续用到下一轮。

**为什么是钩子而不是一句提示。** Ithaca Local Guide MVP 一次运行里，同一个
be-tester 在多轮修改之间被一直续用：702 轮、3.21 亿 token。PLAYBOOK 当时没有
禁止续用，而「每轮新开」写成句子之后仍然要靠调度者记得。Constitution §8.1 是规则，
这个文件是承载它的结构。

**判据。** SendMessage 的 ``to`` 是代理名或 agentId，本身看不出角色。Claude Code
为每个子代理写一份 ``<会话记录目录>/subagents/agent-<id>.meta.json``，其中有
``agentType`` 与 ``finished``。钩子据此判断：

- 目标不是 be-* / fe-*（或查不到） → 放行。钩子只管本 harness 的团队。
- 目标仍在运行（``finished`` 不为 true） → 放行。同一轮内给活着的代理补一句话不是续用。
- 目标已返回，且从未被续用过 → 放行一次并记账。这是 §8.1 唯一的例外：
  代理因一个问题而 blocked，同一轮内把答案带给它。
- 目标已返回，且已经续用过一次 → 拒绝：新开一个代理，按 HANDOFF.md 写简短说明。

读不懂输入、找不到文件，一律放行 —— 钩子不该成为新的故障源。
"""
import json
import pathlib
import re
import sys

HARNESS_TYPE = re.compile(r"^(be|fe)-")

REASON = (
    "Constitution §8.1：这个 {kind} 已经返回，并且已经续用过一次。不要再续用它。\n"
    "新开一个 {kind}（Agent 工具，subagent_type={kind}），按 ~/.claude/route/HANDOFF.md §3 "
    "写一份 10–15 行的说明：第几个 {kind}、第几轮、任务、条目、证据路径、要读的交接条目、"
    "已知陷阱。上一轮学到的东西在交接日志里，不在它的上下文里。"
)


def find_meta(subagents: pathlib.Path, to: str):
    """``to`` 可以是 agentId，也可以是代理名；两种都试。"""
    direct = subagents / f"agent-{to}.meta.json"
    if direct.is_file():
        return direct
    for meta in subagents.glob("agent-*.meta.json"):
        try:
            if json.loads(meta.read_text()).get("name") == to:
                return meta
        except Exception:
            continue
    return None


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0
    if payload.get("tool_name") != "SendMessage":
        return 0
    to = str(payload.get("tool_input", {}).get("to", "")).strip()
    to = re.sub(r"\s*\[[^\]]*\]$", "", to)  # 去掉 " [ref]" 后缀
    transcript = payload.get("transcript_path")
    if not to or to == "main" or not transcript:
        return 0
    subagents = pathlib.Path(transcript).with_suffix("") / "subagents"
    meta_path = find_meta(subagents, to)
    if meta_path is None:
        return 0
    try:
        meta = json.loads(meta_path.read_text())
    except Exception:
        return 0
    kind = str(meta.get("agentType", ""))
    if not HARNESS_TYPE.match(kind) or meta.get("finished") is not True:
        return 0
    ledger = meta_path.with_name(meta_path.name.replace(".meta.json", ".continuations"))
    try:
        used = int(ledger.read_text().strip() or 0) if ledger.exists() else 0
    except Exception:
        used = 0
    if used >= 1:
        print(json.dumps({
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": REASON.format(kind=kind),
            }
        }))
        return 0
    try:
        ledger.write_text(str(used + 1))
    except Exception:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
