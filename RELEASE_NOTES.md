# Release Notes — StorageUnit SimLay

## 2.1.0 — Market Intelligence + Continuity Runtime

Status: canonical FalseTech SimLay core upgrade.

### Continuity enforcement

- Canonical core remains `ifalsetto/StorageUnit_SimLay`.
- `ifalsetto/StorageUnit-Simlay` remains the Wix storefront adapter and is not merged as a second core.
- Added `CONTINUITY_CHECK_WINDOWS.ps1` to scan active FalseTech project repositories, distinguish reference copies, verify the canonical origin, and stop on likely parallel-core conflicts.
- Added `READY_SIMLAY_WINDOWS.ps1` as the preferred one-command sync/install/test/build/start workflow.
- Existing install, start, test, frontend build, Android signing, AAB build, and Play-release verification scripts now require continuity preflight.
- Runtime startup performs an additional lineage check; strict Windows launches set `SIMLAY_CONTINUITY_STRICT=1`.
- CI validates canonical lineage before backend tests and frontend builds.

### Valuation intelligence

- Preserved percentile/IQR valuation architecture rather than replacing it.
- Enforced the existing `max_comp_age_days` rule that previously existed in configuration but was not applied by valuation.
- Added source-authority weighting so verified sold evidence has more influence than active listings or MSRP.
- Added date/freshness decay for older sold evidence.
- Added temporary, expiring market-state signals separate from sold-comp value.
- Gross comp value, market-adjusted value, marketplace fee estimate, and expected seller net are stored separately.
- Added marketplace route estimation and recommended-marketplace persistence.
- Added deterministic fee/source/routing tests.

### Marketplace policy

- Added `backend/config/market_intelligence.yaml` as the date-stamped policy source for fees, source authority, freshness, routing, and market-state signals.
- Corrected the eBay connector configuration to match actual capability: active Browse search is supported when credentials are enabled; sold-listing API coverage is not claimed.
- Added fee models/routing support for eBay, Mercari, Reverb, Poshmark, and TCGplayer, with local/Facebook cash routes available for explicit planning rather than automatic recommendation.
- Policy age is exposed and produces a stale-policy warning instead of silently treating old marketplace economics as current.

### UI/API

- Added `/api/market/policy`, `/api/market/estimate-fee`, `/api/market/estimate-routes`, and `/api/market/revalue/{item_id}`.
- Inventory cards now show market state, adjusted gross value, recommended marketplace, estimated fee, expected net, and policy date.
- Added one-tap `Revalue` from the inventory dashboard.
- Inventory summary now includes expected-net totals in the client view.

### Data safety

- Market fields are added to existing SQLite databases through an idempotent migration; existing item/evidence records are preserved.
- Continuity reports are written under the already-ignored runtime exports area instead of creating source-tree noise.
- Dirty local work is preserved before safe `main` synchronization in the READY workflow.

## Earlier public-deploy baseline

Included FastAPI, React/Vite, SQLite, local filesystem uploads/exports, configuration-driven profiles, OpenAI Vision/mock providers, video keyframe extraction, OCR evidence parsing, dedupe, percentile valuation, eBay connector scaffold, URL refresh adapters, Wix CSV exports, audit exports, Windows helpers, Docker Compose, and the Pro Command Center UI.

Known external requirements remain: OpenAI Vision needs `OPENAI_API_KEY`; OCR quality depends on Tesseract when local OCR is used; eBay sold comps require approved/manual Product Research evidence rather than being fabricated from active Browse API results; Facebook Marketplace automated refresh remains constrained by platform access.
