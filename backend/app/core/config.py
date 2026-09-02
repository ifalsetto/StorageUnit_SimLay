import copy
import json
import os
from pathlib import Path
from typing import Any

import yaml

BASE_DIR = Path(__file__).resolve().parents[2]
CONFIG_DIR = BASE_DIR / "config"


def deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    result = copy.deepcopy(base)
    for key, value in (override or {}).items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = copy.deepcopy(value)
    return result


def load_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(path)
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(path)
    return json.loads(path.read_text(encoding="utf-8"))


def load_all_config(profile_name: str = "default") -> dict[str, Any]:
    config = {
        "app_config": load_yaml(CONFIG_DIR / "app_config.yaml"),
        "taxonomy": load_yaml(CONFIG_DIR / "taxonomy.yaml"),
        "confidence_rules": load_yaml(CONFIG_DIR / "confidence_rules.yaml"),
        "dedupe_rules": load_yaml(CONFIG_DIR / "dedupe_rules.yaml"),
        "valuation_rules": load_yaml(CONFIG_DIR / "valuation_rules.yaml"),
        "market_intelligence": load_yaml(CONFIG_DIR / "market_intelligence.yaml"),
        "connectors": load_yaml(CONFIG_DIR / "connectors.yaml"),
        "wix_schema": load_json(CONFIG_DIR / "wix_schema.json"),
    }
    profile_path = CONFIG_DIR / "profiles" / f"{profile_name}_profile.json"
    if not profile_path.exists():
        profile_path = CONFIG_DIR / "profiles" / "default_profile.json"
    profile = load_json(profile_path)
    config["profile"] = profile
    # A lightweight override layer for top-level named configs.
    for section, overrides in profile.get("overrides", {}).items():
        target_key = section if section in config else f"{section}_rules"
        if target_key in config and isinstance(config[target_key], dict):
            config[target_key] = deep_merge(config[target_key], overrides)
    return config


def resolve_storage_path(config: dict[str, Any], key: str) -> Path:
    rel = config["app_config"]["storage"][key]
    return BASE_DIR / rel


def require_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Required environment variable missing: {name}")
    return value
