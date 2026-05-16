from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

RefreshStatus = Literal["ok", "changed", "blocked", "gone", "unsupported", "error"]

@dataclass
class RefreshResult:
    status: RefreshStatus
    price: float | None = None
    title: str | None = None
    condition: str | None = None
    sale_date: str | None = None
    notes: str | None = None
    exclusion_reason: str | None = None
