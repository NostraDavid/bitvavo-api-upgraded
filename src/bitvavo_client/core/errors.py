"""Error definitions for bitvavo_client."""


class BitvavoError(Exception):  # pragma: no cover
    """Base exception for Bitvavo API errors."""


class RateLimitError(BitvavoError):  # pragma: no cover
    """Raised when rate limit is exceeded."""


class AuthenticationError(BitvavoError):  # pragma: no cover
    """Raised when authentication fails."""


class NetworkError(BitvavoError):  # pragma: no cover
    """Raised when network operations fail."""
