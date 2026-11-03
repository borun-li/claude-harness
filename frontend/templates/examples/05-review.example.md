# Review — Duplicate upload message

- Compiled by: fe-reviewer (coordinator) · Round: 1 · Date: 2026-11-05
- Panelists run: fe-review-experience (always), fe-review-integration (the diff maps API errors) — accessibility not run: no new interactive component (PLAYBOOK §6)
- Evidence: `evidence/verify-1/manifest.md`

## 1. Verdict
accept with fixes — one major: the duplicate notice never appears on a slow network.

## 2. Findings
| ID | Severity | Panelist | Where | Ref | Claim |
|---|---|---|---|---|---|
| FND-001 | major | integration | web/upload/api.ts:31 | PAGE-001 error | A 409 arriving after the 10 s client timeout shows "Upload failed" |

### FND-001 — A late 409 shows "Upload failed"
- **Scenario:** Dana on a slow phone connection uploads a duplicate; the 409 arrives at 12 s; she reads "Upload failed" and uploads again.
- **Suggested direction:** let the server's answer win over the client timeout.
- **Status:** open

## 3. Dropped by the coordinator
| Candidate | Panelist | Claim | Counter-evidence |
|---|---|---|---|
| E-2 | experience | link has no focus style | `evidence/verify-1/Q-001-dup@1440.styles.json`: `:focus-visible` outline 2px solid |

## 4. Deferred
E-3 (minor: notice icon 1px off baseline)

## 5. Re-check (fix rounds)
| FND | Result | Evidence |
|---|---|---|
