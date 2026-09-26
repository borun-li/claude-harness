# Detailed design — {feature}

- Author: be-architect · Input: `01-requirements.md`, `02-architecture.md`
- Style: signatures in code, behaviour as numbered one-line steps, each DES at most 120 words
  (code excluded). See `examples/03-detailed-design.example.md`.

## 1. Files
| Path | Responsibility | New / changed |
|---|---|---|

## 2. Modules
### DES-001 — {file or module}
- **Serves:** REQ-001
- **Side:** backend | frontend   (keep the keywords `Serves:` and `Side:` in English)
- **Interface:**
```
<signatures with types>
```
- **Behaviour:**
  1. {step}
- **Errors:** {names from §3}

## 3. Errors
| Error | Raised when | Retry | Handled in | Message |
|---|---|---|---|---|

## 4. State
| State | → | Trigger | Persisted |
|---|---|---|---|

## 5. Config & secrets
| Key | Source | Default | Required |
|---|---|---|---|

## 6. Logging
| Event | Level | Fields |
|---|---|---|

## 7. Dependencies
| Name | Version | Why |
|---|---|---|
<Every new external dependency. The `p4` gate rejects any not named here.>

## 8. Build order
1. {riskiest first}
