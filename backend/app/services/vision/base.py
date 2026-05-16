from abc import ABC, abstractmethod
from pathlib import Path


class VisionProvider(ABC):
    provider_name: str

    @abstractmethod
    async def detect_items(self, image_path: Path) -> list[dict]:
        """Return raw detected item dictionaries. Must never guess beyond visual evidence."""
        raise NotImplementedError
