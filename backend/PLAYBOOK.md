# Backend Agent Team — Orchestration Playbook

> **Read `~/.claude/CONSTITUTION.md` first. It overrides this file; on conflict, follow it and report the conflict.**
> **Then read `~/.claude/ORCHESTRATOR.md`: how you dispatch, decide, keep context and use gates.**

Harness version: `harness_version` in `~/.claude/backend/config.json`. This file is *what* the
Backend team runs and *when*: roles, phases, fixed stops, gate table, artifacts, state. *How* the
orchestrator works in every phase is `ORCHESTRATOR.md`; this file does not repeat it. Commands and
agent files are thin loaders.

---

## 0. Roles

| Agent | Role | Owns | Writes code? |
|---|---|---|---|
| `be-analyst` | Requirements Analyst | `01-requirements.md` | No |
| `be-architect` | Architect | `02-architecture.md`, `03-detailed-design.md` | No |
| `be-developer` | Backend Engineer | backend code, `08-implementation-log.md` | Backend only (§3C) |
| `be-tester` | Test Engineer | `04-test-plan.md`, test code, `05-test-report.md` | Tests only |
| `be-reviewer` | Reviewer | `06-review-report.md` | No |
| Orchestrator | Project Manager | `state.json`, `07-acceptance.md` | No |

Interface work is built by the Frontend team (`fe-designer`, `fe-critic`, `fe-engineer`,
`fe-tester`), dispatched by you under §3C.

---

## 1. Configuration resolution

1. Read `~/.claude/backend/config.json`.
2. If `<project>/.claude/backend.json` exists, shallow-merge it (top-level keys replace) and say so.
3. Gates, lenses, loop caps and artifact dir come from the merged config, never from memory.
4. **Legacy paths.** If `docs/backend/` is absent but `docs/waterfall/` exists, use the legacy dir
   for the whole run and say so; same for `.claude/waterfall.json`. Never move a legacy dir yourself.

## 1A. Project context vs. harness

See `ORCHESTRATOR.md`, Boundaries.

---

## 2. Phase 0 — Kickoff (always runs)

**2.0 Tier — first, alone.** Unless `/route` already asked it: one `AskUserQuestion`, Small change
/ Prototype / Full development (Constitution §7). Small change → `~/.claude/commands/route.md` §4;
Prototype → `~/.claude/route/PROTOTYPE.md`; either way leave this PLAYBOOK. Full development →
continue, with `tier: "full"` in `state.json`.

**2.1 Understand the ask.** Read any file it names. Empty request → ask what to build.

**2.1a Cut line.** Write the ask in the user's words, then its simplest useful version: that is
the round. Everything unnamed (variants, legacy data, concurrency, migrations, non-functional axes)
goes below the line into `NN-deferred.md`. Put the cut line in the analyst's dispatch. Round size
is proportional to the ask; an obviously incomplete but working first version is the goal.

**2.2 Recon (≈30 s, read-only).** Stack, build/test commands, git or not, prior run in
`docs/backend/`. If the product calls an LLM at runtime, benchmark candidate models on a
production-shaped prompt before build and record the numbers (reasoning models share
`max_tokens` between reasoning and answer). If `<project>/.claude/gates.json` is missing, run
`gate.py profile` (§3D).

**2.3 Confirm the run plan — mandatory.** Print a preview table whose Model column you fill by
reading `config.model_plan.tiers[_active_tier]` now (add `fe-*` roles if the round touches the
interface). Then `AskUserQuestion` with these questions:
- **Model plan** — each tier, active one first `(Recommended)`, each description listing the full
  per-role mapping read from config. "Other" = a patch on the chosen tier.
- **Document language** — `English (default)` / `中文` / `中文 docs + English code`. Code,
  identifiers, filenames and commits stay English.
- **Gate profile** — only while `.claude/gates.json` is unconfirmed: show the detected commands;
  on approval set `confirmed: true` and `confirmed_on`.

**2.4 Init state.** Create the artifact dir and `state.json` (§8). If a `state.json` with
`status != "accepted"` exists, stop and point to `/backend-resume`.

