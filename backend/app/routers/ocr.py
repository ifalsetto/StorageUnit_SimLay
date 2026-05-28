from __future__ import annotations

import base64
import hashlib
import mimetypes
import os
import re
import statistics
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import httpx
from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile

from app.core.config import load_all_config
from app.core.database import db_session, row_to_dict, rows_to_dicts, to_json_text
from app.core.ids import new_uuid
from app.services.normalization import choose_category, normalize_name

router = APIRouter(prefix="/api/ocr", tags=["ocr-testground"])

BACKEND_DIR = Path(__file__).resolve().parents[2]
SUPPORTED_IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp"}
SUPPORTED_MIME_TYPES = {"image/jpeg", "image/png", "image/webp"}
SUPPORTED_MERGE_LEVELS = {"word", "sentence", "paragraph"}
MAX_UPLOAD_BYTES = int(os.getenv("SIMLAY_OCR_MAX_UPLOAD_BYTES", str(8 * 1024 * 1024)))
MAX_UPLOAD_FILES = int(os.getenv("SIMLAY_OCR_MAX_UPLOAD_FILES", "20"))
ALLOWED_PROMOTION_PROVIDERS = {"nvidia"}

COMMON_BRANDS = [
    "Sony", "Samsung", "LG", "Panasonic", "Vizio", "Bose", "JBL", "Kreg",
    "DeWalt", "Milwaukee", "Ryobi", "Craftsman", "Makita", "Nintendo", "Xbox",
    "PlayStation", "Apple", "Dell", "HP", "Lenovo", "Asus", "Acer", "Logitech",
    "Razer", "Corsair", "KitchenAid", "Shark", "Dyson", "Whirlpool", "GE",
    "Frigidaire", "Black+Decker", "Singer", "Brother", "Canon", "Epson", "Kobalt", "Husky",
]

MODEL_PATTERNS = [
    r"\bMODEL[:\s#-]*([A-Z0-9][A-Z0-9\-_.]{2,})\b",
    r"\bMOD[:\s#-]*([A-Z0-9][A-Z0-9\-_.]{2,})\b",
    r"\bM/N[:\s#-]*([A-Z0-9][A-Z0-9\-_.]{2,})\b",
    r"\bTYPE[:\s#-]*([A-Z0-9][A-Z0-9\-_.]{2,})\b",
    r"\b([A-Z]{1,6}[-_]?\d{2,7}[A-Z0-9\-_.]*)\b",
]

SERIAL_PATTERNS = [
    r"\bSERIAL[:\s#-]*([A-Z0-9][A-Z0-9\-_.]{4,})\b",
    r"\bS/N[:\s#-]*([A-Z0-9][A-Z0-9\-_.]{4,})\b",
    r"\bSN[:\s#-]*([A-Z0-9][A-Z0-9\-_.]{4,})\b",
]

BARCODE_PATTERNS = [
    r"\bUPC[:\s#-]*(\d{8,14})\b",
    r"\bEAN[:\s#-]*(\d{8,14})\b",
    r"\bISBN[:\s#-]*([0-9Xx\-]{10,17})\b",
    r"\b(\d{12,14})\b",
]

PRICE_PATTERNS = [
    r"\$\s?\d+(?:\.\d{2})?",
    r"\bTOTAL[:\s]*\$?\s?\d+(?:\.\d{2})?\b",
]


@dataclass
class OCRBox:
    text: str
    confidence: float
    bounding_box: dict[str, Any]


@dataclass
class SimLayItemSeed:
    source_image: str
    media_id: str | None
    candidate_name: str
    brand_guess: str | None
    model_guess: str | None
    serial_guess: str | None
    barcode_guess: str | None
    price_guess: str | None
    evidence_text: list[str]
    avg_confidence: float
    simlay_usefulness_score: int
    status: str
    notes: str


def env_bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def selected_mode(provider: str | None = None) -> str:
    if provider:
        provider = provider.strip().lower()
        if provider in {"mock", "nvidia"}:
            return provider
        raise HTTPException(400, "OCR provider must be mock or nvidia")
    return "mock" if env_bool("SIMLAY_OCR_MOCK", True) else "nvidia"


