# FalseTech Runtime Guidance for StorageUnit SimLay

## Purpose

This file translates the FalseTech Master Controller v2.4 runtime rules into practical SimLay repo behavior.

## Runtime Boundary

Daily SimLay work should operate inside the slim runtime boundary:

- Use active implementation docs, schemas, tests, and source code.
- Keep archival reference material out of default execution paths.
- Pull archival material only when solving a specific historical or design-trace question.

## Controller Guidance Applied to SimLay

| Controller rule | SimLay implementation behavior |
|---|---|
| Output Contract Resolver | Every requested output should resolve to one clear format: code patch, repo doc, test, export file, report block, or decision summary. |
| Router Alias Map | Similar terms should route to the same subsystem. Example: valuation, price band, bid ceiling, and resale value all route through valuation logic. |
| Appendix Entry Gate | Legacy notes and archived docs must not become default app behavior unless explicitly promoted. |
| Registry location upgrade | New modules should document where they live and whether they are runtime, reference, test, or archive. |
| Seed-module warnings | Early experimental modules should be labeled as seed/experimental before they influence production logic. |
| Sidecar self-hash policy | Large generated reference files should include hash sidecars when reproducibility matters. |
| Slim runtime build | Default development should prefer the smaller runtime surface instead of loading the full archive. |

## Repo Rules

1. Runtime code belongs in `backend/app`, `frontend`, or active `tests`.
2. Active project docs belong in `docs/`.
3. Raw imported reference docs belong in `docs/legacy_reference/` or archive folders.
4. Generated outputs belong in `backend/data/exports`, `exports/`, or a purpose-specific export folder.
5. Do not blend app runtime files with archive notes.
6. Promote archived guidance into runtime only through a clear doc update, code change, and test when applicable.

## SimLay Module Registry

| Module | Location | Status | Notes |
|---|---|---|---|
| API app | `backend/app/main.py` | runtime | FastAPI entrypoint. |
| Database schema | `backend/app/core/database.py` | runtime | SQLite schema and connection helpers. |
| Domain models | `backend/app/models/` | runtime | Canonical truth-first models and export guardrails. |
| API schemas | `backend/app/schemas.py` | runtime | Request/response validation surface. |
| Item routes | `backend/app/routers/items.py` | runtime | Manual item create/update/value workflows. |
| Evidence routes | `backend/app/routers/evidence.py` | runtime | Comps and source capture. |
| CSV export | `backend/app/services/csv_exporter.py` | runtime | Wix-compatible PRODUCT CSV output. |
| Audit export | `backend/app/services/audit_exporter.py` | runtime | Decision/audit JSON output. |
| Problem map | `docs/PROBLEM_MAP.md` | active reference | Governing problem and values. |
| Legacy reference | `docs/legacy_reference/` | archive/reference | Not default runtime. |

## Output Contract Resolver

Use this resolver when deciding what to produce next:

| User intent | Output type |
|---|---|
| Fix repo/app behavior | Code patch plus tests. |
| Clarify system structure | Repo doc update. |
| Validate pricing/export logic | Test and guardrail update. |
| Prepare sharing artifact | Export/report file. |
| Decide storage-unit action | Decision summary with confidence/source labels. |
| Preserve history | Archive/reference doc, not runtime code. |

## Hard Guardrail

No model, schema, or export should claim certainty without one of these:

1. photo-confirmed evidence,
2. user-confirmed evidence,
3. approved comp,
4. cited web comp stored as evidence.

Unknown stays Unknown until promoted by evidence.
