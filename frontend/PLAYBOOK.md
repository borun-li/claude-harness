# Frontend Agent Team — Orchestration Playbook

> **Read `~/.claude/CONSTITUTION.md` first. It overrides this file; on conflict, follow it and report the conflict.**
> **Then read `~/.claude/ORCHESTRATOR.md`: how you dispatch, decide, keep context and use gates.**

What the Frontend team runs and when. Version: `harness_version` in `~/.claude/harness/config.json`.
The team follows real frontend work: **product** decides what it does, **UX** how the user gets
through it, **UI** how it looks, **engineering** makes it run on the real surface with real data.
Work flows forward; feedback flows back (§3A). Besides orchestrating, you keep the preview running
and capture evidence; you make no Figma calls.

---

## 0. Roles

| Agent | Does | Writes |
|---|---|---|
| `be-analyst` | Product features in a frontend-only run (cross-stack: the Backend team's Phase 1) | `00-requirements.md` |
| `fe-ux` | Flows, pages, state tables, wireframes (Figma for a UX stop); intake of an external design; post-launch insights | `01-ux.md`, `06-feedback.md`, Figma wireframes |
| `fe-ui` | Design plan, tokens, components, Figma frames; intake index; frame exports | `02-ui.md`, Figma, `evidence/design/` |
| `fe-engineer` | Scaffold, feasibility, contract draft, queue, runnable prototype, rows, fixes | `03-queue.md`, contract draft, frontend code |
| `fe-tester` | One verdict per row against its frame and state rows | `04-verification.md`, tests |
| `fe-review-*` | Review panel (§6), read-only | returned candidates |
| `fe-reviewer` | Coordinator; re-checks fixed FNDs | `05-review.md` |

Queue rows on the backend side of the line go to `be-developer` (`~/.claude/route/FRONTEND_BACKEND_LINE.md`).

## 1. Configuration

1. The merged configuration (`ORCHESTRATOR.md` § Capabilities, Start); say which layers you
   merged. Models come from `models.tiers[_active_tier]`: judgement → `opus`, carrying out a
   decision → `sonnet` (`models.adjust` says when a role moves for one dispatch); a role in
   `models.floor` is never dispatched below its model (the hook refuses).
2. Every `fe-*` agent works in the user's document language; identifiers stay English.

## 1C. Delivery surface

From the project context; ask at kickoff if unset; never assume a browser. A terminal is designed as
text mockups in `02-ui.md`; everything else in Figma. Evidence is the surface's own structure (DOM
and computed styles, view or accessibility tree, raw terminal bytes), never a picture alone.

## 1D. Named user and priority

One concrete `primary_user_role`. **P1**: that user is blocked or does the wrong thing; **P2**:
finishes, but it is hard; **P3**: would not notice. Rows are built P1 first.

## 1E. Figma budget

The user's monthly cap is `figma.monthly_budget`; a run's budget is `base + per_page × pages`,
shown at kickoff and re-shown when the page count changes. Only `fe-ux` (UX-stop wireframes),
`fe-ui` and `fe-engineer` call Figma: each brief carries the calls left (its `Budget:` line), each return's
`figma_calls` is logged. Warn at `warn_at`; going over needs the user's yes (`--stop Budget`).

---

## 2. Kickoff

**2.1** The ask in the user's words and its simplest useful version: that is the round.

**2.2 Recon (read-only, brief):** surface and stack, existing frontend artifacts and design system,
the design input (§2.5), and what a second copy of the project needs to build and run
(`ORCHESTRATOR.md` § Parallel).

**2.3 One `AskUserQuestion`** (skip what `/route` asked). First a preview of what stands unless the
user changes it: language, design input, models, risk with its evidence, design stops and budget.
Ask only:
- **Tier** (Constitution §7). Prototype = up to the Prototype stop. A confirmed design or prototype
  is named in the first option ("Full development, reusing the design confirmed <date>"); choosing
  it confirms the design is final. Small change → `~/.claude/commands/route.md` §4; Standard
  change → `~/.claude/route/STANDARD.md`.
