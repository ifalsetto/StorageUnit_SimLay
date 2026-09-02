from __future__ import annotations

import sqlite3


MARKET_ITEM_COLUMNS: dict[str, str] = {
    "market_state": "TEXT NOT NULL DEFAULT 'NORMAL'",
    "market_adjusted_value": "REAL",
    "recommended_marketplace": "TEXT",
    "estimated_market_fee": "REAL",
    "expected_net": "REAL",
    "market_policy_as_of": "TEXT",
}


def _column_names(conn: sqlite3.Connection, table: str) -> set[str]:
    return {row["name"] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}


def ensure_market_schema(conn: sqlite3.Connection) -> None:
    """Idempotently extend older and current SimLay databases with market fields."""
    existing = _column_names(conn, "items")
    for name, definition in MARKET_ITEM_COLUMNS.items():
        if name not in existing:
            conn.execute(f"ALTER TABLE items ADD COLUMN {name} {definition}")
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_items_market_route ON items(recommended_marketplace, market_state, deleted_at)"
    )