def validate_merge_level(value: str | None) -> str:
    level = (value or os.getenv("OCR_MERGE_LEVEL", "word")).strip().lower()
    if level not in SUPPORTED_MERGE_LEVELS:
        raise HTTPException(400, "OCR merge_level must be word, sentence, or paragraph")
    return level


def verify_image_upload(filename: str, content_type: str | None, raw: bytes) -> str:
    if not raw:
        raise HTTPException(400, f"{filename}: empty upload")
    if len(raw) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, f"{filename}: OCR image exceeds {MAX_UPLOAD_BYTES} byte limit")
    if content_type not in SUPPORTED_MIME_TYPES:
        raise HTTPException(415, f"{filename}: unsupported OCR content type {content_type}")
    suffix = Path(filename).suffix.lower()
    expected_magic = {
        "image/jpeg": [b"\xff\xd8\xff"],
        "image/png": [b"\x89PNG\r\n\x1a\n"],
        "image/webp": [b"RIFF"],
    }
    if content_type == "image/webp" and not (raw.startswith(b"RIFF") and raw[8:12] == b"WEBP"):
        raise HTTPException(415, f"{filename}: invalid WEBP image bytes")
    if content_type != "image/webp" and not any(raw.startswith(prefix) for prefix in expected_magic[content_type]):
        raise HTTPException(415, f"{filename}: file bytes do not match declared content type")
    if suffix and suffix not in SUPPORTED_IMAGE_SUFFIXES:
        raise HTTPException(415, f"{filename}: unsupported OCR file extension")
    return content_type


def file_to_data_url(raw: bytes, mime_type: str) -> str:
    encoded = base64.b64encode(raw).decode("utf-8")
    return f"data:{mime_type};base64,{encoded}"


def mime_for_path(path: Path) -> str:
    guessed, _ = mimetypes.guess_type(path.name)
    if guessed in SUPPORTED_MIME_TYPES:
        return guessed
    if path.suffix.lower() in {".jpg", ".jpeg"}:
        return "image/jpeg"
    if path.suffix.lower() == ".png":
        return "image/png"
    if path.suffix.lower() == ".webp":
        return "image/webp"
    raise HTTPException(415, f"Unsupported OCR image type: {path.name}")


def mock_ocr_result(names: list[str]) -> dict[str, Any]:
    data = []
    for idx, name in enumerate(names):
        lower = name.lower()
        if "sony" in lower or "speaker" in lower:
            entries = [("MOCK_DO_NOT_SAVE SONY", 0.98), ("MOCK_DO_NOT_SAVE MODEL SS-U40A", 0.94), ("MOCK_DO_NOT_SAVE 6 OHMS", 0.90)]
        elif "kreg" in lower or "workbench" in lower or "tool" in lower:
            entries = [("MOCK_DO_NOT_SAVE KREG", 0.98), ("MOCK_DO_NOT_SAVE KWS1000", 0.96), ("MOCK_DO_NOT_SAVE UPC 647096805149", 0.88)]
        elif "singer" in lower or "sewing" in lower:
            entries = [("MOCK_DO_NOT_SAVE SINGER", 0.96), ("MOCK_DO_NOT_SAVE MODEL 4562", 0.89), ("MOCK_DO_NOT_SAVE SERIAL SN88912044", 0.75)]
        elif "receipt" in lower:
            entries = [("MOCK_DO_NOT_SAVE WALMART", 0.95), ("MOCK_DO_NOT_SAVE TOTAL $42.77", 0.93), ("MOCK_DO_NOT_SAVE ITEM 885911", 0.88)]
        else:
            entries = [("MOCK_DO_NOT_SAVE STORAGE UNIT ITEM", 0.80), ("MOCK_DO_NOT_SAVE MODEL FT-100", 0.76), ("MOCK_DO_NOT_SAVE SERIAL SN123456", 0.74)]
        detections = []
        for text, confidence in entries:
            detections.append({
                "text_prediction": {"text": text, "confidence": confidence},
                "bounding_box": {"points": []},
            })
        data.append({"index": idx, "text_detections": detections})
    return {"data": data, "_simlay_endpoint": "mock", "_simlay_latency_ms": 0}


