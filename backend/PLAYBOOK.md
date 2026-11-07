# Backend Agent Team — Orchestration Playbook

> **Read `~/.claude/CONSTITUTION.md` first. It overrides this file; on conflict, follow it and report the conflict.**
> **Then read `~/.claude/ORCHESTRATOR.md`: how you dispatch, decide, keep context and use gates.**

What the Backend team runs and when, in Full development: roles, phases, stops, gates, artifacts,
state. The orchestrator reads it at kickoff and on resume. Version: `harness_version` in
`~/.claude/backend/config.json`.

---

## 0. Roles

| Agent | Role | Owns | Writes code? |
|---|---|---|---|
| `be-analyst` | Requirements Analyst | `01-requirements.md`, fixture candidates | No |
| `be-architect` | Architect | `02-architecture.md`, `03-detailed-design.md` | No |
| `be-developer` | Backend Engineer | backend code, `08-implementation-log.md` | Backend only (§3C) |
| `be-tester` | Test Engineer | `04-test-plan.md`, test code, `05-test-report.md` | Tests only |
| `be-review-behavior` | Panelist: Behaviors & Contracts | its findings (returned, read-only) | No |
| `be-review-reliability` | Panelist: Reliability & Operations | its findings (returned, read-only) | No |
| `be-review-security` | Panelist: Security & Trust boundaries | its findings (returned, read-only) | No |
| `be-reviewer` | Review Coordinator | merged `06-review-report.md` (returned, read-only) | No |
| Orchestrator | Project Manager | `state.json`, `07-acceptance.md`, `deferred.md`, filing read-only roles' text | No |

Interface work is designed and built by the Frontend team (`fe-ux`, `fe-ui`, `fe-engineer`,
`fe-tester`, its review panel), dispatched by you under §3C.

---

## 1. Configuration resolution

1. Read `~/.claude/backend/config.json`.
2. If `<project>/.claude/backend.json` exists, shallow-merge it (top-level keys replace) and say so.
3. Gates, panels, loop caps and artifact dir come from the merged config, never from memory.
4. **Legacy paths.** If `docs/backend/` is absent but `docs/waterfall/` exists, use the legacy dir
   for the whole run and say so; same for `.claude/waterfall.json`. Never move a legacy dir yourself.

---

## 2. Phase 0 — Kickoff (always runs)

**2.1 Understand the ask.** Read any file it names. Empty request → ask what to build.

**2.1a Cut line.** Write the ask in the user's words, then its simplest useful version: that is
the round. Everything unnamed (variants, legacy data, concurrency, migrations, non-functional axes)
goes below the line into `deferred.md`. Put the cut line in the analyst's dispatch.

**2.2 Recon (≈30 s, read-only).** Stack, build/test commands, git or not, prior run in
`docs/backend/`, a confirmed prototype (`<run-dir>/01b-prototype.md`). If the product calls an LLM
at runtime, benchmark candidate models on a production-shaped prompt before build and record the
numbers. If `<project>/.claude/gates.json` is missing, run `gate.py profile` (§3D).

**2.3 Confirm the run — one `AskUserQuestion`, mandatory** (skip the questions `/route` already
asked). First print a preview: the model table read from `config.model_plan.tiers[_active_tier]`
(add `fe-*` roles if the round touches the interface), the document language and the risk with
its evidence; these stand unless the user changes them. Then ask:
- **Tier** — Small change / Prototype / Full development (Constitution §7). If a confirmed
  prototype exists, offer "Full development, reusing the prototype confirmed <date>" first.
  Small change → `~/.claude/commands/route.md` §4; Prototype → `~/.claude/route/PROTOTYPE.md`;
  either way leave this PLAYBOOK.
- With an interface: the facts frontend PLAYBOOK §2.3 asks.

**Risk** is `high` if the round touches money, personal data, auth or secrets, an irreversible
operation or data migration, a schema change, a new external dependency or a public API. **Gate
profile:** run each detected command once and confirm the ones that work yourself (logged); ask
only about one that cannot be detected or does not run.

Documents are written in the user's language, code, identifiers, filenames and commits in English;
the preview says so, and "Other" on any question changes it.

**2.4 Init state.** Create the artifact dir and `state.json` (§8) with `tier: "full"`, `risk` and
`prototype`. If a `state.json` with `status != "accepted"` exists, stop and point to
`/backend-resume`. A reused prototype: log
`log human --stop Prototype --decision approved --by <user> --note "reused <path>, confirmed <date>"`.

