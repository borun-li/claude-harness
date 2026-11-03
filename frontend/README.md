# Frontend Agent Team

A frontend team for Claude Code, installed globally, organised like real frontend work: product
decides what the product does, UX how the user gets through it, UI how it looks and feels, and the
frontend engineer makes it run on the real surface with real data. Backend work goes to the Backend
team. Usually entered through `/route`.

## Commands

| Command | Does |
|---|---|
| `/route <ask>` | Ask the tier, classify the work, start the right team |
| `/frontend <ask>` | Run the Frontend team directly |
| `/frontend status` | Read-only status, gates, Figma budget and timeline |
| `/frontend-resume [phase]` | Continue an interrupted run |
| `/frontend-config [change]` | Show or change models, review panel, design stops, Figma budget |

An audit or review of an existing interface alone is not a run: name `fe-review-experience`,
`fe-review-accessibility` or `fe-review-integration` directly (and `fe-reviewer` to merge).

## How it works

```mermaid
flowchart LR
    S(["/frontend"]) --> P[be-analyst<br/>features] --> UX[fe-ux<br/>flows, pages, states] --> UI[fe-ui<br/>Figma]
    UI --> Q[fe-engineer<br/>feasibility, queue] --> B[fe-engineer<br/>build] --> V[fe-tester ‖ review panel<br/>→ fe-reviewer] --> E([accepted])
    UI -. "flow feels wrong" .-> UX
    Q -. "too costly, does not fit" .-> UI
    V -. "not done, blocker, major" .-> B
    V -. "design defect" .-> UI
    E -. "after launch: feedback" .-> UX
```

- **Solid arrows**: the order of work. In a cross-stack run the features come from the Backend
  team's requirements.
- **Dotted arrows**: feedback flows back. Any role may raise a design-feedback item (DFB); its
  owner decides it; a change to something you confirmed comes back to you.
- **While UI draws**, the engineer already builds what does not depend on visuals (data fetching,
  state handling, routing).
- **Figma**: UI is drawn in Figma and confirmed there before anything is built. Each run has a call
  budget proposed at kickoff (20 + 8 per page by default, under a 300-a-month cap).
- **Your sign-off**: Kickoff (one question), **UX** (flows and states; only for 2+ pages or a new
  flow), **UI** (the Figma frames and the queue of expected results), and **Acceptance**.
- **Review**: a panel of up to three reviewers on the running interface — experience (always),
  accessibility, data & runtime (by risk and what changed) — merged by a coordinator who drops a
  finding only with counter-evidence. Only blockers and majors go to a fix round.
- **Checks**: automatic gates after every phase (shared with the Backend team); results you accept
  are registered and re-checked in every later round. A tamper-evident run log records every
  dispatch, sign-off and Figma call count.

## Team

| Agent | Role | Writes |
|---|---|---|
| `be-analyst` | Product features, in frontend-only runs | `00-requirements.md` |
| `fe-ux` | Flows, page structure, state tables, ASCII wireframes; post-launch insights | `01-ux.md`, `06-feedback.md` |
| `fe-ui` | Design plan and self-check, tokens, components, Figma frames | `02-ui.md`, Figma |
| `fe-engineer` | Scaffold, feasibility, the queue, then one row at a time; fixes | `03-queue.md`, frontend code, contract draft |
| `fe-tester` | One verdict per row against its frame and state rows | `04-verification.md`, tests |
| `fe-review-experience` · `-accessibility` · `-integration` | Review panel, read-only | returned candidates |
| `fe-reviewer` | Coordinator and re-checker | `05-review.md` |
| Orchestrator | Interviews, evidence capture, frame exports, gates, state | `state.json`, `evidence/` |

## Files

| Path | Change it to… |
|---|---|
| `~/.claude/CONSTITUTION.md` | change rules every agent follows (yours alone) |
| `frontend/QUALITY-BARS.md` | raise the Definition of Done |
| `frontend/PLAYBOOK.md` | change phases, stops, feedback routing |
| `frontend/config.json` | change models, review panel, design stops, Figma budget, viewports, caps |
| `frontend/templates/` | change the deliverables (examples in `templates/examples/`) |
| `route/FRONTEND_BACKEND_LINE.md` | change the line between the teams |
| `gates/` | change the automatic checks (keep `gates/tests` green) |
| `agents/fe-*.md` | change one role |
| `frontend/CHANGELOG.md` | record what changed and why |

Per-project: `<project>/.claude/project-context.md` (surface, named user, frontend/backend line,
taste choices) and `<project>/.claude/frontend.json`.

The agents that use Figma (`fe-ui`, `fe-engineer`) list the tools of the Figma plugin's MCP server
as `mcp__plugin_figma_figma__*`. If your Figma server is installed under another name, change that
entry in their frontmatter.
