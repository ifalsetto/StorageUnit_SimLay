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

## Local data safety

The public repository ignores `backend/data/simlay.db`, `backend/data/uploads/*`, and `backend/data/exports/*`. Back up `backend/data/` before bulk changes.
