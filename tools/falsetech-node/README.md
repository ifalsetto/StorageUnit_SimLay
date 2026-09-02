# FalseTech Node

This is the Windows set-and-forget Continuity client for the FalseTech shared data platform.

## Use

Run exactly one wrapper on each Windows device:

- `Setup-AJ-Desktop-Main.cmd`
- `Setup-AJ-Desktop-2.cmd`
- `Setup-AJ-Laptop.cmd`

All three wrappers call the same canonical `Install-FalseTechNode.ps1`. There are not three independent implementations.

The phone uses the installable PWA surface at `/continuity.html` and registers as `AJ-Phone` after authentication.

## What installation does

1. Inspects and reuses the existing `C:\FalseTech` root. It does not delete or blindly move existing work.
2. Installs/reuses Python and creates an isolated virtual environment.
3. Creates `C:\FalseTech\System\FalseTech-Node.json` with the human-readable device identity.
4. Creates `C:\FalseTech\Continuity\FalseTech-Node-Cache.db` as the local SQLite cache/offline queue.
5. Authenticates once; the refresh token is kept in Windows Credential Manager.
6. Registers the device in FalseTech Data Platform.
7. Scans known FalseTech and user work locations.
8. Hashes artifacts for cross-device duplicate detection.
9. Renames opaque/hash/UUID-style files only in approved safe locations such as Downloads and managed FalseTech media/document folders.
10. Preserves original filename/path/hash in Continuity provenance.
11. Installs the background agent at Windows logon.
12. Uploads approved shareable artifacts to private workspace-scoped object storage hourly.
13. Runs a daily health check and writes human-readable JSON reports under `C:\FalseTech\Continuity\Reports`.

## Important safety rules

- Never file-sync a live SQLite database.
- Never rename framework-required source files just to make them prettier.
- Never auto-delete duplicates in this phase. Detect and record them first.
- Scripts, installers, and live database files remain metadata/Git managed rather than being blindly copied into object storage.
- No service-role or database-admin key is stored on a PC or phone.

## Repair

Run `Repair-FalseTechNode.ps1` when a node reports unhealthy. Repair refreshes the runtime, scheduled tasks, and dependencies without deleting local databases or Continuity history.

## Current readiness

Automated CI validates the node's opaque-name detection, safe rename boundary, and SQLite offline queue. The final release gate is the real four-device acceptance test documented in `docs/MULTI_DEVICE_DATA_PLATFORM.md`.
