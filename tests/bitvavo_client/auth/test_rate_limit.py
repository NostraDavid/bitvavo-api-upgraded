"""Tests for RateLimitManager class."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from bitvavo_client.auth.rate_limit import RateLimitManager


class TestRateLimitManagerInitialization:
    """Test RateLimitManager initialization and basic configuration."""

    def test_init_default_state(self) -> None:
        """Test initialization creates correct default state."""
        manager = RateLimitManager(default_remaining=1000, buffer=50)

        # Should initialize with keyless state (index -1)
        assert -1 in manager.state
        assert manager.state[-1]["remaining"] == 1000
        assert manager.state[-1]["resetAt"] == 0
        assert manager.buffer == 50

    def test_init_with_different_values(self) -> None:
        """Test initialization with different parameter values."""
        manager = RateLimitManager(default_remaining=500, buffer=25)

        assert manager.state[-1]["remaining"] == 500
        assert manager.state[-1]["resetAt"] == 0
        assert manager.buffer == 25

    def test_init_with_zero_values(self) -> None:
        """Test initialization with zero values."""
        manager = RateLimitManager(default_remaining=0, buffer=0)

        assert manager.state[-1]["remaining"] == 0
        assert manager.buffer == 0


class TestRateLimitManagerKeyManagement:
    """Test key index management functionality."""

    def test_ensure_key_creates_new_key(self) -> None:
        """Test that ensure_key creates new key entries."""
        manager = RateLimitManager(default_remaining=1000, buffer=50)

        # Initially only keyless (-1) exists
        assert 0 not in manager.state
        assert 1 not in manager.state

        # Ensure key 0 exists
        manager.ensure_key(0)
        assert 0 in manager.state
        assert manager.state[0]["remaining"] == 1000  # Inherits from keyless
        assert manager.state[0]["resetAt"] == 0

        # Ensure key 1 exists
        manager.ensure_key(1)
        assert 1 in manager.state
        assert manager.state[1]["remaining"] == 1000
        assert manager.state[1]["resetAt"] == 0

    def test_ensure_key_idempotent(self) -> None:
        """Test that ensure_key is idempotent - doesn't overwrite existing keys."""
        manager = RateLimitManager(default_remaining=1000, buffer=50)

        # Create and modify key 0
        manager.ensure_key(0)
        manager.state[0]["remaining"] = 500
        manager.state[0]["resetAt"] = 12345

        # Ensure key 0 again - should not overwrite
        manager.ensure_key(0)
        assert manager.state[0]["remaining"] == 500
        assert manager.state[0]["resetAt"] == 12345

    def test_ensure_key_negative_index(self) -> None:
        """Test ensure_key with negative indices."""
        manager = RateLimitManager(default_remaining=1000, buffer=50)

        # Keyless (-1) already exists
        manager.ensure_key(-1)
        assert manager.state[-1]["remaining"] == 1000

        # Test other negative index
        manager.ensure_key(-5)
        assert -5 in manager.state
        assert manager.state[-5]["remaining"] == 1000

    def test_ensure_key_inherits_from_keyless(self) -> None:
        """Test that new keys inherit values from keyless state."""
        manager = RateLimitManager(default_remaining=800, buffer=30)

        # Modify keyless state
        manager.state[-1]["remaining"] = 600
        manager.state[-1]["resetAt"] = 54321

        # New key should inherit from keyless
        manager.ensure_key(2)
        assert manager.state[2]["remaining"] == 600
        assert manager.state[2]["resetAt"] == 0  # resetAt is always initialized to 0