async def call_nvidia_ocr(data_urls: list[str], merge_level: str) -> dict[str, Any]:
    endpoint = os.getenv("OCR_NIM_ENDPOINT")
    if not endpoint:
        raise HTTPException(500, "OCR_NIM_ENDPOINT must be set for provider=nvidia")
    endpoint = endpoint.rstrip("/")
    timeout = float(os.getenv("OCR_TIMEOUT_SECONDS", "120"))
    payload = {
        "input": [{"type": "image_url", "url": url} for url in data_urls],
        "merge_levels": [merge_level for _ in data_urls],
    }
    started = time.time()
    async with httpx.AsyncClient(timeout=timeout) as client:
        response = await client.post(
            f"{endpoint}/v1/infer",
            headers={"accept": "application/json", "Content-Type": "application/json"},
            json=payload,
        )
    latency_ms = round((time.time() - started) * 1000, 2)
    if response.status_code >= 400:
        raise HTTPException(502, {
            "message": "NVIDIA OCR request failed",
            "endpoint": f"{endpoint}/v1/infer",
            "status_code": response.status_code,
            "body": response.text[:500],
        })
    result = response.json()
    result["_simlay_endpoint"] = f"{endpoint}/v1/infer"
    result["_simlay_latency_ms"] = latency_ms
    return result


def parse_boxes_for_index(result: dict[str, Any], image_index: int) -> list[OCRBox]:
    boxes: list[OCRBox] = []
    for image_result in result.get("data", []):
        if int(image_result.get("index", -1)) != image_index:
            continue
        for detection in image_result.get("text_detections", []):
            prediction = detection.get("text_prediction", {})
            text = str(prediction.get("text", "")).strip()
            if not text:
                continue
            boxes.append(OCRBox(
                text=text,
                confidence=float(prediction.get("confidence", 0) or 0),
                bounding_box=detection.get("bounding_box", {}),
            ))
    return boxes


def first_match(patterns: list[str], text: str) -> str | None:
    cleaned = text.replace("MOCK_DO_NOT_SAVE", "")
    for pattern in patterns:
        match = re.search(pattern, cleaned, flags=re.IGNORECASE)
        if match:
            return (match.group(1) if match.groups() else match.group(0)).strip()
    return None


def guess_brand(texts: list[str]) -> str | None:
    joined = " ".join(texts).replace("MOCK_DO_NOT_SAVE", "").lower()
    for brand in COMMON_BRANDS:
        if brand.lower() in joined:
            return brand
    for text in texts:
        text = text.replace("MOCK_DO_NOT_SAVE", "").strip()
        cleaned = re.sub(r"[^A-Za-z0-9+]", "", text)
        if cleaned.isupper() and 2 <= len(cleaned) <= 15 and not cleaned.isdigit():
            return cleaned.title()
    return None


def build_candidate_name(brand: str | None, model: str | None, texts: list[str]) -> str:
    clean_texts = [text.replace("MOCK_DO_NOT_SAVE", "").strip() for text in texts]
    if brand and model:
        return f"{brand} {model}"
    if model:
        return f"Unknown Brand {model}"
    if brand:
        for text in clean_texts:
            if brand.lower() not in text.lower() and 4 <= len(text) <= 80:
                return f"{brand} {text}"
        return brand
    for text in clean_texts:
        if 4 <= len(text) <= 80:
            return text
    return "Unidentified OCR Candidate"


def score_item(brand: str | None, model: str | None, serial: str | None, barcode: str | None, price: str | None, avg_confidence: float, text_count: int) -> int:
    score = 0
    if brand:
        score += 20
    if model:
        score += 30
    if barcode:
        score += 25
    if serial:
        score += 10
    if price:
        score += 5
    if avg_confidence >= 0.85:
        score += 10
    elif avg_confidence >= 0.70:
        score += 5
    if text_count >= 4:
        score += 5
    return max(0, min(100, score))


