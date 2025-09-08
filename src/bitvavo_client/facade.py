"""Main facade for the Bitvavo client."""

from __future__ import annotations

from typing import TYPE_CHECKING, TypeVar

from bitvavo_client.auth.rate_limit import RateLimitManager
from bitvavo_client.core.settings import BitvavoSettings
from bitvavo_client.endpoints.private import PrivateAPI
from bitvavo_client.endpoints.public import PublicAPI
from bitvavo_client.transport.http import HTTPClient

if TYPE_CHECKING:  # pragma: no cover
    from bitvavo_client.core.model_preferences import ModelPreference

T = TypeVar("T")


class BitvavoClient:
    """
    Main Bitvavo API client facade providing backward-compatible interface.

    TODO(NostraDavid): add mechanisms to get a ton of data efficiently, which then uses the public and private APIs.
    Otherwise, users can just grab the data themselves via the public and private API endpoints.
    """

    def __init__(
        self,
        settings: BitvavoSettings | None = None,
        *,
        preferred_model: ModelPreference | str | None = None,
        default_schema: dict | None = None,
    ) -> None:
        """Initialize Bitvavo client.

        Args:
            settings: Optional settings override. If None, uses defaults.
            preferred_model: Preferred model format for responses
            default_schema: Default schema for DataFrame conversion
        """
        self.settings = settings or BitvavoSettings()
        self.rate_limiter = RateLimitManager(
            self.settings.default_rate_limit,
            self.settings.rate_limit_buffer,
        )
        self.http = HTTPClient(self.settings, self.rate_limiter)

        # Initialize API endpoint handlers with preferred model settings
        self.public = PublicAPI(self.http, preferred_model=preferred_model, default_schema=default_schema)
        self.private = PrivateAPI(self.http, preferred_model=preferred_model, default_schema=default_schema)

        # Configure API keys if available
        self._api_keys: list[tuple[str, str]] = []
        self._current_key: int = 0
        self._configure_api_keys()

    def _configure_api_keys(self) -> None:
        """Configure API keys for authentication."""
        # Collect keys from settings
        if self.settings.api_key and self.settings.api_secret:
            self._api_keys.append((self.settings.api_key, self.settings.api_secret))
        if self.settings.api_keys:
            self._api_keys.extend((item["key"], item["secret"]) for item in self.settings.api_keys)

        if not self._api_keys:
            return

        for idx, (_key, _secret) in enumerate(self._api_keys):
            self.rate_limiter.ensure_key(idx)

        first_key = self._api_keys[0]
        self.http.configure_key(first_key[0], first_key[1], 0)
        if len(self._api_keys) > 1:
            self.http.set_key_rotation_callback(self.rotate_key)

    def rotate_key(self) -> bool:
        """Rotate to the next configured API key if available."""
        if len(self._api_keys) <= 1:
            return False
        self._current_key = (self._current_key + 1) % len(self._api_keys)
        key, secret = self._api_keys[self._current_key]
        self.http.configure_key(key, secret, self._current_key)
        return True

    def select_key(self, index: int) -> None:
        """Select a specific API key by index."""
        if not (0 <= index < len(self._api_keys)):
            msg = "API key index out of range"
            raise IndexError(msg)
        self._current_key = index
        key, secret = self._api_keys[index]
        self.http.configure_key(key, secret, index)
