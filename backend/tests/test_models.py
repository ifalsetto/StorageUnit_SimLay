from pydantic import ValidationError

from app.models.enums import Confidence
from app.models.item import ItemModel
from app.models.valuation import should_export_price
from app.schemas import ItemCreate, EvidenceCreate


def test_item_create_uses_guardrail_enums_and_strips_name():
    payload = ItemCreate(run_id="run_1", final_name="  Vintage Tool Box  ", confidence="Inferred")
    assert payload.final_name == "Vintage Tool Box"
    assert payload.confidence == "Inferred"
    assert payload.source == "User Visual"


def test_item_quantity_must_be_positive():
    try:
        ItemCreate(run_id="run_1", final_name="Chair", confidence="Verified", quantity=0)
    except ValidationError as exc:
        assert "greater than or equal to 1" in str(exc)
    else:
        raise AssertionError("quantity=0 should fail validation")


def test_unknown_confidence_cannot_export_price():
    item = {
        "confidence": Confidence.UNKNOWN.value,
        "valuation_passed_gates": 1,
        "value_export": 25.0,
    }
    assert should_export_price(item) is False


def test_verified_with_passed_gates_can_export_price():
    item = ItemModel(
        run_id="run_1",
        final_name="Chair",
        confidence="Verified",
        valuation_passed_gates=True,
        value_export=25.0,
    )
    assert item.can_export_price is True
    assert should_export_price(item.model_dump()) is True


def test_unverified_barcode_evidence_must_be_unpriced_observation():
    payload = EvidenceCreate(
        item_id="item_1", source_type="barcode", source_name="local_barcode_scan",
        listing_type="observation", price=None,
        notes="Unverified local barcode EAN_13: 1234567890123",
    )
    assert payload.source_type == "barcode"
    assert payload.listing_type == "observation"
    assert payload.price is None


def test_barcode_cannot_be_marked_as_sold_or_priced():
    for invalid in (
        {"listing_type": "sold", "price": None},
        {"listing_type": "observation", "price": 49.99},
    ):
        try:
            EvidenceCreate(
                item_id="item_1", source_type="barcode", notes="Unverified barcode observation",
                **invalid,
            )
        except ValidationError:
            pass
        else:
            raise AssertionError("Barcode must never count as a priced sale")


def test_barcode_requires_provenance_note():
    try:
        EvidenceCreate(
            item_id="item_1", source_type="barcode",
            listing_type="observation", price=None, notes=None,
        )
    except ValidationError:
        pass
    else:
        raise AssertionError("Barcode evidence must include provenance")
