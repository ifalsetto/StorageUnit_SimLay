from __future__ import annotations

import base64
import os
import time
from dataclasses import dataclass
from typing import Any

import httpx

EBAY_TOKEN_URL = "https://api.ebay.com/identity/v1/oauth2/token"
EBAY_BROWSE_SEARCH_URL = "https://api.ebay.com/buy/browse/v1/item_summary/search"

@dataclass
class EbayStatus:
    configured: bool
    reason: str


class EbayConnector:
    """Official eBay API connector scaffold.

    This connector never claims sold-listing coverage. It only performs calls when
    credentials are present and the relevant feature is enabled in connectors.yaml.
    """

    def __init__(self, config: dict[str, Any]):
        self.config = config
        ebay_cfg = config.get("connectors", {}).get("market_connectors", {}).get("ebay_api", {})
        self.enabled = bool(ebay_cfg.get("enabled", False))
        self.client_id_env = ebay_cfg.get("client_id_env", "EBAY_CLIENT_ID")
        self.client_secret_env = ebay_cfg.get("client_secret_env", "EBAY_CLIENT_SECRET")
        self.marketplace_id = ebay_cfg.get("marketplace_id", "EBAY_US")
        self.scope = ebay_cfg.get("scope", "https://api.ebay.com/oauth/api_scope")
        self._token: str | None = None
        self._token_expiry = 0.0

    def status(self) -> EbayStatus:
        if not self.enabled:
            return EbayStatus(False, "disabled_in_connectors_yaml")
        if not os.getenv(self.client_id_env):
            return EbayStatus(False, f"missing_env:{self.client_id_env}")
        if not os.getenv(self.client_secret_env):
            return EbayStatus(False, f"missing_env:{self.client_secret_env}")
        return EbayStatus(True, "configured")

    async def access_token(self) -> str:
        status = self.status()
        if not status.configured:
            raise RuntimeError(f"eBay connector unavailable: {status.reason}")
        if self._token and time.time() < self._token_expiry - 60:
            return self._token
        client_id = os.getenv(self.client_id_env, "")
        client_secret = os.getenv(self.client_secret_env, "")
        basic = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                EBAY_TOKEN_URL,
                headers={"Authorization": f"Basic {basic}", "Content-Type": "application/x-www-form-urlencoded"},
                data={"grant_type": "client_credentials", "scope": self.scope},
            )
            response.raise_for_status()
            data = response.json()
        self._token = data["access_token"]
        self._token_expiry = time.time() + int(data.get("expires_in", 7200))
        return self._token

    async def search_active(self, query: str, limit: int = 10) -> dict[str, Any]:
        token = await self.access_token()
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.get(
                EBAY_BROWSE_SEARCH_URL,
                headers={"Authorization": f"Bearer {token}", "X-EBAY-C-MARKETPLACE-ID": self.marketplace_id},
                params={"q": query, "limit": max(1, min(limit, 50))},
            )
            response.raise_for_status()
            return response.json()

    async def search_sold(self, query: str, limit: int = 10) -> dict[str, Any]:
        raise NotImplementedError(
            "Sold-listing access is not enabled in this scaffold. Add an approved eBay data source before using sold comps."
        )
