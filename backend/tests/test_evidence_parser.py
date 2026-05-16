from app.services.evidence_parser import parse_evidence_text


def test_parse_sold_ebay_text():
    parsed = parse_evidence_text("eBay SOLD RAGU Projector $32.00 Sold Feb 3, 2026 Similar model tested working")
    assert parsed.price == 32.00
    assert parsed.platform == "ebay"
    assert parsed.listing_type == "sold"
    assert parsed.sale_date == "2026-02-03"


def test_parse_missing_price_is_allowed():
    parsed = parse_evidence_text("Facebook Marketplace listing blocked by login wall")
    assert parsed.price is None
    assert "price_not_found" in parsed.warnings
