from __future__ import annotations

from pathlib import Path

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class BitvavoSettings(BaseSettings):
    """
    Core Bitvavo API settings using Pydantic v2.

    Provides both snake_case (modern) and UPPERCASE (original library compatibility) field access.
    Enhanced with multi-API key support and comprehensive validation.
    """

    model_config = SettingsConfigDict(
        env_file=Path.cwd() / ".env",
        env_file_encoding="utf-8",
        env_prefix="BITVAVO_",
        extra="ignore",
    )

    # Core API endpoints
    rest_url: str = Field(default="https://api.bitvavo.com/v2", description="Bitvavo REST API base URL")
    ws_url: str = Field(default="wss://ws.bitvavo.com/v2/", description="Bitvavo WebSocket API URL")

    # Timing and rate limiting
    access_window_ms: int = Field(default=10_000, description="API access window in milliseconds")

    # Client behavior
    prefer_keyless: bool = Field(default=True, description="Prefer keyless requests when possible")
    default_rate_limit: int = Field(default=1_000, description="Default rate limit for new API keys")
    rate_limit_buffer: int = Field(default=0, description="Rate limit buffer to avoid hitting limits")
    lag_ms: int = Field(default=0, description="Artificial lag to add to requests in milliseconds")
    debugging: bool = Field(default=False, description="Enable debug logging")

    # API key configuration
    api_key: str = Field(default="", alias="BITVAVO_APIKEY", description="Primary API key")
    api_secret: str = Field(default="", alias="BITVAVO_APISECRET", description="Primary API secret")

    # Multiple API keys support
    api_keys: list[dict[str, str]] = Field(
        default_factory=list, description="List of API key/secret pairs for multi-key support"
    )

    @model_validator(mode="after")
    def process_api_keys(self) -> BitvavoSettings:
        """Process API keys from single key/secret into multi-key list."""
        if self.api_key and self.api_secret and not self.api_keys:
            object.__setattr__(self, "api_keys", [{"key": self.api_key, "secret": self.api_secret}])
        return self
