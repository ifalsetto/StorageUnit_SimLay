# StorageUnit SimLay — Canonical FalseTech Core

Accuracy-first storage-unit inventory, evidence, valuation, and resale-routing system.

Canonical repository: `ifalsetto/StorageUnit_SimLay`

`ifalsetto/StorageUnit-Simlay` is the Wix storefront adapter connected to the live resale site. It is intentionally separate and must not become a second valuation/inventory core.

## One-command Windows readiness

From the canonical FalseTech checkout:

```powershell
cd C:\FalseTech\Projects\SimLay\StorageUnit_SimLay_repo
.\READY_SIMLAY_WINDOWS.ps1
```

That command performs the operational sequence before starting the app:

1. Scans FalseTech project continuity and verifies this is the canonical SimLay lineage.
2. Preserves dirty local work before any safe canonical sync.
3. Fast-forwards `main` from `origin/main` without destructive reset.
4. Creates/updates the backend virtual environment and dependencies.
5. Installs exact frontend lockfile dependencies with `npm ci`.
6. Validates configuration.
7. Runs the complete backend test suite.
8. Runs the frontend production build.
9. Re-runs continuity verification.
10. Starts backend + frontend only after the checks pass.

Use `READY_SIMLAY_WINDOWS.ps1 -NoStart` when you want verification without launching the app.

Open after startup:

```text
Frontend:      http://127.0.0.1:5173
Backend docs:  http://127.0.0.1:8000/docs
Market policy: http://127.0.0.1:8000/api/market/policy
```

## What SimLay owns

- Photo/video inventory capture and OCR/vision assistance.
- Explicit inventory owners: `Thomas`, `Mine`, `Unassigned`.
- Evidence/comparable-sale storage with source provenance.
- Confidence truth states: `Verified`, `Inferred`, `Unknown`.
- Source-weighted valuation with stale-comp and outlier gates.
- Gross comp value kept separate from current market adjustment.
- Marketplace fee estimates and expected seller net.
- Marketplace routing recommendations.
- Recoverable deletes and audit events.
- Wix-compatible exports and explicit storefront integration boundaries.

## Market intelligence model

Marketplace economics and source authority live in:

```text
backend/config/market_intelligence.yaml
```

The policy is date-stamped and intentionally configuration-driven because marketplace fees and market conditions change. SimLay warns when the policy becomes stale instead of silently treating old fees as permanent truth.

Valuation flow:

```text
exact identification
→ evidence validation
→ source authority + freshness weighting
→ outlier/age gates
→ confidence/condition valuation
→ gross comp value
→ temporary market-state adjustment
→ eligible marketplace fee estimate
→ expected seller net
→ route recommendation
```

Active asking prices, MSRP, verified sold prices, market adjustments, fees, and expected net are never treated as equivalent facts.

### eBay sold data

The built-in official eBay Browse connector supports active-search access only. It does **not** claim sold-listing API coverage. For sold comps, add approved evidence from eBay Product Research/Terapeak or another approved sold-data source through the existing Evidence workflow. Do not convert active listings into fake sold records.

## Continuity doctrine

Every substantial SimLay operation follows:

**REUSE → CONTINUE → EXTEND → INTEGRATE → MERGE → REFACTOR → BUILD NEW**

Before creating/editing/installing/testing/building/migrating/deploying/starting project code, use the existing continuity gate:

```powershell
.\CONTINUITY_CHECK_WINDOWS.ps1 -RequireCanonical
```

Backups, datasets, older dashboards, ZIPs, and legacy builds are reference sources unless continuity evidence promotes them. The Wix repo remains an adapter rather than a parallel core.

## Truthfulness rules

- No silent guessing.
- Unknown items stay unknown.
- Unknown-confidence items export blank calculated price.
- Physical inventory is never merged solely because names/photos look similar.
- Evidence may be stored even when price is unavailable.
- Price exports only when valuation gates pass.
- Sold-data access is never claimed when a connector only supports active listings.
- Gross value and expected seller net remain separate.
- Wix export hard-fails when required schema does not match.

## Public repository boundary

Do not commit real customer/user media, personal addresses/phones/emails, real storage-unit locations, private sales history, inventory databases, exports, API keys, OAuth secrets, signing files, `.env` files, or other private FalseTech/customer data.

## Useful commands

```powershell
.\CONTINUITY_CHECK_WINDOWS.ps1 -RequireCanonical
.\RUN_TESTS_WINDOWS.ps1
.\READY_SIMLAY_WINDOWS.ps1 -NoStart
.\READY_SIMLAY_WINDOWS.ps1
```

```bash
docker compose up --build
```

## Main docs

- `AGENTS.md`
- `DEPLOYMENT_GUIDE.md`
- `RELEASE_NOTES.md`
- `docs/PROBLEM_MAP.md`
- `docs/PUBLIC_RUNTIME_GUIDANCE.md`
