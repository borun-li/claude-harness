# Frontend Agent Team — Orchestration Playbook

> **Read `~/.claude/CONSTITUTION.md` first. It overrides this file; on conflict, follow it and report the conflict.**
> **Then read `~/.claude/ORCHESTRATOR.md`: how you dispatch, decide, keep context and use gates.**

What the Frontend team runs and when. Version: `harness_version` in `~/.claude/frontend/config.json`.
The team follows real frontend work: **product** decides what it does, **UX** how the user gets
through it, **UI** how it looks, **engineering** makes it run on the real surface with real data.
Work flows forward; feedback flows back (§3A). Besides orchestrating, you keep the preview running
and capture evidence; you make no Figma calls.

---

## 0. Roles

| Agent | Does | Writes |
|---|---|---|
| `be-analyst` | Product features in a frontend-only run (cross-stack: the Backend team's Phase 1) | `00-requirements.md` |
| `fe-ux` | Flows, pages, state tables, wireframes; intake of an external design; post-launch insights | `01-ux.md`, `06-feedback.md` |
| `fe-ui` | Design plan, tokens, components, Figma frames; intake index; frame exports | `02-ui.md`, Figma, `evidence/design/` |
| `fe-engineer` | Scaffold, feasibility, contract draft, queue, runnable prototype, rows, fixes | `03-queue.md`, contract draft, frontend code |
| `fe-tester` | One verdict per row against its frame and state rows | `04-verification.md`, tests |
| `fe-review-*` | Review panel (§6), read-only | returned candidates |
| `fe-reviewer` | Coordinator; re-checks fixed FNDs | `05-review.md` |

Queue rows on the backend side of the line go to `be-developer` (`~/.claude/route/FRONTEND_BACKEND_LINE.md`).

## 1. Configuration

1. Read `~/.claude/frontend/config.json`; shallow-merge `<project>/.claude/frontend.json` and say so.
   Models come from `roles`: judgement → `opus`, carrying out a decision → `sonnet`; floors hold.
2. Every `fe-*` agent works in the user's document language; identifiers stay English.
3. A `state.json` below 7.0 is not resumed: offer a new round that reads its artifacts as input.

## 1C. Delivery surface

From the project context; ask at kickoff if unset; never assume a browser. A terminal is designed as
text mockups in `02-ui.md`; everything else in Figma. Evidence is the surface's own structure (DOM
and computed styles, view or accessibility tree, raw terminal bytes), never a picture alone.

## 1D. Named user and priority

One concrete `primary_user_role`. **P1**: that user is blocked or does the wrong thing; **P2**:
finishes, but it is hard; **P3**: would not notice. Rows are built P1 first.

## 1E. Figma budget

The user's monthly cap is `figma.monthly_budget`; a run's budget is `base + per_page × pages`,
shown at kickoff and re-shown when the page count changes. Only `fe-ui` and `fe-engineer` call
Figma: each brief carries the calls left (`--figma-left` on `log dispatch`), each return's
`figma_calls` is logged. Warn at `warn_at`; going over needs the user's yes (`--stop Budget`).

---

## 2. Kickoff

**2.1** The ask in the user's words and its simplest useful version: that is the round.

**2.2 Recon (≈30 s, read-only):** surface and stack, a backend run (`docs/backend/01-requirements.md`
makes it cross-stack), existing frontend artifacts and design system, and the design input (§2.5).

**2.3 One `AskUserQuestion`** (skip what `/route` asked). First a preview of what stands unless the
user changes it: language, design input, models, risk with its evidence, design stops and budget.
Ask only:
- **Tier** (Constitution §7). Prototype = up to the Prototype stop. A confirmed design or prototype
  is named in the first option ("Full development, reusing the design confirmed <date>"); choosing
  it confirms the design is final. Small change → `~/.claude/commands/route.md` §4.
- **Goal** (Constitution §7.4): what the user will observe at the end and how they will check it;
  the round (§2.1) is what that goal needs, and nothing more.
- Facts the project context lacks: surface, named user, the `design-taste` §1 choices. Record them
  in `project-context.md`.

Design stops (`design_stop_rule`): two (UX, then UI) for a new design with 2+ pages or a new flow,
one otherwise, none for an external design.

**2.4** Write `state.json` (§8) with the goal in the user's words, and with `requirements` pointing
at the backend's `01-requirements.md` in a cross-stack run; an unfinished one → `/frontend-resume`.

