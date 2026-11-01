# SimLay Local Barcode Evidence — Continuity and Acceptance

Canonical repository: `ifalsetto/StorageUnit_SimLay`. This extends Quick Capture and the existing evidence table; it does **not** introduce a separate product, new database, paid dependency or external barcode API.

## Workflow
1. Open existing Quick Capture and select the owner (Thomas, Mine, or Unassigned).
2. Upload and process a product photo using existing SimLay controls so the run has at least one inventory item.
3. Choose **Scan barcode from photo (local)**. The browser decodes the selected image on-device when its native `BarcodeDetector` supports the format.
4. Review the barcode value and select an existing item **from that owner-specific run**. Saving is an explicit action, not automatic identification.
5. **Save unverified code to selected item** writes to the existing `evidence` table via `POST /api/evidence`: `source_type=barcode`, `listing_type=observation`, `price=null`.
6. Existing evidence retrieval returns the observation. Barcode records have `included_in_valuation=0`, so no sales-price/market-value claim is made. Duplicate code + item combinations are checked before saving.
7. No matching inventory item? Process the run first. Unsupported browser? Display an honest no-scan fallback; no image is sent to a barcode provider.

## Security and truth guarantees
- No scan automatically creates, merges, deletes, prices or reassigns inventory.
- No barcode is deemed verified solely by decoding. Item identity, condition, pricing and ownership require independent evidence and manual review.
- Backend schema rejects barcode observations with a sale listing type or non-null monetary price.
- User-selected item is from the selected owner run; the existing backend item-auth/access model remains unchanged and requires independent production security acceptance.
- Existing upload media API and all ownership paths remain unchanged. The barcode scan's input image stays in the browser unless separately uploaded through the established photo flow.
- New barcode evidence is persisted to the **current SimLay backend** only when user explicitly selects an item and presses Save; no external service or extra API subscription.

## Automated acceptance
- `node --test frontend/tests/barcode.test.mjs` (from frontend): detector capability, duplicate results, malformed values, offline/error fallback, bitmap cleanup.
- `pytest -q` (from backend): includes deterministic historic/expired market-state tests, barcode validation and persistence/valuation-exclusion coverage.
- `npm run build` (from frontend).
- Existing continuity and FalseTech Node tests remain mandatory in `.github/workflows/continuity-ci.yml`.

## Manual preview acceptance (before production)
- Android Chrome: photograph UPC/EAN packaging; choose a known item; save; reopen item evidence and verify unverified observation with null price and no valuation change.
- Unsupported browser: explicit local scanner unavailable message; upload flow unaffected.
- Wrong owner / owner change mid-scan: pending evidence cleared, saving prevented.
- Item not yet created or backend unavailable: no save; helpful instruction; no fabricated evidence.
- Duplicate scan: existing same item/barcode does not create a second record.
- 320px mobile viewport: capture buttons and owner/item selectors remain accessible; no hidden panel leaks.

Do not claim production release or complete cross-browser QA until real-device testing and deployment verification are recorded.
