# StorageUnit SimLay — Public Deploy Release

Accuracy-first storage-unit inventory companion app for resale workflows.

## Fastest Windows install

```powershell
cd C:\Projects\StorageUnit_SimLay_Public_Deploy_Release
.\INSTALL_WINDOWS.ps1
.\START_APP_WINDOWS.ps1
```

Open:

```text
Frontend: http://127.0.0.1:5173
Backend API docs: http://127.0.0.1:8000/docs
```

## What it does

- Upload photos or video keyframes.
- Detect inventory items using OpenAI Vision or mock provider.
- Require confidence labels: Verified, Inferred, Unknown.
- Store structured price evidence from URLs/screenshots/text.
- Compute conservative percentile valuation bands.
- Export exact Wix-compatible PRODUCT CSV rows.
- Export audit JSON explaining decisions, warnings, and missing data.

## Truthfulness rules

- No silent guessing.
- Unknown items stay unknown.
- Unknown-confidence items export blank price.
- Evidence can be stored even if price is unavailable.
- Price exports only when valuation gates pass.
- Wix export hard-fails if headers do not match exactly.

## Public repository boundary

This public repo should contain only app source, public documentation, templates, mock/sample data, and non-secret configuration examples.

Do not commit:

- Real customer/user media
- Personal addresses, phone numbers, or emails
- Real storage-unit locations
- Private sales history
- API keys, OAuth secrets, keystores, `.env` files, or signing files
- Internal planning notes that are not required to build or run the app

See: `docs/PUBLIC_RUNTIME_GUIDANCE.md`

## Useful commands

```powershell
.\RUN_TESTS_WINDOWS.ps1
```

```bash
docker compose up --build
```

## Main docs

- `DEPLOYMENT_GUIDE.md`
- `RELEASE_NOTES.md`
- `docs/PROBLEM_MAP.md`
- `docs/PUBLIC_RUNTIME_GUIDANCE.md`
