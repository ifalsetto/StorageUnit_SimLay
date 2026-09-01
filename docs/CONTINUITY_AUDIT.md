# StorageUnit SimLay Continuity Audit

## Canonical identity

- Repository: `ifalsetto/StorageUnit_SimLay`
- Runtime architecture: FastAPI + SQLite backend, React/Vite frontend, local filesystem media/exports.
- Canonical continuity version: `2.0.0-continuity-master`.

## Continuity Engine evidence

The FalseTech Continuity Engine already records a 2026-09-01 canonical consolidation decision for StorageUnit SimLay. That decision selected the current FastAPI/SQLite repository as the architectural base after comparing prior refactor, consolidated, Accuracy First, HTML dashboard, guided-capture, deployment, and Git branch artifacts. It explicitly requires one canonical runtime and merge-forward behavior.

The decision also records that the prior local consolidation had not yet been published to the remote canonical repository. This branch publishes the owner-separated inventory layer into that canonical repo rather than creating another app.

## Relevant lineage

| Artifact | Classification | Continuity treatment |
|---|---|---|
| `ifalsetto/StorageUnit_SimLay` | CANONICAL | Active runtime and merge target |
| FastAPI/React/SQLite public deploy release | DESCENDANT / CANONICAL BASE | Preserve transactional DB, media/evidence, valuation, OCR, exports, tests |
| `StorageUnit_SimLay_consolidated` | REFERENCE IMPLEMENTATION | Preserve legacy Tony/Work/Report behavior and report concepts |
| `StorageUnit_SimLay_refactor` | HISTORICAL ARCHITECTURAL PARENT | Reference for typed models, atomic JSON history, admin/audit behavior |
| Owner/photo Streamlit dashboard | FEATURE BRANCH / REFERENCE | Port owner isolation, quick edit/delete, photo-centric inventory UX |
| Earlier standalone HTML dashboards | REFERENCE / ARCHIVE | UX/reference only |
| Render/cloud deployment refinements | DESCENDANT | Preserve deployment configuration/history |
| `legacy-streamlit-backup` Git branch | ARCHIVE / REFERENCE | Not a second production runtime |

## Owner/photo gap addressed

Before this branch, the published canonical schema did not contain explicit `owner`, disposition/action, manual resale band, asking price, or soft-delete fields, and the React inventory list was read-only. This merge adds those capabilities directly to the canonical FastAPI/SQLite + React runtime.

## Privacy decision

The canonical GitHub repository is public. User inventory databases, photos, and exports remain local and are ignored by `.gitignore`. No Thomas/Mine photos or private inventory records are committed by this continuity merge.
