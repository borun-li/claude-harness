# Specification — {feature}

- Author: fe-designer · Input: `01-brief.md`, `02-structure.md` · Status: draft
- Style: tables and state matrices; no paragraph over 50 words. See `examples/03-spec.example.md`.

## 1. Tokens
| Semantic token | Primitive | Value | Use |
|---|---|---|---|

## 2. Components
### CMP-001 — {component}
- **Variants:** <…>
- **States:** default · hover · focus · active · disabled · loading · error · empty · selected
- **Sizes and limits:** {max length, overflow: truncate | wrap | tooltip}
- **Accessibility:** {role, accessible name, keyboard}

## 3. Pages
### PAGE-001 — {page}
- **Goal:** {one line} · **Serves:** T-001
- **Components:** CMP-001, …
- **States:**

| State | What renders | Copy |
|---|---|---|
| loading | | |
| empty | | |
| success | | |
| error | | |
| permission-denied | | |

- **Permissions:** {role → can see / can act}
- **Accept:** AC-001 — {testable by a stranger}

## 4. Accessibility rules
| Rule | Requirement |
|---|---|
| Keyboard order | |
| Focus | |
| Contrast | {ratio against named tokens} |
| Target size | |
| Screen reader | {what is announced for each status} |

## 5. Adaptation
| Size / class | What changes | What the user loses |
|---|---|---|

## 6. Dependencies
| Name | Version | Why |
|---|---|---|
{Every new package. The `fe-build` gate rejects any not named here.}
