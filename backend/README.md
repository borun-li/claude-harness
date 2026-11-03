# Backend Agent Team

A phase-gated development team for Claude Code, installed globally. It builds the backend;
interface work goes to the Frontend team (PLAYBOOK §3C). Commands: see the root `README.md`.

## How it works

```mermaid
flowchart LR
    S(["/backend"]) --> K{{kickoff ■}} --> AN[be-analyst<br/>requirements] --> P{{prototype ■}}
    P --> AR[be-architect<br/>architecture + detailed design] --> FX[be-analyst<br/>fixture answers] --> PL{{Plan ■}}
    AR -. "risk: high" .-> DR[design review<br/>behavior · reliability] -. "one revision" .-> AR
    FX -. "design contradicts a REQ" .-> AR
    PL --> DEV[be-developer<br/>build] & TP[be-tester<br/>test plan]
    PL --> FT[[Frontend team<br/>side: frontend items]]
    DEV & TP --> VT[be-tester<br/>run tests] --> PN[review panel<br/>behavior · reliability · security] --> CO[be-reviewer<br/>coordinator] --> AC{{Acceptance ■}}
    FT --> AC
    VT -. "failed tests" .-> DEV
    CO -. "blocker / major" .-> DEV
```

- **■ Your sign-off**: the kickoff question (tier, models, risk), the prototype, **Plan** (one page of
  requirements, decisions and fixture answers, before any code) and **Acceptance**. You are asked
  in between only when an answer would change what gets built.
- **Solid arrows**: the order of work — Phase 1 requirements, 1b prototype, 2 design (ending at
  Plan), 4 build ∥ test plan, 5 verification, 6 review, 7 acceptance (Phase 3 was merged into 2).
- **Prototype**: a rough, runnable version (`route/PROTOTYPE.md`), skipped when you already
  confirmed one. When the round touches an interface people operate, the Frontend team's UX and UI
  stops (Figma, or text mockups for a terminal) are the prototype instead
  (`route/FRONTEND_BACKEND_LINE.md` §4).
- **Frontend team**: `side: frontend` items are designed and built by the Frontend team once their
  seam's backend half exists, and verified by its tester and review panel; one Acceptance covers both.
- **Risk**: `high` (money, personal data, auth, irreversible operations, schema, new dependencies,
  public APIs) adds the design review and the full panel; `normal` trims the panel (PLAYBOOK §6).
- **Review panel**: read-only reviewers in parallel, one lens each; the coordinator merges them,
  tries to disprove each candidate, and keeps only what survives. Only blockers and majors are
  fixed; a fix is re-checked by one reviewer, not the whole panel.
- **Dotted arrows**: fix and revision loops, always through the orchestrator, each round a fresh agent.
- **A requirement added mid-run** never restarts the run: it joins at the next stop as an increment
  (PLAYBOOK §3B).
- **Orchestrator**: dispatches every step and runs automatic checks between steps (PLAYBOOK §3D).
- **Run log**: every dispatch, gate result, decision and sign-off goes into a tamper-evident
  `run-log.jsonl`. `/backend-status` shows it as a timeline.
- **Deliverables**: `<project>/docs/backend/`.

## Team

| Agent | Role | Writes |
|---|---|---|
| Orchestrator | Plans, dispatches, runs gates, keeps state, reports | `state.json`, `07-acceptance.md` |
| `be-analyst` | Testable requirements; later, the fixture answers and design-vs-requirement check (also the Frontend team's product role in frontend-only runs) | `01-requirements.md`, fixtures |
| `be-architect` | Architecture and detailed design, in one pass | `02-architecture.md`, `03-detailed-design.md` |
| `be-developer` | Builds the backend exactly to the design | backend code, `08-implementation-log.md` |
| `be-tester` | Plans tests from the design, then writes and runs them | `04-test-plan.md`, tests, `05-test-report.md` |
| `be-review-behavior` · `-reliability` · `-security` | One review lens each (read-only) | candidate findings |
| `be-reviewer` | Coordinates the panel; re-checks fixes (read-only) | findings → `06-review-report.md` |

## Files

| Path | Change it to… |
|---|---|
| `~/.claude/CONSTITUTION.md` | change rules every agent must follow (yours alone to amend) |
| `backend/QUALITY-BARS.md` | raise the Definition of Done |
| `backend/PLAYBOOK.md` | change phase flow, gates, delegation |
| `backend/config.json` | change models, review panels, loop caps (human stops are fixed) |
| `backend/templates/` | change the deliverable documents |
| `route/FRONTEND_BACKEND_LINE.md` | change the line between the teams |
| `gates/` | change computational checks (keep `gates/tests` green) |
| `agents/be-*.md` | change one role |
| `backend/CHANGELOG.md` | record what changed and why |

Per-project overrides: `<project>/.claude/backend.json` and `<project>/.claude/gates.json`.
