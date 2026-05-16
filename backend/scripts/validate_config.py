from pathlib import Path
import json
import sys
import yaml

ROOT = Path(__file__).resolve().parents[1]
REQUIRED = [
    "config/app_config.yaml",
    "config/wix_schema.json",
    "config/taxonomy.yaml",
    "config/confidence_rules.yaml",
    "config/dedupe_rules.yaml",
    "config/valuation_rules.yaml",
    "config/connectors.yaml",
    "config/profiles/default_profile.json",
]

def main():
    errors = []
    for rel in REQUIRED:
        path = ROOT / rel
        if not path.exists():
            errors.append(f"missing: {rel}")
            continue
        try:
            if path.suffix in {".yaml", ".yml"}:
                yaml.safe_load(path.read_text(encoding="utf-8"))
            else:
                json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            errors.append(f"invalid {rel}: {exc}")
    schema = json.loads((ROOT / "config/wix_schema.json").read_text(encoding="utf-8"))
    headers = schema.get("required_headers", [])
    if not headers:
        errors.append("wix_schema.json required_headers is empty")
    for required in ["handle", "fieldType", "Name", "Visible", "plainDescription", "SKU (auto)"]:
        if required not in headers:
            errors.append(f"Wix header missing: {required}")
    if errors:
        print("CONFIG INVALID")
        for e in errors:
            print("-", e)
        raise SystemExit(1)
    print("CONFIG VALID")

if __name__ == "__main__":
    main()
