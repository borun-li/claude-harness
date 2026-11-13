# Quality Bars — Definition of Done per Phase

A phase is done only when every bar in its section holds. `[FE…]` = also enforced by that gate
(`~/.claude/gates`, PLAYBOOK §3D). "On the running interface" means the project's
`delivery_surface` (PLAYBOOK §1C).

---

## Every artifact

- Written for the next role: tables, state tables and numbered steps; no paragraph or bullet over
  50 words. `[FE1.prose · FE2.prose]`
- Every decision traces to a `REQ-###`, the user's words, evidence, or a labelled `[ASSUMPTION]`;
  the label travels into every artifact that uses it.
- No invented product feature or backend capability: a missing feature goes back to `be-analyst`,
  an unconfirmed capability is a contract open item with an owner.
- Technical vocabulary (error codes, field paths, status enums) never reaches end-user copy unless
  the named user is technical; the raw value stays behind a "details" affordance.
- A change to something the user confirmed goes through a DFB (PLAYBOOK §3A), never a silent edit.

## Phase 0 — Product features (`00-requirements.md`, frontend-only runs)

- The backend bar § Phase 1 holds (`~/.claude/backend/QUALITY-BARS.md`), with every active REQ a
  person uses tagged `[interface]`; acceptance says what the user can do and see, not how it looks.
  `[P1.*]`

## Phase 1 — UX (`01-ux.md`)

- One named user and the surface, from the project context or the kickoff answer. `[FE1.user · FE1.surface]`
- **Pages.** Each `PAGE-###` has one job in one sentence, the REQs it serves and its form
  (table, form, wizard, list, detail, workbench) with the reason. Every active `[interface]` REQ is
  served by a page. `[FE1.pages · FE1.coverage]`
- **Flows.** Each `FLOW-###` serves REQs and lists its steps, then its success, failure, cancel,
  recovery and boundary paths. Fewest steps and decisions; the information needed to decide is on
  the screen where the user decides. A flow is at most 80 words. `[FE1.flows · FE1.flow-length]`
- **Navigation model:** what is global, what is contextual, how the user knows where they are.
- **State table per page:** loading, empty, success, error, permission (plus offline or partial
  where they apply), each with what the user sees, the words they read and what they can do next,
  or `n/a — <reason>`. An error row names its cause (a backend error code when one exists) and the
  way out. `[FE1.states]`
- **One wireframe per page**, layout and priority only: a grey Figma frame linked as
  `- **Wireframe:**` when the run has a UX stop on a canvas surface (it is what the user approves);
  otherwise a text block. A page block is at most 200 words, wireframe excluded.
  `[FE1.wireframes · FE1.page-length]`
- No visual decision: no colour, font, icon or component styling.
- **Intake form** (external design): flows and wireframes are not required; pages and every state
  row still are. `[FE1.pages · FE1.coverage · FE1.states]`

## Phase 2 — UI (`02-ui.md`, Figma)

- **Design plan before any frame:** 4–6 named hex colours, typefaces and their roles, a layout
  concept, the principles that make this interface its own. `[FE2.plan]`
- **Self-check written:** what in the plan read like the default for any similar product, and
  what replaced it — or why nothing did. `[FE2.self-check]`
- **Tokens** in two layers, primitive and semantic; components reference semantic aliases only;
  no colour value outside the plan and tokens tables. `[FE2.tokens]`
- **Components** (`CMP-###`): variants, sizes, content limits, overflow and every state that
  applies — default, hover, focus, active, disabled, loading, error, empty, selected. Every
  component has a focus state. Status is never colour alone. `[FE2.components]`
- **Frames** (`FRAME-###`): every UX page has at least one, each row naming its page, state, size
  and Figma node link (`node-id=`); a state or size whose layout differs has its own frame;
  states that only swap a component state point to the component sheet. Terminal surfaces: text
  mockups instead of links. `[FE2.frames]`
- Accessibility as rules: contrast of each text/background token pair (≥ 4.5:1 body, 3:1 large text
  and controls), target sizes, focus appearance, reduced-motion alternative for every animation.
- Figma calls within the run budget (PLAYBOOK §1E). `[FE.figma]`
- **Intake form** (external design): no design plan or self-check; frames still are. `[FE2.frames]`

## Phase 2 — Queue (`03-queue.md`)

- **§ Scaffold** lists every file the scaffold changed and what each does. `[ROLE.unplanned]`
- **Rows.** Every `Q-###` has `Page`, `Frame` (or `n/a — no visual`), `States`, `REQ`, `Files`,
  `Observable`, `Acceptance`, `Priority` P1–P3, `Side`, `Depends on`, `Status`. `[FE2.rows]`
- `Observable` is what a person perceives on the running interface, in that surface's terms; a
  row that cannot be observed is split. A row is at most 80 words. `[FE2.row-length]`
- **Coverage.** Every page, every frame and every non-`n/a` state row is delivered by some row. `[FE2.coverage]`
- **Dependencies table** names every new package, with why. `[FE3.dependencies]`
- **Contract.** Every capability the pages use is in `contracts/FRONTEND_BACKEND_CONTRACT.md`,
  marked `verified` (with source), `unverified` or `new`; open items have an owner. `[FE2.contract]`
- **Feedback decided.** Every DFB in `06-feedback.md` has a decision, by whom; `needs user: yes`
  ones are listed for the stop. `[FE2.feedback]`

## Phase 3 — Build

