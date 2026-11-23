# Standard change

> **Read `~/.claude/CONSTITUTION.md` first. It overrides this file; on conflict, follow it and report the conflict.**
> **Then `~/.claude/ORCHESTRATOR.md`: how you dispatch, decide, keep context and use gates.**

For a change to software that already exists and whose design holds: the work fits a one-page
plan. It keeps what makes a run trustworthy (a confirmed plan, tests written by another role, a
review, gates, a run log, the demo before and after) and drops the documents a new product needs.
Three to five dispatches.

Ask whether to switch to Full development (Constitution §7.3) when the plan would need a new
screen or flow designed, a new data model, a new external dependency, or an interface others
build on. The plan and the code so far carry over.

## 1. Kickoff

1. Models and configuration as `ORCHESTRATOR.md` § Capabilities says; `risk` as backend PLAYBOOK
   §2.3.
2. `docs/runs/<slug>/state.json` (`~/.claude/route/HANDOFF.md` §8) with `"tier": "standard"`, the
   `scope`, the goal in the user's words and its `kind` (`preserve` for a refactor).
3. The demo's before (`ORCHESTRATOR.md` § Demo), then `gate.py baseline`, before any dispatch.

The first line of every brief names the step: `1` plan, `2` build, `3` tests, `4` review.

## 2. Plan — step 1

Dispatch the engineer of each side the change touches. Cross-stack: the seam goes into the
contract first (`commands/route.md` §2); then backend first when the frontend reads what it adds,
otherwise both in one message, each in a worktree of its own (`ORCHESTRATOR.md` § Parallel), after
you committed `plan.md` with the headings below so that their rows merge. Each reads the code and its callers, writes its side of
`<run-dir>/plan.md`, and returns blocked on the Plan.

```
# Plan — <feature>
## Change
<what the user will see, a few lines>
## Files
| Path | Change | Side |
|---|---|---|
## Checks
| CHK | Shows | How |
|---|---|---|
| CHK-001 | <what it proves, in the user's terms> | test, or manual: <evidence path> |
## Retired tests
<tests removed with the code they covered, by path, or "none">
## Risks and assumptions
```

**Plan stop:** show the user the change, the checks and anything risky in a few lines (not the
file) and ask to confirm. On yes `log human --stop Plan --decision approved --by <user> --note "<what>"`.
Nothing is built before.

## 3. Build — step 2

Continue each engineer with the user's answer, both at once when there are two. It builds its
side and keeps the plan true: a file
it had to touch that the plan did not name is added to Files with the reason (the gate fails a
changed file the plan does not name). Gate `std-build`; a failure goes back to its owner.

## 4. Tests — step 3

`be-tester` for backend checks, `fe-tester` for interface checks: a test for each `CHK`, written
from the plan's wording and never from the code, carrying its `CHK` id in its name, a comment or
its docstring. A check no test can make is `manual:` with evidence you capture at the real entry
point. Failures go back to the engineer, then to the tester for those checks. `std-build` again
after any change.

## 5. Review — step 4

One reviewer, chosen by what the diff touches (the panel tables in the two PLAYBOOKs §6); its
brief says it is the sole reviewer, and you file what it returns as `<run-dir>/review.md`.
`risk: high`: that side's whole panel and its coordinator instead. Blockers and majors go back to
the engineer, then `std-build`, then a new reviewer of the same kind re-checks only the fixed
`FND`s and you set each `**Status:**`. Minors go to `<run-dir>/deferred.md`.

## 6. Acceptance

`gate.py demo after`, then `std-accept`, then the stop: the goal, the demo's before and after, the
user running their own check, and the `gate.py stats` table. On yes
`log human --stop Acceptance --decision approved --by <user> --note "<what>"` and `status: accepted`.
