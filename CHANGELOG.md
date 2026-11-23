# Changelog

Semver: patch = prompt or bar tuning · minor = new behaviour or new role · major = changed phase
flow, artifact contract, run layout or command line.

## 16.0.0 — 2026-11-21 — one run, one configuration, parallel writers

Major: the run layout, the configuration files, the commands and the command line change. The
backend (10.0.0) and frontend (15.0.0) version lines end here: the harness has one version.

**One run**
- A run is one directory, `docs/runs/<slug>/`, with one `state.json` (new key `scope`: `backend`,
  `frontend` or `cross-stack`), one run log, one handoff, one baseline, one demo and one
  acceptance, whichever teams work in it. `docs/backend/` and `docs/frontend/`, the second
  `state.json` and run log of a cross-stack run, and every rule about "the other team's run" are gone.
- `gate.py`: `--team` and `--run-dir` are removed; `--run <slug>` names the run when a project has
  several open.
- One `state.json` schema (`route/HANDOFF.md` §8). The statuses `prototyping`, `building`,
  `verifying` and `fix_capped` are removed; the step says where a run is.
- `fe-plan` writes `gates/fe-plan-review.md` and `fe-accept` writes `gates/fe-traceability.md`
  (`p2` and `p7` keep `plan-review.md` and `traceability.md`). The approved-observable registry is
  `docs/observables.json`.

**One configuration, one version, four commands**
- `harness/config.json` replaces `backend/config.json` and `frontend/config.json`: one `models`
  table (tiers × every role, `floor`, `adjust`), `review` panels, `loops`, the frontend's design
  stops, Figma budget and viewports, and `artifacts.run_dir`. The user's own defaults are
  `~/.claude/harness-local/config.json`; a project's are `.claude/harness.json`. A layer names
  only the keys it changes: keys merge two levels deep.
- `/route`, `/route-resume`, `/route-status` and `/route-config` replace `/backend`, `/frontend`
  and their `-resume`, `-status` and `-config` pairs.
- One `CHANGELOG.md`; the two teams' histories are kept below.

**Parallel writers**
- The run's tree has one writer at a time. Writers that are out together are dispatched with
  `isolation: "worktree"`: each works in a git worktree of its own, from the run's last commit
  (`ORCHESTRATOR.md` § Parallel).
- `gate.py land` puts each return on the run's branch as one commit per agent, with no merge
  commits: an in-tree writer's work is committed; an isolated writer's changes are checked against
  its role, merged with the run's branch in its worktree and committed on top of it. Lines two writers both changed stay in the later author's worktree with git's markers
  for that author to settle, outside the round count; run documents and the code map keep both
  sides' lines. The orchestrator no longer stages and commits writers' returns by hand.
- A gate is busy only while a writer is out in the run's tree or a return is not landed; isolated
  writers still out do not hold it. Role checks for isolated writers happen at `land`;
  `ROLE.shared` and the rule that kept one team's writers out at a time are removed.
- The two sides of a seam written in the contract build at the same time; so do frontend build
  groups, backend developer groups and the tester planning tests.
- A continued author keeps its worktree, brought up to the run's branch first.
- `gate.py worktrees` lists them; `--setup --link <dirs>` writes `worktree.baseRef: "head"` and
  the shared dependency directories into the project's `.claude/settings.json`; `--clean` removes
  the landed ones.
- Run log: `dispatch` gains `isolated`, `head` and `brief`; `return` gains `worktree` and
  `dispatch`; new event `land`. By hand: `log dispatch --isolated` (replaces `--parallel`),
  `log return --worktree <path>`. A return is paired with its dispatch by the brief's hash, so two agents of one type out
  together are told apart.

**Taste measures**
- A web capture also writes `<capture>.page.json`: the page's font families, text sizes, corner
  radii, gradient backgrounds and dialogs open at once, read from the rendered page.
- For a product whose `product_class` is `tool` (new optional key in `state.json` and the
  configuration), `gate.py capture` and `fe-verify` print where a page differs from the new
  `taste` values in `harness/config.json` (`FE4.taste`). The lines are reported for the reviewer
  and the user and fail nothing; a null value leaves a measure out.

**Upgrading a project**
- Move the keys of `.claude/backend.json` and `.claude/frontend.json` into `.claude/harness.json`
  (models are under `models`); `git mv docs/frontend/observables.json docs/observables.json`.
  `gate.py` names what it finds.
- Finished runs under `docs/backend/` and `docs/frontend/` stay as history; ids continue only
  from runs under `docs/runs/`, so move a finished run there to keep its numbering going. A run
  still in progress is finished on the version that started it, or abandoned.

**Documentation**
- The README is shorter: what it is, how it works in six points, the prerequisites, the quick
  start and a table of the tiers. The details it held (what install changes, each tier, hooks,
  branches, configuration, upgrading) are in the new `GUIDE.md`.
- `skills/design-taste`: each rule carries its reason; motion, radius and spacing have exact
  values; each generic model default is listed with what to do instead; three lines (who, their
  most frequent task, its step count) are written before any screen; no harness-only terms, so
  the skill also works outside a run.

---

# Before 16.0.0 — Backend team

### 10.0.0 — 2026-11-21 — fewer and warmer dispatches, visible changes, one round counter

Major: the phase flow, the round counting, the waiver store and the run-log format change. Shared with frontend 15.0.0.
Constitution amended (§7.1, §7.4, §8.1, §8.3) on the user's instruction of 2026-11-21.

**Fewer dispatches**
- New tier **Standard change** (`route/STANDARD.md`, gates `std-build` and `std-accept`): plan,
  build, tests, one review, acceptance, with one document (`plan.md`); three to five dispatches.
- **Small change:** one engineer reads the code, returns its plan, and builds it on the user's yes;
  the orchestrator no longer reads the code first.
- Frontend build goes out in groups (rows of one page or sharing a file), not one row per
  dispatch; groups that share no file go out in one message. A backend design that splits into
  groups sharing no file may go to one developer per group.
- A review with one panelist has no coordinator: the panelist returns the report.

**Fewer cold starts**
- Constitution §8.1: the author of a piece of work keeps it for fixes, revisions and its role's
  next step, while its context is under `loops.continue_max_context` (now 150000); judges are new
  every time. The PLAYBOOKs no longer ask for a fresh author anywhere; the continuation hook no
  longer caps an author's continuations by count.
- Agent files ask for the items the brief names, not whole documents; the handoff rule says so
  outranks any "read X" in an agent file.
- The code map may be an index with one file per module; a pitfall that outlives the round goes
  into the module's `Traps`.

**What each agent changed**
- A writer's return is logged with the files it changed (added, modified, deleted, line counts),
  its `user_visible` line, its time and tokens; its full report is saved under
  `<run-dir>/logs/returns/`. The timeline shows dates and these summaries.
- Writers return `user_visible`; the handoff entry has a `Visible:` line.
- The orchestrator commits each writer's return on its own and reports it in one line.
- `gate.py status` (step, open dispatches, gate verdicts, rounds, last changes, next ordinals) and
  `gate.py stats` (time, tokens, waiting, gate failures by owner).

**Rounds**
- One counter, in the run log, per item of the brief's `Only:` line. The dispatch hook infers a
  redo from the log whatever round the brief claims. Gates count nothing and never exit 3; exit 5
  means the gate itself crashed.
- `gate.py check <gate>`: a read-only self-check authors run before returning (the git hook allows
  sub-agents this one call). The code-map and handoff checks run at build, verification and
  acceptance gates only.

