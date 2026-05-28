from app.routers.ocr import OCRBox, build_item_seed


def test_ocr_seed_extracts_brand_and_model():
    boxes = [
        OCRBox(text="SONY", confidence=0.98, bounding_box={}),
        OCRBox(text="MODEL SS-U40A", confidence=0.94, bounding_box={}),
        OCRBox(text="6 OHMS", confidence=0.90, bounding_box={}),
    ]

    seed = build_item_seed("sony-speaker.jpg", "media_test", boxes)

    assert seed.brand_guess == "Sony"
    assert seed.model_guess == "SS-U40A"
    assert seed.candidate_name == "Sony SS-U40A"
    assert seed.status in {"ready_for_review", "needs_review"}


def test_ocr_seed_extracts_barcode():
    boxes = [
        OCRBox(text="KREG", confidence=0.98, bounding_box={}),
        OCRBox(text="KWS1000", confidence=0.96, bounding_box={}),
        OCRBox(text="UPC 647096805149", confidence=0.88, bounding_box={}),
    ]

    seed = build_item_seed("kreg-workbench.jpg", "media_test", boxes)

    assert seed.brand_guess == "Kreg"
    assert seed.barcode_guess == "647096805149"
    assert seed.simlay_usefulness_score >= 70
