from __future__ import annotations

import shutil
from pathlib import Path
from urllib.parse import urlparse

from fastapi import APIRouter, HTTPException, UploadFile, File, Form

from app.core.config import load_all_config, resolve_storage_path
from app.core.database import db_session, rows_to_dicts, row_to_dict
from app.core.ids import new_uuid
from app.schemas import EvidenceCreate
from app.services.evidence_parser import parse_screenshot
from app.services.url_refresh.service import refresh_evidence_url
from app.services.valuation import compute_item_valuation

router = APIRouter(prefix="/api/evidence", tags=["evidence"])


def platform_from_url(url: str | None) -> str | None:
    if not url:
        return None
    host = urlparse(url).netloc.lower()
    if "ebay" in host:
        return "ebay"
    if "facebook" in host:
        return "facebook"
    if "mercari" in host:
        return "mercari"
    if "whatnot" in host:
        return "whatnot"
    return host or "other"


def _insert_evidence(conn, *, evidence_id: str, item_id: str, source_type: str, source_name: str | None,
                     url: str | None = None, url_title: str | None = None, url_platform: str | None = None,
                     screenshot_path: str | None = None, price: float | None = None, currency: str = "USD",
                     condition: str | None = None, sale_date: str | None = None, listing_type: str = "sold",
                     is_bundle: bool = False, notes: str | None = None, refresh_status: str = "never") -> None:
    config = load_all_config()
    discount_pct = float(config["app_config"]["evidence"].get("active_listing_discount_pct", 15))
    is_active = listing_type == "active"
    discounted = price * (1 - discount_pct / 100) if price is not None and is_active else None
    exclusion_reason = "price_null" if price is None else None
    included = 0 if price is None else 1
    conn.execute("""
        INSERT INTO evidence(evidence_id, item_id, source_type, source_name, url, url_title, url_platform,
        screenshot_path, price, currency, condition, sale_date, listing_type, is_active_listing, discounted_price,
        is_bundle, notes, refresh_status, included_in_valuation, exclusion_reason)
        VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (evidence_id, item_id, source_type, source_name, url, url_title, url_platform, screenshot_path,
          price, currency, condition, sale_date, listing_type, 1 if is_active else 0, discounted,
          1 if is_bundle else 0, notes, refresh_status, included, exclusion_reason))


@router.post("")
def add_evidence(payload: EvidenceCreate):
    evidence_id = new_uuid("evidence")
    config = load_all_config()
    platform = payload.url_platform or platform_from_url(payload.url)
    with db_session() as conn:
        item = conn.execute("SELECT item_id FROM items WHERE item_id=?", (payload.item_id,)).fetchone()
        if not item:
            raise HTTPException(404, "Item not found")
        _insert_evidence(
            conn,
            evidence_id=evidence_id,
            item_id=payload.item_id,
            source_type=payload.source_type,
            source_name=payload.source_name,
            url=payload.url,
            url_title=payload.url_title,
            url_platform=platform,
            price=payload.price,
            currency=payload.currency,
            condition=payload.condition,
            sale_date=payload.sale_date,
            listing_type=payload.listing_type,
            is_bundle=payload.is_bundle,
            notes=payload.notes,
        )
        result = compute_item_valuation(conn, payload.item_id, config)
    return {"evidence_id": evidence_id, "valuation": result}


@router.post("/screenshot")
def add_screenshot_evidence(
    item_id: str = Form(...),
    file: UploadFile = File(...),
    listing_type: str = Form("sold"),
    platform: str | None = Form(None),
    notes: str | None = Form(None),
    ocr_text: str | None = Form(None),
):
    """Upload a screenshot and extract structured evidence.

    OCR is best-effort. If no price is found, evidence is stored with price=NULL and
    excluded from valuation with a clear exclusion_reason.
    """
    config = load_all_config()
    evidence_id = new_uuid("evidence")
    with db_session() as conn:
        item = row_to_dict(conn.execute("SELECT item_id, run_id FROM items WHERE item_id=?", (item_id,)).fetchone())
        if not item:
            raise HTTPException(404, "Item not found")
        root = resolve_storage_path(config, "uploads_dir") / item["run_id"] / "evidence"
        root.mkdir(parents=True, exist_ok=True)
        safe_name = Path(file.filename or f"{evidence_id}.png").name
        path = root / f"{evidence_id}_{safe_name}"
        with path.open("wb") as out:
            shutil.copyfileobj(file.file, out)
        parsed = parse_screenshot(path, override_text=ocr_text, listing_type_default=listing_type, platform_default=platform)
        rel = path.relative_to(Path(__file__).resolve().parents[2])
        combined_notes = "\n".join([x for x in [notes, f"OCR warnings: {parsed.warnings}" if parsed.warnings else None, f"OCR raw: {parsed.raw_text[:1000]}" if parsed.raw_text else None] if x])
        _insert_evidence(
            conn,
            evidence_id=evidence_id,
            item_id=item_id,
            source_type="screenshot",
            source_name="user_screenshot",
            url_title=parsed.title,
            url_platform=parsed.platform or platform,
            screenshot_path=str(rel),
            price=parsed.price,
            condition=None,
            sale_date=parsed.sale_date,
            listing_type=parsed.listing_type,
            notes=combined_notes,
        )
        result = compute_item_valuation(conn, item_id, config)
    return {"evidence_id": evidence_id, "parsed": parsed.__dict__, "valuation": result}


@router.get("/item/{item_id}")
def list_evidence(item_id: str):
    with db_session() as conn:
        rows = rows_to_dicts(conn.execute("SELECT * FROM evidence WHERE item_id=? ORDER BY created_at DESC", (item_id,)).fetchall())
    return {"evidence": rows}


@router.post("/{evidence_id}/refresh")
async def refresh_evidence(evidence_id: str):
    config = load_all_config()
    with db_session() as conn:
        try:
            return await refresh_evidence_url(conn, evidence_id, config)
        except ValueError as exc:
            raise HTTPException(404, str(exc))


@router.post("/run/{run_id}/refresh")
async def refresh_run_evidence(run_id: str):
    config = load_all_config()
    results = []
    with db_session() as conn:
        evidence = rows_to_dicts(conn.execute(
            "SELECT e.evidence_id FROM evidence e JOIN items i ON i.item_id=e.item_id WHERE i.run_id=? AND e.url IS NOT NULL",
            (run_id,),
        ).fetchall())
        for ev in evidence:
            results.append(await refresh_evidence_url(conn, ev["evidence_id"], config))
    return {"refreshed": results}


@router.post("/{evidence_id}/mark-blocked")
def mark_blocked(evidence_id: str):
    with db_session() as conn:
        ev = conn.execute("SELECT * FROM evidence WHERE evidence_id=?", (evidence_id,)).fetchone()
        if not ev:
            raise HTTPException(404, "Evidence not found")
        conn.execute("UPDATE evidence SET refresh_status='blocked', included_in_valuation=0, exclusion_reason='refresh_blocked' WHERE evidence_id=?", (evidence_id,))
    return {"updated": True, "refresh_status": "blocked"}
