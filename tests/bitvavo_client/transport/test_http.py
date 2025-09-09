"""Tests for HTTPClient transport layer."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import patch

import httpx
from returns.result import Success

from bitvavo_client.auth.rate_limit import RateLimitManager
from bitvavo_client.core.settings import BitvavoSettings
from bitvavo_client.transport.http import HTTPClient

if TYPE_CHECKING:  # pragma: no cover
    import pytest


def test_request_updates_rate_limiter(monkeypatch: pytest.MonkeyPatch) -> None:
    """HTTPClient.request should record weight usage for each call."""
    settings = BitvavoSettings(api_keys=[{"key": "k", "secret": "s"}])
    manager = RateLimitManager(settings.default_rate_limit, settings.rate_limit_buffer)
    client = HTTPClient(settings, manager)

    # Provide dummy HTTP response
    response = httpx.Response(200, json={})

    def fake_request(method: str, url: str, headers: dict[str, str], body: object) -> httpx.Response:
        return response

    monkeypatch.setattr(client, "_make_http_request", fake_request)

    start_remaining = manager.get_remaining(0)
    result = client.request("GET", "/test", weight=5)

    assert isinstance(result, Success)
    # Initial rate limit check consumes 1 weight in addition to the request weight
    assert manager.get_remaining(0) == start_remaining - 6


def test_request_without_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    """HTTPClient.request should work without API key for public endpoints."""
    settings = BitvavoSettings()
    manager = RateLimitManager(settings.default_rate_limit, settings.rate_limit_buffer)
    client = HTTPClient(settings, manager)

    response = httpx.Response(200, json={})
    monkeypatch.setattr(client, "_make_http_request", lambda m, u, h, b: response)

    start_remaining = manager.get_remaining(-1)
    result = client.request("GET", "/test")

    assert isinstance(result, Success)
    assert manager.get_remaining(-1) == start_remaining - 1


def test_initial_rate_limit_fetch(monkeypatch: pytest.MonkeyPatch) -> None:
    """Initial request should fetch rate limit before making the API call."""
    settings = BitvavoSettings(api_keys=[{"key": "k", "secret": "s"}])
    manager = RateLimitManager(settings.default_rate_limit, settings.rate_limit_buffer)
    client = HTTPClient(settings, manager)

    responses = [
        httpx.Response(200, headers={"bitvavo-ratelimit-remaining": "1000"}, json={}),
        httpx.Response(200, headers={"bitvavo-ratelimit-remaining": "995"}, json={}),
    ]
    called_urls: list[str] = []

    def fake_request(method: str, url: str, headers: dict[str, str], body: object) -> httpx.Response:
        called_urls.append(url)
        return responses.pop(0)

    monkeypatch.setattr(client, "_make_http_request", fake_request)

    result = client.request("GET", "/test", weight=5)

    assert isinstance(result, Success)
    assert called_urls == [f"{settings.rest_url}/account", f"{settings.rest_url}/test"]
    assert manager.get_remaining(0) == 995


def test_initial_rate_limit_handles_429(monkeypatch: pytest.MonkeyPatch) -> None:
    """Client should sleep and retry when initial check returns 429 error 101."""
    settings = BitvavoSettings(api_keys=[{"key": "k", "secret": "s"}])
    manager = RateLimitManager(settings.default_rate_limit, settings.rate_limit_buffer)
    client = HTTPClient(settings, manager)

    responses = [
        httpx.Response(429, json={"error": {"code": 101}}),
        httpx.Response(200, headers={"bitvavo-ratelimit-remaining": "1000"}, json={}),
        httpx.Response(200, headers={"bitvavo-ratelimit-remaining": "995"}, json={}),
    ]
    called_urls: list[str] = []

    def fake_request(method: str, url: str, headers: dict[str, str], body: object) -> httpx.Response:
        called_urls.append(url)
        return responses.pop(0)

    monkeypatch.setattr(client, "_make_http_request", fake_request)

    with patch("time.sleep") as mock_sleep, patch("time.time", return_value=0):
        result = client.request("GET", "/test", weight=5)

    assert isinstance(result, Success)
    assert mock_sleep.called
    assert called_urls == [
        f"{settings.rest_url}/account",
        f"{settings.rest_url}/account",
        f"{settings.rest_url}/test",
    ]
    assert manager.get_remaining(0) == 995


def test_initial_rate_limit_below_threshold(monkeypatch: pytest.MonkeyPatch) -> None:
    """Client should sleep when initial remaining is below buffer threshold."""
    settings = BitvavoSettings(api_keys=[{"key": "k", "secret": "s"}], rate_limit_buffer=50)
    manager = RateLimitManager(settings.default_rate_limit, settings.rate_limit_buffer)
    client = HTTPClient(settings, manager)

    responses = [
        httpx.Response(
            200,
            headers={
                "bitvavo-ratelimit-remaining": "40",
                "bitvavo-ratelimit-resetat": "60000",
            },
            json={},
        ),
        httpx.Response(200, headers={"bitvavo-ratelimit-remaining": "1000"}, json={}),
        httpx.Response(200, headers={"bitvavo-ratelimit-remaining": "995"}, json={}),
    ]
    called_urls: list[str] = []

    def fake_request(method: str, url: str, headers: dict[str, str], body: object) -> httpx.Response:
        called_urls.append(url)
        return responses.pop(0)

    monkeypatch.setattr(client, "_make_http_request", fake_request)

    with patch("time.sleep") as mock_sleep, patch("time.time", return_value=0):
        result = client.request("GET", "/test", weight=5)

    assert isinstance(result, Success)
    assert mock_sleep.called
    assert called_urls == [
        f"{settings.rest_url}/account",
        f"{settings.rest_url}/account",
        f"{settings.rest_url}/test",
    ]
    assert manager.get_remaining(0) == 995


def test_request_rotates_keys_when_budget_exhausted(monkeypatch: pytest.MonkeyPatch) -> None:
    """Client should rotate to next API key when current key has no budget."""
    settings = BitvavoSettings(
        api_keys=[{"key": "k1", "secret": "s1"}, {"key": "k2", "secret": "s2"}],
    )
    manager = RateLimitManager(settings.default_rate_limit, settings.rate_limit_buffer)
    client = HTTPClient(settings, manager)

    # Skip initial rate limit call
    monkeypatch.setattr(client, "_ensure_rate_limit_initialized", lambda: None)

    def has_budget(idx: int, weight: int) -> bool:
        return idx == 1

    monkeypatch.setattr(manager, "has_budget", has_budget)
    monkeypatch.setattr(manager, "get_reset_at", lambda idx: 0)
    monkeypatch.setattr(manager, "sleep_until_reset", lambda idx: None)
    monkeypatch.setattr(manager, "reset_key", lambda idx: None)

    response = httpx.Response(200, json={})
    monkeypatch.setattr(client, "_make_http_request", lambda m, u, h, b: response)

    result = client.request("GET", "/test")

    assert isinstance(result, Success)
    assert client.key_index == 1
