# Structure — Duplicate upload message

- Author: fe-designer · Input: `01-brief.md`

## 1. Pages
| Page | Job (one sentence) | Serves | Form | Why this form |
|---|---|---|---|---|
| PAGE-001 | Upload one file and see the result | T-001 | form | single file, one decision |

## 2. Navigation
| Level | Global / contextual | How the user knows where they are |
|---|---|---|
| Files › Upload | global menu | breadcrumb and page title |

## 3. Flows
### FLOW-001 — Upload a duplicate
- **Serves:** T-001
- **Success:** 1. Choose file 2. Upload 3. See "Already uploaded" with a link 4. Open the original
- **Failure:** network error → "Upload failed, try again" with Retry
- **Cancel:** Cancel during upload → back to empty form
- **Recovery:** Retry keeps the chosen file
- **Boundary:** file over 20 MB → size message before upload

## 4. Wireframes
### PAGE-001
```
[Title: Upload a file]
[File picker]            [Upload]
[Result area: empty | uploading… | ✓ uploaded | ⚠ already uploaded → Open original | ✕ failed → Retry]
```
