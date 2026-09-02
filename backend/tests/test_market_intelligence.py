from app.core.config import load_all_config
from app.services.market.intelligence import (
    estimate_marketplace_fee,
    estimate_routes,
    evidence_weight,
    resolve_market_state,
    weighted_percentile,
)


def config():
    return load_all_config()


def test_weighted_percentile_respects_source_weight():
    assert weighted_percentile([(100, 1.0), (200, 0.5)], 50) == 100
    assert weighted_percentile([(100, 1.0), (200, 0.5)], 100) == 200


def test_exact_sold_comp_has_more_authority_than_active_listing():
    cfg = config()
    sold_weight, sold_meta = evidence_weight(
        {
            "listing_type": "sold",
            "source_name": "verified_exact_sold",
            "url_platform": "ebay",
        },
        cfg,
    )
    active_weight, active_meta = evidence_weight(
        {
            "listing_type": "active",
            "source_name": "user_url",
            "url_platform": "ebay",
        },
        cfg,
    )
    assert sold_weight == 1.0
    assert active_weight == 0.35
    assert sold_meta["source_key"] == "verified_exact_sold"
    assert active_meta["source_key"] == "active_listing"


def test_ebay_default_fee_estimate():
    result = estimate_marketplace_fee("ebay", 100, config())
    assert result["estimated_fee"] == 14.00
    assert result["fee_rule"].startswith("13.60_percent")


def test_poshmark_threshold_fee_estimate():
    cfg = config()
    assert estimate_marketplace_fee("poshmark", 10, cfg)["estimated_fee"] == 2.95
    assert estimate_marketplace_fee("poshmark", 20, cfg)["estimated_fee"] == 4.00


def test_tcgplayer_marketplace_standard_fee_estimate():
    result = estimate_marketplace_fee("tcgplayer", 100, config())
    assert result["estimated_fee"] == 13.55


def test_music_gear_routes_to_best_expected_net():
    item = {
        "final_name": "Used guitar amplifier",
        "category": "Music Gear",
        "subcategory": "Amplifier",
    }
    result = estimate_routes(item, 100, config())
    assert result["recommended"]["marketplace"] == "reverb"
    assert result["recommended"]["expected_net"] == 91.32


def test_generic_sneaker_signal_softens_value_temporarily():
    state = resolve_market_state(
        {"final_name": "General release sneaker", "category": "Shoes"},
        config(),
    )
    assert state["state"] == "SOFTENING"
    assert state["multiplier"] == 0.92
