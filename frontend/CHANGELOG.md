# Frontend Agent Team（原 UI/UX Agent Team） — Harness Changelog

Semver: **patch** = prompt/bar tuning · **minor** = new behaviour, role or lens ·
**major** = changed phase flow or artifact contract.

**体例**：条目记录事故发生的具体项目与数字；规则正文一律不得携带项目名词。
一条经验要进规则，先脱掉它的项目外壳；脱不掉的，它属于那个项目的
`team/uiux-team-config.md`，不属于这里。

> **本文件是历史，不重写。** 下面 2.0.0 及更早的条目描述的是当时的 harness：其中点名的
> `ux-lead` / `ux-researcher` / `ux-architect` / `ux-contract` / `ux-auditor` / `ux-reviewer`
> 六个角色**今天已经不存在**，归档在 `~/.claude/archive/agents-v1/`，harness 里没有任何一处派工
> 指向它们。把这些条目改写成四角色的措辞，等于把「当时是七个角色」这件事从记录里抹掉 —— 而
> 变更日志唯一的价值就是它没被改写过。**要找活的角色定义，看 `PLAYBOOK.md` §1B。**

## 7.2.3 — 2026-11-03 — read-only agents return their handoff entry

Patch: `fe-review-experience`, `fe-review-accessibility` and `fe-review-integration` end their output
block with a `handoff:` field naming the agent, as in backend 3.3.4 (a live direct call returned no
entry).

## 7.2.2 — 2026-11-03 — agent files: one job, input, output, boundaries

Patch: the 8 `fe-*` agents and the shared `be-analyst` follow the structure in backend 3.3.3
(frontmatter, Constitution line, `Your ONLY job is …`, Input, Output, Boundaries; at most 48 lines).
Descriptions drop phase numbers and dispatch conditions (PLAYBOOK §6 keeps those) and name the
neighbour that is not them. `fe-engineer`'s coded-prototype rule is removed: a Prototype-tier
interface ends at the UI stop, not in code. `tools`, `skills` and `model` unchanged.

## 7.2.1 — 2026-11-03 — terminal prototypes stay in this PLAYBOOK

Patch, with backend 3.3.2: a terminal surface is prototyped here as text mockups up to the UI stop,
never through `route/PROTOTYPE.md`; §7 drops `prototype/` (no frontend code prototype remains).

## 7.2.0 — 2026-11-03 — `/frontend-status`; commands follow Claude Code's guidance

Minor (a new command), from the same comparison as backend 3.3.1.

- New `/frontend-status`, replacing `/frontend status`: the same report, in line with
  `/backend-status`, and callable by the model (`/frontend` is user-only). Read-only by tool
  (`disallowed-tools`), with `state.json` and the timeline loaded before it starts. `/frontend
  status` now points to it and starts nothing.
- `/frontend-config` and `/frontend-resume` set `disable-model-invocation: true`.

## 7.1.0 — 2026-11-02 — design taste: type, spacing, icons, avoid-list

Minor: new taste rules, agreed with the user after comparing `design-taste` with Anthropic's
`frontend-design` skill, the frontend-aesthetics cookbook prompt and skill-authoring best practices,
and the community `taste-skill` and `design-memory`. Section numbers unchanged; §8 appended.

- **§1 by class.** The brand question now covers typefaces as well as colours (still four
  questions). The class table adds small screens, keyboard (command palette for tools only), dark
  mode (required for tools; one mode for showcases unless the user asks), density (tools: 14 px
  body, 36–40 px rows) and boldness (showcases: one signature moment). The kickoff procedure is left
  to the PLAYBOOK.
- **§3** adds empty states. **§4** adds type (follows the brand; with none, fe-ui proposes and uses
  the system stack meanwhile), a 4 px spacing scale, 4–6 px radius, and icons (the library's own
  set, else Lucide; one set, line style). **§5**: start Figma work from the library's kit.
- **§6** adds a list of generic AI-design defaults to avoid. **§7** checklist split into 14
  single-question items. **§8** where the preferences come from; new ones are proposed by fe-ui and
  added only when the user confirms.
