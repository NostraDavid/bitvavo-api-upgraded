"""Tests for BitvavoClient facade class."""

from __future__ import annotations

import os
from typing import Any
from unittest.mock import Mock, patch

import pytest
from pydantic_settings import SettingsConfigDict
from returns.result import Failure, Success

from bitvavo_client.adapters.returns_adapter import BitvavoError
from bitvavo_client.core.model_preferences import ModelPreference
from bitvavo_client.core.settings import BitvavoSettings
from bitvavo_client.endpoints.private import PrivateAPI
from bitvavo_client.endpoints.public import PublicAPI
from bitvavo_client.facade import BitvavoClient


class TestBitvavoSettings(BitvavoSettings):
    """Test-specific BitvavoSettings that disables ALL environment loading."""

    model_config = SettingsConfigDict(
        env_file=None,  # Disable .env file loading
        env_prefix="",  # Disable env var prefix to prevent env loading
        extra="ignore",
    )

    def __init__(self, **kwargs: Any) -> None:
        """Initialize without any environment variable loading."""
        # Temporarily clear environment variables that might interfere
        original_env = {}
        bitvavo_vars = [key for key in os.environ if key.startswith("BITVAVO_")]
        for var in bitvavo_vars:
            original_env[var] = os.environ.pop(var)

        try:
            kwargs.setdefault("api_keys", [{"key": "k", "secret": "s"}])
            super().__init__(**kwargs)
        finally:
            # Restore original environment
            for var, value in original_env.items():
                os.environ[var] = value


class TestBitvavoClientInitialization:
    def test_init_custom_settings(self) -> None:
        """Test initialization with custom settings."""
        custom_settings = TestBitvavoSettings(
            rest_url="https://custom.api.com/v2",
            debugging=True,
            default_rate_limit=500,
        )

        client = BitvavoClient(custom_settings)

        assert client.settings is custom_settings
        assert client.settings.rest_url == "https://custom.api.com/v2"
        assert client.settings.debugging is True
        assert client.settings.default_rate_limit == 500

    def test_init_with_preferred_model(self) -> None:
        """Test initialization with preferred model parameter."""
        client = BitvavoClient(settings=TestBitvavoSettings(), preferred_model=ModelPreference.PYDANTIC)

        # Should pass preferred_model to API endpoints
        assert client.public.preferred_model == ModelPreference.PYDANTIC
        assert client.private.preferred_model == ModelPreference.PYDANTIC

    def test_init_with_preferred_model_string(self) -> None:
        """Test initialization with preferred model as string."""
        client = BitvavoClient(settings=TestBitvavoSettings(), preferred_model="dataframe")

        # Should accept string and pass to API endpoints
        assert client.public.preferred_model == "dataframe"
        assert client.private.preferred_model == "dataframe"

    def test_init_with_default_schema(self) -> None:
        """Test initialization with default schema parameter."""
        schema = {"field1": "type1", "field2": "type2"}
        client = BitvavoClient(settings=TestBitvavoSettings(), default_schema=schema)

        # Should pass schema to API endpoints
        assert client.public.default_schema is schema
        assert client.private.default_schema is schema

    def test_init_with_all_parameters(self) -> None:
        """Test initialization with all optional parameters."""
        # Create settings with test values using api_keys
        settings = TestBitvavoSettings(api_keys=[{"key": "test_key", "secret": "test_secret"}])
        schema = {"market": str, "price": float}

        client = BitvavoClient(
            settings=settings,
            preferred_model=ModelPreference.RAW,
            default_schema=schema,
        )

        assert client.settings is settings
        assert client.public.preferred_model == ModelPreference.RAW
        assert client.private.preferred_model == ModelPreference.RAW
        assert client.public.default_schema is schema
        assert client.private.default_schema is schema


