"""Error definitions for bitvavo_client."""

from __future__ import annotations


class BitvavoError(Exception):
    """Base exception for Bitvavo API errors."""


class RateLimitError(BitvavoError):
    """Raised when rate limit is exceeded."""


class AuthenticationError(BitvavoError):
    """Raised when authentication fails."""


class NetworkError(BitvavoError):
    """Raised when network operations fail."""