class TestRateLimitManagerBudgetChecking:
    """Test rate limit budget checking functionality."""

    def test_has_budget_sufficient_remaining(self) -> None:
        """Test has_budget when there's sufficient remaining budget."""
        manager = RateLimitManager(default_remaining=1000, buffer=50)

        # Keyless request with plenty of budget
        assert manager.has_budget(-1, 100) is True
        assert manager.has_budget(-1, 900) is True

        # Request right at the buffer boundary
        assert manager.has_budget(-1, 950) is True  # 1000 - 950 = 50 (equals buffer)

    def test_has_budget_insufficient_remaining(self) -> None:
        """Test has_budget when there's insufficient remaining budget."""
        manager = RateLimitManager(default_remaining=1000, buffer=50)

        # Request that would go below buffer
        assert manager.has_budget(-1, 951) is False  # 1000 - 951 = 49 (less than buffer)
        assert manager.has_budget(-1, 1000) is False

    def test_has_budget_creates_key_if_needed(self) -> None:
        """Test that has_budget creates key index if it doesn't exist."""
        manager = RateLimitManager(default_remaining=1000, buffer=50)

        # Key 0 doesn't exist yet
        assert 0 not in manager.state

        # has_budget should create it
        result = manager.has_budget(0, 100)
        assert result is True
        assert 0 in manager.state
        assert manager.state[0]["remaining"] == 1000

    def test_has_budget_with_modified_state(self) -> None:
        """Test has_budget with manually modified state."""
        manager = RateLimitManager(default_remaining=1000, buffer=50)

        # Modify state for key 0
        manager.ensure_key(0)
        manager.state[0]["remaining"] = 200

        # Test budget checking with modified state
        assert manager.has_budget(0, 100) is True  # 200 - 100 = 100 > 50
        assert manager.has_budget(0, 149) is True  # 200 - 149 = 51 > 50
        assert manager.has_budget(0, 150) is True  # 200 - 150 = 50 = 50 (equals buffer)
        assert manager.has_budget(0, 151) is False  # 200 - 151 = 49 < 50

    def test_has_budget_zero_buffer(self) -> None:
        """Test has_budget behavior with zero buffer."""
        manager = RateLimitManager(default_remaining=100, buffer=0)

        assert manager.has_budget(-1, 99) is True  # 100 - 99 = 1 > 0
        assert manager.has_budget(-1, 100) is True  # 100 - 100 = 0 = 0 (equals buffer)
        assert manager.has_budget(-1, 101) is False  # 100 - 101 = -1 < 0


class TestRateLimitManagerCallRecording:
    """Test recording calls decreases remaining budget."""

    def test_record_call_updates_remaining(self) -> None:
        """record_call should subtract the request weight from remaining."""
        manager = RateLimitManager(default_remaining=1000, buffer=50)

        # Record a call and verify remaining budget decreased
        manager.record_call(-1, 100)
        assert manager.get_remaining(-1) == 900

    def test_record_call_creates_key(self) -> None:
        """record_call should ensure key exists before updating."""
        manager = RateLimitManager(default_remaining=1000, buffer=50)

        # Record call for a new key index
        manager.record_call(1, 200)
        assert manager.get_remaining(1) == 800


class TestRateLimitManagerHeaderUpdates:
    """Test updating rate limit state from HTTP headers."""

    def test_update_from_headers_both_values(self) -> None:
        """Test updating state when both remaining and resetAt headers are present."""
        manager = RateLimitManager(default_remaining=1000, buffer=50)

        headers = {
            "bitvavo-ratelimit-remaining": "750",
            "bitvavo-ratelimit-resetat": "1693843200000",
        }

        manager.update_from_headers(0, headers)

        assert manager.state[0]["remaining"] == 750
        assert manager.state[0]["resetAt"] == 1693843200000

    def test_update_from_headers_remaining_only(self) -> None:
        """Test updating state when only remaining header is present."""
        manager = RateLimitManager(default_remaining=1000, buffer=50)

        # Set initial state
        manager.ensure_key(0)
        manager.state[0]["resetAt"] = 12345

        headers = {
            "bitvavo-ratelimit-remaining": "600",
        }

        manager.update_from_headers(0, headers)

        assert manager.state[0]["remaining"] == 600
        assert manager.state[0]["resetAt"] == 12345  # Should remain unchanged

    def test_update_from_headers_resetat_only(self) -> None:
        """Test updating state when only resetAt header is present."""
        manager = RateLimitManager(default_remaining=1000, buffer=50)

        # Set initial state
        manager.ensure_key(0)
        manager.state[0]["remaining"] = 800

        headers = {
            "bitvavo-ratelimit-resetat": "1693843260000",
        }

        manager.update_from_headers(0, headers)

        assert manager.state[0]["remaining"] == 800  # Should remain unchanged
        assert manager.state[0]["resetAt"] == 1693843260000

    def test_update_from_headers_no_relevant_headers(self) -> None:
        """Test updating state when no relevant headers are present."""
        manager = RateLimitManager(default_remaining=1000, buffer=50)

        # Set initial state
        manager.ensure_key(0)
        manager.state[0]["remaining"] = 700
        manager.state[0]["resetAt"] = 54321

        headers = {
            "content-type": "application/json",
            "some-other-header": "value",
        }

        manager.update_from_headers(0, headers)

        # State should remain unchanged
        assert manager.state[0]["remaining"] == 700
        assert manager.state[0]["resetAt"] == 54321

    def test_update_from_headers_creates_key_if_needed(self) -> None:
        """Test that update_from_headers creates key index if it doesn't exist."""
        manager = RateLimitManager(default_remaining=1000, buffer=50)

        # Key 1 doesn't exist yet
        assert 1 not in manager.state

        headers = {
            "bitvavo-ratelimit-remaining": "500",
            "bitvavo-ratelimit-resetat": "1693843300000",
        }

        manager.update_from_headers(1, headers)

        assert 1 in manager.state
        assert manager.state[1]["remaining"] == 500
        assert manager.state[1]["resetAt"] == 1693843300000

    def test_update_from_headers_invalid_values(self) -> None:
        """Test behavior with invalid header values."""
        manager = RateLimitManager(default_remaining=1000, buffer=50)

        # Test with non-numeric strings (should raise ValueError)
        headers = {
            "bitvavo-ratelimit-remaining": "not-a-number",
        }

        with pytest.raises(ValueError, match="invalid literal"):
            manager.update_from_headers(0, headers)

        # Test with empty strings
        headers = {
            "bitvavo-ratelimit-remaining": "",
        }

        with pytest.raises(ValueError, match="invalid literal"):
            manager.update_from_headers(0, headers)


