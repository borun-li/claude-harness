---
description: Resume the unfinished agent-team run in this project from its state.json, optionally from a given phase.
argument-hint: '[phase to resume from, e.g. 4] [optional note]'
model: opus
disable-model-invocation: true
hooks:
  PreToolUse:
    - matcher: Bash
      hooks:
        - type: command
          command: python3 "$HOME/.claude/hooks/no-tree-restoring-git.py" --role orchestrator
        - type: command
          command: python3 "$HOME/.claude/hooks/no-foreign-process-kill.py"
    - matcher: SendMessage
      hooks:
        - type: command
          command: python3 "$HOME/.claude/hooks/no-agent-continuation.py"
    - matcher: Agent
      hooks:
        - type: command
          command: python3 "$HOME/.claude/hooks/run-log.py" dispatch
---

> **Read `~/.claude/CONSTITUTION.md` first. It overrides this file; on conflict, follow it and report the conflict.**

You are the **Orchestrator** resuming a run. Read `~/.claude/ORCHESTRATOR.md`; then, by the run's
`state.json`: `tier: "standard"` → `~/.claude/route/STANDARD.md`; otherwise the PLAYBOOK and
QUALITY-BARS of each team in its `scope` (`~/.claude/backend/`, `~/.claude/frontend/`).

## Recover state

Runs live in `docs/runs/<slug>/` (the project may move the root: `artifacts.run_dir`).
`gate.py status --project .` finds the open run; several open → ask the user which, and set a
dropped one's `status` to `abandoned`. No open run → say so and suggest `/route`; never start a new
run silently.

1. Read `<run-dir>/state.json`, then the `orchestrator` section of `<run-dir>/handoff.md`
   (`~/.claude/route/HANDOFF.md` §5) and any section dated after it: that is where the run stopped.
   Then read the artifacts the next step depends on; skim the others (headings, ids, status).
2. `gate.py status` shows the step, each gate's last verdict, rounds used, open dispatches,
   returns not yet landed and what the last writers changed. **A return that is not landed, or is
   newer than the latest gate run, is unverified work: `gate.py land`, then that phase's gate,
   before anything else.**
3. A `dispatch` with no `return` is an agent that never reported back: treat its work as
   unverified. Agents of the earlier session cannot be continued; their work goes on from the
   handoff. `gate.py worktrees` lists what they left: land what is finished, then
   `gate.py worktrees --clean`.
4. If `state.json` and disk disagree, trust the disk, say so, and correct the state.

## Confirm before continuing

Show the user the goal, tier and scope, phases done, their decisions at each stop, gate results,
rounds used, open questions (with an interface: open DFBs and Figma calls against the budget) and
the phase you will resume at. The models and document language in `state.json` stand: show them,
and ask only for one that is missing.

## Arguments

$ARGUMENTS

A leading number means: resume from that phase. Say which artifacts will be regenerated and get
confirmation before overwriting an approved one.

## Then

Continue the flow from that point.
