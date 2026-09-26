---
description: Inspect or change the backend team's configuration — model tiers, human gates, review lenses, loop caps, computational gate settings, quality bars — globally or for this project only.
argument-hint: '[what to change, e.g. "reviewer to sonnet" | "prose limit 60 words" | "gate timeout 3600" | empty to just show]'
model: opus
---

> **Read `~/.claude/CONSTITUTION.md` first. It overrides this file; on conflict, follow it and report the conflict.**

You maintain the backend harness. Its files:

| File | Holds | Scope |
|---|---|---|
| `~/.claude/backend/config.json` | models, human gates, lenses, loop caps (incl. `max_gate_fix_rounds`), policy | global |
| `./.claude/backend.json` | overrides of the above | project |
| `~/.claude/gates/config.json` | gate defaults: globs, patterns, timeout, required commands | global |
| `./.claude/gates.json` | the project's commands and gate overrides (user-confirmed) | project |
| `~/.claude/backend/PLAYBOOK.md`, `QUALITY-BARS.md` | procedure and Definition of Done | global |

## Request

$ARGUMENTS

If empty: print the effective configuration (global, project overrides, resolved result), the
harness version and the project's gate profile. Then stop.

## When making a change

1. Say what changes, in which file, and its effect on cost and quality.
2. Ask: **global** or **this project only**? Default to project scope for anything experimental.
3. Apply the edit.
4. A change to gate code (`~/.claude/gates/gatelib/`) must add a red case and an innocent case to
   `~/.claude/gates/tests/test_gates.py` (backend) or `test_frontend_gates.py` (frontend), and both
   suites must pass before you finish.
5. Bump `harness_version` (patch: tuning, minor: new behaviour, major: changed phase flow or
   artifact contract) and add a dated entry to `~/.claude/backend/CHANGELOG.md` from a real `date`
   call. Keep rules terse; put history in the CHANGELOG.

Never edit a role agent's file to work around a config value; fix the config or the PLAYBOOK.
