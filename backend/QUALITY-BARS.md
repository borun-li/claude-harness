# Quality Bars — Definition of Done per Phase

A phase is done only when every bar in its section holds. Raise the team's level here.
`[P1.cut-line]` = also enforced by that gate (`~/.claude/gates`, PLAYBOOK §3D). Meet the bar
anyway; the gate proves it.

---

## Phase 1 — Requirements (`be-analyst`)

- Every requirement has a unique `REQ-###`, is testable, states an observable outcome, and has
  Given/When/Then acceptance criteria. `[P1.req-ids · P1.acceptance]`
- §0 Understanding restates the ask in the user's words and lists ambiguities, each blocking or
  assumed. `[P1.understanding]`
- Every REQ's Source quotes the user or cites an artifact. `[P1.source]`
- Tables and one-line fields, not prose: a REQ is at most 60 words, and no paragraph or bullet runs
  over 50. `[P1.req-length · P1.prose]`
- Sections present: **Non-goals**, **Assumptions** (each `[verified]`/`[unverified]`), **Open
  questions** (each with a recommended default).
- Inputs and outputs are concrete: formats, sample values, real paths.
- Requirements a person perceives through a GUI/TUI are tagged `[interface]` and describe what is
  observed, not how the screen looks.
- Non-functional axes are considered; "not this round" is a complete one-line answer.
- Every active REQ with observable output declares fixtures, or says why not. Inputs are real
  (from the project's data), cover a common case and an edge or absent shape, and are redacted where
  sensitive. `[P1.fixtures · PLAN.inputs]`

**Scope proportion**
- The round implements the simplest common path of what the user asked. Variants, legacy data,
  concurrency, migrations and edge cases go to `NN-deferred.md` (file:line + one-line scenario).
- An explicit MVP cut line; every `REQ` is above or below it; nothing below is built. `[P1.cut-line]`
- Requirement count is proportional to the ask. Each `REQ` names, in one sentence, the user's
  words that require it; one that cannot goes below the line.
- Every exclusion says which kind it is — **deferred** (to be built later) or **not ours** (closed
  for good) — and what it makes true, forbids, and leaves owing.

---

## Phase 2 — Architecture (`be-architect`)

- Components, each with a one-sentence responsibility.
- Data model: entities, key fields, ownership, persistence.
- External contracts: signatures, auth, error shapes, rate limits.
- At least two alternatives, each with its rejection reason.
- Risk register: likelihood, impact, mitigation, early detection.
- Failure model for each external dependency.
- `REQ → component` coverage; an uncovered requirement is a blocker. `[P2.coverage]`
- Tables, not prose: at most 800 words of prose, no paragraph or bullet over 50. `[P2.length · P2.prose]`
- **Cost of the next one.** For any family that will grow (platform, tenant, locale, provider…):
  list what adding a member changes and what goes red if one edit is forgotten. Prefer one
  declaration read by many. Name a test that measures the footprint (e.g. a synthetic extra
  member); without one, label the cost an estimate.

---

## Phase 3 — Detailed design (`be-architect`)

- File layout with each file's responsibility; typed signatures for every public function/class.
- Each DES at most 120 words outside code; behaviour as numbered one-line steps. `[P3.des-length · P3.prose]`
- Error taxonomy (which errors, which retry, where handled); state transitions; config and
  secrets named, never inlined.
- Every `DES-###` names its `REQ-###`, every `REQ-###` is claimed by a `DES-###`.
  `[P3.serves · P3.req-claimed]`
- Every `DES-###` has `side: backend | frontend` (PLAYBOOK §3C). A frontend item specifies only
  the seam and appears in `contracts/FRONTEND_BACKEND_CONTRACT.md`; layout, components, copy or
  styling in it is sent back. `[P3.side · P3.contract]`
- Every guard states the case that fires it and the case that does not.
- Expected sets come from an independent source (spec, fixed declaration), never from the output
  being checked.
- A catch-all names what must pass through it untouched (framework control-flow signals first).
- Each sentinel ("missing", "unknown", …) has one predicate, used everywhere.
- Each durable id is declared content-derived, persisted, or per-run, matching what consumers need.

---

## Phase 4/5 — Implementation & Verification (`be-developer`, `be-tester`)

**Code**
- Lint, typecheck and build pass with the project's own commands. `[CMD.*]`
- `be-developer`'s diff contains no frontend-side files. `[ROLE.frontend]`
- No secrets, tokens or absolute personal paths. `[P4.secrets · P4.personal-paths]`
- No dead code, commented-out blocks, or ownerless `TODO`.
- Every deviation from the design, including an override of a requirement, is logged in
  `08-implementation-log.md` with the reason. `[ROLE.unplanned]`
- A field that reads as an observation (`reason`, `basis`, `evidence`, `source`, `note`) varies
  with the input; a constant belongs in a `*_declared` / `*_spec` field.

**Test coverage**
- Every `REQ` has a `TC`; every `TC` names its `REQ`. Failure paths and boundaries included.
  `[P4.plan-ids · P4.plan-cases · P4.plan-coverage]`
- Every automated `TC` is tagged in test code and passes in the orchestrator's own run.
  `[P5.tc-in-code · P5.tc-results]`
- No test is removed or newly skipped. `[CMD.test · P4/P5.test-drift]`
- Expected fixture outputs come from the spec, not the code. Tests load the approved fixtures and
  pass; nobody edits them. `[PLAN.expected · P4/P5.fixtures · P5.fixtures-used]`
- Each seam has a `TC` showing the contracted shape from the backend side, including its empty case.
- Fixtures include the legitimately-absent shape of every optional field.
- One fixture is state written by an earlier version, upgraded in the test.
- At least one test runs the real integration path end to end.
- Tests enter through the real entry point, with inputs from the same producer the shipping path
  uses. Any scaffolding is disclosed at the point of the claim.
- Claims about external systems are verified with production-shaped input; the rest is marked
  assumed.
- If the round delivers an interface (GUI, TUI or CLI): every control is exercised once on real
  data, and every resource it references by name resolves (enumerate from the source).

**Test validity**
- An assertion counts only after you made it fail; record what went red.
  - Expected and actual must not share a producer.
  - Coverage by an unrelated test is not coverage.
  - A guard that cannot fire is replaced in the same change.
  - An assertion over several sources must fail for each source.
- A negative result ("unchanged", "identical") needs a positive control on the same run.
- A new guard is tested on innocent cases as well as guilty ones.
- **Mutate-and-restore:** copy aside → mutate → run → copy back → `cmp` against the copy →
  confirm no diff vs. the repo → delete the copy. Never restore with git. Never mutate files
  another agent is editing.

**Reporting**
- Only real captured output. Each pass names its assertion precisely enough to grep. Not run →
  `blocked`. `[P5.report-complete · P5.report-honest]`
- Non-deterministic results: state the run count, mean and range; separate always-errors from
  sometimes-errors.
- Fix the mechanism, not the instance; name what else it reaches, or what stays broken.
- If acceptance criteria contradict each other or the code: do the unambiguous part, quote both
  artifacts, and do not edit whichever is easier to change.

**If the round scores accuracy** (otherwise write "N/A" in the test report):
- Units that produced no answer leave the denominator; report the failure rate next to accuracy.
- Every answer-key value is reachable from the input by the rule under test.

---

## Phase 6 — Review (`be-reviewer`)

- Each `FND-###` has a concrete failure scenario, a `file:line`, a severity, and the `REQ` above
  the cut line it breaks. Anything else goes to `NN-deferred.md` with file:line and scenario.
  `[P6.findings]`
- Every guard the round relies on is broken once by the reviewer (mutate-and-restore). "Nothing
  catches X" is reportable only after letting X be wrong.
- **Maintainability lens:** measure the cost of the next member against the code; run Phase 2's
  footprint test and report the delta. A fact spelled twice with nothing reconciling the two is a
  finding.
- **Traceability lens:** the id matrix is `P7.matrix`'s. Judge whether each `TC` really verifies
  its `REQ`; list every zero-caller public symbol. Coverage counts only what a user can reach from
  the delivered entry point.
- Declared non-goals are verified absent in code.
- Every number carries its composition and measurement conditions.
- Completion and accuracy are separate claims; an unmeasured one is stated as unmeasured.
- A deferral names the user-visible path it sits on; nothing on the first-run path is deferred
  quietly.
- A diagnosis based on a string in an artifact locates the code that produced it.
- Style nits are dropped unless they break a written project convention.
- Reviewers never edit. `[P6.tree-unchanged]`

---

## Phase 7 — Acceptance (Orchestrator)

- Coverage matrix: `REQ → DES → TC → result`. `[P7.matrix]`
- No open blocker or major finding. `[P7.open-findings]`
- The run log accounts for every dispatch, return and human stop, and is intact.
  `[LOG.valid · LOG.trail]`
- Frontend items: who built each, and `fe-tester`'s verdict ("can't tell" is not "works").
- Accepted-but-unfixed findings, with rationale; known limitations; follow-up work.
- Size against the ask: what was asked (in the user's words), shipped, deferred.
- Deferred items are never folded into a fix round without the user.
- Constitution §6 (Definition of Completion) holds in full.