- **Goal** (Constitution §7.4): what the user will observe at the end and how they will check it;
  the round (§2.1) is what that goal needs, and nothing more.
- Facts the project context lacks: surface, named user, the `design-taste` §1 choices. Record them
  in `project-context.md`, and the product class in `state.json` (`product_class`).

Design stops (`design_stop_rule`): two (UX, then UI) for a new design with 2+ pages or a new flow,
one otherwise, none for an external design.

**2.4** Write `docs/runs/<slug>/state.json` (§8) with the goal in the user's words; an unfinished
run → `/route-resume`. Then the demo's before (`ORCHESTRATOR.md` § Demo), before any dispatch. A
cross-stack run is already open: add the interface's keys to its `state.json`.

**2.5 Design input** (`design`):
- `new` — nothing, or only reference material. Full Phases 1–2.
- `external` — a design the user confirmed elsewhere and calls final (Figma, mockups, a product to
  match). Phase 1E instead of the design work; `design_stops: 0`; log at once
  `log human --stop UI --decision approved --by <user> --note "external <link>, confirmed <date>"`. Never
  assume it: what the user has not called final is reference material.
- `reused` — a prototype confirmed by this harness. Keep its run dir, re-run its design gates, go to
  Phase 3.

---

## 3. Phase flow

A phase ends when its gate exits 0. Phase numbers are the run log's step, named in each brief's
first line (section numbers are stable, so gaps are retired sections); the hook marks each writer
and the panel's coordinator; `baseline` once per run, before its first code writer. Each role's work stays with the agent that started it, across phases
too (`ORCHESTRATOR.md` § Boundaries): where a step below names a role that already worked in this
session, continue that agent; `fe-tester` and reviewers are always new. Writers a step sends out
together each get a worktree of their own (`ORCHESTRATOR.md` § Parallel).

