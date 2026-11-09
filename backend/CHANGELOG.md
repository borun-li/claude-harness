# Backend Agent Team — Changelog

Semver: patch = prompt/bar tuning · minor = new behaviour or new role · major = changed phase flow or artifact contract.

## 3.7.0 — 2026-11-09 — safety hooks act only in harness sessions

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

## 3.6.1 — 2026-11-08 — public changelog; neutral comments

Patch, wording only.
- `CHANGELOG.md` lists what changed in each version, nothing else.
- Hook docstrings and deny messages keep the design rationale only; hook test cases renamed.
- README Contributing: record what changed, without project names.

## 3.6.0 — 2026-11-08 — TC ids unique per project; ids found in any language's test names

Minor. Shared with frontend 8.2.0.
- `p4` gains `P4.tc-ids`: a `TC-###` already headed in another backend run dir's `04-test-plan.md` fails, naming the next free id. Template: TC ids continue across features.
- be-tester and QUALITY-BARS: a test carries its `TC-###` in its name or title; the JUnit match accepts `TestX/TC-003_case` and rejects `TC-0031`.

## 3.5.0 — 2026-11-08 — agents stop only processes they started

Minor.
- New hook `hooks/no-foreign-process-kill.py` (PreToolUse on Bash), registered by `install.sh`. Denies `pkill`/`killall`, `fuser -k`/`kill-port`, a process lookup (`pgrep`, `pidof`, `lsof`, `ps` except `ps -p`) combined with `kill`, and `kill` of 0, -1 or a negative PID. Allows `kill <pid>`, `kill $!`, `kill "$VAR"`, `kill %1`, `kill $(cat <pidfile>)`, lookups alone, and quoted/heredoc text. The deny message gives the PID-file pattern.
- New `hooks/test_no_foreign_process_kill.py` (43 cases).
- Constitution §4.6: a process you start is yours; record its PID and stop only that PID.
- `ORCHESTRATOR.md` Boundaries and the root README name the hook.

## 3.4.1 — 2026-11-07 — PLAYBOOK and agents trimmed

Patch, wording only.
- PLAYBOOK shortened (2,596 → 1,389 words); rules held by gates or `ORCHESTRATOR.md` are cited, not retold; section numbers kept.
- Agent descriptions shortened (shared with frontend 8.0.1); repeated handoff/long-output/"no gates" lines now cite `HANDOFF.md`. No role rule changed.

## 3.4.0 — 2026-11-07 — fewer questions to the user; shared 8.0 changes

Minor.
- Constitution §2.7, §5.4, §6 amended (see frontend 8.0.0).
- Kickoff asks only the tier (and missing frontend facts); model plan, risk and gate profile are shown with defaults. The gate profile is confirmed by running its commands.
- Phase 1b for an interface is the Frontend team's run up to its Prototype stop; `route/PROTOTYPE.md`, `FRONTEND_BACKEND_LINE.md` §4 and `/route` updated.
- Phase 6 cap: minor survivors are deferred and listed; only blockers, majors and failing TCs of in-scope REQs escalate.
- `ORCHESTRATOR.md`: ask only what is the user's to decide; process decisions are logged and shown at the next stop; product questions batched; self-caused failures re-run, never waived; exit `4`; one writer at a time across teams. `HANDOFF.md`: Budget line is the `--figma-left` number.
- Gates (shared): busy exit `4`, mark-order trail fix, `--figma-left`.

## 3.3.8 — 2026-11-03 — `compileall -f`

Patch.
- `gate.py profile` writes `compileall -f` for Python projects.
- `BuildGate.test_build_failure` pins the broken file's mtime; the profile test asserts `-f`.
- Existing `.claude/gates.json` is not rewritten; add `-f` via `/backend-config`.

## 3.3.7 — 2026-11-03 — stale wording and examples

Patch.
- README: sixteen agents; single-page design stop; `CLAUDE_HOME` for test installs only.
- `07-acceptance.md` gains § Frontend items and a Prototype sign-off line.
- Detailed-design example lists the script its build order names.
- `HANDOFF.md` §6: roles without Write put long output in a scratch file outside the tree.
- `capture` finds Chrome or Chromium on PATH when the macOS app is absent. Test added.

## 3.3.6 — 2026-11-03 — one reading for each ambiguous rule

