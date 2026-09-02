from __future__ import annotations

import math
from datetime import date, datetime, timezone
from typing import Any


def _slug(value: Any) -> str:
    return "_".join(str(value or "").strip().lower().replace("-", " ").split())


def _text(*values: Any) -> str:
    return " ".join(str(value or "").strip().lower() for value in values if value is not None)


def _parse_date(value: Any) -> date | None:
    if not value:
        return None
    raw = str(value).strip()
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00")).date()
    except ValueError:
        try:
            return date.fromisoformat(raw[:10])
        except ValueError:
            return None


def policy(config: dict[str, Any]) -> dict[str, Any]:
    return config.get("market_intelligence", {}) or {}


def policy_status(config: dict[str, Any], *, stale_after_days: int = 45) -> dict[str, Any]:
    cfg = policy(config)
    as_of = _parse_date(cfg.get("policy_as_of"))
    today = datetime.now(timezone.utc).date()
    age_days = (today - as_of).days if as_of else None
    return {
        "policy_as_of": cfg.get("policy_as_of"),
        "age_days": age_days,
        "stale": age_days is None or age_days > stale_after_days,
    }


def evidence_weight(evidence: dict[str, Any], config: dict[str, Any]) -> tuple[float, dict[str, Any]]:
    """Return transparent authority/freshness weight for one saved comp."""
    cfg = policy(config)
    authority = cfg.get("source_authority", {})
    listing_type = _slug(evidence.get("listing_type"))
    source_name = _slug(evidence.get("source_name"))
    platform = _slug(evidence.get("url_platform"))
    notes_text = _text(evidence.get("notes"), evidence.get("url_title"), evidence.get("source_name"))

    key = None
    if listing_type == "active" or bool(evidence.get("is_active_listing")):
        key = "active_listing"
    elif "retail" in source_name or "msrp" in source_name:
        key = "retail_msrp"
    elif platform == "ebay" and ("product research" in notes_text or "terapeak" in notes_text):
        key = "ebay_product_research"
    elif "accepted offer" in notes_text or "best offer" in notes_text:
        key = "accepted_offer"
    else:
        for candidate in authority:
            if candidate in {"sold_default", "active_listing", "retail_msrp"}:
                continue
            if candidate and (candidate in source_name or candidate == platform):
                key = candidate
                break
    if key is None:
        key = "sold_default" if listing_type != "active" else "active_listing"

    authority_weight = float(authority.get(key, authority.get("sold_default", 0.80)))
    freshness_weight = 1.0
    sale_date = _parse_date(evidence.get("sale_date"))
    if sale_date:
        age_days = max(0, (datetime.now(timezone.utc).date() - sale_date).days)
        freshness = cfg.get("freshness", {})
        half_life = max(1.0, float(freshness.get("half_life_days", 120)))
        minimum = min(1.0, max(0.0, float(freshness.get("minimum_weight", 0.50))))
        freshness_weight = max(minimum, math.pow(0.5, age_days / half_life))
    else:
        age_days = None

    final = max(0.0, min(1.0, authority_weight * freshness_weight))
    return final, {
        "source_key": key,
        "authority_weight": round(authority_weight, 4),
        "freshness_weight": round(freshness_weight, 4),
        "sale_age_days": age_days,
        "weight": round(final, 4),
    }


def weighted_percentile(weighted_values: list[tuple[float, float]], percentile: float) -> float | None:
    clean = sorted((float(value), max(0.0, float(weight))) for value, weight in weighted_values if weight > 0)
    if not clean:
        return None
    target = max(0.0, min(100.0, float(percentile))) / 100.0 * sum(weight for _, weight in clean)
    cumulative = 0.0
    for value, weight in clean:
        cumulative += weight
        if cumulative >= target:
            return value
    return clean[-1][0]


