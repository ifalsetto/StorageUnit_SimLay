from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Literal

PRICE_RE = re.compile(r"(?:US\s*)?\$\s*([0-9]{1,5}(?:,[0-9]{3})*(?:\.[0-9]{2})?)")
DATE_PATTERNS = [
    re.compile(r"(?:sold|ended|date)\s*[:\-]?\s*(\w+\s+\d{1,2},\s*\d{4})", re.I),
    re.compile(r"(\d{1,2}/\d{1,2}/\d{2,4})"),
    re.compile(r"(\d{4}-\d{2}-\d{2})"),
]
SOLD_WORDS = re.compile(r"\b(sold|ended|completed|accepted offer)\b", re.I)
ACTIVE_WORDS = re.compile(r"\b(buy it now|available|listing|listed|watching)\b", re.I)

@dataclass
class ParsedEvidence:
    price: float | None
    title: str | None
    sale_date: str | None
    listing_type: Literal["sold", "active", "auction_ended"]
    platform: str | None
    raw_text: str
    warnings: list[str]


def extract_text_from_image(path: Path) -> tuple[str, list[str]]:
    warnings: list[str] = []
    try:
        from PIL import Image
        import pytesseract
        text = pytesseract.image_to_string(Image.open(path))
        if not text.strip():
            warnings.append("ocr_empty")
        return text, warnings
    except Exception as exc:
        warnings.append(f"ocr_unavailable:{type(exc).__name__}:{exc}")
        return "", warnings


def parse_price(text: str) -> float | None:
    matches = PRICE_RE.findall(text or "")
    if not matches:
        return None
    # Use the first visible price. The UI/audit keeps raw text for review.
    try:
        return float(matches[0].replace(",", ""))
    except ValueError:
        return None


def parse_date(text: str) -> str | None:
    for pattern in DATE_PATTERNS:
        match = pattern.search(text or "")
        if not match:
            continue
        raw = match.group(1)
        for fmt in ("%b %d, %Y", "%B %d, %Y", "%m/%d/%Y", "%m/%d/%y", "%Y-%m-%d"):
            try:
                return datetime.strptime(raw, fmt).date().isoformat()
            except ValueError:
                pass
    return None


def infer_listing_type(text: str, fallback: str = "sold") -> Literal["sold", "active", "auction_ended"]:
    if SOLD_WORDS.search(text or ""):
        return "sold"
    if ACTIVE_WORDS.search(text or ""):
        return "active"
    if fallback in {"sold", "active", "auction_ended"}:
        return fallback  # type: ignore[return-value]
    return "sold"


def infer_platform(text: str, fallback: str | None = None) -> str | None:
    t = (text or "").lower()
    if "ebay" in t:
        return "ebay"
    if "facebook" in t or "marketplace" in t:
        return "facebook"
    if "mercari" in t:
        return "mercari"
    if "whatnot" in t:
        return "whatnot"
    return fallback


def parse_title(text: str) -> str | None:
    lines = [ln.strip() for ln in (text or "").splitlines() if ln.strip()]
    bad = ("$", "shipping", "seller", "feedback", "watch", "cart", "sponsored")
    for line in lines[:12]:
        lower = line.lower()
        if len(line) >= 6 and not any(token in lower for token in bad):
            return line[:160]
    return None


def parse_evidence_text(text: str, listing_type_default: str = "sold", platform_default: str | None = None) -> ParsedEvidence:
    warnings: list[str] = []
    price = parse_price(text)
    if price is None:
        warnings.append("price_not_found")
    return ParsedEvidence(
        price=price,
        title=parse_title(text),
        sale_date=parse_date(text),
        listing_type=infer_listing_type(text, listing_type_default),
        platform=infer_platform(text, platform_default),
        raw_text=text,
        warnings=warnings,
    )


def parse_screenshot(path: Path, override_text: str | None = None, listing_type_default: str = "sold", platform_default: str | None = None) -> ParsedEvidence:
    warnings: list[str] = []
    if override_text and override_text.strip():
        text = override_text
    else:
        text, warnings = extract_text_from_image(path)
    parsed = parse_evidence_text(text, listing_type_default, platform_default)
    parsed.warnings.extend(warnings)
    return parsed
