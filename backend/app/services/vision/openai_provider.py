from __future__ import annotations

import base64
import os
from pathlib import Path
from typing import Any

from app.services.vision.base import VisionProvider
from app.services.vision.prompts import SYSTEM_PROMPT, build_storage_unit_prompt, coerce_vision_json


class OpenAIVisionProvider(VisionProvider):
    provider_name = "openai"

    def __init__(self, model: str = "gpt-4o-mini", profile: dict[str, Any] | None = None):
        self.model = model
        self.profile = profile or {}

    async def detect_items(self, image_path: Path) -> list[dict]:
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY is not set. Use provider=mock for local dry runs.")
        try:
            from openai import AsyncOpenAI
        except ImportError as exc:
            raise RuntimeError("openai package is not installed") from exc

        image_b64 = base64.b64encode(image_path.read_bytes()).decode("utf-8")
        prompt = build_storage_unit_prompt(self.profile)
        client = AsyncOpenAI(api_key=api_key)

        response = await client.chat.completions.create(
            model=self.model,
            temperature=0,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_b64}"}},
                    ],
                },
            ],
        )
        text = response.choices[0].message.content or "{\"items\": []}"
        try:
            items = coerce_vision_json(text)
        except Exception as exc:
            raise RuntimeError(f"Vision response was not valid SimLay JSON: {text[:500]}") from exc
        return items
