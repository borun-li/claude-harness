# Detailed design — Duplicate upload guard

- Author: be-architect · Input: `01-requirements.md`, `02-architecture.md`

## 1. Files
| Path | Responsibility | New / changed |
|---|---|---|
| `app/uploads/service.py` | Upload flow with the hash check | changed |
| `app/uploads/hash_index.py` | Hash lookup and insert | new |
| `migrations/0042_file_hash.sql` | `file_hash` table and unique index | new |

## 2. Modules
### DES-001 — `app/uploads/hash_index.py`
- **Serves:** REQ-001
- **Side:** backend
- **Interface:**
```python
def find(sha256: str) -> int | None: ...
def insert(sha256: str, file_id: int) -> None:  # raises DuplicateContent
```
- **Behaviour:**
  1. `find` returns the stored `file_id` or `None`.
  2. `insert` relies on the unique index; a violation becomes `DuplicateContent(existing_id)`.
- **Errors:** `DuplicateContent`

### DES-002 — `app/uploads/service.py`
- **Serves:** REQ-001
- **Side:** backend
- **Interface:**
```python
def upload(stream: BinaryIO, user_id: int) -> int:  # returns file id
```
- **Behaviour:**
  1. Hash the stream while writing it to a temp file.
  2. `find(hash)` → if found, delete temp, raise `DuplicateContent(id)`.
  3. Move temp to storage, `insert(hash, id)`; on `DuplicateContent`, delete the stored copy and re-raise.
- **Errors:** `DuplicateContent` → 409 `{"duplicate_of": id}`

## 3. Errors
| Error | Raised when | Retry | Handled in | Message |
|---|---|---|---|---|
| `DuplicateContent` | hash already stored | no | API layer | 409 `{"duplicate_of": id}` |

## 6. Logging
| Event | Level | Fields |
|---|---|---|
| `duplicate_rejected` | info | `sha256`, `existing_id`, `user_id` |

## 7. Dependencies
| Name | Version | Why |
|---|---|---|
| — | — | none |

## 8. Build order
1. Migration and dedupe script (riskiest: existing duplicates).
2. `hash_index.py`, then `service.py`.
