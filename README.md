# Claude Harness

**A software team inside Claude Code.** You say what you want; specialist agents plan, build, test
and review it; scripts check each step; you sign off at a few fixed points.

---

## What it is

One long Claude Code session tends to review its own work, skip a check it feels sure about, and
lose the thread when the session ends. Claude Harness splits the work instead: one agent writes,
others test and review, a script checks each step's result, and every run is kept on disk so it
can stop and resume. It installs into `~/.claude` and works in every project.

---

## How it works

1. **One orchestrator, sixteen specialists.** Your session delegates; each agent has one job
   (analyst, architect, developer, tester, reviewer, UX, UI, frontend engineer…) and hands its
   work on as a document in `docs/runs/<name>/`.
2. **You decide at fixed points.** In between, the team takes the recommended default and shows it
   to you at the next stop. It interrupts only before something that cannot be undone.
3. **Scripts check the work.** After each step a gate checks that the documents are complete, each
   requirement has a test, the tests pass, and no agent changed files outside its role. A failed
   item is redone at most twice; then you are asked.
4. **Authors keep their work, reviewers start fresh.** A fix goes back to the agent that wrote the
   code; every review is done by a new agent that has not seen the author's reasoning.
5. **Independent work runs in parallel.** Agents working at the same time each get their own copy
   of the repository, and their changes are merged one by one.
6. **Everything is on disk.** The state, a log of every step, and before-and-after captures, so a
   run can be paused, resumed in a new session, and checked afterwards.

---

## Prerequisites

| To do this | You need |
|---|---|
| Anything | [Claude Code](https://claude.com/claude-code), Python 3.9+, git, Node.js 18+ with npm |
| Work on a web interface | Also Google Chrome (it captures the evidence) |
| A new visual design | Also the Figma plugin for Claude Code, with a seat that can write to Figma files |
| Build from a Figma design you have | The Figma plugin; read access is enough |
| A terminal interface | No Figma: screens are designed as text mockups |

Developed on macOS; Linux should work; on Windows use WSL.

---

## Quick Start

**1. Download.**

```sh
git clone https://github.com/borun-li/claude-harness.git
cd claude-harness
```

**2. Check the prerequisites.** It prints `prerequisites ok`, or each missing tool with what needs it.

```sh
./install.sh --check
```

**3. Install.** It backs up what it replaces, then copies the harness into `~/.claude`.

```sh
./install.sh
```

**4. Restart Claude Code and start.** In any project:

```
/route <what you want, in plain words>
```

Update later with `git pull && ./install.sh`. What install changes and how to undo it:
[GUIDE.md](GUIDE.md#installing-updating-uninstalling).

---

## Pick a tier

`/route` first asks how big the work is. You choose; the team never guesses.

| Tier | Choose it when | What the team does | You sign off |
|---|---|---|---|
| **Small change** | A tweak: no new data, no new dependency, nothing to decide about scope | One engineer plans, then builds | The plan · the result running |
| **Standard change** | Everyday work on software that exists; it fits a one-page plan | Plan → build → a separate tester → one reviewer | The plan · acceptance |
| **Prototype** | You want to see whether an idea is worth building | Designs the screens, then runs it with fake data | The design · the prototype |
| **Full development** | New screens or flows, new data, or a new dependency | Requirements → design → prototype → plan → build → tests → review panel | Kickoff · UX and UI · prototype · plan · acceptance |

Examples:

```
/route add a CSV export button to the orders page                # small: one button, existing data
/route add a status filter to the orders endpoint and its page   # standard: both sides, no new design
/route prototype a habit tracker                                 # prototype
/route let users reset their password by email                   # full: two new screens, stored reset
                                                                 #       tokens, sending email
```

If the work turns out bigger than its tier, the team stops and asks whether to switch.

You can also:

- **Build from a design you have.** Give the Figma link and say it is confirmed; the team asks
  only about what the design leaves out.
- **Change your mind.** Say so mid-run; the change joins at the next sign-off.
- **Pause and continue.** `/route-status` shows where a run stands; `/route-resume` continues it,
  also in a new session.
- **Use one specialist.** `have be-review-security review src/auth`: one agent, no phases.

---

## Commands

| Command | Does |
|---|---|
| `/route <what you want>` | Starts a run: asks the tier, decides frontend, backend or both, runs the team |
| `/route-status` | Shows a run: steps done, checks, what the last agents changed, open items |
| `/route-resume` | Continues a run, also in a new session |
| `/route-config` | Shows or changes models, review panels, limits and budgets; prints the version |

---

## Scope today

Built and tested on **web applications**: a backend, a browser frontend, or both. Terminal
interfaces work with text mockups and are less used so far; native and desktop apps need their
evidence supplied by hand. Details: [GUIDE.md](GUIDE.md#what-it-supports).

---

## Documentation

- [GUIDE.md](GUIDE.md): what install changes, each tier in detail, safety hooks,
  branches and pull requests, parallel work, long runs, configuration, upgrading, uninstalling
- [Backend team](backend/README.md) · [Frontend team](frontend/README.md): each team's flow and rules
- [ORCHESTRATOR.md](ORCHESTRATOR.md): how the main session dispatches and decides ·
  [CONSTITUTION.md](CONSTITUTION.md): the rules above every other file
- [CHANGELOG.md](CHANGELOG.md)

---

## Contributing

Work on a branch and open a pull request. Before merging, run the tests and record the change in
`CHANGELOG.md`: what changed, without project names or the story behind it.

```sh
(cd gates && npm ci && python3 -m unittest discover -s tests)   # npm ci once: the capture tests need it
for t in hooks/test_*.py; do python3 "$t" || break; done        # each script prints its cases and failures
```

---

## License

[MIT](LICENSE) © 2026 borun-li

Questions, bugs and ideas: [open an issue](https://github.com/borun-li/claude-harness/issues).
