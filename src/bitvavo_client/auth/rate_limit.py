"""Rate limiting manager for Bitvavo API."""

from __future__ import annotations

import time
from typing import Protocol

from structlog.stdlib import get_logger

logger = get_logger()


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

        logger.info(
            "rate-limit-manager-initialized",
            default_remaining=default_remaining,
            buffer=buffer,
            strategy=type(self._strategy).__name__,
        )

    def ensure_key(self, idx: int) -> None:
        """Ensure a key index exists in the state."""
        if idx not in self.state:
            self.state[idx] = {"remaining": self.default_remaining, "resetAt": 0}
            logger.debug(
                "rate-limit-key-initialized",
                key_idx=idx,
                default_remaining=self.default_remaining,
            )

    def has_budget(self, idx: int, weight: int) -> bool:
        """Check if there's enough rate limit budget for a request.

        Args:
            idx: API key index
            weight: Weight of the request

        Returns:
            True if request can be made within rate limits
        """
        self.ensure_key(idx)
        has_budget = (self.state[idx]["remaining"] - weight) >= self.buffer

        logger.debug(
            "rate-limit-budget-check",
            key_idx=idx,
            weight=weight,
            remaining=self.state[idx]["remaining"],
            buffer=self.buffer,
            has_budget=has_budget,
        )

        return has_budget

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
        old_remaining = self.state[idx]["remaining"]
        self.state[idx]["remaining"] = max(0, self.state[idx]["remaining"] - weight)

        logger.debug(
            "rate-limit-call-recorded",
            key_idx=idx,
            weight=weight,
            old_remaining=old_remaining,
            new_remaining=self.state[idx]["remaining"],
        )

    def update_from_headers(self, idx: int, headers: dict[str, str]) -> None:
        """Update rate limit state from response headers.

        Args:
            idx: API key index
            headers: HTTP response headers
        """
        self.ensure_key(idx)

        remaining = headers.get("bitvavo-ratelimit-remaining")
        reset_at = headers.get("bitvavo-ratelimit-resetat")

        old_state = dict(self.state[idx])

        if remaining is not None:
            self.state[idx]["remaining"] = int(remaining)
        if reset_at is not None:
            self.state[idx]["resetAt"] = int(reset_at)

        logger.debug(
            "rate-limit-updated-from-headers",
            key_idx=idx,
            old_remaining=old_state["remaining"],
            new_remaining=self.state[idx]["remaining"],
            old_reset_at=old_state["resetAt"],
            new_reset_at=self.state[idx]["resetAt"],
            has_remaining_header=remaining is not None,
            has_reset_header=reset_at is not None,
        )

    def update_from_error(self, idx: int, _err: dict[str, object]) -> None:
        """Update rate limit state from API error response.

        Args:
            idx: API key index
            _err: Error response from API (unused but kept for interface compatibility)
        """
        self.ensure_key(idx)
        old_remaining = self.state[idx]["remaining"]
        old_reset_at = self.state[idx]["resetAt"]

        self.state[idx]["remaining"] = 0
        self.state[idx]["resetAt"] = int(time.time() * 1000) + 60_000

        logger.warning(
            "rate-limit-updated-from-error",
            key_idx=idx,
            old_remaining=old_remaining,
            old_reset_at=old_reset_at,
            new_reset_at=self.state[idx]["resetAt"],
        )

    def sleep_until_reset(self, idx: int) -> None:
        """Sleep until rate limit resets for given key index.

        Args:
            idx: API key index
        """

        self.ensure_key(idx)
        now = int(time.time() * 1000)
        ms_left = max(0, self.state[idx]["resetAt"] - now)
        sleep_seconds = ms_left / 1000 + 1

        logger.info(
            "rate-limit-exceeded",
            key_idx=idx,
            sleep_seconds=sleep_seconds,
            reset_at=self.state[idx]["resetAt"],
        )
        time.sleep(sleep_seconds)

        logger.info(
            "rate-limit-sleep-completed",
            key_idx=idx,
            slept_seconds=sleep_seconds,
        )

    def handle_limit(self, idx: int, weight: int) -> None:
        """Invoke the configured strategy when rate limit is exceeded."""
        logger.info(
            "rate-limit-handling-strategy",
            key_idx=idx,
            weight=weight,
            strategy=type(self._strategy).__name__,
        )
        self._strategy(self, idx, weight)

    def reset_key(self, idx: int) -> None:
        """Reset the remaining budget and reset time for a key index."""
        self.ensure_key(idx)
        old_remaining = self.state[idx]["remaining"]
        old_reset_at = self.state[idx]["resetAt"]

        self.state[idx]["remaining"] = self.default_remaining
        self.state[idx]["resetAt"] = 0

        logger.info(
            "rate-limit-key-reset",
            key_idx=idx,
            old_remaining=old_remaining,
            old_reset_at=old_reset_at,
            new_remaining=self.default_remaining,
        )

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
            logger.debug("rate-limit-no-keys-available", weight=weight)
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
            best_key = max(suitable_keys, key=lambda x: x[1])[0]
            logger.debug(
                "rate-limit-best-key-found",
                key_idx=best_key,
                weight=weight,
                remaining=self.state[best_key]["remaining"],
                suitable_keys_count=len(suitable_keys),
            )
            return best_key

        # If no keys have budget, return the one that resets earliest
        if fallback_keys:
            fallback_key = min(fallback_keys, key=lambda x: x[1])[0]
            logger.warning(
                "rate-limit-using-fallback-key",
                key_idx=fallback_key,
                weight=weight,
                reset_at=self.state[fallback_key]["resetAt"],
                fallback_keys_count=len(fallback_keys),
            )
            return fallback_key

        logger.warning("rate-limit-no-suitable-keys", weight=weight, available_keys=available_keys)
        return None

    def get_earliest_reset_time(self, key_indices: list[int]) -> int:
        """Get the earliest reset time among the given keys.

        Args:
            key_indices: List of key indices to check

        Returns:
            Earliest reset timestamp in milliseconds, or 0 if no keys have reset times
        """
        if not key_indices:
            logger.debug("rate-limit-no-keys-for-reset-time")
            return 0

        reset_times = []
        for idx in key_indices:
            self.ensure_key(idx)
            reset_at = self.state[idx]["resetAt"]
            if reset_at > 0:  # Only consider keys that actually have a reset time
                reset_times.append(reset_at)

        earliest_reset = min(reset_times) if reset_times else 0

        logger.debug(
            "rate-limit-earliest-reset-time",
            key_indices=key_indices,
            keys_with_reset=len(reset_times),
            earliest_reset=earliest_reset,
        )

        return earliest_reset
