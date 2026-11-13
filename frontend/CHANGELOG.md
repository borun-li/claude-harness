# Frontend Agent Team — Changelog

Semver: patch = prompt/bar tuning · minor = new behaviour, role or lens · major = changed phase flow or artifact contract.

## 12.1.0 — 2026-11-12 — install leaves your files alone; gates stop recounting

Minor. Shared with backend 7.1.0.
- `install.sh` no longer replaces the whole `agents/` and `commands/` folders: it writes only the
  harness's files there, removes a file an earlier version installed once the harness stops
  shipping it (`~/.claude/.harness-files`), and leaves your own agents and commands alone.
- A gate counts a fix round only when the tree or the set of failing checks changed since its last
  failure; re-running on the same tree is not a round. Reports show both numbers
  (`consecutive_failures`, `failed_runs`).
- A green test suite on an unchanged tree with the same command is reused for
  `test_reuse_minutes` (default 30) instead of run again; a red one is always re-run.

## 12.0.0 — 2026-11-12 — the run log written by hooks

Major: the orchestrator's logging steps and the brief's first line change. Shared with backend 7.0.0.
- Hook `run-log.py` writes the run log: at each be-*/fe-* dispatch (`Agent`, or `SendMessage` to a
  finished agent) it marks the writer, or the panel's coordinator at the first reviewer after a gate
  run, and logs the dispatch; at each agent's handback and stop it logs the return, `blocked` when
  the report says so, with its Figma calls. Outside an active run it does nothing. The orchestrator
  no longer runs `mark`, `log dispatch` or `log return`; by hand only a dead agent's failed return.
- The brief's first line is `You are <agent> #<n> — step <s>, round <r>.`; the hook refuses a
  dispatch with no step, a round past `loops.max_rounds` (the cap is now enforced at the dispatch,
  not self-reported with `--redo`), a Figma role without its `Budget:` line, or a writer while the
  other team has one out, and gives the reason.
- Writers out at the same time are checked together (`ROLE.shared`): a change fails only if none of
  their roles may make it, instead of charging one writer with another's work.
- `TOOL.lint`, `TOOL.typecheck`, `TOOL.test`: a failing checker that printed neither findings nor a
  summary (it crashed or was not found) is reported as having no reading, separately from findings,
  and cannot be waived.
- Run-log appends are locked, so parallel dispatches keep the hash chain intact.

## 11.0.0 — 2026-11-12 — before and after at the real entry point

Major: a new artifact Acceptance requires. Shared with backend 6.0.0.
- Every Prototype and Full development run captures its goal at the real entry point before the
  first dispatch (`gate.py demo before`) and on the final code (`gate.py demo after`), from
  `<run-dir>/demo-plan.json`: a page and its steps (screenshot, DOM), a command (output, exit code,
  seconds) or files an instrument produced. The before is taken once; the after is retaken when the
  product changes.
- New Acceptance check `DEMO` in `p7` and `fe-accept`: fails when either capture is missing, the
  before was logged after the first dispatch, the product changed after the after, an entry point
  captured before is missing after, or the two are byte-identical. A cross-stack run keeps one demo
  in the backend run dir. Acceptance opens with the two side by side.
- Small change: the orchestrator captures its check before dispatching and shows it before and
  after when the user accepts.
- Web captures keep a screenshot of the page even when a step fails; terminal captures record
  seconds.
- Runs started before this version have no before; their `DEMO` needs the user's waiver.

## 10.1.0 — 2026-11-12 — a fix goes back to its author

Minor. Shared with backend 5.1.0.
- Constitution §8.1 amended: the author of work being fixed or revised may be continued into that
  step's next rounds while its context is still small, so it does not re-read what it already
  knows. Whoever judges the work (reviewers, verifiers) is always a fresh agent. The exception for
  an agent blocked on a question stays.
- The orchestrator sends a fix back to its author by `SendMessage`, still logged `log dispatch
  --redo`, with only the round, the items, their evidence and the files changed since it returned.
- `no-agent-continuation.py`: authors (`be-analyst`, `be-architect`, `be-developer`, `be-tester`,
  `fe-ux`, `fe-ui`, `fe-engineer`) may be continued up to `loops.max_rounds` times while their last
  request was at most `loops.continue_max_context` tokens (default 200000); judges once, to receive
  an answer. Refused → a fresh agent with the reading list.

## 10.0.0 — 2026-11-12 — a code map, a reading list, a handoff of the current state

