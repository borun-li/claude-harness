---
description: Inspect or change the agent team's configuration — models per role, document language, review panels, round caps, design stops, Figma budget, viewports, gate settings — globally or for this project only.
argument-hint: '[what to change, e.g. "be-reviewer to sonnet" | "Figma budget 400" | "gate timeout 3600" | empty to just show]'
model: opus
disable-model-invocation: true
---

> **Read `~/.claude/CONSTITUTION.md` first. It overrides this file; on conflict, follow it and report the conflict.**

You maintain the harness configuration. Its files:

| File | Holds | Scope |
|---|---|---|
| `~/.claude/harness/config.json` | the harness defaults: models per role and tier, review panels, round cap, design stops, Figma budget, viewports, taste measures, where runs live | replaced by every install; read it, never edit it |
| `~/.claude/harness-local/config.json` | the user's own defaults, overriding the above | global |
| `./.claude/harness.json` | overrides of both | project |
| `~/.claude/gates/config.json` | gate defaults: globs, patterns, timeout, required commands | replaced by every install |
| `./.claude/gates.json` | the project's commands and gate overrides (user-confirmed) | project |
| `./.claude/settings.json` `worktree` | how parallel writers' worktrees are made (`gate.py worktrees --setup`) | project |
| `./.claude/project-context.md` | delivery surface, named user, frontend/backend line | project (the user writes it) |

## Request

$ARGUMENTS

If empty: print the effective configuration (defaults, the user's, the project's, resolved), the
harness version, the project's gate profile and, with an interface, the delivery surface, the named
user and the Figma calls used this month (summed from `figma_calls` in the run logs). Then stop.

## When making a change

1. Say what changes, in which file, and its effect on cost and quality. A role in `models.floor`
   never drops below its model; say so if asked.
2. Ask: **global** or **this project only**? Default to project scope for anything experimental.
3. Apply the edit: global goes to `~/.claude/harness-local/config.json` (create it; only the keys
   that differ; a nested key such as `loops.max_rounds` or `models._active_tier` is enough by
   itself), project to `./.claude/harness.json`. A gate setting goes to
   `./.claude/gates.json`; nested keys such as `doc_budgets` and `commands` merge key by key.
   Never write into `project-context.md` without the user's words for it.

Never edit a role agent's file to work around a config value. A change to the harness itself
(rules, gate code, hooks) is made in its repository and installed from there: files under
`~/.claude` that install owns are replaced by the next install.
