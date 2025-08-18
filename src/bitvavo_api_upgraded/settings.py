from __future__ import annotations

import logging
import os
from pathlib import Path

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from bitvavo_api_upgraded.type_aliases import ms


class BitvavoApiUpgradedSettings(BaseSettings):
    """
    These settings provide extra functionality. Originally I wanted to combine
    then, but I figured that would be a bad idea.
    """

    LOG_LEVEL: str = Field("INFO")
    LOG_EXTERNAL_LEVEL: str = Field("WARNING")
    LAG: ms = Field(ms(50))
    RATE_LIMITING_BUFFER: int = Field(25)
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

    @classmethod
    @field_validator("LOG_LEVEL", "LOG_EXTERNAL_LEVEL", mode="before")
    def validate_log_level(cls, v: str) -> str:
        if v not in logging._nameToLevel:  # noqa: SLF001
            msg = f"Invalid log level: {v}"
            raise ValueError(msg)
        return v

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
    """

    ACCESSWINDOW: int = Field(10_000)
    API_RATING_LIMIT_PER_MINUTE: int = Field(default=1000)
    API_RATING_LIMIT_PER_SECOND: int = Field(default=1000)
    APIKEY: str = Field(default="BITVAVO_APIKEY is missing")
    APISECRET: str = Field(default="BITVAVO_APISECRET is missing")
    DEBUGGING: bool = Field(default=False)
    RESTURL: str = Field(default="https://api.bitvavo.com/v2")
    WSURL: str = Field(default="wss://ws.bitvavo.com/v2/")

    # Configuration for Pydantic Settings
    model_config = SettingsConfigDict(
        env_file=Path.cwd() / ".env",
        env_file_encoding="utf-8",
        env_prefix="BITVAVO_",
        extra="ignore",
    )

    @model_validator(mode="after")
    def set_api_rating_limit_per_second(self) -> BitvavoSettings:
        self.API_RATING_LIMIT_PER_SECOND = self.API_RATING_LIMIT_PER_SECOND // 60
        return self


# Initialize the settings
bitvavo_upgraded_settings = BitvavoApiUpgradedSettings()
BITVAVO_API_UPGRADED = bitvavo_upgraded_settings
bitvavo_settings = BitvavoSettings()
BITVAVO = bitvavo_settings