class TestBitvavoClientAPIKeyConfiguration:
    """Test API key configuration in BitvavoClient."""

    def test_configure_single_api_key(self) -> None:
        """Test configuration with a single API key."""
        settings = TestBitvavoSettings(api_keys=[{"key": "test_key", "secret": "test_secret"}])
        client = BitvavoClient(settings)
        assert client.http.api_key == "test_key"
        assert client.http.key_index == 0

    def test_configure_multiple_api_keys(self) -> None:
        """Test configuration with multiple API keys."""
        settings = TestBitvavoSettings(
            api_keys=[
                {"key": "key1", "secret": "secret1"},
                {"key": "key2", "secret": "secret2"},
            ],
        )
        client = BitvavoClient(settings)
        assert client.http.api_key == "key1"
        assert client.http.key_index == 0
        assert 0 in client.rate_limiter.state
        assert 1 in client.rate_limiter.state

    def test_no_api_keys(self) -> None:
        """Test initialization without API keys."""
        settings = TestBitvavoSettings(api_keys=[])
        with pytest.raises(ValueError, match="API keys are required"):
            BitvavoClient(settings)

    def test_empty_api_keys_list(self) -> None:
        """Test initialization with empty API keys list."""
        settings = TestBitvavoSettings(api_keys=[])
        with pytest.raises(ValueError, match="API keys are required"):
            BitvavoClient(settings)


class TestBitvavoClientComponentIntegration:
    """Test integration between BitvavoClient components."""

    def test_http_client_receives_settings_and_rate_limiter(self) -> None:
        """Test that HTTPClient is initialized with correct dependencies."""
        settings = TestBitvavoSettings(rest_url="https://test.api.com")
        client = BitvavoClient(settings)

        # HTTPClient should have references to settings and rate limiter
        assert client.http.settings is settings
        assert client.http.rate_limiter is client.rate_limiter

    def test_api_endpoints_receive_http_client(self) -> None:
        """Test that API endpoints are initialized with HTTPClient."""
        client = BitvavoClient(TestBitvavoSettings())

        # Both API endpoints should receive the same HTTP client
        assert client.public.http is client.http
        assert client.private.http is client.http

    def test_api_endpoints_receive_preferences(self) -> None:
        """Test that API endpoints receive preference parameters."""
        schema = {"test": "schema"}
        client = BitvavoClient(
            settings=TestBitvavoSettings(),
            preferred_model=ModelPreference.POLARS,
            default_schema=schema,
        )

        # Both endpoints should have the same preferences
        assert client.public.preferred_model == ModelPreference.POLARS
        assert client.private.preferred_model == ModelPreference.POLARS
        assert client.public.default_schema is schema
        assert client.private.default_schema is schema


class TestBitvavoClientPublicAPIAccess:
    """Test accessing public API methods through the client."""

    @patch("bitvavo_client.endpoints.public.PublicAPI.time")
    def test_time_access(self, mock_time: Mock) -> None:
        """Test accessing time endpoint through client."""
        mock_time.return_value = Success({"time": 1234567890, "timeNs": 1234567890123456})

        client = BitvavoClient(TestBitvavoSettings())
        result = client.public.time()

        mock_time.assert_called_once()
        assert isinstance(result, Success)

    @patch("bitvavo_client.endpoints.public.PublicAPI.markets")
    def test_markets_access(self, mock_markets: Mock) -> None:
        """Test accessing markets endpoint through client."""
        mock_markets.return_value = Success([{"market": "BTC-EUR", "status": "trading"}])

        client = BitvavoClient(TestBitvavoSettings())
        result = client.public.markets()

        mock_markets.assert_called_once()
        assert isinstance(result, Success)

    @patch("bitvavo_client.endpoints.public.PublicAPI.ticker_price")
    def test_ticker_price_with_parameters(self, mock_ticker: Mock) -> None:
        """Test accessing ticker price with parameters through client."""
        mock_ticker.return_value = Success([{"market": "BTC-EUR", "price": "50000"}])

        client = BitvavoClient(TestBitvavoSettings())
        result = client.public.ticker_price({"market": "BTC-EUR"})

        mock_ticker.assert_called_once_with({"market": "BTC-EUR"})
        assert isinstance(result, Success)


