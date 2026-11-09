---
description: Resume an in-flight frontend run from docs/frontend/state.json, optionally from a specific phase.
argument-hint: '[phase number to resume from] [optional note]'
model: opus
disable-model-invocation: true
hooks:
  PreToolUse:
    - matcher: Bash
      hooks:
        - type: command
          command: python3 "$HOME/.claude/hooks/no-tree-restoring-git.py"
        - type: command
          command: python3 "$HOME/.claude/hooks/no-foreign-process-kill.py"
    - matcher: SendMessage
      hooks:
        - type: command
          command: python3 "$HOME/.claude/hooks/no-agent-continuation.py"
---

> **Read `~/.claude/CONSTITUTION.md` first. It overrides this file; on conflict, follow it and report the conflict.**

You are the **Orchestrator** resuming a frontend run. Read `~/.claude/ORCHESTRATOR.md`, `~/.claude/frontend/PLAYBOOK.md`,
`config.json` (merged with `./.claude/frontend.json`) and `QUALITY-BARS.md`.

## Recover state

The run dir is `docs/frontend/`, or a second round's `docs/frontend/<slug>/`: find them with
`grep -rl --include=state.json '' docs/frontend`, resume the one whose `status` is
not `accepted` or `prototype_confirmed`, and ask the user which if there are several. Every gate
and log command then takes `--run-dir <run dir>` when it is not `docs/frontend`. A `state.json`
with `harness_version` below 7.0 is not resumed
(PLAYBOOK §1.3): report it and offer a new round that reads its artifacts as input.

1. Read `<run-dir>/state.json`. If missing, say there is no run and suggest `/frontend`.
2. Read the last `orchestrator` entry in `<run-dir>/handoff.md` (`~/.claude/route/HANDOFF.md` §5)
   and the entries after it; a cross-stack run keeps one log, in the Backend run dir: use
   `/backend-resume`. Then read the artifacts the next step depends on; skim the
   others (headings, ids, status) (Constitution §8).
3. Read `<run-dir>/gates/`: latest report per gate, `attempts.json`, `waivers.json`, `observables-approved.json`
   and the `snap-*.json` marks. **A mark newer than the latest gate report is unverified work: run
   that phase's gate first.**
4. Run `gate.py timeline --team frontend`. A `dispatch` with no `return` is unverified work.
5. If `state.json` and disk disagree, trust the disk, say so, and correct the state.

## Confirm before continuing

Show the tier, phases done, human stop decisions, gate results, loop counters, open DFBs, Figma
calls used against the budget, open questions and the phase you will resume at. Re-confirm the
model plan with `AskUserQuestion`.

## Arguments

$ARGUMENTS

A leading number means: resume from that phase. Say which artifacts will be regenerated and get
confirmation before overwriting an approved one.

## Then

Continue the PLAYBOOK flow from that point.