Patch.
- Phase 5 runs only `fe-tester` for frontend items; the frontend panel joins the backend panel in Phase 6.
- `mark --role be-reviewer` before each panel and each re-check, not before the coordinator; no mark for Phase 1b.
- `be-architect`'s `user_decisions` are shown at Plan with a default (§3F).
- `NN-deferred.md` → `deferred.md`, written by the orchestrator.
- `be-tester` plans from the contract's seam entries too.
- Kickoff (and `route.md` §0) asks frontend design stops and Figma budget when the interface is touched.
- `config.json` `gates` lists Kickoff, Prototype, Plan, Acceptance for reference only; `G0_*` keys removed.
- Roles without Write return their handoff entry. `p2` checks `P2.prototype-first`. Test added.

## 3.3.5 — 2026-11-03 — conflicting descriptions fixed

Patch.
- `--run-dir` is a path from the project root (`docs/backend/<slug>`).
- Phase 4 marks `be-tester` first and `be-developer` last.
- Phase 6.4: the orchestrator files the re-check table in `06-review-report.md` §5 (new) and sets each confirmed FND's `Status`.
- `be-analyst` output comment fixed (no "stopped after §0").
- Gates: `log` and `timeline` no longer need a confirmed `gates.json`; `timeline` writes `run-log.md` only if the run dir exists; `baseline` ignores `prototype/`; `ROLE.unplanned` accepts files named in `03-queue.md`. Tests added.
- `/backend-status` and `/backend-resume` find additional `docs/backend/<slug>/` dirs.

## 3.3.4 — 2026-11-03 — read-only agents return their handoff entry

Patch.
- `be-reviewer`, the three `be-review-*` and the three `fe-review-*` end their output block with a `handoff:` field naming the agent and how to number the entry.

## 3.3.3 — 2026-11-03 — agent files: one job, input, output, boundaries

Patch. All 16 agent files (shared with frontend) rewritten.
- Structure: frontmatter, Constitution line, `Your ONLY job is …`, `## Input`, `## Output`, `## Boundaries`; rules held elsewhere are cited.
- Descriptions say what, when, and which neighbour it is not; no phase numbers.
- Direct calls: user's words set scope, no gates, entry to `docs/handoff.md`; `be-tester` without requirements tests current behaviour.
- `handoff: <entry header>` sits in the output block.
- `fe-engineer` no longer builds coded prototypes; `route/PROTOTYPE.md` is `be-developer`'s.

## 3.3.2 — 2026-11-03 — route docs agree on who prototypes what

Patch.
- Every human-operated interface, terminal included, is prototyped by the Frontend PLAYBOOK up to its UI stop. `route/PROTOTYPE.md` covers only work with no such interface (APIs, scripts, CLI arguments, jobs), built by `be-developer` in `docs/backend/`. `commands/route.md` §3, PLAYBOOK Phase 1b and READMEs updated.
- `route/FRONTEND_BACKEND_LINE.md` §4 and §7 clarified (`frontend_items` scope).

## 3.3.1 — 2026-11-03 — commands follow Claude Code's command guidance

Patch.
- `/backend-config` and `/backend-resume` set `disable-model-invocation: true`.
- `/backend-status` is read-only by tool (`disallowed-tools`), preloads `state.json` and the last 15 timeline events, and lists the Prototype stop.

## 3.3.0 — 2026-11-02 — shared line file; be-analyst as the product role

Shared with frontend 7.0.0.
- §3C moved to `~/.claude/route/FRONTEND_BACKEND_LINE.md` (cited as §3C.n); adds frontend designers (`fe-ux`, `fe-ui`), the cross-stack table (§4) and finer fix routing.
- `be-analyst` writes product features in frontend-only runs (`00-requirements.md`, gate `fe-product`).
- Gates: role checks ignore the other team's run dir and, for `fe-*`, the fixtures dirs; shared `_trail_common`.
- Constitution §2.7, §3.2, §5.1, §5.5, §6 amended; backend behaviour unchanged.

## 3.2.0 — 2026-11-02 — one design phase, review panel with a coordinator, depth by risk

