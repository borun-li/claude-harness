# Guide

The details behind the [README](README.md): what you need, what install changes, each tier, and
how the parts work.

- [What it supports](#what-it-supports)
- [Prerequisites](#prerequisites)
- [Installing, updating, uninstalling](#installing-updating-uninstalling)
- [The tiers in detail](#the-tiers-in-detail)
- [Long runs](#long-runs)
- [How it works, in detail](#how-it-works-in-detail)
- [Safety hooks](#safety-hooks)
- [Branches and pull requests](#branches-and-pull-requests)
- [Configuration](#configuration)
- [Upgrading from 9.x / 14.x](#upgrading-from-9x--14x)
- [Repository structure](#repository-structure)

---

## What it supports

Built and tested on **web applications**: a backend, a browser frontend, or both.

| Interface | Design | Evidence and checks |
|---|---|---|
| Web | Figma | Automated: Chrome captures the DOM and computed styles at every screen size |
| Terminal | Text mockups | Automated capture of the program's output; less used so far |
| Native app, desktop | Figma | Manual: you or an instrument supply the evidence files; the gates do not yet recognise native UI code as frontend files |

Backend-only work does not depend on the interface. Per-test results (which the verification and
acceptance gates need) are read automatically from pytest, vitest, jest and playwright; any other
test runner needs a JUnit report path in `<project>/.claude/gates.json` (`"junit"`). Support
beyond the web grows as projects use it.

---

## Prerequisites

| To do this | You need |
|---|---|
| Anything | [Claude Code](https://claude.com/claude-code), Python 3.9+, git, Node.js 18+ with npm |
| Work on a web interface | Also Google Chrome (evidence capture) |
| A new visual design | Also the Figma plugin for Claude Code, with a seat that can write to Figma files |
| Build from a Figma design you have | The Figma plugin; read access is enough |
| A terminal interface | No Figma: screens are designed as text mockups |

Developed on macOS; Linux should work; on Windows use WSL.

The Figma agents list the Figma plugin's tools as `mcp__plugin_figma_figma__*`; if your server has
another name, change that line in `agents/fe-ux.md`, `agents/fe-ui.md` and `agents/fe-engineer.md`.
Each run has a Figma call budget under a monthly cap; the default cap (300) is the author's, so set
yours with `/route-config`. The cap is a number the orchestrator works to; nothing outside the run
counts your calls.

---

## Installing, updating, uninstalling

```sh
git clone https://github.com/borun-li/claude-harness.git
cd claude-harness
./install.sh --check    # "prerequisites ok", or each missing tool with what needs it
./install.sh            # ends with: done. Restart Claude Code, then run /route in a project.
```

Install backs up what it will replace to `~/.claude/backup-harness-<date>.tgz`, copies the harness
into `~/.claude` and installs `playwright-core` for the gates. To confirm, restart Claude Code and
run `/route-config` in any project: it prints the effective configuration and the version.

**What install changes.** After the backup, `CONSTITUTION.md`, `ORCHESTRATOR.md` and the folders
`harness/`, `backend/`, `frontend/`, `route/`, `gates/` in `~/.claude` are replaced. In `agents/`,
`commands/` and `hooks/` only the harness's own files are written, and a file an earlier version
installed is removed when the harness no longer ships it (listed in `~/.claude/.harness-files`);
your own agents, commands and hooks there stay. `skills/design-taste/` is replaced unless you
edited it (or it differs from the default and predates the install's record); then yours is kept
and the install says so. Your own defaults live in `~/.claude/harness-local/config.json` (written
by `/route-config`), which install never touches. Nothing else is touched; `settings.json` is not
changed (an update removes the hook entries earlier versions put there).

**Update** with `git pull && ./install.sh`.

**Uninstall.**
1. `./install.sh --uninstall` removes what install wrote and prints what it left: the backups,
   your `~/.claude/harness-local/`, a `design-taste` you edited, and your own agents, commands,
   hooks and `settings.json`. To get your earlier copies back instead:
   `tar xzf ~/.claude/backup-harness-<date>.tgz -C ~/.claude`.
2. Restart Claude Code.

---

## The tiers in detail

Describe the work in plain words, or start with `/route`. A request that changes what users see or
how the software is built starts the team; questions, research, one-off scripts and coursework do
not.

### Small change

For a change that needs no new data model, dependency or scope decision.

```
/route add a CSV export button to the orders page
```

One engineer per side reads the code and comes back with a short plan (what you will see change,
the files, how it will be checked); you say yes once and the same engineer builds it. The
orchestrator runs the build and tests, and you accept it running, with a capture of it before and
after. The only record is `docs/handoff.md` and the git history. If the work turns out bigger, it
stops and asks whether to switch tiers.

### Standard change

For everyday work on software that already exists: a change that fits a one-page plan and needs no
new screen design or data model, but should be tested by someone other than its author and
reviewed.

```
/route add a status filter to the orders endpoint and use it on the orders page
```

The engineer plans (the files, the checks), you confirm; it builds; a tester writes a test for
each check from the plan; one reviewer reads the diff; you accept it running, before and after
side by side. Three to five agents, with gates and a run log, and one document: the plan. A
refactor is a standard change whose goal is that behaviour stays the same.

### Prototype

For seeing whether something is worth building before committing to it.

```
/route prototype a habit tracker
```

With an interface, its screens are designed first (Figma, or text mockups for a terminal) and you
confirm them; then it runs on the real surface with fake data and you try it. Without an interface,
a throwaway prototype runs and you confirm its behaviour. The run ends there; a later Full
development run offers to reuse the confirmed prototype.

### Full development

For work that will be used and maintained: new screens or flows, a new data model, a new
dependency.

```
/route let users reset their password by email
```

The orchestrator reads the code and decides frontend, backend or both; a change on both sides runs
as one cross-stack run with one acceptance, and the two sides build at the same time once their
seam is written in the contract. You sign off at kickoff, the prototype and acceptance; backend
work also at the plan (design, risk and approved test fixtures), and a new interface also at UX
and UI. Deliverables go to `docs/runs/<slug>/`, one directory per run whatever its scope.

### From a design you already have

```
/route build the onboarding screens from this Figma file: <link>. The design is confirmed.
```

The design is taken in, not redrawn. UX and UI list its gaps (missing states, screen sizes) and you
answer them in one batch; then the prototype runs from it and the flow continues as a Prototype or
Full development run.

### Changing your mind, pausing, resuming

Tell the orchestrator the new requirement mid-run. The run is not restarted: the change joins at the
next sign-off. Where your new words replace something you approved earlier, the team follows them
and lists what it changed; anything else that would change an approved result comes back to you.

```
/route-status      # phases, sign-offs, checks, open items
/route-resume      # continue, also in a fresh session
```

Both work for any run, backend, frontend or cross-stack. With several open runs in a project,
`/route-status <slug>` names one and `/route-resume` asks which.

Between sign-offs you are asked only when something irreversible or outward-facing is about to
happen. Everything else is decided with a recommended default and shown to you at the next stop.
A question that doesn't block the run waits in a list while work continues.

### One agent, one job

For a review, a test plan or a design question without running the flow.

```
have be-review-security review src/auth
have fe-review-accessibility check the sign-up page
```

The named agent works alone: no phases, no sign-offs, no gates.

---

## Long runs

Each time something you can see is done, the orchestrator posts what changed and a link to the page
on the local preview, and sends a notification when you are away from the terminal. To get them:

- Desktop: Ghostty, Kitty and iTerm2 show them (in iTerm2, turn on Settings → Profiles → Terminal →
  Notification Center Alerts, and in Filter Alerts allow escape-sequence alerts); Apple Terminal
  does not. Allow notifications for your terminal in macOS settings, and note Focus / Do Not
  Disturb hides them.
- Phone: sign in with your claude.ai account, run `/remote-control` in the session (or turn on
  *Enable Remote Control for all sessions* in `/config`), and open the session in the Claude app.
- Keep the machine awake: start with `caffeinate -i claude` on macOS. A run that must survive the
  laptop closing belongs in a cloud session (claude.ai/code).

---

## How it works, in detail

- **Orchestrator** — the main session dispatches, decides with recommended defaults and keeps
  context ([`ORCHESTRATOR.md`](ORCHESTRATOR.md)). [`CONSTITUTION.md`](CONSTITUTION.md) overrides
  every other file.
- **A goal per run** — with the tier, you say what change you will see when the run ends and how
  you will check it; the run does not grow past it, and Acceptance opens with your check.
- **Round caps** — each item may be redone twice by default (`loops.max_rounds`); after that the
  run asks you instead of looping.
- **Authors continue, judges are new** — the agent that wrote a piece of work keeps it: fixes,
  revisions and its role's next step go back to it while its context is small, so it does not
  re-read the codebase. Reviewers and verifiers are new every time, so no review inherits the
  author's blind spots.
- **Writers in parallel** — independent work goes out together: build groups, a developer and the
  tester planning its tests, both sides of a cross-stack run once their seam is written in the
  contract. Writers that are out together each work in a git worktree of their own; `gate.py land`
  checks each one's changes against its role, commits them and merges them onto the run's branch,
  leaving a real conflict to the author of the later change. Gates run on what has landed while
  other writers are still out. Once per project, `gate.py worktrees --setup --link <dependency
  dirs>` writes `worktree.baseRef: "head"` and `symlinkDirectories` into the project's
  `.claude/settings.json`.
- **Code map and reading list** — a short `docs/codemap.md` and a brief that names the lines to
  read let a new agent start in minutes instead of rediscovering the codebase; `handoff.md`
  keeps only each role's latest note.
- **What each agent changed** — every writer's return is recorded with the files it changed and
  what you will see differently, landed as one commit, and reported to you in one line;
  `gate.py status` shows the last ones and `gate.py stats` the time and tokens per dispatch.
- **Before and after** — at kickoff the run captures your check at its real entry point (a
  screenshot, or a command's output and time), and again on the final code; Acceptance opens with
  the two side by side, and its gate fails if either is missing or nothing changed.
- **Automatic gates** — between phases, `gates/gate.py` checks documents, traceability, tests and
  the working tree. Only the orchestrator runs a gate; an author can run its read-only self-check
  (`gate.py check`) before returning, so a format slip does not cost a round.
- **Taste measures** — on a tool-class web product, each capture also measures the page (font
  families, text sizes, corner radii, gradients, dialogs open at once) against `taste` in the
  configuration, whose defaults are the values of `skills/design-taste`. Differences are printed
  for the reviewer and for you; they fail nothing. Set your own values with `/route-config`.
- **Run log** — every dispatch, landing, gate, waiver and sign-off goes to one log per run, which
  status, resume and the final checks read. It is hash-chained against accidental edits; it is not
  proof against forgery.

---

## Safety hooks

Four hooks, declared in the agent and command files, so they act only in harness sessions: inside
every `be-*` and `fe-*` agent, and in your session from the moment `/route` or `/route-resume`
runs until the session ends.

- One blocks git commands that discard uncommitted work or force and rewrite history, and keeps git
  writes to the main session (branch, commit, push the run's branch, draft PR).
- One blocks stopping processes by name, pattern or port: an agent stops only a process it started.
- One limits reusing a finished agent to the author of the work, within a context limit.
- One writes every dispatch and return to the run log and enforces the round cap, counting redo
  rounds from the log itself, so neither depends on memory.

There Claude cannot run `git stash`, `git checkout -- <file>`, `pkill` and similar commands; run
such a command yourself with `! <command>` in the prompt. Other sessions are not affected. A
session reopened with `claude --resume` has no hooks until `/route-resume` runs in it; an agent
returning there without them is reported at once. The hooks guard against mistakes, not against a
determined bypass.

---

## Branches and pull requests

Each run works on its own branch, and each agent's work lands on it as one commit
(`gate.py land`); only the main session does git writes, never an agent. To let it also push that
branch and open a draft pull request for you to review and merge, add `"git": {"push": true}` to
`<project>/.claude/gates.json` (the harness asks at the start of a run if the key is missing).
Merging the pull request, force pushes, deleting unmerged branches and rewriting history stay
yours; the hook lets the main session run only the git writes a run needs.

---

## Configuration

`/route-config` shows the effective configuration; `/route-config <what to change>` changes it,
globally or for one project.

The version is `harness_version` in `harness/config.json`, one for the whole harness.
Configuration is read in three layers, each overriding the one before: `harness/config.json`, your
own defaults in `~/.claude/harness-local/config.json`, and a project's `.claude/harness.json`.
Gate settings are separate: `gates/config.json` and `<project>/.claude/gates.json`.

---

## Upgrading from 9.x / 14.x

The backend (9.x) and frontend (14.x) versions are now one harness version, 16.0.0, with one
configuration and one run directory. In each project that used them:

- Move the keys of `.claude/backend.json` and `.claude/frontend.json` into `.claude/harness.json`
  (models are now under `models`). `gate.py` names what is left to move.
- Global values you had edited in `~/.claude/backend/config.json` or `frontend/config.json` are in
  the install backup; set them again with `/route-config`.
- `git mv docs/frontend/observables.json docs/observables.json`.
- Old runs under `docs/backend/` and `docs/frontend/` stay as history; new runs go to
  `docs/runs/<slug>/`. A run still in progress is finished on the version that started it. New
  runs continue the ids (`REQ`, `TC`, …) only of runs under `docs/runs/`: to keep the numbering
  going, `git mv` each finished run directory there under a name of its own.

---

## Repository structure

```
claude-harness/
├── README.md · GUIDE.md
├── LICENSE
├── install.sh            # back up, copy into ~/.claude
├── CONSTITUTION.md       # rules that override everything else
├── ORCHESTRATOR.md       # how the main session dispatches, decides and keeps context
├── CHANGELOG.md          # one changelog for the whole harness
├── harness/              # config.json: the defaults and the version
├── commands/             # /route, /route-resume, /route-status, /route-config
├── agents/               # the sixteen be-* and fe-* roles
├── backend/ · frontend/  # each team's README, playbook, quality bars, templates
├── route/                # standard-change and prototype procedures, handoff format, the frontend/backend line
├── gates/                # automatic checks, run log and evidence capture, with tests
├── hooks/                # the safety and run-log hooks, with their tests
└── skills/design-taste/  # the author's interface taste; edit it to yours (a project's brand wins)
```
