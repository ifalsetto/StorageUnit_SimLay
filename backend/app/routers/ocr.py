from __future__ import annotations

import base64
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
from app.core.database import db_session, rows_to_dicts, to_json_text
from app.core.ids import new_uuid
from app.services.normalization import choose_category, normalize_name

router = APIRouter(prefix="/api/ocr", tags=["ocr-testground"])

BACKEND_DIR = Path(__file__).resolve().parents[2]
SUPPORTED_IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp"}
SUPPORTED_MIME_TYPES = {"image/jpeg", "image/png", "image/webp"}
SUPPORTED_MERGE_LEVELS = {"word", "sentence", "paragraph"}

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
            entries = [("SONY", 0.98), ("MODEL SS-U40A", 0.94), ("6 OHMS", 0.90)]
        elif "kreg" in lower or "workbench" in lower or "tool" in lower:
            entries = [("KREG", 0.98), ("KWS1000", 0.96), ("UPC 647096805149", 0.88)]
        elif "singer" in lower or "sewing" in lower:
            entries = [("SINGER", 0.96), ("MODEL 4562", 0.89), ("SERIAL SN88912044", 0.75)]
        elif "receipt" in lower:
            entries = [("WALMART", 0.95), ("TOTAL $42.77", 0.93), ("ITEM 885911", 0.88)]
        else:
            entries = [("STORAGE UNIT ITEM", 0.80), ("MODEL FT-100", 0.76), ("SERIAL SN123456", 0.74)]

        detections = []
        for text, confidence in entries:
            detections.append({
                "text_prediction": {"text": text, "confidence": confidence},
                "bounding_box": {"points": []},
            })
        data.append({"index": idx, "text_detections": detections})
    return {"data": data, "_simlay_endpoint": "mock", "_simlay_latency_ms": 0}


async def call_nvidia_ocr(data_urls: list[str], merge_level: str) -> dict[str, Any]:
    endpoint = os.getenv("OCR_NIM_ENDPOINT", "http://localhost:8000").rstrip("/")
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
            "body": response.text[:2000],
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
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            return (match.group(1) if match.groups() else match.group(0)).strip()
    return None


def guess_brand(texts: list[str]) -> str | None:
    joined = " ".join(texts).lower()
    for brand in COMMON_BRANDS:
        if brand.lower() in joined:
            return brand
    for text in texts:
        cleaned = re.sub(r"[^A-Za-z0-9+]", "", text)
        if cleaned.isupper() and 2 <= len(cleaned) <= 15 and not cleaned.isdigit():
            return cleaned.title()
    return None


def build_candidate_name(brand: str | None, model: str | None, texts: list[str]) -> str:
    if brand and model:
        return f"{brand} {model}"
    if model:
        return f"Unknown Brand {model}"
    if brand:
        for text in texts:
            if brand.lower() not in text.lower() and 4 <= len(text) <= 80:
                return f"{brand} {text}"
        return brand
    for text in texts:
        if 4 <= len(text) <= 80:
            return text
    return "Unidentified OCR Item"


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
        notes = "Strong OCR seed. Confirm visually before listing."
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