def build_item_seed(source_image: str, media_id: str | None, boxes: list[OCRBox]) -> SimLayItemSeed:
    min_confidence = float(os.getenv("SIMLAY_MIN_CONFIDENCE", "0.50"))
    useful = [box for box in boxes if box.confidence >= min_confidence]
    texts = [box.text for box in useful]
    joined = "\n".join(texts)
    brand = guess_brand(texts)
    model = first_match(MODEL_PATTERNS, joined)
    serial = first_match(SERIAL_PATTERNS, joined)
    barcode = first_match(BARCODE_PATTERNS, joined)
    price = first_match(PRICE_PATTERNS, joined)
    avg_confidence = round(statistics.mean([b.confidence for b in useful]), 4) if useful else 0.0
    score = score_item(brand, model, serial, barcode, price, avg_confidence, len(texts))
    candidate_name = build_candidate_name(brand, model, texts)
    if score >= 75:
        status = "ready_for_review"
        notes = "Strong OCR candidate. Must be visually confirmed before item promotion."
    elif score >= 45:
        status = "needs_review"
        notes = "OCR found usable clues, but item identity still needs confirmation."
    elif texts:
        status = "weak_evidence"
        notes = "OCR found text, but not enough for trusted inventory identity."
    else:
        status = "unidentified"
        notes = "No useful OCR evidence found."
    return SimLayItemSeed(source_image, media_id, candidate_name, brand, model, serial, barcode, price, texts[:50], avg_confidence, score, status, notes)


def candidate_hash(run_id: str, provider: str, seed: SimLayItemSeed) -> str:
    payload = "|".join([
        run_id,
        provider,
        seed.media_id or "",
        seed.source_image,
        normalize_name(seed.candidate_name),
        seed.barcode_guess or "",
        seed.model_guess or "",
        "\n".join(seed.evidence_text[:20]),
    ])
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def insert_or_update_candidate(conn, run_id: str, provider: str, seed: SimLayItemSeed, raw_ocr: dict[str, Any] | None = None) -> str:
    h = candidate_hash(run_id, provider, seed)
    existing = conn.execute(
        "SELECT candidate_id FROM ocr_candidates WHERE run_id=? AND candidate_hash=?",
        (run_id, h),
    ).fetchone()
    candidate_id = existing["candidate_id"] if existing else new_uuid("ocr")
    raw_text = to_json_text(raw_ocr) if raw_ocr is not None else None
    conn.execute(
        """
        INSERT INTO ocr_candidates(
            candidate_id, run_id, media_id, source_image, provider, candidate_hash,
            candidate_name, brand_guess, model_guess, serial_guess, barcode_guess, price_guess,
            evidence_text, raw_ocr, avg_confidence, simlay_usefulness_score,
            ocr_status, review_status, notes
        ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending_review', ?)
        ON CONFLICT(run_id, candidate_hash) DO UPDATE SET
            candidate_name=excluded.candidate_name,
            brand_guess=excluded.brand_guess,
            model_guess=excluded.model_guess,
            serial_guess=excluded.serial_guess,
            barcode_guess=excluded.barcode_guess,
            price_guess=excluded.price_guess,
            evidence_text=excluded.evidence_text,
            raw_ocr=excluded.raw_ocr,
            avg_confidence=excluded.avg_confidence,
            simlay_usefulness_score=excluded.simlay_usefulness_score,
            ocr_status=excluded.ocr_status,
            notes=excluded.notes,
            updated_at=CURRENT_TIMESTAMP
        """,
        (
            candidate_id, run_id, seed.media_id, seed.source_image, provider, h,
            seed.candidate_name, seed.brand_guess, seed.model_guess, seed.serial_guess,
            seed.barcode_guess, seed.price_guess, to_json_text(seed.evidence_text), raw_text,
            seed.avg_confidence, seed.simlay_usefulness_score, seed.status, seed.notes,
        ),
    )
    conn.execute(
        """
        INSERT INTO audit_events(audit_id, run_id, entity_type, entity_id, action, payload)
        VALUES(?, ?, 'ocr_candidate', ?, 'create', ?)
        """,
        (new_uuid("audit"), run_id, candidate_id, to_json_text({"provider": provider, "candidate_hash": h, "candidate_name": seed.candidate_name})),
    )
    return candidate_id


