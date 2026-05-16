from app.services.dedupe import dedupe_items, duplicate_score


def test_strong_dedupe_merges_same_item():
    items = [
        {"final_name": "RAGU Projector", "brand": "RAGU", "category": "Electronics", "confidence": "Verified", "detected_in_media": ["m1"]},
        {"final_name": "RAGU Projector", "brand": "RAGU", "category": "Electronics", "confidence": "Verified", "detected_in_media": ["m2"]},
    ]
    result = dedupe_items(items, threshold=0.90)
    assert len(result) == 1
    assert result[0]["detected_in_media"] == ["m1", "m2"]


def test_near_duplicate_is_flagged_not_silently_merged():
    items = [
        {"final_name": "Generic projector", "category": "Electronics", "confidence": "Inferred"},
        {"final_name": "Projector with missing remote", "category": "Electronics", "confidence": "Inferred"},
    ]
    result = dedupe_items(items, threshold=0.95)
    assert len(result) >= 1
    assert any("duplicate_suspect" in r.get("flags", []) for r in result)


def test_score_penalizes_conflicting_brands():
    a = {"final_name": "RAGU Projector", "brand": "RAGU", "category": "Electronics"}
    b = {"final_name": "RAGU Projector", "brand": "Epson", "category": "Electronics"}
    assert duplicate_score(a, b).score < 0.90
