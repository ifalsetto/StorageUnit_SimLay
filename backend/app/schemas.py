from typing import Optional, Literal
from pydantic import BaseModel, Field, HttpUrl, field_validator

Confidence = Literal["Verified", "Inferred", "Unknown"]
Condition = Literal["New", "Like New", "Used", "Fair", "Parts", "Unknown"]
ListingType = Literal["sold", "active", "auction_ended"]

class CreateRunRequest(BaseModel):
    profile_name: str = "default"
    media_type: Literal["photos", "video"] = "photos"

class ItemCreate(BaseModel):
    run_id: str
    final_name: str = Field(min_length=1)
    raw_name: Optional[str] = None
    brand: Optional[str] = None
    category: Optional[str] = None
    subcategory: Optional[str] = None
    quantity: int = 1
    visible_condition: Condition = "Unknown"
    confidence: Confidence
    confidence_reason: Optional[str] = None
    source: str = "User Visual"
    notes: Optional[str] = None
    representative_image_id: Optional[str] = None

class ItemUpdate(BaseModel):
    final_name: Optional[str] = None
    brand: Optional[str] = None
    category: Optional[str] = None
    subcategory: Optional[str] = None
    quantity: Optional[int] = None
    visible_condition: Optional[Condition] = None
    confidence: Optional[Confidence] = None
    confidence_reason: Optional[str] = None
    notes: Optional[str] = None

class EvidenceCreate(BaseModel):
    item_id: str
    source_type: Literal["api", "url", "screenshot", "library", "manual_url"] = "url"
    source_name: Optional[str] = "user_url"
    url: Optional[str] = None
    url_title: Optional[str] = None
    url_platform: Optional[str] = None
    price: Optional[float] = None
    currency: str = "USD"
    condition: Optional[str] = None
    sale_date: Optional[str] = None
    listing_type: ListingType = "sold"
    is_bundle: bool = False
    notes: Optional[str] = None

    @field_validator("price")
    @classmethod
    def price_nonnegative(cls, v):
        if v is not None and v <= 0:
            raise ValueError("price must be greater than zero when present")
        return v

class EvidenceUrlRefreshRequest(BaseModel):
    evidence_id: str

class ExportResponse(BaseModel):
    export_id: str
    file_path: str
    row_count: int
    validation_passed: bool
