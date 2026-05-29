# StorageUnit SimLay — Public Deployment Guide

## What this release is

StorageUnit SimLay is an accuracy-first companion app for storage unit inventory and resale workflows.

It converts photos or video keyframes into reviewable inventory records, supports structured price evidence, computes conservative valuation bands, exports exact Wix-compatible PRODUCT rows, and writes audit JSON.

## Truth rules

1. No silent guessing.
2. Every item must have `Verified`, `Inferred`, or `Unknown` confidence.
3. Condition is visual-only.
4. Numeric export price requires valid evidence gates.
5. Unknown-confidence items export with blank price.
6. Wix CSV export fails closed if headers do not match the configured schema.

## Windows local deployment

1. Extract the zip into a generic project directory:

```powershell
C:\Projects\StorageUnit_SimLay_Public_Deploy_Release
```

2. Run:

```powershell
cd C:\Projects\StorageUnit_SimLay_Public_Deploy_Release
.\INSTALL_WINDOWS.ps1
.\START_APP_WINDOWS.ps1
```

3. Open:

```text
Frontend: http://127.0.0.1:5173
Backend docs: http://127.0.0.1:8000/docs
```

## Docker deployment

```bash
docker compose up --build
```

Then open:

```text
http://localhost:5173
http://localhost:8000/docs
```

## OpenAI Vision setup

Set the key before starting the backend:

```powershell
$env:OPENAI_API_KEY="your_key_here"
```

Or add it to your deployment environment.

Without an API key, use the mock provider for dry-run workflows.

## eBay connector status

The release includes an official eBay API scaffold. It is disabled by default and does not claim sold-listing access. Enable only after configuring approved credentials and connector behavior in:

```text
backend/config/connectors.yaml
```

## Wix template replacement

Replace:

```text
backend/data/templates/Master_Inventory.csv
```

Then regenerate schema:

```powershell
cd backend
.\.venv\Scripts\activate
python scripts\generate_wix_schema.py
python scripts\validate_config.py
```

## Test command

```powershell
.\RUN_TESTS_WINDOWS.ps1
```

Expected result for this release:

```text
12 passed
```

## Files users should not edit casually

```text
backend/app/services/csv_exporter.py
backend/app/services/valuation.py
backend/app/core/database.py
```

Edit configs first:

```text
backend/config/*.yaml
backend/config/profiles/default_profile.json
backend/config/wix_schema.json
```

## Public safety note

Do not deploy this repository with real uploaded media, private sales history, real storage-unit locations, secrets, or signing keys committed to source control.
