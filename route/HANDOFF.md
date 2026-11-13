# Dispatch brief and handoff

How Constitution §8 runs in every tier and team. The orchestrator writes the brief; the agent
writes the handoff entry. With the code map (§7) they replace an agent's memory between rounds, so
a fresh agent reads a little and starts, instead of rediscovering the codebase.

## 1. Where

| Run | Handoff |
|---|---|
| Full development, Prototype | `<run-dir>/handoff.md` (`docs/backend/…` or `docs/frontend/…`) |
| Small change | `docs/handoff.md` |
| Direct call (one agent named, no tier) | `docs/handoff.md` |
| Cross-stack | the orchestrating team's run dir; both teams' agents keep their sections in it |

The brief always names the file. It holds the current state only: one section per role, that
role's latest entry, plus the orchestrator's. A returning agent replaces its role's section; the
history is in git and the run log. The `CTX.handoff` check fails a second section for a role or a
section over 20 lines.

## 2. Counting

- **Ordinal** `#n`: the n-th dispatch of that agent type in this run. Count it from `run-log.jsonl`
  (Small change: your own dispatches) before dispatching.
- **Round** `r`: the pass of the current step. The first build or test pass is round 1; each fix
  round after a gate, a failing test or a review adds one. The Prototype's change rounds count
  the same way.

## 3. The brief (orchestrator → agent)

About 10–15 lines. Ids and paths, never pasted documents, logs or earlier conversation.

```
You are <agent> #<n> — <phase or tier>, round <r>[, increment <i>].
Task: <one sentence: what is done when you return>
Increment: <i — append only to the `## Increment <i>` section of your documents; omit if none>
Only: <TC-014, FND-003, Q-5 … — the items of this round>
Evidence: <report path#entry for each failing item>
Feedback: <DFB-### to decide, or "raise a DFB for what you cannot build or draw as given"; omit if none>
Budget: <Figma calls left this run, the number given to `log dispatch --figma-left`; omit for agents without Figma>
Read: docs/codemap.md, then <file:line this item touches, from its design item, queue row or finding>;
      handoff sections: <roles>
Code map: <"create it (§7)" when docs/codemap.md is missing and the role reads code; omit otherwise>
Known pitfalls / tried and failed: <≤3 lines, from earlier entries; "none" if none>
Do not touch: <out-of-round files or items>
Handoff: replace your role's section of <handoff path> before returning (~/.claude/route/HANDOFF.md §4);
         a role without Write puts it in its return instead.
Return: your agent file's output contract, plus `handoff: <entry header>`.
```

Name only the sections the agent needs (usually its own role's and the one that reported the
failure). **The reading list** comes from the design item, queue row or finding, and from the last
entry's `Next agent reads`. The agent starts from the map and the list, reads named items of a
document rather than the whole document, and opens anything else only when it needs it, naming it
in its entry so the next list and the map get better.

## 4. The entry (agent → handoff)

Time from a real `date -u +%FT%TZ`. At most 20 lines. It replaces your role's section.

```
## <agent> #<n> · <phase or tier> · round <r>[ · increment <i>] · <ISO-8601 UTC>
Task: <the brief's task line>
Changed: <path (+a/-b) — what it does now>, or "nothing"
Feedback: <DFB-### raised or decided, one line each>, or omit
Result: <pass/fail counts, gate verdict or outcome> — evidence: <path>
Next agent must know:
- Pitfalls: <environment quirks, traps, order that matters>
- Tried, did not work: <approach — why>
- Left open: <items not finished, and why>
Read beyond the list: <path — why>, or "nothing"
Next agent reads: <file:line the next agent on this work needs>
```

Roles without Write (`be-review-*`, `be-reviewer`, `fe-review-*`) put the entry in their return; the orchestrator files it
unchanged as that role's section. An agent that dies leaves no entry: the orchestrator writes one from the disk
(`orchestrator for <agent> #<n>`), then dispatches a fresh agent.

## 5. Orchestrator entries

At every human stop, and before suggesting a fresh session, the orchestrator replaces its section with:

```
## orchestrator · <phase> · <stop or reason> · <ISO-8601 UTC>
State: <phase, status, gate verdicts, loop counters>
Decided: <decisions since the last orchestrator entry, each with who decided>
Open: <questions, findings, rows>
Next: <the exact next step>
```

What it then tells the user is in `~/.claude/ORCHESTRATOR.md`, Handoff.

## 6. Long output

Command output beyond about 50 lines goes to a file under `<run-dir>/logs/` (Small change:
`docs/logs/`), named after the agent and round. Read it with `tail` or `grep`; cite the path as
evidence. Roles without Write (§4) use a scratch file outside the project tree instead, so the
review gates' tree check stays meaningful.

## 7. Code map

`docs/codemap.md`, one per project, shared by both teams: what every agent reads before opening
code. At most 200 lines. Backticks hold paths only; the `CTX.codemap` check fails one that no
longer exists, or a map over its cap.

```
# Code map
## `<module path>/`
Does: <one line>  Entry: `<file>:<symbol>`  Used by: <modules>
Invariants: <what must stay true>  Tests: `<path>`  Traps: <what bit an agent>
```

- **Create:** when it is missing, the brief to the first role that reads code (analyst, architect,
  engineer, tester) says so. It maps the modules it read and gives the rest one line each.
- **Keep:** a role that adds, moves or renames a file, or changes a module's entry or invariants,
  updates that module's lines in the same round. Designers and reviewers report a wrong line instead.
- It is a pointer, not evidence (Constitution §2.8): where it and the code disagree, the code wins
  and the agent fixes the map.