def save_seed_as_item(conn, run_id: str, seed: SimLayItemSeed, config: dict[str, Any]) -> str:
    category, subcategory, sort_tier, collectible = choose_category(seed.candidate_name, config.get("taxonomy", {}))
    current = conn.execute("SELECT COUNT(*) c FROM items WHERE run_id=?", (run_id,)).fetchone()["c"]
    item_id = new_uuid("item")
    confidence = "Inferred" if seed.status in {"ready_for_review", "needs_review"} else "Unknown"
    confidence_reason = f"OCR seed score {seed.simlay_usefulness_score}/100; avg confidence {seed.avg_confidence}"
    notes = "\n".join([
        seed.notes,
        f"OCR evidence: {', '.join(seed.evidence_text[:12])}",
        f"Model: {seed.model_guess or 'unknown'}; Serial: {seed.serial_guess or 'unknown'}; Barcode: {seed.barcode_guess or 'unknown'}",
    ])
    conn.execute(
        """
        INSERT INTO items(
            item_id, run_id, raw_name, final_name, normalized_name, brand, category, subcategory,
            quantity, visible_condition, confidence, confidence_reason, source, notes,
            representative_image_id, detected_in_media, flag_unknown, flag_possible_collectible,
            sort_tier, sort_order
        ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (item_id, run_id, seed.candidate_name, seed.candidate_name, normalize_name(seed.candidate_name), seed.brand_guess,
         category, subcategory, 1, "Unknown", confidence, confidence_reason, "NVIDIA OCR Testground", notes,
         seed.media_id, to_json_text([seed.media_id] if seed.media_id else []), 1 if confidence == "Unknown" else 0,
         1 if collectible else 0, sort_tier, current + 1),
    )
    return item_id


@router.get("/health")
def ocr_health(provider: str | None = Query(default=None)) -> dict[str, Any]:
    mode = selected_mode(provider)
    return {
        "ok": True,
        "mode": mode,
        "mock": mode == "mock",
        "endpoint": "mock" if mode == "mock" else os.getenv("OCR_NIM_ENDPOINT", "http://localhost:8000").rstrip("/"),
        "merge_level": os.getenv("OCR_MERGE_LEVEL", "word"),
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

    mode = selected_mode(provider)
    level = validate_merge_level(merge_level)
    names: list[str] = []
    data_urls: list[str] = []

    for upload in files:
        if upload.content_type not in SUPPORTED_MIME_TYPES:
            raise HTTPException(415, f"{upload.filename}: unsupported OCR content type {upload.content_type}")
        raw = await upload.read()
        names.append(upload.filename or "upload.jpg")
        data_urls.append(file_to_data_url(raw, upload.content_type or "image/jpeg"))

    raw_ocr = mock_ocr_result(names) if mode == "mock" else await call_nvidia_ocr(data_urls, level)
    seeds = [asdict(build_item_seed(name, None, parse_boxes_for_index(raw_ocr, idx))) for idx, name in enumerate(names)]

    return {
        "ok": True,
        "mode": mode,
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
    save_items: bool = Query(default=False, description="Save OCR seeds as review items"),
    return_raw_ocr: bool = Query(default=False),
) -> dict[str, Any]:
    mode = selected_mode(provider)
    level = validate_merge_level(merge_level)
    config = load_all_config()

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

    for media in media_rows:
        file_path = BACKEND_DIR / media["file_path"]
        if not file_path.exists() or file_path.suffix.lower() not in SUPPORTED_IMAGE_SUFFIXES:
            continue
        raw = file_path.read_bytes()
        names.append(file_path.name)
        data_urls.append(file_to_data_url(raw, mime_for_path(file_path)))
        usable_media.append(media)

    if not usable_media:
        raise HTTPException(400, "Run has no OCR-supported images. Use JPG, PNG, or WEBP.")

    raw_ocr = mock_ocr_result(names) if mode == "mock" else await call_nvidia_ocr(data_urls, level)
    seeds = [build_item_seed(names[idx], media.get("media_id"), parse_boxes_for_index(raw_ocr, idx)) for idx, media in enumerate(usable_media)]

    saved_item_ids: list[str] = []
    if save_items:
        with db_session() as conn:
            for seed in seeds:
                if seed.status != "unidentified":
                    saved_item_ids.append(save_seed_as_item(conn, run_id, seed, config))
            conn.execute("UPDATE runs SET total_items=(SELECT COUNT(*) FROM items WHERE run_id=?) WHERE run_id=?", (run_id, run_id))

    scores = [seed.simlay_usefulness_score for seed in seeds]
    return {
        "ok": True,
        "mode": mode,
        "run_id": run_id,
        "images_processed": len(usable_media),
        "items_saved": len(saved_item_ids),
        "saved_item_ids": saved_item_ids,
        "avg_simlay_usefulness_score": round(statistics.mean(scores), 2) if scores else 0,
        "items": [asdict(seed) for seed in seeds],
        "raw_ocr": raw_ocr if return_raw_ocr else None,
    }