def resolve_market_state(item: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
    cfg = policy(config).get("market_state", {})
    default_state = str(cfg.get("default", "NORMAL")).upper()
    state = default_state
    signal_name = None
    today = datetime.now(timezone.utc).date()
    haystack = _text(
        item.get("final_name"),
        item.get("raw_name"),
        item.get("brand"),
        item.get("category"),
        item.get("subcategory"),
        item.get("notes"),
    )
    for signal in cfg.get("signals", []) or []:
        expires = _parse_date(signal.get("expires_at"))
        if expires and today > expires:
            continue
        terms = [str(term).strip().lower() for term in signal.get("terms", []) if str(term).strip()]
        if any(term in haystack for term in terms):
            state = str(signal.get("state", default_state)).upper()
            signal_name = signal.get("name")
            break
    multiplier = float((cfg.get("multipliers", {}) or {}).get(state, 1.0))
    return {"state": state, "multiplier": multiplier, "signal": signal_name}


def _category_percent(platform_cfg: dict[str, Any], category_text: str) -> tuple[float, str | None]:
    default_pct = float((platform_cfg.get("default", {}) or {}).get("percent", 0.0))
    haystack = str(category_text or "").lower()
    matches: list[tuple[int, float, str]] = []
    for rule in platform_cfg.get("category_rules", []) or []:
        for term in rule.get("terms", []) or []:
            term_text = str(term).strip().lower()
            if term_text and term_text in haystack:
                matches.append((len(term_text), float(rule.get("percent", default_pct)), term_text))
    if not matches:
        return default_pct, None
    matches.sort(key=lambda row: row[0], reverse=True)
    _, pct, term = matches[0]
    return pct, term


def estimate_marketplace_fee(
    marketplace: str,
    sale_price: float,
    config: dict[str, Any],
    *,
    shipping_charged_to_buyer: float = 0.0,
    estimated_tax: float = 0.0,
    category_text: str = "",
) -> dict[str, Any]:
    cfg = policy(config)
    platforms = cfg.get("marketplaces", {}) or {}
    key = _slug(marketplace)
    platform_cfg = platforms.get(key)
    if not platform_cfg or not platform_cfg.get("enabled", False):
        raise ValueError(f"Marketplace is not enabled in market policy: {marketplace}")

    price = max(0.0, float(sale_price))
    shipping = max(0.0, float(shipping_charged_to_buyer))
    tax = max(0.0, float(estimated_tax))
    fee_model = platform_cfg.get("fee_model", "percent_fixed")
    warnings: list[str] = []

    if fee_model == "poshmark_us":
        fee = 2.95 if price < 15.0 else price * 0.20
        base = price
        applied = "flat_2.95_under_15" if price < 15.0 else "20_percent"
    elif fee_model == "reverb_us":
        default = platform_cfg.get("default", {}) or {}
        selling_base = price + shipping
        processing_base = price + shipping + tax
        fee = selling_base * float(default.get("selling_percent", 5.0)) / 100.0
        fee += processing_base * float(default.get("processing_percent", 3.19)) / 100.0
        fee += float(default.get("processing_fixed", 0.49))
        base = processing_base
        applied = "5.00_selling_plus_3.19_processing"
        if tax <= 0:
            warnings.append("Tax was not supplied; Reverb processing estimate excludes buyer tax.")
    elif fee_model == "tcgplayer_marketplace_standard":
        default = platform_cfg.get("default", {}) or {}
        commission_base = price + shipping
        commission = min(
            commission_base * float(default.get("commission_percent", 10.75)) / 100.0,
            float(default.get("commission_cap_per_item", 75.0)),
        )
        transaction_base = price + shipping + tax
        transaction = transaction_base * float(default.get("transaction_percent", 2.5)) / 100.0
        transaction += float(default.get("transaction_fixed", 0.30))
        fee = commission + transaction
        base = transaction_base
        applied = "marketplace_standard"
        if tax <= 0:
            warnings.append("Tax was not supplied; TCGplayer processing estimate excludes buyer tax.")
    else:
        default = platform_cfg.get("default", {}) or {}
        pct, matched_term = _category_percent(platform_cfg, category_text)
        base = price + shipping
        if key == "ebay":
            base += tax
            if tax <= 0:
                warnings.append("Tax was not supplied; eBay fee estimate may be slightly low.")
        fee = base * pct / 100.0
        if "fixed" in default:
            fee += float(default.get("fixed", 0.0))
        elif price <= 10:
            fee += float(default.get("fixed_10_or_less", 0.0))
        else:
            fee += float(default.get("fixed_over_10", 0.0))
        applied = f"{pct:.2f}_percent"
        if matched_term:
            applied += f":{matched_term}"
        elif platform_cfg.get("category_rules"):
            warnings.append("No category-specific fee rule matched; platform default was used.")

    return {
        "marketplace": key,
        "sale_price": round(price, 2),
        "fee_base": round(base, 2),
        "estimated_fee": round(max(0.0, fee), 2),
        "fee_rule": applied,
        "warnings": warnings,
        "policy_as_of": cfg.get("policy_as_of"),
    }


def eligible_marketplaces(item: dict[str, Any], config: dict[str, Any]) -> list[str]:
    cfg = policy(config)
    platforms = cfg.get("marketplaces", {}) or {}
    routing = cfg.get("routing", {}) or {}
    haystack = _text(item.get("final_name"), item.get("brand"), item.get("category"), item.get("subcategory"))
    selected: list[str] = []

    for name in routing.get("include_general_markets", ["ebay", "mercari"]):
        platform_cfg = platforms.get(name, {}) or {}
        if platform_cfg.get("enabled", False) and platform_cfg.get("auto_route", False):
            selected.append(name)

    for name, platform_cfg in platforms.items():
        if name in selected or not platform_cfg.get("enabled", False) or not platform_cfg.get("auto_route", False):
            continue
        terms = [str(term).strip().lower() for term in platform_cfg.get("category_terms", []) if str(term).strip()]
        if terms and any(term in haystack for term in terms):
            selected.append(name)

    return selected


def estimate_routes(
    item: dict[str, Any],
    gross_value: float,
    config: dict[str, Any],
    *,
    shipping_cost: float | None = None,
    shipping_charged_to_buyer: float = 0.0,
    estimated_tax: float = 0.0,
    risk_allowance_pct: float | None = None,
) -> dict[str, Any]:
    cfg = policy(config)
    routing = cfg.get("routing", {}) or {}
    gross = max(0.0, float(gross_value))
    seller_shipping = max(0.0, float(
        routing.get("shipping_cost_default", 0.0) if shipping_cost is None else shipping_cost
    ))
    risk_pct = max(0.0, float(
        routing.get("risk_allowance_pct_default", 0.0) if risk_allowance_pct is None else risk_allowance_pct
    ))
    risk = gross * risk_pct / 100.0
    category_text = _text(item.get("category"), item.get("subcategory"), item.get("final_name"))
    routes: list[dict[str, Any]] = []
    for marketplace in eligible_marketplaces(item, config):
        fee = estimate_marketplace_fee(
            marketplace,
            gross,
            config,
            shipping_charged_to_buyer=shipping_charged_to_buyer,
            estimated_tax=estimated_tax,
            category_text=category_text,
        )
        expected_net = gross - fee["estimated_fee"] - seller_shipping - risk
        routes.append({
            **fee,
            "seller_shipping_cost": round(seller_shipping, 2),
            "risk_allowance": round(risk, 2),
            "expected_net": round(expected_net, 2),
        })

    positive = [route for route in routes if route["expected_net"] > 0]
    recommendation = max(positive or routes, key=lambda route: route["expected_net"], default=None)
    return {
        "gross_value": round(gross, 2),
        "routes": sorted(routes, key=lambda route: route["expected_net"], reverse=True),
        "recommended": recommendation,
        "policy": policy_status(config),
    }
