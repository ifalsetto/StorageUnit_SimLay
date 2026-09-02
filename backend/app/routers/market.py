from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from app.core.config import load_all_config
from app.core.database import db_session, row_to_dict
from app.services.market.intelligence import estimate_marketplace_fee, estimate_routes, policy_status
from app.services.valuation import compute_item_valuation

router = APIRouter(prefix="/api/market", tags=["market"])


class MarketEstimateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    marketplace: str
    sale_price: float = Field(gt=0)
    shipping_charged_to_buyer: float = Field(default=0, ge=0)
    estimated_tax: float = Field(default=0, ge=0)
    category: Optional[str] = None


class RouteEstimateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    final_name: str = "Item"
    brand: Optional[str] = None
    category: Optional[str] = None
    subcategory: Optional[str] = None
    gross_value: float = Field(gt=0)
    shipping_cost: float = Field(default=0, ge=0)
    shipping_charged_to_buyer: float = Field(default=0, ge=0)
    estimated_tax: float = Field(default=0, ge=0)
    risk_allowance_pct: float = Field(default=0, ge=0, le=100)


@router.get("/policy")
def market_policy():
    config = load_all_config()
    return {
        "status": policy_status(config),
        "market_intelligence": config.get("market_intelligence", {}),
    }


@router.post("/estimate-fee")
def estimate_fee(payload: MarketEstimateRequest):
    config = load_all_config()
    try:
        return estimate_marketplace_fee(
            payload.marketplace,
            payload.sale_price,
            config,
            shipping_charged_to_buyer=payload.shipping_charged_to_buyer,
            estimated_tax=payload.estimated_tax,
            category_text=payload.category or "",
        )
    except ValueError as exc:
        raise HTTPException(422, str(exc))


@router.post("/estimate-routes")
def estimate_route_options(payload: RouteEstimateRequest):
    config = load_all_config()
    item = {
        "final_name": payload.final_name,
        "brand": payload.brand,
        "category": payload.category,
        "subcategory": payload.subcategory,
    }
    return estimate_routes(
        item,
        payload.gross_value,
        config,
        shipping_cost=payload.shipping_cost,
        shipping_charged_to_buyer=payload.shipping_charged_to_buyer,
        estimated_tax=payload.estimated_tax,
        risk_allowance_pct=payload.risk_allowance_pct,
    )


@router.post("/revalue/{item_id}")
def revalue_item(item_id: str):
    config = load_all_config()
    with db_session() as conn:
        item = row_to_dict(conn.execute("SELECT item_id FROM items WHERE item_id=?", (item_id,)).fetchone())
        if not item:
            raise HTTPException(404, "Item not found")
        valuation = compute_item_valuation(conn, item_id, config)
        updated = row_to_dict(conn.execute("SELECT * FROM items WHERE item_id=?", (item_id,)).fetchone())
    return {"valuation": valuation, "item": updated}
