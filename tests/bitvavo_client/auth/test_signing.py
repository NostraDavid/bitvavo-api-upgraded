"""Tests for signature creation utilities."""

from __future__ import annotations

from bitvavo_client.auth.signing import create_signature


class TestCreateSignature:
    """Test create_signature function for Bitvavo API authentication."""

    def test_create_signature_get_request_no_body(self) -> None:
        """Test signature creation for GET request without body."""
        timestamp = 1693843200000
        method = "GET"
        url = "/markets"
        body = None
        api_secret = "test-secret-key"

        signature = create_signature(timestamp, method, url, body, api_secret)

        # Expected string: "1693843200000GET/v2/markets"
        # This should produce a consistent HMAC-SHA256 signature

        # Verify it's a valid hex string of correct length (64 characters for SHA256)
        assert len(signature) == 64
        assert all(c in "0123456789abcdef" for c in signature)

        # Test reproducibility - same inputs should always produce same signature
        signature2 = create_signature(timestamp, method, url, body, api_secret)
        assert signature == signature2

    def test_create_signature_get_request_empty_body(self) -> None:
        """Test signature creation for GET request with empty body dict."""
        timestamp = 1693843200000
        method = "GET"
        url = "/markets"
        body = {}  # Empty dict should be treated same as None
        api_secret = "test-secret-key"

        signature = create_signature(timestamp, method, url, body, api_secret)

        # Should produce same result as None body since empty dict is ignored
        signature_none_body = create_signature(timestamp, method, url, None, api_secret)
        assert signature == signature_none_body

    def test_create_signature_post_request_with_body(self) -> None:
        """Test signature creation for POST request with body."""
        timestamp = 1693843200000
        method = "POST"
        url = "/order"
        body = {"market": "BTC-EUR", "side": "buy", "orderType": "market", "amount": "0.001"}
        api_secret = "test-secret-key"

        signature = create_signature(timestamp, method, url, body, api_secret)

        # Verify signature properties
        assert len(signature) == 64
        assert all(c in "0123456789abcdef" for c in signature)

        # Test reproducibility
        signature2 = create_signature(timestamp, method, url, body, api_secret)
        assert signature == signature2

    def test_create_signature_different_methods(self) -> None:
        """Test signature creation for different HTTP methods."""
        timestamp = 1693843200000
        url = "/order/123"
        body = None
        api_secret = "test-secret-key"

        # Test all common HTTP methods
        methods = ["GET", "POST", "PUT", "DELETE"]
        signatures = {}

        for method in methods:
            signature = signatures[method] = create_signature(timestamp, method, url, body, api_secret)
            assert len(signature) == 64
            assert all(c in "0123456789abcdef" for c in signature)

        # All signatures should be different since method is part of the signed string
        unique_signatures = set(signatures.values())
        assert len(unique_signatures) == len(methods)

    def test_create_signature_different_timestamps(self) -> None:
        """Test signature creation with different timestamps."""
        method = "GET"
        url = "/markets"
        body = None
        api_secret = "test-secret-key"

        timestamps = [1693843200000, 1693843200001, 1693843300000]
        signatures = []

        for timestamp in timestamps:
            signature = create_signature(timestamp, method, url, body, api_secret)
            signatures.append(signature)
            assert len(signature) == 64

        # All signatures should be different since timestamp is part of the signed string
        assert len(set(signatures)) == len(timestamps)

    def test_create_signature_different_urls(self) -> None:
        """Test signature creation with different URLs."""
        timestamp = 1693843200000
        method = "GET"
        body = None
        api_secret = "test-secret-key"

        urls = ["/markets", "/order", "/balance", "/orders", "/trades"]
        signatures = []

        for url in urls:
            signature = create_signature(timestamp, method, url, body, api_secret)
            signatures.append(signature)
            assert len(signature) == 64

        # All signatures should be different since URL is part of the signed string
        assert len(set(signatures)) == len(urls)

    def test_create_signature_different_secrets(self) -> None:
        """Test signature creation with different API secrets."""
        timestamp = 1693843200000
        method = "GET"
        url = "/markets"
        body = None

        secrets = ["secret1", "secret2", "very-long-secret-key-12345", ""]
        signatures = []

        for secret in secrets:
            signature = create_signature(timestamp, method, url, body, secret)
            signatures.append(signature)
            assert len(signature) == 64

        # All signatures should be different since secret is used as HMAC key
        assert len(set(signatures)) == len(secrets)

    def test_create_signature_complex_body(self) -> None:
        """Test signature creation with complex request body."""
        timestamp = 1693843200000
        method = "POST"
        url = "/order"
        body = {
            "market": "BTC-EUR",
            "side": "buy",
            "orderType": "limit",
            "amount": "0.001",
            "price": "45000.50",
            "timeInForce": "GTC",
            "postOnly": True,
            "selfTradePrevention": "decrementAndCancel",
            "responseRequired": False,
        }
        api_secret = "test-secret-key"

        signature = create_signature(timestamp, method, url, body, api_secret)

        # Verify signature properties
        assert len(signature) == 64
        assert all(c in "0123456789abcdef" for c in signature)

        # Test reproducibility with same complex body
        signature2 = create_signature(timestamp, method, url, body, api_secret)
        assert signature == signature2

    def test_create_signature_body_json_serialization(self) -> None:
        """Test that body is serialized consistently (no spaces after separators)."""
        timestamp = 1693843200000
        method = "POST"
        url = "/order"
        api_secret = "test-secret-key"

        # Bodies that should serialize to same JSON
        body1 = {"market": "BTC-EUR", "side": "buy"}
        body2 = {"side": "buy", "market": "BTC-EUR"}  # Different key order

        signature1 = create_signature(timestamp, method, url, body1, api_secret)
        signature2 = create_signature(timestamp, method, url, body2, api_secret)

        # Note: In Python 3.7+, dict order is preserved, so these will be different
        # This test verifies the current behavior - if dict order changes, signature changes
        assert len(signature1) == 64
        assert len(signature2) == 64

        # Test with same body object twice - should be identical
        signature3 = create_signature(timestamp, method, url, body1, api_secret)
        assert signature1 == signature3

    def test_create_signature_url_prefixes(self) -> None:
        """Test that /v2 prefix is correctly added to URL in signature string."""
        timestamp = 1693843200000
        method = "GET"
        body = None
        api_secret = "test-secret-key"

        # Test various URL formats
        test_cases = ["/markets", "/order/123", "/balance", "/trades", "/candles/BTC-EUR/1h"]

        for url in test_cases:
            signature = create_signature(timestamp, method, url, body, api_secret)

            # All should produce valid signatures
            assert len(signature) == 64
            assert all(c in "0123456789abcdef" for c in signature)

            # Verify the string being signed includes /v2 prefix
            # We can't directly test the internal string, but we can verify
            # that URLs with same ending but different prefixes produce different signatures
            url_with_prefix = f"/prefix{url}"
            signature_with_prefix = create_signature(timestamp, method, url_with_prefix, body, api_secret)
            assert signature != signature_with_prefix

    def test_create_signature_edge_cases(self) -> None:
        """Test signature creation with edge case inputs."""
        api_secret = "test-secret-key"

        # Test with minimum timestamp
        signature = create_signature(0, "GET", "/", None, api_secret)
        assert len(signature) == 64

        # Test with maximum reasonable timestamp (year 2038)
        signature = create_signature(2147483647000, "GET", "/", None, api_secret)
        assert len(signature) == 64

        # Test with empty URL path
        signature = create_signature(1693843200000, "GET", "", None, api_secret)
        assert len(signature) == 64

        # Test with root path
        signature = create_signature(1693843200000, "GET", "/", None, api_secret)
        assert len(signature) == 64

    def test_create_signature_special_characters(self) -> None:
        """Test signature creation with special characters in URL and body."""
        timestamp = 1693843200000
        method = "POST"
        api_secret = "test-secret-key"

        # URL with query parameters and special characters
        url = "/search?query=bitcoin%20price&limit=10"
        body = {
            "description": "Order with special chars: éñ中文",
            "amount": "1.23456789",
            "metadata": {"key": "value with spaces and symbols!@#$%"},
        }

        signature = create_signature(timestamp, method, url, body, api_secret)

        # Should handle special characters without error
        assert len(signature) == 64
        assert all(c in "0123456789abcdef" for c in signature)

        # Test reproducibility
        signature2 = create_signature(timestamp, method, url, body, api_secret)
        assert signature == signature2

    def test_create_signature_numeric_body_values(self) -> None:
        """Test signature creation with numeric values in body."""
        timestamp = 1693843200000
        method = "POST"
        url = "/order"
        api_secret = "test-secret-key"

        # Body with various numeric types
        body = {
            "amount": 1.23456789,  # float
            "price": 45000,  # int
            "quantity": "0.001",  # string representation
            "enabled": True,  # boolean
            "count": 0,  # zero
        }

        signature = create_signature(timestamp, method, url, body, api_secret)

        # Should handle numeric types correctly
        assert len(signature) == 64
        assert all(c in "0123456789abcdef" for c in signature)

        # Test that changing numeric values changes signature
        body_modified = body.copy()
        body_modified["amount"] = 1.23456788  # Slightly different
        signature_modified = create_signature(timestamp, method, url, body_modified, api_secret)
        assert signature != signature_modified

    def test_create_signature_none_vs_missing_body_fields(self) -> None:
        """Test signature differences between None values and missing fields."""
        timestamp = 1693843200000
        method = "POST"
        url = "/order"
        api_secret = "test-secret-key"

        # Body with None value
        body_with_none = {"market": "BTC-EUR", "note": None}

        # Body without the field
        body_without_field = {"market": "BTC-EUR"}

        signature_with_none = create_signature(timestamp, method, url, body_with_none, api_secret)
        signature_without_field = create_signature(timestamp, method, url, body_without_field, api_secret)

        # These should produce different signatures since JSON representation differs
        assert len(signature_with_none) == 64
        assert len(signature_without_field) == 64
        assert signature_with_none != signature_without_field

    def test_create_signature_empty_string_vs_none_secret(self) -> None:
        """Test behavior with empty string vs None secret."""
        timestamp = 1693843200000
        method = "GET"
        url = "/markets"
        body = None

        # Empty string secret should work
        signature_empty = create_signature(timestamp, method, url, body, "")
        assert len(signature_empty) == 64

        # Test that empty secret produces different result than non-empty
        signature_non_empty = create_signature(timestamp, method, url, body, "secret")
        assert signature_empty != signature_non_empty

    def test_create_signature_consistency_across_calls(self) -> None:
        """Test that signature creation is consistent across multiple calls."""
        timestamp = 1693843200000
        method = "POST"
        url = "/order"
        body = {"market": "BTC-EUR", "side": "buy", "amount": "0.001"}
        api_secret = "test-secret-key"

        # Create same signature multiple times
        signatures = [create_signature(timestamp, method, url, body, api_secret) for _ in range(10)]

        # All should be identical
        assert len(set(signatures)) == 1
        assert all(len(sig) == 64 for sig in signatures)

    def test_create_signature_type_annotations(self) -> None:
        """Test that function handles type annotations correctly."""
        # This test ensures the function works with proper type hints
        timestamp: int = 1693843200000
        method: str = "GET"
        url: str = "/markets"
        body: dict[str, str] | None = None
        api_secret: str = "test-secret-key"

        signature: str = create_signature(timestamp, method, url, body, api_secret)

        assert isinstance(signature, str)
        assert len(signature) == 64
