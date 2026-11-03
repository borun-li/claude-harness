# Review — {feature}

- Compiled by: fe-reviewer (coordinator) · Round: {n} · Date: {real date}
- Panelists run: {fe-review-experience, fe-review-accessibility, fe-review-integration} — and why (PLAYBOOK §6)
- Evidence: `evidence/verify-<n>/manifest.md`

## 1. Verdict
{accept | accept with fixes | send back} — one short paragraph.

## 2. Findings
`Where` is a file under the run dir (`evidence/…`) or `path:line` in the project; the `fe-review`
gate checks it exists. `Ref` is the UX or contract item (`FLOW-002`, `PAGE-003 error`, `C-04`, WCAG).

| ID | Severity | Panelist | Where | Ref | Claim |
|---|---|---|---|---|---|
| FND-001 | blocker | experience | evidence/verify-1/{file} | PAGE-001 error | |

### FND-001 — {claim}
- **Scenario:** {this user, this size, this state, trying this, gets this}
- **Suggested direction:**
- **Status:** open | fixed in round n | accepted as-is (rationale)

## 3. Dropped by the coordinator
Candidate ids are the panelists' own (`E-1`, `A-1`, `I-1`), never `FND-`.

| Candidate | Panelist | Claim | Counter-evidence |
|---|---|---|---|

## 4. Deferred
Minors and candidates outside the cut line: {ids}

## 5. Re-check (fix rounds)
| FND | Result | Evidence |
|---|---|---|
