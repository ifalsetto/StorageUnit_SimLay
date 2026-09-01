# StorageUnit SimLay Operations

## Start

Windows:

```powershell
.\INSTALL_WINDOWS.ps1
.\START_APP_WINDOWS.ps1
```

Frontend: `http://127.0.0.1:5173`  
Backend/API docs: `http://127.0.0.1:8000/docs`

## Thomas vs Mine

1. Select the correct run.
2. Open **Quick Inventory**.
3. Filter `Thomas`, `Mine`, or `Unassigned`.
4. Use the always-visible Owner selector for quick reassignment.
5. Leave uncertain ownership as `Unassigned`; do not guess.

## Edit

Use **Edit** to change name, owner, disposition, category, condition, confidence, source, manual low/expected/high value, asking price, and notes.

Manual value bands do not silently replace evidence-derived valuation records; they remain separate operator inventory values.

## Delete / restore

1. Press **Delete**.
2. Press **Confirm**.
3. The item moves to recoverable trash and an audit event is written.
4. Toggle **Trash** to view deleted items.
5. Press **Restore** to return the item.

## Photos

The dashboard only displays photos explicitly linked to an item by representative/detected media references. It does not borrow the first photo from a run, preventing unrelated property from appearing on the wrong item.

## Import a private photo inventory

Use the API docs at `http://127.0.0.1:8000/docs` and the `imports` endpoints. This is designed for the private `FalseTech_SimLay_Photo_Inventory.json` style export without putting private inventory or photos in GitHub.

1. Create/select the destination run first.
2. Open `POST /api/imports/photo-inventory/{run_id}`.
3. Upload the JSON file.
4. Choose the owner explicitly: `Thomas`, `Mine`, or `Unassigned`.
5. Keep `dry_run=true` for the first pass. Review `would_create`, `already_imported`, and `invalid`.
6. Re-run with `dry_run=false` only after the preview looks correct.
7. Upload the private photos into the same run using the existing media upload endpoint/UI.
8. Call `POST /api/imports/photo-inventory/{run_id}/relink-media`.
9. Review `missing` and `ambiguous` results. SimLay only links an exact filename basename when there is exactly one match; it never guesses between duplicate filenames.
10. Use `GET /api/imports/photo-inventory/{run_id}/status` to review imported IDs, ownership, and photo-link status.

Import safety rules:

- Owner defaults to `Unassigned`; the importer never infers ownership from the file.
- Existing source item IDs are idempotency keys, so re-importing the same JSON into the same run does not create duplicates.
- Imported source URLs are preserved as reference-only evidence with no price and are excluded from valuation until properly approved/entered as evidence.
- Free-form condition text that does not exactly match SimLay's condition enum is preserved in notes while the structured condition stays `Unknown`.
- The importer does not invent an expected value from low/high ranges. It preserves only values explicitly present in the source file.

## Local data safety

The public repository ignores `backend/data/simlay.db`, `backend/data/uploads/*`, and `backend/data/exports/*`. Back up `backend/data/` before bulk changes.

Never commit Thomas/Mine inventory JSON, the local SQLite database, uploaded photos, or generated exports to the public repository.
