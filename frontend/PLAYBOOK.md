# Frontend Agent Team — Orchestration Playbook

> **Read `~/.claude/CONSTITUTION.md` first. It overrides this file; on conflict, follow it and report the conflict.**

Harness version: `harness_version` in `~/.claude/frontend/config.json`. This file is the single
source of truth for how the team runs; the command and agent files are thin loaders.

You are the **Orchestrator**. You interview the user, capture evidence, write the queue, run the
gates, enforce the stops, keep state and report. You never write briefs, specs, findings or code yourself.

---

## 0. Roles

| Agent | Does | Writes |
|---|---|---|
| `fe-critic` | Findings, their side (frontend / backend / cross-stack) and priority; capability rulings | Nothing (no Write/Edit); you file its text |
| `fe-designer` | Structure, then specification and the contract draft | Frontend artifact dirs only |
| `fe-engineer` | Frontend code on its side of the project's line | Production frontend code |
| `fe-tester` | Assertions that can fail; verdicts on captured evidence | Test files only |
| Orchestrator | Interview, evidence capture, queue, gates, state, run log | `state.json`, `05-queue.md`, `evidence/` |

- Only you can ask the user or drive the running product; no subagent has a tool for either.
- Queue rows on the other side of the line go to the Backend team's `be-developer`.

---

## 1. Configuration

1. **Models.** Tier names live in the shared registry `~/.claude/backend/config.json`; this
   team maps its roles one by one in `config.json` `roles`. Judgement → `opus`; carrying out a
   decided conclusion → `sonnet`. `fe-critic` never drops below `opus`. One role registry only.
2. Read `~/.claude/frontend/config.json`; shallow-merge `<project>/.claude/frontend.json` and say so.
3. **Legacy names.** When the new name is absent, read the old one and say so: `docs/uiux/`, `uiux/`,
   `.claude/uiux.json`, `team/*-team-config.md`, and the pre-5.0 artifacts (`FRONTEND_BRIEF.md`,
   `UX_AUDIT.md`, `PAGE_SPEC.md`, `IMPLEMENTATION_QUEUE.md`, `VERIFICATION_REPORT.md`, …). Never
   rename a project's files yourself.

## 1A. Project context vs. harness

- Read `<project>/.claude/project-context.md` at kickoff if it exists, and say so. The user writes it.
- A preference for **this project** goes there. A rule enters this harness only after it held on
  more than one unrelated project.

## 1C. The delivery surface

`delivery_surface` comes from the project context. If it is null, ask once at kickoff, record the
answer there, and continue. Never default to a browser.

| Surface | A capture is, beyond a picture |
|---|---|
| Web page | DOM of the state plus computed styles for the properties the spec commits to |
| Native app | View hierarchy plus accessibility tree |
| Desktop app | Window/widget tree plus accessibility API dump |
| Terminal / CLI | Real stdout/stderr bytes plus the terminal size |
| Game / 3D engine | UI node tree plus the node properties the spec names |
| Other | That environment's inspector output, named in the manifest |

A picture alone is never evidence.

## 1D. The named user and priority

- `primary_user_role` is one concrete, named user. If it is null, ask at kickoff. Without it
  nothing can be graded, and an ungraded finding is not received.
- **P1**: that user is blocked or will do the wrong thing. **P2**: finishes, but it is hard.
  **P3**: would not notice. P1s are cleared before P2s, P2s before P3s.

---

## 2. Phase 0 — Kickoff (always runs)

**2.0 Tier — first, alone.** Unless `/route` already asked it: one `AskUserQuestion`, Small change
/ Prototype / Full development (Constitution §7). Small change → `~/.claude/commands/route.md` §4;
Prototype → `~/.claude/route/PROTOTYPE.md`; either way leave this PLAYBOOK. Full development →
continue, with `tier: "full"` in `state.json`.

**2.1 Mode.** Ambiguous → ask; never guess.

| Mode | Runs |
|---|---|
| `new` | 1 → 1b → 3 → 4 → 5 → **Plan** (design approval) |
| `redesign` | 1 → 2 → 1b → 3 → 4 → 5 → **Plan** |
| `audit` | 1 → 2, then report |
| `review` | 5 on existing artifacts, then report |
| `implement` | 6 → **Plan** → 7 → 8 → **Acceptance** (needs an approved design) |
| `status` | Read-only report; no agents |

