# Frontend Agent Team — Orchestration Playbook

> **Read `~/.claude/CONSTITUTION.md` first. It overrides this file; on conflict, follow it and report the conflict.**
> **Then read `~/.claude/ORCHESTRATOR.md`: how you dispatch, decide, keep context and use gates.**

Harness version: `harness_version` in `~/.claude/frontend/config.json`. This file is *what* the
Frontend team runs and *when*: roles, phases, fixed stops, gate table, evidence, artifacts, state.
*How* the orchestrator works in every phase is `ORCHESTRATOR.md`; this file does not repeat it.
In this team you also capture evidence and export the confirmed frames; you never write flows,
designs, queues, findings or code.

The team follows real frontend work: **product** decides what the product does, **UX** how the
user gets through it, **UI** how it looks and feels, **frontend engineering** makes it run on the
real surface with real data. Work flows forward, and feedback flows back (§3A).

---

## 0. Roles

| Agent | Does | Writes |
|---|---|---|
| `be-analyst` | Product features (`REQ-###`) in a frontend-only run; in a cross-stack run the Backend team's Phase 1 provides them | `00-requirements.md` |
| `fe-ux` | Flows, page structure, navigation, per-page state tables, ASCII wireframes; post-launch insights | `01-ux.md`, `06-feedback.md` |
| `fe-ui` | Design plan and self-check, tokens, components and their states, Figma frames | `02-ui.md`, the Figma file |
| `fe-engineer` | Scaffold, feasibility check, the queue, then one row at a time on the frontend side of the line; fixes | `03-queue.md`, frontend code |
| `fe-tester` | One verdict per row against its frame and state rows; assertions that can fail | `04-verification.md`, test files |
| `fe-review-experience` · `fe-review-accessibility` · `fe-review-integration` | Review panel (§6): candidates in their lens | Nothing; you file their returns |
| `fe-reviewer` | Coordinator: merges, disproves with counter-evidence only, ranks `FND-###`; re-checks fixed FNDs | `05-review.md` |
| Orchestrator | Interviews, evidence capture, frame exports, gates, state, run log | `state.json`, `evidence/` |

- Only you can ask the user. Any agent may raise a design-feedback item (§3A); you route it.
- Queue rows on the other side of the line go to the Backend team's `be-developer`
  (`~/.claude/route/FRONTEND_BACKEND_LINE.md`).

---

## 1. Configuration

1. **Models.** Tier names live in the shared registry `~/.claude/backend/config.json`; this team
   maps its roles one by one in `config.json` `roles`. Judgement → `opus`; carrying out a decided
   conclusion → `sonnet`. Reviewers and `fe-ux` never drop below `opus`.
2. Read `~/.claude/frontend/config.json`; shallow-merge `<project>/.claude/frontend.json` and say so.
3. **Earlier versions.** A `state.json` with `harness_version` below 7.0 is not resumed by this
   PLAYBOOK: report it and offer to start a new round that reads the old artifacts as input.

## 1C. The delivery surface

`delivery_surface` comes from the project context. If it is null, ask at kickoff, record the answer
there, and continue. Never default to a browser.

| Surface | Design medium | A capture is, beyond a picture |
|---|---|---|
| Web page | Figma | DOM of the state plus computed styles for the properties the design commits to |
| Native app | Figma | View hierarchy plus accessibility tree |
| Desktop app | Figma | Window/widget tree plus accessibility API dump |
| Terminal / CLI | Text mockups in `02-ui.md` | Real stdout/stderr bytes plus the terminal size |
| Game / 3D engine | Figma for HUD and menus | UI node tree plus the node properties the design names |
| Other | Named at kickoff | That environment's inspector output, named in the manifest |

A picture alone is never evidence.

## 1D. The named user and priority

- `primary_user_role` is one concrete, named user. If it is null, ask at kickoff.
- **P1**: that user is blocked or will do the wrong thing. **P2**: finishes, but it is hard.
  **P3**: would not notice. Queue rows are built P1 first.

## 1E. Figma budget

- `figma.monthly_budget` (default 300) is the user's own cap across runs; `figma.per_run` estimates
  each run as `base + per_page × pages` (default 20 + 8 per UX page). You propose the run's budget
  at kickoff (from the expected page count) and re-propose it at the UX stop (from `01-ux.md`).
