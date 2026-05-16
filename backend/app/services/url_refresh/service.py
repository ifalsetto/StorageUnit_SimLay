from __future__ import annotations

from app.services.url_refresh.adapters import adapter_for_url
from app.services.valuation import compute_item_valuation


async def refresh_evidence_url(conn, evidence_id: str, config: dict) -> dict:
    ev = conn.execute("SELECT * FROM evidence WHERE evidence_id=?", (evidence_id,)).fetchone()
    if not ev:
        raise ValueError(f"Evidence not found: {evidence_id}")
    ev = dict(ev)
    url = ev.get("url")
    if not url:
        conn.execute(
            "UPDATE evidence SET refresh_status='blocked', included_in_valuation=0, exclusion_reason='no_url', last_refreshed_at=CURRENT_TIMESTAMP WHERE evidence_id=?",
            (evidence_id,),
        )
        return {"evidence_id": evidence_id, "status": "blocked", "reason": "no_url"}
    result = await adapter_for_url(url, config).refresh(url)
    included = 1 if result.status in {"ok", "changed"} and result.price is not None else 0
    exclusion = None if included else (result.exclusion_reason or f"refresh_{result.status}")
    conn.execute(
        """
        UPDATE evidence SET refresh_status=?, price=?, url_title=COALESCE(?, url_title), condition=COALESCE(?, condition),
        sale_date=COALESCE(?, sale_date), notes=COALESCE(?, notes), included_in_valuation=?, exclusion_reason=?,
        last_refreshed_at=CURRENT_TIMESTAMP WHERE evidence_id=?
        """,
        (result.status, result.price, result.title, result.condition, result.sale_date, result.notes, included, exclusion, evidence_id),
    )
    compute_item_valuation(conn, ev["item_id"], config)
    return {"evidence_id": evidence_id, "status": result.status, "price": result.price, "exclusion_reason": exclusion, "notes": result.notes}
