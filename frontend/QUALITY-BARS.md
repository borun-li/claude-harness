# Quality Bars — Definition of Done per Phase

A phase is done only when every bar in its section holds. `[FE…]` = also enforced by that gate
(`~/.claude/gates`, PLAYBOOK §3D). "On the running interface" means the
project's `delivery_surface` (PLAYBOOK §1C).

---

## Every artifact

- Written for an engineering team: tables, state matrices and numbered steps; no paragraph or
  bullet over 50 words.
- Every design decision traces to a user task, a business goal, evidence, or a labelled
  `[ASSUMPTION]`; the label travels into every artifact that uses it.
- No invented backend capability: anything unverified is an open item in the contract, with an owner.
- Technical vocabulary (error codes, field paths, status enums) never reaches end-user copy unless
  the named user is technical; the raw value stays behind a "details" affordance.

## Phase 1 — Discovery (`01-brief.md`)

- §0 Understanding: the ask in the user's words, what it means, ambiguities marked blocking or assumed. `[FE1.understanding]`
- One named user and their tasks (`T-###`), each task's success stated as something observable. `[FE1.user · FE1.surface · FE1.tasks]`
- Every task's Source quotes the user or cites an artifact. `[FE1.source]`
- Explicit non-goals, cut line, assumptions (`[confirmed]` with who / `[unconfirmed]`) and open
  questions, each with what its answer changes.
- The interview happened; no user answer is invented. Only questions that change the design are asked.
- Scope is proportional to the ask; anything the user's words do not require goes below the line.

## Phase 2 — Audit and Phase 5 — Review (`04-findings.md`)

- Every finding has: the task it damages for the named user · priority P1–P3 · side · evidence
  (capture name, captured state or `file:line`) · observed or inferred · recommendation · owner · status. `[FE5.findings]`
- No evidence, no finding; no priority, not received.
- A review finding states a concrete failure: this user, in this state, trying this task, gets this.
- Audits cover normal, loading, empty, error, permission-denied, long-content and narrow states,
  and name any state they could not capture.
- Only what breaks a task above the cut line is ranked; the rest is filed as deferred.
- Reviewers never edit artifacts. Completeness and quality are reported as separate claims.

## Phase 3 — Structure (`02-structure.md`)

- Delivered, and read, before any visual decision.
- Page inventory: each page's job in one sentence and the tasks it serves. `[FE3.pages · FE3.coverage]`
- Every flow has success, failure, cancel, recovery and boundary paths. `[FE3.flows]`
- A flow is at most 80 words; a page spec at most 200; a finding and a queue row at most 80.
  `[FE3.flow-length · FE4.page-length · FE5.finding-length · FE6.row-length]`
- Navigation model: what is global, what is contextual, how the user knows where they are.
- Each page's form (table, form, wizard, list, detail, workbench) is chosen for its task, with
  the reason. The information needed to decide is on the screen where the user decides.

## Phase 4 — Specification (`03-spec.md`, contract)

- Tokens are named and referenced, never inlined; components use semantic aliases only. `[FE4.tokens]`
- Every component states variants, states (default, hover, focus, active, disabled, loading,
  error, empty, selected), sizes, content limits and overflow.
- Every page states its goal, components, a state matrix (every state × what renders), permissions
  and acceptance criteria (`AC-###`) a stranger can test. `[FE4.pages · FE4.states]`
- Copy is written out for empty, loading, error, success, permission-denied and confirmation states.
- Accessibility as rules: keyboard order, focus, contrast against named tokens, target sizes,
  semantics, what a screen reader announces. Status is never carried by colour alone.
- Adaptation stated size by size for this surface.
- The contract covers, per page and action: data fields, capability needed, every state,
  validation and error copy, permissions, and open items with owners.

## Phase 6 — Queue (`05-queue.md`)

- Every row has `spec`, `files`, `observable`, `priority`, `side`, `acceptance`, `depends on`. `[FE6.rows]`
- `observable` is what a person perceives on the running interface, in that surface's terms.
  A row that cannot be observed is split or marked not observable.
- Rows are graded by `fe-critic` before dispatch; rows blocked on an open question name it.

## Phase 7 — Build

- The engineer changes only what its row names, on its side of the project's written line; if
  the line is not written, it stops and reports. `[ROLE.unplanned]`
- It never edits tests or loosens an acceptance criterion; a red check is handed back red. `[ROLE.tests · FE7.test-drift]`
- It adds no package the spec's Dependencies table does not name. `[FE7.dependencies]`
- Its own measurement is labelled "implementer self-check", with how it was taken.
- Nothing outside the row is fixed in passing; it is registered.

## Phase 8 — Verify (`06-verification.md`)

- Every row has exactly one verdict: done · not done · not observable. Not observable is not done. `[FE8.verdicts · FEA.rows]`
- Evidence comes from the surface, never a picture alone, and every claim cites fields present
  in the dump it cites. `[FE8.evidence]`
- Evidence is captured by `gate.py capture` from a plan covering every row, size and state, after
  the last build and against the current source. `[FE8.capture-plan · FE8.capture]`
- A new assertion is shown both red when its behaviour breaks and green when unrelated copy
  changes. Prefer equality over containment or absence.
- Expected values come from an independent source, never from what is checked.
- A negative result ("unchanged") needs a positive control in the same run.
- Mutation uses copy aside → mutate → run → copy back → `cmp`; never git restore; never touch a
  file another agent is editing.
- A spec the running interface contradicts is filed against the spec; it costs no rework round.
- A red result is delivered red; no expected-failure markers.

## Plan and Acceptance

- Plan (design): scope against the ask, page inventory, key decisions, open P1s and contract items.
  An open blocker makes it conditional, with the blockers and their impact listed.
- Plan (`implement`): every row's `observable` shown for approval. `[FE.observables]`
- Acceptance: every active task delivered by a row verified done (`gates/traceability.md`). `[FEA.matrix]`
- Every registered observable from earlier rounds still holds, unless the user retired it.
  `[FE.regression · FE.regression-captures]`
- Acceptance: verdicts per row with evidence, what is unmeasured (e.g. never tested with a real
  user), and what the user must do for it to be live. Constitution §6 holds in full.
