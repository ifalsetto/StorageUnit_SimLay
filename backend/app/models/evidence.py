from __future__ import annotations

from typing import Optional

from pydantic import Field, field_validator

from .base import SimLayModel
from .enums import EvidenceSourceType, ListingType


class EvidenceModel(SimLayModel):
    evidence_id: Optional[str] = None
    item_id: str
    source_type: EvidenceSourceType = EvidenceSourceType.URL
    source_name: Optional[str] = "user_url"
    url: Optional[str] = None
    url_title: Optional[str] = None
    url_platform: Optional[str] = None
    screenshot_path: Optional[str] = None
    price: Optional[float] = Field(default=None, gt=0)
    currency: str = "USD"
    condition: Optional[str] = None
    sale_date: Optional[str] = None
    listing_type: ListingType = ListingType.SOLD
    is_active_listing: bool = False
    discounted_price: Optional[float] = None
    is_bundle: bool = False
    is_outlier: bool = False
    notes: Optional[str] = None
    last_refreshed_at: Optional[str] = None
    refresh_status: str = "never"
    included_in_valuation: bool = True
    exclusion_reason: Optional[str] = None

    @field_validator("currency")
    @classmethod
    def normalize_currency(cls, value: str) -> str:
        value = (value or "USD").strip().upper()
        if len(value) != 3:
            raise ValueError("currency must be a 3-letter code")
        return value

    @field_validator("discounted_price")
    @classmethod
    def discounted_price_nonnegative(cls, value: Optional[float]) -> Optional[float]:
        if value is not None and value <= 0:
            raise ValueError("discounted_price must be greater than zero when present")
        return value