**2.2 Recon (≈30 s, read-only).** Surface and stack, a backend run in `docs/backend/`, existing
frontend artifacts, captures or URLs supplied.

**2.3 Cut line.** Write the ask in the user's words and its simplest useful version. Everything
unnamed goes below the line in `01-brief.md`. Round size is proportional to the ask.

**2.4 Confirm the run plan — mandatory.** `AskUserQuestion`: model plan (the `roles` mapping,
naming the `fe-critic` floor), document language, and — only when null — the delivery surface
and the named user. In `new` and `redesign`, also ask the product-dependent taste choices the
`design-taste` skill lists (§1: product class, brand colours, motion, copy tone) unless
`project-context.md` already records them; record the answers there. No agent starts before this
is answered.

**2.5 Init state.** Write `docs/frontend/state.json` (§8). If one is unfinished, stop and point to
`/frontend-resume`. If `<project>/.claude/gates.json` is missing, run `gate.py profile` and
confirm it with the user in 2.4.

---

## 3. Phase flow

Serial between phases; fan-outs in one message. **A phase ends only when its gate exits 0 (§3D).**

**Phase 1 — Discovery** → `01-brief.md`. `fe-critic` returns §0 Understanding, the named user and
tasks, scope and cut line, non-goals, assumptions (`[confirmed]` / `[unconfirmed]`) and open
questions, each with what its answer would change. You file it. Questions that change what gets
built are a conditional stop (§3F): ask the fewest that branch the design, at most
`loops.max_interview_rounds_before_gate` rounds.

**Phase 1b — Prototype** (`new`, `redesign`; `~/.claude/route/PROTOTYPE.md`) → intent questions,
then one `fe-engineer` builds a rough, runnable page sketch in `prototype/`; the user confirms it
(fixed stop, §3F). If the confirmation changed scope, `fe-critic` amends `01-brief.md`. Phase 3
starts only after the confirmation (Constitution §2.7). In a cross-stack run the Backend team's
Phase 1b covers it; do not build a second prototype, but log the same `Prototype` stop here.

**Phase 2 — Audit** (brownfield) → `04-findings.md`. First capture evidence yourself (§1C) into
`docs/frontend/evidence/` with a manifest (file · state shown · instrument). Then one `fe-critic` per
`parallelism.audit_lenses`. Say which states were captured from the running product and which
were only read from code.

**Phase 3 — Structure** → `02-structure.md`. `fe-designer`, dispatched alone. Read it before
Phase 4; structure precedes every visual decision.

**Phase 4 — Specification** → `03-spec.md` and `contracts/FRONTEND_BACKEND_CONTRACT.md`.
`fe-designer` writes both. In parallel, `fe-critic` rules every capability the draft relies on:
side (frontend / backend / cross-stack) and `verified` (with source) / `unverified` / `new`,
checking the backend before calling anything cross-stack. Unverified and new capabilities go into
the contract's open items with an owner. Never invent backend capability.

**Phase 5 — Review** → `04-findings.md`. One `fe-critic` per `parallelism.review_lenses`, then,
if `parallelism.final_critic_pass`, one pass that reconciles priorities the lenses disagree on.
Blockers and P1s go back to `fe-designer`. Cap `loops.max_revision_rounds_after_review`.

| Lens | Asks |
|---|---|
| `ux-flow` | Can the named user finish the task, at what cost in decisions and clicks? |
| `design-system` | Hierarchy, component consistency, token use, adaptation |
| `accessibility-and-content` | Keyboard, focus, contrast, semantics, forms, error text, copy, i18n |
| `contract-and-feasibility` | Undefined data/API/permission, missing states, contract conflicts |

**Plan (human).** Design modes: show the brief's scope, the page inventory, key spec decisions,
open P1 findings and open contract items; approval accepts the design (conditional if a blocker
or a blocking contract item is open). `implement`: show `05-queue.md`; each row's `observable` is
the answer the running interface must match — the frontend's approved fixtures, locked by
`fe-approve` (§3E). Nothing is built before this.

**Phase 6 — Queue** → `05-queue.md`, written by you from the spec and findings. `fe-critic`
grades every row P1–P3; an ungraded row is not dispatched. One row per design problem, split
until each is independently buildable and observable. A row blocked on an open question is
listed as blocked, with the question and its owner.

