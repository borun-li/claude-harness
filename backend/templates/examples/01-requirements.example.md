# Requirements — Duplicate upload guard

- Author: be-analyst · Status: draft

## 0. Understanding
- **Asked:** "don't let people upload the same file twice"
- **Means:** an upload whose content already exists is refused and points to the original
- **Ambiguities:** same name but different content — assumed: allowed (A1)

## 1. Requirements
### REQ-001 — Refuse duplicate content
- **Cut:** above
- **Behaviour:** An upload whose SHA-256 matches a stored file is refused with the original's id.
- **Accept:** Given file X stored as id 17, When X is uploaded again, Then the response is 409 `{"duplicate_of": 17}`
- **Source:** "don't let people upload the same file twice"
- **Fixtures:** FX-001

### REQ-002 — Duplicate check across users
- **Cut:** below
- **Behaviour:** The check spans all users, not only the uploader.
- **Accept:** Given user A stored X, When user B uploads X, Then B gets 409
- **Source:** "the same file" (scope across users not stated)
- **Fixtures:** n/a — deferred

## 2. Non-goals
- Near-duplicate detection (resized images, re-encoded PDFs).
- Deleting existing duplicates.

## 3. Assumptions
| # | Assumption | Status | If wrong |
|---|---|---|---|
| A1 | Same name, different content is allowed | [unverified] | REQ-001 also checks names |

## 4. Open questions
| # | Question | Default | Blocks |
|---|---|---|---|
| Q1 | Should REQ-002 ship this round? | No | REQ-002 |

## 5. Non-functional
| Axis | This round |
|---|---|
| Performance | hash check adds < 50 ms at 20 MB |
| Security & secrets | not this round |
| Data & retention | hashes kept as long as the file |
| Errors | 409 body names the original id |
| Observability | log `duplicate_rejected` with both ids |