Major: `handoff.md` changes from an append-only log to one section per role. Shared with backend 5.0.0.
- A code map, `docs/codemap.md`: one per project, shared by both teams, at most 200 lines; per
  module what it does, its entry, users, invariants, tests and traps. Every agent reads it before
  opening code. The first role that reads code creates it when it is missing; a role that adds,
  moves or renames a file, or changes a module's entry or invariants, updates it in the same round.
  It is a pointer, not evidence: the code wins and the agent fixes the map.
- The brief's reading list: `Read:` names the code map, then the `file:line` this item touches,
  from its design item, queue row or finding, and the last entry's `Next agent reads`. Agents read
  the items a brief names rather than whole documents, and name what they read beyond the list.
- `handoff.md` keeps the current state only: one section per role, that role's latest entry, plus
  the orchestrator's; a returning agent replaces its section, and the history is in git and the
  run log. Entries gain `Read beyond the list` and `Next agent reads`, at most 20 lines. The
  orchestrator trims a run still on the old append-only log.
- New gate checks on every gate run, both teams: `CTX.codemap` (every backticked path exists, within
  its cap; owed by the latest role that reads code, never by designers or reviewers) and
  `CTX.handoff` (one section per role, each within 20 lines). Caps: `doc_budgets.codemap_lines`,
  `doc_budgets.handoff_section_lines`.

## 9.3.0 — 2026-11-12 — report what the user can see, as it happens

Minor. Shared with backend 4.2.0.
- Each time a visible change passes its check, the orchestrator says so at once, without waiting
  for a stop: what changed, a link to the exact page on the preview, the steps to see it (no
  interface: the command and its output). The same line goes out as a `PushNotification`, which
  reaches the desktop, or the phone through Remote Control, when the user is away from the terminal.
- Every report, phase end and stop leads with what the user can see now that they could not
  before, or says that nothing new is visible yet and what is next; internal state comes last.
- Frontend §3J: a report per row that passes `fe-build`, instead of one line per batch.
- README: how to receive the notifications (desktop terminals, Remote Control on a phone) and how
  to keep a long run awake.

## 9.2.0 — 2026-11-12 — a newer decision replaces an older one; waiting never stops the team

Minor. Shared with backend 4.1.0.
- Constitution §5 amended: when the user's later words, the run's goal or a harness update
  contradict an earlier decision, an approved expected output or observable, or a test written to
  the earlier one, the team follows the newer one without asking: change, re-lock, record whose
  words and when, list it at the next stop. §2.5 and §5.1 point to it. Waivers stay the user's.
- Re-locking: `fixtures-approve --reapprove FX-nnn` and `fe-approve` (including `--retire`) take
  `--by orchestrator --because "<whose words, when>"`; `--by orchestrator` without `--because` is
  refused. The reason is stored with the lock and in the run log.
- A question that does not block the run's goal opens no dialog: the recommended default is taken,
  the question goes to `state.json` `open_questions` and the next report or stop. Before a blocking
  question, every piece of work that does not depend on it is dispatched first (dispatched agents
  keep running while a dialog is open).

## 9.1.0 — 2026-11-12 — show the user what answers the question

Minor. Backend 4.0.1 shares the ORCHESTRATOR rule.
- Every question to the user carries what answers it, chosen by the question rather than the
  phase: how it looks → Figma frames side by side; whether it works → a link to the exact page of
  the running product and the steps to try; no screen → a few lines; no interface → the real
  command and its output. Never a long document to read.
- UX stop: `fe-ux` draws one grey low-fidelity Figma wireframe per page and the stop shows those
  frames. One-stop runs and terminal surfaces keep text wireframes. `fe-ux` gains the Figma tools
  and joins the Figma budget (`--figma-left`, `figma_calls`); `per_page` 8 → 10.
  `FE1.wireframes` requires a `- **Wireframe:**` node link when `design_stops` is 2 on a canvas.
- A new screen or a changed look gets its Figma frame before code, also mid-build; a DFB the user
  decides is shown as that frame.
- The preview opens as is: the run's current code, seeded data, signed in or credentials given,
  at the page in question.

## 9.0.0 — 2026-11-12 — a goal per run, round caps, simplest thing that works

