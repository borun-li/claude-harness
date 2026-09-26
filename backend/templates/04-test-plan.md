# Test Plan — {Feature / Product}

- Author: be-tester (Backend Phase 4)
- Derived from `01-requirements.md` and `03-detailed-design.md` only — **not** from the
  implementation. This independence is the point of the phase.

## 1. Strategy
<Levels used (unit / integration / e2e), framework, how the environment is set up,
what is stubbed and what is real, and why.>

## 2. Test environment
| Item | Value |
|---|---|
| Commands | |
| Fixtures / sample data | |
| External services | real / sandbox / stubbed |

## 3. Test cases
### TC-001 — {title}
- **Verifies:** REQ-001   (and FX-001 if it checks an approved fixture)
- **Level:** unit | integration | e2e   **Mode:** automated | manual
- **Preconditions:**
- **Steps:**
- **Expected result:**
- **Observed how:** {assertion, log line, API response, screenshot}

Tag each automated test with its `TC-###` (comment above the test, or in its docstring). The `p5`
gate looks for the tag and re-runs the test.

## 4. Negative, boundary and failure cases
{Bad input, missing permissions, dependency down, timeout, partial write, duplicate submit.}

## 5. Coverage matrix
| REQ | Test cases | Level |
|---|---|---|

Requirements with no test case: {list, or "none"}

## 6. Untestable requirements
| REQ | Why not testable now | What would make it testable |
|---|---|---|
