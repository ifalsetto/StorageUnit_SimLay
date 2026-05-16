from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from app.core.config import load_all_config
from app.services.market.ebay import EbayConnector

router = APIRouter(prefix="/api/connectors", tags=["connectors"])


@router.get("/ebay/status")
def ebay_status():
    connector = EbayConnector(load_all_config())
    status = connector.status()
    return {"connector": "ebay_api", "configured": status.configured, "reason": status.reason}


@router.get("/ebay/search-active")
async def ebay_search_active(q: str = Query(..., min_length=2), limit: int = Query(10, ge=1, le=50)):
    connector = EbayConnector(load_all_config())
    status = connector.status()
    if not status.configured:
        raise HTTPException(400, f"eBay API not configured: {status.reason}")
    try:
        return await connector.search_active(q, limit=limit)
    except Exception as exc:
        raise HTTPException(502, str(exc))
