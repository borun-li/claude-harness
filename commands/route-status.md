---
description: Show the status of the agent-team run in this project — step, the user's decisions at each stop, gates, what the last agents changed, open items. Read-only, cheap.
argument-hint: '[run slug, when several]'
model: sonnet
allowed-tools: Bash(cat:*), Bash(grep:*), Bash(echo:*), Bash(tail:*), Bash(python3 ~/.claude/gates/gate.py status:*), Bash(python3 ~/.claude/gates/gate.py timeline:*)
disallowed-tools: Write, Edit, NotebookEdit, Agent
---

> **Read `~/.claude/CONSTITUTION.md` first. It overrides this file; on conflict, follow it and report the conflict.**

Report the run's status. **Read-only**: change nothing, run no gate (gates run tests and write
reports), dispatch no agent, advance no phase.

Runs live in `docs/runs/<slug>/`. With several, report the open one in full and the others in a
line each; `$ARGUMENTS` names one (`--run <slug>` on the commands below).

## Loaded

- Runs: !`grep -H '"status"' docs/runs/*/state.json 2>/dev/null || echo "(no run under docs/runs)"`
- Status: !`python3 ~/.claude/gates/gate.py status --project . 2>&1 | tail -40 || true`
- Timeline (last 15): !`python3 ~/.claude/gates/gate.py timeline --project . 2>&1 | tail -15 || true`

## Report

1. **Run:** feature, goal, tier, scope, status, started and last updated.
2. **Phases:** per team in scope: phase, status, artifact (size, modified time), the user's decision
   at each stop, model. Flag a phase marked done whose artifact is missing or near-empty.
3. **Gates:** from the status loaded above: each gate's last verdict, failing checks with owners,
   rounds used against `loops.max_rounds`, waivers. Flag a return that is not landed or is newer
   than the latest gate run: that work has not been verified.
4. **Changes:** the last writer returns: who, which files, what the user will see.
5. **Counts:** requirements (active / below the cut), test cases and results, findings by severity;
   with an interface: pages, frames, queue rows by verdict, DFBs by decision, Figma calls against
   the budget.
6. **Open items:** open questions, unresolved findings, unconfirmed assumptions, the timeline's
   `Rounds used` line; whether `LOG.valid` passed in the latest gate report.