**2.5 Design input** (`design`):
- `new` — nothing, or only reference material. Full Phases 1–2.
- `external` — a design the user confirmed elsewhere and calls final (Figma, mockups, a product to
  match). Phase 1E instead of the design work; `design_stops: 0`; log at once
  `log human --stop UI --decision approved --note "external <link>, confirmed <date>"`. Never
  assume it: what the user has not called final is reference material.
- `reused` — a prototype confirmed by this harness. Keep its run dir, re-run its design gates, go to
  Phase 3 (one confirmed before 8.0.0 was design only: run Phase 2b first).

---

## 3. Phase flow

A phase ends when its gate exits 0. Phase numbers are the run log's `--step`. `mark --role <agent>
--team frontend` before every dispatch (`fe-reviewer` once per panel or re-check).

**Phase 0 — Features.** Frontend-only: `be-analyst` → `00-requirements.md`, gate `fe-product`.

**Phase 1 — UX** (`new`). `fe-ux` → `01-ux.md`, gate `fe-ux`; `missing_requirements` go back to the
analyst as one amendment. **UX stop** in two-stop runs.

**Phase 1E — Intake** (`external`). In one message `fe-ux` and `fe-ui` take in the design: what it
shows is pointed at, not rewritten; what it leaves open gets a recommended decision; `fe-ui` exports
the frames. Gates `fe-ux`, `fe-ui`. Then ask, **once and together**, the open decisions that would
change what the prototype shows; the rest take their defaults and go on the Prototype stop's list.

**Phase 2 — UI and queue.** `baseline --team frontend` first.
- `new`: `fe-ui` draws, gate `fe-ui`; in two-stop runs `fe-engineer` scaffolds alongside (the
  confirmed UX is its approved design), gate `fe-build`.
- `fe-engineer` checks feasibility (DFBs for what is costly or does not fit), writes the queue and
  names earlier approved results the round may change (§3I). Gates `fe-queue`, `fe-plan`.
- **UI stop** (`new`): the frames and DFB decisions. Revisions go to a fresh `fe-ui`, with the
  budget left. On yes a fresh `fe-ui` exports the frames.

**Phase 2b — Prototype.** `fe-engineer` makes the confirmed design run on the real surface: pages
reachable, the primary flow working, fake data behind one replaceable layer. It is the start of the
product, not throwaway. Gate `fe-build`; start the preview (§3J) and try it yourself.
- **Prototype stop**: the address, `gates/plan-review.md`, the earlier results it may change (§3I),
  and what was decided without the user. Changes → a fresh `fe-engineer`, or a DFB if the design
  changes. On yes: `fe-approve --by <user>` (`--retire` what they let go) and log `--stop Prototype`
  (cross-stack: in both run logs). A Prototype-tier run ends here (`prototype_confirmed`).

**Phase 3 — Build.** One row per dispatch, by `side`, P1 first, rows sharing a file serially; each
brings its page to the frame at every size and connects real data. `fe-build` after each. Report
progress (§3J). A design problem is a DFB, never a silent deviation.

**Phase 4 — Verify and review.**
1. Capture (§3H), then in one message `fe-tester` and the panel (§6).
2. A fresh `fe-reviewer` merges candidates and not-done rows into `05-review.md`. Gates `fe-review`,
   then `fe-verify` (it reruns the tests).
3. Fix only blockers, majors and not-done rows, by fresh owners; design defects go to `fe-ux`/`fe-ui`.
   Recapture; fresh tester and reviewer re-judge only the named defects. At `loops.max_rounds`
   minors are deferred; only blockers, majors and P1 rows escalate (Constitution §5.4).

**Acceptance.** `fe-accept`, then lead with the goal and the user running their own check; show
verification, review (drops and deferred), the DFB register and `gates/traceability.md`. On yes `status: accepted` and `fe-promote --by <user>`.

**Phase 5 — After launch.** User or user feedback → a fresh `fe-ux` writes `INS-###` entries; the
ones the user picks start the next round as an increment.

## 3A. Design feedback

Any agent may raise a `DFB-###`; you file it in `06-feedback.md` and a fresh owner decides it
(`fe-ux` for flows, pages, states; `fe-ui` for looks). A change to something the user confirmed
needs the user: at once if it blocks, otherwise at the next stop; until then the confirmed design
stands. Smaller details the owner decides and you list. Accepted changes flow forward (UX → frames
→ rows); approved rows change only by re-approval.

