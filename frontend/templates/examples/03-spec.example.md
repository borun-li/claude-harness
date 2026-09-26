# Specification — Duplicate upload message

- Author: fe-designer · Input: `01-brief.md`, `02-structure.md`

## 1. Tokens
| Semantic token | Primitive | Value | Use |
|---|---|---|---|
| `color-status-warning` | `amber-700` | #B45309 | duplicate notice text and icon |

## 2. Components
### CMP-001 — Result notice
- **Variants:** success · warning · error
- **States:** default · focus (link) · empty (hidden)
- **Sizes and limits:** file name max 60 chars, then middle-truncate with full name in tooltip
- **Accessibility:** `role="status"`; icon has text; link names the file

## 3. Pages
### PAGE-001 — Upload
- **Goal:** upload one file and learn the outcome · **Serves:** T-001
- **Components:** CMP-001
- **States:**

| State | What renders | Copy |
|---|---|---|
| loading | progress bar | "Uploading…" |
| empty | picker, Upload disabled | — |
| success | success notice | "Uploaded" |
| duplicate | warning notice with link | "Already uploaded. Open the original" |
| error | error notice with Retry | "Upload failed. Try again" |
| permission-denied | notice, no picker | "You can't upload here. Ask an admin." |

- **Permissions:** any signed-in user can upload and open
- **Accept:** AC-001 — uploading a file whose content exists shows "Already uploaded" and a link that opens that stored file

## 4. Accessibility rules
| Rule | Requirement |
|---|---|
| Screen reader | the notice text is announced when it appears |
| Contrast | `color-status-warning` on white ≥ 4.5:1 |

## 6. Dependencies
| Name | Version | Why |
|---|---|---|
| — | — | none |
