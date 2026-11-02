# Backend Agent Team

A phase-gated development team for Claude Code, installed globally. It builds the backend;
interface work goes to the Frontend team (PLAYBOOK §3C). Commands: see the root `README.md`.

## How it works

```mermaid
flowchart LR
    S(["/backend"]) --> AN[be-analyst] --> P([prototype]) --> AR[be-architect] --> FX[be-analyst<br/>fixture answers]
    FX --> DEV[be-developer] & TE[be-tester]
    DEV & TE --> PN[review panel<br/>behavior · reliability · security] --> CO[be-reviewer<br/>coordinator] --> E([delivered])
    CO -. "blocker / major" .-> DEV
    TE -. "failed tests" .-> DEV
```

- **Solid arrows**: the order of work. The prototype is skipped when you already confirmed one.
- **be-developer ∥ be-tester**: code is built while the test plan is written from the design.
- **Review panel**: three read-only reviewers in parallel, one lens each; the coordinator merges
  them, tries to disprove each candidate, and keeps only what survives. Only blockers and majors
  are fixed; a fix is re-checked by one reviewer, not the whole panel.
- **Risk**: `high` (money, personal data, auth, irreversible operations, schema, new dependencies,
  public APIs) adds a design review and the full panel; `normal` trims the panel (PLAYBOOK §6).
- **Dotted arrows**: fix loops, always through the orchestrator, each round a fresh agent.
- **Orchestrator**: dispatches every step and runs automatic checks between steps (PLAYBOOK §3D).
- **Your sign-off**: the kickoff question, the prototype, **Plan** (one page of requirements,
  decisions and fixture answers, before any code) and **Acceptance**. You are asked in between only
  when an answer would change what gets built.
- **Run log**: every dispatch, gate result, decision and sign-off goes into a tamper-evident
  `run-log.jsonl`. `/backend-status` shows it as a timeline.
- **Deliverables**: `<project>/docs/backend/`.

## Team

| Agent | Role | Writes |
|---|---|---|
| Orchestrator | Plans, dispatches, runs gates, keeps state, reports | `state.json`, `07-acceptance.md` |
| `be-analyst` | Testable requirements; later, the fixture answers and design-vs-requirement check | `01-requirements.md`, fixtures |
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
| `backend/config.json` | change models, human gates, review panels, loop caps |
| `backend/templates/` | change the deliverable documents |
| `gates/` | change computational checks (keep `gates/tests` green) |
| `agents/be-*.md` | change one role |
| `backend/CHANGELOG.md` | record what changed and why |

Per-project overrides: `<project>/.claude/backend.json` and `<project>/.claude/gates.json`.
