from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.models.enums import (
    Confidence,
    Condition,
    EvidenceSourceType,
    InventoryOwner,
    ItemAction,
    ListingType,
    TruthSource,
)


class ApiSchema(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        use_enum_values=True,
        validate_assignment=True,
    )


class CreateRunRequest(ApiSchema):
    profile_name: str = "default"
    media_type: str = Field(default="photos", pattern="^(photos|video)$")
    owner: InventoryOwner = InventoryOwner.UNASSIGNED


class ManualValueBandMixin:
    @model_validator(mode="after")
    def manual_value_band_is_ordered(self):
        low = getattr(self, "manual_value_low", None)
        expected = getattr(self, "manual_value_expected", None)
        high = getattr(self, "manual_value_high", None)
        if low is not None and high is not None and high < low:
            raise ValueError("manual_value_high must be greater than or equal to manual_value_low")
        if expected is not None and low is not None and expected < low:
            raise ValueError("manual_value_expected cannot be below manual_value_low")
        if expected is not None and high is not None and expected > high:
            raise ValueError("manual_value_expected cannot be above manual_value_high")
        return self


class ItemCreate(ManualValueBandMixin, ApiSchema):
    run_id: str
    final_name: str = Field(min_length=1)
    raw_name: Optional[str] = None
    brand: Optional[str] = None
    category: Optional[str] = None
    subcategory: Optional[str] = None
    quantity: int = Field(default=1, ge=1)
    visible_condition: Condition = Condition.UNKNOWN
    confidence: Confidence
    confidence_reason: Optional[str] = None
    source: TruthSource = TruthSource.USER_VISUAL
    notes: Optional[str] = None
    owner: InventoryOwner = InventoryOwner.UNASSIGNED
    item_action: ItemAction = ItemAction.UNASSIGNED
    manual_value_low: Optional[float] = Field(default=None, ge=0)
    manual_value_expected: Optional[float] = Field(default=None, ge=0)
    manual_value_high: Optional[float] = Field(default=None, ge=0)
    asking_price: Optional[float] = Field(default=None, ge=0)
    representative_image_id: Optional[str] = None

    @field_validator("final_name")
    @classmethod
    def final_name_required(cls, value: str) -> str:
        value = (value or "").strip()
        if not value:
            raise ValueError("final_name is required")
        return value


class ItemUpdate(ManualValueBandMixin, ApiSchema):
    final_name: Optional[str] = None
    brand: Optional[str] = None
    category: Optional[str] = None
    subcategory: Optional[str] = None
    quantity: Optional[int] = Field(default=None, ge=1)
    visible_condition: Optional[Condition] = None
    confidence: Optional[Confidence] = None
    confidence_reason: Optional[str] = None
    source: Optional[TruthSource] = None
    notes: Optional[str] = None
    owner: Optional[InventoryOwner] = None
    item_action: Optional[ItemAction] = None
    manual_value_low: Optional[float] = Field(default=None, ge=0)
    manual_value_expected: Optional[float] = Field(default=None, ge=0)
    manual_value_high: Optional[float] = Field(default=None, ge=0)
    asking_price: Optional[float] = Field(default=None, ge=0)
    representative_image_id: Optional[str] = None

    @field_validator("final_name")
    @classmethod
    def final_name_not_blank_when_present(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        value = value.strip()
        if not value:
            raise ValueError("final_name cannot be blank")
        return value


class ItemDuplicateRequest(ApiSchema):
    owner: Optional[InventoryOwner] = None


class EvidenceCreate(ApiSchema):
    item_id: str
    source_type: EvidenceSourceType = EvidenceSourceType.URL
    source_name: Optional[str] = "user_url"
    url: Optional[str] = None
    url_title: Optional[str] = None
    url_platform: Optional[str] = None
    price: Optional[float] = Field(default=None, gt=0)
    currency: str = "USD"
    condition: Optional[str] = None
    sale_date: Optional[str] = None
    listing_type: ListingType = ListingType.SOLD
    is_bundle: bool = False
    notes: Optional[str] = None

    @field_validator("currency")
    @classmethod
    def normalize_currency(cls, value: str) -> str:
        value = (value or "USD").strip().upper()
        if len(value) != 3:
            raise ValueError("currency must be a 3-letter code")
        return value


class EvidenceUrlRefreshRequest(ApiSchema):
    evidence_id: str


class ExportResponse(ApiSchema):
    export_id: str
    file_path: str
    row_count: int
    validation_passed: bool