**Phase 0 — Features.** Frontend-only: `be-analyst` → `00-requirements.md`, gate `fe-product`
(cross-stack: the run's `01-requirements.md` stands in, and there is no Phase 0).

**Phase 1 — UX** (`new`). `fe-ux` → `01-ux.md`, gate `fe-ux`; `missing_requirements` go back to the
analyst as one amendment. **UX stop** in two-stop runs: on a canvas surface `fe-ux` draws one grey
low-fidelity wireframe per page in Figma (layout and priority, no visual style), and the stop shows
those frames with the flows as the path between them, never `01-ux.md` to read. One-stop runs and
terminals keep text wireframes: they are a handoff to `fe-ui`, not something the user is asked about.

**Phase 1E — Intake** (`external`). In one message `fe-ux` and `fe-ui` take in the design: what it
shows is pointed at, not rewritten; what it leaves open gets a recommended decision; `fe-ui` exports
the frames. Gates `fe-ux`, `fe-ui`. Then ask, **once and together**, the open decisions that would
change what the prototype shows; the rest take their defaults and go on the Prototype stop's list.

**Phase 2 — UI and queue.**
- `new`: `fe-ui` draws, gate `fe-ui`; in two-stop runs `fe-engineer` scaffolds alongside (the
  confirmed UX is its approved design), gate `fe-build`.
- `fe-engineer` checks feasibility (DFBs for what is costly or does not fit), writes the queue and
  names earlier approved results the round may change (§3I). Gates `fe-queue`, `fe-plan`.
- **UI stop** (`new`): the frames and DFB decisions. Revisions go back to `fe-ui`, with the budget
  left. On yes it exports the frames.

**Phase 2b — Prototype.** `fe-engineer` makes the confirmed design run on the real surface: pages
reachable, the primary flow working, fake data behind one replaceable layer. It is the start of the
product, not throwaway. Gate `fe-build`; start the preview (§3J) and try it yourself.
- **Prototype stop**: the link to the page to try (it opens as is, §3J), `gates/fe-plan-review.md`, the earlier results it may change (§3I),
  and what was decided without the user. Changes → back to the engineer, or a DFB if the design
  changes. On yes: `fe-approve --by <user>` (`--retire` what they let go) and log `--stop Prototype`.
  A Prototype-tier run ends here (`prototype_confirmed`).

**Phase 3 — Build.** Rows go out in groups, by `side`, P1 first. Rows on one page, or naming a
common file, are one group and one dispatch (about a page; split a group one agent could not hold).
The groups go out together in one message, each in a worktree of its own (`ORCHESTRATOR.md`
§ Parallel). Each group brings its pages to the frame at every size and connects real data. Land
each group as it returns, then `fe-build`, without waiting for the others. Report progress (§3J).
A design problem is a DFB, never a silent deviation.

**Phase 4 — Verify and review.**
1. Capture (§3H), then in one message `fe-tester` and the panel (§6).
2. Two or more panelists, or not-done rows: `fe-reviewer` merges candidates and not-done rows into
   `05-review.md`. One panelist and every row done: its brief says it is the sole reviewer; it
   checks its own candidates and returns the review, which you file as `05-review.md`; no
   coordinator runs. Gates `fe-review`, then `fe-verify` (it reruns the tests).
3. Fix only blockers, majors and not-done rows, by their owners; design defects go to `fe-ux`/`fe-ui`.
   Recapture; a new tester and reviewer re-judge only the named defects. At `loops.max_rounds`
   minors are deferred; only blockers, majors and P1 rows escalate (Constitution §5.4).

**Acceptance.** `gate.py demo after`, `fe-accept`, then
lead with the goal, the demo's before and after, and the user running their own check; show
verification, review (drops and deferred), the DFB register and `gates/fe-traceability.md`. On yes `status: accepted` and `fe-promote --by <user>`.

**Phase 5 — After launch.** User or user feedback → `fe-ux` writes `INS-###` entries; the
ones the user picks start the next round as an increment.

## 3A. Design feedback

Any agent may raise a `DFB-###`; you file it in `06-feedback.md` and its owner decides it
(`fe-ux` for flows, pages, states; `fe-ui` for looks). A change to something the user confirmed,
other than by a newer decision of theirs (Constitution §5), needs the user: at once if it blocks, otherwise at the next stop; until then the confirmed design
stands. Smaller details the owner decides and you list. Accepted changes flow forward (UX → frames
→ rows); approved rows change only by re-approval. A new screen or a changed look gets its frame from
`fe-ui` before any code, also mid-build; a DFB the user decides is shown as that frame. Wording-only
changes need no frame.

## 3B. Increments

As backend PLAYBOOK §3B: never restart; the original flow reaches its next stop; there the
increment joins with only its items, in `## Increment <n>` sections with new ids.

## 3C. The frontend/backend line

`~/.claude/route/FRONTEND_BACKEND_LINE.md`. An unwritten line stops the queue.

## 3D. Gates

Run by you, never by the agent checked; reports in `<run-dir>/gates/`. Phase gates are named in
§3. Exit codes and waivers: `ORCHESTRATOR.md`. Authors check their own documents before returning
with `gate.py check <gate>`, which reads only and records nothing.

## 3E. Approved observables

A row's `observable` and its frame export are what the running interface must show. `fe-approve`
locks both at the Prototype stop; changing either afterwards needs the user's re-approval, or a
newer decision that replaces it: re-lock with `fe-approve --by orchestrator --because "<whose
words, date>"` and list it at the next stop.

## 3F. Human stops

**Fixed:** Kickoff; UX and UI (`new`, by design stops); Prototype; Acceptance. Otherwise only a
Constitution §5 case, Phase 1E's one batch, a blocking `needs user` DFB, or the budget. Everything
else is decided with a recommended default and shown at the next stop.

## 3G. Run log

Commands in `ORCHESTRATOR.md`. `fe-accept` checks the trail follows §3's
order: design approved before the prototype, the Prototype stop before the build.

## 3H. Evidence capture

A script produces evidence. Write `capture-plan.json` covering every row, size and state (the gate
checks each combination: a capture's `state` names the row's state word, and `sizes` holds every
`viewports` width):
`surface` (`web` | `terminal` | `manual`); web: `base_url`, `sizes` (one `{name, width, height}` per
`viewports` entry, height `viewport_height`); per capture `id`, `row`, `state`, then `url` + `steps`
+ `styles` (web), `command` + `columns`/`lines` (terminal) or `instrument` + `files` (manual); and
`source`, the globs of the files that make what is captured, so an unrelated edit does not stale it
(globs that match no file fail the plan). `steps` is a list of `{action, …}`: `goto` (`url`), `click`,
`waitFor` (`selector`), `fill` (`selector`, `value`), `press` (`selector`, `key`), `setInputFiles`
(`selector`, `file`), `wait` (`ms`). `styles` is `{selector, properties}`: the computed properties to
record for those elements. A terminal capture may set `timeout` (seconds, default 120) and
`expect_exit` when a non-zero exit is the state being shown. Run
`fe-capture-plan`, start an isolated instance, `capture --round <n>`. A round is never
overwritten. Frame exports (`evidence/design/FRAME-###.png`) come from `fe-ui` once, and are locked.

**Taste measures.** A web capture also records what each page measures (`<capture>.page.json`:
font families, text sizes, corner radii, gradient backgrounds, dialogs open at once). For a
product whose `product_class` is `tool`, `capture` and `fe-verify` print where a page differs from
`taste` in the configuration (`reported, fails nothing: FE4.taste: …`). These lines are leads, not
findings: put them in the experience reviewer's brief, and at Acceptance show the user the ones
the final capture still prints. A project whose brand differs sets its own values in
`.claude/harness.json`.

## 3I. Approved-observable registry

`fe-promote` registers accepted rows as `OBS-###`, each guarded by a tagged test or a capture;
later rounds must keep them (`FE.regression`). What a round may change comes from `fe-plan` and from
`fe-engineer`'s `may_change`; show them as one list with a recommendation, and retire only what the
user lets go or a newer decision replaces (`--because`).

## 3J. Preview and progress

From the prototype on, keep the product running in an isolated instance and give the user its
address. It opens as is: on the run's current code, with seeded data, signed in or with the
credentials given, at the page in question; never a copy that needs setup. After each group passes
`fe-build`, report it as `ORCHESTRATOR.md` § Capabilities says: what changed, the link to that page,
the steps. Not a stop; what the user says becomes a DFB or an increment.

---

## 4. Rules in every phase

1. No phase starts without its upstream artifact.
2. The handoff is `<run-dir>/handoff.md`, one current section per role; the code map is `docs/codemap.md` (`~/.claude/route/HANDOFF.md` §1, §7).
3. Reviewers hold Bash: `fe-review` checks the tree is unchanged outside the run dir and tests.

## 6. Risk and review panel

| | `risk: normal` | `risk: high` |
|---|---|---|
| `fe-review-experience` | always | always |
| `fe-review-accessibility` | diff touches interactive components, forms or navigation | always |
| `fe-review-integration` | diff touches API calls, data loading or client state | always |

`fe-reviewer` coordinates when two or more panelists ran or a row is not done. Say whom you
dispatched and why; a risk change mid-run is a Constitution §5.1 stop.

## 7. Artifacts

```
docs/runs/<slug>/   (cross-stack: the backend PLAYBOOK §7 documents sit beside these)
  00-requirements.md  01-ux.md  02-ui.md  03-queue.md  04-verification.md  05-review.md
  06-feedback.md  state.json  run-log.jsonl  handoff.md  capture-plan.json
  evidence/{design,verify-<n>}/  gates/  logs/
docs/observables.json                    the approved-observable registry (§3I), across runs
contracts/FRONTEND_BACKEND_CONTRACT.md
```

## 8. `state.json`

`~/.claude/route/HANDOFF.md` §8.
