# SimLay Nemotron OCR Testground

## 1 - Purpose

This branch adds a contained OCR evaluation layer to the existing StorageUnit SimLay app.

Goal:

```text
Uploaded SimLay media
→ OCR text extraction
→ item seed candidates
→ optional save as review inventory items
```

This does not replace the existing OpenAI Vision or mock vision pipeline. It is a testground to decide whether NVIDIA OCR is worth keeping.

## 2 - Added backend endpoints

```text
GET  /api/ocr/health?provider=mock
POST /api/ocr/analyze-upload?provider=mock
POST /api/ocr/run/{run_id}?provider=mock&save_items=false
POST /api/ocr/run/{run_id}?provider=mock&save_items=true
```

Provider options:

```text
mock
nvidia
```

## 3 - Mock mode

Mock mode works without NVIDIA installed.

```powershell
$env:SIMLAY_OCR_MOCK="true"
.\START_APP_WINDOWS.ps1
```

Then open:

```text
http://127.0.0.1:8000/docs
```

Test:

```text
GET /api/ocr/health?provider=mock
```

## 4 - Real NVIDIA OCR mode

Expected NVIDIA NIM endpoint:

```text
http://localhost:8000/v1/infer
```

Set environment:

```powershell
$env:SIMLAY_OCR_MOCK="false"
$env:OCR_NIM_ENDPOINT="http://localhost:8000"
$env:OCR_MERGE_LEVEL="word"
$env:OCR_TIMEOUT_SECONDS="120"
$env:SIMLAY_MIN_CONFIDENCE="0.50"
```

Then call:

```text
POST /api/ocr/run/{run_id}?provider=nvidia&save_items=false
```

## 5 - Best SimLay test flow

1. Create a run.
2. Upload 10-20 photos.
3. Use the normal media intake first.
4. Run OCR in mock mode.
5. Run OCR in NVIDIA mode.
6. Compare usefulness score and evidence text.
7. Only use `save_items=true` after reviewing output quality.

## 6 - OCR output contract

Each OCR item seed returns:

```json
{
  "source_image": "photo.jpg",
  "media_id": "media_xxx",
  "candidate_name": "Sony SS-U40A",
  "brand_guess": "Sony",
  "model_guess": "SS-U40A",
  "serial_guess": null,
  "barcode_guess": null,
  "price_guess": null,
  "evidence_text": ["SONY", "MODEL SS-U40A", "6 OHMS"],
  "avg_confidence": 0.94,
  "simlay_usefulness_score": 60,
  "status": "needs_review",
  "notes": "OCR found usable clues, but item identity still needs confirmation."
}
```

## 7 - Save behavior

If `save_items=true`, the backend creates review items using:

```text
source = NVIDIA OCR Testground
confidence = Inferred or Unknown
condition = Unknown
notes = OCR evidence + model/serial/barcode clues
```

Unidentified OCR results are not saved.

## 8 - Pass / fail gate

Keep OCR if:

```text
- 80%+ of label/box photos produce useful text
- average confidence stays above 0.75
- brand/model/barcode clues appear often
- saved seeds reduce manual typing
```

Reject or pause OCR if:

```text
- it only works on perfect photos
- storage-unit lighting destroys accuracy
- it creates too many wrong candidates
- setup friction outweighs the benefit
```

## 9 - Current branch safety rule

This branch adds OCR as optional infrastructure only.

Do not merge this as default behavior until real storage-unit photos pass the test gate.
