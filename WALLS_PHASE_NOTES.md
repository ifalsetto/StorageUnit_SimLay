# StorageUnit SimLay — WALLS Phase Upgrade

## Added modules

1. Real OpenAI Vision test prompts
   - `backend/app/services/vision/prompts.py`
   - `backend/app/services/vision/openai_provider.py`
   - `backend/scripts/test_openai_vision_prompt.py`

2. Screenshot OCR evidence parser
   - `backend/app/services/evidence_parser.py`
   - `POST /api/evidence/screenshot`
   - Stores `price=NULL` when parsing fails and excludes that evidence from valuation.

3. Stronger dedupe engine
   - `backend/app/services/dedupe.py`
   - Multi-signal text/category/brand scoring.
   - Ambiguous near-matches are flagged, not silently merged.

4. eBay API connector scaffold
   - `backend/app/services/market/ebay.py`
   - `GET /api/connectors/ebay/status`
   - `GET /api/connectors/ebay/search-active`
   - Disabled until credentials and config are supplied.
   - Sold-listing coverage is not claimed.

5. URL refresh adapters
   - `backend/app/services/url_refresh/*`
   - `POST /api/evidence/{evidence_id}/refresh`
   - `POST /api/evidence/run/{run_id}/refresh`
   - Fails closed for unsupported/login-wall domains.

6. Full end-to-end test suite
   - `backend/tests/test_prompt_contract.py`
   - `backend/tests/test_evidence_parser.py`
   - `backend/tests/test_dedupe_engine.py`
   - `backend/tests/test_url_refresh.py`
   - `backend/tests/test_e2e_export.py`
   - `backend/tests/test_valuation.py`

## Verification performed

```powershell
cd backend
$env:PYTHONPATH='.'
python scripts\validate_config.py
python -m compileall app scripts tests
pytest -q
```

Expected result:

```text
CONFIG VALID
12 passed
```

## Truth rules preserved

- No silent guessing.
- Unknown evidence stays excluded from valuation.
- URL refresh does not scrape login walls or bypass protections.
- eBay connector stays disabled until credentials/config are present.
- Wix CSV headers stay schema-driven and strict.
