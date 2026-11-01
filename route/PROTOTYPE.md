# Prototype — Phase 1b

The user sees something running and confirms it before any detailed design (Constitution §2.7).
Used by the Prototype tier (the whole run) and by Full development (Phase 1b, after requirements
and before detailed design). The orchestrator runs this procedure; one engineer builds.

## 1. Understand the ask

- **Full development:** the approved Phase 1 output (`01-requirements.md` or `01-brief.md`).
- **Prototype tier:** no requirements phase. Write down the ask in the user's words, then do
  recon (≈30 s, read-only: stack, existing code, what already runs).

## 2. Intent questions

Ask in one `AskUserQuestion`, in the user's language, at most 4 questions, each with a recommended
answer drawn from step 1. Pick the questions whose answer would change what the prototype shows:

- Who uses it, and in what situation?
- What must they see or do first — the one screen or flow that matters most?
- What would make you say "yes, this is it" at this stage?
- What is deliberately not in this round?
- Any look, product or site you want it to feel like (or not like)?

Record the answers in the project's `.claude/project-context.md` under `## Intent` (dated), so
later phases and runs read them.

## 3. Build the prototype — one engineer, one fresh dispatch

- **Who:** `fe-engineer` if the work has any interface; `be-developer` only for work with no
  interface (it then shows the behaviour through a runnable command with sample input and output).
- **Where:** `prototype/` at the project root, and nowhere else. It may contain throwaway stubs
  on either side of the frontend/backend line.
- **Brief:** the intent answers, the must-see screen or flow, and the non-goals, in the format of
  `~/.claude/route/HANDOFF.md` §3 (round 1). Paths, not pasted documents. The engineer appends
  its handoff entry to `<run-dir>/handoff.md`.
- **Rules for the engineer:** rough is right. Hard-coded or fake data, no tests, no design
  documents, no ids, no polish beyond what makes the main idea readable. It must start with one
  command, written at the top of `prototype/README.md` along with "throwaway, not product code".
- Log it: `gate.py log dispatch --agent <a> --model <m> --step 1b --note "prototype"` and its return.
  No `mark` and no gate run for this phase.

## 4. Show it and get confirmation

1. Run it yourself through its one command (Constitution §6.4), on a free port, never the user's.
2. Give the user the URL or the command and a two-line summary of what it shows.
3. Ask: **confirm**, **change** (what), or **stop**.
4. **Change:** a new, fresh dispatch with a short brief listing only the changes, the next round
   number, and the pitfalls from the previous engineer's handoff entry. After 3 rounds,
   ask the user whether to continue.
5. **Confirm:** log `gate.py log human --stop Prototype --decision approved --by <user> --note "<what was confirmed>"`
   (cross-stack runs: in both teams' run logs). Write `<run-dir>/01b-prototype.md`: what the user
   confirmed, what changed against step 1, how to run the prototype.

## 5. After confirmation

- **Prototype tier:** report and stop. Offer Full development as the next step; the confirmed
  prototype and the intent answers become its input.
- **Full development:** if the confirmation changed scope, the Phase 1 owner (`be-analyst` or
  `fe-critic`) amends the requirements or brief first. Then continue with the next phase. The gates
  refuse a detailed-design dispatch (step `3`) before the Prototype approval (`LOG.trail`).
- The prototype stays in `prototype/` as a reference. Product code is written from the design,
  never copied from it without the design saying so.
