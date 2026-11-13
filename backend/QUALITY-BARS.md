# Quality Bars — Definition of Done per Phase

What "done" means for each Backend phase. Each agent checks its own section before returning; the
orchestrator checks it before the phase's gate and stop. `[P1.cut-line]` = also enforced by that
gate (PLAYBOOK §3D): meet the bar anyway; the gate proves it.

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
  concurrency, migrations and edge cases go to `deferred.md` (file:line + one-line scenario).
- An explicit MVP cut line; every `REQ` is above or below it; nothing below is built. `[P1.cut-line]`
- Requirement count is proportional to the ask. Each `REQ` names, in one sentence, the user's
  words that require it; one that cannot goes below the line.
- Every exclusion says which kind it is — **deferred** (to be built later) or **not ours** (closed
  for good) — and what it makes true, forbids, and leaves owing.

---

## Phase 2 — Design (`be-architect`, then `be-analyst` for fixture answers)

**Architecture (`02-architecture.md`)**
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

**Detailed design (`03-detailed-design.md`)**
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

**Design review (`risk: high` only)**
- Each panelist argues against the design through its own lens: where it breaks, what is assumed
  without evidence, a materially simpler design that meets the same requirements.
- The revision answers every point: changed, or why not, in one line each.

**Fixture answers (`be-analyst`)** `[PLAN.expected · PLAN.meta]`
- Every declared fixture has `expected.*` and a `meta.json` with `req`, `source` and `compare`.
- The value comes from the requirement; the shape (fields, format, message text) from the design.
  Where the design does not deliver the REQ as written, quote both and report it; never follow the
  design. Preserved behaviour is captured from the current output and says so in `source`.
- Fixture outputs come from requirements and design, never from new code.

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
- Every automated `TC` is carried in its test's name or title and passes in the orchestrator's own run.
  `[P5.tc-in-code · P5.tc-results]`
- No test is removed or newly skipped. `[CMD.test · P4/P5.test-drift]`
- Tests load the approved fixtures and pass; nobody edits them. `[P4/P5.fixtures · P5.fixtures-used]`
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
- Mutation follows `ORCHESTRATOR.md`, Boundaries (copy aside, mutate, copy back, `cmp`); never on
  files another agent is editing.

**Reporting** (Constitution §2.3 and §2.5 apply)
- Each pass names its assertion precisely enough to grep. `[P5.report-complete · P5.report-honest]`
- Non-deterministic results: state the run count, mean and range; separate always-errors from
  sometimes-errors.
- Fix the mechanism, not the instance; name what else it reaches, or what stays broken.

**If the round scores accuracy** (otherwise write "N/A" in the test report):
- Units that produced no answer leave the denominator; report the failure rate next to accuracy.
- Every answer-key value is reachable from the input by the rule under test.

---

## Phase 6 — Review (panelists, then `be-reviewer`)

**Every panelist**
- Read-only: never edit code, tests or documents. `[P6.tree-unchanged]`
- Stay in your lens; the other lenses run in parallel. Judge against the requirements and design
  the dispatch names, not against taste. Style is never a finding unless it breaks a written
  project convention.
- Each candidate has a concrete failure scenario (inputs/state → wrong result), a `file:line`, a
  severity, the `REQ` above the cut line it breaks, and the evidence that it is real. Grep before
  reporting that something is missing. Anything outside the cut line is a deferral, not a finding.
- "Nothing catches X" is reportable only after letting X be wrong (mutate-and-restore).
- A diagnosis based on a string in an artifact locates the code that produced it.
- Severity: **blocker** (must fix before acceptance) · **major** (should fix) · **minor** (worth
  knowing). An empty list from a clean lens is a valid result; never pad.

**Behaviors & Contracts** — does the logic do what the REQ says in the normal case?
- Each REQ's behaviour, boundaries and error paths against its acceptance criteria.
- Contracts between components and at the seam: shapes, nullability, ordering, units.
- Whether each `TC` really verifies its `REQ` or merely touches the code; happy-path-only
  coverage; code serving no REQ; declared non-goals absent in code. (The id matrix is `P7.matrix`'s.)

**Reliability & Operations** — does it break under failure, load or a real operator?
- Dependency failure, timeouts, retries, partial writes, restart and upgrade from earlier state,
  concurrency, resource limits.
- Operability: failure messages carry stage, cause and next step on screen and in the log; every
  required action has a way to do it. Run the product read-only, never in the user's workspace.
- The cost of the next member, measured against the code with Phase 2's footprint test; a fact
  spelled twice with nothing reconciling the two.

**Security & Trust boundaries** — can an attacker use it?
- Every input crossing a trust boundary: validation, injection, path traversal, unsafe
  deserialisation, file and upload handling.
- Authentication, authorisation, secret handling, unsafe defaults, resource exhaustion.

**Coordinator (`be-reviewer`)**
- Merges duplicates across panelists, keeping each source panelist.
- Tries to disprove every candidate against the code. A candidate is dropped only with concrete
  counter-evidence (`file:line` or command output), and every drop is listed with it.
- Ranks the survivors as `FND-###`, most severe first; numbers carry their composition and
  measurement conditions; completion and accuracy stay separate claims.
- A deferral names the user-visible path it sits on; nothing on the first-run path is deferred
  quietly. `[P6.findings]`

**Re-check (`be-reviewer`)**
- Judges only the `FND-###` the dispatch names: fixed (with evidence) or still open.

---

## Phase 7 — Acceptance (Orchestrator)

- Coverage matrix: `REQ → DES → TC → result`. `[P7.matrix]`
- No open blocker or major finding. `[P7.open-findings]`
- The run log accounts for every dispatch, return and human stop, and is intact.
  `[LOG.valid · LOG.trail]`
- Frontend items: who built each, and `fe-tester`'s verdict ("can't tell" is not "works").
- Accepted-but-unfixed findings, with rationale; findings the coordinator dropped (count and where
  listed); known limitations; follow-up work.
- The goal (Constitution §7.4) first: the change, the user's check, and its result.
- The demo's before and after, captured at the goal's real entry point (`ORCHESTRATOR.md` § Demo). `[DEMO]`
- Size against the ask: what was asked (in the user's words), shipped, deferred.
- Deferred items are never folded into a fix round without the user.
- Constitution §6 (Definition of Completion) holds in full.
