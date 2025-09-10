"""Main facade for the Bitvavo client."""

from __future__ import annotations

from typing import TYPE_CHECKING

from bitvavo_client.auth.rate_limit import RateLimitManager
from bitvavo_client.core.settings import BitvavoSettings
from bitvavo_client.endpoints.private import PrivateAPI
from bitvavo_client.endpoints.public import PublicAPI
from bitvavo_client.transport.http import HTTPClient

if TYPE_CHECKING:  # pragma: no cover
    from bitvavo_client.core.model_preferences import ModelPreference


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
            default_remaining=self.settings.default_rate_limit,
            buffer=self.settings.rate_limit_buffer,
        )
        self.http = HTTPClient(self.settings, self.rate_limiter)

        # Initialize API endpoint handlers with preferred model settings
        self.public = PublicAPI(
            self.http,
            preferred_model=preferred_model,
            default_schema=default_schema,
        )
        self.private = PrivateAPI(
            self.http,
            preferred_model=preferred_model,
            default_schema=default_schema,
        )