**Phase 7 — Build.** One engineer per row, by `side`: `fe-engineer` or `be-developer`. P1 rows
first; rows sharing a file run serially. You, `fe-critic` and `fe-designer` never write code.
Record each row as done / blocked / skipped, with the reason.

**Phase 8 — Verify** → `06-verification.md`. You capture every touched screen, at every size the
spec commits to, in the states that need real data, with `gate.py capture` (§3H) into
`docs/frontend/evidence/verify-<round>/`. `fe-tester` gives each row exactly one verdict: **done** · **not done** ·
**not observable** (never counted as done: recapture, or fix the row). Not done → the row's
engineer, then verify again, capped at `loops.max_rework_rounds_after_verification`, then
escalate with each survivor's history and whether the spec is unbuildable or a capability is
missing. When the running interface contradicts the spec, the spec may be the defect: route it to
`fe-designer`; that costs no rework round.

**Acceptance (human).** Show `06-verification.md`, the evidence manifest and `gates/traceability.md`
(task → page → row → verdict, written by `fe-accept`); on yes set `status = "verified"` and run
`fe-promote --by <user>` (§3I).

## 3D. Computational gates

`python3 ~/.claude/gates/gate.py <gate> --project <root>`, run by you, never by the agent checked.
Shared with the Backend team: `profile`, and `baseline`, `mark`, `log`, `timeline` with
`--team frontend`. Exit 0 pass · 1 fail (send to `fail_by_owner`, `mark`, re-dispatch, re-run) ·
3 fix-round cap (escalate) · 2 config error. Reports: `docs/frontend/gates/`.

| When | Run |
|---|---|
| After Phase 1 / 3 / 4 / 2 or 5 / 6 | `fe-brief` / `fe-structure` / `fe-spec` / `fe-findings` / `fe-queue` |
| Before the Plan stop | `fe-plan` (writes `gates/plan-review.md`) |
| After the user approves a queue | `fe-approve --by <user>` |
| Phase 7 start | `baseline --team frontend` |
| Before dispatching any agent | `mark --role <agent> --team frontend` |
| After each Phase 7 row | `fe-build` |
| After writing `capture-plan.json` | `fe-capture-plan`, then `capture --round <n>` |
| After Phase 8 | `fe-verify` |
| Before the Acceptance stop | `fe-accept` |
| After the user accepts | `fe-promote --by <user>` (`--exclude Q-…` for rows they leave out) |

Never edit a gate, its config or its reports to get green; waivers are the user's alone
(`gates/waivers.json`).

## 3E. Approved observables

Each queue row's `observable` is the result the running interface must show. At the Plan stop the
user approves them; `fe-approve` hashes each row's spec, observable and acceptance. A row changed
afterwards fails `FE.observables` until the user re-approves; nobody edits an approved row to fit
the build.

## 3F. Human stops

**Fixed:** Prototype (in `new` and `redesign`, before Phase 3), Plan, and Acceptance in `implement`. **Conditional**, batched per phase in one
`AskUserQuestion` with a recommendation each:

- a Constitution §5 case;
- a domain fact only the user knows;
- changing words the user wrote;
- a genuine tie: no numbered invariant, decision or measurement on disk derives the answer;
- a contract capability the backend team cannot confirm.

Anything else is ruled and logged as a `decision` (who ruled, the derivation, what would
overturn it). An agent's ruling is never recorded as the user's.

## 3G. Run log

Same as the Backend team (backend PLAYBOOK §3G), with `--team frontend`: log every dispatch and
return, every human stop and every agent's own ruling. `fe-accept` checks the trail, including that
the Plan approval precedes the first `fe-engineer` dispatch outside Phase 1b, and (`tier: "full"`)
that the Prototype approval precedes the first Phase 3 dispatch.

## 3H. Evidence capture

Evidence is produced by a script, never assembled by hand.

1. **Plan.** Write `docs/frontend/capture-plan.json` from the queue: `surface` (`web` · `terminal` ·
   `manual`), for web `base_url` and every size the spec commits to, and per capture `id`, `row`,
   `state`, then `url` + `steps` + `styles` (web), `command` + `columns`/`lines` (terminal), or
   `instrument` + `files` (manual). `fe-capture-plan` checks every row to verify is covered.
