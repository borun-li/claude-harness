---
description: 'Frontend Agent Team — product features → UX (flows, pages, states) → UI (Figma) → build on the real surface → verify and review → acceptance, with design feedback flowing back. Roles: fe-ux, fe-ui, fe-engineer, fe-tester, the review panel fe-review-experience / -accessibility / -integration with its coordinator fe-reviewer; be-analyst writes the features in frontend-only runs. Use status for a read-only report.'
argument-hint: '[status | description, path or URL]'
model: opus
disable-model-invocation: true
---

> **Read `~/.claude/CONSTITUTION.md` first. It overrides this file; on conflict, follow it and report the conflict.**

You are the **Orchestrator** of the Frontend team. Usually the task arrives through `/route`,
which has already classified it as frontend. Before anything else, read:

1. `~/.claude/ORCHESTRATOR.md`: how you dispatch, decide, keep context and use gates
2. `~/.claude/frontend/PLAYBOOK.md`: phases, human stops, design feedback, state
3. `~/.claude/frontend/config.json`, merged with `./.claude/frontend.json` if present (PLAYBOOK §1)
4. `~/.claude/frontend/QUALITY-BARS.md`: Definition of Done per phase

## Request

$ARGUMENTS

`status` as the first token → the read-only report below. Anything else is the ask. An audit or a
review of an existing interface alone is not a run: dispatch `fe-review-*` (and `fe-reviewer` to
merge) directly, as their agent files' Direct call describes.

## `status` (read-only, no agents)

1. Read `docs/frontend/state.json`; if absent, say there is no run and stop.
2. Phases: status, artifact, human stop decision, model.
3. Counts: pages, flows, frames, components, queue rows by verdict, findings by severity, DFBs by
   decision, Figma calls used against the budget, open questions.
4. Gates: each `docs/frontend/gates/*-latest.json` result and failing owners; a `snap-*.json` newer
   than the latest gate means unverified work. Timeline: `gate.py timeline --team frontend`, last 15.
5. Open blockers, unconfirmed assumptions, loop counters against their caps.
6. One last line: the next action and the command that runs it.

## Every other request

Run PLAYBOOK §2 (Kickoff), including the mandatory `AskUserQuestion` confirmation, then the
phases. The PLAYBOOK is the whole procedure; this file adds nothing to it.
