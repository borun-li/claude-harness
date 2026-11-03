# Backend Agent Team（原 Waterfall Agent Team） — Harness Changelog

Semver: **patch** = prompt/bar tuning · **minor** = new behaviour or new role ·
**major** = changed phase flow or artifact contract.

体例：**本文件的条目记录事故发生的具体项目、平台与数字**，出处越具体越好；而
**规则正文（`PLAYBOOK.md`、`QUALITY-BARS.md`、`agents/`、`templates/`）一律不得携带项目名词** ——
每个项目都要读的规则里出现某一个项目的名词、阈值或裁定，就是把一个团队的偏好发给了所有团队。

## 3.3.0 — 2026-11-02 — shared line file; be-analyst as the product role

Shared with frontend 7.0.0 (see `~/.claude/frontend/CHANGELOG.md`).
- §3C moved to `~/.claude/route/FRONTEND_BACKEND_LINE.md`, cited as §3C.n; it adds who designs the
  frontend side (`fe-ux`, `fe-ui`), the cross-stack table (§4: the frontend UI stop is the Phase 1b
  Prototype stop when the round touches a visual interface) and finer fix routing.
- `be-analyst` also writes product features in frontend-only runs (`00-requirements.md`, gate
  `fe-product`, which reuses `p1`).
- Gates: role checks ignore the other team's run dir and, for `fe-*` roles, the fixtures dirs;
  `_trail_common` shared by both teams' trail checks.
- Constitution amended (2026-11-02, by the user): §2.7, §3.2, §5.1, §5.5, §6 — see frontend 7.0.0
  for the text and reasons. Backend behaviour is unchanged: §5.1 covers results the user confirmed
  (approved fixture answers already need `--reapprove`), not internal design amendments, which stay
  logged decisions unless they change scope (PLAYBOOK Phase 4); the backend kickoff stays at 4
  questions; no backend budget is set.

## 3.2.0 — 2026-11-02 — one design phase, review panel with a coordinator, depth by risk

Source: the Ithaca Local Guide MVP run log (harness 2.7.4): about 931 agent-minutes, of which Phase 6 took 570 (61%) over 39 dispatches (17 reviewer, 9 developer, 7 architect) for 71 findings (3 blocker, 24 major, 44 minor); Phase 3 took 161 minutes and `p3` ran 17 times, one dispatch spending 114 minutes to bring one DES under the word limit. Review design after Block's `block/review` (three fixed lenses; a coordinator that merges and tries to disprove) and the user's AGNT Con notes (precision over recall; deep review only for high-risk changes).
- **Phase 2 — Design** replaces Phases 2, 3 and 3b: one `be-architect` dispatch writes `02-architecture.md` and `03-detailed-design.md`; `risk: high` adds a design review (`be-review-behavior`, `be-review-reliability`) and one revision; then a fresh `be-analyst` writes the fixture answers (value from the requirement, shape from the design, contradictions reported, never followed) instead of `be-tester`. The Plan stop is the phase's exit. Phase numbers 3 and 3b are retired; the others are unchanged.
- **Gates:** `p2` now runs the former `p2`, `p3` and `plan` checks and writes `plan-review.md`; `p3` and `plan` are removed; `fixtures-approve` requires a green `p2`; `PLAN.expected` / `PLAN.meta` are owned by `be-analyst`; `P7.gates` requires `p1 p2 p4 p5 p6`. `LOG.trail` (backend): the Prototype approval precedes the first step-`2` dispatch (step `3` still counts for older runs); the frontend keeps step `3`, since its Phase 2 is an audit. `ALL.state` validates `risk`. `be-review-*` marks count as reviewer marks; `p2` runs writer role checks only when a writer mark exists.
- **Review:** new agents `be-review-behavior` (Behaviors & Contracts), `be-review-reliability` (Reliability & Operations), `be-review-security` (Security & Trust boundaries) run in parallel; `be-reviewer` is now the coordinator: merges, disproves with counter-evidence only, lists every drop, ranks `FND-###`; it also re-checks only the fixed findings, never the whole panel. Only blockers and majors go to fix rounds; minors are deferred. Lenses retired: correctness, security-and-robustness, maintainability-and-simplicity, operator-experience, traceability (TC-verifies-REQ moves to behavior; the id matrix stays `P7.matrix`), feasibility-and-risk, simplicity-and-alternatives (into the design review). No judge and no confidence threshold.
- **Risk** (`state.json` `risk: high | normal`, recommended at kickoff, the user decides): high = money, personal data, auth or secrets, irreversible operations or migrations, schema changes, new external dependencies, public APIs. Normal trims the panel by what the diff touches (PLAYBOOK §6, which replaces the 200-line rule).
- **Kickoff:** tier, model plan, risk and gate profile in one `AskUserQuestion` (`/route` asks it after its read-only classification for backend and cross-stack work). Document language follows the user's language and is stated in the preview, not asked (`language.default_docs: "user"`). Full development reuses a confirmed prototype (`prototype: "reused"`, logged as the Prototype approval) instead of building another.
- PLAYBOOK trimmed: §1A, §2.0, §2.5, §3A and §5 removed (they only pointed to `ORCHESTRATOR.md`); exit codes and stop rules that repeat `ORCHESTRATOR.md` or Constitution §5 removed. QUALITY-BARS: Phases 2 and 3 merged under Phase 2 with all `P2.*`/`P3.*` bars; Phase 6 rewritten per panelist and coordinator; mutate-and-restore and reporting rules point to `ORCHESTRATOR.md` and Constitution §2.3/§2.5.
- **§3B Increments** replaces Re-baseline (decided by the user): a requirement added or changed mid-run never restarts the run. The original flow continues to its next fixed stop; there the increment starts at Phase 1 with only its own items, catches up, and shares the stop (one Plan, one Acceptance). Agents append a `## Increment <n>` section holding only new or changed items, with new ids; a replaced item is retired in place. Handoff entries record only the delta. `state.json` gains `increments`; `route/HANDOFF.md` brief and entry carry the increment number. A test shows the gates read an appended increment and exempt retired items.
- `be-architect`, `be-analyst`, `be-tester`, `be-reviewer` aligned; templates `06-review-report.md` (Panelist column, coordinator drops with counter-evidence) and `07-acceptance.md` (drop count). `route/HANDOFF.md` §1: direct calls log to `docs/handoff.md`.