- Phase 2 — Design replaces Phases 2, 3 and 3b: one `be-architect` dispatch writes `02-architecture.md` and `03-detailed-design.md`; `risk: high` adds a design review and one revision; a fresh `be-analyst` writes fixture answers. Plan stop ends the phase.
- Gates: `p2` absorbs `p3` and `plan` and writes `plan-review.md`; `p3`, `plan` removed; `fixtures-approve` needs green `p2`; `P7.gates` requires `p1 p2 p4 p5 p6`; `LOG.trail` and `ALL.state` (`risk`) updated.
- Review: new `be-review-behavior`, `be-review-reliability`, `be-review-security` in parallel; `be-reviewer` becomes the coordinator (merges, disproves, ranks `FND-###`, re-checks fixed findings only). Blockers and majors go to fix rounds; minors deferred. Old lenses retired.
- Risk: `state.json` `risk: high | normal`; normal trims the panel by what the diff touches (PLAYBOOK §6).
- Kickoff: one `AskUserQuestion` for tier, model plan, risk, gate profile; `language.default_docs: "user"`; `prototype: "reused"`.
- §3B Increments replaces Re-baseline: mid-run requirement changes join at the next fixed stop as `## Increment <n>` sections; `state.json` gains `increments`.
- PLAYBOOK and QUALITY-BARS trimmed; agents and templates `06-review-report.md`, `07-acceptance.md` aligned.

## 3.1.0 — 2026-10-31 — context discipline; constitution made stable

- Constitution §8 Context discipline (fresh agent per dispatch, short briefs, handoff entries, long output to files) and §9 Amendments (stable section numbers); Constitution made roster- and path-free; §2.3, §2.8, §2.9, §4.6 added.
- New `route/HANDOFF.md` (brief and entry formats, `logs/`).
- Fix rounds are fresh dispatches naming only failing items; `/backend-resume` starts from the last orchestrator handoff entry.
- New `ORCHESTRATOR.md` holding shared orchestrator rules; PLAYBOOKs point to it. Team agents do not dispatch.
- `/route` gets `when_to_use`; `/backend` and `/frontend` set `disable-model-invocation: true`.
- New hook `hooks/no-agent-continuation.py` (PreToolUse on SendMessage): a finished agent may be continued once.
- Constitution §5 Decision Rules simplified: decide, log, continue; only four cases stop the run. `be-analyst` no longer stops in Phase 1.

## 3.0.0 — 2026-10-18 — run tiers and Phase 1b prototype

- Constitution §7 run tiers: Small change / Prototype / Full development, asked of the user. `commands/route.md` §4 and `route/PROTOTYPE.md`.
- Constitution §2.7: new Phase 1b and a fixed Prototype stop in Full development.
- Gates: `log human --stop Prototype`; `LOG.trail` tier rules; `ALL.state` validates `tier`.
- `be-developer`, `fe-engineer`: rules for Prototype and Small change dispatches.

## 2.7.4 — 2026-09-24 — route-classifier removed

- `agents/route-classifier.md` deleted; `/route` classifies from code facts and the contract's capability table.
- Capability ledger merged into the contract; legacy `contracts/CAPABILITY_LEDGER.md` still read.
- Constitution §3: orchestrators classify tasks (`/route`).

## 2.7.3 — 2026-09-23 — JUnit for JS test runners (shared gates)

- Per-test results for vitest, playwright and jest (jest-junit), including via `npm run`/`pnpm`/`yarn`; other runners via `gates.json` `"junit"`. Vitest summary fallback.
- Test ids (`TC-`, `FX-`, `Q-`) recognised in JS test titles and preceding comments.

## 2.7.2 — 2026-09-23 — shared-gate changes for the frontend

- `baseline` excludes both teams' run dirs.
- `LOG.trail` treats `fe-engineer` like `be-developer`.
- §3C.4 points at `docs/frontend/05-queue.md`.

## 2.7.1 — 2026-09-23 — frontend alignment touch-ups

- §3C.4 points at `frontend/05-queue.md`; frontend observables shown at Plan.
- Template placeholders `<…>` → `{…}`; gates treat both as unfilled.

## 2.7.0 — 2026-09-23 — Run log (control panel)

- `<run-dir>/run-log.jsonl`: append-only, hash-chained; gates write `gate`/`mark`/`approve`; orchestrator writes events via `gate.py log`; `gate.py timeline` renders `run-log.md`.
- `LOG.valid` on every gate; `LOG.trail` in P7.
- PLAYBOOK §3G; `/backend-status` shows the timeline; `/backend-resume` treats unreturned dispatches as unverified.

## 2.6.0 — 2026-09-23 — Two human stops; concise, understood requirements

