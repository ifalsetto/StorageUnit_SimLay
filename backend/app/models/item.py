from __future__ import annotations

from typing import Any, Optional

from pydantic import Field, field_validator

from .base import SimLayModel
from .enums import Confidence, Condition, TruthSource


class ItemModel(SimLayModel):
    item_id: Optional[str] = None
    run_id: str
    raw_name: Optional[str] = None
    final_name: str = Field(min_length=1)
    normalized_name: Optional[str] = None
    brand: Optional[str] = None
    category: Optional[str] = None
    subcategory: Optional[str] = None
    quantity: int = Field(default=1, ge=1)
    visible_condition: Condition = Condition.UNKNOWN
    confidence: Confidence
    confidence_reason: Optional[str] = None
    source: TruthSource = TruthSource.USER_VISUAL
    notes: Optional[str] = None
    representative_image_id: Optional[str] = None
    flag_unknown: bool = False
    flag_duplicate_suspect: bool = False
    flag_missing_comps: bool = False
    flag_high_variance: bool = False
    flag_possible_collectible: bool = False
    sort_tier: int = 99
    sort_order: int = 999
    value_p25: Optional[float] = None
    value_p50: Optional[float] = None
    value_p75: Optional[float] = None
    value_export: Optional[float] = None
    value_source: Optional[str] = None
    valuation_passed_gates: bool = False
    wix_handle: Optional[str] = None
    wix_sku: Optional[str] = None
    wix_exported: bool = False

    @field_validator("final_name")
    @classmethod
    def final_name_required(cls, value: str) -> str:
        value = (value or "").strip()
        if not value:
            raise ValueError("final_name is required")
        return value

    @field_validator("value_p25", "value_p50", "value_p75", "value_export")
    @classmethod
    def valuation_values_nonnegative(cls, value: Optional[float]) -> Optional[float]:
        if value is not None and value < 0:
            raise ValueError("valuation values cannot be negative")
        return value

    @property
    def is_unknown(self) -> bool:
        return self.confidence == Confidence.UNKNOWN.value

    @property
    def can_export_price(self) -> bool:
        return bool(self.value_export is not None and self.valuation_passed_gates and not self.is_unknown)

    @classmethod
    def from_db_row(cls, row: dict[str, Any]) -> "ItemModel":
        data = dict(row)
        for key in (
            "flag_unknown",
            "flag_duplicate_suspect",
            "flag_missing_comps",
            "flag_high_variance",
            "flag_possible_collectible",
            "valuation_passed_gates",
            "wix_exported",
        ):
            if key in data:
                data[key] = bool(data[key])
        return cls(**data)