**2.5 Apply the model plan** on every dispatch (`ORCHESTRATOR.md`, Capabilities).

---

## 3. Phase flow

Serial between phases; fan-outs inside a phase go in one message. **A phase ends only when its
gate exits 0 (§3D).**

**Phase 1 — Requirements** → `be-analyst`. It writes §0 Understanding first, takes the recommended
default for every open question, labels it, and finishes; you ask the questions together with the
Phase 1b intent questions, and `be-analyst` amends what the answers change. It also picks real fixture inputs (§3E).

**Phase 1b — Prototype** (`~/.claude/route/PROTOTYPE.md`) → intent questions, then one engineer
builds a rough, runnable version in `prototype/`; the user confirms it (fixed stop, §3F). If the
confirmation changed scope, `be-analyst` amends `01-requirements.md` and `p1` runs again. Nothing
in Phase 3 starts before the confirmation (Constitution §2.7).

**Phase 2 — Architecture** → `be-architect`. If `parallelism.architecture_critique`: one
`be-reviewer` per `architecture_critique_lenses`, each arguing against the design; then one
revision pass by the architect. New dependencies, schema changes and genuine ties are
decided with a recommendation, logged, and shown at the Plan stop (§3F); the phase continues.

**Phase 3 — Detailed design** → `be-architect`. Every `DES-###` names its `REQ-###` and a
`side` (§3C.3). No gate.

**Phase 3b — Fixtures** (§3E) → `be-tester` drafts expected outputs.

**Plan (human).** Run `plan`; show the user `<run-dir>/gates/plan-review.md` (requirements,
non-goals, decisions, dependencies, fixtures) and any open critique items. Stop for approval; on
yes run `fixtures-approve --by <user>` if there are fixtures. Nothing is built before this.

**Phase 4 — Build**, in one message:
- `be-developer` builds the `side: backend` items only.
- `be-tester` writes `04-test-plan.md` from requirements and design only, never the code.
- `side: frontend` items go to the Frontend team (§3C.4) once their seam's backend half exists.
- A design reported unimplementable goes back to `be-architect` for an amendment; the developer
  never improvises.

**Phase 5 — Verification** → `be-tester` runs every `TC-###` and records real output; frontend
items are verified by `fe-tester` (§3C.5). Failures go to the owning engineer (§3C.6) through the
`p5` loop (§3D), each round a fresh engineer and a fresh `be-tester` (`ORCHESTRATOR.md`, Handoff). Never relax a test.

