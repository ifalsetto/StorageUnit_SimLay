from __future__ import annotations

from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Iterable

from app.services.normalization import normalize_name

STOP_WORDS = {"the", "a", "an", "set", "lot", "box", "contents", "unknown", "generic", "unbranded", "item", "items"}

@dataclass
class DedupeDecision:
    score: float
    reason: str


def tokens(value: str) -> set[str]:
    return {t for t in normalize_name(value).split() if t and t not in STOP_WORDS}


def string_similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, normalize_name(a), normalize_name(b)).ratio()


def jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def brand_match(a: dict, b: dict) -> float:
    ba = normalize_name(a.get("brand") or "")
    bb = normalize_name(b.get("brand") or "")
    if not ba or not bb:
        return 0.0
    return 1.0 if ba == bb else -0.35


def category_match(a: dict, b: dict) -> float:
    ca = normalize_name(a.get("category") or "")
    cb = normalize_name(b.get("category") or "")
    if not ca or not cb:
        return 0.0
    return 0.15 if ca == cb else -0.15


def duplicate_score(a: dict, b: dict) -> DedupeDecision:
    name_a = a.get("final_name") or a.get("raw_name") or ""
    name_b = b.get("final_name") or b.get("raw_name") or ""
    seq = string_similarity(name_a, name_b)
    jac = jaccard(tokens(name_a), tokens(name_b))
    brand = brand_match(a, b)
    cat = category_match(a, b)
    score = max(seq, jac) + brand + cat
    reason = f"seq={seq:.2f};tokens={jac:.2f};brand={brand:.2f};category={cat:.2f}"
    return DedupeDecision(score=max(0.0, min(1.0, score)), reason=reason)


def merge_duplicate(existing: dict, incoming: dict, reason: str) -> dict:
    existing.setdefault("flags", []).append("duplicate_suspect")
    existing.setdefault("dedupe_reasons", []).append(reason)
    media = set(existing.get("detected_in_media", []) or []) | set(incoming.get("detected_in_media", []) or [])
    existing["detected_in_media"] = sorted(media)
    # Quantity only increases when the upstream item explicitly confirms multiple visible units.
    incoming_qty = int(incoming.get("quantity") or 1)
    existing_qty = int(existing.get("quantity") or 1)
    if incoming.get("quantity_visually_confirmed") is True and incoming_qty > existing_qty:
        existing["quantity"] = incoming_qty
    # Prefer Verified names over Inferred/Unknown without inventing details.
    order = {"Unknown": 0, "Inferred": 1, "Verified": 2}
    if order.get(incoming.get("confidence", "Unknown"), 0) > order.get(existing.get("confidence", "Unknown"), 0):
        for key in ["raw_name", "final_name", "brand", "category", "subcategory", "visible_condition", "confidence", "confidence_reason", "notes"]:
            if incoming.get(key):
                existing[key] = incoming[key]
    return existing


def dedupe_items(raw_items: Iterable[dict], threshold: float = 0.90) -> list[dict]:
    """Conservative multi-signal dedupe.

    It merges obvious duplicates only. Ambiguous near-matches are kept separate and
    flagged for human review instead of silently combining inventory.
    """
    merged: list[dict] = []
    review_threshold = max(0.50, threshold - 0.45)
    for item in raw_items:
        name = item.get("final_name") or item.get("raw_name") or ""
        if not name.strip():
            continue
        best_index: int | None = None
        best = DedupeDecision(0.0, "no_match")
        for idx, existing in enumerate(merged):
            decision = duplicate_score(existing, item)
            if decision.score > best.score:
                best = decision
                best_index = idx
        if best_index is not None and best.score >= threshold:
            merged[best_index] = merge_duplicate(merged[best_index], item, best.reason)
        elif best.score >= review_threshold:
            clone = dict(item)
            clone.setdefault("flags", []).append("duplicate_suspect")
            clone.setdefault("dedupe_reasons", []).append(f"possible_duplicate:{best.reason}")
            merged.append(clone)
        else:
            merged.append(dict(item))
    return merged

# Backward-compatible alias used by older tests.
similarity = string_similarity
