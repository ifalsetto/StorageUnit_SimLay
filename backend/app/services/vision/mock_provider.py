from pathlib import Path
from app.services.vision.base import VisionProvider


class MockVisionProvider(VisionProvider):
    provider_name = "mock"

    async def detect_items(self, image_path: Path) -> list[dict]:
        return [{
            "raw_name": image_path.stem.replace("_", " ").replace("-", " ") or "Unidentified item",
            "final_name": image_path.stem.replace("_", " ").replace("-", " ") or "Unidentified item",
            "quantity": 1,
            "visible_condition": "Unknown",
            "confidence": "Unknown",
            "confidence_reason": "Mock provider used. No real visual verification performed.",
            "source": "Unknown",
            "notes": "Replace mock provider with OpenAI Vision for actual extraction."
        }]
