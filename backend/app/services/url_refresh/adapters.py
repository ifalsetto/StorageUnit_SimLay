from __future__ import annotations

import re
from urllib.parse import urlparse
from typing import Any

import httpx

from app.services.evidence_parser import parse_evidence_text
from app.services.market.ebay import EbayConnector
from app.services.url_refresh.base import RefreshResult


class BaseRefreshAdapter:
    def __init__(self, config: dict[str, Any]):
        self.config = config

    async def refresh(self, url: str) -> RefreshResult:
        raise NotImplementedError


class UnsupportedRefreshAdapter(BaseRefreshAdapter):
    async def refresh(self, url: str) -> RefreshResult:
        return RefreshResult(status="unsupported", exclusion_reason="domain_unsupported", notes="No compliant adapter is enabled for this domain")


class DisabledRefreshAdapter(BaseRefreshAdapter):
    def __init__(self, config: dict[str, Any], reason: str):
        super().__init__(config)
        self.reason = reason

    async def refresh(self, url: str) -> RefreshResult:
        return RefreshResult(status="blocked", exclusion_reason="refresh_disabled", notes=self.reason)


class EbayRefreshAdapter(BaseRefreshAdapter):
    async def refresh(self, url: str) -> RefreshResult:
        connector = EbayConnector(self.config)
        status = connector.status()
        # Official API preferred. Item-specific lookup can be added once item IDs are normalized.
        if status.configured:
            return RefreshResult(status="unsupported", exclusion_reason="ebay_item_lookup_not_mapped", notes="eBay API configured, but item ID extraction is not enabled yet")
        domain_cfg = self.config.get("connectors", {}).get("url_refresh", {}).get("domains", {}).get("ebay.com", {})
        if not domain_cfg.get("allow_public_html_parse", False):
            return RefreshResult(status="blocked", exclusion_reason=status.reason, notes="HTML parsing disabled; enable only if allowed for your use case")
        try:
            async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
                response = await client.get(url, headers={"User-Agent": "StorageUnitSimLay/1.0 (+local user evidence refresh)"})
            if response.status_code in {404, 410}:
                return RefreshResult(status="gone", exclusion_reason="http_gone")
            if response.status_code in {401, 403, 429}:
                return RefreshResult(status="blocked", exclusion_reason=f"http_{response.status_code}")
            response.raise_for_status()
            # Conservative text extraction: no login/CAPTCHA bypass. Parse visible text only.
            text = re.sub(r"<[^>]+>", " ", response.text)
            parsed = parse_evidence_text(text, platform_default="ebay")
            if parsed.price is None:
                return RefreshResult(status="changed", price=None, title=parsed.title, notes="No parseable price found", exclusion_reason="price_null")
            return RefreshResult(status="ok", price=parsed.price, title=parsed.title, sale_date=parsed.sale_date, notes="Refreshed from public page text")
        except Exception as exc:
            return RefreshResult(status="error", exclusion_reason="refresh_error", notes=str(exc))


def adapter_for_url(url: str, config: dict[str, Any]) -> BaseRefreshAdapter:
    host = urlparse(url or "").netloc.lower()
    if "ebay." in host or host.endswith("ebay.com"):
        return EbayRefreshAdapter(config)
    if "facebook." in host:
        return DisabledRefreshAdapter(config, "Facebook Marketplace is login-wall/partner-only for this MVP")
    return UnsupportedRefreshAdapter(config)