def update_run_counts(conn, run_id: str) -> None:
    counts = conn.execute(
        """
        SELECT COUNT(*) total,
               SUM(CASE WHEN confidence='Verified' THEN 1 ELSE 0 END) verified,
               SUM(CASE WHEN confidence='Inferred' THEN 1 ELSE 0 END) inferred,
               SUM(CASE WHEN confidence='Unknown' THEN 1 ELSE 0 END) unknown
        FROM items WHERE run_id=?
        """,
        (run_id,),
    ).fetchone()
    conn.execute(
        """
        UPDATE runs
        SET total_items=?, total_verified=?, total_inferred=?, total_unknown=?, updated_at=CURRENT_TIMESTAMP
        WHERE run_id=?
        """,
        (counts["total"] or 0, counts["verified"] or 0, counts["inferred"] or 0, counts["unknown"] or 0, run_id),
    )


def promote_candidate_to_item(conn, candidate: dict[str, Any], config: dict[str, Any]) -> str:
    if candidate["provider"] not in ALLOWED_PROMOTION_PROVIDERS:
        raise HTTPException(400, "Mock/test OCR candidates cannot be promoted to inventory")
    if candidate.get("review_status") == "promoted" and candidate.get("promoted_item_id"):
        return candidate["promoted_item_id"]
    if candidate.get("review_status") == "rejected":
        raise HTTPException(400, "Rejected OCR candidates cannot be promoted")

    run_id = candidate["run_id"]
    category, subcategory, sort_tier, collectible = choose_category(candidate["candidate_name"], config.get("taxonomy", {}))
    current = conn.execute("SELECT COUNT(*) c FROM items WHERE run_id=?", (run_id,)).fetchone()["c"]
    item_id = new_uuid("item")
    confidence_reason = (
        f"Promoted from OCR candidate {candidate['candidate_id']}; "
        f"provider={candidate['provider']}; score={candidate['simlay_usefulness_score']}/100; "
        f"avg_confidence={candidate['avg_confidence']}. Requires human visual confirmation."
    )
    evidence_text = candidate.get("evidence_text") or "[]"
    notes = "\n".join([
        candidate.get("notes") or "OCR candidate promoted for review.",
        f"OCR evidence: {evidence_text}",
        f"Model: {candidate.get('model_guess') or 'unknown'}; Serial: {candidate.get('serial_guess') or 'unknown'}; Barcode: {candidate.get('barcode_guess') or 'unknown'}",
    ])
    conn.execute(
        """
        INSERT INTO items(
            item_id, run_id, raw_name, final_name, normalized_name, brand, category, subcategory,
            quantity, visible_condition, confidence, confidence_reason, source, notes,
            representative_image_id, detected_in_media, flag_unknown, flag_missing_comps,
            flag_possible_collectible, sort_tier, sort_order
        ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, 1, 'Unknown', 'Unknown', ?, 'Manual', ?, ?, ?, 1, 1, ?, ?, ?)
        """,
        (
            item_id, run_id, candidate["candidate_name"], candidate["candidate_name"], normalize_name(candidate["candidate_name"]),
            candidate.get("brand_guess"), category, subcategory, confidence_reason, notes,
            candidate.get("media_id"), to_json_text([candidate["media_id"]] if candidate.get("media_id") else []),
            1 if collectible else 0, sort_tier, current + 1,
        ),
    )
    conn.execute(
        """
        INSERT INTO evidence(evidence_id, item_id, source_type, source_name, listing_type, included_in_valuation, notes)
        VALUES(?, ?, 'library', 'ocr_candidate', 'active', 0, ?)
        """,
        (new_uuid("ev"), item_id, f"OCR candidate evidence only. Not a price comp. {evidence_text}"),
    )
    conn.execute(
        """
        UPDATE ocr_candidates
        SET review_status='promoted', promoted_item_id=?, updated_at=CURRENT_TIMESTAMP
        WHERE candidate_id=?
        """,
        (item_id, candidate["candidate_id"]),
    )
    conn.execute(
        """
        INSERT INTO audit_events(audit_id, run_id, entity_type, entity_id, action, payload)
        VALUES(?, ?, 'ocr_candidate', ?, 'update', ?)
        """,
        (new_uuid("audit"), run_id, candidate["candidate_id"], to_json_text({"promoted_item_id": item_id, "candidate_name": candidate["candidate_name"]})),
    )
    update_run_counts(conn, run_id)
    return item_id


