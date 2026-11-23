# Backend Agent Team — Orchestration Playbook

> **Read `~/.claude/CONSTITUTION.md` first. It overrides this file; on conflict, follow it and report the conflict.**
> **Then read `~/.claude/ORCHESTRATOR.md`: how you dispatch, decide, keep context and use gates.**

What the Backend team runs and when, in Full development. Version: `harness_version` in
`~/.claude/harness/config.json`.

---

## 0. Roles

| Agent | Does |
|---|---|
| `be-analyst` | Requirements and fixture inputs; later the fixtures' expected outputs |
| `be-architect` | Architecture and detailed design |
| `be-developer` | Backend code (§3C), `08-implementation-log.md` |
| `be-tester` | Test plan, tests, test report |
| `be-review-behavior` · `-reliability` · `-security` | Review panel (§6), read-only |
| `be-reviewer` | Coordinator; re-checks fixed FNDs |
| Orchestrator | `state.json`, `07-acceptance.md`, `deferred.md`, filing read-only roles' returns |

Interface work goes to the Frontend team under §3C.

## 1. Configuration

The merged configuration (`ORCHESTRATOR.md` § Capabilities, Start); say which layers you merged.
Gates, panels, caps and paths come from it, never from memory. Rounds are counted in the run log
(`ORCHESTRATOR.md` § Decisions), not in `state.json`.

---

## 2. Kickoff

**2.1** The ask in the user's words, then its simplest useful version: that is the round. What the
user did not name (variants, legacy data, concurrency, migrations, non-functional axes) goes below
the cut line into `deferred.md`; the cut line goes in the analyst's brief.

**2.2 Recon (read-only, brief):** stack, build and test commands, a prior run, a confirmed prototype
(`01b-prototype.md`), and what a second copy of the project needs to build and run
(`ORCHESTRATOR.md` § Parallel). No `.claude/gates.json` → `gate.py profile`. A product that calls an LLM at
runtime: benchmark candidate models on a production-shaped prompt before build.

