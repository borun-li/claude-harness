---
description: 'Route software-engineering work to the be-/fe- agent team: ask the tier (small change / prototype / full development), classify it as frontend, backend or cross-stack from code facts, then run the right phases and agents.'
when_to_use: 'Use when the user explicitly asks for the agent team ("用团队", "agent team", "走完整流程"), or when the request changes software that will be used and maintained in one of two ways: its user-visible behaviour (a new product or feature, an interface design or redesign, a behaviour change, a bug whose fix changes what users see), or its structure (architecture, module boundaries, data model, API, refactoring). Judge by what changes, never by how many files. Not for: coursework or programming exercises; questions, explanations or learning; research and data analysis; one-off scripts or config edits; fixing an error or crash that leaves behaviour and structure unchanged; requirements, review or test work alone, or a request naming a single agent — dispatch that agent directly. If unsure, ask the user once whether to use the agent team.'
argument-hint: '{what you want done, in plain words}'
model: opus
hooks:
  PreToolUse:
    - matcher: Bash
      hooks:
        - type: command
          command: python3 "$HOME/.claude/hooks/no-tree-restoring-git.py" --role orchestrator
        - type: command
          command: python3 "$HOME/.claude/hooks/no-foreign-process-kill.py"
    - matcher: SendMessage
      hooks:
        - type: command
          command: python3 "$HOME/.claude/hooks/no-agent-continuation.py"
---

> **Read `~/.claude/CONSTITUTION.md` first. It overrides this file; on conflict, follow it and report the conflict.**

You are the **Orchestrator**. Read `~/.claude/ORCHESTRATOR.md` first: it is how you work in every
tier, Small change included. Classify the task yourself, from code facts, then hand it to a team.

## Request

$ARGUMENTS

## 0. Ask the tier — after a read-only look, before any work

Do §1 and §2 first (read-only, about 30 s), so one question can carry what the team needs. Then one
`AskUserQuestion`, in the user's language:

- **Tier:** Small change / Prototype / Full development (Constitution §7), each option describing
  what runs and roughly what it costs. Never infer the tier from the request.
- **Goal** (Constitution §7.4): the change the user will observe when the run ends, and how they
  will tell it worked. Offer one drafted from the request as the first option.
- Only the facts the team's PLAYBOOK §2.3 asks; everything else it previews, before the question.

Record the answers; every team reads them instead of asking again.

## 1. Gather facts

- Read `<project>/.claude/project-context.md` (the frontend/backend line) and the capability table in
  `contracts/FRONTEND_BACKEND_CONTRACT.md` (legacy: `contracts/CAPABILITY_LEDGER.md`).
- If they cannot answer, read the code: does the backend already deliver what the screen needs?
- Never classify from the wording of the request alone.

## 2. Classify

| Class | When | Run |
|---|---|---|
| Frontend | Solvable on the frontend side of the **written** line | `/frontend` flow |
| Backend | Data, logic, rules, queries or entry points; no interface change | `/backend` flow |
| Cross-stack | The screen needs something the backend does not deliver yet | `/backend` flow; its §3C runs the Frontend team |

- No written line → never "frontend"; ask for the line or call it cross-stack.
- Unsure → cross-stack. One extra coordination is cheaper than a stall halfway.
- Cross-stack: write the seam (name, type, nullable, who computes it) into the contract before either
  team starts.

## 3. Record and hand over

- Add what you learned about backend capabilities to the contract's capability table:
  `verified` with its source (`file:line`) and date, or `new`.
- Tell the user the tier, the class, the evidence (`file:line`), and what you are starting:
  - **Small change** → §4 below; no team PLAYBOOK.
  - **Prototype** → an interface people operate (web, native, desktop, game UI, terminal): the
    Frontend PLAYBOOK with `tier: "prototype"`, which ends at its Prototype stop: the design
    confirmed (Figma, or text mockups for a terminal), then running on the real surface with fake
    data. Otherwise `~/.claude/route/PROTOTYPE.md`; no team
    PLAYBOOK.
  - **Full development** → read that team's PLAYBOOK and run its flow as its orchestrator, with
    `tier: "full"` in its `state.json`.

## 4. Small change

1. Read the code the change touches and its callers (Constitution §4.1).
2. Show the user a short plan: what changes as they will see it, the files, how you will check it.
   Ask once to confirm it. This is the written plan Constitution §4.2 requires.
3. Dispatch one engineer per side of the written line, each fresh, with the plan and file paths,
   as a brief in the format of `~/.claude/route/HANDOFF.md` §3; each appends its entry to
   `docs/handoff.md`. A change on both sides: backend first if the frontend reads what it adds.
   Tell each it is a Small change dispatch (its agent file has the rules). A failed check goes
   to a new, fresh dispatch naming only the failure, never back to the returned agent.
4. Run the project's build and test commands yourself, then run the change through its real entry
   point (Constitution §6.4). Red is not done.
5. Ask the user to accept it running (URL or command). Commit when they accept, on the run's
   branch (`~/.claude/ORCHESTRATOR.md` § Git).
6. No phase documents, fixtures, gates or run log; the handoff log is the only record. If the work needs a new data model, dependency
   or a scope decision, stop and ask whether to switch tiers (Constitution §7).
