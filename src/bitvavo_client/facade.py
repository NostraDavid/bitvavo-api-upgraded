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
        self._configure_api_keys()

    def _configure_api_keys(self) -> None:
        """Configure API keys for authentication."""
        if self.settings.api_key and self.settings.api_secret:
            # Single API key configuration
            self.http.configure_key(self.settings.api_key, self.settings.api_secret, 0)
            self.rate_limiter.ensure_key(0)
        elif self.settings.api_keys:
            # Multiple API keys - configure the first one by default
            if self.settings.api_keys:
                first_key = self.settings.api_keys[0]
                self.http.configure_key(first_key["key"], first_key["secret"], 0)
                self.rate_limiter.ensure_key(0)
