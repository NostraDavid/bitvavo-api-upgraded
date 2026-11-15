"""Tests for HTTPClient transport layer."""

from __future__ import annotations

import hashlib
import hmac
import json
from io import BytesIO
from typing import TYPE_CHECKING
from unittest.mock import patch

import niquests as http
import pytest
from returns.result import Failure, Success

from bitvavo_api_upgraded.bitvavo import Bitvavo
from bitvavo_client.auth.rate_limit import RateLimitManager
from bitvavo_client.core.settings import BitvavoSettings
from bitvavo_client.transport.http import HTTPClient

if TYPE_CHECKING:  # pragma: no cover
    from collections.abc import Callable


def _response(
    status_code: int,
    *,
    headers: dict[str, str] | None = None,
    json_body: object = None,
) -> http.Response:
    response = http.Response()
    response.status_code = status_code
    response.headers.update(headers or {})
    response._content = json.dumps(json_body).encode()  # noqa: SLF001
    return response


def test_request_updates_rate_limiter(monkeypatch: pytest.MonkeyPatch) -> None:
    """HTTPClient.request should record weight usage for each call."""
    settings = BitvavoSettings(api_keys=[{"key": "k", "secret": "s"}])
    manager = RateLimitManager(settings.default_rate_limit, settings.rate_limit_buffer)
    client = HTTPClient(settings, manager)

    # Provide dummy HTTP response
    response = _response(200, json_body={})

    def fake_request(method: str, url: str, headers: dict[str, str], body: object) -> http.Response:
        return response

    monkeypatch.setattr(client, "_make_http_request", fake_request)

    start_remaining = manager.get_remaining(0)
    result = client.request("GET", "/test", weight=5)

    assert isinstance(result, Success)
    # Initial rate limit check consumes 1 weight in addition to the request weight
    assert manager.get_remaining(0) == start_remaining - 6


def test_initial_rate_limit_fetch(monkeypatch: pytest.MonkeyPatch) -> None:
    """Initial request should fetch rate limit before making the API call."""
    settings = BitvavoSettings(api_keys=[{"key": "k", "secret": "s"}])
    manager = RateLimitManager(settings.default_rate_limit, settings.rate_limit_buffer)
    client = HTTPClient(settings, manager)

    responses = [
        _response(200, headers={"bitvavo-ratelimit-remaining": "1000"}, json_body={}),
        _response(200, headers={"bitvavo-ratelimit-remaining": "995"}, json_body={}),
    ]
    called_urls: list[str] = []

    def fake_request(method: str, url: str, headers: dict[str, str], body: object) -> http.Response:
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
        _response(429, json_body={"error": {"code": 101}}),
        _response(200, headers={"bitvavo-ratelimit-remaining": "1000"}, json_body={}),
        _response(200, headers={"bitvavo-ratelimit-remaining": "995"}, json_body={}),
    ]
    called_urls: list[str] = []

    def fake_request(method: str, url: str, headers: dict[str, str], body: object) -> http.Response:
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
        _response(
            200,
            headers={
                "bitvavo-ratelimit-remaining": "40",
                "bitvavo-ratelimit-resetat": "60000",
            },
            json_body={},
        ),
        _response(200, headers={"bitvavo-ratelimit-remaining": "1000"}, json_body={}),
        _response(200, headers={"bitvavo-ratelimit-remaining": "995"}, json_body={}),
    ]
    called_urls: list[str] = []

    def fake_request(method: str, url: str, headers: dict[str, str], body: object) -> http.Response:
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

    response = _response(200, json_body={})
    monkeypatch.setattr(client, "_make_http_request", lambda m, u, h, b: response)

    result = client.request("GET", "/test")

    assert isinstance(result, Success)
    assert client.key_index == 1


def test_rotate_key_does_not_reset_when_budget_available(monkeypatch: pytest.MonkeyPatch) -> None:
    """Rotation should not reset key state if the key still has budget."""
    settings = BitvavoSettings(
        api_keys=[{"key": "k1", "secret": "s1"}, {"key": "k2", "secret": "s2"}],
    )
    manager = RateLimitManager(settings.default_rate_limit, settings.rate_limit_buffer)
    client = HTTPClient(settings, manager)

    manager.state[1]["remaining"] = 500
    manager.state[1]["resetAt"] = 0

    with patch.object(manager, "reset_key") as mock_reset:
        client._rotate_key()  # noqa: SLF001

    assert client.key_index == 1
    mock_reset.assert_not_called()


