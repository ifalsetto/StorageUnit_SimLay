import re
from typing import Any


def normalize_name(value: str | None) -> str:
    value = (value or "").strip().lower()
    value = re.sub(r"[^a-z0-9\s-]", "", value)
    value = re.sub(r"\s+", " ", value)
    return value


def choose_category(name: str, taxonomy: dict[str, Any]) -> tuple[str, str | None, int, bool]:
    text = normalize_name(name)
    categories = taxonomy.get("categories", {})
    best = ("Uncategorized", None, 99, False)
    for key, meta in categories.items():
        if meta.get("enabled", True) is False:
            continue
        keywords = meta.get("keywords", [])
        if any(k.lower() in text for k in keywords):
            return meta.get("label", key), None, int(meta.get("sort_tier", 99)), bool(meta.get("flag_as_collectible", False))
    return best
