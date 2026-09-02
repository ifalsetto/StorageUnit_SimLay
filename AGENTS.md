# StorageUnit SimLay — Continuity Gate

This repository is the canonical StorageUnit SimLay code lineage: `ifalsetto/StorageUnit_SimLay`.

## Mandatory pre-execution rule

Before creating, modifying, installing, testing, building, migrating, deploying, or starting SimLay code:

1. Run the established continuity preflight for the environment. On FalseTech Windows systems use `CONTINUITY_CHECK_WINDOWS.ps1 -RequireCanonical`.
2. Query the FalseTech Continuity Engine project registry and decision memory when that established write/read path is available, using `StorageUnit`, `SimLay`, `inventory`, `valuation`, `owner`, `market`, and semantic equivalents.
3. Inspect this repository and relevant branches before scaffolding a parallel implementation.
4. If an equivalent project-specific capability already exists, REUSE → CONTINUE → EXTEND → INTEGRATE → MERGE → REFACTOR it before considering anything new.
5. Treat older HTML dashboards, Streamlit builds, ZIP exports, Drive folders, backups, datasets, and `legacy-streamlit-backup` as feature/reference sources unless continuity evidence promotes them.
6. `ifalsetto/StorageUnit-Simlay` is the Wix storefront adapter, not a second core. Do not merge its Git history into this repository.
7. Do not execute a project helper script that bypasses the continuity preflight. Add the preflight to the existing helper instead of creating a bypass wrapper.

## Data and truth rules

1. Never infer inventory ownership. Valid owners are `Thomas`, `Mine`, and `Unassigned`.
2. Never merge physical-item records solely because names/photos look similar. Flag suspected duplicates for review.
3. Preserve confidence/source truthfulness. `Verified`, `Inferred`, and `Unknown` are evidence states.
4. Sold evidence, active asking prices, MSRP, market-state adjustments, marketplace fees, and expected seller net are distinct facts and must remain distinct in storage and UI.
5. Never claim sold-listing API coverage when the connector only has active-listing coverage.
6. Never commit private inventory databases, uploads, exports, secrets, or customer data to the public repository.
7. Destructive inventory actions must be auditable and recoverable where practical.
8. Market fee/source policy is configuration-driven and date-stamped. Do not hard-code changing marketplace economics into UI components.

## Completion rule

A substantial change is not complete until continuity passes, backend tests pass, the frontend production build passes, existing data remains migratable, and continuity documentation is updated. Update the external Continuity Engine through its established write path when available.

Current continuity master version: `2.1.0-market-intelligence`.