---

## 3. Phase flow

Serial between phases; fan-outs inside a phase go in one message. **A phase ends only when its
gate exits 0 (§3D).** Log every dispatch with its phase number as `--step`.

Phase 3 (detailed design) and 3b (fixtures) were merged into Phase 2 in 3.2.0; the numbers are kept
because gates `p4`–`p7` and run logs use them.

**Phase 1 — Requirements** → `be-analyst`. It writes §0 Understanding first, takes the recommended
default for every open question, labels it, and finishes. It declares fixtures and picks their real
inputs (§3E.1). You ask its blocking questions together with the Phase 1b intent questions; a fresh
`be-analyst` amends what the answers change.

**Phase 1b — Prototype** (`~/.claude/route/PROTOTYPE.md`; skipped when `prototype: "reused"`).
When the round touches an interface people operate (including a terminal), the Frontend team's
run up to its Prototype stop is the prototype: the design confirmed, then running on fake data
(§3C.4).
The user confirms a rough, runnable version (fixed stop, §3F). If the confirmation changed scope, a
fresh `be-analyst` amends `01-requirements.md` and `p1` runs again. Nothing in Phase 2 starts before
the confirmation (Constitution §2.7).

**Phase 2 — Design**, ending at the Plan stop:
1. `be-architect` writes `02-architecture.md` and `03-detailed-design.md` in one dispatch. Every
   `DES-###` names its `REQ-###` and a `side` (§3C.3). New dependencies, schema changes and genuine
   ties are decided with a recommendation, logged, and shown at Plan.
2. `risk: high` only: `mark --role be-reviewer`, then `parallelism.design_review_panel` in one
   message, each arguing against the design through its own lens; then one revision by a fresh
   `be-architect`.
3. A fresh `be-analyst` writes each fixture's expected output (§3E.2) and lists every point where
   the design does not deliver a REQ as written. A contradiction goes to a fresh `be-architect` as
   one amendment before Plan (Constitution §2.5).
4. Run `p2`; it also writes `<run-dir>/gates/plan-review.md`.
5. **Plan (human).** Show the review sheet (requirements, non-goals, decisions, dependencies,
   fixtures), the risk level, open design-review items and the assumptions to confirm. Stop for
   approval; on yes run `fixtures-approve --by <user>` if there are fixtures. Nothing is built
   before this.

