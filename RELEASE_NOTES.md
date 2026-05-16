# Release Notes — StorageUnit SimLay Public Deploy Release

## Release status

Deployable local/public handoff package.

## Included modules

- FastAPI backend
- React/Vite frontend
- SQLite local database
- Local filesystem uploads and exports
- Config-driven project profiles
- OpenAI Vision adapter with strict JSON prompt contract
- Mock Vision provider for no-cost dry runs
- Video keyframe extraction service
- Manual structured evidence workflow
- Screenshot OCR evidence parser using pytesseract when available
- Evidence parser fallback using pasted OCR/text
- Stronger dedupe engine using normalized names, token similarity, and category/condition checks
- Percentile-based valuation engine with outlier filtering
- Active-listing discount and conservative fallback rules
- Official eBay API connector scaffold
- URL refresh adapter framework with fail-closed behavior
- Exact Wix CSV exporter
- Audit JSON exporter
- 12-test backend suite
- Windows install/start/test scripts
- Docker Compose deployment files

## Known limits

- Real OpenAI Vision requires `OPENAI_API_KEY`.
- OCR quality depends on local Tesseract availability. If unavailable, the app preserves the evidence record and flags OCR failure instead of guessing.
- eBay sold-comps access is not enabled by default. The connector scaffold is present, but sold data requires an approved/compliant data source.
- Facebook Marketplace refresh remains disabled because it is login-wall/partner-only.

## Verified checks

- Config validation passed.
- SQLite init passed.
- Backend pytest suite passed: 12 passed.

## Pro Command Center UX Upgrade

- Replaced basic single-page form UI with a professional dashboard UI.
- Added sidebar navigation and workflow-specific screens.
- Added item review cards and selected-item editor.
- Added evidence locker UI for URL comps and screenshot comps.
- Added export download center.
- Added frontend-local START_APP_WINDOWS.ps1 shim to recover if user runs start command from /frontend.
