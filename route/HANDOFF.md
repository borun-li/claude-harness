# Dispatch brief and handoff log

How Constitution §8 runs in every tier and team. The orchestrator writes the brief; the agent
writes the handoff entry. Together they replace an agent's memory between rounds.

## 1. Where

| Run | Handoff log |
|---|---|
| Full development, Prototype | `<run-dir>/handoff.md` (`docs/backend/…` or `docs/frontend/…`) |
| Small change | `docs/handoff.md` |
| Direct call (one agent named, no tier) | `docs/handoff.md` |
| Cross-stack | the orchestrating team's run dir; both teams' agents append to it |

The brief always names the file. Append only; never rewrite or delete an entry.

## 2. Counting

- **Ordinal** `#n`: the n-th dispatch of that agent type in this run. Count it from `run-log.jsonl`
  (or the log's own headers for Small change) before dispatching.
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
Read: <paths>; handoff entries: <their headers>
Known pitfalls / tried and failed: <≤3 lines, from earlier entries; "none" if none>
Do not touch: <out-of-round files or items>
Handoff: append your entry to <handoff path> before returning (~/.claude/route/HANDOFF.md §4).
Return: your agent file's output contract, plus `handoff: <entry header>`.
```

Name only the entries the agent needs (usually the last one for its role and the one that
reported the failure), not the whole log.

## 4. The entry (agent → log)

Time from a real `date -u +%FT%TZ`. At most about 15 lines.

```
## <agent> #<n> · <phase or tier> · round <r>[ · increment <i>] · <ISO-8601 UTC>
Task: <the brief's task line>
Changed: <path (+a/-b) — what it does now>, or "nothing"
Result: <pass/fail counts, gate verdict or outcome> — evidence: <path>
Next agent must know:
- Pitfalls: <environment quirks, traps, order that matters>
- Tried, did not work: <approach — why>
- Left open: <items not finished, and why>
```

Read-only roles (reviewers, critics) put the entry in their return; the orchestrator appends it
unchanged. An agent that dies leaves no entry: the orchestrator writes one from the disk
(`orchestrator for <agent> #<n>`), then dispatches a fresh agent.

## 5. Orchestrator entries

At every human stop, and before suggesting a fresh session, the orchestrator appends:

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
evidence.
