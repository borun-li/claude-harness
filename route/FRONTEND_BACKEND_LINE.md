# The frontend/backend line

Shared by both teams: `~/.claude/backend/PLAYBOOK.md` §3C cites §n below as §3C.n;
`~/.claude/frontend/PLAYBOOK.md` §3C points here. Neither team's engineer builds the other side,
whether or not the other team was dispatched.

## 1. Default line

A line the project wrote, named and dated, in `<project>/.claude/project-context.md` (or the legacy
`team/frontend-team-config.md`), overrides this one.

| Side | Covers | Designed by | Built by |
|---|---|---|---|
| backend | schema and migrations, business logic, APIs, queries, CLI args, script entry points, jobs | `be-architect` | `be-developer` |
| frontend | human-operated GUI/TUI: templates, styles, client scripts, client state, display-only fields | `fe-ux` (flows, states), `fe-ui` (look) | `fe-engineer` |

## 2. When the line must be written

Only if the round touches the interface. Then, if unwritten, ask at the next fixed stop and have
the user sign one; offer §1 as the draft. An unwritten line stops the frontend queue.

## 3. The seam

- Every backend `DES-###` has `side: backend | frontend`. A frontend item specifies only the seam
  (name, type, nullable, who computes it, endpoint or field) in
  `contracts/FRONTEND_BACKEND_CONTRACT.md`; flows, states and looks are the Frontend team's.
  A two-sided item becomes two `DES` sharing one contract entry.
- `fe-engineer` drafts the contract's capabilities from the pages it builds; each is `verified`
  (with source), `unverified` or `new`, checked against the backend before anything is called
  missing. The Backend team confirms or designs it.
- Each UX error state names the backend error code it shows, when one exists.

## 4. Cross-stack runs

The Backend team's run drives; the Frontend team runs inside it.

| Backend | Frontend |
|---|---|
| Phase 1 requirements (`[interface]` REQs) | input to Phase 1 UX (no Phase 0) |
| Phase 1b Prototype | Phases 1–2b: the frontend Prototype stop **is** the backend's; log it in both run logs |
| Phase 2 design → Plan | the contract's `new` capabilities get their `DES`; the queue rows' observables are shown again at Plan only if a DES changed them |
| Phase 4 build | Phase 3 build: frontend rows refine the prototype; a row replaces fake data once its seam's backend half exists |
| Phase 5 verification | Phase 4 verify: `fe-tester` verifies the frontend rows; `be-tester` tests each seam from the backend side |
| Phase 6 review | Phase 4 review: the frontend panel reviews the frontend diff, the backend panel the backend diff; their findings make one fix list |
| Phase 7 acceptance | one Acceptance for both |

Frontend artifacts stay in `docs/frontend/`; `state.json` (backend) records which `DES` went to
the Frontend team (`frontend_items`).

## 5. Verify

The orchestrator captures evidence on the running surface; `fe-tester` judges it. `be-tester`
tests each seam from the backend side.

## 6. Fix routing

A defect goes to the side where it is: data → `be-developer`; screen, client state or API use →
`fe-engineer`; a flow or state → `fe-ux`; a look → `fe-ui`; a backend design → `be-architect`.
Never route interface work to `be-developer` for speed.

## 7. Nothing is lost at the seam

Every entry in `frontend_items` — a `side: frontend` `DES` from `be-architect`, or frontend work
`be-developer` found while building — gets a queue row (and a `DES` if it has none), or is moved
to `deferred.md`.
