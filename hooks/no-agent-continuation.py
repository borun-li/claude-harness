#!/usr/bin/env python3
"""PreToolUse(SendMessage) —— 已返回的 be-* / fe-* 代理，只按 Constitution §8.1 续用。

**为什么是钩子而不是一句提示。** 续用多轮的代理上下文越积越大；新开的代理又要从头
重读代码。§8.1 在两者之间划了线，这个文件是承载它的结构。

**判据。** SendMessage 的 ``to`` 是代理名或 agentId，本身看不出角色。Claude Code
为每个子代理写一份 ``<会话记录目录>/subagents/agent-<id>.meta.json``（``agentType``、
``finished``），旁边是它的记录 ``agent-<id>.jsonl``。钩子据此判断：

- 目标不是 be-* / fe-*（或查不到） → 放行。钩子只管本 harness 的团队。
- 目标仍在运行（``finished`` 不为 true） → 放行。同一轮内给活着的代理补一句话不是续用。
- 目标是**作者**（写被返工的那份东西的角色，``AUTHORS``） → 续用次数到 ``loops.max_rounds``
  为止放行，且它最后一次请求的上下文不超过 ``loops.continue_max_context``；否则拒绝。
  它已经读过的东西不必重读，这正是续用的意义。
- 目标是**评判者**（审查员、``fe-tester``） → 只放行一次：因一个问题而 blocked，
  同一轮内把答案带给它。评判永远由没见过这份工作的新代理做。

读不懂输入、找不到文件，一律放行 —— 钩子不该成为新的故障源。
"""
import json
import pathlib
import re
import sys

HARNESS_TYPE = re.compile(r"^(be|fe)-")
AUTHORS = {"be-analyst", "be-architect", "be-developer", "be-tester", "fe-ux", "fe-ui", "fe-engineer"}
HERE = pathlib.Path(__file__).resolve().parent

REASON = (
    "Constitution §8.1：这个 {kind} 已经返回，{why}。不要再续用它。\n"
    "新开一个 {kind}（Agent 工具，subagent_type={kind}），按 ~/.claude/route/HANDOFF.md §3 "
    "写简报：第几个 {kind}、第几轮、任务、条目、证据路径、阅读清单（代码地图和要读的 file:line）、"
    "已知陷阱。上一轮学到的东西在交接和代码地图里，不在它的上下文里。"
)


def loops(kind, cwd):
    """团队配置的 loops，项目的 .claude/<team>.json 可整体覆盖（与 gate.loop_cap 同序）。"""
    team = "backend" if kind.startswith("be-") else "frontend"
    out = {"max_rounds": 2, "continue_max_context": 200000}
    for f in (HERE.parent / team / "config.json", pathlib.Path(cwd or ".") / ".claude" / f"{team}.json"):
        try:
            out.update(json.loads(f.read_text()).get("loops") or {})
        except Exception:
            continue
    return out


def last_context(transcript):
    """代理最后一次请求送进模型的 token 数（输入 + 缓存写 + 缓存读）。"""
    size = 0
    try:
        for line in transcript.read_text().splitlines():
            u = (json.loads(line).get("message") or {}).get("usage") if '"usage"' in line else None
            if u:
                size = sum(u.get(k, 0) for k in
                           ("input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens"))
    except Exception:
        return 0
    return size


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
    why = None
    if kind in AUTHORS:
        cfg = loops(kind, payload.get("cwd"))
        size = last_context(meta_path.with_name(meta_path.name.replace(".meta.json", ".jsonl")))
        if used >= max(1, int(cfg["max_rounds"])):
            why = f"已经续用了 {used} 次（loops.max_rounds = {cfg['max_rounds']}）"
        elif size > int(cfg["continue_max_context"]):
            why = f"上下文已有 {size} token（loops.continue_max_context = {cfg['continue_max_context']}）"
    elif used >= 1:
        why = "已经续用过一次；评判者每一轮都要新开"
    if why:
        print(json.dumps({
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": REASON.format(kind=kind, why=why),
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
