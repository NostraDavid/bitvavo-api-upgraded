"""Rate limiting manager for Bitvavo API."""

from __future__ import annotations

import time
from typing import Protocol


class RateLimitStrategy(Protocol):
    """Protocol for custom rate limit handling strategies."""

    def __call__(self, manager: RateLimitManager, idx: int, weight: int) -> None: ...


class DefaultRateLimitStrategy(RateLimitStrategy):
    """Default RateLimitStrategy implementation that sleeps until the key's rate limit resets."""

    def __call__(self, manager: RateLimitManager, idx: int, _: int) -> None:
        manager.sleep_until_reset(idx)


class RateLimitManager:
    """Manages rate limiting for multiple API keys.

    Each API key index has its own rate limit state.
    """

    def __init__(self, default_remaining: int, buffer: int, strategy: RateLimitStrategy | None = None) -> None:
        """Initialize rate limit manager.

        Args:
            default_remaining: Default rate limit amount
            buffer: Buffer to keep before hitting limit
            strategy: Optional strategy callback when rate limit exceeded
        """
        self.default_remaining: int = default_remaining
        self.state: dict[int, dict[str, int]] = {}
        self.buffer: int = buffer

        self._strategy: RateLimitStrategy = strategy or DefaultRateLimitStrategy()

    def ensure_key(self, idx: int) -> None:
        """Ensure a key index exists in the state."""
        if idx not in self.state:
            self.state[idx] = {"remaining": self.default_remaining, "resetAt": 0}

    def has_budget(self, idx: int, weight: int) -> bool:
        """Check if there's enough rate limit budget for a request.

        Args:
            idx: API key index
            weight: Weight of the request

        Returns:
            True if request can be made within rate limits
        """
        self.ensure_key(idx)
        return (self.state[idx]["remaining"] - weight) >= self.buffer

    def record_call(self, idx: int, weight: int) -> None:
        """Record a request by decreasing the remaining budget.

        This should be called whenever an API request is made to ensure
        the local rate limit state reflects all outgoing calls, even when
        the response doesn't include rate limit headers.

        Args:
            idx: API key index
            weight: Weight of the request
        """
        self.ensure_key(idx)
        self.state[idx]["remaining"] = max(0, self.state[idx]["remaining"] - weight)

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

    def handle_limit(self, idx: int, weight: int) -> None:
        """Invoke the configured strategy when rate limit is exceeded."""
        self._strategy(self, idx, weight)

    def reset_key(self, idx: int) -> None:
        """Reset the remaining budget and reset time for a key index."""
        self.ensure_key(idx)
        self.state[idx]["remaining"] = self.default_remaining
        self.state[idx]["resetAt"] = 0

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

    def find_best_available_key(self, available_keys: list[int], weight: int) -> int | None:
        """Find the best API key for a request with given weight.

        Prioritizes keys by:
        1. Keys with sufficient budget (remaining - weight >= buffer)
        2. Keys with the most remaining budget
        3. Keys with the earliest reset time (if all are rate limited)

        Args:
            available_keys: List of available key indices
            weight: Weight of the request

        Returns:
            Best key index or None if no keys are suitable
        """
        if not available_keys:
            return None

        suitable_keys = []
        fallback_keys = []

        for idx in available_keys:
            self.ensure_key(idx)
            if self.has_budget(idx, weight):
                suitable_keys.append((idx, self.state[idx]["remaining"]))
            else:
                fallback_keys.append((idx, self.state[idx]["resetAt"]))

        # Return key with most remaining budget if any have sufficient budget
        if suitable_keys:
            return max(suitable_keys, key=lambda x: x[1])[0]

        # If no keys have budget, return the one that resets earliest
        if fallback_keys:
            return min(fallback_keys, key=lambda x: x[1])[0]

        return None

    def get_earliest_reset_time(self, key_indices: list[int]) -> int:
        """Get the earliest reset time among the given keys.

        Args:
            key_indices: List of key indices to check

        Returns:
            Earliest reset timestamp in milliseconds, or 0 if no keys have reset times
        """
        if not key_indices:
            return 0

        reset_times = []
        for idx in key_indices:
            self.ensure_key(idx)
            reset_at = self.state[idx]["resetAt"]
            if reset_at > 0:  # Only consider keys that actually have a reset time
                reset_times.append(reset_at)

        return min(reset_times) if reset_times else 0