Major (`state.json` gains a required `goal`). Shared with backend 4.0.0.
- Constitution amended: every run ends with a change the user can observe (§1); principle §2.10
  "Simplest thing that works" for code and documents alike; every step has a round cap, going past
  it needs the user's yes (§5.4); done includes the run's goal met (§6.8); the user sets the goal
  with the tier, and it does not grow during the run (§7.4).
- Kickoff asks the goal with the tier: the change the user will observe and how they will check
  it. `state.json` `goal: {change, check}` is required (`ALL.state`); resuming a run without one
  asks for it. Acceptance opens with the goal and the user's check.
- One round cap, `loops.max_rounds` (default 2, per project in `.claude/frontend.json`), replaces
  `max_fix_rounds`. It counts redo dispatches (`log dispatch --redo`) per agent and step from the run log;
  past the cap `log dispatch` exits 3 until the user says yes
  (`log human --stop conditional --decision approved --step <s>`), which grants another cap.
  Gate fix rounds use the same cap (was 3). `timeline` ends with a `Rounds used` line.
- `state.json` no longer carries `loops`.

## 8.5.0 — 2026-11-11 — runs work on a branch and open a draft PR

Minor. Shared with backend 3.8.0.
- The git hook takes a role. The main session (`--role orchestrator`, from the run commands) may
  create a branch at HEAD, switch to an existing branch when the tree is clean, stage by path,
  commit, push the run's branch, open a draft PR and mark it ready, and delete a merged branch
  with `git branch -d`. Agents (`--role agent`) do no git writes. No role means agent.
- Both roles are denied force and history rewrites: `push --force`/`--force-with-lease`/`+ref`,
  pushing the default branch, `branch -D`, `switch -C`, `rebase`, `commit --amend`/`--no-verify`/`-a`,
  `git add -A`/`.`/`-u`, `gh pr merge`, and non-GET `gh api`.
- Push and PR need `"git": {"push": true}` in the project's `.claude/gates.json`.
- Commands inside `bash -c "…"` / `eval` are checked; a quoted `-C` directory no longer hides
  the subcommand.
- ORCHESTRATOR § Git: one run, one branch, one PR; commit after each passed gate and human stop;
  draft PR at the first push, ready at Acceptance; unrelated work gets its own PR.

## 8.4.1 — 2026-11-11 — gate fixes: JUnit report location, shared fixtures

Patch. Shared with backend 3.7.1.
- The JUnit report the gates read is written outside the project (system temp directory), no
  longer to `<run-dir>/gates/junit.xml`, so the project's own tests never see it.
- A fixture declared by several REQs is tied to all of them: `PLAN.meta` accepts any of them in
  `meta.json`, and the plan review sheet lists them all. The result no longer varies between runs.
- Tests for both.

## 8.4.0 — 2026-11-09 — safety hooks act only in harness sessions

Minor. Shared with backend 3.7.0.
- The three safety hooks are declared in frontmatter, no longer in the global `settings.json`:
  every `be-*` / `fe-*` agent carries the git and process hooks; `/route`, `/backend`,
  `/frontend`, `/backend-resume` and `/frontend-resume` carry all three for the session that runs them.
- `install.sh` no longer registers hooks and removes the entries earlier versions added to
  `settings.json`; other settings are untouched.
- New `hooks/test_hook_scoping.py`: every agent and run command declares its hooks; the
  `settings.json` cleanup keeps the user's own hooks.
- ORCHESTRATOR Boundaries: a run continued in a reopened session goes through a `-resume` command.
- README: where the hooks apply; Uninstall no longer edits `settings.json`.

## 8.3.1 — 2026-11-08 — public changelog; neutral comments

Patch, wording only. Shared with backend 3.6.1.
- `CHANGELOG.md` lists what changed in each version, nothing else.

## 8.3.0 — 2026-11-08 — review converges: minor deviations, rework judges the named defect

Minor.
- A row is done when it matches its observable, frame and state rows in everything the person doing
  its task would notice; differences visible only side by side go under the new § Minor deviations
  (template, example, `minor:` in the return).
- A rework round fails a row only if the named defect still shows or the fix broke something;
  anything newly seen is judged by the rule above.
- `fe-reviewer` files minor deviations as minor FNDs in § Deferred. PLAYBOOK Phase 4 re-judges only
  the named defects. No gate change.

## 8.2.0 — 2026-11-08 — row ids unique per project; OBS guards for any language

Minor.
- `fe-queue` gains `FE2.row-ids`: a `Q-###` already used in another frontend run dir fails, naming
  the next free id. Template: ids continue across rounds.
