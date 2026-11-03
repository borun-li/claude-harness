# Queue — Duplicate upload message

- **Author:** fe-engineer · **Status:** approved at the design stop 2026-11-04

## Scaffold
| File | What it does |
|---|---|
| `web/upload/api.ts` | maps 409 `duplicate_of` to a `duplicate` result; network failure to `failed` |

## Dependencies
| Package | Version | Why |
|---|---|---|

### Q-001 — Duplicate notice with a link to the original
- **Page:** PAGE-001
- **Frame:** FRAME-002
- **States:** error
- **REQ:** REQ-001
- **Files:** `web/upload/Result.tsx`, `web/upload/messages.ts`
- **Observable:** after uploading an existing file, an amber notice reads "Already uploaded. Open the original", and the link opens the stored file
- **Acceptance:** at 1440 and 375, notice text and link target match; announced as status
- **Priority:** P1
- **Side:** frontend
- **Depends on:** none
- **Status:** queued

### Q-002 — Upload states around the notice
- **Page:** PAGE-001
- **Frame:** FRAME-001
- **States:** loading, empty, success, permission
- **REQ:** REQ-001
- **Files:** `web/upload/Result.tsx`, `web/upload/UploadForm.tsx`
- **Observable:** each state shows the words in its UX state row; Upload is disabled until a file is chosen
- **Acceptance:** each state captured at 1440 and 375 matches its row
- **Priority:** P2
- **Side:** frontend
- **Depends on:** Q-001
- **Status:** queued
