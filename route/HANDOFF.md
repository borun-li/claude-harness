# Dispatch brief and handoff

How Constitution §8 runs in every tier and team. The orchestrator writes the brief; the agent
writes the handoff entry. With the code map (§7) they replace an agent's memory between rounds, so
a fresh agent reads a little and starts, instead of rediscovering the codebase.

## 1. Where

| Run | Handoff |
|---|---|
| Full development, Standard change, Prototype | `<run-dir>/handoff.md` (`docs/runs/<slug>/`); both teams' agents keep their sections in it |
| Small change | `docs/handoff.md` |
| Direct call (one agent named, no tier) | `docs/handoff.md` |

The brief always names the file. It holds the current state only: one section per role, that
role's latest entry, plus the orchestrator's. A returning agent replaces its role's section; the
history is in git and the run log. The `CTX.handoff` check fails a second section for a role or a
section over 20 lines.

## 2. Counting

- **Ordinal** `#n`: the n-th dispatch of that agent type in this run. `gate.py status` prints the
  next one (Small change: count your own dispatches). A continued agent keeps its ordinal.
- **Round** `r`: the pass over an item at the current step. The first build or test pass is round
  1; each fix round after a gate, a failing test or a review adds one. The Prototype's change
  rounds count the same way. The hook counts rounds per item of the `Only:` line, from the log.

## 3. The brief (orchestrator → agent)

About 10–15 lines. Ids and paths, never pasted documents, logs or earlier conversation.

```
You are <agent> #<n> — step <s>, round <r>[, increment <i>].
Task: <one sentence: what is done when you return>
Increment: <i — append only to the `## Increment <i>` section of your documents; omit if none>
Only: <TC-014, FND-003, Q-5 … — the items of this dispatch; rounds are counted per item>
Evidence: <report path#entry for each failing item>
Feedback: <DFB-### to decide, or "raise a DFB for what you cannot build or draw as given"; omit if none>
Budget: <Figma calls left this run; omit for agents without Figma>
Read: docs/codemap.md, then <file:line this item touches, from its design item, queue row or finding>;
      handoff sections: <roles>
Code map: <"create it (§7)" when docs/codemap.md is missing and the role reads code; omit otherwise>
Known pitfalls / tried and failed: <≤3 lines, from earlier entries; "none" if none>
Do not touch: <out-of-round files or items; never a file outside the role's scope (Constitution §3):
            build and dependency manifests and runner config are the engineer's>
Tree: <"a copy of your own: start any instance on a free port, leave the run's preview alone";
      omit for an agent in the run's tree>
Check: <gate> — before returning, from your tree's root, `python3 ~/.claude/gates/gate.py check <gate> --project .` and fix
       what it reports about your documents, the code map and the handoff; omit for reviewers
Handoff: replace your role's section of <handoff path> before returning (~/.claude/route/HANDOFF.md §4);
         a role without Write puts it in its return instead.
Return: your agent file's output contract, plus `handoff: <entry header>`.
```

The first line is read by `hooks/run-log.py`: `step` is the run log's step (the PLAYBOOK's phase
number, e.g. `4` or `2b`), `round` is 1 for a step's first dispatch and higher for each redo.

A continued author (Constitution §8.1) gets only the first line, `Task`, `Only`, `Evidence` and
the files changed since it returned; it already has the rest. For a new agent, name only the
handoff sections it needs (usually its own role's and the one that reported the failure).
**The reading list** comes from the design item, queue row or finding, and from the last entry's
`Next agent reads`. The agent starts from the map and the list, reads the named items of a
document rather than the whole document, and opens anything else only when it needs it, naming it
in its entry so the next list and the map get better. This rule outranks any "read X" in an agent
file: those name where things are, not what to read end to end.

## 4. The entry (agent → handoff)

Time from a real `date -u +%FT%TZ`. At most 20 lines. It replaces your role's section. `gate.py
check` (the brief's `Check:` line) reads your documents the way the gate will, changes nothing and
counts no round: run it before you return, so a format slip does not cost a dispatch.

```
## <agent> #<n> · <phase or tier> · round <r>[ · increment <i>] · <ISO-8601 UTC>
Task: <the brief's task line>
Changed: <path (+a/-b) — what it does now>, or "nothing"
Visible: <what the user will see differently, and where (page or command)>, or "nothing yet"
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
code. At most 200 lines; a project too large for that keeps one line per module there and the
module's block in `docs/codemap/<module>.md`, each under the same cap, so an agent reads the index
and the modules its work touches. The `CTX.codemap` check fails a backticked path that no longer
exists, or a map over its cap.

```
# Code map
## `<module path>/`
Does: <one line>  Entry: `<file>:<symbol>`  Used by: <modules>
Invariants: <what must stay true>  Tests: `<path>`  Traps: <what bit an agent>
```

- **Create:** when it is missing, the brief to the first role that reads code (analyst, architect,
  engineer, tester) says so. It maps the modules it read and gives the rest one line each.
- **Keep:** a role that adds, moves or renames a file, or changes a module's entry or invariants,
  updates that module's lines in the same round. A pitfall that will outlive the round goes into
  that module's `Traps` as well as the handoff entry, which the next entry replaces. Designers and
  reviewers report a wrong line instead.
- It is a pointer, not evidence (Constitution §2.8): where it and the code disagree, the code wins
  and the agent fixes the map.

## 8. `state.json`

One per run, at `docs/runs/<slug>/state.json`, kept by the orchestrator after every transition.

```json
{
  "harness_version": "x.y.z", "feature": "one line", "slug": "run-slug",
  "goal": { "change": "what the user will observe", "check": "how they will tell it worked",
            "kind": "change | preserve" },
  "started_at": "ISO-8601", "updated_at": "ISO-8601",
  "status": "in_progress | blocked | accepted | abandoned | prototype_confirmed",
  "tier": "small | standard | prototype | full",
  "scope": "backend | frontend | cross-stack",
  "risk": "normal | high",
  "models": { "be-analyst": "opus", "…": "…" },
  "current_phase": "where the run is, e.g. 4, or be 4 · fe 3", "phases": [],
  "increments": [], "open_questions": [], "notes": []
}
```

With an interface (`scope` other than `backend`, tier `prototype` or `full`) it also holds
`"design": "new | external | reused"`, `"design_stops": 1`, `"delivery_surface"`,
`"primary_user_role"`, `"product_class": "tool | showcase"`, `"figma": { "file": "…", "budget": 60 }`,
`"stops": {}` and `"preview"`;
with a prototype step and no interface, `"prototype": "built | reused"`.
