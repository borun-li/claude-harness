# Frontend Agent Team

Designs and builds interfaces people operate (built and checked on the web so far; terminal,
native and desktop as the [root README](../README.md#scope-today) says) the way a real frontend
team does: product decides what, UX how the user gets through it, UI how it looks,
engineering makes it run with real data. Install and commands: the [root README](../README.md).

## How it works

```mermaid
flowchart LR
    S(["/route"]) --> K{{kickoff ■}} --> P[be-analyst<br/>features] --> D{design input}
    D -- new --> UX[fe-ux<br/>flows, pages, states<br/>Figma wireframes] --> US{{UX ■<br/>2+ pages or new flow}}
    US --> UI[fe-ui<br/>design plan, Figma frames] & SC[fe-engineer<br/>scaffold]
    UI & SC --> Q[fe-engineer<br/>feasibility, queue] --> IS{{UI ■<br/>Figma}}
    D -- "confirmed design" --> IN[fe-ux ∥ fe-ui<br/>intake: gaps, frame index] --> GQ[/gap questions<br/>one batch/] --> Q2[fe-engineer<br/>feasibility, queue]
    IS & Q2 --> PR[fe-engineer<br/>runnable prototype, fake data] --> PS{{Prototype ■<br/>try it running}}
    PS --> B[fe-engineer<br/>build, page groups in parallel · preview] --> V[fe-tester ∥ review panel<br/>experience · accessibility · integration] --> CO[fe-reviewer<br/>coordinator] --> AC{{Acceptance ■}}
    AC --> L[fe-ux<br/>after launch] -. "next round" .-> UX
    UI -. "flow feels wrong" .-> UX
    Q -. "too costly, does not fit" .-> UI
    CO -. "not done, blocker, major" .-> B
    CO -. "design defect (UI or UX)" .-> UI
```

**Your sign-offs (■):** the tier at kickoff; **UX** (grey Figma wireframes) and **UI** (Figma
frames) for a new design (one combined stop for a single page); **Prototype**, the design running with fake data, plus the results you
expect from it; **Acceptance**.

- **Bring your own design**: a design you already confirmed is taken in, not redrawn; only its gaps
  are asked, once.
- **Running early**: the prototype is the start of the product, and from then on a preview address
  shows the build as it grows.
- **Build in parallel**: the build goes out in groups of about a page, each in a git worktree of
  its own; `gate.py land` commits each group and merges it onto the run's branch as it returns,
  and the build gate runs without waiting for the others. In a cross-stack run the frontend builds
  at the same time as the backend once their seam is written in the contract, and replaces fake
  data when the backend half has landed.
- **Work flows back**: UI can push back on UX and engineering on the design (a design-feedback
  item); a change to anything you confirmed comes back to you.
- **Review panel**: experience always; accessibility and data & runtime when the change calls for
  them; a coordinator keeps only findings it cannot disprove.
- **Figma budget**: each run has a call budget under your monthly cap; you see the count before
  each design revision.
- **After launch**: your and your users' feedback becomes insights that start the next round.

Rules in full: [`PLAYBOOK.md`](PLAYBOOK.md). Deliverables: `<project>/docs/runs/<slug>/`, shared
with the Backend team in a cross-stack run.

## Team

| Agent | Role |
|---|---|
| `be-analyst` | Product features in frontend-only runs |
| `fe-ux` | Flows, pages, state tables, wireframes (Figma when there is a UX stop); post-launch insights |
| `fe-ui` | Visual design, tokens, components, Figma frames |
| `fe-engineer` | Feasibility, build queue, prototype, then the build |
| `fe-tester` | Checks each built piece against its frame and states |
| `fe-review-experience` · `-accessibility` · `-integration` | Review panel, read-only |
| `fe-reviewer` | Coordinates the panel; re-checks fixes |

## Customise

| Change | File |
|---|---|
| Models, design stops, Figma budget, screen sizes, loop caps | Your defaults `~/.claude/harness-local/config.json`, or per project `<project>/.claude/harness.json` (`/route-config` writes both); they override [`harness/config.json`](../harness/config.json) |
| Definition of done | `QUALITY-BARS.md` |
| Deliverable documents | `templates/` |
| Surface, named user, taste, frontend/backend line | `<project>/.claude/project-context.md` |