- New `examples.md` (error, single-value edit, risky action, empty state, in-place feedback,
  optimistic rollback, status not colour alone, a generic AI-design first screen): only rules that
  need judgement or that models habitually break; more are added from real runs (§8). Description
  rewritten as what + when, without section numbers. `PLAYBOOK.md` §2.3 and `fe-ui` say "brand
  (colours, typefaces)".

## 7.0.0 — 2026-11-02 — product, UX, UI, engineering; Figma; review panel

Major: changed roles, phase flow and every artifact contract. Built from a review of the ithaca run
(harness 5.5.0, mode `new` plus implement: 41 dispatches, 239 agent-minutes — Phase 7 build 135,
Phase 8 verify 37, Phase 5 document review 35 — 10 human events, 20 rows, verification round 4;
two of the human events were `ROLE.designer-scope` waivers for fixture files the Backend team wrote
while `fe-designer` was the latest mark), and from Anthropic's `frontend-design` skill and best
practices, OneRedOak's design-review agent and ux-agent.

- **Roles follow real frontend work.** `fe-designer` is split into `fe-ux` (flows, page structure,
  per-page state tables, ASCII wireframes, post-launch insights) and `fe-ui` (design plan with a
  self-check against generic defaults, tokens, components, Figma frames). `fe-critic` is removed:
  `be-analyst` writes product features in frontend-only runs (Phase 0); the document review is gone.
  `fe-engineer` also scaffolds while UI draws, checks feasibility, drafts the contract and writes the
  queue (no longer the orchestrator).
