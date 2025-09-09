"""Tests for HTTPClient transport layer."""

from __future__ import annotations

import httpx
import pytest
from returns.result import Success

from bitvavo_client.auth.rate_limit import RateLimitManager
from bitvavo_client.core.settings import BitvavoSettings
from bitvavo_client.transport.http import HTTPClient


def test_request_updates_rate_limiter(monkeypatch) -> None:
    """HTTPClient.request should record weight usage for each call."""
    settings = BitvavoSettings()
    manager = RateLimitManager(settings.default_rate_limit, settings.rate_limit_buffer)
    client = HTTPClient(settings, manager)
    client.configure_key("k", "s", 0)

    # Provide dummy HTTP response
    response = httpx.Response(200, json={})

    def fake_request(method: str, url: str, headers: dict[str, str], body):
        return response

    monkeypatch.setattr(client, "_make_http_request", fake_request)

    start_remaining = manager.get_remaining(0)
    result = client.request("GET", "/test", weight=5)

    assert isinstance(result, Success)
    assert manager.get_remaining(0) == start_remaining - 5


def test_request_requires_api_key() -> None:
    """HTTPClient.request should raise if no API key configured."""
    settings = BitvavoSettings()
    manager = RateLimitManager(settings.default_rate_limit, settings.rate_limit_buffer)
    client = HTTPClient(settings, manager)

    with pytest.raises(RuntimeError, match="API key and secret must be configured"):
        client.request("GET", "/test")