class TestBitvavoClientPrivateAPIAccess:
    """Test accessing private API methods through the client."""

    @patch("bitvavo_client.endpoints.private.PrivateAPI.account")
    def test_account_access(self, mock_account: Mock) -> None:
        """Test accessing account endpoint through client."""
        mock_account.return_value = Success({"fees": {"taker": "0.0025", "maker": "0.0015"}})

        client = BitvavoClient(TestBitvavoSettings())
        result = client.private.account()

        mock_account.assert_called_once()
        assert isinstance(result, Success)

    @patch("bitvavo_client.endpoints.private.PrivateAPI.balance")
    def test_balance_access(self, mock_balance: Mock) -> None:
        """Test accessing balance endpoint through client."""
        mock_balance.return_value = Success([{"symbol": "EUR", "available": "1000.00"}])

        client = BitvavoClient(TestBitvavoSettings())
        result = client.private.balance()

        mock_balance.assert_called_once()
        assert isinstance(result, Success)

    @patch("bitvavo_client.endpoints.private.PrivateAPI.get_order")
    def test_get_order_with_parameters(self, mock_get_order: Mock) -> None:
        """Test accessing get_order endpoint with parameters through client."""
        mock_get_order.return_value = Success({"orderId": "12345", "status": "filled"})

        client = BitvavoClient(TestBitvavoSettings())
        result = client.private.get_order("BTC-EUR", "67890")

        mock_get_order.assert_called_once_with("BTC-EUR", "67890")
        assert isinstance(result, Success)


class TestBitvavoClientErrorHandling:
    """Test error handling in BitvavoClient."""

    @patch("bitvavo_client.endpoints.public.PublicAPI.time")
    def test_public_api_error_propagation(self, mock_time: Mock) -> None:
        """Test that public API errors are properly propagated."""
        error = BitvavoError(http_status=500, error_code=1000, reason="Server Error", message="Internal error", raw={})
        mock_time.return_value = Failure(error)

        client = BitvavoClient(TestBitvavoSettings())
        result = client.public.time()

        assert isinstance(result, Failure)
        assert result.failure() is error

    @patch("bitvavo_client.endpoints.private.PrivateAPI.account")
    def test_private_api_error_propagation(self, mock_account: Mock) -> None:
        """Test that private API errors are properly propagated."""
        error = BitvavoError(http_status=401, error_code=1001, reason="Unauthorized", message="Auth failed", raw={})
        mock_account.return_value = Failure(error)

        client = BitvavoClient(TestBitvavoSettings())
        result = client.private.account()

        assert isinstance(result, Failure)
        assert result.failure() is error