@router.get("/health")
def ocr_health(provider: str | None = Query(default=None)) -> dict[str, Any]:
    mode = selected_mode(provider)
    return {
        "ok": True,
        "mode": mode,
        "mock": mode == "mock",
        "can_stage_candidates": True,
        "can_promote_to_inventory": mode in ALLOWED_PROMOTION_PROVIDERS,
        "endpoint": "mock" if mode == "mock" else os.getenv("OCR_NIM_ENDPOINT"),
        "merge_level": os.getenv("OCR_MERGE_LEVEL", "word"),
        "max_upload_bytes": MAX_UPLOAD_BYTES,
        "max_upload_files": MAX_UPLOAD_FILES,
    }


@router.post("/analyze-upload")
async def analyze_uploads(
    files: list[UploadFile] = File(...),
    provider: str | None = Query(default=None, description="mock or nvidia"),
    merge_level: str | None = Form(default=None),
    return_raw_ocr: bool = Form(default=False),
) -> dict[str, Any]:
    if not files:
        raise HTTPException(400, "Upload at least one image")
    if len(files) > MAX_UPLOAD_FILES:
        raise HTTPException(413, f"Too many OCR files. Limit is {MAX_UPLOAD_FILES}")
    mode = selected_mode(provider)
    level = validate_merge_level(merge_level)
    names: list[str] = []
    data_urls: list[str] = []
    for upload in files:
        filename = upload.filename or "upload.jpg"
        raw = await upload.read()
        mime_type = verify_image_upload(filename, upload.content_type, raw)
        names.append(filename)
        data_urls.append(file_to_data_url(raw, mime_type))
    raw_ocr = mock_ocr_result(names) if mode == "mock" else await call_nvidia_ocr(data_urls, level)
    seeds = [asdict(build_item_seed(name, None, parse_boxes_for_index(raw_ocr, idx))) for idx, name in enumerate(names)]
    return {
        "ok": True,
        "mode": mode,
        "warning": "Mock OCR output is synthetic and cannot be saved or promoted." if mode == "mock" else None,
        "images_processed": len(files),
        "avg_simlay_usefulness_score": round(statistics.mean([s["simlay_usefulness_score"] for s in seeds]), 2) if seeds else 0,
        "items": seeds,
        "raw_ocr": raw_ocr if return_raw_ocr else None,
    }


@router.post("/run/{run_id}")
async def analyze_run_media(
    run_id: str,
    provider: str | None = Query(default=None, description="mock or nvidia"),
    merge_level: str | None = Query(default=None),
    stage_candidates: bool = Query(default=True, description="Save OCR output to ocr_candidates staging table"),
    save_items: bool = Query(default=False, description="Deprecated and blocked. Use candidate promotion instead."),
    return_raw_ocr: bool = Query(default=False),
) -> dict[str, Any]:
    if save_items:
        raise HTTPException(400, "save_items=true has been removed. OCR must stage candidates first, then promote after review.")
    mode = selected_mode(provider)
    level = validate_merge_level(merge_level)
    with db_session() as conn:
        run = conn.execute("SELECT * FROM runs WHERE run_id=?", (run_id,)).fetchone()
        if not run:
            raise HTTPException(404, "Run not found")
        media_rows = rows_to_dicts(conn.execute(
            """
            SELECT * FROM media_inputs
            WHERE run_id=? AND file_type IN ('photo', 'keyframe')
            ORDER BY sequence_order
            """,
            (run_id,),
        ).fetchall())
    if not media_rows:
        raise HTTPException(400, "No photo/keyframe media found for this run")
    names: list[str] = []
    data_urls: list[str] = []
    usable_media: list[dict[str, Any]] = []
    for media in media_rows[:MAX_UPLOAD_FILES]:
        file_path = BACKEND_DIR / media["file_path"]
        if not file_path.exists() or file_path.suffix.lower() not in SUPPORTED_IMAGE_SUFFIXES:
            continue
        raw = file_path.read_bytes()
        if len(raw) > MAX_UPLOAD_BYTES:
            continue
        names.append(file_path.name)
        data_urls.append(file_to_data_url(raw, mime_for_path(file_path)))
        usable_media.append(media)
    if not usable_media:
        raise HTTPException(400, "Run has no OCR-supported images. Use JPG, PNG, or WEBP.")
    raw_ocr = mock_ocr_result(names) if mode == "mock" else await call_nvidia_ocr(data_urls, level)
    seeds = [build_item_seed(names[idx], media.get("media_id"), parse_boxes_for_index(raw_ocr, idx)) for idx, media in enumerate(usable_media)]
    candidate_ids: list[str] = []
    if stage_candidates:
        with db_session() as conn:
            for idx, seed in enumerate(seeds):
                if seed.status != "unidentified":
                    single_raw = {"data": [raw_ocr.get("data", [])[idx]]} if raw_ocr.get("data") and idx < len(raw_ocr["data"]) else None
                    candidate_ids.append(insert_or_update_candidate(conn, run_id, mode, seed, single_raw if return_raw_ocr else None))
    scores = [seed.simlay_usefulness_score for seed in seeds]
    return {
        "ok": True,
        "mode": mode,
        "warning": "Mock OCR output is synthetic and cannot be promoted." if mode == "mock" else None,
        "run_id": run_id,
        "images_processed": len(usable_media),
        "candidates_staged": len(candidate_ids),
        "candidate_ids": candidate_ids,
        "items_saved": 0,
        "avg_simlay_usefulness_score": round(statistics.mean(scores), 2) if scores else 0,
        "items": [asdict(seed) for seed in seeds],
        "raw_ocr": raw_ocr if return_raw_ocr else None,
    }


