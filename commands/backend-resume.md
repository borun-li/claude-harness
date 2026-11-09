---
description: Resume an in-flight backend run from its state.json, optionally from a specific phase.
argument-hint: '[phase number to resume from, e.g. 4] [optional note]'
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

You are the **Orchestrator** resuming a backend run. Read `~/.claude/ORCHESTRATOR.md`, `~/.claude/backend/PLAYBOOK.md`,
`config.json` (merged with `./.claude/backend.json`) and `QUALITY-BARS.md`.

## Recover state

The run dir is `docs/backend/`, a second feature's `docs/backend/<slug>/`, or legacy
`docs/waterfall/` if only that exists (say so). Find them with `grep -rl --include=state.json '' docs/backend`. Resume the one whose `status` is not `accepted`; more than one, ask the
user which. Every gate and log command then takes `--run-dir <run dir>` when it is not `docs/backend`.

1. Read `<run-dir>/state.json`. If missing, say there is no run and suggest `/backend`; never
   start a new run silently.
2. Read the last `orchestrator` entry in `<run-dir>/handoff.md` (`~/.claude/route/HANDOFF.md`
   §5) and the entries after it: that is where the run stopped. Then read the artifacts the next
   step depends on; skim the others (headings, ids, status) so decisions rest on what was agreed
   without loading every document whole (Constitution §8).
3. Read `<run-dir>/gates/`: the latest report per gate, `attempts.json`, `waivers.json` and the
   `snap-*.json` marks. **A mark newer than the latest gate report means an agent's work was
   never verified: run that phase's gate before anything else.**
4. Read `<run-dir>/run-log.jsonl` (`gate.py timeline`). A `dispatch` with no `return` is an agent
   that never reported back: treat its work as unverified.
5. If `state.json` and disk disagree, trust the disk, say so, and correct the state.

## Confirm before continuing

Show the user the feature, phases done, human gate decisions, computational gate results, loop
counters, open questions, and the phase you will resume at. Re-confirm the model plan with
`AskUserQuestion`; re-confirm the document language only if `state.json` has none.

## Arguments

$ARGUMENTS

A leading number means: resume from that phase. Everything after it in `state.json` is
invalidated. Say which artifacts will be regenerated and get confirmation before overwriting a
signed-off document.

## Then

Continue the PLAYBOOK flow from that point.