class TestBitvavoClientRealWorldUsage:
    """Test realistic usage patterns of BitvavoClient."""

    def test_basic_public_api_workflow(self) -> None:
        """Test a basic workflow using only public API."""
        with patch.multiple(
            "bitvavo_client.endpoints.public.PublicAPI",
            time=Mock(return_value=Success({"time": 1234567890})),
            markets=Mock(return_value=Success([{"market": "BTC-EUR"}])),
            ticker_price=Mock(return_value=Success([{"market": "BTC-EUR", "price": "50000"}])),
        ):
            client = BitvavoClient(TestBitvavoSettings())

            # Get server time
            time_result = client.public.time()
            assert isinstance(time_result, Success)

            # Get available markets
            markets_result = client.public.markets()
            assert isinstance(markets_result, Success)

            # Get ticker price for BTC-EUR
            price_result = client.public.ticker_price({"market": "BTC-EUR"})
            assert isinstance(price_result, Success)

    def test_authenticated_workflow(self) -> None:
        """Test a workflow requiring authentication."""
        with patch.multiple(
            "bitvavo_client.endpoints.private.PrivateAPI",
            account=Mock(return_value=Success({"fees": {}})),
            balance=Mock(return_value=Success([{"symbol": "EUR", "available": "1000"}])),
        ):
            # Create client with API credentials using api_keys
            settings = TestBitvavoSettings(
                api_keys=[{"key": "test_key", "secret": "test_secret"}],
            )
            client = BitvavoClient(settings)

            # Get account information
            account_result = client.private.account()
            assert isinstance(account_result, Success)

            # Get account balance
            balance_result = client.private.balance()
            assert isinstance(balance_result, Success)

    def test_model_preference_workflow(self) -> None:
        """Test workflow with specific model preferences."""
        with patch.multiple(
            "bitvavo_client.endpoints.public.PublicAPI",
            ticker_price=Mock(return_value=Success([{"market": "BTC-EUR", "price": "50000"}])),
        ):
            # Create client with Pydantic model preference
            client = BitvavoClient(
                settings=TestBitvavoSettings(),
                preferred_model=ModelPreference.PYDANTIC,
            )

            # Make API call - should use Pydantic models
            result = client.public.ticker_price()
            assert isinstance(result, Success)

            # Verify the preference was passed to the endpoint
            assert client.public.preferred_model == ModelPreference.PYDANTIC

    def test_multiple_clients_independence(self) -> None:
        """Test that multiple client instances are independent."""
        # Create two clients with different settings
        settings1 = TestBitvavoSettings(default_rate_limit=500)
        settings2 = TestBitvavoSettings(default_rate_limit=1000)

        client1 = BitvavoClient(settings1, preferred_model=ModelPreference.RAW)
        client2 = BitvavoClient(settings2, preferred_model=ModelPreference.PYDANTIC)

        # Clients should have independent settings and components
        assert client1.settings is not client2.settings
        assert client1.settings.default_rate_limit == 500
        assert client2.settings.default_rate_limit == 1000

        assert client1.public.preferred_model == ModelPreference.RAW
        assert client2.public.preferred_model == ModelPreference.PYDANTIC

        assert client1.http is not client2.http
        assert client1.rate_limiter is not client2.rate_limiter


class TestBitvavoClientTypeCompatibility:
    """Test type compatibility and parameter passing."""

    def test_none_preferred_model_parameter(self) -> None:
        """Test that None preferred_model parameter is handled correctly."""
        client = BitvavoClient(settings=TestBitvavoSettings(), preferred_model=None)

        # Should pass None to API endpoints
        assert client.public.preferred_model is None
        assert client.private.preferred_model is None

    def test_none_default_schema_parameter(self) -> None:
        """Test that None default_schema parameter is handled correctly."""
        client = BitvavoClient(settings=TestBitvavoSettings(), default_schema=None)

        # Should pass None to API endpoints
        assert client.public.default_schema is None
        assert client.private.default_schema is None

    def test_string_model_preference_handling(self) -> None:
        """Test that string model preferences are passed correctly."""
        client = BitvavoClient(settings=TestBitvavoSettings(), preferred_model="raw")

        assert client.public.preferred_model == "raw"
        assert client.private.preferred_model == "raw"


class TestBitvavoClientDocumentation:
    """Test that BitvavoClient behavior matches its docstring."""

    def test_backward_compatible_interface_claim(self) -> None:
        """Test that the client provides backward-compatible interface."""
        client = BitvavoClient(TestBitvavoSettings())
        assert hasattr(client, "public")
        assert hasattr(client, "private")
        assert isinstance(client.public, PublicAPI)
        assert isinstance(client.private, PrivateAPI)

    def test_facade_pattern_implementation(self) -> None:
        """Test that the client implements the facade pattern correctly."""
        client = BitvavoClient(TestBitvavoSettings())
        assert hasattr(client, "settings")
        assert hasattr(client, "rate_limiter")
        assert hasattr(client, "http")
        assert hasattr(client, "public")
        assert hasattr(client, "private")
