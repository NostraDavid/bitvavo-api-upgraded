from __future__ import annotations

from typing import ClassVar

from pydantic_settings import BaseSettings, SettingsConfigDict


class BitvavoSettings(BaseSettings):
    """Core Bitvavo API settings using Pydantic v2."""

    model_config: ClassVar[SettingsConfigDict] = SettingsConfigDict(
        env_prefix="BITVAVO_", extra="ignore", env_file=".env"
    )

    rest_url: str = "https://api.bitvavo.com/v2"
    ws_url: str = "wss://ws.bitvavo.com/v2/"
    access_window_ms: int = 10_000
    prefer_keyless: bool = True
    default_rate_limit: int = 1_000
    rate_limit_buffer: int = 0
    lag_ms: int = 0
    debugging: bool = False

    # API key configuration
    api_key: str = ""
    api_secret: str = ""

    # Multiple API keys support
    api_keys: list[dict[str, str]] = []
