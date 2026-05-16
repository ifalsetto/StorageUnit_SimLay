import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "data" / "templates" / "Master_Inventory.csv"
OUTPUT = ROOT / "config" / "wix_schema.json"
POPULATED = ["handle", "fieldType", "Name", "Visible", "plainDescription", "media", "mediaAltText", "Brand", "Price", "inventory", "SKU (auto)"]


def generate_wix_schema(template_csv_path: Path = TEMPLATE, output_path: Path = OUTPUT):
    with template_csv_path.open("r", encoding="utf-8-sig", newline="") as f:
        headers = next(csv.reader(f))
    schema = {
        "schema_version": "1.0",
        "description": "Auto-generated from Wix CSV template headers. Do not hand-edit headers.",
        "template_source": str(template_csv_path.relative_to(ROOT)),
        "required_headers": headers,
        "field_mappings": {
            "handle": {"source": "wix_handle", "required": True},
            "fieldType": {"source": "constant", "value": "PRODUCT", "required": True},
            "Name": {"source": "final_name", "required": True},
            "Visible": {"source": "constant", "value": "TRUE", "required": True},
            "plainDescription": {"source": "template", "template": "Pre-owned {visible_condition}. {notes}", "fallback": "Pre-owned item. Honest condition. See photos for details.", "required": True},
            "media": {"source": "public_media_url", "required": False},
            "mediaAltText": {"source": "final_name", "required": False},
            "Brand": {"source": "brand", "required": False, "condition": "confidence == 'Verified'"},
            "Price": {"source": "value_export", "required": False, "format": "{:.0f}"},
            "inventory": {"source": "quantity", "required": False},
            "SKU (auto)": {"source": "wix_sku", "required": True}
        },
        "defaults": {h: "" for h in headers if h not in POPULATED}
    }
    output_path.write_text(json.dumps(schema, indent=2), encoding="utf-8")
    print(f"Generated {output_path} with {len(headers)} exact headers")

if __name__ == "__main__":
    generate_wix_schema()