## 3.1.0 — 2026-10-31 — context discipline; constitution made stable

Source: Ithaca Local Guide MVP run: one `be-tester` was continued across fix rounds (702 turns, 321M tokens), the orchestrator session reached 574 turns, 254M tokens and a 965K-token context.
- Constitution (amended by the user): new §8 **Context discipline** — one fresh agent per dispatch (one exception: an agent blocked on a question may be continued once in the same round), short briefs by id and path, a dated handoff entry from every agent, long output to files, summary returns, orchestrator handoff at every human stop. New §9 Amendments: section numbers are stable.
- Constitution made roster- and path-free: §3 is generic role boundaries (the roster lives in each PLAYBOOK); §7 keeps only the tier rules (procedures stay in `route.md` and `route/PROTOTYPE.md`); §6 is one list for every tier. Lifted from PLAYBOOK §3A into the Constitution: §2.3 (a returned agent has stopped), §2.8 (a description is not the thing), §2.9 (the user's observation outranks analysis), §4.6 (the user's workspace is off-limits). Existing section numbers are unchanged.
- New `route/HANDOFF.md`: brief format (ordinal, round, task, items, evidence, pitfalls), handoff entry format, orchestrator entries, `logs/` for long output. Log: `<run-dir>/handoff.md`; Small change: `docs/handoff.md`.
- PLAYBOOK §4.2–4.3 and §3D: every fix round is a fresh dispatch naming only the failing items; the orchestrator reads verdicts and summaries, not whole reports. `/backend-resume` starts from the last orchestrator handoff entry instead of reading every artifact whole.
- All agents: a Handoff section. `be-tester` fix rounds run only the named TCs; the `p5` gate re-runs the suite.
- New `ORCHESTRATOR.md` (installed at `~/.claude/`): the orchestrator is the main session, since subagents cannot dispatch. It holds what both teams' orchestrators share — role, the dispatch cycle, context, decisions and stops, discipline (from backend §3A and frontend §5), run log (from backend §3G), gates in general (from backend §3D), reports. The PLAYBOOKs keep only what each team runs and when; their §1A, §3A, §3G, §4, §5, §6 now point to it. All commands load it.
- Entry: `/route` gets a `when_to_use` (amended by the user): it is the only natural-language entry, used when the request changes the user-visible behaviour or the structure of maintained software, or the user asks for the agent team; judged by what changes, never by file count. Not for coursework, questions, research, one-off edits, behaviour-preserving error fixes, or requirements / review / test work alone (those dispatch a single agent directly). `/backend` and `/frontend` get `disable-model-invocation: true`: typed by the user or reached through `/route` only.
- Correction (2026-11-01): the `ORCHESTRATOR.md` entry above says subagents cannot dispatch; that is wrong. Claude Code lets a subagent spawn subagents (up to three layers below the main conversation). The orchestrator is the main session because subagents cannot ask the user (`AskUserQuestion` is removed from them). `ORCHESTRATOR.md` now says so, and that team agents do not dispatch (no `Agent` in their tool lists).
- New hook `hooks/no-agent-continuation.py` (PreToolUse on SendMessage): reads `<session>/subagents/agent-<id>.meta.json`; a finished `be-*`/`fe-*` agent may be continued once (the §8.1 exception), a second continuation is denied. `install.sh` registers it.
- Constitution §5 **Decision Rules** simplified (amended by the user; its items renumbered, the one exception to §9): default is decide, log and continue; questions and assumptions wait for the next fixed stop with a recommended default. Only four cases stop the run: scope or priority change, irreversible or outward-facing action, a fixed stop, stuck (failed twice or loop cap). Removed as stop reasons: a fact only the user knows, options with different costs, new dependency or schema change (all shown at the Plan stop, which precedes any code). §2.1 now says an assumption carries a recommended default and is shown at the next fixed stop. `be-analyst` no longer stops in Phase 1: its blocking questions are asked with the Phase 1b intent questions; an unimplementable design is a logged amendment, not a stop.

## 3.0.0 — 2026-10-18 — run tiers and Phase 1b prototype

Source: retrospective on the Ithaca Local Guide MVP (2026-09-24..25): about 38 h and about 1.0B tokens; the user first saw the site after acceptance, and it was not the MVP they wanted.
- Constitution §7 **run tiers**: the user is asked first, never inferred: Small change / Prototype / Full development. Small change: `commands/route.md` §4 (confirmed short plan, a fresh engineer dispatch per side, no documents or gates). Prototype: `route/PROTOTYPE.md`.
- Constitution §2.7: in Full development the user sees and confirms a runnable prototype before detailed design. New **Phase 1b** (after requirements, before architecture and detailed design) and a fixed **Prototype** stop.
- Gates: `log human --stop Prototype`; `LOG.trail` lets step-`1b` engineer dispatches precede the Plan and, when `state.json` has `tier: "full"`, fails a step-`3` dispatch before the Prototype approval; `ALL.state` validates `tier`. Runs without `tier` are unchanged.
- `be-developer`, `fe-engineer`: rules for Prototype and Small change dispatches.

## 2.7.4 — 2026-09-24 — route-classifier removed

- `agents/route-classifier.md` deleted at the user's request. `/route` rewritten (English, core rules):
  the orchestrator classifies from code facts and the contract's capability table, then runs
  `/frontend`, `/backend`, or `/backend` with the Frontend team for cross-stack work.
- The capability ledger is merged into the contract's capability table; legacy
  `contracts/CAPABILITY_LEDGER.md` is still read.
- Constitution §3 (amended by the user): the route-classifier row was removed, and orchestrators
  now "classify tasks (`/route`)".

## 2.7.3 — 2026-09-23 — JUnit for JS test runners (shared gates)

- Per-test results for vitest, playwright and jest (with jest-junit), including runners behind
  `npm run` / `pnpm` / `yarn` scripts; any other runner via `gates.json` `"junit": "<path or glob>"`.
  Only reports written by this run are read. Vitest summary counts are parsed as a fallback.
- Test ids (`TC-`, `FX-`, `Q-`) are recognised in JS test titles and in comments above tests.
- Checked against real vitest 2 and jest 29 + jest-junit 16. Suites: 69 backend, 23 frontend.

