from __future__ import annotations

import os
from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from bitvavo_api_upgraded.type_aliases import ms


class BitvavoApiUpgradedSettings(BaseSettings):
    """
    These settings provide extra functionality. Originally I wanted to combine
    then, but I figured that would be a bad idea.
    """

    LOG_LEVEL: Literal["CRITICAL", "FATAL", "ERROR", "WARN", "WARNING", "INFO", "DEBUG", "NOTSET"] = Field(
        default="INFO",
        description="Logging level for the application",
    )
    LOG_EXTERNAL_LEVEL: Literal["CRITICAL", "FATAL", "ERROR", "WARN", "WARNING", "INFO", "DEBUG", "NOTSET"] = Field(
        default="WARNING",
        description="Logging level for external libraries",
    )
    LAG: ms = Field(default=ms(50))
    RATE_LIMITING_BUFFER: int = Field(default=25)

    # Multi-API key settings
    PREFER_KEYLESS: bool = Field(default=True, description="Prefer keyless requests over API key requests")
    DEFAULT_RATE_LIMIT: int = Field(default=1000, description="Default rate limit for new API keys")

    SSL_CERT_FILE: str | None = Field(
        default=None,
        description="Path to SSL certificate file for HTTPS/WSS connections",
    )

    # Configuration for Pydantic Settings
    model_config: SettingsConfigDict = SettingsConfigDict(
        env_file=Path.cwd() / ".env",
        env_file_encoding="utf-8",
        env_prefix="BITVAVO_API_UPGRADED_",
        extra="ignore",
    )

    @field_validator("LOG_LEVEL", "LOG_EXTERNAL_LEVEL", mode="before")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        valid_levels = {"CRITICAL", "FATAL", "ERROR", "WARN", "WARNING", "INFO", "DEBUG", "NOTSET"}
        if v.upper() not in valid_levels:
            msg = f"Invalid log level: {v}. Must be one of: {', '.join(valid_levels)}"
            raise ValueError(msg)
        return v.upper()

    @model_validator(mode="after")
    def configure_ssl_certificate(self) -> BitvavoApiUpgradedSettings:
        """Configure SSL certificate file path and set environment variable if needed."""
        if self.SSL_CERT_FILE is None and "SSL_CERT_FILE" not in os.environ:
            # Try to auto-detect SSL certificate file only if not already set in environment
            common_ssl_cert_paths = [
                "/etc/ssl/certs/ca-certificates.crt",  # Debian/Ubuntu/NixOS
                "/etc/ssl/certs/ca-bundle.crt",  # CentOS/RHEL/Fedora
                "/etc/ssl/cert.pem",  # OpenBSD/macOS
                "/usr/local/share/certs/ca-root-nss.crt",  # FreeBSD
                "/etc/pki/tls/certs/ca-bundle.crt",  # Old CentOS/RHEL
            ]

            for cert_path in common_ssl_cert_paths:
                if Path(cert_path).exists():
                    self.SSL_CERT_FILE = cert_path
                    break

        # Set the environment variable if we have a certificate file
        if self.SSL_CERT_FILE and Path(self.SSL_CERT_FILE).exists():
            os.environ["SSL_CERT_FILE"] = self.SSL_CERT_FILE
        elif self.SSL_CERT_FILE:
            # User specified a path but it doesn't exist
            msg = f"SSL certificate file not found: {self.SSL_CERT_FILE}"
            raise FileNotFoundError(msg)

        return self


class BitvavoSettings(BaseSettings):
    """
    These are the base settings from the original library.
    Enhanced to support multiple API keys.
    """

    ACCESSWINDOW: int = Field(default=10_000)
    API_RATING_LIMIT_PER_MINUTE: int = Field(default=1000)
    API_RATING_LIMIT_PER_SECOND: int = Field(default=1000)
    APIKEY: str = Field(default="")
    APISECRET: str = Field(default="")

    # Multiple API key support
    APIKEYS: list[dict[str, str]] = Field(default_factory=list, description="List of API key/secret pairs")

    DEBUGGING: bool = Field(default=False)
    RESTURL: str = Field(default="https://api.bitvavo.com/v2")
    WSURL: str = Field(default="wss://ws.bitvavo.com/v2/")

    # Multi-key specific settings
    PREFER_KEYLESS: bool = Field(default=True)

    # Configuration for Pydantic Settings
    model_config: SettingsConfigDict = SettingsConfigDict(
        env_file=Path.cwd() / ".env",
        env_file_encoding="utf-8",
        env_prefix="BITVAVO_",
        extra="ignore",
    )

    @model_validator(mode="after")
    def set_api_rating_limit_per_second(self) -> BitvavoSettings:
        # Create a new value instead of modifying the Field directly
        object.__setattr__(self, "API_RATING_LIMIT_PER_SECOND", self.API_RATING_LIMIT_PER_SECOND // 60)
        return self

    @model_validator(mode="after")
    def process_api_keys(self) -> BitvavoSettings:
        """Process API keys from environment variables."""
        # If single APIKEY/APISECRET provided and APIKEYS is empty, create APIKEYS list
        if self.APIKEY and self.APISECRET and not self.APIKEYS:
            object.__setattr__(self, "APIKEYS", [{"key": self.APIKEY, "secret": self.APISECRET}])

        return self


# Initialize the settings
bitvavo_upgraded_settings = BitvavoApiUpgradedSettings()
BITVAVO_API_UPGRADED = bitvavo_upgraded_settings
bitvavo_settings = BitvavoSettings()
BITVAVO = bitvavo_settings
