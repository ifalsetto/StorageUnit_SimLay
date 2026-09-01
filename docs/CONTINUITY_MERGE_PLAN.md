# Continuity Merge Plan — Owner-Separated Inventory

## Canonical base

`ifalsetto/StorageUnit_SimLay` on the current `main` lineage.

## Why

Continuity Engine records identify the FastAPI/SQLite release as the strongest current architecture for transactional durability, valuation/evidence integrity, media support, tests, and deployment readiness. The owner/photo Streamlit dashboard is treated as a feature source, not a replacement runtime.

## Features ported

- Explicit owner: `Thomas`, `Mine`, `Unassigned`.
- Owner filter/badges and fast owner reassignment.
- Sell / Donate / Dump / Hold / Unassigned disposition.
- Manual low / expected / high resale band kept separate from evidence-derived valuation.
- Asking price, search, inline edit, and action filters.
- Two-step recoverable deletion and trash/restore.
- Duplicate-item action with duplicate-review flag.
- Owner-separated inventory totals.
- Photo rendering only from item-linked media; no unrelated run-photo fallback.
- Audit events for create/update/delete/restore/duplicate/value.
- Idempotent SQLite schema migration for existing canonical databases.

## Data policy

- Existing rows default to `Unassigned` unless ownership is explicit.
- No ownership is guessed from item name, image, history, or conversation context.
- No user photos/data are committed to GitHub.
- Existing IDs, valuation fields, evidence, and audit history remain intact.
- Soft delete retains records for restoration.

## Runtime decision

The owner/photo Streamlit ZIP and standalone HTML dashboards remain reference artifacts only. FastAPI/React is the active runtime after this merge.
