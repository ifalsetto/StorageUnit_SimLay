import sqlite3

import pytest

from app.core.database import SCHEMA
from app.models.decision import DecisionInput
from app.services.practice_flow import build_simlay_practice_flow


def make_conn():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    conn.execute(
        """
        INSERT INTO runs(run_id, run_short, profile_name, profile_snapshot, status, errors, warnings)
        VALUES('run_1', 'R001', 'default', '{}', 'processed', '[]', '[]')
        """
    )
    return conn


def test_practice_flow_reuses_real_decision_and_does_not_fake_outcome():
    conn = make_conn()
    conn.execute(
        """
        INSERT INTO items(
            item_id, run_id, final_name, quantity, confidence, source,
            value_export, valuation_passed_gates
        )
        VALUES('item_1', 'run_1', 'Tool Chest', 1, 'Verified', 'User Visual', 600, 1)
        """
    )
    conn.execute(
        """
        INSERT INTO evidence(
            evidence_id, item_id, source_type, source_name, listing_type, price
        )
        VALUES('ev_1', 'item_1', 'market_comp', 'Sold Comp', 'sold', 625)
        """
    )

    flow = build_simlay_practice_flow(
        conn,
        'run_1',
        DecisionInput(
            current_bid=40,
            dump_fee_estimate=20,
            fuel_misc_estimate=20,
            minimum_profit_dollars=100,
            sell_through_pct=75,
        ),
    )

    assert flow.pattern == [
        'REAL INPUT',
        'FALSETECH PROCESS',
        'EVIDENCE',
        'DECISION',
        'ACTION',
        'RESULT',
    ]
    assert flow.capability == 'simlay.storage_unit_decision'
    assert flow.evidence['total_item_count'] == 1
    assert flow.evidence['priced_item_count'] == 1
    assert flow.evidence['evidence_record_count'] == 1
    assert flow.decision['safe_bid'] <= flow.decision['max_bid']
    assert flow.action['human_authorization_required'] is True
    assert flow.action['executed'] is False
    assert flow.result['executed'] is False
    assert flow.result['verified_outcome'] is False
    assert flow.result['proof_recorded'] is False
    assert flow.result['outcome_memory_persisted'] is False
    assert flow.provenance['decision_engine'] == 'app.services.decision_engine.compute_decision'


def test_practice_flow_requires_existing_run():
    conn = make_conn()

    with pytest.raises(ValueError, match='Run not found'):
        build_simlay_practice_flow(conn, 'missing', DecisionInput(current_bid=10))