class TestRateLimitManagerErrorUpdates:
    """Test updating rate limit state from API errors."""

    @patch("time.time")
    def test_update_from_error_sets_zero_remaining(self, mock_time: MagicMock) -> None:
        """Test that update_from_error sets remaining to 0."""
        mock_time.return_value = 1693843200.5  # Mock current time

        manager = RateLimitManager(default_remaining=1000, buffer=50)

        # Set initial state
        manager.ensure_key(0)
        manager.state[0]["remaining"] = 500

        error: dict[str, object] = {"error": "Rate limit exceeded"}
        manager.update_from_error(0, error)

        assert manager.state[0]["remaining"] == 0
        assert manager.state[0]["resetAt"] == 1693843200500 + 60000  # Current time + 1 minute

    @patch("time.time")
    def test_update_from_error_sets_reset_time(self, mock_time: MagicMock) -> None:
        """Test that update_from_error sets resetAt to current time + 1 minute."""
        mock_time.return_value = 1693843300.123  # Mock current time

        manager = RateLimitManager(default_remaining=1000, buffer=50)

        error: dict[str, object] = {"error": "Too many requests"}
        manager.update_from_error(0, error)

        expected_reset_at = int(1693843300.123 * 1000) + 60000
        assert manager.state[0]["remaining"] == 0
        assert manager.state[0]["resetAt"] == expected_reset_at

    def test_update_from_error_creates_key_if_needed(self) -> None:
        """Test that update_from_error creates key index if it doesn't exist."""
        manager = RateLimitManager(default_remaining=1000, buffer=50)

        # Key 2 doesn't exist yet
        assert 2 not in manager.state

        error: dict[str, object] = {"error": "Rate limit exceeded"}
        manager.update_from_error(2, error)

        assert 2 in manager.state
        assert manager.state[2]["remaining"] == 0

    def test_update_from_error_error_parameter_unused(self) -> None:
        """Test that the error parameter is unused but interface is maintained."""
        manager = RateLimitManager(default_remaining=1000, buffer=50)

        # Different error objects should produce same result
        error1: dict[str, object] = {"error": "Rate limit exceeded"}
        error2: dict[str, object] = {"different": "error", "format": 123}
        error3: dict[str, object] = {}

        with patch("time.time", return_value=1000.0):
            manager.update_from_error(0, error1)
            state1 = manager.state[0].copy()

        with patch("time.time", return_value=1000.0):
            manager.update_from_error(1, error2)
            state2 = manager.state[1].copy()

        with patch("time.time", return_value=1000.0):
            manager.update_from_error(2, error3)
            state3 = manager.state[2].copy()

        # All should have same result regardless of error content
        assert state1 == state2 == state3