- Every brief to `fe-ui` or `fe-engineer` states the calls left; each returns `figma_calls`, which
  you log with `log return … --figma-calls <n>`. At `figma.warn_at` (80%) of the run budget, say so
  before the next Figma dispatch. Exceeding the budget needs the user's yes, recorded with
  `log human --stop Budget …`. The `FE.figma` check sums the log.
- Before each revision round at the UI stop, tell the user the calls used and left.

---

## 2. Phase 0 — Kickoff (always runs)

**2.1 Understand the ask** in the user's words and its simplest useful version: that is the round.
Everything unnamed goes below the cut line.

**2.2 Recon (≈30 s, read-only).** Surface and stack; a backend run in `docs/backend/` (its
`01-requirements.md` makes this a cross-stack run); existing frontend artifacts and design system;
a confirmed design from a Prototype-tier run (`01-ux.md` and `02-ui.md` with UX and UI stops
approved); the project's Figma file, if any.

**2.3 Confirm the run — one `AskUserQuestion`, mandatory** (skip what `/route` already asked).
First print a preview: the model table from `roles`, the document language (the user's), the
risk evidence, the expected pages and the Figma budget it implies. Then ask:
- **Tier** — Small change / Prototype / Full development (Constitution §7). Prototype here means
  Phases 0–2 up to the UI stop (§3F); Full development reusing a confirmed design is offered first
  when one exists. Small change → `~/.claude/commands/route.md` §4, leaving this PLAYBOOK;
  Prototype and Full development continue here, with `tier` recorded.
- **Model plan** — the `roles` mapping `(Recommended)`; "Other" patches it.
- **Risk** — `high` if the product is public, handles money, personal data or auth, or a legal
  accessibility duty applies; otherwise `normal`. Recommend one, citing the evidence.
- **Design stops** — two (UX, then UI) when the round has 2 or more pages or a new flow; one (UX
  and UI together) for a single page or component (`design_stops` in config). Recommend one.
- **Figma budget** for this run, and, only when null, the delivery surface and the named user.
- **Gate profile** — only while `.claude/gates.json` is unconfirmed.

Taste choices the `design-taste` skill lists (§1: product class, brand colours, motion, copy tone)
are asked here only if `project-context.md` lacks them; record the answers there.

**2.4 Init state.** Write `docs/frontend/state.json` (§8). If one is unfinished, stop and point to
`/frontend-resume`. Record `requirements`: `docs/backend/01-requirements.md` in a cross-stack run,
else `docs/frontend/00-requirements.md`. A reused design: log `log human --stop UX` and
`--stop UI --decision approved --note "reused <paths>, confirmed <date>"`, and start at Phase 2,
step 4 (feasibility and queue).

---

## 3. Phase flow

Serial between phases; fan-outs in one message. **A phase ends only when its gate exits 0 (§3D).**
Phase numbers are the `--step` values in the run log.

**Phase 0 — Product features.** Frontend-only run: `be-analyst` writes `00-requirements.md`
(its "Frontend-only runs" section), gate `fe-product`. Cross-stack run: the Backend team's Phase 1
REQs are the input; this phase is skipped. You ask the blocking questions it returns before Phase 1.

**Phase 1 — UX** → `01-ux.md`. `fe-ux`, alone: flows, page inventory and navigation, a state table
and an ASCII wireframe per page. Gate `fe-ux`. Its `missing_requirements` go back to `be-analyst`
(or the Backend team) as one amendment before the stop.
- **UX stop** (two-stop runs): show the flows, pages and state tables, and the open decisions with
  their recommended defaults. Changes → a fresh `fe-ux`, gate, show again. Then re-propose the Figma budget.

**Phase 2 — UI, scaffold, feasibility, queue.**
1. `baseline --team frontend`.
2. In one message: `fe-ui` (design plan, self-check, tokens, components, frames in the Figma file
   you name) and `fe-engineer` **scaffold** (what does not depend on visuals; files listed in
   `03-queue.md` § Scaffold). Gate `fe-ui` when `fe-ui` returns; `fe-build` when the scaffold returns.
3. Design feedback raised by `fe-ui` against UX is routed per §3A before step 4.
4. `fe-engineer` **feasibility and queue**: reads the frames, raises DFBs for what is costly or does
   not fit, and writes `03-queue.md` and its Dependencies table. DFBs to UI or UX go to a fresh
   owner (§3A); if a frame changes, the queue rows on it are updated by a fresh `fe-engineer`.
   Gate `fe-queue`, then `fe-plan` (writes `gates/plan-review.md`).
- **UI stop** (one-stop runs: the design stop, with `01-ux.md` shown too): the user reviews the
  frames in Figma and the review sheet — pages, frames, DFB decisions, the queue rows' observables,
  and registered observables this round may change. Revisions go to a fresh `fe-ui` (and
  `fe-engineer` for the rows they touch), with the budget reported each round; the user decides
  when it is confirmed. On yes: export every frame (`get_screenshot` → PNG) to
  `evidence/design/FRAME-###.png`, then `fe-approve --by <user>`, which locks the rows' observables
  and the frame exports (§3E). Nothing outside § Scaffold is built before this.

**Phase 3 — Build.** One engineer per row, by `side`: `fe-engineer` or `be-developer`. P1 rows
first; rows sharing a file run serially. `fe-build` after each row. Record each row as done /
blocked / skipped, with the reason. A design problem found while building is a DFB (§3A), never a
silent deviation.

**Phase 4 — Verify and review.**
1. Write `capture-plan.json` (§3H) covering every row, every width in `viewports` and every state
   the rows deliver; `fe-capture-plan`, then `capture --round <n>`.
2. `mark --role fe-reviewer`, then `mark --role fe-tester` (both `--team frontend`), then in one
   message: `fe-tester` (verdicts → `04-verification.md`) and the review panel §6 selects, each
   given the capture round and the isolated instance's address.
3. A fresh `fe-reviewer` **coordinates** the panel's candidates and the tester's not-done rows into
   `05-review.md`. Gates `fe-verify` and `fe-review`.
4. **Fix only blockers and majors and not-done rows**: a fresh dispatch of the owning engineer
   names only those (`ORCHESTRATOR.md`, Handoff); a design defect goes to `fe-ui` or `fe-ux` and
   costs no rework round. Minors are deferred, listed in `05-review.md` § Deferred.
5. Recapture into a new round; a fresh `fe-tester` judges only the reworked rows and a fresh
   `fe-reviewer` **re-checks** only the fixed FNDs. Cap `loops.max_fix_rounds` (default 2), then
   escalate with each survivor's history.

**Acceptance (human).** Show `04-verification.md`, `05-review.md` (findings, drops, deferred), the
DFB register with every decision made without the user, the evidence manifest and
`gates/traceability.md` (REQ → flow → page → row → verdict, written by `fe-accept`). On yes set
`status = "accepted"` and run `fe-promote --by <user>` (§3I).

**Phase 5 — After launch.** When the user brings their own feedback or their users' feedback, a
fresh `fe-ux` writes it into `06-feedback.md` § Post-launch as `INS-###` entries (quote, source,
flow or page hit, suggested change). The user picks which go into the next round; that round is an
increment (§3B) starting at Phase 1 (or Phase 0 if it needs a new feature).

## 3A. Design feedback — work flows back

Any agent may raise a `DFB-###`: `fe-ui` against a flow; `fe-engineer` against a frame (motion too
costly, a layout that does not fit the narrow size) or a flow; `fe-tester` and the panel as
design defects. You append each to `06-feedback.md` § Design feedback and route it:

1. A fresh dispatch of the owner (`fe-ux` for flows, pages, states; `fe-ui` for visuals) decides
   accept or reject with the reason, amending its document if accepted.
2. **Needs the user** when the change alters a flow, page or state the user confirmed, or anything
   visible in a confirmed frame. Ask at once if it blocks work, otherwise at the next fixed stop;
   until then the confirmed design stands.
3. Everything else (a detail inside a confirmed decision, e.g. stacking two fields on the narrow
   size) the owner decides; it is listed at the next stop.
4. Accepted changes flow forward: UX change → UI frames → queue rows, each by a fresh owner; rows
   already approved change only with the user's re-approval (`fe-approve`).
5. The `fe-queue` gate requires every DFB decided before the UI stop; `fe-accept` requires every
   `needs user` DFB to carry the user's decision.

## 3B. Increments — the user adds or changes something mid-run

As the Backend team's §3B: the run is never restarted; the user's words are recorded verbatim in
`state.json` `increments` and a handoff entry; the original flow continues to its next fixed stop
(UX, UI or Acceptance); there the increment starts at Phase 0 or 1 with only its own items, catches
up, and shares the stop. Each agent appends `## Increment <n> — <date>` sections holding only new
or changed items with new ids (`REQ`, `FLOW`, `PAGE`, `FRAME`, `CMP`, `Q`, `DFB`, `FND`); a replaced
item is retired in place (`retired, increment <n>` in its heading). Gates read the whole documents;
`fe-build` and `fe-verify` re-run the registry regression; review covers the increment's diff.

## 3C. The frontend/backend line

`~/.claude/route/FRONTEND_BACKEND_LINE.md`: who builds what, the contract, the seam, fix routing.
An unwritten line stops the queue.

## 3D. Computational gates

`python3 ~/.claude/gates/gate.py <gate> --project <root>`, run by you, never by the agent checked.
Shared with the Backend team: `profile`, and `baseline`, `mark`, `log`, `timeline` with
`--team frontend`. Exit codes, fix routing and waivers: `ORCHESTRATOR.md`, Key information and
Boundaries. Reports: `docs/frontend/gates/`.

| When | Run |
|---|---|
| Before dispatching any agent | `mark --role <agent> --team frontend` (for the panel and coordinator: `--role fe-reviewer` once per review or re-check) |
| After Phase 0 / 1 / 2 (`fe-ui`) | `fe-product` / `fe-ux` / `fe-ui` |
| Phase 2 start | `baseline --team frontend` |
| After the scaffold and each Phase 3 row | `fe-build` |
| After the queue | `fe-queue`, then `fe-plan` (writes `gates/plan-review.md`) |
| After the user confirms the UI and the frames are exported | `fe-approve --by <user>` |
| After writing `capture-plan.json` | `fe-capture-plan`, then `capture --round <n>` |
| After Phase 4 verdicts / coordinator | `fe-verify` / `fe-review` |
| Before the Acceptance stop | `fe-accept` |
| After the user accepts | `fe-promote --by <user>` (`--exclude Q-…` for rows they leave out) |

## 3E. Approved observables

Each queue row's `observable` is the result the running interface must show, and its frame export
is the picture it must match. At the UI stop the user approves both; `fe-approve` hashes each row
(page, frame, states, observable, acceptance) and each export. A row or export changed afterwards
fails `FE.observables` until the user re-approves; nobody edits an approved row to fit the build.

## 3F. Human stops

**Fixed:** Kickoff, UX (two-stop runs), UI, Acceptance. A Prototype-tier run ends at the UI stop.
In a cross-stack run the UI stop is also the Backend team's Prototype stop: log it in both run
logs (`--stop Prototype` in `docs/backend/`).

**Otherwise** only a Constitution §5 case, a `needs user` DFB that blocks work, or the Figma
budget stops the run. Domain facts, ties and wording choices are decided with a recommended default,
labelled in the artifact, and shown together at the next fixed stop. The user's own words are never
changed without asking (Constitution §5.1).

## 3G. Run log

Commands in `ORCHESTRATOR.md`, Key information, with `--team frontend`. `fe-accept` checks the
trail: every dispatch returned; every writer mark was followed by its dispatch; in two-stop runs the
UX approval precedes the first `fe-ui` dispatch; the UI approval precedes the first Phase 3
dispatch; and the Figma calls stay within budget or carry the user's yes.

## 3H. Evidence capture

Evidence is produced by a script, never assembled by hand.

1. **Plan.** Write `docs/frontend/capture-plan.json` from the queue: `surface` (`web` · `terminal` ·
   `manual`), for web `base_url` and every width in `viewports`, and per capture `id`, `row`,
   `state`, then `url` + `steps` + `styles` (web), `command` + `columns`/`lines` (terminal), or
   `instrument` + `files` (manual). `fe-capture-plan` checks every row to verify is covered.
2. **Capture.** Start the product in an isolated instance, then `gate.py capture --round <n>`.
   - web: playwright-core drives the system Chrome; each capture × size yields DOM, computed
     styles, ARIA snapshot and screenshot;
   - terminal: raw stdout/stderr bytes at the stated size;
   - manual (native, desktop, engine): files taken with that surface's inspector, copied and stamped.
   It writes `manifest.json` / `manifest.md` with the instrument, time and a source fingerprint.
   A round is never overwritten: recapture into a new round.
3. **Check.** `fe-verify` (`FE4.capture`) fails if a planned capture or size is missing, failed or
   empty, or if the evidence predates the last `fe-build` or the source changed since capture.
4. **Design exports** (`evidence/design/FRAME-###.png`) are taken once, at the UI stop, and locked.

## 3I. Approved-observable registry

Accepted rows become permanent: `fe-promote` adds each row verified done to
`docs/frontend/observables.json` as `OBS-###`, hashed, with approver and date.

- **Guard.** A row with a passing test tagged `Q-###` is guarded by that test. A row without one
  needs a planned capture, and every later round re-captures and re-judges it (`OBS-###` verdict in
  `04-verification.md`). A row with neither is refused.
- **Every later round.** `fe-build` and `fe-verify` run `FE.regression`: each registered test
  still exists and passes. `fe-capture-plan` requires captures for capture-guarded entries.
- **Change.** `fe-plan` lists registered observables this round's rows may change. The user keeps
  each or retires it at the UI stop (`fe-approve --retire OBS-…`). Nobody else edits the registry.

---

## 4. Rules in every phase

The dispatch cycle, context, briefs and handoff are `ORCHESTRATOR.md`, Capabilities and Handoff.
In this team also:

1. No phase starts without its upstream artifact, present and non-trivial.
2. The handoff log is `docs/frontend/handoff.md`; resume with `/frontend-resume`.
3. A role writes each artifact to disk as it finishes it, so a dead agent costs one file.
4. Reviewers hold Bash: `fe-review` checks the tree is unchanged outside the run dir and test
   files (the tester's, checked by `fe-verify`) while the panel and coordinator ran. Role checks ignore the other team's run dir and fixtures (both teams
   may work in one tree).

## 6. Risk and cost

| | `risk: normal` | `risk: high` |
|---|---|---|
| `fe-review-experience` | always | always |
| `fe-review-accessibility` | if the diff adds or changes interactive components, forms or navigation | always |
| `fe-review-integration` | if the diff touches API calls, data loading or client state | always |
| `fe-reviewer` (coordinator) | whenever a panelist ran | whenever a panelist ran |

- Say which panelists you dispatched and why. A change of risk mid-run is a Constitution §5.1 stop.
- Design stops: §2.3. One page or component → one design stop and the smallest budget.
- A terminal surface has no Figma: the UI stop reviews the text mockups.

## 7. Artifact layout

```
docs/frontend/      (second round: docs/frontend/<slug>/…)
  00-requirements.md (frontend-only)  01-ux.md  02-ui.md  03-queue.md  04-verification.md
  05-review.md  06-feedback.md  state.json  run-log.jsonl  handoff.md  capture-plan.json
  observables.json  evidence/{design,verify-<n>}/  gates/  logs/
contracts/          FRONTEND_BACKEND_CONTRACT.md
prototype/          throwaway prototype (surfaces without a canvas)
```

## 8. `frontend/state.json` schema

```json
{
  "harness_version": "x.y.z",
  "feature": "one line", "slug": "round-slug",
  "started_at": "ISO-8601 from `date -u +%FT%TZ`", "updated_at": "ISO-8601",
  "status": "in_progress | blocked | design_confirmed | building | verifying | accepted | fix_capped",
  "tier": "prototype | full",
  "risk": "normal | high",
  "design_stops": 1,
  "requirements": "docs/frontend/00-requirements.md",
  "design": "new | reused",
  "language": { "docs": "user", "identifiers": "en" },
  "delivery_surface": "…", "primary_user_role": "…",
  "figma": { "file": "https://www.figma.com/design/…", "budget": 60, "raised_by": null },
  "models": { "orchestrator": "opus", "be-analyst": "opus", "fe-ux": "opus", "fe-ui": "opus",
              "fe-engineer": "sonnet", "fe-tester": "sonnet", "fe-reviewer": "opus",
              "fe-review-experience": "opus", "fe-review-accessibility": "opus",
              "fe-review-integration": "opus" },
  "current_phase": 2,
  "phases": [ { "n": 1, "name": "ux", "status": "done", "artifact": "docs/frontend/01-ux.md" } ],
  "stops": { "UX": { "decision": "approved", "date": "…" } },
  "implementation": { "rows": 0, "done": 0, "blocked": 0, "fix_round": 0 },
  "increments": [], "open_questions": [], "notes": []
}
```

Timestamps come from a real `date` call.
