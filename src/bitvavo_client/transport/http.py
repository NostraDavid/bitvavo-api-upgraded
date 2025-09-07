"""HTTP client for Bitvavo API."""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, Any

import httpx
from returns.result import Failure, Result

from bitvavo_client.adapters.returns_adapter import (
    BitvavoError,
    decode_response_result,
)
from bitvavo_client.auth.signing import create_signature

if TYPE_CHECKING:  # pragma: no cover
    from bitvavo_client.auth.rate_limit import RateLimitManager
    from bitvavo_client.core.settings import BitvavoSettings
    from bitvavo_client.core.types import AnyDict


class HTTPClient:
    """HTTP client for Bitvavo REST API with rate limiting and authentication."""

    def __init__(self, settings: BitvavoSettings, rate_limiter: RateLimitManager) -> None:
        """Initialize HTTP client.

        Args:
            settings: Bitvavo settings configuration
            rate_limiter: Rate limit manager instance
        """
        self.settings: BitvavoSettings = settings
        self.rate_limiter: RateLimitManager = rate_limiter
        self.key_index: int = -1
        self.api_key: str = ""
        self.api_secret: str = ""

    def configure_key(self, key: str, secret: str, index: int) -> None:
        """Configure API key for authenticated requests.

        Args:
            key: API key
            secret: API secret
            index: Key index for rate limiting
        """
        self.api_key = key
        self.api_secret = secret
        self.key_index = index

    def request(
        self,
        method: str,
        endpoint: str,
        *,
        body: AnyDict | None = None,
        weight: int = 1,
    ) -> Result[Any, BitvavoError | httpx.HTTPError]:
        """Make HTTP request and return raw JSON data as a Result.

        Args:
            method: HTTP method (GET, POST, PUT, DELETE)
            endpoint: API endpoint path
            body: Request body for POST/PUT requests
            weight: Rate limit weight of the request

        Returns:
            Result containing raw JSON response or error

        Raises:
            HTTPError: On transport-level failures
        """
        # Check rate limits
        if not self.rate_limiter.has_budget(self.key_index, weight):
            self.rate_limiter.sleep_until_reset(self.key_index)

        url = f"{self.settings.rest_url}{endpoint}"
        headers = self._create_auth_headers(method, endpoint, body)

        try:
            response = self._make_http_request(method, url, headers, body)
        except httpx.HTTPError as exc:
            return Failure(exc)

        self._update_rate_limits(response)
        # Always return raw data - let the caller handle model conversion
        return decode_response_result(response, model=Any)

    def _create_auth_headers(self, method: str, endpoint: str, body: AnyDict | None) -> dict[str, str]:
        """Create authentication headers if API key is configured."""
        headers: dict[str, str] = {}

        if self.api_key:
            timestamp = int(time.time() * 1000) + self.settings.lag_ms
            signature = create_signature(timestamp, method, endpoint, body, self.api_secret)

            headers.update(
                {
                    "bitvavo-access-key": self.api_key,
                    "bitvavo-access-signature": signature,
                    "bitvavo-access-timestamp": str(timestamp),
                    "bitvavo-access-window": str(self.settings.access_window_ms),
                },
            )
        return headers

    def _make_http_request(
        self,
        method: str,
        url: str,
        headers: dict[str, str],
        body: AnyDict | None,
    ) -> httpx.Response:
        """Make the actual HTTP request."""
        timeout = self.settings.access_window_ms / 1000

        match method:
            case "GET":
                return httpx.get(url, headers=headers, timeout=timeout)
            case "POST":
                return httpx.post(url, headers=headers, json=body, timeout=timeout)
            case "PUT":
                return httpx.put(url, headers=headers, json=body, timeout=timeout)
            case "DELETE":
                return httpx.delete(url, headers=headers, timeout=timeout)
            case _:
                msg = f"Unsupported HTTP method: {method}"
                raise ValueError(msg)

    def _update_rate_limits(self, response: httpx.Response) -> None:
        """Update rate limits based on response."""
        try:
            json_data = response.json()
        except ValueError:
            json_data = {}

        if isinstance(json_data, dict) and "error" in json_data:
            if self._is_rate_limit_error(response, json_data):
                self.rate_limiter.update_from_error(self.key_index, json_data)
            else:
                self.rate_limiter.update_from_headers(self.key_index, dict(response.headers))
        else:
            self.rate_limiter.update_from_headers(self.key_index, dict(response.headers))

    def _is_rate_limit_error(self, response: httpx.Response, json_data: dict[str, Any]) -> bool:
        """Check if response indicates a rate limit error."""
        status = getattr(response, "status_code", None)
        if status == httpx.codes.TOO_MANY_REQUESTS:
            return True

        err = json_data.get("error")
        if isinstance(err, dict):
            code = str(err.get("code", "")).lower()
            message = str(err.get("message", "")).lower()
        else:
            code = ""
            message = str(err).lower()

        return any(k in code or k in message for k in ("rate", "limit", "too_many"))
