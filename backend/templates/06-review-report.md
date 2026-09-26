# Review Report — {Feature / Product}

- Compiled by: Orchestrator, from parallel be-reviewer lenses
- Lenses run: {correctness, security-and-robustness, maintainability-and-simplicity, traceability}
- Round: {n}   Date: {real date}

## 1. Verdict
{accept | accept with fixes | send back to development} — one paragraph of reasoning.

## 2. Findings
`Where` is `path:line` relative to the project root; the `p6` gate checks it exists.

| ID | Severity | Lens | Where | REQ | Claim |
|---|---|---|---|---|---|
| FND-001 | blocker | correctness | src/x.ts:214 | REQ-006 | |

### FND-001 — {claim}
- **Scenario:** {inputs/state -} wrong result>
- **Suggested direction:**
- **Status:** open | fixed in round n | accepted as-is (rationale)

## 3. Traceability audit
| REQ | Implemented (DES/file) | Tested (TC) | Status |
|---|---|---|---|

- Requirements implemented but not tested:
- Requirements neither implemented nor tested:
- Code serving no requirement (scope creep):

## 4. Dropped observations
<Raised by a lens but discarded for lacking a concrete failure scenario. Kept for the record
so the same non-issue is not re-litigated next round.>