**Phase 6 — Review.** One `be-reviewer` per `review_lenses`, plus, if
`parallelism.traceability_audit`, a `traceability` lens that judges only whether each TC really
verifies its REQ (the id matrix is the gates' job), all in one message. Merge into `06-review-report.md`:
de-duplicate, rank `FND-###` blocker/major/minor, drop findings without a failure scenario.
Blockers and majors go to the owning engineer as a fresh dispatch naming only those `FND-###`
(`ORCHESTRATOR.md`, Handoff), then Phase 5 again with a fresh `be-tester` that re-runs the affected TCs. Cap
`loops.max_fix_rounds_after_review`, then escalate.

**Phase 7 — Acceptance (human).** You write `07-acceptance.md` per the Phase 7 bar. Stop for
acceptance; on yes set `status = "accepted"`.

---

## 3A. Orchestrator discipline

In `ORCHESTRATOR.md`, Key information, for every team.

## 3B. Re-baseline — the brief changes mid-run

1. Stop the phase in flight.
2. Restate the change in the user's terms; get it confirmed.
3. Re-enter at Phase 1.
4. Retire `REQ-###`, never delete; never reuse ids.
5. Verify each scope cut is absent in code, not only in prose.
6. Recompute every count and restate its composition.
7. Record in `state.json`: what changed, artifacts reissued, gates re-taken.

## 3C. The frontend/backend line

`be-developer` writes backend code only, whether or not the Frontend team was dispatched.

**3C.1 Default line** (a line the project wrote, named and dated, in
`<project>/.claude/project-context.md` or `team/frontend-team-config.md`, overrides it):

| Side | Covers | Built by |
|---|---|---|
| backend | schema and migrations, business logic, APIs, queries, CLI args, script entry points, jobs | `be-developer` |
| frontend | human-operated GUI/TUI: templates, styles, client scripts, display-only fields | `fe-engineer` (design `fe-designer`) |

**3C.2 When the line must be written.** Only if the round touches the interface. Then, if
unwritten, ask at the next fixed stop (§3F) and have the user sign one; offer 3C.1 as the draft.

**3C.3 Design.** Every `DES-###` has `side: backend | frontend`. A frontend item specifies only
the seam (name, type, nullable, who computes, endpoint/field) in
`contracts/FRONTEND_BACKEND_CONTRACT.md`. Two-sided items split into two `DES` sharing one entry.

**3C.4 Build.** Follow `~/.claude/frontend/PLAYBOOK.md` §1C and Phases 6–8 and its QUALITY-BARS:
`fe-designer` for items needing design decisions → you write `docs/frontend/05-queue.md` → `fe-critic`
grades each row P1–P3 → the rows' `observable`s are shown at the Plan stop → `fe-engineer` per row.
`fe-*` models come from `~/.claude/frontend/config.json` `roles`. Frontend artifacts stay in the
Frontend dirs; record in `state.json` which `DES` went to the Frontend team.

**3C.5 Verify.** You capture evidence on the running surface; `fe-tester` judges it.
`be-tester` tests each seam from the backend side.

**3C.6 Fix routing.** A defect goes to the side where it is: data → `be-developer`, screen →
`fe-engineer`, design → `be-architect` / `fe-designer`. Never route interface work to
`be-developer` for speed.

**3C.7** Every item in `be-developer`'s `frontend_items` gets a `DES` and a queue row, or is moved
to `NN-deferred.md`.

## 3D. Computational gates

`python3 ~/.claude/gates/gate.py <gate> --project <root>` (`--run-dir` for a feature slug). You run
it, never the agent whose work it checks. Exit `0` pass · `1` fail · `3` fix-round cap reached ·
`2` configuration error. Reports: `<run-dir>/gates/`.

| When | Run |
|---|---|
| First run in a project | `profile`, then user confirms `.claude/gates.json` (§2.3) |
| After Phase 1 / 2 / 3 | `p1` / `p2` / `p3` |
| Phase 1b | no gate; log its dispatch with `--step 1b` and the `Prototype` stop (`LOG.trail` checks the order) |
| After Phase 3b, before the Plan stop | `plan` |
| After the user approves the Plan | `fixtures-approve --by <user>` |
| Phase 4 start | `baseline` |
| Before dispatching any writing agent | `mark --role <agent>` |
| Before / after every dispatch | `log dispatch …` / `log return …` (`ORCHESTRATOR.md`, Key information) |
| After Phase 4 / Phase 5 | `p4` / `p5` |
| Before the review fan-out | `mark --role be-reviewer` |
| After compiling `06-review-report.md` | `p6` |
| After writing `07-acceptance.md`, before the Acceptance stop | `p7` |

Exit codes, fix routing, waivers and the rule never to edit a gate: `ORCHESTRATOR.md`, Key information and Boundaries. After
any code change, re-run `p4` then `p5`.

## 3E. Approved fixtures

Human-confirmed input/output pairs that every later test must match.

1. **Declare (Phase 1).** Each active REQ with observable output names its fixtures
   (`**Fixtures:** FX-001`) or says why not (`**Fixtures:** n/a — <reason>`). `be-analyst` puts each
   real input in `<candidates>/FX-nnn/input.*` with `meta.json` (`req`, `source`), redacting
   sensitive data. Aim for 1–3 per REQ, about 10 per round.
2. **Draft (Phase 3b).** `be-tester` writes `expected.*` from requirements and design only, never
   from code; to preserve existing behaviour, it captures the current output instead and says so in
   `source`. It sets `compare` (`exact` by default).
3. **Approve (Plan).** The Plan review sheet lists every fixture; the user approves, edits or
   rejects each. On approval run `fixtures-approve --by <user>`; it hashes
   and locks them in `<fixtures_dir>/APPROVED.json`. Nothing is locked without the user's yes.
4. **Use (Phases 4–5).** Tests load the approved files and are tagged `FX-nnn`. No agent edits an
   approved fixture; `P4/P5.fixtures` and `P5.fixtures-used` enforce it.
5. **Wrong answer found later.** Stop (Constitution §2.5), show the user the old and proposed
   output, and lock the new answer with `--reapprove FX-nnn` once they approve. History is kept.
6. Fixtures live in the project, not the run, so they accumulate into a regression suite.

## 3F. Human stops

**Fixed:** Prototype (before detailed design, Constitution §2.7), Plan (before any product code)
and Acceptance (Constitution §6.7).

**Otherwise** only a Constitution §5 case stops the run (`ORCHESTRATOR.md`, Decisions). Ambiguities, domain
facts, ties, new dependencies and schema changes are decided with a recommended default, labelled
as assumptions or decisions in the artifact, and shown together at the next fixed stop; the Plan
stop comes before any product code, so a wrong default costs no build.

## 3G. Run log

Commands in `ORCHESTRATOR.md`, Key information. `P7` requires every dispatch to have returned, every mark to be
followed by its dispatch, the Plan approval to precede the first `be-developer` dispatch outside
Phase 1b, and (`tier: "full"`) the Prototype approval to precede the first Phase 3 dispatch.

---

## 4. Rules in every phase

The dispatch cycle, context, briefs and handoff are `ORCHESTRATOR.md`, Capabilities and Handoff. In this team also:

1. No phase starts without its upstream document (`policy.block_phase_on_missing_upstream_doc`).
2. The handoff log is `<run-dir>/handoff.md`; resume with `/backend-resume`.
3. Traceability ids are mandatory; send an id-less document back once.
4. `be-reviewer` has no Write/Edit but has Bash, so run `gate.py mark --role be-reviewer` before the
   fan-out; `p6` verifies the tree is unchanged. Mutations belong in a throwaway tree.

## 5. Escalation

`ORCHESTRATOR.md`, Decisions. A design reported unimplementable goes to `be-architect` for an amendment
as a logged decision; it stops the run only if the amendment changes scope (Constitution §5.1).

## 6. Cost discipline

- Diff under ~200 lines: run only `correctness` + traceability, plus `operator-experience` if the
  change touches anything the user sees or operates. Say so.

## 7. Artifact layout

```
<project>/docs/backend/            (second feature: docs/backend/<slug>/…)
  state.json  01-requirements.md  01b-prototype.md  02-architecture.md  03-detailed-design.md
  04-test-plan.md  05-test-report.md  06-review-report.md  07-acceptance.md
  08-implementation-log.md  NN-deferred.md  handoff.md  logs/
<project>/prototype/               throwaway prototype from Phase 1b
```

## 8. `state.json` schema

```json
{
  "harness_version": "x.y.z",
  "feature": "one line", "slug": "feature-slug",
  "started_at": "ISO-8601 from `date -u +%FT%TZ`", "updated_at": "ISO-8601",
  "status": "in_progress | blocked | accepted",
  "tier": "full",
  "language": { "docs": "en", "code": "en" },
  "models": { "orchestrator": "…", "be-analyst": "…", "be-architect": "…",
              "be-developer": "…", "be-tester": "…", "be-reviewer": "…" },
  "current_phase": 4,
  "phases": [ { "n": 1, "name": "requirements", "status": "done",
                "artifact": "docs/backend/01-requirements.md",
                "gate": { "id": "Plan", "decision": "approved", "note": "" } } ],
  "frontend_items": [ { "des": "DES-021", "queue_row": "Q-3", "status": "verified" } ],
  "gates": { "p1": { "overall": "pass", "time": "ISO-8601" } },
  "loops": { "review_rounds": 0 },
  "open_questions": [], "notes": []
}
```

Timestamps come from a real `date` call.
