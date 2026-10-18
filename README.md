# Claude Harness

The shared Claude Code agent team for our web_dev group: a Backend team and a Frontend team, run by one orchestrator, with automatic gates between steps.
It lives in `~/.claude`, so it works in every project you open with Claude Code.

## Install

Prerequisites: [Claude Code](https://claude.com/claude-code), Python 3, Node.js with npm, git, and Google Chrome (used for frontend screenshots). Go only if the project is in Go.

```sh
git clone https://github.com/borun-li/claude-harness.git
cd claude-harness
./install.sh --check   # prerequisites only
./install.sh
```

What `install.sh` does:
- copies `CONSTITUTION.md agents commands backend frontend route gates hooks skills/design-taste` into `~/.claude` (set `CLAUDE_HOME` to install somewhere else);
- backs up any existing copies of those folders first, to `~/.claude/backup-harness-<date>.tgz`;
- adds one hook to `~/.claude/settings.json` that blocks git commands which throw away work (`git checkout -- .`, `git reset --hard`, …); your other settings stay as they are;
- installs `playwright-core` for the gates.

Restart Claude Code afterwards.

**Update:** `git pull && ./install.sh`.

## Use

In a project folder, start Claude Code and type:

| Command | Does |
|---|---|
| `/route <what you want>` | Single entry point: decides frontend, backend or cross-stack and runs the right team |
| `/backend <what to build>` | Backend team directly: requirements → architecture → design → build + tests → review |
| `/frontend <what to build>` | Frontend team directly: brief → structure → spec → queue → build → verify |
| `/backend-status`, `/backend-resume`, `/frontend-resume` | See or continue a run |
| `/backend-config`, `/frontend-config` | Show or change models, gates, caps |

Every task starts with one question: which tier is it?

| Tier | What happens |
|---|---|
| Small change | Claude shows a short plan, you confirm, one engineer makes the change, you check it running |
| Prototype | A few questions about what you want, then a rough, runnable version for you to confirm |
| Full development | The whole team process. After requirements, you see and confirm a rough running prototype before any detailed design |

In Full development you also approve the plan and the final acceptance. Everything irreversible or outward-facing (deploys, pushes, deletes) waits for you.

## What is in here

| Path | What |
|---|---|
| `CONSTITUTION.md` | Rules that override every playbook |
| `commands/` | The slash commands above |
| `agents/` | Nine roles: `be-analyst`, `be-architect`, `be-developer`, `be-tester`, `be-reviewer`, `fe-critic`, `fe-designer`, `fe-engineer`, `fe-tester` |
| `backend/`, `frontend/` | Playbooks, quality bars, document templates, changelogs |
| `route/` | `PROTOTYPE.md` (the prototype procedure) and the capability-table template |
| `gates/` | `gate.py`: automatic checks between steps, run log, fixtures, waivers, screenshot capture (tests in `gates/tests`) |
| `hooks/` | The git safety hook and its test |
| `skills/design-taste/` | Design guidance for `fe-designer` |

Harness version: backend 3.0.0, frontend 6.0.0 (see `backend/CHANGELOG.md`, `frontend/CHANGELOG.md`).

## Changing the harness

Make changes on a branch and open a pull request, so the whole group stays on the same version.
Before merging, run:

```sh
(cd gates && python3 -m unittest discover -s tests)
python3 hooks/test_no_tree_restoring_git.py
```

Record the change in the matching `CHANGELOG.md`.
