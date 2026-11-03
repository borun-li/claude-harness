---
description: 'Frontend Agent Team — product features → UX (flows, pages, states) → UI (Figma) → build on the real surface → verify and review → acceptance, with design feedback flowing back. Roles: fe-ux, fe-ui, fe-engineer, fe-tester, the review panel fe-review-experience / -accessibility / -integration with its coordinator fe-reviewer; be-analyst writes the features in frontend-only runs. For a read-only report use /frontend-status.'
argument-hint: '[description, path or URL]'
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

`status` as the first token → say the report is now `/frontend-status` and stop; never start a
run. An audit or a review of an existing interface alone is not a run: dispatch `fe-review-*`
(and `fe-reviewer` to merge) directly, as their agent files' "Called directly" rules describe.

## Then

Run PLAYBOOK §2 (Kickoff), including the mandatory `AskUserQuestion` confirmation, then the
phases. The PLAYBOOK is the whole procedure; this file adds nothing to it.