class TestRateLimitManagerSleep:
    """Test sleep functionality for rate limit resets."""

    @patch("time.sleep")
    @patch("time.time")
    def test_sleep_until_reset_future_reset(self, mock_time: MagicMock, mock_sleep: MagicMock) -> None:
        """Test sleeping when reset time is in the future."""
        mock_time.return_value = 1693843200.0  # Current time

        manager = RateLimitManager(default_remaining=1000, buffer=50)
        manager.ensure_key(0)
        manager.state[0]["resetAt"] = 1693843205000  # 5 seconds in the future

        manager.sleep_until_reset(0)

        # Should sleep for 5 seconds + 1 second buffer
        mock_sleep.assert_called_once_with(6.0)

    @patch("time.sleep")
    @patch("time.time")
    def test_sleep_until_reset_past_reset(self, mock_time: MagicMock, mock_sleep: MagicMock) -> None:
        """Test sleeping when reset time is in the past."""
        mock_time.return_value = 1693843200.0  # Current time

        manager = RateLimitManager(default_remaining=1000, buffer=50)
        manager.ensure_key(0)
        manager.state[0]["resetAt"] = 1693843195000  # 5 seconds in the past

        manager.sleep_until_reset(0)

        # Should sleep for 1 second (minimum)
        mock_sleep.assert_called_once_with(1.0)

    @patch("time.sleep")
    @patch("time.time")
    def test_sleep_until_reset_exact_reset_time(self, mock_time: MagicMock, mock_sleep: MagicMock) -> None:
        """Test sleeping when current time equals reset time."""
        mock_time.return_value = 1693843200.0  # Current time

        manager = RateLimitManager(default_remaining=1000, buffer=50)
        manager.ensure_key(0)
        manager.state[0]["resetAt"] = 1693843200000  # Exactly current time

        manager.sleep_until_reset(0)

        # Should sleep for 1 second (minimum)
        mock_sleep.assert_called_once_with(1.0)

    def test_sleep_until_reset_creates_key_if_needed(self) -> None:
        """Test that sleep_until_reset creates key index if it doesn't exist."""
        manager = RateLimitManager(default_remaining=1000, buffer=50)

        # Key 3 doesn't exist yet
        assert 3 not in manager.state

        with patch("time.sleep") as mock_sleep, patch("time.time", return_value=1000.0):
            manager.sleep_until_reset(3)

        assert 3 in manager.state
        mock_sleep.assert_called_once()


class TestRateLimitManagerGetters:
    """Test getter methods for rate limit state."""

    def test_get_remaining_existing_key(self) -> None:
        """Test getting remaining limit for existing key."""
        manager = RateLimitManager(default_remaining=1000, buffer=50)

        # Test keyless
        assert manager.get_remaining(-1) == 1000

        # Test after modification
        manager.state[-1]["remaining"] = 750
        assert manager.get_remaining(-1) == 750

        # Test specific key
        manager.ensure_key(0)
        manager.state[0]["remaining"] = 500
        assert manager.get_remaining(0) == 500

    def test_get_remaining_creates_key_if_needed(self) -> None:
        """Test that get_remaining creates key index if it doesn't exist."""
        manager = RateLimitManager(default_remaining=800, buffer=25)

        # Key 4 doesn't exist yet
        assert 4 not in manager.state

        remaining = manager.get_remaining(4)

        assert 4 in manager.state
        assert remaining == 800  # Should inherit from keyless

    def test_get_reset_at_existing_key(self) -> None:
        """Test getting reset timestamp for existing key."""
        manager = RateLimitManager(default_remaining=1000, buffer=50)

        # Test keyless (initially 0)
        assert manager.get_reset_at(-1) == 0

        # Test after modification
        manager.state[-1]["resetAt"] = 1693843200000
        assert manager.get_reset_at(-1) == 1693843200000

        # Test specific key
        manager.ensure_key(0)
        manager.state[0]["resetAt"] = 1693843300000
        assert manager.get_reset_at(0) == 1693843300000

    def test_get_reset_at_creates_key_if_needed(self) -> None:
        """Test that get_reset_at creates key index if it doesn't exist."""
        manager = RateLimitManager(default_remaining=800, buffer=25)

        # Key 5 doesn't exist yet
        assert 5 not in manager.state

        reset_at = manager.get_reset_at(5)

        assert 5 in manager.state
        assert reset_at == 0  # New keys always start with resetAt = 0

    def test_reset_key(self) -> None:
        """Test that reset_key restores default state."""
        manager = RateLimitManager(default_remaining=1000, buffer=50)
        manager.ensure_key(0)
        manager.state[0]["remaining"] = 100
        manager.state[0]["resetAt"] = 123
        manager.reset_key(0)
        assert manager.get_remaining(0) == 1000
        assert manager.get_reset_at(0) == 0


