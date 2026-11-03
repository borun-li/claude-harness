# Review Report — {Feature / Product}

- Compiled by: be-reviewer (coordinator), filed by the orchestrator
- Panelists run: {be-review-behavior, be-review-reliability, be-review-security} — and why (PLAYBOOK §6)
- Round: {n}   Date: {real date}

## 1. Verdict
{accept | accept with fixes | send back to development} — one paragraph of reasoning.

## 2. Findings
`Where` is `path:line` relative to the project root; the `p6` gate checks it exists.

| ID | Severity | Panelist | Where | REQ | Claim |
|---|---|---|---|---|---|
| FND-001 | blocker | behavior | src/x.ts:214 | REQ-006 | |

### FND-001 — {claim}
- **Scenario:** {inputs/state → wrong result}
- **Suggested direction:**
- **Status:** open | fixed in round n | accepted as-is (rationale)

## 3. Dropped by the coordinator
Every candidate the coordinator disproved, with its counter-evidence. Kept so the same non-issue is
not re-litigated next round. Candidate ids are the panelists' own (`B-1`, `R-1`, `S-1`), never
`FND-`: only survivors get an `FND-###`.

| Candidate | Panelist | Claim | Counter-evidence (`file:line` or command output) |
|---|---|---|---|

## 4. Deferred
Candidates outside the cut line, or minors, moved to `NN-deferred.md`: {ids}

## 5. Re-checks
Filed by the orchestrator from each re-check `be-reviewer`; it then sets the FND's `**Status:**`.

| Round | FND | Fixed? | Evidence (`file:line` or command output) |
|---|---|---|---|