- The engineer changes only what its row (or § Scaffold) names, on its side of the written line;
  no written line → it stops and reports. `[ROLE.unplanned]`
- It builds every state row its row names and every width in `viewports`, with data from the
  contract — not only the frame's success state.
- It never edits tests or loosens an acceptance; a red check is handed back red. `[ROLE.tests · FE3.test-drift]`
- It adds no package the Dependencies table does not name. `[FE3.dependencies]`
- Its own measurement is labelled "implementer self-check", with how it was taken.
- Nothing outside the row is fixed in passing; it is registered. A design it cannot build as
  drawn is a DFB.

## Phase 4 — Verify and review

### Verification (`04-verification.md`)

- Every row has exactly one verdict: done · not done · not observable. Not observable is not
  done. `[FE4.verdicts · FEA.rows]`
- Done means the capture matches the row's observable, its frame export at the same size, and
  its state rows' words and ways out, in everything the person doing the row's task would notice or
  be held up by. A difference seen only by setting capture and frame side by side leaves the row
  done and goes under § Minor deviations, with its capture.
- In a rework round a row is not done only if the named defect still shows or the fix broke what
  held before; anything else newly seen is judged by the bullet above.
- Evidence comes from the surface, never a picture alone, and every claim cites fields present in
  the dump it cites. `[FE4.evidence]`
- Evidence is captured by `gate.py capture` from a plan covering every row, width and state, after
  the last build and against the current source. `[FE4.capture-plan · FE4.capture]`
- A new assertion is shown red when its behaviour breaks and green when unrelated copy changes;
  with its `Q-###` in the test's name or title, it passes in this run. `[FE4.row-tests]`
- Expected values come from an independent source; a negative result needs a positive control.
- Mutation uses copy aside → mutate → run → copy back → `cmp`; never git restore.
- A design the running interface contradicts is filed as a design defect; it costs no rework round.

### Every panelist

- Read-only: the tree outside the run dir and test files is unchanged while the panel and
  coordinator ran.
  `[FE4.tree-unchanged]`
- Every candidate states a concrete failure: this user, this size, this state, trying this, gets
  this — with the capture field, probe output or `file:line` that shows it.
- Problems, not prescriptions: the impact, and at most a one-line direction.
- Severity: **blocker** — a task above the cut line cannot be completed, or data is lost or wrong;
  **major** — completed only with real difficulty, or a group of users is shut out; **minor** —
  everything else. No style or taste findings unless they break the confirmed design or a written
  convention.

### Experience

- Each confirmed flow walked as the named user, success and failure paths, at every width.
- Each state as the user sees it matches its state row (words, way out).
- Pages and states without a frame are consistent with those that have one.
- Copy: one name per action through the flow; errors say what happened and what to do.

### Accessibility

- Every flow completes by keyboard alone, with visible focus and no trap.
- Every control has an accessible name; fields have labels; errors are tied to fields and announced.
- A screen-reader transcript per flow, from the ARIA snapshot; state changes are announced.
- Contrast from computed colours; no colour-only status; 200% zoom; reduced motion respected.
- Each candidate cites its WCAG 2.2 success criterion; scan hits are confirmed by hand.

### Data & runtime

- Every request and response the code uses matches the contract.
- Slow, empty, error (each backend code), 401/403 and offline responses each reach their UX
  state, shown by request interception against the isolated instance.
- Double submit, out-of-order responses, leaving mid-request and stale data after a mutation are tried.
- No console error during a flow; first load and interaction on the narrow size are stated with
  how they were measured.

### Coordinator (`05-review.md`)

- Every candidate is in the report: as an `FND-###` (merged duplicates name every panelist) or in
  § Dropped with concrete counter-evidence. `[FE4.findings]`
- Each finding has severity, `Where` (a run-dir file or `path:line` that exists), the UX or
  contract reference, and a scenario. `[FE4.findings]`
- Only blockers and majors go to a fix round; minors, the tester's minor deviations among them, are
  listed in § Deferred.
- The panel includes at least what PLAYBOOK §6 requires for the risk `[FE4.panel]`; the panelists
  added for the diff are the orchestrator's call, and the report says why.

### Re-check

- Only the FNDs and rows the brief names; each fixed or open, with the evidence; no new review.

## Phase 5 — After launch (`06-feedback.md` § Post-launch)

- Each `INS-###` has its source (the user, or a named channel of their users), the quote, the flow
  or page it hits, and the change it suggests. Nothing is paraphrased into a stronger claim.

## UI stop, Prototype stop and Acceptance

- UI stop (`design: new`): pages, frames and every DFB decision, shown for approval; frames then
  exported by `fe-ui`.
- Prototype stop: the prototype running on the real surface, the queue's observables, the earlier
  approved results this round may change (each with a recommendation), the decisions taken by
  default; on approval the observables and frame exports are locked. `[FE.observables]`
- Acceptance opens with the goal (Constitution §7.4): the change, the user's check, its result, and
  the demo's before and after at the goal's real entry point (`ORCHESTRATOR.md` § Demo). `[DEMO]`
- Acceptance: every active `[interface]` REQ delivered by a row verified done
  (`gates/traceability.md`). `[FEA.matrix]`
- Every `needs user` DFB carries the user's decision. `[FEA.feedback]`
- Every registered observable from earlier rounds still holds, unless the user retired it.
  `[FE.regression · FE.regression-captures]`
- Acceptance also shows what is unmeasured (e.g. never tried by a real user), the deferred minors,
  and what the user must do for it to be live. Constitution §6 holds in full.
