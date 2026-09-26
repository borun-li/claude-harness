# Findings — Duplicate upload message

- Author: fe-critic · Lenses: ux-flow · Round: 1

## Captured / not captured
- **Captured from the running product:** duplicate and error states at 1280 px (`evidence/verify-1/manifest.md`)
- **Read from code only:** narrow-screen layout
- **Not captured:** screen-reader announcement

## Findings
### F-001 — Duplicate upload shows a raw error code
- **Priority:** P1
- **Side:** frontend
- **Task damaged:** T-001 — the admin sees "409" and uploads again, creating the same confusion
- **Evidence:** `evidence/verify-1/duplicate.dom.html:42` (observed)
- **Recommendation:** map 409 to the duplicate notice in PAGE-001
- **Owner:** fe-engineer · **Status:** open
