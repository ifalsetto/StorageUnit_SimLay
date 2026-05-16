import asyncio
from app.services.url_refresh.adapters import adapter_for_url


def test_facebook_refresh_fails_closed():
    adapter = adapter_for_url("https://facebook.com/marketplace/item/123", {})
    result = asyncio.run(adapter.refresh("https://facebook.com/marketplace/item/123"))
    assert result.status == "blocked"
    assert result.exclusion_reason == "refresh_disabled"


def test_unknown_domain_unsupported():
    adapter = adapter_for_url("https://example.com/item/123", {})
    result = asyncio.run(adapter.refresh("https://example.com/item/123"))
    assert result.status == "unsupported"
