from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ALLOWED_CONFIDENCE = ["Verified", "Inferred", "Unknown"]
ALLOWED_CONDITION = ["New", "Like New", "Used", "Fair", "Parts", "Unknown"]

SYSTEM_PROMPT = """
You are StorageUnit SimLay's accuracy-first visual inventory analyst.
Your only job is to describe visible storage-unit items truthfully and defensibly.
You must never invent brand, model, condition, quantity, or contents.
When uncertain, label uncertainty instead of guessing.
""".strip()

ITEM_DETECTION_PROMPT = """
Analyze the storage-unit image and return ONLY valid JSON matching this shape:
{
  "items": [
    {
      "raw_name": "string",
      "final_name": "string",
      "brand": "string or null",
      "category": "string or null",
      "subcategory": "string or null",
      "quantity": 1,
      "visible_condition": "New | Like New | Used | Fair | Parts | Unknown",
      "confidence": "Verified | Inferred | Unknown",
      "confidence_reason": "short visual rationale",
      "source": "User Visual",
      "notes": "visible-only notes",
      "flags": ["unknown", "duplicate_suspect", "missing_comps", "high_variance", "possible_collectible"]
    }
  ],
  "image_notes": "short note about visibility/limitations"
}

Truth rules:
1. Do not invent brands, models, variants, years, generations, sizes, editions, or contents.
2. Verified means a clear brand/model/identifier is visible in the image.
3. Inferred means the item type is clear but exact brand/model is not visually confirmed.
4. Unknown means the item is obscured, boxed, bundled, blurry, too dark, or unclear.
5. visible_condition must be based only on what is visible.
6. If condition cannot be seen confidently, use Unknown.
7. Quantity increases only when multiple units are clearly visible.
8. Boxes/totes must be named as "Contents unknown" unless contents are visible.
9. Small indistinct objects should be grouped as a lot.
10. Do not estimate price in this step.

Item ordering preference for returned items:
- large anchor items first
- medium standalone items second
- small grouped lots third
- boxes/totes fourth
- scrap/junk last only if clearly useful
""".strip()

SELF_CHECK_PROMPT = """
Before returning JSON, silently check:
- Is every confidence value one of Verified/Inferred/Unknown?
- Did you avoid guessing brands/models?
- Did you use Unknown for obscured/boxed/unclear items?
- Did you avoid prices?
- Is the JSON parseable?
Return only JSON. No markdown.
""".strip()

VISION_RESPONSE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["items", "image_notes"],
    "additionalProperties": False,
    "properties": {
        "items": {
            "type": "array",
            "items": {
                "type": "object",
                "required": [
                    "raw_name", "final_name", "brand", "category", "subcategory", "quantity",
                    "visible_condition", "confidence", "confidence_reason", "source", "notes", "flags"
                ],
                "additionalProperties": False,
                "properties": {
                    "raw_name": {"type": "string"},
                    "final_name": {"type": "string"},
                    "brand": {"type": ["string", "null"]},
                    "category": {"type": ["string", "null"]},
                    "subcategory": {"type": ["string", "null"]},
                    "quantity": {"type": "integer", "minimum": 1},
                    "visible_condition": {"type": "string", "enum": ALLOWED_CONDITION},
                    "confidence": {"type": "string", "enum": ALLOWED_CONFIDENCE},
                    "confidence_reason": {"type": "string"},
                    "source": {"type": "string"},
                    "notes": {"type": "string"},
                    "flags": {"type": "array", "items": {"type": "string"}},
                },
            },
        },
        "image_notes": {"type": "string"},
    },
}


def build_storage_unit_prompt(profile: dict[str, Any] | None = None) -> str:
    profile_name = (profile or {}).get("profile_name", "default")
    return "\n\n".join([
        f"Project profile: {profile_name}",
        ITEM_DETECTION_PROMPT,
        SELF_CHECK_PROMPT,
    ])


def coerce_vision_json(text: str) -> list[dict[str, Any]]:
    """Accept either {items:[...]} or a raw array from older prompts."""
    cleaned = (text or "").strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`").replace("json\n", "", 1).strip()
    data = json.loads(cleaned)
    if isinstance(data, dict):
        items = data.get("items", [])
    elif isinstance(data, list):
        items = data
    else:
        raise ValueError("Vision JSON must be an object with items or an array")
    if not isinstance(items, list):
        raise ValueError("Vision items must be a list")
    return items


def save_prompt_snapshot(path: Path, profile: dict[str, Any] | None = None) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(build_storage_unit_prompt(profile), encoding="utf-8")
    return path