- Human stops reduced to Plan and Acceptance (PLAYBOOK §3F); config `gates`: `Plan`, `Acceptance`.
- Gate `gf` renamed `plan` (`PLAN.*`); writes `plan-review.md`.
- be-analyst writes §0 Understanding; every REQ needs a `Source` field quoting the user or citing an artifact.
- Templates 01–03 rewritten as skeletons with worked examples in `templates/examples/`.
- New gates `P1.understanding`, `P1.source`, `P1.req-length`, `P2.length`, `P3.des-length`, `P1/P2/P3.prose`; limits in `doc_budgets`.
- Fixed: headings inside fenced code split DES blocks.

## 2.5.0 — 2026-09-23 — Approved fixtures

- PLAYBOOK §3E and Phase 3b: per-REQ `Fixtures:` declarations; human gate GF; `fixtures-approve --by <user>` locks answers.
- Gates: `P1.fixtures`, `gf`, `fixtures-approve` (`--reapprove`), `P4/P5.fixtures`, `P5.fixtures-used`, Fixtures column in the P7 matrix.
- Fixed: `baseline` counting the run's own files; fixture data under `tests/` counting as a test reference.

## 2.4.1 — 2026-09-23 — tidy-up, no behaviour change

- QUALITY-BARS tags gate-backed bars with gate ids.
- be-* agent files slimmed.
- Commands `/backend`, `/backend-status`, `/backend-resume`, `/backend-config` updated.
- Fixed YAML frontmatter in `backend-resume.md`, `backend-config.md`, `frontend.md`.
- README rewritten.

## 2.4.0 — 2026-09-23 — Computational gates

- New `~/.claude/gates/` (`gate.py profile | p1 | p2 | p3 | baseline | mark | p4 | p5 | p6 | p7`); exit 0/1/2/3; regression suite in `gates/tests/`.
- `mark` snapshots before each writing dispatch; role rules per agent diff.
- `p4`/`p5` re-run build/lint/typecheck/tests and check counts, skips, dependencies, secrets, TC tags, fixture hashes.
- Fix loop capped by `loops.max_gate_fix_rounds` (3); waivers need `approved_by` + `date`.
- PLAYBOOK §3D, §2.2/2.3, §4.7; `state.json` gains `gates`; templates gain `Cut:`, `Side:`, design §9 Dependencies.

## 2.3.0 — 2026-09-23 — Constitution adopted

- New `~/.claude/CONSTITUTION.md`, overriding PLAYBOOK, QUALITY-BARS, agents and prompts.
- Every agent, command and PLAYBOOK opens with "Read CONSTITUTION.md first".
- Duplicated rules removed in favour of the Constitution; PLAYBOOK §4 renumbered.

## 2.2.0 — 2026-09-23 — PLAYBOOK + QUALITY-BARS slimmed (11,703 → 3,201 words)

- Rules reduced to one or two lines; duplicates merged; §3A to 15 items; section anchors kept.
- L2/L3 staged bars removed.
- `state.json` gains `frontend_items`; layout lists `NN-deferred.md`.
- `no-tree-restoring-git.py` reference updated to §3A.11.

## 2.1.0 — 2026-09-23 — be-developer builds backend only

- `be-developer` builds backend only (PLAYBOOK §0).
- New PLAYBOOK §3C: default frontend/backend line; `DES` tagged `side: backend | frontend`; Frontend team dispatched within the run.
- `be-analyst` tags `[interface]` requirements; `be-developer` returns `frontend_items`.
- New QUALITY-BARS L1 bars in Phases 1, 3, 4/5 and 7.

## 2.0.0 — 2026-09-22 — renamed: waterfall → backend

Major (artifact paths).
- `/waterfall*` → `/backend`, `/backend-status`, `/backend-resume`, `/backend-config`.
- `~/.claude/waterfall/` → `~/.claude/backend/`; agents `wf-*` → `be-*`.
- `docs/waterfall/` → `docs/backend/`, `.claude/waterfall.json` → `.claude/backend.json`; legacy paths still read (PLAYBOOK §1 rule 4).

## 1.10.0 — let it be wrong, and watch what turns red

- QUALITY-BARS Phase 4/5: an assertion counts only after it has been made to fail; a negative result needs a positive control; tests are fed by the producer production uses; guards are judged by false-positive rate too.
- QUALITY-BARS Phase 6: the reviewer breaks every guard it relies on.
- QUALITY-BARS Phase 1: a scope exclusion states whether it is deferred or not ours.
- PLAYBOOK §3A.16 (acceptance criteria can be wrong) and §3A.17 (reading a description instead of the code).
- Agents: satisfying a wrong criterion is worse than failing it.

