"""Smoke-test the real OpenAI Vision prompt against a local image.

Usage:
  set OPENAI_API_KEY=...
  python scripts/test_openai_vision_prompt.py path/to/storage_unit_photo.jpg

This script does not write inventory records. It only verifies that the prompt returns
parseable SimLay item JSON.
"""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.core.config import load_all_config
from app.services.vision.openai_provider import OpenAIVisionProvider


async def main() -> int:
    if len(sys.argv) < 2:
        print("Usage: python scripts/test_openai_vision_prompt.py <image_path>")
        return 2
    image_path = Path(sys.argv[1])
    if not image_path.exists():
        print(f"Image not found: {image_path}")
        return 2
    config = load_all_config()
    model = config["connectors"].get("vision_providers", {}).get("openai", {}).get("model", "gpt-4o-mini")
    provider = OpenAIVisionProvider(model=model, profile=config.get("profile", {}))
    items = await provider.detect_items(image_path)
    print(json.dumps({"item_count": len(items), "items": items}, indent=2))
    return 0

if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
