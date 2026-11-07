# Claude Harness

The shared Claude Code agent team for our web_dev group: a Backend team and a Frontend team with automatic gates between steps.
The orchestrator is your own Claude Code session: once `/route` (or a team command) loads `ORCHESTRATOR.md`, it dispatches the sixteen agents, holds the human stops and keeps the run on disk.
It lives in `~/.claude`, so it works in every project you open with Claude Code.

## Install

Prerequisites: [Claude Code](https://claude.com/claude-code), Python 3, Node.js with npm, git, and Google Chrome (used for frontend screenshots). For visual frontend design, the Figma plugin for Claude Code with a Full seat (writing to Figma files needs one). Plus whatever toolchain your own project needs.

```sh
git clone https://github.com/borun-li/claude-harness.git
cd claude-harness
./install.sh --check   # prerequisites only
./install.sh
```

What `install.sh` does:
- copies `CONSTITUTION.md ORCHESTRATOR.md agents commands backend frontend route gates hooks skills/design-taste` into `~/.claude` (`CLAUDE_HOME` installs elsewhere for testing only: the docs and hooks assume `~/.claude`);
- backs up any existing copies of those folders first, to `~/.claude/backup-harness-<date>.tgz`;
- adds two hooks to `~/.claude/settings.json`, leaving your other settings as they are:
  - one blocks git commands that throw away work (`git checkout -- .`, `git reset --hard`, …);
  - one stops a finished `be-*` / `fe-*` agent from being continued a second time, so each round gets a fresh agent;
- installs `playwright-core` for the gates.

Restart Claude Code afterwards.

**Update:** `git pull && ./install.sh`.

## Use

In a project folder, start Claude Code and either describe the work in plain words or type a command.

**Plain words.** A request that changes what users see (a new feature, a redesign, a behaviour change) or how the software is built (architecture, data model, API, refactoring) starts `/route` on its own. Coursework, questions, research, one-off scripts and fixes that change no behaviour do not. When it is unclear, Claude asks whether to use the team. You can also name one agent directly, for example "have `be-review-security` review this module".

| Command | Does |
|---|---|
| `/route <what you want>` | Single entry point: decides frontend, backend or cross-stack and runs the right team |
| `/backend <what to build>` | Backend team directly: requirements → prototype → design → build + tests → review panel (typed only) |
| `/frontend <what to build>` | Frontend team directly: features → UX → UI in Figma → build → verify and review (typed only) |
| `/backend-status`, `/frontend-status`, `/backend-resume`, `/frontend-resume` | See or continue a run |
| `/backend-config`, `/frontend-config` | Show or change models, gates, caps |

Every task starts with one question: which tier is it?

| Tier | What happens |
|---|---|
| Small change | Claude shows a short plan, you confirm, one engineer makes the change, you check it running |
| Prototype | A few questions about what you want, then a rough running version for you to try: for an interface people operate, the screens are designed first in Figma (text mockups for a terminal), or taken from a design you already confirmed, then run on the real surface with fake data |
| Full development | The whole team process. After requirements, you try and confirm a running prototype before any detailed design (skipped if you already confirmed one in a Prototype run); for an interface, its design is confirmed first unless you bring a confirmed one |

In Full development you also approve the plan (backend) or the UX and UI designs (frontend; one combined confirmation for a single page or component), and the final acceptance. Everything irreversible or outward-facing (deploys, pushes, deletes) waits for you. Other questions do not stop the run: the team takes a recommended default, marks it, and shows it to you at the next stop.

**Long runs.** Every round is done by a fresh agent with a short brief; what it learned goes into the run's `handoff.md`. At each stop the orchestrator writes its own entry and suggests `/clear`, then `/backend-resume` or `/frontend-resume`, so the session's context stays small.

## What is in here

| Path | What |
|---|---|
| `CONSTITUTION.md` | Rules that override every playbook |
| `ORCHESTRATOR.md` | How the orchestrator (the main session) dispatches, decides, keeps context and uses gates in every team |
| `commands/` | The slash commands above |
| `agents/` | Sixteen roles. Backend: `be-analyst` (also the product role for frontend-only runs), `be-architect`, `be-developer`, `be-tester`, the review panel `be-review-behavior`, `be-review-reliability`, `be-review-security` with its coordinator `be-reviewer`. Frontend: `fe-ux`, `fe-ui`, `fe-engineer`, `fe-tester`, the review panel `fe-review-experience`, `fe-review-accessibility`, `fe-review-integration` with its coordinator `fe-reviewer` |
| `backend/`, `frontend/` | Playbooks, quality bars, document templates, changelogs |
| `route/` | `PROTOTYPE.md` (the prototype procedure), `HANDOFF.md` (dispatch brief and handoff log) and `FRONTEND_BACKEND_LINE.md` (the line between the teams) |
| `gates/` | `gate.py`: automatic checks between steps, run log, fixtures, waivers, screenshot capture (tests in `gates/tests`) |
| `hooks/` | The git safety hook, the agent-continuation hook, and their tests |
| `skills/design-taste/` | The user's design taste, for `fe-ux`, `fe-ui` and `fe-review-experience` |

Harness version: backend 3.3.8, frontend 7.2.6 (see `backend/CHANGELOG.md`, `frontend/CHANGELOG.md`).

## Changing the harness

Make changes on a branch and open a pull request, so the whole group stays on the same version.
Before merging, run:

```sh
(cd gates && python3 -m unittest discover -s tests)
python3 hooks/test_no_tree_restoring_git.py
python3 hooks/test_no_agent_continuation.py
```

Record the change in the matching `CHANGELOG.md`.
