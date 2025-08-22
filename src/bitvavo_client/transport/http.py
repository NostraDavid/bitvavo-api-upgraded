"""HTTP client for Bitvavo API."""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, cast

from httpx import delete, get, post, put

from bitvavo_client.auth.signing import create_signature

if TYPE_CHECKING:
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

    def request(self, method: str, endpoint: str, *, body: AnyDict | None = None, weight: int = 1) -> dict[str, object]:
        """Make HTTP request to Bitvavo API.

        Args:
            method: HTTP method (GET, POST, PUT, DELETE)
            endpoint: API endpoint path
            body: Request body for POST/PUT requests
            weight: Rate limit weight of the request

        Returns:
            JSON response as dictionary

        Raises:
            requests.exceptions.RequestException: On HTTP errors
        """
        # Check rate limits
        if not self.rate_limiter.has_budget(self.key_index, weight):
            self.rate_limiter.sleep_until_reset(self.key_index)

        url = f"{self.settings.rest_url}{endpoint}"
        headers: dict[str, str] = {}

        # Add authentication headers if API key is configured
        if self.api_key:
            timestamp = int(time.time() * 1000) + self.settings.lag_ms
            signature = create_signature(timestamp, method, endpoint, body, self.api_secret)

            headers.update(
                {
                    "bitvavo-access-key": self.api_key,
                    "bitvavo-access-signature": signature,
                    "bitvavo-access-timestamp": str(timestamp),
                    "bitvavo-access-window": str(self.settings.access_window_ms),
                }
            )

        # Make request
        timeout = self.settings.access_window_ms / 1000

        if method == "GET":
            response = get(url, headers=headers, timeout=timeout)
        elif method == "POST":
            response = post(url, headers=headers, json=body, timeout=timeout)
        elif method == "PUT":
            response = put(url, headers=headers, json=body, timeout=timeout)
        elif method == "DELETE":
            response = delete(url, headers=headers, timeout=timeout)
        else:
            msg = f"Unsupported HTTP method: {method}"
            raise ValueError(msg)

        # Parse response
        data = cast("dict[str, object]", response.json())

        # Update rate limits based on response
        if "error" in data:
            self.rate_limiter.update_from_error(self.key_index, data)
        else:
            self.rate_limiter.update_from_headers(self.key_index, dict(response.headers))

        return data
