import json
from app.services.vision.prompts import build_storage_unit_prompt, coerce_vision_json


def test_prompt_contains_truth_rules():
    prompt = build_storage_unit_prompt({"profile_name": "test"})
    assert "Do not invent brands" in prompt
    assert "Verified" in prompt and "Inferred" in prompt and "Unknown" in prompt
    assert "Do not estimate price" in prompt


def test_coerce_vision_json_accepts_object():
    data = {"items": [{"final_name": "Generic projector"}], "image_notes": "ok"}
    assert coerce_vision_json(json.dumps(data))[0]["final_name"] == "Generic projector"