## 2.7.2 — 2026-09-23 — shared-gate changes for the frontend

- `baseline` excludes both teams' run dirs (and legacy ones) from the clean-tree check.
- `LOG.trail` treats `fe-engineer` like `be-developer` (Plan approval must come first).
- §3C.4 points at `docs/frontend/05-queue.md`.

## 2.7.1 — 2026-09-23 — frontend alignment touch-ups

- §3C.4 points at the new frontend queue `frontend/05-queue.md`; frontend rows' observables are
  shown at the Plan stop.
- Template placeholders changed from `<…>` to `{…}` (the preview swallowed `<word>`); gates treat
  both as unfilled (`P1.source`, findings scenario). Suite: 64 cases.

## 2.7.0 — 2026-09-23 — Run log (control panel)

- `<run-dir>/run-log.jsonl`: append-only, hash-chained audit trail. Gates write `gate`, `mark` and
  `approve` events themselves. The orchestrator writes `dispatch`, `return`, `human` and `decision`
  events with `gate.py log`, which validates required fields and allowed values and refuses forged
  gate events. `gate.py timeline` renders `run-log.md`.
- `LOG.valid` on every gate (log present, schema valid, chain intact). `LOG.trail` in P7: every
  dispatch returned, every writer mark followed by its dispatch, and the Plan approval before the
  first be-developer dispatch.
- PLAYBOOK §3G; `/backend-status` shows the timeline; `/backend-resume` treats a dispatch with no
  return as unverified work.
- Suite: 63 cases (6 new); chain and plan-order checks mutation-tested.
- Backend harness upgrade complete for this cycle (2.2–2.7). Not yet exercised on a real run.

## 2.6.0 — 2026-09-23 — Two human stops; concise, understood requirements

- Human stops cut from four (G1, G2, GF, G3) to two fixed: **Plan** (one page before any code:
  requirements, non-goals, decisions, dependencies, fixtures) and **Acceptance**. Others only for a
  Constitution §5 case, batched per phase (PLAYBOOK §3F). Config `gates`: `Plan`, `Acceptance`.
- Gate `gf` renamed `plan` (`PLAN.*`); it now writes `plan-review.md` lifted verbatim from 01–03.
- be-analyst writes §0 Understanding first (ask in the user's words, meaning, ambiguities marked
  blocking or assumed) and stops on blocking ones. Every REQ needs a `Source:` that quotes the user
  or cites an artifact.
- Templates 01–03 rewritten as table/one-line skeletons (734 → 526 words), plus a worked example
  each in `templates/examples/`. The examples must pass p1–p3 (regression case).
- New gates: `P1.understanding`, `P1.source`, `P1.req-length` (60), `P2.length` (800 prose words),
  `P3.des-length` (120), `P1/P2/P3.prose` (50 per paragraph or bullet). Limits in gates config
  `doc_budgets`; tables and code do not count; CJK at 2 characters per word.
- Fixed: headings inside fenced code (e.g. `# comment` in a signature block) split DES blocks and
  dropped their fields.
- Suite: 57 cases (9 new); three new checks mutation-tested.

## 2.5.0 — 2026-09-23 — Approved fixtures

- New PLAYBOOK §3E and Phase 3b. be-analyst declares `Fixtures: FX-nnn | n/a — <reason>` per active
  REQ and supplies real (redacted) inputs. be-tester drafts expected outputs from the spec only, or
  captures current output to preserve behaviour. New human gate **GF**: the user approves each
  answer from an auto-generated review sheet. `fixtures-approve --by <user>` locks them (hashes,
  approver, date, history). Fixtures live in the project and accumulate as a regression suite.
- Gates: `P1.fixtures`, `gf` (`GF.inputs/expected/meta` plus review sheet), `fixtures-approve`
  (refuses without a green `gf` and an approver; changing an approved answer needs `--reapprove`),
  `P4/P5.fixtures` (hash intact, every declared FX approved), `P5.fixtures-used` (referenced by a
  passing test), and a Fixtures column in the P7 matrix.
- Fixed: `baseline` counted this run's own contract and fixture files as someone else's
  uncommitted work. Fixed: fixture data under `tests/` (which contains FX ids) counted as a test
  referencing the fixture, so the unused-fixture check could never fire. Found by mutation testing.
- Suite: 48 cases (11 new); three checks mutation-tested.

## 2.4.1 — 2026-09-23 — tidy-up, no behaviour change

- QUALITY-BARS: bars enforced by a gate are tagged with its id (e.g. `[P1.cut-line]`); added the
  gate-backed bars that were only in code (TC tags pass, no removed/skipped tests, no open
  blocker/major).
- be-* agent files slimmed to role, inputs, method and output contract; duplicates of the
  constitution, PLAYBOOK and QUALITY-BARS removed; be-developer's Chinese section condensed to English.
- Commands: `/backend` defers to the PLAYBOOK; `/backend-status` reports gates and flags unverified
  marks; `/backend-resume` runs the gate for unverified work first; `/backend-config` covers gate
  config and requires gate tests for gate-code changes.
- Fixed invalid YAML frontmatter (pre-existing) in `backend-resume.md`, `backend-config.md` and
  `frontend.md` by quoting values.
- README rewritten: agent-only Mermaid flowchart with fix loops, bullet-point notes, team table.

## 2.4.0 — 2026-09-23 — Computational gates

- New `~/.claude/gates/` (Python stdlib): `gate.py profile | p1 | p2 | p3 | baseline | mark | p4 | p5 |
  p6 | p7`, run by the orchestrator, never by the agent being checked. Exit 0 pass, 1 fail, 3 fix-round
  cap, 2 config error. 37-case regression suite in `gates/tests/`.
- Doc gates keep only checks later gates depend on or that catch real omissions: ids, Given/When/
  Then, cut-line marks, coverage REQ→architecture→DES, DES side, frontend DES in contract.
- `mark` snapshots before each writing dispatch; role rules apply to exactly that agent's diff
  (developer: no frontend, no existing-test edits, no unplanned files; tester: tests/docs only;
  reviewers: nothing).