**2.3 One `AskUserQuestion`** (skip what `/route` asked). First a preview of what stands unless the
user changes it: models (`models.tiers[_active_tier]`), language
(documents in the user's unless `language.default_docs` names one; code in English), risk with its
evidence. Ask only:
- **Tier** (Constitution §7). A confirmed prototype is offered first ("Full development, reusing the
  prototype confirmed <date>"). Small change → `~/.claude/commands/route.md` §4; Standard change →
  `~/.claude/route/STANDARD.md`; Prototype → `~/.claude/route/PROTOTYPE.md`.
- **Goal** (Constitution §7.4): what the user will observe at the end and how they will check it;
  the round (§2.1) is what that goal needs, and nothing more.
- With an interface: the facts frontend PLAYBOOK §2.3 asks.

**Risk** is `high` for money, personal data, auth or secrets, irreversible operations or data
migration, schema changes, new external dependencies or public APIs. **Gate profile:** run each
detected command once, confirm the ones that work yourself (logged), ask only about the rest.

**2.4** Write `docs/runs/<slug>/state.json` (§8) with the goal in the user's words; an unfinished
run → `/route-resume`. Then the demo's before (`ORCHESTRATOR.md` § Demo), before any dispatch. A reused
prototype: `log human --stop Prototype --decision approved --by <user> --note "reused <path>,
confirmed <date>"`.

---

## 3. Phase flow

A phase ends when its gate exits 0; phase numbers are the run log's `--step` (there is no Phase 3:
it was merged into 2; section numbers are stable, so gaps are retired sections), named in each
brief's first line; the hook logs each dispatch and marks the panel's coordinator (§4.4). After any code
change, `p4` then `p5`. Each role's work stays with the agent that started it, across phases too
(`ORCHESTRATOR.md` § Boundaries): where a step below names a role that already worked in this
session, continue that agent; reviewers are always new. Writers a step sends out together each get
a worktree of their own (`ORCHESTRATOR.md` § Parallel).

**Phase 1 — Requirements.** `be-analyst` takes a recommended default for every open question and
declares fixtures (§3E). Its blocking questions go out with the prototype's intent questions; the
analyst amends. Gate `p1`.

**Phase 1b — Prototype** (`route/PROTOTYPE.md`; with an interface, the Frontend team up to its
Prototype stop, §3C.4). No gate; log `--step 1b`. The user confirms it running; a scope change goes
back to the analyst and `p1`. Nothing in Phase 2 starts before (Constitution §2.7).

**Phase 2 — Design.**
1. `be-architect` writes `02-architecture.md` and `03-detailed-design.md`; every `DES` names its
   `REQ` and `side` (§3C.3). New dependencies, schema changes and ties are decided and shown at Plan.
2. `risk: high`: the design review panel argues against it; one revision by the architect.
3. The analyst writes the fixtures' expected outputs and every point where the design misses a REQ;
   a contradiction goes back to the architect before Plan.
4. Gate `p2` (writes `gates/plan-review.md`).
- **Plan stop:** the review sheet, risk, open review items, assumptions. On yes
  `fixtures-approve --by <user>`. Nothing is built before.

**Phase 4 — Build.** `baseline` (once per run, before its first code writer); then in one message,
each in a worktree of its own (`ORCHESTRATOR.md` § Parallel): `be-developer` builds `side: backend`
items, one developer per group when the design's items fall into groups that share no file, each
brief naming its items and files; `be-tester` plans tests from requirements and design only; and
the Frontend team builds the `side: frontend` items whose seam is written in the contract (frontend
PLAYBOOK Phase 3), connecting real data once the backend half has landed. Land and gate each as it
returns. An unbuildable design goes back to the architect; it stops the run only if scope changes.
Gate `p4`.

**Phase 5 — Verification.** The tester that planned them implements and runs every `TC` (frontend
items: `fe-tester`, §3C.5). Failures go to their owner (§3C.6) naming only the failing TCs, then
back to the tester for those TCs. Gate `p5`. Never relax a test.

**Phase 6 — Review** (panel by §6; with frontend items, the frontend panel joins in the same message).
1. Panelists return candidates; keep them in `logs/`.
2. Two or more panelists: `be-reviewer` merges and tries to disprove each, dropping one only with
   counter-evidence. One panelist: its brief says it is the sole reviewer; it checks its own
   candidates and returns the report, and no coordinator runs. File the text as
   `06-review-report.md`; gate `p6`.
3. Blockers and majors go to their owners; minors to `deferred.md`; then Phase 5 on the affected TCs.
4. `be-reviewer` re-checks only the fixed FNDs; file its table in `06-review-report.md` §5
   and set each FND's `**Status:**` to `fixed in round <n>` or leave it `open` (back to step 3).
   At `loops.max_rounds` minors are deferred (Constitution §5.4).

**Phase 7 — Acceptance.** `gate.py demo after`, write `07-acceptance.md` (QUALITY-BARS § Phase 7),
gate `p7`, stop: lead with the goal, the demo's before and after, and the user running their own
check. On yes `status: accepted`.

## 3B. Increments

1. The run is never restarted. Record the user's words in `state.json` `increments`; a change to
   something approved is a Constitution §5.1 stop.
2. The original flow continues to its next fixed stop; there the increment joins at Phase 1 with only
   its items (Phase 1b only if the user will see something new) and the two share the stop.
3. Agents append `## Increment <n> — <date>` sections with only new or changed items; ids are never
   reused; a replaced item is retired in place (`retired, increment <n>`).
4. Gates read whole documents and the full suite still runs; review covers the increment's diff.

## 3C. The frontend/backend line

`~/.claude/route/FRONTEND_BACKEND_LINE.md`, cited here as §3C.n.

## 3D. Gates

`gate.py <gate> --project <root>`, run by you,
never by the agent checked; reports in `<run-dir>/gates/`. Phase gates are named in §3; exit codes
and waivers in `ORCHESTRATOR.md`. Authors check their own documents before returning with
`gate.py check <gate>`, which reads only and records nothing.

## 3E. Approved fixtures

Real input/output pairs the user confirms, which every later test must match.
1. `be-analyst` declares each REQ's fixtures and their real inputs in Phase 1, and writes the
   expected outputs in Phase 2 from the requirement, never from code (QUALITY-BARS § Phase 1–2).
2. At Plan the user approves, edits or rejects each; `fixtures-approve` hashes and locks them.
   Nothing is locked without their yes.
3. Tests load the approved files and are tagged `FX-nnn`; nobody edits them (`P4/P5.fixtures`).
4. An answer a newer decision replaces (Constitution §5): the analyst rewrites it, then
   `p2` and `fixtures-approve --by orchestrator --reapprove FX-nnn --because "<whose words, date>"`;
   list it at the next stop. An answer found wrong for any other reason: stop, show the user old and
   proposed, and lock the new one with `--reapprove FX-nnn` on their yes. Fixtures live in the
   project and accumulate into a regression suite.

## 3F. Human stops

**Fixed:** Kickoff, Prototype, Plan, Acceptance. Otherwise only a Constitution §5 case; everything
else is decided with a recommended default and shown at the next stop.

## 3G. Run log

Commands in `ORCHESTRATOR.md`. `p7` checks the trail follows §3's order.

---

## 4. Rules in every phase

1. No phase starts without its upstream document.
2. The handoff is `<run-dir>/handoff.md`, one current section per role; the code map is
   `docs/codemap.md` (`~/.claude/route/HANDOFF.md` §1, §7).
3. Traceability ids are mandatory; an id-less document goes back once.
4. Reviewers have Bash but no Write: the hook marks `be-reviewer` at the first reviewer dispatched
   after a gate run, so the mark covers the whole panel; `p6` checks the tree is unchanged.

## 6. Risk and review panel

| | `risk: normal` | `risk: high` |
|---|---|---|
| Design review | none | `review.design_panel` + one revision |
| Review panel | `be-review-behavior`; `-security` if the diff touches input parsing, auth, files, network or secrets; `-reliability` if it touches persistence, concurrency, external calls or long-running work | all of `review.backend_panel` |

`be-reviewer` coordinates when two or more panelists ran. Say whom you dispatched and why; a risk
change mid-run is a Constitution §5.1 stop.

## 7. Artifacts

```
docs/runs/<slug>/  (with an interface, the frontend PLAYBOOK §7 documents sit beside these)
  state.json  run-log.jsonl  01-requirements.md  01b-prototype.md  02-architecture.md  03-detailed-design.md
  04-test-plan.md  05-test-report.md  06-review-report.md  07-acceptance.md
  08-implementation-log.md  deferred.md  handoff.md  logs/
prototype/         throwaway prototype (Phase 1b, no interface)
```

## 8. `state.json`

`~/.claude/route/HANDOFF.md` §8.
