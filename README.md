# StorageUnit SimLay — Public Deploy Release

Accuracy-first storage-unit inventory companion app for FalseTech / SimLay.

## Fastest Windows install

```powershell
cd C:\FalseTech\Projects\StorageUnit_SimLay_Public_Deploy_Release
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

## FalseTech runtime guidance

SimLay follows the FalseTech Master Controller runtime boundary:

- Daily work should stay inside active runtime docs, source code, tests, and schemas.
- Archive-heavy references should not become default app behavior unless explicitly promoted.
- Similar requests should route to the same subsystem instead of creating duplicate logic.
- Output should resolve to one clear contract: code patch, repo doc, test, export, report, or decision summary.

See: `docs/FALSETECH_RUNTIME_GUIDANCE.md`

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
- `docs/FALSETECH_RUNTIME_GUIDANCE.md`