- `p4`/`p5`: orchestrator re-runs build/lint/typecheck/tests; test count may not fall, skips may not
  rise; new dependencies must be named in the design; secret and personal-path scan of added lines;
  automated TCs must be tagged in code and pass (per-test for pytest via JUnit); reported passes the
  run did not observe fail the gate; approved-fixture hashes checked.
- Fix loop: hard block, failures routed to `owner`; the script counts rounds and returns 3 after
  `loops.max_gate_fix_rounds` (3). `max_fix_rounds_after_verification` removed. Waivers only with
  `approved_by` + `date`.
- PLAYBOOK §3D (schedule), §2.2/2.3 (profile confirmation), Phase 6 traceability lens is semantic
  only, §4.7 reviewer tree check via `mark`/`p6`, `state.json` gains `gates`.
- Templates: `Cut:`, `Side:`, design §9 Dependencies, TC tags in tests, exact result words,
  `path:line` findings. Agent files: one or two lines each on what the gates read.
- Language support: generic for docs, snapshots and commands; per-test verification is pytest-only
  for now (other runners: exit code only, counts `unavailable`).

## 2.3.0 — 2026-09-23 — Constitution adopted

- New `~/.claude/CONSTITUTION.md` (shared by all teams): mission and priority order, core
  principles, roles, workflow, decision rules, definition of completion. It overrides PLAYBOOK,
  QUALITY-BARS, agent files and dispatch prompts; only the user amends it.
- Every agent file, command and PLAYBOOK now opens with "Read CONSTITUTION.md first".
- Duplicates removed in favour of the constitution: be-analyst (no guessing → §2.1), be-tester and
  be-developer (observed results only → §2.3; never weaken a test → §4.5), PLAYBOOK §4 "never
  fabricate test results" (items renumbered: old §4.7–4.8 → §4.6–4.7), PLAYBOOK §5 escalation
  (→ Constitution §5), QUALITY-BARS Phase 7 honesty/live-steps bars (→ Constitution §6).
- Hook comment reference updated to §3A.11.

## 2.2.0 — 2026-09-23 — PLAYBOOK + QUALITY-BARS slimmed (11,703 → 3,201 words)

Why: the two files every agent reads had grown to ~12k words; the length itself cost context and
diluted the rules that matter. Rewrite keeps every substantive rule and all section anchors other
files cite (§1, §1A, §2.3, §3A, §3B, §3C.1–7, §8, QUALITY-BARS "Phase N").

- Each rule reduced to one or two imperative lines. Incident narratives removed; they remain in
  the entries below and in `~/.claude/backup-slim-20260923.tgz`.
- Duplicates merged: "make it fail" (4×), independent expectations (3×), mutate-and-restore (3×),
  criteria-can-be-wrong (2×). Orchestrator discipline 3A: 17 items + §4.9 → 15 items.
- Removed all L2/L3 "staged" bars (never enforced). Performance regression checks will be
  redesigned under architecture fitness.
- `state.json` schema gains `frontend_items`; artifact layout lists `NN-deferred.md`.
- Hook `no-tree-restoring-git.py`: stale `~/.claude/waterfall/… §3A.13` reference → backend §3A.11.

## 2.1.0 — 2026-09-23 — be-developer builds backend only

Before: when no Frontend team was dispatched, `be-developer` also built the interface. That meant
interface code nobody verified on the running surface and the Frontend ledger never heard of.