- A test proves a row by carrying its `Q-###` in its name or title (`fe-tester`, `[FE4.row-tests]`).
  JUnit id matching accepts Go subtest names (`TestRows/Q-003_cards`) and rejects `Q-0031` (shared
  with backend).
- `fe-promote` registers unparsed tests as `{file, tag: Q-###}`; `FE.regression` requires a passing
  JUnit case carrying the id. Older entries with an empty test list are guarded by the row id in
  their `source`.
- Tests: `RowIds`, `Registry`, `IdInName`.

## 8.1.0 — 2026-11-08 — agents stop only processes they started

Minor. Shared with backend 3.5.0: new hook `no-foreign-process-kill.py`; Constitution §4.6 amended.

## 8.0.1 — 2026-11-07 — agent files trimmed

Patch, wording only; see backend 3.4.1.

## 8.0.0 — 2026-11-07 — a running prototype before the build; fewer questions

Major (phase flow).
- Constitution: §2.7 the prototype runs (fake data allowed) and a visual design is confirmed first;
  §5.4 a cap with only minors left defers them; §6 design-only clause removed.
- Design input `new | external | reused`; an external design runs Phase 1E intake, with no UX/UI stop.
- New Phase 2b prototype (`fe-engineer`, product code on fake data) and a fixed Prototype stop, where
  observables and retirements are approved; the UI stop confirms the look only. §3J preview.
- Kickoff asks the tier and missing facts and previews models, risk, stops and budget. Only `fe-ui`
  and `fe-engineer` call Figma; `fe-engineer` names earlier approved results the round may change.
- Gates: exit `4` while the other team has a writer out; marks may precede dispatches until the next
  gate; `--figma-left` required; intake forms accepted; trail requires the Prototype stop before the
  build; `fe-review` before `fe-verify`.
- PLAYBOOK rewritten and shortened.

## 7.2.6 — 2026-11-03 — stale wording and examples

Patch.
- PLAYBOOK `## 2. Kickoff`; Phase 0 means product features only; `fe-engineer` owns the contract draft.
- Examples follow the bars (no colour in UX, one page = one design stop, system font stack, capture
  names `@1440`, requirements § Assumptions).
- Contract ids `C-001`; queue template Scaffold covers one-stop runs; UI template has a `Dark` column.
- `FE4.panel` checks the risk's minimum panel. `commands/frontend.md` names the agents' "Called
  directly" rules.

## 7.2.5 — 2026-11-03 — one reading for each ambiguous rule

Patch.
- A cross-stack run keeps one handoff log, in the Backend run dir (`HANDOFF.md` §1).
- A DFB's raiser returns it; the orchestrator files it in `06-feedback.md`; the owner fills in the decision.
- Prototype tier includes Phase 0 in frontend-only runs and ends with `status: "prototype_confirmed"`.
- One-stop runs recompute the Figma budget after `fe-ux` and ask only if it grew.
- Config `design_stops` → `design_stop_rule`; `.claude/frontend.json` `artifacts.run_dir` sets the run dir.

## 7.2.4 — 2026-11-03 — conflicting descriptions that broke runs

Patch.
- §3H: `capture-plan.json` `sizes` are `{name, width, height}` objects (new `viewport_height`, 900);
  `fe-capture-plan` rejects bare widths.
- §2.4 reused design: log commands carry `--decision` and `--by`; the run starts at Phase 2 step 1 and
  a short UI stop confirms the new queue's observables.
- Rework rounds replace reworked rows' verdicts in place; `04-verification.md` points at the new manifest.
- `be-developer` in a frontend run builds from its `Side: backend` row. `/frontend-status` and
  `/frontend-resume` find a second round's run dir.

## 7.2.3 — 2026-11-03 — read-only agents return their handoff entry

Patch: `fe-review-experience`, `fe-review-accessibility`, `fe-review-integration` end with a
`handoff:` field (as backend 3.3.4).

## 7.2.2 — 2026-11-03 — agent files: one job, input, output, boundaries

Patch: the 8 `fe-*` agents and `be-analyst` follow the backend 3.3.3 structure (at most 48 lines).
Descriptions drop phase numbers and name the neighbouring role. `fe-engineer`'s coded-prototype rule
removed.

## 7.2.1 — 2026-11-03 — terminal prototypes stay in this PLAYBOOK

