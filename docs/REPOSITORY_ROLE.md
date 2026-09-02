# Repository Role — Canonical SimLay Core

## Status

**CANONICAL SOURCE OF TRUTH for SimLay application logic and data workflows.**

Repository: `ifalsetto/StorageUnit_SimLay`

This repository owns the actual SimLay runtime and should receive all future core product work unless a capability clearly belongs to a separate adapter.

## Owns

- FastAPI backend
- React/Vite frontend
- SQLite schema and migrations
- inventory capture and processing
- OCR staging/promotion
- item/evidence models
- valuation guardrails
- decision engine
- owner-isolated inventory workflow
- exports and Wix export policy/guardrails
- FalseTech Practice integration contract
- tests, validation, deployment configuration, and continuity CI

## Does NOT own

The Wix Git Integration repository `ifalsetto/FalseTech-Resale-Wix-Storefront` is **not another SimLay core implementation**. It is the source repository bound to the FalseTech Resale Wix site (`falsetechresell.com`). Treat that repository as a storefront adapter/site shell only.

Historical name retained for provenance only: `ifalsetto/StorageUnit-Simlay`.

## Integration boundary

Use this direction:

`SimLay core → approved export/API contract → FalseTech Resale / Wix storefront`

Do not copy valuation, evidence, decision, inventory, or persistence logic into the Wix repository. The storefront may consume approved public/seller-facing outputs from SimLay but must not become a second source of truth.

## Continuity rule

Before creating another SimLay repository or subsystem:

**REUSE → CONTINUE → EXTEND → INTEGRATE → MERGE → REFACTOR → BUILD NEW**

If work appears in another repository, first determine whether it is:

1. core SimLay logic that should move here,
2. a deployment/storefront adapter that should stay separate,
3. historical/provenance material that should be archived,
4. or an actual duplicate that can be retired after verification.

## Current repository-role resolution

- `StorageUnit_SimLay` = canonical SimLay product/runtime.
- `FalseTech-Resale-Wix-Storefront` = Wix storefront/site integration shell for FalseTech Resale.

Preserve both histories and responsibilities, but never treat them as peer implementations of SimLay.
