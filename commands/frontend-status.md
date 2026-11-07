---
description: Show the status of the frontend run in this project — phases, human stops, gates, design feedback, Figma calls against the budget, open items. Read-only, cheap.
argument-hint: (no arguments)
model: sonnet
allowed-tools: Bash(cat:*), Bash(grep:*), Bash(echo:*), Bash(tail:*), Bash(python3 ~/.claude/gates/gate.py timeline:*)
disallowed-tools: Write, Edit, NotebookEdit, Agent
---

> **Read `~/.claude/CONSTITUTION.md` first. It overrides this file; on conflict, follow it and report the conflict.**

Report the frontend run's status. **Read-only**: change nothing, run no gate (gates run tests and
write reports), dispatch no agent, advance no phase. The one exception is
`python3 ~/.claude/gates/gate.py timeline`, which renders the run log (it also writes
`<run-dir>/run-log.md`).

The run dir is `docs/frontend/`, or a second round's `docs/frontend/<slug>/`. Several runs: report
the one whose `status` is not `accepted`; more than one such run, report each briefly. Its timeline:
`gate.py timeline --project . --team frontend --run-dir <run dir>`.

Loaded before you start:

- state.json: !`grep -rH --include=state.json '' docs/frontend 2>/dev/null || echo "(no state.json)"`
- Timeline (last 15): !`python3 ~/.claude/gates/gate.py timeline --project . --team frontend 2>&1 | tail -15 || true`

1. Use the `state.json` loaded above. If there is none, say there is no run here and stop.
2. **Phases:** tier, phase, status, artifact, human stop decision (UX, UI, Prototype, Acceptance, Budget,
   conditional), model.
3. **Counts:** pages, flows, frames, components, queue rows by verdict, findings by severity, DFBs
   by decision, Figma calls used against the budget, open questions.
4. **Gates:** each `<run-dir>/gates/*-latest.json` result and failing owners; a `snap-*.json`
   newer than the latest gate report means unverified work.
5. **Timeline:** the last 15 events loaded above.
6. **Open items:** open blockers, unconfirmed assumptions, loop counters against their caps.
7. One last line: the next action and the command that runs it.

A compact terminal report, no prose.
