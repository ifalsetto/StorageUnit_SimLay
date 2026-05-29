# Public Runtime Guidance for StorageUnit SimLay

## Purpose

This file defines the public repository boundary for StorageUnit SimLay. It is intended for source code, public docs, mock/sample data, build scripts, and non-secret configuration examples only.

## Public repo rules

1. Runtime code belongs in `backend/app`, `frontend`, `mobile`, or active tests.
2. Active public docs belong in `docs/`.
3. Archive/reference material must not include private planning notes, addresses, personal names, private sale history, or customer/user media.
4. Generated exports committed to the repo must be synthetic examples only.
5. Do not commit real `.env` files, API keys, OAuth secrets, signing keys, keystores, private URLs, customer media, or personal contact details.
6. Public sample data must use generic run IDs, generic SKUs, and non-identifying examples.

## Module registry

| Module | Location | Status | Notes |
|---|---|---|---|
| API app | `backend/app/main.py` | runtime | FastAPI entrypoint. |
| Database schema | `backend/app/core/database.py` | runtime | SQLite schema and connection helpers. |
| Domain models | `backend/app/models/` | runtime | Truth-first models and export guardrails. |
| API schemas | `backend/app/schemas.py` | runtime | Request/response validation surface. |
| Item routes | `backend/app/routers/items.py` | runtime | Manual item create/update/value workflows. |
| Evidence routes | `backend/app/routers/evidence.py` | runtime | Comps and source capture. |
| CSV export | `backend/app/services/csv_exporter.py` | runtime | Wix-compatible PRODUCT CSV output. |
| Audit export | `backend/app/services/audit_exporter.py` | runtime | Decision/audit JSON output. |
| Problem map | `docs/PROBLEM_MAP.md` | public reference | Governing problem and values. |

## Hard guardrail

No model, schema, or export should claim certainty without one of these:

1. photo-confirmed evidence,
2. user-confirmed evidence,
3. approved comp,
4. cited web comp stored as evidence.

Unknown stays Unknown until promoted by evidence.