- `be-developer` builds backend only, always (agent prompt + PLAYBOOK §0).
- New PLAYBOOK §3C: default line (API, CLI, scripts, schema = backend; human-operated GUI/TUI =
  frontend; the project's written line overrides). The line must be written down only when a round
  touches the interface (checked at G1). Architect tags every `DES` `side: backend | frontend` and
  specifies only the seam for frontend items. The orchestrator dispatches the Frontend team
  (`fe-designer` → `fe-critic` grading → `fe-engineer` → `fe-tester`) inside the same run. Fixes
  go to the side where the defect is.
- `be-analyst` tags `[interface]` requirements; `be-developer` returns `frontend_items`.
- QUALITY-BARS: new L1 bars in Phases 1, 3, 4/5 and 7.
- `route` / `route-classifier`: state that the Backend team never builds frontend.

## 2.0.0 — 2026-09-22 — renamed: waterfall → backend

Rename only; no behaviour change. The team runs the same phase-gated waterfall process.

- Command `/waterfall*` → `/backend`, `/backend-status`, `/backend-resume`, `/backend-config`.
- Harness dir `~/.claude/waterfall/` → `~/.claude/backend/`.
- Agents `wf-{analyst,architect,developer,tester,reviewer}` → `be-*`.
- **Artifact contract (why major):** `docs/waterfall/` → `docs/backend/`,
  `.claude/waterfall.json` → `.claude/backend.json`. Legacy paths are still read when the new ones
  are absent (PLAYBOOK §1 rule 4). Migrated: socsci-replication-availability. Not migrated (code
  hardcodes the old path in ~120 places): ctrip.
- Entries below this one are history and keep the old names.

## 1.10.0 — let it be wrong, and watch what turns red

One round produced the same defect three times over, from three different readers, and none of the
existing bars caught any of them: **a description of the code standing in for the code.** An agent
inferred a parameter's provenance from a type annotation that was wider than reality; an agent
inferred 「no guard exists」 from 「no reconciliation is declared」 while a behavioural test upstream
already had it; and a design document written by this harness recorded a plausible mechanism that
was wrong in a way that would have produced a fix that could not work. The same round also found an
assertion that read as a reconciliation and compared a constant with itself — structurally
incapable of failing.

One mutation in a throwaway worktree settled each of them in about four minutes.

- **QUALITY-BARS Phase 4/5** — five new bars, all from measured incidents:
  - *An assertion counts as coverage only after you have made it fail*, with three corollaries:
    an expectation derived from the thing it checks is an identity; accidental coverage is not
    coverage; a guard that cannot fire is worse than none because it occupies the slot.
  - *A negative result requires a positive control* — 「the bytes are identical」 proves nothing
    until the same probe is shown to notice a change on the same run.
  - *A test must be fed by the producer production uses* — a suite drove the real adapter through
    its real entry point and still proved nothing, because the input came from a different (also
    real) serializer that agreed on top-level keys and diverged one level down.
  - *A guard is judged by its false-positive rate as well as its catch rate* — one that fires on
    legitimate work gets switched off, leaving no guard plus the belief that there is one.
- **QUALITY-BARS Phase 6** — the reviewer breaks every guard it relies on; 「nothing would catch X」
  is not reportable until X was made wrong and nothing caught it.
- **QUALITY-BARS Phase 1** — a scope exclusion must state which kind it is: *deferred* leaves a
  hole the next reader fills, *not ours* closes a road and the closing is the deliverable.
- **PLAYBOOK §3A.16** — your acceptance criterion is an artefact and can be the wrong thing.
  Three times in one round it was: one logically unsatisfiable, one contradicted by a sibling
  artefact, one predicting bytes would not change for a fix that had to change them. All three were
  caught by the agent, none by the orchestrator. State criteria as observable outcomes; say in the
  brief that challenging them is the job.
- **PLAYBOOK §3A.17** — 「read the description of the code」 as a named failure mode, with the one
  operational question that replaces it.
- **Agents** — `wf-developer`, `wf-tester`, `wf-reviewer`, `fe-engineer`, `fe-tester` gained the
  counterpart: *satisfying a wrong criterion is worse than failing it*, do the unambiguous part,
  quote both artefacts, never resolve it by editing whichever is easier to change.

## 1.9.0 — the git ban stops being a sentence

Four agents in five days ran a tree-restoring git command (`git checkout --`, `git apply -R`,
`git checkout <docx>`, `git stash push/pop`). The ban was already written — in dispatch prompts and
in a project memory file — and all four agents knew it, because all four disclosed the breach
themselves. One cost real work: three uncommitted production edits belonging to another agent.

- **New**: `~/.claude/hooks/no-tree-restoring-git.py`, a `PreToolUse(Bash)` hook registered in
  `~/.claude/settings.json`. Denies the tree-restoring family and names the alternative in the deny
  message. Read-only git is untouched.
- **New**: `~/.claude/hooks/test_no_tree_restoring_git.py` — 27 cases. The DENY half is the four
  real violation commands; the ALLOW half is the false positives that would get the guard switched
  off (grepping for the ban's own text, writing it into a heredoc). A guard's false-positive rate
  decides how long it survives, so both halves are acceptance criteria.
- **PLAYBOOK §3A.13**: never dispatch a writing agent against a dirty tree — the expensive breach
  was expensive *because of the dirty tree*, not because of the command.
- **PLAYBOOK §3A.14**: the enforcement is a hook, not a prompt, plus the wanted/denied/instead
  table. Generalised rule for future guards: not "is this dangerous" but "can the caller name
  everything it touches".
- **PLAYBOOK §3A.15**: self-disclosure is what made all four recoverable — record it, fix the
  structure, and say in the report that the agent disclosed it. Punishing disclosure would remove
  the harness's only detector for failures nobody wrote a test for.
- **Agents**: `wf-tester`, `wf-developer`, `fe-engineer`, `fe-tester` gained the mutation-testing
  protocol (cp → mutate → cp back → `cmp` → `rm`) and the disclosure instruction.

Same release, same principle applied to a second bar. The Phase 2 *cost of the next one* bar
already demanded an answer to 「what tells them when they have forgotten one?」 and already called a
design unfinished if the answer was 「nothing」. In production it produced a correct and detailed
prose inventory — 23 edit sites across 14 files, 8 of them silent — which is exactly the artefact
that goes stale the moment the fifteenth file appears.

- **QUALITY-BARS Phase 2**: the footprint answer must be **executable** — a test that adds a
  synthetic extra member and asserts the change footprint, so the number has a live source. Its
  value is in what it names when it fails. A footprint claim with no such test must be labelled an
  estimate.
- **QUALITY-BARS Phase 6**: the `maintainability-and-simplicity` lens **re-measures** rather than
  quoting Phase 2's number; a footprint that grew during the round is the finding this lens exists
  to produce, and a round may not close on a stale count.

## 1.8.0 — 2026-08-25

**测量本身会说谎，而且骗得过它自己的作者。** Three L1 bars promoted into Phase 4/5 and two
orchestrator rules added, all from one measurement round where every wrong number looked exactly
like a real result.

1. **A failed run is not a wrong answer.** A timed-out call left one document with zero output;
   scored naively that read as recall 63.6% against an unchanged extractor and looked precisely
   like an over-aggressive rule change. Excluding the failed units moved the same data from 77.0%
   to 92.4%. The bar now requires a per-unit failed/blocked flag carried through to the scorer and
   the failure rate reported beside the accuracy — the round's measured failure rate was **20%**,
   which is itself the finding. The orchestrator wrote this rule for a subagent and then broke it
   in its own scoring script one round later: the field existed and went unused.

2. **One run is not a measurement of a non-deterministic system.** Five runs of an unchanged prompt
   on unchanged inputs spanned **13.9 points of precision, 21.2 of recall, 40.2 of a text-match
   rate**. A +8-point 「improvement」 had already been reported from a single run — inside the noise.
   The bar now requires mean, range, run count, and — before optimising — the split between errors
   present in **every** run and errors present in **some**. In that round the split was decisive:
   0 systematic misses, 9 intermittent ones, and the intermittency was per-document, not per-item.

3. **An answer key must be shown to be reachable before it scores anything.** Three cells of a
   hand-adjudicated key held text silently normalised while transcribing — a character restored
   from a typo elsewhere in the same document, a curly quote squared, a separator swapped. Each
   marked a cell no correct implementation could ever win, and each would have been scored as the
   model's failure. **A wrong key cell is visually identical to a wrong answer**, which is why the
   check has to be mechanical: every expected value must be obtainable from the input by the same
   rule the system under test must use.

Two PLAYBOOK rules, both from the orchestrator's own failures rather than an agent's:

**§3A.11** — long work writes each unit to disk as it completes, with a resume that skips what is
already there; no agent may end a turn waiting on its own background job. Three agents in a row
died on the same task; one signed off with 「I'll wait for the notification」 and delivered nothing.

**§3A.12** — a command that exits 0 having done nothing is the failure mode to design against, and
the orchestrator's own shell is where it happens. Four in a row, all silent: `set -e` versus
`[ -f x ] && continue`, a `&`-backgrounded job reaped with its parent, a zsh no-match glob aborting
a wait loop, and zsh's lack of word-splitting collapsing three paths into one impossible filename.
**Verify by artefact, never by exit code** — this class is indistinguishable from 「still running」
until you go looking for the product.

## 1.7.0 — 2026-08-19

**一轮做一件事的最简单形态。** The harness had strong bars for completeness and honesty and
none for proportion: every bar pushed outward, and nothing anywhere said 「够了」.

Measured, from the round that produced this entry: a user asked for two things — the wait is
silent and looks dead, and the screen never says which file is being read. That became **26
requirements, 14 components, 93 test cases and 24 review findings**, and the user's verdict was
that this is a habit, not an accident.

Three places let it happen, and all three are fixed here:

1. **Phase 1 had no floor.** Its L1 bar required all seven non-functional axes be 「addressed or
   declared out of scope」 and called zero open questions a smell — both of which reward
   expansion. The MoSCoW/MVP cut line, the one bar that could have contained it, sat unused in L2.
   Promoted to L1 and sharpened: the round is the simplest common path of what the user said
   out loud; disproportion between the ask and the requirement count is now **a defect in the
   analysis**, and the analyst must justify each requirement from the user's own words.

2. **Phase 6 re-widened what Phase 1 narrowed.** Five lenses, each doing its job well, ranked
   every true thing they found — so a round scoped small at Phase 1 arrived at the gate with a
   fix list the size of a new feature. Reviewers now rank only what breaks a requirement above
   the cut line; everything else is filed to `NN-deferred.md` with file:line and scenario intact.
   **Recorded fully, scheduled separately** — the finding is not lost, only unscheduled.

3. **The orchestrator undid the deferral.** New Phase 7 bar: deferred findings may not be
   bundled into a fix round. 把二十条推迟项塞进一次修复轮,等于用一次修复轮开了一个新需求 —
   and the user, who scoped the round smaller, never agreed to it.

New PLAYBOOK §2.1a: the cut line is written **before Phase 1 is dispatched**, so the round is
scoped before anyone is being paid to be thorough. And the standing principle behind all of it:
a first version that is obviously incomplete but working is the goal. Growing it is cheap;
shrinking a large speculative build is not, because by then every part has tests, documents and
an agent defending it.

## 1.6.0 — 2026-08-18

**A declaration may not occupy an observation's slot.** Two L1 bars promoted and one
orchestrator rule rewritten, all against one defect class seen five times in a single
project round.

The shape: a sentence written in advance, sitting where a record of what happened
belongs. It reads exactly like evidence, because the slot it occupies is named for
evidence.

Where it appeared:

- A check's `red_when` **declaration** — 「this check goes red when the model answers 大理」
  — printed as the runtime **evidence** for why it fired, on a document containing 大理 zero
  times.
- A constant fallback string, 「the model read no city-level place name in this document」,
  appearing 30 times in a measurement artefact. The analyst, the architect and the
  orchestrator each read it as the model's own answer. It produced a root-cause diagnosis
  all three agreed on, and it was wrong: the field could not have produced a value for any
  answer, because a grounding helper returned `None` for every tuple. Thirty paid model
  calls were spent testing a prompt hypothesis about a code defect.
- A second multi-valued field with the same code defect scored **30/30 correct**, because
  its answer key was all-absence. It would have been recorded as 「correctly detected
  absence」. Only the trivial-baseline column caught it.
- The orchestrator telling the user 「I sent this back to the architect」 while nothing had
  been sent and every agent had been idle for 35 minutes — an intention in the past tense,
  the same shape one level up.

**Phase 4/5 L1 (new):** a field that reads as an observation — `reason`, `basis`,
`evidence`, `source`, `note` — must be shown to vary across two differing inputs. A
constant in such a slot is a declaration wearing an observation's name; rename it
(`*_declared`, `*_spec`, `*_policy`) or produce it from the run. Two inputs, two values, or
it is not evidence.

**Phase 6 L1 (new):** a diagnosis resting on a string in an artefact is not accepted until
its producer is located in code. Reading a `reason` tells you what the field says, never who
wrote it. The lens that eventually caught the defect above did exactly this and nothing
more.

**PLAYBOOK §3A rule 9 (rewritten, not added to):** every claim about work in flight carries
its evidence in the sentence — "last wrote at 22:33, nine minutes ago", not "is building".
The rule already existed in its 「remember to check the mtimes」 form and was violated three
times anyway (six hours, ten minutes, thirty-five minutes; twice the user caught it by
asking whether anything was running). A rule asking you to remember to check is weaker than
one that makes the unchecked sentence unwritable — so the evidence is now required in the
claim itself, the same way a rate may not print without its denominator.

## 1.5.0 — 2026-08-18

**`quality` tier: `wf-developer` sonnet → opus.**

Chosen by the user after selecting the same override manually at kickoff for four
consecutive rounds of one project — a preference confirmed four times is a default, and
re-asking it every round was the harness making the user repeat themselves.

The evidence is that the build role's work in this harness is not mechanical
transcription of the detailed design. In those four rounds the developer caught that a
declared assertion used a field absent from the demotion list and **would therefore have
passed vacuously forever**; found and replaced an `assert X in Y or True` it had itself
just written; ruled that a whitelist must be keyed by `(module, symbol)` rather than by
occurrence, because an occurrence-keyed one goes red on a conforming repo and pressures
the next person into loosening it; and repeatedly reported its own work as **not
delivered** ("zero production callers — by the Phase 6 bar it is not in the product",
"this round produced no measurement numbers") when a weaker reading of its own output
would have passed. Those are judgement calls against the quality bars, and they are what
the bars are for.

Cost: the build role is the largest single token consumer in a run (~430k in the most
recent round), so this raises per-run cost materially. Projects that do not need it should
select `balanced` or set a project-level override in `.claude/waterfall.json`.

## 1.0.0 — 2026-08-09

Initial harness.

- 5 roles: `wf-analyst`, `wf-architect`, `wf-developer`, `wf-tester`, `wf-reviewer`,
  orchestrated by the `/waterfall` command acting as project manager.
- 7-phase waterfall: requirements → architecture → detailed design → build → verification →
  review → acceptance.
- Hybrid orchestration: serial between phases; parallel inside phase 2 (design critique),
  phase 4 (implementation ∥ test-plan authoring) and phase 6 (multi-lens review).
- 3 human gates: G1 requirements, G2 architecture, G3 acceptance.
- Per-role model plan with a mandatory confirmation prompt at kickoff; four tiers
  (quality / balanced / economy / max) plus free-form per-role overrides.
- Traceability spine `REQ → DES → code → TC → FND` enforced by `policy.require_traceability_ids`
  and audited by a dedicated reviewer lens.
- Quality bars split into L1 (enforced) and staged L2/L3 for later promotion.
- Resumable runs via `docs/waterfall/state.json`.

## 1.1.0 — 2026-08-10

Three L1 quality bars added, each learned from a real failure in the first production run
(CTrip Stage 0 POC). All three are project-independent.

- **Phase 3 — a completeness assertion may not be derived from the output of what it checks.**
  That run's consistency checker asserted `len(verdicts) == len(CHECK_UNIVERSE)` where
  `CHECK_UNIVERSE` was itself built from the verdicts, making the assertion algebraically
  equivalent to "no duplicates" — which the next line already checked. Two independent review
  lenses found it; one proved it by execution: 30 genuinely missing field verdicts produced
  `status: VALID, unverdicted: ()`. The assertion had been added specifically to stop an earlier
  finding from recurring, and it could not detect the case it named.

- **Phase 4/5 — fixtures must include the legitimately-absent shape, and tests must reach their
  subject through its real entry point.** Two blockers in that run traced to the same root. Every
  one of 165 passing tests used fully-populated fixtures, so `compile_plan` crashing on the
  codebase's own mandated "not mentioned" representation went unnoticed and made an acceptance
  criterion look proven when it was not. Separately, a non-reentrant transaction defect broke the
  entire manager-approval flow and survived 71 tests because they seeded state with raw SQL,
  structurally bypassing the transaction boundaries of the functions under test.

- **Phase 6 — coverage is claimed by behaviour, not by symbol; and a test counts as coverage only
  if it can fail.** The traceability audit found seven public functions with zero production
  callers, six requirements with a symbol but no working code behind them, and a design coverage
  table concluding "all 37 requirements claimed, no gaps". Separately, a gate criterion's test
  hand-constructed a state the system could not produce, so it would have passed against a broken
  implementation. The run's most convincing single artifact was a deliberate red/green experiment
  proving a regression test actually went red when the regression was reintroduced.

## 1.2.0 — 2026-08-12

Five L1 quality bars and a new orchestrator-discipline section, all learned from the second
production run (CTrip POC re-baseline: 22 real UI screenshots, 4 real customer documents, a live
model, and a user testing by hand). Every rule below fired at least twice in that run.

- **Phase 3 — every guard declares what makes it fire AND what makes it not fire.** A compliance
  rule forbidding 「第一」 matched 「第一天」, so every multi-day itinerary tripped a blocker-severity
  check. In the same run a departure-closure guard became unreachable by construction after a scope
  cut, and the developer named the principle exactly: *an always-true guard is behaviourally
  indistinguishable from no guard.* Two more rules were unreachable (one not locally computable,
  one with no trigger left).

- **Phase 4/5 — a claim about an external system is verified under production-shaped input.** The
  provider sent `response_format: json_object` alongside a prompt demanding a JSON array. A trivial
  probe returned an array and was taken as proof; under the real 12,929-character prompt the model
  returned a single object and the core extraction path failed on first contact with a real
  document. Same shape twice more: a red experiment that "passed" because it patched a comment, and
  a regex probe whose own bug produced a wrong measurement that two conclusions were then built on.

- **Phase 6 — reachability is judged from the user's entry point.** The gate told the clerk to fill
  11 gaps and acknowledge 17 advisory items. Both routes existed, were tested, and had no UI
  anywhere pointing at them — the user could not finish the flow in a browser. Earlier in the same
  project a `POST /edit` route had no page either, and seven public functions had zero production
  callers.

- **Phase 6 — a declared non-goal must be verifiable as absent.** The brief said price/inventory/
  departures were out of scope and the field registry agreed, while the publish chain kept
  executing both actions. Image handling was similarly half-retired. Prose scope with surviving
  behaviour is worse than no declaration, because every later reader trusts it.

- **Phase 6/7 — a number carries its composition and its measurement conditions.** "44 active
  requirements" was identical before and after a re-baseline that retired three and added nine.
  "2 blocking gaps per product" was a stub-provider count; the real figure was 9. "93 un-carried
  clauses" counted fragments — 4-character headings and numbered sub-items — where the meaningful
  unit was 15 topics. A pass count rose from 201 while 33 test files sat quarantined.

- **PLAYBOOK §3A, new — orchestrator discipline.** Verify a number before relaying it; re-verify
  with an instrument that measures what you think it does; exercise the real entry point yourself,
  including on an environment that already has state; protect a hand-testing human's session from
  agent convenience; relay disagreement rather than arbitrating it silently. Every item is a
  mistake the orchestrator made in this run — including overriding a correct user observation using
  a non-interactive login shell that never sourced the file being compared.

## 1.3.0 — 2026-08-13

Stage 0 closing retrospective on the CTrip POC. Eight new L1 bars, one promotion, a fourth review
lens, two orchestrator rules and a re-baseline procedure. The theme of this round differs from
1.1.0 and 1.2.0: those were about tests that could not fail. **These are about a product that was
green, complete and traceable, and still met its first real operator with a 500 on the first page.**

- **Phase 3 — a catch-all branch must state what it does not claim.** A review finding
  ("three real inputs produce logless 500s") was fixed by installing `register_error_handler(
  Exception, ...)`, commented *catch all exceptions*. It did — including werkzeug's `NotFound`, so
  every mistyped URL became `UNHANDLED_ERROR`/500 and every page view wrote a fake ERROR row for
  `/favicon.ico`, burying real failures in the one file kept for finding them. The remedy acquired
  the disease in mirror image while wearing the badge of the fix.

- **Phase 3 — a sentinel has exactly one predicate.** `NOT_PROVIDED` was interpreted independently
  at nine sites across three positions (scalar, object slot, list element); five days of a real
  itinerary were asked to cite a source for a field that was never provided. Fixed by one
  structural `is_missing` recursing over `dataclasses.fields`.

- **Phase 3 — a durable reference must survive recomputation.** `span_id` was a fresh ULID per
  extraction, so every stored lineage became unresolvable after any re-extract, and the entire
  edit / `HUMAN_OVERRIDE` path returned 400. Unit tests minted and consumed ids within one run and
  never saw it. It shipped as a known defect pinned with `xfail(strict=True)`.

- **Phase 4/5 — exercise the system against state written by an earlier version of itself.** An
  existing workspace failed at startup with `IntegrityError`: `CREATE TABLE IF NOT EXISTS` silently
  kept a `NOT NULL` column from the PDF era after the source format changed. Only machines with
  history were affected — i.e. every machine except the test runner's.

- **Phase 4/5 — every interactive control is clicked once, through the interface, on real data.**
  Cheapest bar in the file. Would have caught the 400-on-every-edit, the favicon 500, and 1.2.0's
  two unreachable routes.

- **Phase 4/5 — a non-deterministic producer yields a sample, not a property.** Same document,
  same model, same prompt, different output. A single green run of an LLM pipeline was repeatedly
  read as "it works"; it means the path *can* work.

- **Phase 4/5 — real end-to-end integration test promoted L2 → L1.** Almost every defect in three
  retrospectives was found by a real run and missed by a green suite. It has stopped being an
  aspiration.

- **Phase 6 — completion and accuracy are separate claims.** The POC proved the flow runs end to
  end and never measured extraction accuracy after the re-baseline. Both facts are true; only one
  survives summarisation unless the report forces the other.

- **Phase 6 — a finding may only be deferred with its user path named.** The missing exception
  boundary was found in review, ranked "next round, does not affect current use", and was the first
  thing the operator hit on the first page of the first run.

- **Phase 7 — name what the user must do to make the delivered work live.** A verified fix was
  nearly reported as done while the user's server, started before the edit, still contained the
  defect — which would have read as "the fix failed".

- **New review lens `operator-experience`** (config `parallelism.review_lenses`). The three
  existing lenses all read code. Most of this stage's misses were only visible from the operator's
  chair, on a machine that already had state.

- **PLAYBOOK §3A rules 6–7** — a fix is not delivered until the process the user is running
  contains it; one instance, one workspace, established before diagnosing anything. Duplicate
  servers fabricated phantom 500s that cost a debugging round on already-correct code.

- **PLAYBOOK §3B, new — re-baseline procedure.** The brief was rewritten mid-run and 22 UI
  screenshots arrived after G2. Stop the phase in flight, re-enter at Phase 1, retire ids rather
  than delete them, verify each scope cut as absent in code, recompute every count, record it in
  `state.json`.

- **PLAYBOOK §2.2** — when the product calls an LLM at runtime, benchmark candidate models on a
  production-shaped prompt before the build phase. Reasoning models share `max_tokens` between
  reasoning and content, so a long chain of thought truncates the answer to empty and surfaces as
  intermittent malformed-output errors far from the cause.

## 1.4.0 — 2026-08-14

Two consecutive UI rounds on the CTrip project. Four new L1 bars, three expansions, three
orchestrator rules. **The theme is new again**: 1.1.0 was about tests that could not fail, 1.3.0
about a green suite over a broken first page. These are about verification that reports success for
work it never examined — and about a redesign that shipped invisible.

- **Phase 4/5 — every URL a delivered page references is fetched, not merely rendered.** The product
  served every page with zero CSS for a whole round: `Flask(__name__)` gave the app a static folder
  that did not exist, the blueprint registered no `static_url_path`, and `url_for` emitted a path the
  app-level route answered with 404. 559 tests passed. The palette, the sidebar and the red marking
  were all implemented and all invisible. The user restarted, said 「没看到较大改动」, and one `curl`
  found it. The existing "every interactive control is clicked" bar missed it because the
  control-enumerating test collected `<a>` and had never looked at `<link>`.

- **Phase 4/5 — a fix goes where the defect is, not where it was noticed.** The previous round's
  review had already filed this exact 404 — observed on the failure page. The fix inlined a `<style>`
  block into that one template, and the review recorded 「failure.html 的 404 已修复」: true, and it
  left every other page unstyled. A symptom seen on one screen is a report about a mechanism.

- **Phase 4/5 — a pass verdict names the assertion that produced it, specifically enough to grep
  for.** A test report recorded PASS for cases whose evidence was 「随全量套件绿」 — true, and
  unrelated. 9 of 15 mandated red/green experiments were never executed, and 5 of those had **no
  assertion anywhere in the repository**: `sidebar`, `aria-current`, `assembled_constants`,
  `TABLE_A`, `retired_autofill`, `pending_task_ids` each returned zero hits in `tests/`. The report
  was internally consistent and graded its evidence per row; only grepping the asserted symbol
  exposed it. Of 29 requirements, 9 had a failable assertion behind them.

- **Phase 6 — an assertion that combines several sources must be shown to fail for each of them.**
  The round's load-bearing guard was `assert on_rows | counted == expected`, where `counted` and
  `expected` both came from the same call, so `counted == expected` held unconditionally and the row
  half could contribute nothing. The correctness lens measured the guard green while a blocking field
  demonstrably carried no red mark. The developer's red experiment had broken the shared producer,
  which breaks both sides at once and proves nothing about either.

- **Phase 4/5 (expanded) — an override of a requirement is a deviation and gets logged.** Twice a
  design overrode a requirement for good reasons written down in the design and in the code but not
  in the deviation log, so the traceability chain ended in a test asserting the opposite of what the
  requirement mandated, with nothing saying which governed.

- **PLAYBOOK §3A rule 2 (sharpened) — to test "this does not depend on X", change X, do not remove
  it.** I verified 「0 tests depend on the operator's workspace」 by hiding the directory; it passed
  either way. The real dependency was on the database's *state*: the user kept using the tool, a
  migration ran, and the 547-passing baseline handed to the next phase was 545 passed / 2 failed by
  the time it started.

- **PLAYBOOK §3A rule 8 (new) — a user's report of what they see outranks every analysis you have.**
  Reproduce their view before explaining it away.

- **PLAYBOOK §3A rule 9 (new) — never state a precision you did not measure.** I told the user
  「8 个任务中的 7 个」 for a distribution my query had never computed; the truth was 6 of 9. The total
  was measured, the split was invented, and the analyst caught it.