2. **Capture.** Start the product in an isolated instance, then `gate.py capture --round <n>`.
   - web: playwright-core drives the system Chrome; each capture × size yields DOM, computed
     styles, ARIA snapshot and screenshot;
   - terminal: raw stdout/stderr bytes at the stated size;
   - manual (native, desktop, engine): files taken with that surface's inspector, copied and stamped.
   It writes `manifest.json` / `manifest.md` with the instrument, time and a source fingerprint.
   A round is never overwritten: recapture into a new round.
3. **Check.** `fe-verify` (`FE8.capture`) fails if a planned capture or size is missing, failed or
   empty, or if the evidence predates the last `fe-build` or the source changed since capture.

## 3I. Approved-observable registry

Accepted rows become permanent: `fe-promote` adds each row verified done to
`docs/frontend/observables.json` as `OBS-###`, hashed, with approver and date.

- **Guard.** A row with a passing test tagged `Q-###` is guarded by that test (file and name are
  recorded). A row without one needs a planned capture, and every later round re-captures and
  re-judges it (`OBS-###` verdict in `06-verification.md`). A row with neither is refused.
- **Every later round.** `fe-build` and `fe-verify` run `FE.regression`: each registered test still
  exists and passes. `fe-capture-plan` requires captures for capture-guarded entries.
- **Change.** `fe-plan` lists registered observables this round's rows may change. The user keeps
  each or retires it at the Plan stop (`fe-approve --retire OBS-…`). Nobody else edits the registry.

---

## 4. Rules in every phase

1. No phase starts without its upstream artifact, present and non-trivial.
2. Give agents file paths, not pasted content; they return compact summaries.
3. A role writes each artifact to disk as it finishes it, so a dead agent costs one file. On a
   death, check the filesystem, then resume the same agent and name the files that exist.
4. Report to the user after every phase: what was produced, verdict, models used, next step.
5. Update `docs/frontend/state.json` after every phase transition and human stop.
6. Never fabricate research, evidence or a user quote.
7. Dispatch the real `fe-*` type; if one is missing, stop and ask for a restart. `fe-critic`
   holds Bash, and `fe-designer` / `fe-tester` are confined by their dispatch: check the tree is
   unchanged, or changed only in their named directory, when they return.

## 5. Orchestrator discipline

1. Verify a count before relaying it.
2. Before asserting a screen lacks something, print what it rendered.
3. Exercise the real product yourself before believing a report.
4. Relay disagreement with both sides' evidence.
5. A returned agent has stopped; never write an intention in the past tense.
6. Look at a file before overwriting or deleting it.

## 6. Cost discipline

- Name the model used per phase.
- One page or component: run `ux-flow` and `contract-and-feasibility` only, plus
  `accessibility-and-content` when forms, errors or empty states change. Say that you narrowed it.
- Small later changes get a targeted amendment, not a re-run.

## 7. Artifact layout

```
docs/frontend/      (second round: docs/frontend/<slug>/…)
  01-brief.md  01b-prototype.md  02-structure.md  03-spec.md  04-findings.md
  05-queue.md  06-verification.md  state.json  run-log.jsonl  evidence/  gates/
contracts/          FRONTEND_BACKEND_CONTRACT.md
prototype/          throwaway prototype from Phase 1b
```

## 8. `frontend/state.json` schema

```json
{
  "harness_version": "x.y.z",
  "mode": "new | redesign | audit | review | implement",
  "feature": "one line", "slug": "round-slug",
  "started_at": "ISO-8601 from `date -u +%FT%TZ`", "updated_at": "ISO-8601",
  "status": "in_progress | blocked | design_approved | conditional | implementing | verified | rework_capped",
  "tier": "full",
  "language": { "docs": "en", "identifiers": "en" },
  "delivery_surface": "…", "primary_user_role": "…",
  "models": { "orchestrator": "opus", "fe-critic": "opus", "fe-designer": "opus",
              "fe-engineer": "sonnet", "fe-tester": "sonnet" },
  "current_phase": 4,
  "phases": [ { "n": 1, "name": "discovery", "status": "done", "artifact": "docs/frontend/01-brief.md" } ],
  "stops": { "Plan": { "decision": "approved", "date": "…" } },
  "implementation": { "rows": 0, "done": 0, "blocked": 0, "verification_round": 0 },
  "loops": { "interview_rounds": 0, "revision_rounds": 0, "rework_rounds": 0 },
  "open_questions": [], "notes": []
}
```

Timestamps come from a real `date` call.
