---
description: Inspect or change the frontend team's configuration — role models, review panel, design stops, Figma budget, viewports, loop caps, delivery surface, named user, gate settings — globally or for this project only.
argument-hint: '[what to change, e.g. "fe-ui to sonnet" | "Figma budget 400" | empty to just show]'
model: opus
disable-model-invocation: true
---

> **Read `~/.claude/CONSTITUTION.md` first. It overrides this file; on conflict, follow it and report the conflict.**

You maintain the frontend harness. Its files:

| File | Holds | Scope |
|---|---|---|
| `~/.claude/frontend/config.json` | role models, review panel, design stops, Figma budget, viewports, loop caps, run dir | global |
| `./.claude/frontend.json` | overrides of the above | project |
| `./.claude/project-context.md` | delivery surface, named user, frontend/backend line | project (the user writes it) |
| `~/.claude/gates/config.json` · `./.claude/gates.json` | gate defaults · the project's commands | global · project |
| `~/.claude/frontend/PLAYBOOK.md`, `QUALITY-BARS.md` | procedure and Definition of Done | global |

## Request

$ARGUMENTS

If empty: print the effective configuration (global, project overrides, resolved), the harness
version, the delivery surface, the named user and the Figma calls used this month (summed from
`figma_calls` in the run logs). Then stop.

## When making a change

1. Say what changes, in which file, and its effect on cost and quality. Roles marked `floor`
   (`fe-ux`, the reviewers) never drop below `opus`; say so if asked.
2. Ask: **global** or **this project only**? Default to project scope for anything experimental.
3. Apply the edit. Never write into `project-context.md` without the user's words for it.
4. A change to gate code must add a red case and an innocent case to
   `~/.claude/gates/tests/test_frontend_gates.py`, and both gate suites must pass.
5. Bump `harness_version` and add a dated entry to `~/.claude/frontend/CHANGELOG.md` from a real
   `date` call. Keep rules terse; put history in the CHANGELOG.
