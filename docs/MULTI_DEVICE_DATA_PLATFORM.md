# SimLay Multi-Device Data Platform

## Goal

SimLay must be usable from AJ's three Windows computers and phone without requiring AJ to remember which device has the newest copy, where a file was saved, or whether a feature already exists.

This is an extension of the canonical SimLay runtime, not a new SimLay application.

## Canonical identity

- `project_id`: `simlay`
- Canonical product: **SimLay**
- Aliases: `StorageUnit SimLay`, `Storage Unit SimLay`, `FalseTech Resale`
- Canonical core repository: `ifalsetto/StorageUnit_SimLay`
- Wix storefront adapter: `ifalsetto/StorageUnit-Simlay`

## Required device names

User-facing device names must be readable:

- `AJ-Desktop-Main`
- `AJ-Desktop-2`
- `AJ-Laptop`
- `AJ-Phone`

Opaque UUIDs may exist internally but must never be the primary user-facing label.

## Target architecture

```text
Windows PC / Laptop
  -> canonical C:\FalseTech root
  -> local SQLite cache + offline queue
  -> FalseTech background sync agent
  -> authenticated FalseTech API
  -> shared PostgreSQL canonical data platform

Phone
  -> installable SimLay/FalseTech PWA
  -> authenticated FalseTech API
  -> shared PostgreSQL canonical data platform
```

The shared PostgreSQL database is the canonical logical state. Local SQLite remains available for offline operation and existing SimLay compatibility. Synchronization is event-based; live SQLite database files are never synchronized by file-copy tools.

## File responsibilities

- PostgreSQL: structured state, project/device registry, continuity events, inventory, valuations, sales, sync metadata.
- Object/file storage: photos, videos, PDFs, exports, backups, other large binary artifacts.
- Git: source, schemas, migrations, tests, scripts, documentation.
- Local SQLite: offline cache and compatibility layer, not a file to share concurrently.

## Set-and-forget requirements

After one setup run per Windows device and one phone installation:

1. The background agent starts automatically with Windows.
2. Local project/file discovery runs automatically.
3. Device state and changes synchronize automatically.
4. Offline changes queue and synchronize when connectivity returns.
5. Canonical project identity prevents accidental duplicate SimLay implementations.
6. Health checks and backups run without manual commands.
7. A device may be offline for an extended period and automatically catch up later.
8. User-facing search resolves items/projects/files without requiring filesystem paths.
9. Run outcomes are written back to Continuity automatically.
10. Opaque filenames are renamed to readable canonical names when safe, with the original name/path/hash retained in provenance.

## Naming policy

New, downloaded, imported, generated, or discovered artifacts with opaque/hash/UUID-style filenames must receive a readable user-facing name whenever renaming is safe.

Preferred form:

`<Project>-<Purpose>-<Version-or-Date>.<extension>`

Never rename framework-required files where doing so would break the runtime. Every rename must preserve original name, original path, content hash, source device, and rename history.

## Installation model

Maintain one core Windows installer and thin device wrappers. The core installer must be idempotent and continuity-first: inspect/reuse existing `C:\FalseTech`, Continuity, repositories, and databases before creating or replacing anything.

User-facing wrappers:

- `Setup-AJ-Desktop-Main.cmd`
- `Setup-AJ-Desktop-2.cmd`
- `Setup-AJ-Laptop.cmd`

Phone installation is through the PWA; normal phone use must not require Termux.

## Acceptance test

The release is not complete until all of the following pass:

1. Create data on `AJ-Desktop-Main`.
2. Shut that PC down.
3. Find the data from `AJ-Phone`.
4. Modify it from the phone.
5. Start `AJ-Laptop`; it receives the update automatically.
6. Continuity explains what changed, when, and on which device.
7. User-facing artifact names are recognizable.
8. Start `AJ-Desktop-2` after it has been offline; it catches up automatically.
9. Duplicate/conflicting work is detected and surfaced instead of silently multiplying.
10. No manual file copying, database copying, or path memory is required.

## Migration rule

Do not replace the working SQLite runtime in one step. Add synchronization around it, validate cross-device behavior, then move individual canonical data domains to PostgreSQL behind stable API contracts. Every migration must be reversible and preserve existing inventory, evidence, media relationships, audit history, and IDs.