## 1.9.0 — the git ban becomes a hook

- New `~/.claude/hooks/no-tree-restoring-git.py` (PreToolUse on Bash) denies tree-restoring git commands; new `test_no_tree_restoring_git.py` (27 cases).
- PLAYBOOK §3A.13 (no writing agent on a dirty tree), §3A.14 (enforcement by hook), §3A.15 (record self-disclosure).
- Agents gain the mutation-testing protocol (cp → mutate → cp back → `cmp` → `rm`).
- QUALITY-BARS Phase 2: change-footprint answer must be an executable test; Phase 6 re-measures it.

## 1.8.0 — 2026-08-25 — measurement bars

- QUALITY-BARS Phase 4/5: failed runs are flagged and excluded, failure rate reported; non-deterministic systems reported as mean, range and run count, with systematic vs intermittent errors; answer-key values must be reachable from the input.
- PLAYBOOK §3A.11: long work writes each unit to disk with resume; no agent waits on its own background job.
- PLAYBOOK §3A.12: verify by artifact, never by exit code.

## 1.7.0 — 2026-08-19 — proportion

- MVP cut line promoted to L1: the round is the simplest common path of what the user asked; each requirement justified from the user's words.
- Phase 6: reviewers rank only what breaks a requirement above the cut line; the rest goes to `NN-deferred.md`.
- Phase 7: deferred findings may not be bundled into a fix round.
- PLAYBOOK §2.1a: the cut line is written before Phase 1 is dispatched.

## 1.6.0 — 2026-08-18 — declarations vs observations

- Phase 4/5 L1: an observation-named field (`reason`, `basis`, `evidence`, `source`, `note`) must vary across two differing inputs, or be renamed.
- Phase 6 L1: a diagnosis resting on an artifact string requires locating its producer in code.
- PLAYBOOK §3A rule 9 rewritten: claims about work in flight carry their evidence.

## 1.5.0 — 2026-08-18 — `quality` tier

- `quality` tier: `wf-developer` sonnet → opus.

## 1.0.0 — 2026-08-09 — initial harness

- 5 roles (`wf-analyst`, `wf-architect`, `wf-developer`, `wf-tester`, `wf-reviewer`) orchestrated by `/waterfall`.
- 7-phase waterfall with parallel work inside phases 2, 4 and 6.
- Human gates G1, G2, G3; per-role model plan with tiers (quality / balanced / economy / max).
- Traceability `REQ → DES → code → TC → FND` (`policy.require_traceability_ids`).
- L1 quality bars plus staged L2/L3; resumable runs via `docs/waterfall/state.json`.

## 1.1.0 — 2026-08-10 — three L1 bars

- Phase 3: a completeness assertion may not be derived from the output it checks.
- Phase 4/5: fixtures include the legitimately-absent shape; tests reach their subject through its real entry point.
- Phase 6: coverage is claimed by behaviour, and a test counts only if it can fail.

## 1.2.0 — 2026-08-12 — five L1 bars; orchestrator discipline

- Phase 3: every guard declares what makes it fire and not fire.
- Phase 4/5: claims about external systems verified under production-shaped input.
- Phase 6: reachability judged from the user's entry point; declared non-goals verified absent.
- Phase 6/7: a number carries its composition and measurement conditions.
- New PLAYBOOK §3A orchestrator discipline.

## 1.3.0 — 2026-08-13 — operator bars; re-baseline

- Phase 3: catch-all branches state what they do not claim; a sentinel has one predicate; durable references survive recomputation.
- Phase 4/5: test against state from earlier versions; click every control once on real data; a non-deterministic producer yields a sample; real end-to-end integration test promoted to L1.
- Phase 6: completion and accuracy are separate claims; deferral names the user path. Phase 7: name what makes delivered work live.
- New review lens `operator-experience` (`parallelism.review_lenses`).
- PLAYBOOK §3A rules 6–7, §3B re-baseline procedure, §2.2 LLM model benchmarking.

## 1.4.0 — 2026-08-14 — verification bars

- Phase 4/5: fetch every URL a delivered page references; fix where the defect is; a pass verdict names its assertion; overrides of a requirement are logged as deviations.
- Phase 6: a multi-source assertion must fail for each source.
- PLAYBOOK §3A rule 2 sharpened (change X, do not remove it); new rules 8 (user's report outranks analysis) and 9 (no unmeasured precision).
