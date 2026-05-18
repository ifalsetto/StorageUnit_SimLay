from __future__ import annotations

from typing import Any, Mapping, Optional

from pydantic import field_validator

from .base import SimLayModel
from .enums import Confidence, ValuationStatus


def _truthy_gate(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value == 1
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "passed"}
    return False


def should_export_price(item: Mapping[str, Any]) -> bool:
    confidence = str(item.get("confidence") or "Unknown").strip()
    if confidence == Confidence.UNKNOWN.value:
        return False
    if not _truthy_gate(item.get("valuation_passed_gates")):
        return False
    return item.get("value_export") is not None


class ValuationBand(SimLayModel):
    status: ValuationStatus = ValuationStatus.NOT_VALUED
    p25: Optional[float] = None
    p50: Optional[float] = None
    p75: Optional[float] = None
    value_export: Optional[float] = None
    value_source: Optional[str] = None
    valid_comp_count: int = 0
    warnings: list[str] = []

    @field_validator("p25", "p50", "p75", "value_export")
    @classmethod
    def nonnegative(cls, value: Optional[float]) -> Optional[float]:
        if value is not None and value < 0:
            raise ValueError("valuation band values cannot be negative")
        return value

    @property
    def passed(self) -> bool:
        return self.status == ValuationStatus.PASSED.value