## 3B. Increments

As backend PLAYBOOK §3B: never restart; the original flow reaches its next stop; there the
increment joins with only its items, in `## Increment <n>` sections with new ids.

## 3C. The frontend/backend line

`~/.claude/route/FRONTEND_BACKEND_LINE.md`. An unwritten line stops the queue.

## 3D. Gates

Run by you, never by the agent checked; reports in `docs/frontend/gates/`. Phase gates are named in
§3. Exit codes and waivers: `ORCHESTRATOR.md`.

## 3E. Approved observables

A row's `observable` and its frame export are what the running interface must show. `fe-approve`
locks both at the Prototype stop; changing either afterwards needs the user's re-approval.

## 3F. Human stops

**Fixed:** Kickoff; UX and UI (`new`, by design stops); Prototype; Acceptance. Otherwise only a
Constitution §5 case, Phase 1E's one batch, a blocking `needs user` DFB, or the budget. Everything
else is decided with a recommended default and shown at the next stop.

## 3G. Run log

Commands in `ORCHESTRATOR.md` with `--team frontend`. `fe-accept` checks the trail follows §3's
order: design approved before the prototype, the Prototype stop before the build.

## 3H. Evidence capture

A script produces evidence. Write `capture-plan.json` covering every row, size and state:
`surface` (`web` | `terminal` | `manual`); web: `base_url`, `sizes` (one `{name, width, height}` per
`viewports` entry, height `viewport_height`); per capture `id`, `row`, `state`, then `url` + `steps`
+ `styles` (web), `command` + `columns`/`lines` (terminal) or `instrument` + `files` (manual). Run
`fe-capture-plan`, start an isolated instance, `capture --round <n>`. A round is never
overwritten. Frame exports (`evidence/design/FRAME-###.png`) come from `fe-ui` once, and are locked.

## 3I. Approved-observable registry

`fe-promote` registers accepted rows as `OBS-###`, each guarded by a tagged test or a capture;
later rounds must keep them (`FE.regression`). What a round may change comes from `fe-plan` and from
`fe-engineer`'s `may_change`; show them as one list with a recommendation, and retire only what the
user lets go.

## 3J. Preview and progress

From the prototype on, keep the product running in an isolated instance and give the user its
address. After each batch of rows, one line on what is done. Not a stop; what the user says becomes
a DFB or an increment.

---

## 4. Rules in every phase

1. No phase starts without its upstream artifact.
2. The handoff log is `<run-dir>/handoff.md` (cross-stack: the backend run dir's).
3. Reviewers hold Bash: `fe-review` checks the tree is unchanged outside the run dir and tests;
   role checks ignore the other team's run dir.

## 6. Risk and review panel

| | `risk: normal` | `risk: high` |
|---|---|---|
| `fe-review-experience` | always | always |
| `fe-review-accessibility` | diff touches interactive components, forms or navigation | always |
| `fe-review-integration` | diff touches API calls, data loading or client state | always |

`fe-reviewer` coordinates whenever a panelist ran. Say whom you dispatched and why; a risk change
mid-run is a Constitution §5.1 stop.

## 7. Artifacts

```
docs/frontend/      (second round: docs/frontend/<slug>/, gates take --run-dir with that path)
  00-requirements.md  01-ux.md  02-ui.md  03-queue.md  04-verification.md  05-review.md
  06-feedback.md  state.json  run-log.jsonl  handoff.md  capture-plan.json  observables.json
  evidence/{design,verify-<n>}/  gates/  logs/
contracts/FRONTEND_BACKEND_CONTRACT.md
```

## 8. `state.json`

```json
{
  "harness_version": "x.y.z", "feature": "one line", "slug": "round-slug",
  "goal": { "change": "what the user will observe", "check": "how they will tell it worked" },
  "started_at": "ISO-8601", "updated_at": "ISO-8601",
  "status": "in_progress | blocked | prototyping | building | verifying | accepted | fix_capped | prototype_confirmed",
  "tier": "prototype | full", "risk": "normal | high",
  "design": "new | external | reused", "design_stops": 1,
  "requirements": "docs/frontend/00-requirements.md",
  "delivery_surface": "…", "primary_user_role": "…",
  "figma": { "file": "…", "budget": 60 },
  "models": { "fe-ux": "opus", "…": "…" },
  "current_phase": 2, "phases": [], "stops": {}, "preview": "…",
  "increments": [], "open_questions": [], "notes": []
}
```
