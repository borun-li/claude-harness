# Requirements — {feature}

- Author: be-analyst · Status: draft | approved at Plan
- Style: one line per field, tables over prose, no background paragraphs. See `examples/01-requirements.example.md`.

## 0. Understanding
- **Asked:** "{the user's words}"
- **Means:** {one line: what will exist after this round}
- **Ambiguities:** none | {item} — blocking (changes what is built) | assumed: {default}

## 1. Requirements
### REQ-001 — {short title}
- **Cut:** above | below
- **Behaviour:** {one observable sentence}
- **Accept:** Given {state}, When {action}, Then {observable result}
- **Source:** "{user's words}" | {artifact path §section}
- **Fixtures:** FX-001 | n/a — {why no observable output}

## 2. Non-goals
- {one line each}

## 3. Assumptions
| # | Assumption | Status | If wrong |
|---|---|---|---|
| A1 | | [unverified] | |

## 4. Open questions
| # | Question | Default | Blocks |
|---|---|---|---|

## 5. Non-functional
| Axis | This round |
|---|---|
| Performance | {bound at an input size} \| not this round |
| Security & secrets | |
| Data & retention | |
| Errors | |
| Observability | |

## 6. External constraints
| Constraint | Source |
|---|---|