**Checks that passed what was wrong**
- A role failure (`ROLE.*`, the reviews' tree checks) stays until the file is put back or planned;
  dispatching its owner again no longer clears it.
- A finding is closed only when its status starts with fixed, resolved or accepted; `not fixed`,
  `unresolved` and an unfilled template line are open.
- Waivers are `waive` events in the run log (`gate.py waive`), tied to one gate and to the failure
  the user saw; `waivers.json` is no longer read and fails `CTRL.waivers-file`. `.claude/**` is no
  longer a document: `ROLE.control` fails any agent that changes it, and `CTRL.files` fails when an
  agent changed a gate's own files while it was out.
- Approved fixtures' manifest and the active requirements at Plan are recorded in the log
  (`P7.scope`); a baseline cannot be retaken after work started without `--rebaseline`.
- Writers out together are found by overlapping dispatch intervals, not by the order of marks.
- Capture plans are checked per row, state and width; source globs must match files; a terminal
  capture records its exit code.

**Checks that failed what was right**
- Report verdicts, test modes, Figma node ids, colour literals, evidence references and word
  budgets are read more tolerantly; code-map tokens are checked only when they are paths.
- A repeated mark no longer fails `LOG.trail`; marks can be voided. Test reuse ignores documents
  and run dirs; snapshots cache hashes. `commands.fe_test`, when set, is what `fe-build` runs.
- A suite that ran red without a parsable summary is `CMD.test`, not `TOOL.test`; the profile says
  what to configure for runners without per-test results.
- A run log line holding U+2028, U+2029 or U+0085 no longer breaks the log.

**Goals that keep behaviour**
- `goal.kind: "preserve"`: the demo's before and after may match; tests removed with their code
  are listed as retired and not counted as drift.

**Hooks and install**
- The guards run on Python 3.9, see commands inside `bash -lc`, substitutions and after
  redirections, and no longer stop `grep git` or a project's own `gate.py`. The main session may
  run only the git writes a run needs.
- A return with no logged dispatch is reported (the session has no run hooks). Hooks find the
  project root through git.
- `install.sh`: the user's own defaults live in `~/.claude/harness-local/` and are never touched;
  hooks are installed file by file; an edited `design-taste` is kept; a failed `npm ci` fails the
  install; versions are checked; `--uninstall`.
- Config: nested gate keys merge key by key; `artifacts.run_dir` works for both teams; `floor`
  roles are refused below their model; unread keys removed; status `abandoned`.

### 9.0.0 — 2026-11-21 — unused config and old-layout support removed

Major: projects on pre-7.0 layouts or with the removed keys must move to the current ones. Shared with frontend 14.0.0.
- **Removed config keys nothing read:** backend `artifacts`, `gates` (the human stops are fixed,
  PLAYBOOK §3F), `policy`, `parallelism.design_review` / `build_test_design_in_parallel` /
  `review_coordinator`, `language.confirm_at_kickoff`; frontend `artifacts` except `run_dir`,
  `backend_team`, `gates`, `parallelism`, `frontend_backend_boundary`, `language.confirm_at_kickoff`.
  The frontend `_comment` now carries the model rule.
- **Removed support for pre-7.0 layouts and runs:** run dirs `docs/waterfall`, `docs/uiux`, `uiux`; a
  top-level `run_dir` in `.claude/frontend.json` (use `artifacts.run_dir`); `05-queue.md`;
  `contracts/CAPABILITY_LEDGER.md`; `team/frontend-team-config.md` and the `team/**` doc glob; design
  at step 3 in the backend trail; the pre-8.0 exemption from the Prototype stop; registry entries with
  no guarding tests (they now fail `FE.regression`); `/frontend status`; the installer's list of
  agents retired before its manifest.
- README runs every hook test with one loop; a gate docstring no longer names a project.

### 8.1.1 — 2026-11-21 — rules for shared files, varying results and the user's choices

Patch. Shared with frontend 13.1.1.
- Testers never edit build or dependency manifests or runner config; they name the change for the
  engineer, and a brief never assigns a file outside the role's scope.
- Requirements: a REQ whose result varies run to run states its tries, deciding rule and must-pass /
  must-fail examples (`Varies`); behaviour where a wrong default harms the user is asked at the first
  stop with the conservative default; a choice the user made is never written as its opposite.
- Tests choose what runs by an explicit switch, never by probing for a service.
- The orchestrator records the user's answers in their words, option text included, and cites them
  in the briefs they touch.
- Fixes: `/backend` starts at PLAYBOOK §2; the Prototype procedure uses the common round cap; the
  README names all three Figma agents.

### 8.1.0 — 2026-11-21 — parsers read fields, checks compare only what they ask about

Minor. Shared with frontend 13.1.0.
- **Parsers read the field a rule is about.** A finding's status comes from its `**Status:**` line
  (not the first "status" in its text); a DES's REQs from `**Serves:**`, a TC's from `**Verifies:**`,
  a page's from its REQ cell, so a REQ mentioned in passing is not a claim. A REQ an earlier run
  defined counts as known in designs, tests, findings, pages and queue rows; coverage still counts
  this run's.
- **A test report keeps one verdict per TC.** Rows that disagree fail `P5.report-complete` with both
  verdicts, instead of the last row winning. `p7` reads the report as it is now.
- **`fe-verify` judges the evidence round the header names**, or else the latest round mentioned.
- **The code map checks paths only**: backticked relative paths and file names; symbols, routes and
  commands are not checked.
- **Snapshots ignore what no agent changes.** Review tree checks skip every run dir (the other team's
  log included); `volatile_globs` (default `**/*.log`) lists files the running product rewrites, left
  out of every snapshot; `LICENSE*`, `NOTICE*`, `COPYING*` are documents. A capture or demo plan may
  name `source` globs, and only those files make its evidence stale.
- **No check while a writer is out.** Phase gates, `capture` and `demo` exit 4 while a writer of this
  run is dispatched and not returned, as they already did for the other team's.

### 8.0.0 — 2026-11-21 — no false greens, a run log that follows the run

Major: `waivers.json` gains `tests` for test-reporting checks. Shared with frontend 13.0.0.
- **Waivers name their tests.** A waiver of a check that reports failing tests (`CMD.test`,
  `P5.tc-results`) lists them in `tests`; it covers only those, so a new failure, a fallen test
  total or more skips still fails. A waiver without `tests` no longer covers such a check.
- **Not checked is not passed.** Every gate ends with its pass / fail / waived / not-checked counts
  and names each `N/A` check. `P5.report-honest` is `N/A` when the run observed no per-test
  results, instead of accepting every reported pass. A reused green test run is shown on a pass too,
  with the time it ran.
- **Subagents cannot run the gates.** The git hook denies an agent any command that executes
  `gate.py`; marks, rounds and approvals are the orchestrator's.
- **Analysts and architects have a file scope** (`ROLE.doc-scope`): documents, plus fixture
  candidates for the analyst; checked at `p1`, `p2` and `fe-product`. A role with no rules no longer
  lets every change through when writers are out together.
- **The run log follows the run.** Hook entries go to the open run, also a second feature's
  `docs/<team>/<slug>/`; two open runs of one team refuse the dispatch until one is closed. A `be-*`
  agent working in a frontend-only run (Phase 0, backend-side rows) logs in the frontend run, and a
  return goes to the run that holds its dispatch.
- **Continuations are logged** before the message is sent, by the continuation hook, and count
  against the round cap like any dispatch; the `PostToolUse(SendMessage)` hook is gone.
- **An event the hook could not log is reported** to the orchestrator and the user at once.
- **`log void --seq <n>`** takes a wrong entry out of every count (the log stays append-only). A
  manual `log dispatch` that copies an open one is refused (`--parallel` for a second agent out on
  purpose), and so is a `log return` with no open dispatch.

### 7.1.0 — 2026-11-12 — install leaves your files alone; gates stop recounting

Minor. Shared with frontend 12.1.0.
- `install.sh` no longer replaces the whole `agents/` and `commands/` folders: it writes only the
  harness's files there, removes a file an earlier version installed once the harness stops
  shipping it (`~/.claude/.harness-files`), and leaves your own agents and commands alone.
- A gate counts a fix round only when the tree or the set of failing checks changed since its last
  failure; re-running on the same tree is not a round. Reports show both numbers
  (`consecutive_failures`, `failed_runs`).
- A green test suite on an unchanged tree with the same command is reused for
  `test_reuse_minutes` (default 30) instead of run again; a red one is always re-run.

### 7.0.0 — 2026-11-12 — the run log written by hooks

Major: the orchestrator's logging steps and the brief's first line change. Shared with frontend 12.0.0.
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

### 6.0.0 — 2026-11-12 — before and after at the real entry point

Major: a new artifact Acceptance requires. Shared with frontend 11.0.0.
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

### 5.1.0 — 2026-11-12 — a fix goes back to its author

Minor. Shared with frontend 10.1.0.
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

### 5.0.0 — 2026-11-12 — a code map, a reading list, a handoff of the current state

Major: `handoff.md` changes from an append-only log to one section per role. Shared with frontend 10.0.0.
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

### 4.2.0 — 2026-11-12 — report what the user can see, as it happens

Minor. Shared with frontend 9.3.0.
- Each time a visible change passes its check, the orchestrator says so at once, without waiting
  for a stop: what changed, a link to the exact page on the preview, the steps to see it (no
  interface: the command and its output). The same line goes out as a `PushNotification`, which
  reaches the desktop, or the phone through Remote Control, when the user is away from the terminal.
- Every report, phase end and stop leads with what the user can see now that they could not
  before, or says that nothing new is visible yet and what is next; internal state comes last.
- Frontend §3J: a report per row that passes `fe-build`, instead of one line per batch.
- README: how to receive the notifications (desktop terminals, Remote Control on a phone) and how
  to keep a long run awake.

### 4.1.0 — 2026-11-12 — a newer decision replaces an older one; waiting never stops the team

Minor. Shared with frontend 9.2.0.
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

### 4.0.1 — 2026-11-12 — questions carry what answers them

Patch. Shared ORCHESTRATOR rule with frontend 9.1.0: each question to the user carries what answers
it (Figma frames for looks, the running product for whether it works, a few lines otherwise; the
real command and its output without an interface), never a long document.

### 4.0.0 — 2026-11-12 — a goal per run, round caps, simplest thing that works

Major (`state.json` gains a required `goal`). Shared with frontend 9.0.0.
- Constitution amended: every run ends with a change the user can observe (§1); principle §2.10
  "Simplest thing that works" for code and documents alike; every step has a round cap, going past
  it needs the user's yes (§5.4); done includes the run's goal met (§6.8); the user sets the goal
  with the tier, and it does not grow during the run (§7.4).
- Kickoff asks the goal with the tier: the change the user will observe and how they will check
  it. `state.json` `goal: {change, check}` is required (`ALL.state`); resuming a run without one
  asks for it. Acceptance opens with the goal and the user's check.
- One round cap, `loops.max_rounds` (default 2, per project in `.claude/backend.json`), replaces
  `max_gate_fix_rounds` and `max_fix_rounds_after_review`. It counts redo dispatches (`log dispatch --redo`) per agent and step from the run log;
  past the cap `log dispatch` exits 3 until the user says yes
  (`log human --stop conditional --decision approved --step <s>`), which grants another cap.
  Gate fix rounds use the same cap (was 3). `timeline` ends with a `Rounds used` line.
- `state.json` no longer carries `loops`.

### 3.8.0 — 2026-11-11 — runs work on a branch and open a draft PR

Minor. Shared with frontend 8.5.0.
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

### 3.7.1 — 2026-11-11 — gate fixes: JUnit report location, shared fixtures

Patch. Shared with frontend 8.4.1.
- The JUnit report the gates read is written outside the project (system temp directory), no
  longer to `<run-dir>/gates/junit.xml`, so the project's own tests never see it.
- A fixture declared by several REQs is tied to all of them: `PLAN.meta` accepts any of them in
  `meta.json`, and the plan review sheet lists them all. The result no longer varies between runs.
- Tests for both.

### 3.7.0 — 2026-11-09 — safety hooks act only in harness sessions

Minor. Shared with frontend 8.4.0.
- The three safety hooks are declared in frontmatter, no longer in the global `settings.json`:
  every `be-*` / `fe-*` agent carries the git and process hooks; `/route`, `/backend`,
  `/frontend`, `/backend-resume` and `/frontend-resume` carry all three for the session that runs them.
- `install.sh` no longer registers hooks and removes the entries earlier versions added to
  `settings.json`; other settings are untouched.
- New `hooks/test_hook_scoping.py`: every agent and run command declares its hooks; the
  `settings.json` cleanup keeps the user's own hooks.
- ORCHESTRATOR Boundaries: a run continued in a reopened session goes through a `-resume` command.
- README: where the hooks apply; Uninstall no longer edits `settings.json`.

### 3.6.1 — 2026-11-08 — public changelog; neutral comments

Patch, wording only.
- `CHANGELOG.md` lists what changed in each version, nothing else.
- Hook docstrings and deny messages keep the design rationale only; hook test cases renamed.
- README Contributing: record what changed, without project names.

### 3.6.0 — 2026-11-08 — TC ids unique per project; ids found in any language's test names

Minor. Shared with frontend 8.2.0.
- `p4` gains `P4.tc-ids`: a `TC-###` already headed in another backend run dir's `04-test-plan.md` fails, naming the next free id. Template: TC ids continue across features.
- be-tester and QUALITY-BARS: a test carries its `TC-###` in its name or title; the JUnit match accepts `TestX/TC-003_case` and rejects `TC-0031`.

### 3.5.0 — 2026-11-08 — agents stop only processes they started

Minor.
- New hook `hooks/no-foreign-process-kill.py` (PreToolUse on Bash), registered by `install.sh`. Denies `pkill`/`killall`, `fuser -k`/`kill-port`, a process lookup (`pgrep`, `pidof`, `lsof`, `ps` except `ps -p`) combined with `kill`, and `kill` of 0, -1 or a negative PID. Allows `kill <pid>`, `kill $!`, `kill "$VAR"`, `kill %1`, `kill $(cat <pidfile>)`, lookups alone, and quoted/heredoc text. The deny message gives the PID-file pattern.
- New `hooks/test_no_foreign_process_kill.py` (43 cases).
- Constitution §4.6: a process you start is yours; record its PID and stop only that PID.
- `ORCHESTRATOR.md` Boundaries and the root README name the hook.

### 3.4.1 — 2026-11-07 — PLAYBOOK and agents trimmed

Patch, wording only.
- PLAYBOOK shortened (2,596 → 1,389 words); rules held by gates or `ORCHESTRATOR.md` are cited, not retold; section numbers kept.
- Agent descriptions shortened (shared with frontend 8.0.1); repeated handoff/long-output/"no gates" lines now cite `HANDOFF.md`. No role rule changed.

### 3.4.0 — 2026-11-07 — fewer questions to the user; shared 8.0 changes

Minor.
- Constitution §2.7, §5.4, §6 amended (see frontend 8.0.0).
- Kickoff asks only the tier (and missing frontend facts); model plan, risk and gate profile are shown with defaults. The gate profile is confirmed by running its commands.
- Phase 1b for an interface is the Frontend team's run up to its Prototype stop; `route/PROTOTYPE.md`, `FRONTEND_BACKEND_LINE.md` §4 and `/route` updated.
- Phase 6 cap: minor survivors are deferred and listed; only blockers, majors and failing TCs of in-scope REQs escalate.
- `ORCHESTRATOR.md`: ask only what is the user's to decide; process decisions are logged and shown at the next stop; product questions batched; self-caused failures re-run, never waived; exit `4`; one writer at a time across teams. `HANDOFF.md`: Budget line is the `--figma-left` number.
- Gates (shared): busy exit `4`, mark-order trail fix, `--figma-left`.

### 3.3.8 — 2026-11-03 — `compileall -f`

Patch.
- `gate.py profile` writes `compileall -f` for Python projects.
- `BuildGate.test_build_failure` pins the broken file's mtime; the profile test asserts `-f`.
- Existing `.claude/gates.json` is not rewritten; add `-f` via `/backend-config`.

### 3.3.7 — 2026-11-03 — stale wording and examples

Patch.
- README: sixteen agents; single-page design stop; `CLAUDE_HOME` for test installs only.
- `07-acceptance.md` gains § Frontend items and a Prototype sign-off line.
- Detailed-design example lists the script its build order names.
- `HANDOFF.md` §6: roles without Write put long output in a scratch file outside the tree.
- `capture` finds Chrome or Chromium on PATH when the macOS app is absent. Test added.

### 3.3.6 — 2026-11-03 — one reading for each ambiguous rule

Patch.
- Phase 5 runs only `fe-tester` for frontend items; the frontend panel joins the backend panel in Phase 6.
- `mark --role be-reviewer` before each panel and each re-check, not before the coordinator; no mark for Phase 1b.
- `be-architect`'s `user_decisions` are shown at Plan with a default (§3F).
- `NN-deferred.md` → `deferred.md`, written by the orchestrator.
- `be-tester` plans from the contract's seam entries too.
- Kickoff (and `route.md` §0) asks frontend design stops and Figma budget when the interface is touched.
- `config.json` `gates` lists Kickoff, Prototype, Plan, Acceptance for reference only; `G0_*` keys removed.
- Roles without Write return their handoff entry. `p2` checks `P2.prototype-first`. Test added.

### 3.3.5 — 2026-11-03 — conflicting descriptions fixed

Patch.
- `--run-dir` is a path from the project root (`docs/backend/<slug>`).
- Phase 4 marks `be-tester` first and `be-developer` last.
- Phase 6.4: the orchestrator files the re-check table in `06-review-report.md` §5 (new) and sets each confirmed FND's `Status`.
- `be-analyst` output comment fixed (no "stopped after §0").
- Gates: `log` and `timeline` no longer need a confirmed `gates.json`; `timeline` writes `run-log.md` only if the run dir exists; `baseline` ignores `prototype/`; `ROLE.unplanned` accepts files named in `03-queue.md`. Tests added.
- `/backend-status` and `/backend-resume` find additional `docs/backend/<slug>/` dirs.

### 3.3.4 — 2026-11-03 — read-only agents return their handoff entry

Patch.
- `be-reviewer`, the three `be-review-*` and the three `fe-review-*` end their output block with a `handoff:` field naming the agent and how to number the entry.

### 3.3.3 — 2026-11-03 — agent files: one job, input, output, boundaries

Patch. All 16 agent files (shared with frontend) rewritten.
- Structure: frontmatter, Constitution line, `Your ONLY job is …`, `## Input`, `## Output`, `## Boundaries`; rules held elsewhere are cited.
- Descriptions say what, when, and which neighbour it is not; no phase numbers.
- Direct calls: user's words set scope, no gates, entry to `docs/handoff.md`; `be-tester` without requirements tests current behaviour.
- `handoff: <entry header>` sits in the output block.
- `fe-engineer` no longer builds coded prototypes; `route/PROTOTYPE.md` is `be-developer`'s.

### 3.3.2 — 2026-11-03 — route docs agree on who prototypes what

Patch.
- Every human-operated interface, terminal included, is prototyped by the Frontend PLAYBOOK up to its UI stop. `route/PROTOTYPE.md` covers only work with no such interface (APIs, scripts, CLI arguments, jobs), built by `be-developer` in `docs/backend/`. `commands/route.md` §3, PLAYBOOK Phase 1b and READMEs updated.
- `route/FRONTEND_BACKEND_LINE.md` §4 and §7 clarified (`frontend_items` scope).

### 3.3.1 — 2026-11-03 — commands follow Claude Code's command guidance

Patch.
- `/backend-config` and `/backend-resume` set `disable-model-invocation: true`.
- `/backend-status` is read-only by tool (`disallowed-tools`), preloads `state.json` and the last 15 timeline events, and lists the Prototype stop.

### 3.3.0 — 2026-11-02 — shared line file; be-analyst as the product role

Shared with frontend 7.0.0.
- §3C moved to `~/.claude/route/FRONTEND_BACKEND_LINE.md` (cited as §3C.n); adds frontend designers (`fe-ux`, `fe-ui`), the cross-stack table (§4) and finer fix routing.
- `be-analyst` writes product features in frontend-only runs (`00-requirements.md`, gate `fe-product`).
- Gates: role checks ignore the other team's run dir and, for `fe-*`, the fixtures dirs; shared `_trail_common`.
- Constitution §2.7, §3.2, §5.1, §5.5, §6 amended; backend behaviour unchanged.

### 3.2.0 — 2026-11-02 — one design phase, review panel with a coordinator, depth by risk

- Phase 2 — Design replaces Phases 2, 3 and 3b: one `be-architect` dispatch writes `02-architecture.md` and `03-detailed-design.md`; `risk: high` adds a design review and one revision; a fresh `be-analyst` writes fixture answers. Plan stop ends the phase.
- Gates: `p2` absorbs `p3` and `plan` and writes `plan-review.md`; `p3`, `plan` removed; `fixtures-approve` needs green `p2`; `P7.gates` requires `p1 p2 p4 p5 p6`; `LOG.trail` and `ALL.state` (`risk`) updated.
- Review: new `be-review-behavior`, `be-review-reliability`, `be-review-security` in parallel; `be-reviewer` becomes the coordinator (merges, disproves, ranks `FND-###`, re-checks fixed findings only). Blockers and majors go to fix rounds; minors deferred. Old lenses retired.
- Risk: `state.json` `risk: high | normal`; normal trims the panel by what the diff touches (PLAYBOOK §6).
- Kickoff: one `AskUserQuestion` for tier, model plan, risk, gate profile; `language.default_docs: "user"`; `prototype: "reused"`.
- §3B Increments replaces Re-baseline: mid-run requirement changes join at the next fixed stop as `## Increment <n>` sections; `state.json` gains `increments`.
- PLAYBOOK and QUALITY-BARS trimmed; agents and templates `06-review-report.md`, `07-acceptance.md` aligned.

### 3.1.0 — 2026-10-31 — context discipline; constitution made stable

- Constitution §8 Context discipline (fresh agent per dispatch, short briefs, handoff entries, long output to files) and §9 Amendments (stable section numbers); Constitution made roster- and path-free; §2.3, §2.8, §2.9, §4.6 added.
- New `route/HANDOFF.md` (brief and entry formats, `logs/`).
- Fix rounds are fresh dispatches naming only failing items; `/backend-resume` starts from the last orchestrator handoff entry.
- New `ORCHESTRATOR.md` holding shared orchestrator rules; PLAYBOOKs point to it. Team agents do not dispatch.
- `/route` gets `when_to_use`; `/backend` and `/frontend` set `disable-model-invocation: true`.
- New hook `hooks/no-agent-continuation.py` (PreToolUse on SendMessage): a finished agent may be continued once.
- Constitution §5 Decision Rules simplified: decide, log, continue; only four cases stop the run. `be-analyst` no longer stops in Phase 1.

### 3.0.0 — 2026-10-18 — run tiers and Phase 1b prototype

- Constitution §7 run tiers: Small change / Prototype / Full development, asked of the user. `commands/route.md` §4 and `route/PROTOTYPE.md`.
- Constitution §2.7: new Phase 1b and a fixed Prototype stop in Full development.
- Gates: `log human --stop Prototype`; `LOG.trail` tier rules; `ALL.state` validates `tier`.
- `be-developer`, `fe-engineer`: rules for Prototype and Small change dispatches.

### 2.7.4 — 2026-09-24 — route-classifier removed

- `agents/route-classifier.md` deleted; `/route` classifies from code facts and the contract's capability table.
- Capability ledger merged into the contract; legacy `contracts/CAPABILITY_LEDGER.md` still read.
- Constitution §3: orchestrators classify tasks (`/route`).

### 2.7.3 — 2026-09-23 — JUnit for JS test runners (shared gates)

- Per-test results for vitest, playwright and jest (jest-junit), including via `npm run`/`pnpm`/`yarn`; other runners via `gates.json` `"junit"`. Vitest summary fallback.
- Test ids (`TC-`, `FX-`, `Q-`) recognised in JS test titles and preceding comments.

### 2.7.2 — 2026-09-23 — shared-gate changes for the frontend

- `baseline` excludes both teams' run dirs.
- `LOG.trail` treats `fe-engineer` like `be-developer`.
- §3C.4 points at `docs/frontend/05-queue.md`.

### 2.7.1 — 2026-09-23 — frontend alignment touch-ups

- §3C.4 points at `frontend/05-queue.md`; frontend observables shown at Plan.
- Template placeholders `<…>` → `{…}`; gates treat both as unfilled.

### 2.7.0 — 2026-09-23 — Run log (control panel)

- `<run-dir>/run-log.jsonl`: append-only, hash-chained; gates write `gate`/`mark`/`approve`; orchestrator writes events via `gate.py log`; `gate.py timeline` renders `run-log.md`.
- `LOG.valid` on every gate; `LOG.trail` in P7.
- PLAYBOOK §3G; `/backend-status` shows the timeline; `/backend-resume` treats unreturned dispatches as unverified.

### 2.6.0 — 2026-09-23 — Two human stops; concise, understood requirements

- Human stops reduced to Plan and Acceptance (PLAYBOOK §3F); config `gates`: `Plan`, `Acceptance`.
- Gate `gf` renamed `plan` (`PLAN.*`); writes `plan-review.md`.
- be-analyst writes §0 Understanding; every REQ needs a `Source` field quoting the user or citing an artifact.
- Templates 01–03 rewritten as skeletons with worked examples in `templates/examples/`.
- New gates `P1.understanding`, `P1.source`, `P1.req-length`, `P2.length`, `P3.des-length`, `P1/P2/P3.prose`; limits in `doc_budgets`.
- Fixed: headings inside fenced code split DES blocks.

### 2.5.0 — 2026-09-23 — Approved fixtures

- PLAYBOOK §3E and Phase 3b: per-REQ `Fixtures:` declarations; human gate GF; `fixtures-approve --by <user>` locks answers.
- Gates: `P1.fixtures`, `gf`, `fixtures-approve` (`--reapprove`), `P4/P5.fixtures`, `P5.fixtures-used`, Fixtures column in the P7 matrix.
- Fixed: `baseline` counting the run's own files; fixture data under `tests/` counting as a test reference.

### 2.4.1 — 2026-09-23 — tidy-up, no behaviour change

- QUALITY-BARS tags gate-backed bars with gate ids.
- be-* agent files slimmed.
- Commands `/backend`, `/backend-status`, `/backend-resume`, `/backend-config` updated.
- Fixed YAML frontmatter in `backend-resume.md`, `backend-config.md`, `frontend.md`.
- README rewritten.

### 2.4.0 — 2026-09-23 — Computational gates

- New `~/.claude/gates/` (`gate.py profile | p1 | p2 | p3 | baseline | mark | p4 | p5 | p6 | p7`); exit 0/1/2/3; regression suite in `gates/tests/`.
- `mark` snapshots before each writing dispatch; role rules per agent diff.
- `p4`/`p5` re-run build/lint/typecheck/tests and check counts, skips, dependencies, secrets, TC tags, fixture hashes.
- Fix loop capped by `loops.max_gate_fix_rounds` (3); waivers need `approved_by` + `date`.
- PLAYBOOK §3D, §2.2/2.3, §4.7; `state.json` gains `gates`; templates gain `Cut:`, `Side:`, design §9 Dependencies.

### 2.3.0 — 2026-09-23 — Constitution adopted

- New `~/.claude/CONSTITUTION.md`, overriding PLAYBOOK, QUALITY-BARS, agents and prompts.
- Every agent, command and PLAYBOOK opens with "Read CONSTITUTION.md first".
- Duplicated rules removed in favour of the Constitution; PLAYBOOK §4 renumbered.

### 2.2.0 — 2026-09-23 — PLAYBOOK + QUALITY-BARS slimmed (11,703 → 3,201 words)

- Rules reduced to one or two lines; duplicates merged; §3A to 15 items; section anchors kept.
- L2/L3 staged bars removed.
- `state.json` gains `frontend_items`; layout lists `NN-deferred.md`.
- `no-tree-restoring-git.py` reference updated to §3A.11.

### 2.1.0 — 2026-09-23 — be-developer builds backend only

- `be-developer` builds backend only (PLAYBOOK §0).
- New PLAYBOOK §3C: default frontend/backend line; `DES` tagged `side: backend | frontend`; Frontend team dispatched within the run.
- `be-analyst` tags `[interface]` requirements; `be-developer` returns `frontend_items`.
- New QUALITY-BARS L1 bars in Phases 1, 3, 4/5 and 7.

### 2.0.0 — 2026-09-22 — renamed: waterfall → backend

Major (artifact paths).
- `/waterfall*` → `/backend`, `/backend-status`, `/backend-resume`, `/backend-config`.
- `~/.claude/waterfall/` → `~/.claude/backend/`; agents `wf-*` → `be-*`.
- `docs/waterfall/` → `docs/backend/`, `.claude/waterfall.json` → `.claude/backend.json`; legacy paths still read (PLAYBOOK §1 rule 4).

### 1.10.0 — let it be wrong, and watch what turns red

- QUALITY-BARS Phase 4/5: an assertion counts only after it has been made to fail; a negative result needs a positive control; tests are fed by the producer production uses; guards are judged by false-positive rate too.
- QUALITY-BARS Phase 6: the reviewer breaks every guard it relies on.
- QUALITY-BARS Phase 1: a scope exclusion states whether it is deferred or not ours.
- PLAYBOOK §3A.16 (acceptance criteria can be wrong) and §3A.17 (reading a description instead of the code).
- Agents: satisfying a wrong criterion is worse than failing it.

### 1.9.0 — the git ban becomes a hook

- New `~/.claude/hooks/no-tree-restoring-git.py` (PreToolUse on Bash) denies tree-restoring git commands; new `test_no_tree_restoring_git.py` (27 cases).
- PLAYBOOK §3A.13 (no writing agent on a dirty tree), §3A.14 (enforcement by hook), §3A.15 (record self-disclosure).
- Agents gain the mutation-testing protocol (cp → mutate → cp back → `cmp` → `rm`).
- QUALITY-BARS Phase 2: change-footprint answer must be an executable test; Phase 6 re-measures it.

### 1.8.0 — 2026-08-25 — measurement bars

- QUALITY-BARS Phase 4/5: failed runs are flagged and excluded, failure rate reported; non-deterministic systems reported as mean, range and run count, with systematic vs intermittent errors; answer-key values must be reachable from the input.
- PLAYBOOK §3A.11: long work writes each unit to disk with resume; no agent waits on its own background job.
- PLAYBOOK §3A.12: verify by artifact, never by exit code.

### 1.7.0 — 2026-08-19 — proportion

- MVP cut line promoted to L1: the round is the simplest common path of what the user asked; each requirement justified from the user's words.
- Phase 6: reviewers rank only what breaks a requirement above the cut line; the rest goes to `NN-deferred.md`.
- Phase 7: deferred findings may not be bundled into a fix round.
- PLAYBOOK §2.1a: the cut line is written before Phase 1 is dispatched.

### 1.6.0 — 2026-08-18 — declarations vs observations

- Phase 4/5 L1: an observation-named field (`reason`, `basis`, `evidence`, `source`, `note`) must vary across two differing inputs, or be renamed.
- Phase 6 L1: a diagnosis resting on an artifact string requires locating its producer in code.
- PLAYBOOK §3A rule 9 rewritten: claims about work in flight carry their evidence.

### 1.5.0 — 2026-08-18 — `quality` tier

- `quality` tier: `wf-developer` sonnet → opus.

### 1.0.0 — 2026-08-09 — initial harness

- 5 roles (`wf-analyst`, `wf-architect`, `wf-developer`, `wf-tester`, `wf-reviewer`) orchestrated by `/waterfall`.
- 7-phase waterfall with parallel work inside phases 2, 4 and 6.
- Human gates G1, G2, G3; per-role model plan with tiers (quality / balanced / economy / max).
- Traceability `REQ → DES → code → TC → FND` (`policy.require_traceability_ids`).
- L1 quality bars plus staged L2/L3; resumable runs via `docs/waterfall/state.json`.

### 1.1.0 — 2026-08-10 — three L1 bars

- Phase 3: a completeness assertion may not be derived from the output it checks.
- Phase 4/5: fixtures include the legitimately-absent shape; tests reach their subject through its real entry point.
- Phase 6: coverage is claimed by behaviour, and a test counts only if it can fail.

### 1.2.0 — 2026-08-12 — five L1 bars; orchestrator discipline

- Phase 3: every guard declares what makes it fire and not fire.
- Phase 4/5: claims about external systems verified under production-shaped input.
- Phase 6: reachability judged from the user's entry point; declared non-goals verified absent.
- Phase 6/7: a number carries its composition and measurement conditions.
- New PLAYBOOK §3A orchestrator discipline.

### 1.3.0 — 2026-08-13 — operator bars; re-baseline

- Phase 3: catch-all branches state what they do not claim; a sentinel has one predicate; durable references survive recomputation.
- Phase 4/5: test against state from earlier versions; click every control once on real data; a non-deterministic producer yields a sample; real end-to-end integration test promoted to L1.
- Phase 6: completion and accuracy are separate claims; deferral names the user path. Phase 7: name what makes delivered work live.
- New review lens `operator-experience` (`parallelism.review_lenses`).
- PLAYBOOK §3A rules 6–7, §3B re-baseline procedure, §2.2 LLM model benchmarking.

### 1.4.0 — 2026-08-14 — verification bars

- Phase 4/5: fetch every URL a delivered page references; fix where the defect is; a pass verdict names its assertion; overrides of a requirement are logged as deviations.
- Phase 6: a multi-source assertion must fail for each source.
- PLAYBOOK §3A rule 2 sharpened (change X, do not remove it); new rules 8 (user's report outranks analysis) and 9 (no unmeasured precision).

---

# Before 16.0.0 — Frontend team

### 15.0.0 — 2026-11-21 — fewer and warmer dispatches, visible changes, one round counter

Major: the phase flow, the round counting, the waiver store and the run-log format change. Shared with backend 10.0.0.
Constitution amended (§7.1, §7.4, §8.1, §8.3) on the user's instruction of 2026-11-21.

**Fewer dispatches**
- New tier **Standard change** (`route/STANDARD.md`, gates `std-build` and `std-accept`): plan,
  build, tests, one review, acceptance, with one document (`plan.md`); three to five dispatches.
- **Small change:** one engineer reads the code, returns its plan, and builds it on the user's yes;
  the orchestrator no longer reads the code first.
- Frontend build goes out in groups (rows of one page or sharing a file), not one row per
  dispatch; groups that share no file go out in one message. A backend design that splits into
  groups sharing no file may go to one developer per group.
- A review with one panelist has no coordinator: the panelist returns the report.

**Fewer cold starts**
- Constitution §8.1: the author of a piece of work keeps it for fixes, revisions and its role's
  next step, while its context is under `loops.continue_max_context` (now 150000); judges are new
  every time. The PLAYBOOKs no longer ask for a fresh author anywhere; the continuation hook no
  longer caps an author's continuations by count.
- Agent files ask for the items the brief names, not whole documents; the handoff rule says so
  outranks any "read X" in an agent file.
- The code map may be an index with one file per module; a pitfall that outlives the round goes
  into the module's `Traps`.

**What each agent changed**
- A writer's return is logged with the files it changed (added, modified, deleted, line counts),
  its `user_visible` line, its time and tokens; its full report is saved under
  `<run-dir>/logs/returns/`. The timeline shows dates and these summaries.
- Writers return `user_visible`; the handoff entry has a `Visible:` line.
- The orchestrator commits each writer's return on its own and reports it in one line.
- `gate.py status` (step, open dispatches, gate verdicts, rounds, last changes, next ordinals) and
  `gate.py stats` (time, tokens, waiting, gate failures by owner).

**Rounds**
- One counter, in the run log, per item of the brief's `Only:` line. The dispatch hook infers a
  redo from the log whatever round the brief claims. Gates count nothing and never exit 3; exit 5
  means the gate itself crashed.
- `gate.py check <gate>`: a read-only self-check authors run before returning (the git hook allows
  sub-agents this one call). The code-map and handoff checks run at build, verification and
  acceptance gates only.

**Checks that passed what was wrong**
- A role failure (`ROLE.*`, the reviews' tree checks) stays until the file is put back or planned;
  dispatching its owner again no longer clears it.
- A finding is closed only when its status starts with fixed, resolved or accepted; `not fixed`,
  `unresolved` and an unfilled template line are open.
- Waivers are `waive` events in the run log (`gate.py waive`), tied to one gate and to the failure
  the user saw; `waivers.json` is no longer read and fails `CTRL.waivers-file`. `.claude/**` is no
  longer a document: `ROLE.control` fails any agent that changes it, and `CTRL.files` fails when an
  agent changed a gate's own files while it was out.
- Approved fixtures' manifest and the active requirements at Plan are recorded in the log
  (`P7.scope`); a baseline cannot be retaken after work started without `--rebaseline`.
- Writers out together are found by overlapping dispatch intervals, not by the order of marks.
- Capture plans are checked per row, state and width; source globs must match files; a terminal
  capture records its exit code.

**Checks that failed what was right**
- Report verdicts, test modes, Figma node ids, colour literals, evidence references and word
  budgets are read more tolerantly; code-map tokens are checked only when they are paths.
- A repeated mark no longer fails `LOG.trail`; marks can be voided. Test reuse ignores documents
  and run dirs; snapshots cache hashes. `commands.fe_test`, when set, is what `fe-build` runs.
- A suite that ran red without a parsable summary is `CMD.test`, not `TOOL.test`; the profile says
  what to configure for runners without per-test results.
- A run log line holding U+2028, U+2029 or U+0085 no longer breaks the log.

**Goals that keep behaviour**
- `goal.kind: "preserve"`: the demo's before and after may match; tests removed with their code
  are listed as retired and not counted as drift.

**Hooks and install**
- The guards run on Python 3.9, see commands inside `bash -lc`, substitutions and after
  redirections, and no longer stop `grep git` or a project's own `gate.py`. The main session may
  run only the git writes a run needs.
- A return with no logged dispatch is reported (the session has no run hooks). Hooks find the
  project root through git.
- `install.sh`: the user's own defaults live in `~/.claude/harness-local/` and are never touched;
  hooks are installed file by file; an edited `design-taste` is kept; a failed `npm ci` fails the
  install; versions are checked; `--uninstall`.
- Config: nested gate keys merge key by key; `artifacts.run_dir` works for both teams; `floor`
  roles are refused below their model; unread keys removed; status `abandoned`.

### 14.0.0 — 2026-11-21 — unused config and old-layout support removed

Major: projects on pre-7.0 layouts or with the removed keys must move to the current ones. Shared with backend 9.0.0.
- **Removed config keys nothing read:** backend `artifacts`, `gates` (the human stops are fixed,
  PLAYBOOK §3F), `policy`, `parallelism.design_review` / `build_test_design_in_parallel` /
  `review_coordinator`, `language.confirm_at_kickoff`; frontend `artifacts` except `run_dir`,
  `backend_team`, `gates`, `parallelism`, `frontend_backend_boundary`, `language.confirm_at_kickoff`.
  The frontend `_comment` now carries the model rule.
- **Removed support for pre-7.0 layouts and runs:** run dirs `docs/waterfall`, `docs/uiux`, `uiux`; a
  top-level `run_dir` in `.claude/frontend.json` (use `artifacts.run_dir`); `05-queue.md`;
  `contracts/CAPABILITY_LEDGER.md`; `team/frontend-team-config.md` and the `team/**` doc glob; design
  at step 3 in the backend trail; the pre-8.0 exemption from the Prototype stop; registry entries with
  no guarding tests (they now fail `FE.regression`); `/frontend status`; the installer's list of
  agents retired before its manifest.
- README runs every hook test with one loop; a gate docstring no longer names a project.

### 13.1.1 — 2026-11-21 — rules for shared files, varying results and the user's choices

Patch. Shared with backend 8.1.1.
- Testers never edit build or dependency manifests or runner config; they name the change for the
  engineer, and a brief never assigns a file outside the role's scope.
- Requirements: a REQ whose result varies run to run states its tries, deciding rule and must-pass /
  must-fail examples (`Varies`); behaviour where a wrong default harms the user is asked at the first
  stop with the conservative default; a choice the user made is never written as its opposite.
- Tests choose what runs by an explicit switch, never by probing for a service.
- The orchestrator records the user's answers in their words, option text included, and cites them
  in the briefs they touch.
- Fixes: `/backend` starts at PLAYBOOK §2; the Prototype procedure uses the common round cap; the
  README names all three Figma agents.

### 13.1.0 — 2026-11-21 — parsers read fields, checks compare only what they ask about

Minor. Shared with backend 8.1.0.
- **Parsers read the field a rule is about.** A finding's status comes from its `**Status:**` line
  (not the first "status" in its text); a DES's REQs from `**Serves:**`, a TC's from `**Verifies:**`,
  a page's from its REQ cell, so a REQ mentioned in passing is not a claim. A REQ an earlier run
  defined counts as known in designs, tests, findings, pages and queue rows; coverage still counts
  this run's.
- **A test report keeps one verdict per TC.** Rows that disagree fail `P5.report-complete` with both
  verdicts, instead of the last row winning. `p7` reads the report as it is now.
- **`fe-verify` judges the evidence round the header names**, or else the latest round mentioned.
- **The code map checks paths only**: backticked relative paths and file names; symbols, routes and
  commands are not checked.
- **Snapshots ignore what no agent changes.** Review tree checks skip every run dir (the other team's
  log included); `volatile_globs` (default `**/*.log`) lists files the running product rewrites, left
  out of every snapshot; `LICENSE*`, `NOTICE*`, `COPYING*` are documents. A capture or demo plan may
  name `source` globs, and only those files make its evidence stale.
- **No check while a writer is out.** Phase gates, `capture` and `demo` exit 4 while a writer of this
  run is dispatched and not returned, as they already did for the other team's.

### 13.0.0 — 2026-11-21 — no false greens, a run log that follows the run

Major: `waivers.json` gains `tests` for test-reporting checks. Shared with backend 8.0.0.
- **Waivers name their tests.** A waiver of a check that reports failing tests (`CMD.test`,
  `P5.tc-results`) lists them in `tests`; it covers only those, so a new failure, a fallen test
  total or more skips still fails. A waiver without `tests` no longer covers such a check.
- **Not checked is not passed.** Every gate ends with its pass / fail / waived / not-checked counts
  and names each `N/A` check. `P5.report-honest` is `N/A` when the run observed no per-test
  results, instead of accepting every reported pass. A reused green test run is shown on a pass too,
  with the time it ran.
- **Subagents cannot run the gates.** The git hook denies an agent any command that executes
  `gate.py`; marks, rounds and approvals are the orchestrator's.
- **Analysts and architects have a file scope** (`ROLE.doc-scope`): documents, plus fixture
  candidates for the analyst; checked at `p1`, `p2` and `fe-product`. A role with no rules no longer
  lets every change through when writers are out together.
- **The run log follows the run.** Hook entries go to the open run, also a second feature's
  `docs/<team>/<slug>/`; two open runs of one team refuse the dispatch until one is closed. A `be-*`
  agent working in a frontend-only run (Phase 0, backend-side rows) logs in the frontend run, and a
  return goes to the run that holds its dispatch.
- **Continuations are logged** before the message is sent, by the continuation hook, and count
  against the round cap like any dispatch; the `PostToolUse(SendMessage)` hook is gone.
- **An event the hook could not log is reported** to the orchestrator and the user at once.
- **`log void --seq <n>`** takes a wrong entry out of every count (the log stays append-only). A
  manual `log dispatch` that copies an open one is refused (`--parallel` for a second agent out on
  purpose), and so is a `log return` with no open dispatch.

### 12.1.0 — 2026-11-12 — install leaves your files alone; gates stop recounting

Minor. Shared with backend 7.1.0.
- `install.sh` no longer replaces the whole `agents/` and `commands/` folders: it writes only the
  harness's files there, removes a file an earlier version installed once the harness stops
  shipping it (`~/.claude/.harness-files`), and leaves your own agents and commands alone.
- A gate counts a fix round only when the tree or the set of failing checks changed since its last
  failure; re-running on the same tree is not a round. Reports show both numbers
  (`consecutive_failures`, `failed_runs`).
- A green test suite on an unchanged tree with the same command is reused for
  `test_reuse_minutes` (default 30) instead of run again; a red one is always re-run.

### 12.0.0 — 2026-11-12 — the run log written by hooks

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

### 11.0.0 — 2026-11-12 — before and after at the real entry point

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

### 10.1.0 — 2026-11-12 — a fix goes back to its author

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

### 10.0.0 — 2026-11-12 — a code map, a reading list, a handoff of the current state

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

### 9.3.0 — 2026-11-12 — report what the user can see, as it happens

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

### 9.2.0 — 2026-11-12 — a newer decision replaces an older one; waiting never stops the team

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

### 9.1.0 — 2026-11-12 — show the user what answers the question

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

### 9.0.0 — 2026-11-12 — a goal per run, round caps, simplest thing that works

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

### 8.5.0 — 2026-11-11 — runs work on a branch and open a draft PR

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

### 8.4.1 — 2026-11-11 — gate fixes: JUnit report location, shared fixtures

Patch. Shared with backend 3.7.1.
- The JUnit report the gates read is written outside the project (system temp directory), no
  longer to `<run-dir>/gates/junit.xml`, so the project's own tests never see it.
- A fixture declared by several REQs is tied to all of them: `PLAN.meta` accepts any of them in
  `meta.json`, and the plan review sheet lists them all. The result no longer varies between runs.
- Tests for both.

### 8.4.0 — 2026-11-09 — safety hooks act only in harness sessions

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

### 8.3.1 — 2026-11-08 — public changelog; neutral comments

Patch, wording only. Shared with backend 3.6.1.
- `CHANGELOG.md` lists what changed in each version, nothing else.

### 8.3.0 — 2026-11-08 — review converges: minor deviations, rework judges the named defect

Minor.
- A row is done when it matches its observable, frame and state rows in everything the person doing
  its task would notice; differences visible only side by side go under the new § Minor deviations
  (template, example, `minor:` in the return).
- A rework round fails a row only if the named defect still shows or the fix broke something;
  anything newly seen is judged by the rule above.
- `fe-reviewer` files minor deviations as minor FNDs in § Deferred. PLAYBOOK Phase 4 re-judges only
  the named defects. No gate change.

### 8.2.0 — 2026-11-08 — row ids unique per project; OBS guards for any language

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

### 8.1.0 — 2026-11-08 — agents stop only processes they started

Minor. Shared with backend 3.5.0: new hook `no-foreign-process-kill.py`; Constitution §4.6 amended.

### 8.0.1 — 2026-11-07 — agent files trimmed

Patch, wording only; see backend 3.4.1.

### 8.0.0 — 2026-11-07 — a running prototype before the build; fewer questions

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

### 7.2.6 — 2026-11-03 — stale wording and examples

Patch.
- PLAYBOOK `## 2. Kickoff`; Phase 0 means product features only; `fe-engineer` owns the contract draft.
- Examples follow the bars (no colour in UX, one page = one design stop, system font stack, capture
  names `@1440`, requirements § Assumptions).
- Contract ids `C-001`; queue template Scaffold covers one-stop runs; UI template has a `Dark` column.
- `FE4.panel` checks the risk's minimum panel. `commands/frontend.md` names the agents' "Called
  directly" rules.

### 7.2.5 — 2026-11-03 — one reading for each ambiguous rule

Patch.
- A cross-stack run keeps one handoff log, in the Backend run dir (`HANDOFF.md` §1).
- A DFB's raiser returns it; the orchestrator files it in `06-feedback.md`; the owner fills in the decision.
- Prototype tier includes Phase 0 in frontend-only runs and ends with `status: "prototype_confirmed"`.
- One-stop runs recompute the Figma budget after `fe-ux` and ask only if it grew.
- Config `design_stops` → `design_stop_rule`; `.claude/frontend.json` `artifacts.run_dir` sets the run dir.

### 7.2.4 — 2026-11-03 — conflicting descriptions that broke runs

Patch.
- §3H: `capture-plan.json` `sizes` are `{name, width, height}` objects (new `viewport_height`, 900);
  `fe-capture-plan` rejects bare widths.
- §2.4 reused design: log commands carry `--decision` and `--by`; the run starts at Phase 2 step 1 and
  a short UI stop confirms the new queue's observables.
- Rework rounds replace reworked rows' verdicts in place; `04-verification.md` points at the new manifest.
- `be-developer` in a frontend run builds from its `Side: backend` row. `/frontend-status` and
  `/frontend-resume` find a second round's run dir.

### 7.2.3 — 2026-11-03 — read-only agents return their handoff entry

Patch: `fe-review-experience`, `fe-review-accessibility`, `fe-review-integration` end with a
`handoff:` field (as backend 3.3.4).

### 7.2.2 — 2026-11-03 — agent files: one job, input, output, boundaries

Patch: the 8 `fe-*` agents and `be-analyst` follow the backend 3.3.3 structure (at most 48 lines).
Descriptions drop phase numbers and name the neighbouring role. `fe-engineer`'s coded-prototype rule
removed.

### 7.2.1 — 2026-11-03 — terminal prototypes stay in this PLAYBOOK

Patch (with backend 3.3.2): terminal surfaces are prototyped as text mockups up to the UI stop, not
via `route/PROTOTYPE.md`; §7 drops `prototype/`.

### 7.2.0 — 2026-11-03 — `/frontend-status`; commands follow Claude Code's guidance

Minor.
- New read-only `/frontend-status` replaces `/frontend status` (now a pointer), callable by the model.
- `/frontend-config` and `/frontend-resume` set `disable-model-invocation: true`.

### 7.1.0 — 2026-11-02 — design taste: type, spacing, icons, avoid-list

Minor (`design-taste` skill).
- §1: brand question covers typefaces; class table adds small screens, keyboard, dark mode, density,
  boldness.
- §3 empty states; §4 type, 4 px spacing scale, 4–6 px radius, icons (library set, else Lucide);
  §5 start Figma from the library's kit.
- §6 avoid-list of generic AI-design defaults; §7 checklist of 14 items; §8 how preferences are added.
- New `examples.md`. PLAYBOOK §2.3 and `fe-ui` say "brand (colours, typefaces)".

### 7.0.0 — 2026-11-02 — product, UX, UI, engineering; Figma; review panel

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

### 6.1.0 — 2026-10-31 — context discipline; constitution made stable

Shared with backend 3.1.0: Constitution §8, `route/HANDOFF.md`, `ORCHESTRATOR.md`, hook
`no-agent-continuation.py`. A dead agent is replaced by a fresh one from its handoff entry; rework uses
a fresh engineer per row and a fresh `fe-tester`. Log `docs/frontend/handoff.md`. Constitution §5 simplified.

### 6.0.0 — 2026-10-18 — run tiers and Phase 1b prototype

Shared with backend 3.0.0: Constitution §7 tiers asked first at kickoff; Phase 1b prototype with a
fixed Prototype stop; `fe-accept` trail check enforces the order when `tier: "full"`.

### 5.5.0 — 2026-09-24 — The user's design taste as a skill

- New skill `design-taste` (usability, fewest steps, in-place feedback, brand colours, dark mode,
  never-list, review checklist).
- Kickoff (§2.4) confirms class, brand colours, motion, copy tone unless `project-context.md` has them;
  `fe-designer` and `fe-critic` use the skill.

### 5.4.0 — 2026-09-23 — Approved-observable registry

- `docs/frontend/observables.json`: `fe-promote` registers verified rows as `OBS-###`, guarded by a
  test or a planned capture.
- `FE.regression` and `FE.regression-captures` check later rounds; `fe-plan` lists affected
  observables; `fe-approve --retire`. PLAYBOOK §3I.

### 5.3.0 — 2026-09-23 — Parity with the backend's checks

- `FE7.dependencies`, `FEA.matrix` (`gates/traceability.md`), `FE1.source`.
- Item length limits via `doc_budgets`. Templates and examples updated.

### 5.2.0 — 2026-09-23 — Scripted evidence capture

- `gate.py capture --round <n>` from `docs/frontend/capture-plan.json` (§3H): web via playwright-core,
  terminal output bytes, manual files stamped.
- Gates `fe-capture-plan` and `FE8.capture`. Dependency `~/.claude/gates/node_modules/playwright-core`.

### 5.1.1 — 2026-09-23 — JS test results

- `FE8.row-tests`: tests tagged with a queue row id must pass; JS runners report per test.

### 5.1.0 — 2026-09-23 — Gates, approved observables, run log (batch 2)

- Frontend gates in `gatelib/frontend.py` (`fe-brief` … `fe-accept`); shared commands take `--team frontend`.
- Role rules per agent; `fe-approve` hashes rows and `FE.observables` detects changes; `LOG.valid` and
  trail check.
- Run dir moved to `docs/frontend/`. New `/frontend-config`, `/frontend-resume`.
- Fixed: `baseline` counted the other team's run dir as user work; spec example missing states.

### 5.0.0 — 2026-09-23 — Frontend aligned with the backend harness (batch 1)

- PLAYBOOK, QUALITY-BARS, command, README and the four `fe-*` agents rewritten in English, shorter.
- §4b replaced by Constitution §5 plus PLAYBOOK §3F. Stops G0–G4 → Plan and Acceptance.
- Artifacts `01-brief` … `06-verification`; templates in `templates/examples/`. Old names still read.
- Removed: checklists/, workflows/, model-registry-reference.md, 9 templates, retrospective phase.
- Template placeholders `<…>` → `{…}`.

### 4.0.0 — 2026-09-22 — renamed: uiux → frontend

Rename only.
- `/uiux` → `/frontend`; `~/.claude/uiux/` → `~/.claude/frontend/`; `ux-critic`/`ux-designer` →
  `fe-critic`/`fe-designer`; `wf-*` → `be-*`.
- Artifact paths, `.claude/frontend.json`, `team/frontend-team-config.md`, `FRONTEND_*.md`, config key
  `artifacts.frontend_dir`; legacy names still read.

### 3.0.0 — 2026-09-09 — four roles; no assumed browser

Major.
- Four roles: `ux-critic`, `ux-designer`, `fe-engineer`, `fe-tester`; dispatch lines fixed; one role
  registry in `config.json`; duties map in PLAYBOOK §1B.
- `observable` means what a person perceives on the running interface; `delivery_surface` slot (§1C).
- Shared rules moved from role prompts to `QUALITY-BARS.md` §Phase 7; new bar: assertions red on
  broken behaviour, green on copy changes.

### 2.0.0 — 2026-08-29 — implementation, verification and rework phases

Major.
- New Phases 6–8: implementation queue, build by `wf-developer`, browser verification, rework capped
  at 2 rounds; retrospective renumbered to 9.
- New mode `implement`; artifacts `IMPLEMENTATION_QUEUE.md`, `VERIFICATION_REPORT.md`;
  `checklists/verification.md`.
- Queue rows are per design problem with an observable result; `不可观察` verdict; spec defects don't
  consume a rework round.
- §4b automation policy: rule and log by default; three stop conditions.

### 1.0.0 — 2026-08-29 — first release

- Seven roles, one command, five gates, four review lenses.
- `ux-auditor` and `ux-reviewer` have no Write/Edit; model registry shared with waterfall.
- Per-project `team/` pointer; orchestrator captures evidence into `uiux/evidence/`.
- `未定义` placeholder in state matrices; `[ASSUMPTION]` label carried downstream; blocking finding
  forbids "complete".

### 1.0.1 — 2026-08-29 — researcher questions asked by the orchestrator

- `ux-researcher` produces the questions; the orchestrator asks them at G1 (PLAYBOOK §3 Phase 1,
  `agents/ux-researcher.md`).

### 1.0.2 — 2026-08-29 — write each artifact as it finishes

- PLAYBOOK §4: agents write each artifact when done; the orchestrator checks the filesystem before
  recovering.

### 3.0.0 — 2026-08-30 — four roles and a Router

Major.
- Roles: `ux-critic` (also rules on findings), `ux-designer`, `fe-engineer`, `fe-tester`.
- Model tier by judgement: opus for judgement, sonnet for execution.
- Frontend code moved from `wf-developer` to `fe-engineer`.
- New Router (frontend / backend / cross-stack, classified from code) and capability ledger.
- P1/P2/P3 severity required on findings; frontend/backend line written per project before work.