Patch (with backend 3.3.2): terminal surfaces are prototyped as text mockups up to the UI stop, not
via `route/PROTOTYPE.md`; §7 drops `prototype/`.

## 7.2.0 — 2026-11-03 — `/frontend-status`; commands follow Claude Code's guidance

Minor.
- New read-only `/frontend-status` replaces `/frontend status` (now a pointer), callable by the model.
- `/frontend-config` and `/frontend-resume` set `disable-model-invocation: true`.

## 7.1.0 — 2026-11-02 — design taste: type, spacing, icons, avoid-list

Minor (`design-taste` skill).
- §1: brand question covers typefaces; class table adds small screens, keyboard, dark mode, density,
  boldness.
- §3 empty states; §4 type, 4 px spacing scale, 4–6 px radius, icons (library set, else Lucide);
  §5 start Figma from the library's kit.
- §6 avoid-list of generic AI-design defaults; §7 checklist of 14 items; §8 how preferences are added.
- New `examples.md`. PLAYBOOK §2.3 and `fe-ui` say "brand (colours, typefaces)".

## 7.0.0 — 2026-11-02 — product, UX, UI, engineering; Figma; review panel

Major: roles, phase flow and every artifact contract.
- `fe-designer` split into `fe-ux` and `fe-ui`; `fe-critic` removed (`be-analyst` writes product
  features in Phase 0); `fe-engineer` also scaffolds, checks feasibility, drafts the contract, writes
  the queue.
- Flow: Kickoff → 0 features → 1 UX → UX stop → 2 UI ‖ scaffold → queue → UI stop → 3 build →
  4 verify ‖ review panel → fixes → Acceptance → 5 after launch. Modes `new`, `redesign`, `audit`,
  `review`, `implement` retired.
- §3A design feedback (`DFB-###`, `06-feedback.md`); §1E Figma with a per-run call budget
  (`--figma-calls`, `FE.figma`, `--stop Budget`); §3B increments.
- §6 review panel: `fe-review-experience`, `fe-review-accessibility`, `fe-review-integration`, merged
  by `fe-reviewer`.
- Artifacts `00-requirements` … `06-feedback`, `evidence/design/FRAME-###.png`. Gates `fe-product`,
  `fe-ux`, `fe-ui`, `fe-queue`, `fe-plan`, `fe-approve`, `fe-build`, `fe-capture-plan`, `fe-verify`,
  `fe-review`, `fe-accept`; stops `UX`, `UI`, `Budget`.
- Shared: `route/FRONTEND_BACKEND_LINE.md`; Constitution amended with backend 3.3.0 (§2.7, §3.2, §5.1,
  §5.5, §6). 6.x runs are not resumed.

## 6.1.0 — 2026-10-31 — context discipline; constitution made stable

Shared with backend 3.1.0: Constitution §8, `route/HANDOFF.md`, `ORCHESTRATOR.md`, hook
`no-agent-continuation.py`. A dead agent is replaced by a fresh one from its handoff entry; rework uses
a fresh engineer per row and a fresh `fe-tester`. Log `docs/frontend/handoff.md`. Constitution §5 simplified.

## 6.0.0 — 2026-10-18 — run tiers and Phase 1b prototype

Shared with backend 3.0.0: Constitution §7 tiers asked first at kickoff; Phase 1b prototype with a
fixed Prototype stop; `fe-accept` trail check enforces the order when `tier: "full"`.

## 5.5.0 — 2026-09-24 — The user's design taste as a skill

- New skill `design-taste` (usability, fewest steps, in-place feedback, brand colours, dark mode,
  never-list, review checklist).
- Kickoff (§2.4) confirms class, brand colours, motion, copy tone unless `project-context.md` has them;
  `fe-designer` and `fe-critic` use the skill.

## 5.4.0 — 2026-09-23 — Approved-observable registry

- `docs/frontend/observables.json`: `fe-promote` registers verified rows as `OBS-###`, guarded by a
  test or a planned capture.
- `FE.regression` and `FE.regression-captures` check later rounds; `fe-plan` lists affected
  observables; `fe-approve --retire`. PLAYBOOK §3I.

## 5.3.0 — 2026-09-23 — Parity with the backend's checks

- `FE7.dependencies`, `FEA.matrix` (`gates/traceability.md`), `FE1.source`.
- Item length limits via `doc_budgets`. Templates and examples updated.

## 5.2.0 — 2026-09-23 — Scripted evidence capture

