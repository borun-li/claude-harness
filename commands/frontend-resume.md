---
description: Resume an in-flight frontend run from docs/frontend/state.json, optionally from a specific phase.
argument-hint: '[phase number to resume from] [optional note]'
model: opus
---

> **Read `~/.claude/CONSTITUTION.md` first. It overrides this file; on conflict, follow it and report the conflict.**

You are the **Orchestrator** resuming a frontend run. Read `~/.claude/ORCHESTRATOR.md`, `~/.claude/frontend/PLAYBOOK.md`,
`config.json` (merged with `./.claude/frontend.json`) and `QUALITY-BARS.md`.

## Recover state

The run dir is `docs/frontend/`, or legacy `docs/uiux/` / `uiux/` if only that exists (say so).

1. Read `state.json`. If missing, say there is no run and suggest `/frontend`.
2. Read the last `orchestrator` entry in `docs/frontend/handoff.md` (`~/.claude/route/HANDOFF.md`
   §5) and the entries after it. Then read the artifacts the next step depends on; skim the
   others (headings, ids, status) (Constitution §8).
3. Read `gates/`: latest report per gate, `attempts.json`, `waivers.json`, `observables-approved.json`
   and the `snap-*.json` marks. **A mark newer than the latest gate report is unverified work: run
   that phase's gate first.**
4. Run `gate.py timeline --team frontend`. A `dispatch` with no `return` is unverified work.
5. If `state.json` and disk disagree, trust the disk, say so, and correct the state.

## Confirm before continuing

Show the mode, phases done, human stop decisions, gate results, loop counters, open questions and
the phase you will resume at. Re-confirm the model plan with `AskUserQuestion`.

## Arguments

$ARGUMENTS

A leading number means: resume from that phase. Say which artifacts will be regenerated and get
confirmation before overwriting an approved one.

## Then

Continue the PLAYBOOK flow from that point.
