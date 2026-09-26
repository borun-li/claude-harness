# Brief — Duplicate upload message

- Author: fe-critic (filed by the orchestrator) · Status: draft

## 0. Understanding
- **Asked:** "when someone uploads a file we already have, tell them and take them to the original"
- **Means:** a rejected duplicate upload shows why and links to the stored file
- **Ambiguities:** show the original's uploader? — assumed: no, privacy (A1)

## 1. User and surface
- **Named user:** office admin who uploads 20–40 signed contracts a day
- **Surface:** browser

## 2. Tasks
| Task | What the user does | Success looks like | Frequency | Source |
|---|---|---|---|---|
| T-001 | Uploads a file that already exists | Sees it is a duplicate and opens the original in one click | several a week | "tell them and take them to the original" |

## 3. Scope
- **Cut line (above):** T-001
- **Below the line:** bulk upload summary of duplicates
- **Non-goals:** merging or deleting duplicates

## 4. Assumptions
| # | Assumption | Status | If wrong |
|---|---|---|---|
| A1 | The original's uploader is not shown | [unconfirmed] | message gains a name field |

## 5. Open questions
| # | Question | What the answer changes | Default |
|---|---|---|---|
| Q1 | Can every user open every stored file? | link vs. "ask an admin" text | link |
