---
description: Show the status of the backend run in this project — phases, human gates, computational gates, open items. Read-only, cheap.
argument-hint: (no arguments)
model: sonnet
allowed-tools: Bash(cat:*), Bash(grep:*), Bash(echo:*), Bash(tail:*), Bash(python3 ~/.claude/gates/gate.py timeline:*)
disallowed-tools: Write, Edit, NotebookEdit, Agent
---

> **Read `~/.claude/CONSTITUTION.md` first. It overrides this file; on conflict, follow it and report the conflict.**

Report the backend run's status. **Read-only**: change nothing, run no gate (gates run tests and
write reports), dispatch no agent, advance no phase. The one exception is
`python3 ~/.claude/gates/gate.py timeline`, which renders the run log (it also writes
`<run-dir>/run-log.md`).

The run dir is `docs/backend/`, a second feature's `docs/backend/<slug>/`, or legacy
`docs/waterfall/` if only that exists (say so). Several runs: report the one whose `status` is not
`accepted`; more than one such run, report each briefly. Its timeline: `gate.py timeline --project .
--run-dir <run dir>`.

Loaded before you start:

- state.json: !`grep -rH --include=state.json '' docs/backend 2>/dev/null || grep -rH --include=state.json '' docs/waterfall 2>/dev/null || echo "(no state.json)"`
- Timeline (last 15): !`python3 ~/.claude/gates/gate.py timeline --project . 2>&1 | tail -15 || true`

1. Use the `state.json` loaded above. If there is none, say there is no run here and stop.
2. **Phases:** phase, status, artifact (size, modified time), human stop decision (Prototype,
   Plan, Acceptance, conditional), model. Flag a phase marked done whose artifact is missing or
   near-empty.
3. **Gates:** for each `<run-dir>/gates/<gate>-latest.json`: overall, time, failing checks with
   owners. Add the consecutive-failure counts from `gates/attempts.json` against
   `loops.max_gate_fix_rounds`, and any `gates/waivers.json` entries. Flag a `snap-*.json` mark
   newer than the latest gate report: that work has not been verified.
4. **Counts:** requirements (active / below cut), test cases, pass/fail/blocked, open findings by
   severity.
5. **Timeline:** the last 15 events loaded above; say whether `LOG.valid` passed in the latest
   gate report.
6. **Open items:** open questions, unresolved findings, review loop counter against its cap.
7. One last line: the next action and the command that runs it.

A compact terminal report, no prose.