def test_rotate_key_resets_expired_key(monkeypatch: pytest.MonkeyPatch) -> None:
    """Rotation should reset key if its budget is exhausted and reset time passed."""
    settings = BitvavoSettings(
        api_keys=[{"key": "k1", "secret": "s1"}, {"key": "k2", "secret": "s2"}],
    )
    manager = RateLimitManager(settings.default_rate_limit, settings.rate_limit_buffer)
    client = HTTPClient(settings, manager)

    manager.state[1]["remaining"] = 0
    manager.state[1]["resetAt"] = 0

    with patch.object(manager, "reset_key") as mock_reset, patch("time.time", return_value=1):
        client._rotate_key()  # noqa: SLF001

    assert client.key_index == 1
    mock_reset.assert_called_once_with(1)


@pytest.mark.parametrize("legacy", [False, True])
@pytest.mark.parametrize("method", ["GET", "POST", "PUT", "DELETE"])
@pytest.mark.parametrize("status_code", [200, 307])
def test_native_requests(
    monkeypatch: pytest.MonkeyPatch,
    *,
    legacy: bool,
    method: str,
    status_code: int,
) -> None:
    requests: list[http.PreparedRequest] = []
    timeouts: list[object] = []

    def send(adapter: http.adapters.HTTPAdapter, request: http.PreparedRequest, **kwargs: object) -> http.Response:
        requests.append(request)
        timeouts.append(kwargs["timeout"])
        raw = http.packages.urllib3.HTTPResponse(
            body=BytesIO(b'{"result":"ok"}'),
            status=status_code,
            headers={"bitvavo-ratelimit-remaining": "999", "Location": "https://example.invalid/redirect"},
            preload_content=False,
        )
        return adapter.build_response(request, raw)

    monkeypatch.setattr(http.adapters.HTTPAdapter, "send", send)
    body = {"market": "BTC-EUR", "clientOrderId": "caf\u00e9"} if method in {"POST", "PUT"} else None
    if legacy:
        client = Bitvavo({"APIKEY": "k", "APISECRET": "s", "RESTURL": "https://example.invalid/v2"})
        result = client.private_request("/test", "", body, method)
        assert result == {"result": "ok"}
        assert len(requests) == 1
    else:
        settings = BitvavoSettings(api_keys=[{"key": "k", "secret": "s"}], rest_url="https://example.invalid/v2")
        modern_client = HTTPClient(settings, RateLimitManager(settings.default_rate_limit, settings.rate_limit_buffer))
        result = modern_client.request(method, "/test", body=body)
        assert isinstance(result, Success if status_code == 200 else Failure)
        assert len(requests) == 2
        assert requests[0].url == "https://example.invalid/v2/account"

    request = requests[-1]
    assert request.method == method
    assert request.url == "https://example.invalid/v2/test"
    assert timeouts[-1] == 10.0
    assert request.headers["bitvavo-access-key"] == "k"
    message = f"{request.headers['bitvavo-access-timestamp']}{method}/v2/test".encode()
    if body is not None:
        assert request.body == json.dumps(body, separators=(",", ":")).encode()
        assert request.headers["Content-Type"].split(";")[0] == "application/json"
        message += request.body
    else:
        assert request.body is None
    assert request.headers["bitvavo-access-signature"] == hmac.new(b"s", message, hashlib.sha256).hexdigest()


@pytest.mark.parametrize("exception_type", [http.exceptions.ConnectionError, http.exceptions.Timeout])
def test_native_transport_failure(
    monkeypatch: pytest.MonkeyPatch,
    exception_type: Callable[[str], http.exceptions.RequestException],
) -> None:
    error = exception_type("Transport failed")

    def send(adapter: object, request: http.PreparedRequest, **kwargs: object) -> http.Response:
        raise error

    monkeypatch.setattr(http.adapters.HTTPAdapter, "send", send)
    settings = BitvavoSettings(api_keys=[{"key": "k", "secret": "s"}])
    client = HTTPClient(settings, RateLimitManager(settings.default_rate_limit, settings.rate_limit_buffer))

    result = client.request("GET", "/test")

    assert isinstance(result, Failure)
    assert result.failure() is error


def test_legacy_public_request_uses_http(monkeypatch: pytest.MonkeyPatch) -> None:
    response = _response(200, headers={"bitvavo-ratelimit-remaining": "999"}, json_body={"time": 123})
    with patch.object(http, "get", return_value=response) as get:
        client = Bitvavo({"APIKEY": "k", "APISECRET": "s"})

        result = client.public_request("https://example.invalid/time")

    assert result == {"time": 123}
    assert get.call_args.args == ("https://example.invalid/time",)
    assert get.call_args.kwargs["timeout"] == 10.0
    assert get.call_args.kwargs["allow_redirects"] is False