**Phase 4 — Build.** `mark --role be-tester`, then `mark --role be-developer`, in that order
(`p4` applies role rules to the last-marked writer; the tester's plan is a document), then in one
message:
- `be-developer` builds the `side: backend` items only.
- `be-tester` writes `04-test-plan.md` from requirements and design only, never the code.
- `side: frontend` items go to the Frontend team (§3C.4) once their seam's backend half exists.
- A design reported unimplementable goes to a fresh `be-architect` for an amendment, as a logged
  decision; it stops the run only if the amendment changes scope (Constitution §5.1). The developer
  never improvises.

**Phase 5 — Verification** → `be-tester` runs every `TC-###` and records real output; frontend
items are verified by `fe-tester` (§3C.4–5); the frontend panel runs in Phase 6. Failures go to the
owning engineer (§3C.6) through the `p5` loop (§3D): each round a fresh engineer naming only the failing TCs, then a fresh `be-tester`.
Never relax a test.

**Phase 6 — Review** (panel trimmed by §6):
1. `mark --role be-reviewer`, then the panelists in one message, each with the same scope (diff,
   requirements, design); with frontend items, the frontend panel (frontend PLAYBOOK §6) on the
   frontend diff in the same message, its findings joining the one fix list (§3C.4). Each returns
   candidate findings; you keep them in `<run-dir>/logs/`.
2. A fresh `be-reviewer` coordinates: merges duplicates, tries to disprove every candidate against
   the code, drops one only with concrete counter-evidence, and ranks the rest. You file its text as
   `06-review-report.md`, then run `p6`.
3. Blockers and majors go to the owning engineer as a fresh dispatch naming only those `FND-###`;
   minors go to `deferred.md`. Then Phase 5 again with a fresh `be-tester` on the affected TCs.
4. Re-check: `mark --role be-reviewer`, then one fresh `be-reviewer` judges only the fixed
   `FND-###`; never the whole panel again. File its re-check table in `06-review-report.md` §5 and
   set each confirmed FND's `**Status:**` to `fixed in round <n>`; one not confirmed stays `open`
   and goes back to step 3. Cap `loops.max_fix_rounds_after_review`; at the cap minors go to
   `deferred.md` (Constitution §5.4).

**Phase 7 — Acceptance (human).** You write `07-acceptance.md` per the Phase 7 bar. Stop for
acceptance; on yes set `status = "accepted"`.

---

## 3B. Increments — the user adds or changes requirements mid-run

The run in flight is never restarted. The change becomes increment `n` and joins it.

1. **Record and confirm.** Write the user's words verbatim into `state.json` `increments` and an
   orchestrator handoff entry. Restate the change in their terms and ask once whether it adds new
   requirements or changes approved ones; a change to an approved one is a Constitution §5.1 stop.
2. **The original flow continues** to its next fixed stop (Prototype, Plan or Acceptance).
3. **At that stop the increment starts at Phase 1** and runs only its own items through every phase
   the original has passed, then the two continue as one line, sharing the stop: one Plan, one
   Acceptance. Phase 1b runs for the increment only if it adds something the user will see.
4. **Updates only, appended.** Each agent appends a `## Increment <n> — <date>` section to the
   documents it owns, holding only the new or changed items, and its handoff entry records only
   that delta. New items take the next free ids (`REQ`, `DES`, `TC`, `FX`, `FND`); ids are never
   reused. The one edit allowed to earlier content is retiring a replaced item in place (`retired,
   increment <n>` in its heading); its replacement goes in the increment section.
5. **Gates read the whole documents**, so every earlier item is still checked. After any code
   change `p4` and `p5` run the full suite: the original behaviour must still pass. New fixtures
   are approved at the shared Plan; approved ones change only by `--reapprove`.
6. **Review** covers the increment's diff, plus whatever of the original was not yet reviewed.
7. Verify each retired item is absent in code, not only in prose; recompute every count and restate
   its composition.

## 3C. The frontend/backend line

Shared with the Frontend team: `~/.claude/route/FRONTEND_BACKEND_LINE.md`; its §n is cited here as
§3C.n (default line, when it must be written, the seam, cross-stack runs, verify, fix routing,
`frontend_items`). `fe-*` models come from `~/.claude/frontend/config.json` `roles`.

## 3D. Computational gates

`python3 ~/.claude/gates/gate.py <gate> --project <root>` (`--run-dir docs/backend/<slug>` for a second feature: a path, not the bare slug), run by
you, never by the agent whose work it checks. Exit codes, waivers and the rule never to edit a gate:
`ORCHESTRATOR.md`, Key information and Boundaries. Reports: `<run-dir>/gates/`.

| When | Run |
|---|---|
| First run in a project | `profile`, then you confirm `.claude/gates.json` by running its commands (§2.3) |
| After Phase 1 | `p1` |
| Phase 1b | no gate; log its dispatch with `--step 1b` and the `Prototype` stop |
| After Phase 2, before the Plan stop | `p2` (architecture, detailed design, fixture answers, review sheet) |
| After the user approves the Plan | `fixtures-approve --by <user>` |
| Phase 4 start | `baseline` |
| Before dispatching any writing agent | `mark --role <agent>` (Phase 4: `be-tester` first, `be-developer` last; none for Phase 1b) |
| Before a panel (Phase 2.2, 6.1) and before a re-check (6.4); not again before the coordinator | `mark --role be-reviewer` |
| Before / after every dispatch | `log dispatch …` / `log return …` |
| After Phase 4 / Phase 5 | `p4` / `p5` |
| After filing `06-review-report.md` | `p6` |
| After writing `07-acceptance.md`, before the Acceptance stop | `p7` |

After any code change, re-run `p4` then `p5`.

## 3E. Approved fixtures

Human-confirmed input/output pairs that every later test must match.

1. **Declare (Phase 1).** Each active REQ with observable output names its fixtures
   (`**Fixtures:** FX-001`) or says why not (`**Fixtures:** n/a — <reason>`). `be-analyst` puts each
   real input in `<candidates>/FX-nnn/input.*` with `meta.json` (`req`, `source`), redacting
   sensitive data. Aim for 1–3 per REQ, about 10 per round.
2. **Answer (Phase 2, step 3).** A fresh `be-analyst` writes `expected.*`: the value from the
   requirement, the shape from the design; where they disagree it reports, never follows the design.
   To preserve existing behaviour it captures the current output instead and says so in `source`.
   It sets `compare` (`exact` by default).
3. **Approve (Plan).** The review sheet lists every fixture; the user approves, edits or rejects
   each. On approval run `fixtures-approve --by <user>`; it hashes and locks them in
   `<fixtures_dir>/APPROVED.json`. Nothing is locked without the user's yes.
4. **Use (Phases 4–5).** Tests load the approved files and are tagged `FX-nnn`. No agent edits an
   approved fixture; `P4/P5.fixtures` and `P5.fixtures-used` enforce it.
5. **Wrong answer found later.** Stop (Constitution §2.5), show the user the old and proposed
   output, and lock the new answer with `--reapprove FX-nnn` once they approve. History is kept.
6. Fixtures live in the project, not the run, so they accumulate into a regression suite.

## 3F. Human stops

**Fixed:** Kickoff (§2.3), Prototype (before design, Constitution §2.7; a reused prototype is confirmed in the Kickoff question instead), Plan (end of Phase 2, before any product code) and
Acceptance (Constitution §6.7).

**Otherwise** only a Constitution §5 case stops the run. Ambiguities, domain facts, ties, new
dependencies and schema changes are decided with a recommended default, labelled in the artifact,
and shown together at the next fixed stop.

## 3G. Run log

`P7` requires every dispatch to have returned, every writer mark to be followed by its dispatch,
the Plan approval to precede the first `be-developer` dispatch outside Phase 1b, and
(`tier: "full"`) the Prototype approval to precede the first Phase 2 dispatch.

---

## 4. Rules in every phase

1. No phase starts without its upstream document (`policy.block_phase_on_missing_upstream_doc`).
2. The handoff log is `<run-dir>/handoff.md`; resume with `/backend-resume`.
3. Traceability ids are mandatory; send an id-less document back once.
4. Panelists and `be-reviewer` have no Write/Edit but have Bash, so `mark --role be-reviewer` comes
   before each panel and each re-check (never between panel and coordinator, which would hide the
   panel's changes); `p6` verifies the tree is unchanged. Mutations belong in a
   throwaway tree.

## 6. Risk and cost

| | `risk: normal` | `risk: high` |
|---|---|---|
| Design review (Phase 2, step 2) | none | `design_review_panel` + one revision |
| Review panel (Phase 6) | `be-review-behavior`; add `be-review-security` if the diff touches input parsing, auth, files, network or secrets; add `be-review-reliability` if it touches persistence, concurrency, external calls or long-running work | all of `review_panel` |
| Coordinator | whenever a panelist ran | whenever a panelist ran |

Say which panelists you dispatched and why. A change of risk mid-run is a Constitution §5.1 stop.

## 7. Artifact layout

```
<project>/docs/backend/            (second feature: docs/backend/<slug>/…)
  state.json  01-requirements.md  01b-prototype.md  02-architecture.md  03-detailed-design.md
  04-test-plan.md  05-test-report.md  06-review-report.md  07-acceptance.md
  08-implementation-log.md  deferred.md  handoff.md  logs/
<project>/prototype/               throwaway prototype from Phase 1b
```

## 8. `state.json` schema

```json
{
  "harness_version": "x.y.z",
  "feature": "one line", "slug": "feature-slug",
  "started_at": "ISO-8601 from `date -u +%FT%TZ`", "updated_at": "ISO-8601",
  "status": "in_progress | blocked | accepted",
  "tier": "full", "risk": "high | normal", "prototype": "built | reused",
  "language": { "docs": "en", "code": "en" },
  "models": { "orchestrator": "…", "be-analyst": "…", "be-architect": "…", "be-developer": "…",
              "be-tester": "…", "be-review-behavior": "…", "be-review-reliability": "…",
              "be-review-security": "…", "be-reviewer": "…" },
  "current_phase": 4,
  "phases": [ { "n": 1, "name": "requirements", "status": "done",
                "artifact": "docs/backend/01-requirements.md",
                "gate": { "id": "Plan", "decision": "approved", "note": "" } } ],
  "frontend_items": [ { "des": "DES-021", "queue_row": "Q-3", "status": "verified" } ],
  "gates": { "p1": { "overall": "pass", "time": "ISO-8601" } },
  "loops": { "review_rounds": 0 },
  "increments": [ { "n": 2, "asked": "the user's words", "date": "ISO-8601", "joined_at": "Plan",
                    "items": ["REQ-019", "REQ-020"] } ],
  "open_questions": [], "notes": []
}
```

Timestamps come from a real `date` call.