class TestRateLimitManagerIntegration:
    """Integration tests combining multiple rate limit operations."""

    def test_complete_rate_limit_workflow(self) -> None:
        """Test a complete workflow using multiple rate limit operations."""
        manager = RateLimitManager(default_remaining=1000, buffer=100)

        # Initial state - should have budget
        assert manager.has_budget(0, 500) is True
        assert manager.get_remaining(0) == 1000

        # Simulate API response updating state
        headers = {
            "bitvavo-ratelimit-remaining": "450",
            "bitvavo-ratelimit-resetat": "1693843300000",
        }
        manager.update_from_headers(0, headers)

        # Check updated state
        assert manager.get_remaining(0) == 450
        assert manager.get_reset_at(0) == 1693843300000

        # Check budget with new remaining
        assert manager.has_budget(0, 300) is True  # 450 - 300 = 150 > 100
        assert manager.has_budget(0, 350) is True  # 450 - 350 = 100 = 100
        assert manager.has_budget(0, 351) is False  # 450 - 351 = 99 < 100

    def test_rate_limit_error_recovery(self) -> None:
        """Test rate limit behavior after hitting an error."""
        manager = RateLimitManager(default_remaining=1000, buffer=50)

        # Start with normal state
        manager.ensure_key(0)
        manager.state[0]["remaining"] = 500

        # Simulate rate limit error
        with patch("time.time", return_value=1693843200.0):
            manager.update_from_error(0, {"error": "Rate limit exceeded"})

        # Should have no budget after error
        assert manager.get_remaining(0) == 0
        assert manager.has_budget(0, 1) is False

        # Reset time should be set
        expected_reset = int(1693843200.0 * 1000) + 60000
        assert manager.get_reset_at(0) == expected_reset

    def test_multiple_keys_independence(self) -> None:
        """Test that multiple API keys maintain independent state."""
        manager = RateLimitManager(default_remaining=1000, buffer=50)

        # Set different states for different keys
        headers1 = {"bitvavo-ratelimit-remaining": "800"}
        headers2 = {"bitvavo-ratelimit-remaining": "200"}

        manager.update_from_headers(0, headers1)
        manager.update_from_headers(1, headers2)

        # Keys should have independent remaining amounts
        assert manager.get_remaining(0) == 800
        assert manager.get_remaining(1) == 200

        # Budget checking should be independent
        assert manager.has_budget(0, 700) is True  # 800 - 700 = 100 > 50
        assert manager.has_budget(1, 700) is False  # 200 - 700 = -500 < 50

        # Error on one key shouldn't affect the other
        error_dict: dict[str, object] = {"error": "Rate limit exceeded"}
        manager.update_from_error(0, error_dict)

        assert manager.get_remaining(0) == 0  # Affected by error
        assert manager.get_remaining(1) == 200  # Unaffected

    def test_keyless_vs_keyed_requests(self) -> None:
        """Test behavior differences between keyless and keyed requests."""
        manager = RateLimitManager(default_remaining=500, buffer=25)

        # Initially both keyless and new keys have same state
        assert manager.get_remaining(-1) == 500
        assert manager.get_remaining(0) == 500  # Inherits from keyless

        # Update keyless state
        headers_keyless = {"bitvavo-ratelimit-remaining": "300"}
        manager.update_from_headers(-1, headers_keyless)

        # Update keyed state
        headers_keyed = {"bitvavo-ratelimit-remaining": "400"}
        manager.update_from_headers(0, headers_keyed)

        # States should now be independent
        assert manager.get_remaining(-1) == 300
        assert manager.get_remaining(0) == 400

        # New keys should still inherit from keyless
        assert manager.get_remaining(1) == 300  # Inherits current keyless state

    @patch("time.sleep")
    @patch("time.time")
    def test_sleep_and_recovery_workflow(self, mock_time: MagicMock, mock_sleep: MagicMock) -> None:
        """Test workflow involving sleeping and state recovery."""
        mock_time.return_value = 1693843200.0

        manager = RateLimitManager(default_remaining=1000, buffer=50)

        # Simulate hitting rate limit
        error_dict: dict[str, object] = {"error": "Rate limit exceeded"}
        manager.update_from_error(0, error_dict)

        # Should have no budget
        assert manager.has_budget(0, 1) is False

        # Sleep until reset
        manager.sleep_until_reset(0)
        mock_sleep.assert_called_once()

        # Simulate time passing and API response after reset
        mock_time.return_value = 1693843261.0  # After reset time
        headers = {"bitvavo-ratelimit-remaining": "1000"}
        manager.update_from_headers(0, headers)

        # Should have budget again
        assert manager.get_remaining(0) == 1000
        assert manager.has_budget(0, 900) is True


class TestRateLimitStrategy:
    """Test custom rate limit strategy invocation."""

    def test_custom_strategy_called(self) -> None:
        """Ensure custom strategy is invoked when handle_limit is called."""
        called: list[tuple[int, int]] = []

        def strategy(manager: RateLimitManager, idx: int, weight: int) -> None:
            called.append((idx, weight))

        manager = RateLimitManager(default_remaining=100, buffer=0, strategy=strategy)
        manager.handle_limit(2, 5)
        assert called == [(2, 5)]
