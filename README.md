# Claude Harness

A software-development agent team for Claude Code: backend and frontend roles, human sign-offs, automatic gates.

Your Claude Code session becomes the orchestrator: it asks you a few questions, hands each step to
a fresh specialist agent (sixteen in two teams), runs automatic checks between steps, and stops for
your sign-off at fixed points. You see something running before details are designed, and every
run is kept on disk so it can be resumed. It installs into `~/.claude`, so it works in every project.

## Install

Prerequisites: [Claude Code](https://claude.com/claude-code), Python 3, Node.js with npm, git and
Google Chrome (frontend evidence capture). For visual interface design: the Figma plugin for
Claude Code with a seat that can write to Figma files. The Figma agents list its tools as
`mcp__plugin_figma_figma__*`; if your server has another name, change that line in
`agents/fe-ui.md` and `agents/fe-engineer.md`.

```sh
git clone https://github.com/borun-li/claude-harness.git
cd claude-harness
./install.sh --check   # prerequisites only
./install.sh
```

`install.sh` backs up what it will replace to `~/.claude/backup-harness-<date>.tgz`, copies the
harness into `~/.claude`, registers two safety hooks in `~/.claude/settings.json` (one blocks git
commands that discard work, one stops a finished agent from being reused), and installs
`playwright-core` for the gates. Restart Claude Code afterwards. Update with `git pull && ./install.sh`.

## Use

In a project, describe the work in plain words. A request that changes what users see or how the
software is built starts `/route`; questions, research, one-off scripts and coursework do not. You
can also call one agent by name, for example "have `be-review-security` review this module".

| Command | Does |
|---|---|
| `/route <what you want>` | Asks the tier, decides frontend, backend or both, starts the right team |
| `/backend`, `/frontend` | Start one team directly |
| `/backend-status`, `/frontend-status` | Show a run: phases, gates, open items |
| `/backend-resume`, `/frontend-resume` | Continue a run, also in a fresh session |
| `/backend-config`, `/frontend-config` | Show or change models, panels, caps, budgets |

Every task starts with one question: which tier?

| Tier | What happens |
|---|---|
| Small change | A short plan, your yes, one engineer, you check it running |
| Prototype | A rough version running for you to try; an interface is designed first (Figma, or text mockups for a terminal) unless you bring a confirmed design |
| Full development | Prototype first, then design, build, tests, review and your acceptance |

You are asked only at fixed sign-offs and when something irreversible or outward-facing is about
to happen. Everything else is decided with a recommended default and shown to you at the next stop.

## Teams

- [Backend team](backend/README.md): requirements, architecture, build, tests, review.
- [Frontend team](frontend/README.md): UX, UI in Figma, a running prototype, build on the real
  surface, verification and review.

A change that needs both runs as one cross-stack run with a single acceptance.

## Repository

| Path | What |
|---|---|
| `CONSTITUTION.md` | Rules that override everything else |
| `ORCHESTRATOR.md` | How the main session dispatches, decides and keeps context |
| `commands/`, `agents/` | Slash commands and the sixteen agent roles |
| `backend/`, `frontend/` | Each team's playbook, quality bars, templates, config and changelog |
| `route/` | Prototype procedure, dispatch and handoff format, the frontend/backend line |
| `gates/` | Automatic checks, run log and evidence capture, with tests |
| `hooks/`, `skills/design-taste/` | Safety hooks; the design-taste skill |

Versions: `harness_version` in `backend/config.json` and `frontend/config.json`.

## Contributing

Work on a branch and open a pull request. Before merging, run the tests and record the change in
the matching `CHANGELOG.md`:

```sh
(cd gates && python3 -m unittest discover -s tests)
python3 hooks/test_no_tree_restoring_git.py
python3 hooks/test_no_agent_continuation.py
```

Bugs and ideas: [open an issue](https://github.com/borun-li/claude-harness/issues).

## License

[MIT](LICENSE) © 2026 borun-li