@router.get("/candidates/{run_id}")
def list_ocr_candidates(run_id: str, review_status: str | None = Query(default=None)) -> dict[str, Any]:
    with db_session() as conn:
        run = conn.execute("SELECT run_id FROM runs WHERE run_id=?", (run_id,)).fetchone()
        if not run:
            raise HTTPException(404, "Run not found")
        if review_status:
            rows = rows_to_dicts(conn.execute(
                "SELECT * FROM ocr_candidates WHERE run_id=? AND review_status=? ORDER BY created_at DESC",
                (run_id, review_status),
            ).fetchall())
        else:
            rows = rows_to_dicts(conn.execute(
                "SELECT * FROM ocr_candidates WHERE run_id=? ORDER BY created_at DESC",
                (run_id,),
            ).fetchall())
    return {"candidates": rows}


@router.post("/candidates/{candidate_id}/promote")
def promote_candidate(candidate_id: str) -> dict[str, Any]:
    config = load_all_config()
    with db_session() as conn:
        candidate = row_to_dict(conn.execute("SELECT * FROM ocr_candidates WHERE candidate_id=?", (candidate_id,)).fetchone())
        if not candidate:
            raise HTTPException(404, "OCR candidate not found")
        item_id = promote_candidate_to_item(conn, candidate, config)
    return {"promoted": True, "candidate_id": candidate_id, "item_id": item_id}


@router.post("/candidates/{candidate_id}/reject")
def reject_candidate(candidate_id: str, reason: str | None = Query(default=None)) -> dict[str, Any]:
    with db_session() as conn:
        candidate = row_to_dict(conn.execute("SELECT * FROM ocr_candidates WHERE candidate_id=?", (candidate_id,)).fetchone())
        if not candidate:
            raise HTTPException(404, "OCR candidate not found")
        if candidate.get("review_status") == "promoted":
            raise HTTPException(400, "Promoted OCR candidates cannot be rejected")
        conn.execute(
            "UPDATE ocr_candidates SET review_status='rejected', notes=COALESCE(notes, '') || ?, updated_at=CURRENT_TIMESTAMP WHERE candidate_id=?",
            (f"\nRejected: {reason or 'no reason provided'}", candidate_id),
        )
        conn.execute(
            """
            INSERT INTO audit_events(audit_id, run_id, entity_type, entity_id, action, payload)
            VALUES(?, ?, 'ocr_candidate', ?, 'update', ?)
            """,
            (new_uuid("audit"), candidate["run_id"], candidate_id, to_json_text({"review_status": "rejected", "reason": reason})),
        )
    return {"rejected": True, "candidate_id": candidate_id}
