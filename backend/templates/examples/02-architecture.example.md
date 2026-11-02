# Architecture — Duplicate upload guard

- Author: be-architect · Input: `01-requirements.md` · Status: revised after design review

## 1. Components
| Component | Responsibility (one sentence) | Serves |
|---|---|---|
| `UploadService` | Stores a file after checking its hash is new. | REQ-001 |
| `HashIndex` | Maps content hash to the stored file id. | REQ-001 |

## 2. Data model
| Entity | Key fields | Owner | Stored in |
|---|---|---|---|
| `file_hash` | `sha256` (unique), `file_id` | HashIndex | Postgres table `file_hash` |

## 3. External contracts
| Interface | Signature / endpoint | Auth | Errors | Limits | Source |
|---|---|---|---|---|---|
| Upload API | `POST /files` → 201 `{id}` | session | 409 `{duplicate_of}` | 20 MB | existing `api.md` §2 |

## 4. Decisions
| Decision | Chosen | Rejected (why) |
|---|---|---|
| Where to hash | Stream while uploading | Hash after save (writes duplicates to disk first) |
| Uniqueness | DB unique index | App-level lock (races across workers) |

## 5. Risks
| Risk | Likelihood | Impact | Mitigation | Early signal |
|---|---|---|---|---|
| Existing duplicates break the unique index | high | migration fails | dedupe script first | migration dry run |

## 6. Failure model
| Dependency | Fails how | System does |
|---|---|---|
| Postgres | timeout on index lookup | 503, file not stored |

## 7. Cost of the next one
| Growing family | Adding a member changes | Goes red if forgotten |
|---|---|---|
| — | none this round | — |

## 8. Coverage
| REQ | Component(s) |
|---|---|
| REQ-001 | UploadService, HashIndex |