- `gate.py capture --round <n>` from `docs/frontend/capture-plan.json` (§3H): web via playwright-core,
  terminal output bytes, manual files stamped.
- Gates `fe-capture-plan` and `FE8.capture`. Dependency `~/.claude/gates/node_modules/playwright-core`.

## 5.1.1 — 2026-09-23 — JS test results

- `FE8.row-tests`: tests tagged with a queue row id must pass; JS runners report per test.

## 5.1.0 — 2026-09-23 — Gates, approved observables, run log (batch 2)

- Frontend gates in `gatelib/frontend.py` (`fe-brief` … `fe-accept`); shared commands take `--team frontend`.
- Role rules per agent; `fe-approve` hashes rows and `FE.observables` detects changes; `LOG.valid` and
  trail check.
- Run dir moved to `docs/frontend/`. New `/frontend-config`, `/frontend-resume`.
- Fixed: `baseline` counted the other team's run dir as user work; spec example missing states.

## 5.0.0 — 2026-09-23 — Frontend aligned with the backend harness (batch 1)

- PLAYBOOK, QUALITY-BARS, command, README and the four `fe-*` agents rewritten in English, shorter.
- §4b replaced by Constitution §5 plus PLAYBOOK §3F. Stops G0–G4 → Plan and Acceptance.
- Artifacts `01-brief` … `06-verification`; templates in `templates/examples/`. Old names still read.
- Removed: checklists/, workflows/, model-registry-reference.md, 9 templates, retrospective phase.
- Template placeholders `<…>` → `{…}`.

## 4.0.0 — 2026-09-22 — renamed: uiux → frontend

Rename only.
- `/uiux` → `/frontend`; `~/.claude/uiux/` → `~/.claude/frontend/`; `ux-critic`/`ux-designer` →
  `fe-critic`/`fe-designer`; `wf-*` → `be-*`.
- Artifact paths, `.claude/frontend.json`, `team/frontend-team-config.md`, `FRONTEND_*.md`, config key
  `artifacts.frontend_dir`; legacy names still read.

## 3.0.0 — 2026-09-09 — four roles; no assumed browser

Major.
- Four roles: `ux-critic`, `ux-designer`, `fe-engineer`, `fe-tester`; dispatch lines fixed; one role
  registry in `config.json`; duties map in PLAYBOOK §1B.
- `observable` means what a person perceives on the running interface; `delivery_surface` slot (§1C).
- Shared rules moved from role prompts to `QUALITY-BARS.md` §Phase 7; new bar: assertions red on
  broken behaviour, green on copy changes.

## 2.0.0 — 2026-08-29 — implementation, verification and rework phases

Major.
- New Phases 6–8: implementation queue, build by `wf-developer`, browser verification, rework capped
  at 2 rounds; retrospective renumbered to 9.
- New mode `implement`; artifacts `IMPLEMENTATION_QUEUE.md`, `VERIFICATION_REPORT.md`;
  `checklists/verification.md`.
- Queue rows are per design problem with an observable result; `不可观察` verdict; spec defects don't
  consume a rework round.
- §4b automation policy: rule and log by default; three stop conditions.

## 1.0.0 — 2026-08-29 — first release

- Seven roles, one command, five gates, four review lenses.
- `ux-auditor` and `ux-reviewer` have no Write/Edit; model registry shared with waterfall.
- Per-project `team/` pointer; orchestrator captures evidence into `uiux/evidence/`.
- `未定义` placeholder in state matrices; `[ASSUMPTION]` label carried downstream; blocking finding
  forbids "complete".

## 1.0.1 — 2026-08-29 — researcher questions asked by the orchestrator

- `ux-researcher` produces the questions; the orchestrator asks them at G1 (PLAYBOOK §3 Phase 1,
  `agents/ux-researcher.md`).

## 1.0.2 — 2026-08-29 — write each artifact as it finishes

- PLAYBOOK §4: agents write each artifact when done; the orchestrator checks the filesystem before
  recovering.

## 3.0.0 — 2026-08-30 — four roles and a Router

Major.
- Roles: `ux-critic` (also rules on findings), `ux-designer`, `fe-engineer`, `fe-tester`.
- Model tier by judgement: opus for judgement, sonnet for execution.
- Frontend code moved from `wf-developer` to `fe-engineer`.
- New Router (frontend / backend / cross-stack, classified from code) and capability ledger.
- P1/P2/P3 severity required on findings; frontend/backend line written per project before work.
