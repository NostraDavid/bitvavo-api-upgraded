"""Rate limiting manager for Bitvavo API."""

from __future__ import annotations

import time


class RateLimitManager:
    """Manages rate limiting for multiple API keys and keyless requests.

    Each API key index has its own rate limit state. Index -1 is reserved
    for keyless requests.
    """

    def __init__(self, default_remaining: int, buffer: int) -> None:
        """Initialize rate limit manager.

        Args:
            default_remaining: Default rate limit amount
            buffer: Buffer to keep before hitting limit
        """
        self.state: dict[int, dict[str, int]] = {-1: {"remaining": default_remaining, "resetAt": 0}}
        self.buffer: int = buffer

    def ensure_key(self, idx: int) -> None:
        """Ensure a key index exists in the state."""
        if idx not in self.state:
            self.state[idx] = {"remaining": self.state[-1]["remaining"], "resetAt": 0}

    def has_budget(self, idx: int, weight: int) -> bool:
        """Check if there's enough rate limit budget for a request.

        Args:
            idx: API key index (-1 for keyless)
            weight: Weight of the request

        Returns:
            True if request can be made within rate limits
        """
        self.ensure_key(idx)
        return (self.state[idx]["remaining"] - weight) >= self.buffer

    def update_from_headers(self, idx: int, headers: dict[str, str]) -> None:
        """Update rate limit state from response headers.

        Args:
            idx: API key index
            headers: HTTP response headers
        """
        self.ensure_key(idx)

        remaining = headers.get("bitvavo-ratelimit-remaining")
        reset_at = headers.get("bitvavo-ratelimit-resetat")

        if remaining is not None:
            self.state[idx]["remaining"] = int(remaining)
        if reset_at is not None:
            self.state[idx]["resetAt"] = int(reset_at)

    def update_from_error(self, idx: int, _err: dict[str, object]) -> None:
        """Update rate limit state from API error response.

        Args:
            idx: API key index
            _err: Error response from API (unused but kept for interface compatibility)
        """
        self.ensure_key(idx)
        self.state[idx]["remaining"] = 0
        self.state[idx]["resetAt"] = int(time.time() * 1000) + 60_000

    def sleep_until_reset(self, idx: int) -> None:
        """Sleep until rate limit resets for given key index.

        Args:
            idx: API key index
        """
        self.ensure_key(idx)
        now = int(time.time() * 1000)
        ms_left = max(0, self.state[idx]["resetAt"] - now)
        time.sleep(ms_left / 1000 + 1)

    def get_remaining(self, idx: int) -> int:
        """Get remaining rate limit for key index.

        Args:
            idx: API key index

        Returns:
            Remaining rate limit count
        """
        self.ensure_key(idx)
        return self.state[idx]["remaining"]

    def get_reset_at(self, idx: int) -> int:
        """Get reset timestamp for key index.

        Args:
            idx: API key index

        Returns:
            Reset timestamp in milliseconds
        """
        self.ensure_key(idx)
        return self.state[idx]["resetAt"]
