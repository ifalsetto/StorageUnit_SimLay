import sqlite3

from app.core.database import SCHEMA
from app.models.decision import DecisionInput, DecisionVerdict
from app.services.decision_engine import compute_decision


def make_conn():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    conn.execute(
        """
        INSERT INTO runs(run_id, run_short, profile_name, profile_snapshot, errors, warnings)
        VALUES('run_1', 'R001', 'default', '{}', '[]', '[]')
        """
    )
    return conn


def insert_item(conn, item_id, final_name, confidence, value_export, passed=1, quantity=1):
    conn.execute(
        """
        INSERT INTO items(
            item_id, run_id, final_name, quantity, confidence, source,
            value_export, valuation_passed_gates
        )
        VALUES(?, 'run_1', ?, ?, ?, 'User Visual', ?, ?)
        """,
        (item_id, final_name, quantity, confidence, value_export, passed),
    )


def test_profitable_run_generates_bid_ceiling():
    conn = make_conn()
    insert_item(conn, 'item_1', 'Tool Chest', 'Verified', 500, 1)
    insert_item(conn, 'item_2', 'Air Compressor', 'Inferred', 250, 1)

    result = compute_decision(
        conn,
        'run_1',
        DecisionInput(
            current_bid=40,
            dump_fee_estimate=25,
            fuel_misc_estimate=20,
            minimum_profit_dollars=100,
            sell_through_pct=75,
        ),
    )

    assert result.verdict in {DecisionVerdict.BUY, DecisionVerdict.MAYBE}
    assert result.max_bid > 0
    assert result.safe_bid <= result.max_bid
    assert result.projected_gross_resale == 750


def test_unknown_only_run_passes_and_warns():
    conn = make_conn()
    insert_item(conn, 'item_1', 'Mystery Box', 'Unknown', 1000, 1)

    result = compute_decision(conn, 'run_1', DecisionInput(current_bid=25))

    assert result.verdict == DecisionVerdict.PASS
    assert result.projected_gross_resale == 0
    assert result.priced_item_count == 0
    assert result.unknown_item_count == 1
    assert result.warning_count >= 1
