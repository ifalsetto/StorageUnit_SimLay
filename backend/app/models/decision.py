from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import Field

from .base import SimLayModel


class DecisionVerdict(str, Enum):
    BUY = "Buy"
    MAYBE = "Maybe"
    PASS = "Pass"


class DecisionInput(SimLayModel):
    current_bid: float = Field(default=0, ge=0)
    buyer_premium_pct: float = Field(default=0, ge=0, le=100)
    tax_rate_pct: float = Field(default=0, ge=0, le=100)
    unit_size_sqft: float = Field(default=100, gt=0)
    packed_to_ceiling: bool = False
    helpers: int = Field(default=0, ge=0)
    vehicle_loads_estimate: float = Field(default=1, ge=0)
    labor_rate_per_hour: float = Field(default=25, ge=0)
    labor_hours_override: Optional[float] = Field(default=None, ge=0)
    dump_fee_estimate: float = Field(default=0, ge=0)
    fuel_misc_estimate: float = Field(default=25, ge=0)
    selling_fee_pct: float = Field(default=13, ge=0, le=100)
    sell_through_pct: float = Field(default=70, ge=0, le=100)
    risk_buffer_pct: float = Field(default=20, ge=0, le=100)
    minimum_profit_dollars: float = Field(default=100, ge=0)
    target_roi_pct: float = Field(default=35, ge=0)


class DecisionResult(SimLayModel):
    run_id: str
    verdict: DecisionVerdict
    safe_bid: float
    max_bid: float
    current_bid: float
    projected_gross_resale: float
    projected_sell_through_cash: float
    estimated_total_cost: float
    estimated_profit: float
    estimated_roi_pct: float
    labor_hours: float
    labor_cost: float
    dump_fee_estimate: float
    risk_buffer: float
    unknown_item_count: int
    priced_item_count: int
    total_item_count: int
    warning_count: int
    warnings: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
