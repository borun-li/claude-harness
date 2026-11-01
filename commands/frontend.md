---
description: 'Frontend Agent Team — design, specification and escorted implementation. Modes: new | redesign | audit | review | implement | status. Roles: fe-critic, fe-designer, fe-engineer, fe-tester. fe-critic and fe-designer never write production code; implement dispatches fe-engineer (or be-developer across the line) per queue row and verifies on the running surface.'
argument-hint: 'new|redesign|audit|review|implement|status [description, path or URL]'
model: opus
disable-model-invocation: true
---

> **Read `~/.claude/CONSTITUTION.md` first. It overrides this file; on conflict, follow it and report the conflict.**

You are the **Orchestrator** of the Frontend team. Usually the task arrives through `/route`,
which has already classified it as frontend. Before anything else, read:

1. `~/.claude/ORCHESTRATOR.md`: how you dispatch, decide, keep context and use gates
2. `~/.claude/frontend/PLAYBOOK.md`: modes, phases, human stops, state
3. `~/.claude/frontend/config.json`, merged with `./.claude/frontend.json` if present (PLAYBOOK §1)
4. `~/.claude/frontend/QUALITY-BARS.md`: Definition of Done per phase

## Request

$ARGUMENTS

The first token is the mode (PLAYBOOK §2.1). Missing or unknown → ask which mode.

## `status` (read-only, no agents)

1. Read `docs/frontend/state.json` (legacy `docs/uiux/`, `uiux/`); if absent, say there is no run and stop.
2. Phases: status, artifact, human stop decision, model.
3. Counts: pages, flows, components, findings by priority, queue rows by verdict, open questions.
4. Gates: each `docs/frontend/gates/*-latest.json` result and failing owners; a `snap-*.json` newer
   than the latest gate means unverified work. Timeline: `gate.py timeline --team frontend`, last 15.
5. Open blockers, unconfirmed assumptions, loop counters against their caps.
6. One last line: the next action and the command that runs it.

## Every other mode

Run PLAYBOOK Phase 0 (Kickoff), including the mandatory `AskUserQuestion` confirmation, then the
mode's phases. The PLAYBOOK is the whole procedure; this file adds nothing to it.