- **Flow.** Kickoff (one question: tier, models, risk, design stops, Figma budget) → 0 features →
  1 UX → UX stop (2+ pages or a new flow) → 2 UI ‖ scaffold → feasibility and queue → UI stop
  (Figma frames and the queue's observables; frames exported and locked) → 3 build → 4 verify ‖
  review panel → coordinator → fix blockers and majors only → Acceptance → 5 after launch. Modes
  `new`, `redesign`, `audit`, `review`, `implement` are retired; audits and reviews are direct calls.
- **Design feedback (§3A).** Any role raises a `DFB-###`; its owner decides; changes to anything the
  user confirmed need the user. Register in `06-feedback.md`; `fe-queue` and `fe-accept` check it.
- **Figma (§1E).** UI is drawn and confirmed in Figma; a per-run call budget (20 + 8 per page, under
  a monthly 300) is proposed at kickoff, calls are logged on returns (`--figma-calls`) and checked
  (`FE.figma`); exceeding it needs the user (`--stop Budget`). Terminal surfaces use text mockups.
- **Review panel (§6).** `fe-review-experience` (always), `fe-review-accessibility`,
  `fe-review-integration` (by risk and what the diff touches), merged by `fe-reviewer`, which drops
  a candidate only with counter-evidence and re-checks only fixed FNDs. Same rules as backend 3.2.0.
- **Increments (§3B)** as in backend 3.2.0.
- **Artifacts:** `00-requirements`, `01-ux`, `02-ui`, `03-queue`, `04-verification`, `05-review`,
  `06-feedback`; `evidence/design/FRAME-###.png`.
- **Gates:** `fe-product`, `fe-ux`, `fe-ui`, `fe-queue`, `fe-plan`, `fe-approve` (rows and frame
  exports), `fe-build` (scaffold allowed before approval), `fe-capture-plan`, `fe-verify`,
  `fe-review`, `fe-accept` (own trail: UX before UI, UI before Phase 3 build). Role checks no longer
  charge one team's agent for the other team's run dir or fixtures (the ithaca waivers). Run-log
  stops `UX`, `UI`, `Budget`.
- **Shared:** the frontend/backend line moved to `route/FRONTEND_BACKEND_LINE.md`; in a cross-stack
  run the UI stop is the backend's Prototype stop. `/route` asks the frontend kickoff questions in
  its one question; a visual Prototype tier is the frontend run up to the UI stop.
- 6.x runs are not resumed by 7.0 (PLAYBOOK §1.3).
- **Constitution amended (2026-11-02, by the user), shared with backend 3.3.0.** §2.7: the
  rough version may be a visual design when the deliverable is a visual interface. §3.2: reviewers
  never change what they review and may write their own report (`fe-reviewer`). §5.1: a result the
  user confirmed they will see or get (approved expected output or observable, confirmed flow or
  screen) changing is a stop — internal design details are not. §5.5 (new): a budget the user set
  would be exceeded. §6: a tier whose deliverable is a design replaces 6.4 and 6.7 with the user's
  review of the design. Why: the frontend prototype is a Figma design, the coordinator writes its
  report, and DFB and Figma-budget stops need a constitutional basis; worded so backend stops are
  unchanged.
- `ORCHESTRATOR.md`: start is recon then one question; stops `UX`, `UI`, `Budget` and
  `--figma-calls` in the log commands; more than 4 questions → a second call right after.
- Kickoff asks design stops and the Figma budget as one question (4 in all); surface, named user
  and gate profile, when unset, in a second call. One-stop runs scaffold only after the UI stop
  (Constitution §4.2); `fe-build` fails product code before it (`FE.observables`).

## 6.1.0 — 2026-10-31 — context discipline; constitution made stable

Shared with backend 3.1.0 (see `~/.claude/backend/CHANGELOG.md`): Constitution §8 context discipline and the stable, roster-free Constitution; `route/HANDOFF.md`. PLAYBOOK §4.3 no longer resumes a dead agent — the orchestrator writes its handoff entry from the disk and dispatches a fresh one. Phase 8 rework: a fresh engineer per row and a fresh `fe-tester`. `/frontend-resume` starts from the last orchestrator handoff entry. Log: `docs/frontend/handoff.md`. New shared `ORCHESTRATOR.md`; this PLAYBOOK's §1A, §3G, §4, §5, §6 point to it. Constitution §5 simplified: Phase 1 questions carry defaults and are asked with the Phase 1b intent questions (or at the Plan stop); §3F no longer stops for domain facts, ties or unconfirmed capabilities. Hook `no-agent-continuation.py`.

## 6.0.0 — 2026-10-18 — run tiers and Phase 1b prototype

Shared with backend 3.0.0 (see `~/.claude/backend/CHANGELOG.md`): Constitution §7 tiers, asked first in kickoff (§2.0); Phase 1b prototype in `new` and `redesign` before Phase 3, with a fixed Prototype stop; in cross-stack runs the backend Phase 1b covers it, and the same stop is logged here. `fe-accept`'s trail check enforces the order when `tier: "full"`.

## 5.5.0 — 2026-09-24 — The user's design taste as a skill

- New `~/.claude/skills/design-taste/SKILL.md`, from an interview with the user. Usability over looks;
  fewest steps (edit in place or drawer by size, keyboard-first with a command palette, secondary
  items collapsed); in-place feedback, confirm risky actions, skeleton plus optimistic updates;
  brand colours, thin-border hierarchy, dark mode required; product class decides navigation,
  motion and copy; a never-list; an 8-item review checklist.
- Kickoff (§2.4) confirms the product-dependent choices (class, brand colours, motion, copy tone)
  unless `project-context.md` records them. fe-designer reads the skill and never guesses them.
  fe-critic's design-system lens runs its checklist.

## 5.4.0 — 2026-09-23 — Approved-observable registry

- `docs/frontend/observables.json`: after Acceptance, `fe-promote` registers each row verified done
  as `OBS-###` (hashed, approver, date), guarded by its passing test (file and name recorded) or,
  without one, by a planned capture re-judged every round. Rows with neither are refused.
- `FE.regression` (fe-build, fe-verify) and `FE.regression-captures` (fe-verify) check every later
  round; `fe-plan` lists registered observables the round may change; `fe-approve --retire` retires
  them. PLAYBOOK §3I; §3 subsections reordered D→I.
- Suite: 41 frontend cases; tamper, regression and conflict checks mutation-tested.

## 5.3.0 — 2026-09-23 — Parity with the backend's checks

- `FE7.dependencies` (fe-build): new packages must be named in the spec's Dependencies table.
- `FEA.matrix` (fe-accept): task → page → row → verdict written to `gates/traceability.md`; every
  active task must end in a row verified done.
- `FE1.source`: every task in the brief quotes the user or cites an artifact (new Source column).
- Item length limits: flow 80, page spec 200, finding 80, queue row 80 words (gates `doc_budgets`).
- Templates and examples updated (the examples pass the design gates). Suite: 34 frontend cases.

## 5.2.0 — 2026-09-23 — Scripted evidence capture

- `gate.py capture --round <n>` from `docs/frontend/capture-plan.json` (PLAYBOOK §3H). Web: playwright-core
  drives the system Chrome for DOM, computed styles, ARIA snapshot and screenshot per capture and size.
  Terminal: raw stdout/stderr bytes at a fixed size. Manual (native, desktop, engine): files copied and
  stamped. The manifest records instrument, time and source fingerprint; rounds are never overwritten.
- Gates: `fe-capture-plan` (every row to verify is planned); `FE8.capture` in `fe-verify` (every planned
  capture and size present, not failed, not empty, not older than the last `fe-build`, source unchanged).
- Dependency: `~/.claude/gates/node_modules/playwright-core` (13 MB, `package.json` there).
- Suite: 30 frontend cases, including a real-Chrome capture at two sizes.

## 5.1.1 — 2026-09-23 — JS test results

- `FE8.row-tests`: tests tagged with a queue row id must pass in the orchestrator's run. JS runners
  report per test (see backend 2.7.3). fe-tester tags row assertions with `Q-###`.

## 5.1.0 — 2026-09-23 — Gates, approved observables, run log (batch 2)

- Frontend gates in `~/.claude/gates` (`gatelib/frontend.py`): `fe-brief`, `fe-structure`, `fe-spec`,
  `fe-findings`, `fe-queue`, `fe-plan` (writes the Plan sheet), `fe-approve`, `fe-build`, `fe-verify`,
  `fe-accept`. Shared `baseline`, `mark`, `log` and `timeline` take `--team frontend`.
- Role rules: fe-engineer (files named in the queue, no test edits), fe-tester (tests and docs),
  fe-designer (design docs only), fe-critic (read-only).
- Approved observables: `fe-approve` hashes each queue row's spec, observable and acceptance;
  `FE.observables` fails if a row changes after the user's approval.
- Run log: `LOG.valid` on every gate; `fe-accept` checks the trail (Plan before the first fe-engineer).
- Run dir moved to `docs/frontend/` (next to `docs/backend/`); `frontend/` at the root clashed with
  source folders. Legacy `docs/uiux/` and `uiux/` are still read.
- New commands `/frontend-config` and `/frontend-resume`; `/frontend status` shows gates and timeline.
- Fixed: `baseline` counted the other team's run dir as uncommitted user work; the spec example lacked
  the loading and permission-denied states its own bar requires.
- Suites: 22 frontend + 64 backend cases; observables, verdict and designer checks mutation-tested.

## 5.0.0 — 2026-09-23 — Frontend aligned with the backend harness (batch 1)

- PLAYBOOK, QUALITY-BARS, command, README and the four fe-* agents rewritten, core rules only, in
  English. Rules plus templates went from 18,504 to 5,860 words. Incident narratives remain in the
  entries below.
- §4b automation policy replaced by Constitution §5 plus PLAYBOOK §3F (frontend-specific stops).
- Human stops G0–G4 → **Plan** (design approval, or the queue's observables before building) and
  **Acceptance** (implement mode). The model plan is confirmed once at kickoff.
- About 15 artifacts → `01-brief` · `02-structure` · `03-spec` · `04-findings` · `05-queue` ·
  `06-verification`, plus the shared contract. Skeleton templates and worked examples in
  `templates/examples/`. Old artifact names are still read (PLAYBOOK §1.3).
- Removed: checklists/, workflows/, model-registry-reference.md (folded into §1), 9 old
  templates, retrospective phase, frontmatter requirement.
- README: agent-and-loop flowchart and bullets.
- Placeholders in all templates changed from `<…>` to `{…}` (the preview swallowed `<word>`).

## note — 2026-09-23 — Backend team no longer builds the interface

No rule change here. Backend 2.1.0 made `be-developer` backend-only. A `/backend` run that touches
the interface now dispatches this team's roles itself (backend PLAYBOOK §3C), following this
PLAYBOOK's §1C and Phases 6–8 as written.

## 4.0.0 — 2026-09-22 — renamed: uiux → frontend

Rename only; no behaviour change.

- Command `/uiux` → `/frontend`. Harness dir `~/.claude/uiux/` → `~/.claude/frontend/`.
- Agents `ux-critic` / `ux-designer` → `fe-critic` / `fe-designer` (`fe-engineer`, `fe-tester`
  unchanged). The Waterfall team is now the Backend team (`wf-*` → `be-*`).
- **Artifact contract (why major):** `<root>/uiux/` → `<root>/frontend/`, `.claude/uiux.json` →
  `.claude/frontend.json`, `team/uiux-team-config.md` → `team/frontend-team-config.md`,
  `UIUX_*.md` → `FRONTEND_*.md`, config key `artifacts.uiux_dir` → `artifacts.frontend_dir`.
  Legacy names are still read when the new ones are absent (PLAYBOOK §1 rule 4a).
- Entries below this one are history and keep the old names.

## 3.0.0 — 2026-09-09

**Major: seven roles became four, and the harness stopped assuming a browser.** Both by the
user's ruling; this entry records what the harness did about them.

**① 四角色。** `ux-critic` · `ux-designer` · `fe-engineer` · `fe-tester`，加上编排者。

The harness was **not runnable** when this change started, and it had stopped itself: `PLAYBOOK.md`
§4 rule 8 says a dispatch target must be verified to exist and the run must stop otherwise, and
every phase that dispatched named an archived type. Counted from the pre-change `PLAYBOOK.md §3`
by which phases each mode runs: Phase 1 named the researcher, 2A and 7.2 the auditor, 2B the
architect, 3 the contract role and the lead, 4 the reviewer and the lead, 5 / 6.1 / 9 the lead —
so **six of the eight modes had no runnable path**, and only `status` and `config`, which
delegate to nobody, still worked. **The rule was right and the dispatch lines were wrong** —
which is now written into rule 8 itself, so the next person to hit a halt does not "fix" the
rule.

`config.json` also carried **two role registries at once** — an archived seven-role × four-tier
table under `model_plan.roles`, and the live four-role `roles` object — with **no line anywhere
saying which won**, while `PLAYBOOK.md §1` orders every downstream decision to come from the
merged config. There is now exactly one, and §1 gained a rule that finding a second is itself
the bug.

Where the seven roles' duties went is recorded as a table in `PLAYBOOK.md §1B`, including the
ones that went to the orchestrator (the interview, the queue, the state, the retrospective —
each because it needs a tool no subagent has, or because the alternative was letting a role
grade its own work).

**② 交付形态不再默认 Web.** The `observable` criterion used to read 「what a person would see in
a **browser**」 and Phase 7 was called 「browser verification」. The harness is used for products
that have no browser at all. The criterion is unchanged in force and now reads **「what a person
would perceive on the running interface」**, where the surface is a project-declared slot
(`delivery_surface`, `PLAYBOOK.md §1C`): browser page · native app · desktop · terminal · engine
UI. **Only the instrument changes** — DOM and computed styles, view hierarchy and accessibility
tree, real output bytes, UI node tree — and **a picture alone is never evidence on any of them**.

Deliberately **not** a gate: unlike `primary_user_role`, an empty `delivery_surface` does not
stop the run. The right default is to ask one question, not to halt — and not to assume Web.
Deliberately **not** written as `if web / else`, which would have made Web the default again
with a patch on top.

**③ 60 lines moved from role prompts into the bars.** Three sections (the mutation protocol for
touching production files · an acceptance criterion can itself be the defective artifact ·
「make it fail before you claim it covers anything」) had been copied verbatim into five role
files. `README.md` had said not to do this since 1.0.0: a rule that belongs in a bar does not
belong in a role prompt, because only one role reads it.

They now live in `QUALITY-BARS.md` §Phase 7, and the two frontend roles point at it. **The order
mattered**: those two roles read no quality bars at all before this change, and the bars had
**zero** entries for the implementation and verification phases — deleting first would have lost
the rules rather than moved them.

One bar is new and is frontend-specific: **an assertion must be shown red when the behaviour
breaks *and* green when unrelated copy changes.** A backend guard only has to prove sensitivity;
a frontend's product is the words a person reads, so the cheapest possible assertion hangs on
copy, is red for every innocent wording edit, and gets switched off — after which it is not a
weaker guard but no guard, plus the belief that there is one.

## 2.0.0 — 2026-08-29

**Major: the phase flow changed.** The team's output used to end at a document. It now ends at a
screen someone looked at.

New Phases 6 → 8: **implementation queue → `wf-developer` builds it → browser verification →
capped rework**. Retrospective renumbered 6 → 9. New mode `implement`, new artifacts
`IMPLEMENTATION_QUEUE.md` and `VERIFICATION_REPORT.md`, new `checklists/verification.md`.

Why, measured on the first real run: a `redesign` produced **11,093 lines across 22 documents**
for a frontend of **1,415 lines** — roughly 8:1 — and **not one line had been opened in a
browser**. Four numbers (56/64/104/112) were cross-referenced by three documents without a
single pixel having been seen; `@media` appeared **0 times** in the codebase the spec commits to
responsive behaviour for. A design package can be internally consistent, version-stamped and
wrong at the root, and nothing in phases 0–5 can discover that.

Decisions made in this upgrade:

1. **The boundary the user set is unchanged.** `ux-*` still write nothing but documents;
   `wf-developer` is still the only role in either harness that writes production code. What
   changed is that the design team now *escorts* the build and *verifies* it — the team that
   specifies is not the team that builds, and the team that verifies is not the team that built.
2. **The queue is per design problem, not per page or per file** — and every row must state what
   a person would **see in a browser** if it shipped. A row whose result cannot be observed
   cannot be verified; it gets split or marked `不可观察`, never quietly passed.
3. **`不可观察` is a verdict, not a rounding error.** Two outcomes collapse into 「done」 if you
   let them: 「we looked and it is there」 and 「we did not look」. They are kept apart by name.
4. **A spec defect found in the browser does not consume a rework round.** The screen outranks
   the specification: when they disagree, the finding is filed against whichever the evidence
   shows to be wrong, which is sometimes the spec, and it is routed to the owning `ux-*` role.
5. **Rework is capped at 2 rounds.** Two rounds that did not land an item usually mean the spec
   is unbuildable or a capability is missing; a third round buys a third identical failure.
6. **§4b — the automation policy.** Default is to **rule and log**, not to ask. Only three
   things stop: a fact about the world only the user knows · changing words the user authored ·
   a genuine tie no criterion in the package resolves. The tie test is constructive — try to
   derive it from the invariants and measurements on disk first; if a derivation exists, you
   were never tied. Everything ruled by an agent is recorded **as ruled by an agent**, with its
   derivation and what would overturn it, and is never laundered into 「已裁定」 as though the
   user had said it. Stops are batched into one `AskUserQuestion` at a phase boundary.

## 1.0.0 — 2026-08-29

First release. Seven roles, one command, five gates, four review lenses.

Design decisions made at creation, each because the alternative had a known failure mode:

1. **Read-only is a capability, not an instruction.** `ux-auditor` and `ux-reviewer` have no
   `Write` and no `Edit` in their frontmatter. A prompt that says 「you are read-only」 can be
   reasoned around; an absent tool cannot.
2. **The model registry is not forked.** Tier names and semantics stay owned by
   `~/.claude/waterfall/config.json`; this harness adds only the `ux-*` role mapping, and a
   `ux-*` key appearing in the shared file wins over ours. Merging the two is documented as a
   proposal, not performed unilaterally on another team's runtime.
3. **The harness is global, the artifacts are per project.** The requested `team/` directory
   became a project-level pointer instead of a copy of the harness, because a copy per project
   is a fork per project.
4. **Browser evidence is gathered by the orchestrator.** Subagent `tools:` is an allowlist that
   does not include MCP browser tools. Rather than pretend otherwise, the flow captures evidence
   into `uiux/evidence/` and the audit template forces every surface to be labelled **observed**
   or **inferred**.
5. **`未定义` is the only legal placeholder in a state matrix.** A blank cell reads as 「nothing
   to say here」, which is the one message it must never send.
6. **An `[ASSUMPTION]` label travels into every downstream artifact.** The reader of a page spec
   must not have to cross-check the research file to learn that a fact was guessed.
7. **A blocking finding forbids the word 「complete」.** The handoff is either clean or
   explicitly `conditional`. There is no third state, and the checklist enforces it.
8. **Two review traps are named in the checklist**, because both are green-looking failures:
   coverage claimed by presence rather than content, and state matrices reviewed only where
   there is writing.

## 1.0.1 — 2026-08-29

**A role was given a duty its tools cannot perform.** `ux-researcher` was told to 「interview the
user」 with `AskUserQuestion` — a tool no subagent has. Caught on the first real run, by the
researcher itself, which reported the gap instead of simulating answers (the 「never write an
answer the user did not give」 bar working as intended).

Fixed by moving the act to where the capability is: the researcher **produces** the questions
and what each answer would change; the **orchestrator asks them at G1**. `PLAYBOOK.md` §3 Phase 1
and `agents/ux-researcher.md` both updated.

**The general lesson, worth carrying**: when a role prompt assigns an action, check the role's
`tools:` can perform it. A duty without a capability is a prompt that will be either ignored or
faked, and only one of those is detectable.

## 1.0.2 — 2026-08-29

**Four artifacts, one turn, one crash, three losses.** A Phase 2B agent gathered all its grounding,
announced it was writing four files, and died mid-turn when the machine slept. One file had landed.
The other three — and the reasoning that would have produced them — went with the turn.

`PLAYBOOK.md` §4 gains two rules: an agent owning several artifacts **writes each as it finishes**,
and the orchestrator **checks the filesystem before deciding how to recover**, resuming the same
agent rather than paying for the grounding twice.

**The general shape**: a turn is not a transaction. Anything a role produces incrementally should
be durable incrementally, and 「I am about to write」 is a status line, not a result.

## Staged for promotion (L2 → L1 when a round earns it)

- `QUALITY-BARS` §2A: a quantified pre-redesign baseline (clicks/fields/time per core task), so
  「better」 stops being an opinion.
- `QUALITY-BARS` §4: an adversarial pass where each blocker gets an agent trying to refute it.
- `PLAYBOOK` §3 Phase 4: a fifth lens for domain fitness in regulated or expert domains.

## 3.0.0 — 2026-08-30

**Major：角色从七个减到四个，并新增一个前置的 Router。** 用户在跑完一整轮完整闭环之后提的六条改进，逐条落地。

`ux-critic`（发现 + 定性质 + 定档位 + 裁定 + 台账）· `ux-designer`（界面/布局/组件/结构，吸收原 architect）· `fe-engineer`（前端代码）· `fe-tester`（验证，生效不了打回）。旧七角色归档在 `~/.claude/archive/agents-v1/`，未删。

1. **模型按「要不要做判断」分档，不按角色。** 做判断 → opus；照已定结论执行 → sonnet。依据是实测：那一轮里 opus 挣回成本的地方全部是判断（推翻编排者的前提、发现证据早于构建、拆穿一条空转断言），而改字面、扫替换、写量具用 sonnet 足够。

2. **`ux-critic` 兼裁定人。** 用户知情后选的：发现问题的人同时给问题定性。代价写在它自己的提示词里，并要求它对自己格外严（裁定写推导不写偏好 · 署自己的名绝不写成用户裁的 · 每条写明什么能推翻它）。结构上的补偿是 `fe-tester` 只读且独立，编排者仍逐条核 Critic 的数。

3. **前端代码从 Waterfall 移出。** `wf-developer` 收窄为后端专责；模板、样式，以及项目那条前后端分界线划到前端一侧的部分，归 `fe-engineer`。

4. **新增 Router 与能力台账。** 任务先分类（纯前端/纯后端/跨栈），台账只记「后端已经有什么」。**分类必须探代码，不许读 prompt** —— 上一轮有一份需求逐字写着「只修改前端」，而其中三项最后需要后端裁定，那个依赖是做到一半才浮出来的。台账的存在是因为：同一个后端事实被误记为「不存在」，挡了很久，最后靠有人去读源码才拆穿。

5. **P1/P2/P3 是硬闸。** 尺量是「项目声明的那个具名用户能不能完成任务」，不是缺陷难不难发现。上一轮花在 P3 上的往返明显多于 P1，而「操作失败但不说原因」这条 P1 很久没人动。**不带档位的发现不受理。**

6. **前后端的线**：开工前把「前端可改什么、后端才能改什么」写下来，署裁定人的名与日期；撞线就报，不自己越过去。**这条线由项目定，harness 不预置清单** —— 落点数量取决于渲染架构。上一轮这条线没写下来，卡了很久。

**没做的一件**：Designer 的第三方 skills 还没装 —— 候选已选出，但来源仓库没有 license，等用户定。
