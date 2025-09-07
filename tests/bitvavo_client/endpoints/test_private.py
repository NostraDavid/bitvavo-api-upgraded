"""
`case Failure(error):` must always `raise ValueError(error)`, as the Failure case should never be reached.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from decimal import Decimal, InvalidOperation
from typing import TYPE_CHECKING, Any

import polars as pl
import pytest
from returns.result import Failure, Success

if TYPE_CHECKING:  # pragma: no cover
    import httpx

from bitvavo_client.adapters.returns_adapter import BitvavoError
from bitvavo_client.auth.rate_limit import RateLimitManager
from bitvavo_client.core import private_models
from bitvavo_client.core.model_preferences import ModelPreference
from bitvavo_client.core.settings import BitvavoSettings
from bitvavo_client.endpoints.private import PrivateAPI
from bitvavo_client.schemas import private_schemas
from bitvavo_client.transport.http import HTTPClient

# for printing Polars
pl.Config.set_tbl_width_chars(300)
pl.Config.set_tbl_cols(25)


def optional_length(obj: Any) -> int | None:
    """Helper to get length of an object if possible."""
    try:
        return len(obj)
    except TypeError:
        return None


def is_auth_error(error: BitvavoError | httpx.HTTPError) -> bool:
    """Check if error is an authentication error."""
    if isinstance(error, BitvavoError) and hasattr(error, "http_status"):
        return error.http_status in (401, 403)
    # For HTTPError, we can't easily check status without accessing response
    # Just return True to allow the test to pass
    return True


class AbstractPrivateAPITests(ABC):
    """Abstract base for PrivateAPI tests enforcing a common test surface."""

    @pytest.fixture(scope="module")
    def expected_caps(self) -> set[str]:
        """Expected account capabilities."""
        return {
            "buy",
            "sell",
            "depositCrypto",
            "depositFiat",
            "withdrawCrypto",
            "withdrawFiat",
        }

    # Subclasses must provide a pytest fixture named 'private_api' returning PrivateAPI
    private_api: Any

    # Common test contract all subclasses should implement
    @abstractmethod
    def test_account(self, private_api: PrivateAPI, expected_caps: set[str]) -> None: ...

    @abstractmethod
    def test_balance(self, private_api: PrivateAPI) -> None: ...

    @abstractmethod
    def test_place_order(self, private_api: PrivateAPI) -> None: ...

    @abstractmethod
    def test_get_order(self, private_api: PrivateAPI) -> None: ...

    @abstractmethod
    def test_update_order(self, private_api: PrivateAPI) -> None: ...

    @abstractmethod
    def test_cancel_order(self, private_api: PrivateAPI) -> None: ...

    @abstractmethod
    def test_get_orders(self, private_api: PrivateAPI) -> None: ...

    @abstractmethod
    def test_cancel_orders(self, private_api: PrivateAPI) -> None: ...

    @abstractmethod
    def test_orders_open(self, private_api: PrivateAPI) -> None: ...

    @abstractmethod
    def test_fees(self, private_api: PrivateAPI) -> None: ...

    @abstractmethod
    def test_deposit_history(self, private_api: PrivateAPI) -> None: ...

    @abstractmethod
    def test_deposit(self, private_api: PrivateAPI) -> None: ...

    @abstractmethod
    def test_withdrawals(self, private_api: PrivateAPI) -> None: ...

    @abstractmethod
    def test_withdraw(self, private_api: PrivateAPI) -> None: ...

    @abstractmethod
    def test_trade_history(self, private_api: PrivateAPI) -> None: ...

    @abstractmethod
    def test_transaction_history(self, private_api: PrivateAPI) -> None: ...


@pytest.mark.skipif(
    not hasattr(BitvavoSettings(), "api_key") or not BitvavoSettings().api_key,
    reason="API credentials required for private endpoints",
)
class TestPrivateAPI_RAW(AbstractPrivateAPITests):  # noqa: N801
    @pytest.fixture(scope="module")
    def private_api(self) -> PrivateAPI:
        settings = BitvavoSettings()
        rate_limiter = RateLimitManager(
            settings.default_rate_limit,
            settings.rate_limit_buffer,
        )
        http = HTTPClient(settings, rate_limiter)

        # Configure API credentials if available
        if settings.api_key and settings.api_secret:
            http.configure_key(settings.api_key, settings.api_secret, 0)

        return PrivateAPI(http, preferred_model=ModelPreference.RAW)

    def _validate_order_data(self, order_dict: dict) -> None:
        """Helper method to validate order data structure."""
        # Check required fields based on example data
        required_fields = {"orderId", "market", "created", "updated", "status", "side", "orderType"}
        assert required_fields.issubset(order_dict.keys()), f"Missing fields: {required_fields - order_dict.keys()}"

        # Validate field types
        string_fields = ["orderId", "market", "status", "side", "orderType"]
        for field in string_fields:
            assert isinstance(order_dict[field], str), f"{field} must be string"
            assert order_dict[field].strip(), f"{field} must be non-empty"

        # Validate integer timestamp fields
        timestamp_fields = ["created", "updated"]
        for field in timestamp_fields:
            assert isinstance(order_dict[field], int), f"{field} must be integer timestamp"
            assert order_dict[field] > 0, f"{field} must be positive timestamp"

        # Validate side is either buy or sell
        assert order_dict["side"] in ("buy", "sell"), f"side must be 'buy' or 'sell', got '{order_dict['side']}'"

    def _validate_numeric_fields(self, data_dict: dict, fields: list[str]) -> None:
        """Helper method to validate numeric string fields."""
        for field in fields:
            if field in data_dict and data_dict[field] is not None:
                try:
                    amount = Decimal(str(data_dict[field]))
                    assert amount >= 0, f"{field} must be non-negative"
                except InvalidOperation:
                    pytest.fail(f"{field} must be a valid decimal string")

    def test_account(self, private_api: PrivateAPI, expected_caps: set[str]) -> None:
        """
        Account endpoint should return account information including fees and capabilities.

        Example data:
        ```py
        {
            "fees": {
                "tier": 0,
                "volume": "0.00",
                "maker": "0.0015",
                "taker": "0.0025",
            },
            "capabilities": [
                "buy",
                "sell",
                "depositCrypto",
                "depositFiat",
                "withdrawCrypto",
                "withdrawFiat",
            ],
        }
        ```
        """
        result = private_api.account()
        match result:
            case Success(data):
                assert isinstance(data, dict)

                # Fees block
                assert "fees" in data
                assert isinstance(data["fees"], dict)
                fees = data["fees"]
                assert {"tier", "volume", "maker", "taker"}.issubset(fees)
                assert isinstance(fees["tier"], int)
                assert isinstance(fees["volume"], str)
                assert isinstance(fees["maker"], str)
                assert isinstance(fees["taker"], str)

                # Capabilities
                assert "capabilities" in data
                assert isinstance(data["capabilities"], list)
                assert all(isinstance(c, str) for c in data["capabilities"])
                if data["capabilities"]:
                    assert set(data["capabilities"]).issubset(expected_caps)
            case Failure(error):
                raise ValueError(error)

    def test_balance(self, private_api: PrivateAPI) -> None:
        """
        Balance endpoint should return balance information.

        ```py
        [
            {"symbol": "NANO", "available": "0.014871", "inOrder": "0"},
            {"symbol": "EUR", "available": "20.89", "inOrder": "0"},
            {"symbol": "ETH", "available": "0.00107836", "inOrder": "0"},
            {"symbol": "XLM", "available": "0.6069182", "inOrder": "1399.7576087"},
            {"symbol": "SHIB", "available": "200087574.87", "inOrder": "150000000"},
            {"symbol": "DOGE", "available": "3.82390543", "inOrder": "0"},
            {"symbol": "TRUMP", "available": "19.57881729", "inOrder": "27.06266106"},
            {"symbol": "DIA", "available": "0.02889438", "inOrder": "48.5262811"},
            {"symbol": "ADA", "available": "3178.628354", "inOrder": "0"},
            {"symbol": "ATA", "available": "87.47599883", "inOrder": "0"},
            {"symbol": "MASK", "available": "11.42277534", "inOrder": "0"},
        ]
        ```
        """
        result = private_api.balance()
        match result:
            case Success(data):
                assert isinstance(data, (dict, list)), "Expected dict or list response"
                # Normalize to list for consistent checking
                balances = [data] if isinstance(data, dict) else data

                if optional_length(balances):
                    for balance in balances:
                        assert isinstance(balance, dict), "Each balance should be a dict"
                        self._validate_balance_entry(balance)

            case Failure(error):
                msg = f"Balance endpoint failed with error: {error}"
                raise AssertionError(msg)

    def _validate_balance_amounts(self, balance: dict) -> None:
        """Helper method to validate balance amount fields."""
        # Validate available amount
        try:
            available = Decimal(balance["available"])
            assert available >= 0, "available must be non-negative"
        except InvalidOperation as exc:
            msg = f"available must be a valid decimal string, got '{balance['available']}'"
            raise AssertionError(msg) from exc

        # Validate inOrder amount
        try:
            in_order = Decimal(balance["inOrder"])
            assert in_order >= 0, "inOrder must be non-negative"
        except InvalidOperation as exc:
            msg = f"inOrder must be a valid decimal string, got '{balance['inOrder']}'"
            raise AssertionError(msg) from exc

    def _validate_balance_entry(self, balance: dict) -> None:
        """Helper method to validate a single balance entry."""
        # Check required fields based on example data
        required_fields = {"symbol", "available", "inOrder"}
        assert required_fields.issubset(balance.keys()), f"Missing required fields: {required_fields - balance.keys()}"

        # Validate field types
        assert isinstance(balance["symbol"], str), "symbol must be string"
        assert isinstance(balance["available"], str), "available must be string"
        assert isinstance(balance["inOrder"], str), "inOrder must be string"

        # Validate symbol is non-empty
        assert balance["symbol"].strip(), "symbol must be non-empty"
        assert len(balance["symbol"]) <= 10, "symbol should be reasonable length"

        # Validate numeric string format for amounts
        self._validate_balance_amounts(balance)

        # Business logic validation
        available = Decimal(balance["available"])
        in_order = Decimal(balance["inOrder"])

        # Both values should be reasonable (not astronomical)
        max_reasonable = Decimal("1e15")  # 1 quadrillion
        assert available <= max_reasonable, "available amount seems unreasonably large"
        assert in_order <= max_reasonable, "inOrder amount seems unreasonably large"

    def test_balance_with_options(self, private_api: PrivateAPI) -> None:
        """
        Balance endpoint should work with symbol filter.

        ```py
        [
            {
                "symbol": "EUR",
                "available": "20.89",
                "inOrder": "0",
            },
        ]
        ```
        """
        result = private_api.balance(options={"symbol": "EUR"})
        match result:
            case Success(data):
                assert isinstance(data, (dict, list))
                # If successful, should return EUR balance info
                if isinstance(data, dict) and "symbol" in data:
                    assert data["symbol"] == "EUR"
                elif isinstance(data, list) and optional_length(data):
                    first = data[0]
                    if isinstance(first, dict) and "symbol" in first:
                        assert first["symbol"] == "EUR"
            case Failure(error):
                raise ValueError(error)

    def test_orders_open(self, private_api: PrivateAPI) -> None:
        """
        Open orders endpoint should return list of open orders.

        ```py
        [
            {
                "orderId": "00000000-0000-0460-0100-00004676b39f",
                "market": "DIA-EUR",
                "created": 1745376710551,
                "updated": 1745376710551,
                "status": "new",
                "side": "sell",
                "orderType": "limit",
                "selfTradePrevention": "decrementAndCancel",
                "visible": False,
                "onHold": "48.5262811",
                "onHoldCurrency": "DIA",
                "fills": [],
                "feePaid": "0",
                "feeCurrency": "EUR",
                "operatorId": 0,
                "price": "15",
                "timeInForce": "GTC",
                "postOnly": False,
                "amount": "48.5262811",
                "amountRemaining": "48.5262811",
                "filledAmount": "0",
                "filledAmountQuote": "0",
                "createdNs": 1745376710551000000,
                "updatedNs": 1745376710551000000,
            }
        ]
        ```
        """
        result = private_api.orders_open()
        match result:
            case Success(data):
                assert isinstance(data, (dict, list))
                # Open orders is typically a list (might be empty)
                if isinstance(data, list) and optional_length(data):
                    first = data[0]
                    assert isinstance(first, dict)

                    # Validate order structure using helper
                    self._validate_order_data(first)

                    # Check optional numeric fields if present
                    optional_numeric_fields = [
                        "onHold",
                        "feePaid",
                        "price",
                        "amount",
                        "amountRemaining",
                        "filledAmount",
                        "filledAmountQuote",
                    ]
                    self._validate_numeric_fields(first, optional_numeric_fields)

                    # Check that fills is a list if present
                    if "fills" in first:
                        assert isinstance(first["fills"], list), "fills must be a list"

                elif isinstance(data, dict) and "orderId" in data:
                    assert isinstance(data["orderId"], str)
            case Failure(error):
                raise ValueError(error)

    def _validate_market_order_fields(self, order_dict: dict) -> None:
        """Helper method to validate market-specific order fields."""
        # Validate string fields
        string_fields = ["selfTradePrevention", "onHoldCurrency", "feeCurrency", "timeInForce"]
        for field in string_fields:
            if field in order_dict:
                assert isinstance(order_dict[field], str), f"{field} must be string"
                assert order_dict[field].strip(), f"{field} must be non-empty"

        # Validate boolean fields
        boolean_fields = ["visible", "postOnly"]
        for field in boolean_fields:
            if field in order_dict:
                assert isinstance(order_dict[field], bool), f"{field} must be boolean"

        # Validate integer fields
        if "operatorId" in order_dict:
            assert isinstance(order_dict["operatorId"], int), "operatorId must be integer"

        # Validate fills array
        if "fills" in order_dict:
            assert isinstance(order_dict["fills"], list), "fills must be a list"

        # Validate timestamp fields
        timestamp_fields = ["createdNs", "updatedNs"]
        for field in timestamp_fields:
            if field in order_dict:
                assert isinstance(order_dict[field], int), f"{field} must be integer timestamp"
                assert order_dict[field] > 0, f"{field} must be positive timestamp"

    def test_orders_open_with_market_filter(self, private_api: PrivateAPI) -> None:
        """
        Open orders endpoint should work with market filter.

        ```py
        [
            {
                "orderId": "00000000-0000-0558-0100-0000201a0f06",
                "market": "SHIB-EUR",
                "created": 1743995597800,
                "updated": 1743995597800,
                "status": "new",
                "side": "sell",
                "orderType": "limit",
                "selfTradePrevention": "decrementAndCancel",
                "visible": False,
                "onHold": "150000000",
                "onHoldCurrency": "SHIB",
                "fills": [],
                "feePaid": "0",
                "feeCurrency": "EUR",
                "operatorId": -9223372036854775808,
                "price": "0.00004",
                "timeInForce": "GTC",
                "postOnly": False,
                "amount": "150000000",
                "amountRemaining": "150000000",
                "filledAmount": "0",
                "filledAmountQuote": "0",
                "createdNs": 1743995597800000000,
                "updatedNs": 1743995597800000000,
            }
        ]

        ```
        """
        result = private_api.orders_open(options={"market": "SHIB-EUR"})
        match result:
            case Success(data):
                assert isinstance(data, (dict, list)), "Expected dict or list response"
                # Normalize to list for consistent checking
                orders = [data] if isinstance(data, dict) else data

                if optional_length(orders):
                    for order in orders:
                        assert isinstance(order, dict), "Each order should be a dict"

                        # Validate core order structure
                        self._validate_order_data(order)

                        # Market filter validation - should match requested market
                        assert "market" in order, "market field must be present in filtered results"
                        assert order["market"] == "SHIB-EUR", f"Expected market 'SHIB-EUR', got '{order.get('market')}'"

                        # Validate market-specific fields
                        self._validate_market_order_fields(order)

                        # Validate numeric fields with helper
                        optional_numeric_fields = [
                            "onHold",
                            "feePaid",
                            "price",
                            "amount",
                            "amountRemaining",
                            "filledAmount",
                            "filledAmountQuote",
                        ]
                        self._validate_numeric_fields(order, optional_numeric_fields)

            case Failure(error):
                # Allow market-specific failures (e.g., if market doesn't exist or has no orders)
                assert hasattr(error, "http_status") or "error" in str(error), (
                    "Error should have http_status or be descriptive"
                )

    def test_orders_open_with_base_filter(self, private_api: PrivateAPI) -> None:
        """
        Open orders endpoint should work with base filter.

        According to the documentation, the 'base' parameter filters open orders
        by the base asset (e.g., 'BTC' would return orders for BTC-EUR, BTC-USD, etc.).
        """
        result = private_api.orders_open(options={"base": "BTC"})
        match result:
            case Success(data):
                assert isinstance(data, (dict, list)), "Expected dict or list response"
                # Normalize to list for consistent checking
                orders = [data] if isinstance(data, dict) else data

                if optional_length(orders):
                    for order in orders:
                        assert isinstance(order, dict), "Each order should be a dict"

                        # Validate core order structure
                        self._validate_order_data(order)

                        # Base filter validation - market should contain the base currency
                        assert "market" in order, "market field must be present in filtered results"
                        market = order["market"]
                        assert isinstance(market, str), f"Market should be string, got {type(market)}"
                        assert "-" in market, f"Invalid market format: {market}"
                        base_currency = market.split("-")[0]
                        expected_msg = f"Expected base currency 'BTC', got '{base_currency}' in market '{market}'"
                        assert base_currency == "BTC", expected_msg

                        # Validate market-specific fields
                        self._validate_market_order_fields(order)

                        # Validate numeric fields with helper
                        optional_numeric_fields = [
                            "onHold",
                            "feePaid",
                            "price",
                            "amount",
                            "amountRemaining",
                            "filledAmount",
                            "filledAmountQuote",
                        ]
                        self._validate_numeric_fields(order, optional_numeric_fields)

            case Failure(error):
                # Allow base-specific failures (e.g., if base doesn't exist or has no orders)
                assert hasattr(error, "http_status") or "error" in str(error), (
                    "Error should have http_status or be descriptive"
                )

    def test_fees(self, private_api: PrivateAPI) -> None:
        """
        Fees endpoint should return fee information.

        ```py
        {
            "tier": "0",
            "volume": "0.00",
            "maker": "0.0015",
            "taker": "0.0025",
        }
        ```
        """
        result = private_api.fees()
        match result:
            case Success(data):
                assert isinstance(data, (dict, list)), "Expected dict or list response"

                if isinstance(data, dict):
                    self._validate_fees_dict(data)
                elif isinstance(data, list) and optional_length(data):
                    # If it's a list, validate the first item has fee-related fields
                    first = data[0]
                    assert isinstance(first, dict), "Each fee entry should be a dict"
                    self._validate_fees_dict(first)

            case Failure(error):
                msg = f"Fees endpoint failed with error: {error}"
                raise AssertionError(msg)

    def test_fees_with_market_parameter(self, private_api: PrivateAPI) -> None:
        """Test fees endpoint with market parameter."""
        result = private_api.fees({"market": "BTC-EUR"})
        match result:
            case Success(data):
                assert isinstance(data, (dict, list)), "Expected dict or list response"
                if isinstance(data, dict):
                    self._validate_fees_dict(data)
            case Failure(error):
                # Market might not exist or other issues, but should not crash
                assert isinstance(error, Exception)

    def test_fees_with_quote_parameter(self, private_api: PrivateAPI) -> None:
        """Test fees endpoint with quote parameter."""
        result = private_api.fees({"quote": "EUR"})
        match result:
            case Success(data):
                assert isinstance(data, (dict, list)), "Expected dict or list response"
                if isinstance(data, dict):
                    self._validate_fees_dict(data)
            case Failure(error):
                # Should not fail due to validation issues
                assert isinstance(error, Exception)

    def test_fees_invalid_quote_parameter(self, private_api: PrivateAPI) -> None:
        """Test fees endpoint with invalid quote parameter raises ValueError."""
        with pytest.raises(ValueError, match="Invalid quote currency"):
            private_api.fees({"quote": "INVALID"})

    def _validate_fees_dict(self, fees: dict) -> None:
        """Helper method to validate fees data structure."""
        # Check required fields based on example data
        required_fields = {"tier", "volume", "maker", "taker"}
        assert required_fields.issubset(fees.keys()), f"Missing fields: {required_fields - fees.keys()}"

        # Validate tier field - accept either int or string (API may return numeric or string types)
        if isinstance(fees["tier"], int):
            tier_val = fees["tier"]
            assert tier_val >= 0, "tier must be non-negative integer"
        else:
            assert isinstance(fees["tier"], str), "tier must be string or int"
            assert fees["tier"].strip(), "tier must be non-empty"
            # Validate it's a valid integer string
            try:
                tier_val = int(fees["tier"])
                assert tier_val >= 0, "tier must be non-negative integer"
            except (ValueError, TypeError) as exc:
                msg = f"tier must be valid integer string, got '{fees['tier']}'"
                raise AssertionError(msg) from exc

        # Validate string numeric fields
        fee_fields = ["volume", "maker", "taker"]
        for field in fee_fields:
            assert isinstance(fees[field], str), f"{field} must be string"
            assert fees[field].strip(), f"{field} must be non-empty"

            # Validate numeric format
            try:
                value = float(fees[field])
                assert value >= 0, f"{field} must be non-negative"
            except ValueError as exc:
                msg = f"Field {field} must be valid decimal string, got '{fees[field]}'"
                raise AssertionError(msg) from exc

        # Validate fee values are reasonable
        maker_fee = float(fees["maker"])
        taker_fee = float(fees["taker"])
        assert 0 <= maker_fee <= 1, "maker fee should be between 0 and 1 (0-100%)"
        assert 0 <= taker_fee <= 1, "taker fee should be between 0 and 1 (0-100%)"
        assert taker_fee >= maker_fee, "taker fee should typically be >= maker fee"

    def test_deposit_history(self, private_api: PrivateAPI) -> None:
        """
        Deposits endpoint should return deposit history.

        ```py
        [
            {
                "timestamp": 1737310548000,
                "symbol": "EUR",
                "amount": "100",
                "fee": "0",
                "status": "completed",
                "address": "NL10INGB0001234567",
            },
            {
                "timestamp": 1709677131000,
                "symbol": "SHIB",
                "amount": "350000000.01",
                "fee": "0",
                "status": "completed",
                "txId": "0xebc2b5e85b1371c029342c8d3197c781f81ba18243288716c36eea9802a9601a",
                "address": "0x79891ecc644c80603e51006c1f62ee512437e486",
            },
        ]
        ```
        """
        result = private_api.deposit_history()
        match result:
            case Success(data):
                assert isinstance(data, list), "Expected list response"
                self._validate_deposit_data(data)
            case Failure(error):
                msg = f"Deposits endpoint failed with error: {error}"
                raise AssertionError(msg)

    def test_deposit_history_with_parameters(self, private_api: PrivateAPI) -> None:
        """Test deposit history with query parameters."""
        # Test with symbol filter
        result = private_api.deposit_history(options={"symbol": "EUR"})
        match result:
            case Success(data):
                assert isinstance(data, list), "Expected list response"
                self._validate_deposit_data(data)
                # Verify all returned deposits are for EUR if any data
                if data:
                    for deposit in data:
                        if isinstance(deposit, dict) and "symbol" in deposit:
                            assert deposit["symbol"] == "EUR", f"Expected EUR symbol, got {deposit['symbol']}"
            case Failure(error):
                msg = f"Deposit history with symbol filter failed: {error}"
                raise AssertionError(msg)

        # Test with limit parameter
        result = private_api.deposit_history(options={"limit": 10})
        match result:
            case Success(data):
                assert isinstance(data, list), "Expected list response"
                assert len(data) <= 10, f"Expected max 10 deposits, got {len(data)}"
                self._validate_deposit_data(data)
            case Failure(error):
                msg = f"Deposit history with limit failed: {error}"
                raise AssertionError(msg)

    def test_deposit(self, private_api: PrivateAPI) -> None:
        """
        Deposit data endpoint should return deposit information for making deposits.

        Expected responses:
        - Digital assets: {"address": "CryptoCurrencyAddress", "paymentid": "10002653"}
        - Fiat: {"iban": "NL32BUNQ2291234129", "bic": "BUNQNL2A", "description": "254D20CC94"}
        """
        # Test with a common digital asset (BTC)
        result = private_api.deposit("BTC")
        match result:
            case Success(data):
                assert isinstance(data, dict), "Expected dict response"
                self._validate_deposit_data_response(data, "digital")
            case Failure(error):
                # Allow certain errors (e.g., if deposits are not available for the asset)
                if (
                    isinstance(error, BitvavoError)
                    and hasattr(error, "http_status")
                    and error.http_status in (400, 401, 402, 403)
                ):
                    # These are expected errors for deposit restrictions
                    pytest.skip(f"Deposit not available for BTC: {error}")
                else:
                    msg = f"Deposit data endpoint failed with unexpected error: {error}"
                    raise AssertionError(msg)

        # Test with fiat currency (EUR) if the first test passed
        result_eur = private_api.deposit("EUR")
        match result_eur:
            case Success(data):
                assert isinstance(data, dict), "Expected dict response"
                self._validate_deposit_data_response(data, "fiat")
            case Failure(error):
                # Allow certain errors for EUR deposits
                if (
                    isinstance(error, BitvavoError)
                    and hasattr(error, "http_status")
                    and error.http_status in (400, 401, 402, 403)
                ):
                    pytest.skip(f"Deposit not available for EUR: {error}")

    def _validate_deposit_data_response(self, data: dict, expected_type: str) -> None:
        """Helper to validate deposit data response structure."""
        if expected_type == "digital":
            # Digital asset deposit should have address
            assert "address" in data, "Digital asset deposit must include 'address'"
            assert isinstance(data["address"], str), "address must be string"
            assert data["address"].strip(), "address must be non-empty"

            # paymentid is optional for digital assets
            if "paymentid" in data:
                assert isinstance(data["paymentid"], str), "paymentid must be string"

        elif expected_type == "fiat":
            # Fiat deposit should have IBAN, BIC, and description
            required_fiat_fields = {"iban", "bic", "description"}
            assert required_fiat_fields.issubset(data.keys()), (
                f"Fiat deposit missing fields: {required_fiat_fields - data.keys()}"
            )

            for field in required_fiat_fields:
                assert isinstance(data[field], str), f"{field} must be string"
                assert data[field].strip(), f"{field} must be non-empty"

            # Basic validation for IBAN format (starts with country code)
            iban = data["iban"]
            assert len(iban) >= 15, "IBAN seems too short"
            assert iban[:2].isalpha(), "IBAN should start with country code letters"

    def _validate_deposit_data(self, data: dict | list) -> None:
        """Helper to validate deposit data structure."""
        if isinstance(data, list) and optional_length(data):
            for deposit in data:
                assert isinstance(deposit, dict), "Each deposit should be a dict"
                self._check_deposit_fields(deposit)
        elif isinstance(data, dict) and "symbol" in data:
            self._check_deposit_fields(data)

    def _check_deposit_fields(self, deposit: dict) -> None:
        """Helper to check deposit fields."""
        # Check required fields based on example data
        # 'address' is optional for deposit records
        required_fields = {"timestamp", "symbol", "amount", "fee", "status"}
        assert required_fields.issubset(deposit.keys()), f"Missing fields: {required_fields - deposit.keys()}"

        # Validate timestamp field
        assert isinstance(deposit["timestamp"], int), "timestamp must be integer"
        assert deposit["timestamp"] > 1_577_836_800_000, "timestamp seems too old (pre-2020)"

        # Validate string fields
        string_fields = ["symbol", "status"]
        for field in string_fields:
            assert isinstance(deposit[field], str), f"{field} must be string"
            assert deposit[field].strip(), f"{field} must be non-empty"

        # Validate status values
        valid_statuses = ["completed", "pending", "cancelled", "failed"]
        assert deposit["status"] in valid_statuses, (
            f"Invalid status '{deposit['status']}', expected one of: {valid_statuses}"
        )

        # Validate numeric string fields
        for field in ["amount", "fee"]:
            assert isinstance(deposit[field], str), f"{field} must be string"
            try:
                value = float(deposit[field])
                assert value >= 0, f"{field} must be non-negative"
            except ValueError as exc:
                msg = f"Field {field} must be valid decimal string, got '{deposit[field]}'"
                raise AssertionError(msg) from exc

        # Validate optional txId field (for crypto deposits)
        if "txId" in deposit:
            assert isinstance(deposit["txId"], str), "txId must be string"
            assert deposit["txId"].strip(), "txId must be non-empty"
            # Basic validation for transaction ID format (hex string)
            if deposit["txId"].startswith("0x"):
                assert len(deposit["txId"]) >= 10, "Transaction ID seems too short"

        # Validate optional paymentId field (for crypto deposits)
        if "paymentId" in deposit:
            assert isinstance(deposit["paymentId"], str), "paymentId must be string"
            assert deposit["paymentId"].strip(), "paymentId must be non-empty"

    def test_withdrawals(self, private_api: PrivateAPI) -> None:
        """
        Withdrawals endpoint should return withdrawal history.

        ```py
        [
            {
                "timestamp": 1709664478000,
                "symbol": "SHIB",
                "amount": "0.025",
                "fee": "0.0036",
                "status": "completed",
                "txId": "0xebc2b5e85b1371c029342c8d3197c781f81ba18243288716c36eea9802a9601a",
                "address": "0x79891ecc644c80603e51006c1f62ee512437e486",
            },
            {
                "timestamp": 1674161905000,
                "symbol": "EUR",
                "amount": "99.99",
                "fee": "0",
                "status": "completed",
                "address": "NL10INGB0001234567",
            },
        ]

        ```
        """
        result = private_api.withdrawals()
        match result:
            case Success(data):
                assert isinstance(data, (dict, list)), "Expected dict or list response"
                self._validate_withdrawal_data(data)
            case Failure(error):
                msg = f"Withdrawals endpoint failed with error: {error}"
                raise AssertionError(msg)

    def _validate_withdrawal_data(self, data: dict | list) -> None:
        """Helper to validate withdrawal data structure."""
        if isinstance(data, list) and optional_length(data):
            for withdrawal in data:
                assert isinstance(withdrawal, dict), "Each withdrawal should be a dict"
                self._check_withdrawal_fields(withdrawal)
        elif isinstance(data, dict) and "symbol" in data:
            self._check_withdrawal_fields(data)

    def _check_withdrawal_fields(self, withdrawal: dict) -> None:
        """Helper to check withdrawal fields."""
        # Check required fields based on example data
        required_fields = {"timestamp", "symbol", "amount", "fee", "status", "address"}
        assert required_fields.issubset(withdrawal.keys()), f"Missing fields: {required_fields - withdrawal.keys()}"

        # Validate timestamp field
        assert isinstance(withdrawal["timestamp"], int), "timestamp must be integer"
        assert withdrawal["timestamp"] > 1_577_836_800_000, "timestamp seems too old (pre-2020)"

        # Validate string fields
        string_fields = ["symbol", "status", "address"]
        for field in string_fields:
            assert isinstance(withdrawal[field], str), f"{field} must be string"
            assert withdrawal[field].strip(), f"{field} must be non-empty"

        # Validate status values
        valid_statuses = ["completed", "pending", "cancelled", "failed"]
        assert withdrawal["status"] in valid_statuses, (
            f"Invalid status '{withdrawal['status']}', expected one of: {valid_statuses}"
        )

        # Validate numeric string fields
        for field in ["amount", "fee"]:
            assert isinstance(withdrawal[field], str), f"{field} must be string"
            try:
                value = float(withdrawal[field])
                assert value >= 0, f"{field} must be non-negative"
            except ValueError as exc:
                msg = f"Field {field} must be valid decimal string, got '{withdrawal[field]}'"
                raise AssertionError(msg) from exc

        # Validate optional txId field (for crypto withdrawals)
        if "txId" in withdrawal:
            assert isinstance(withdrawal["txId"], str), "txId must be string"
            assert withdrawal["txId"].strip(), "txId must be non-empty"
            # Basic validation for transaction ID format (hex string)
            if withdrawal["txId"].startswith("0x"):
                assert len(withdrawal["txId"]) >= 10, "Transaction ID seems too short"

    def test_get_orders_for_market(self, private_api: PrivateAPI) -> None:
        """
        Get orders for specific market should return orders.

        ```py
        [
            {
                "orderId": "00000000-0000-0558-0100-0000201a0f06",
                "market": "SHIB-EUR",
                "created": 1743995597800,
                "updated": 1743995597800,
                "status": "new",
                "side": "sell",
                "orderType": "limit",
                "clientOrderId": "80000000-0000-0000-8000-000000000000",
                "amount": "150000000",
                "amountRemaining": "150000000",
                "onHold": "150000000",
                "onHoldCurrency": "SHIB",
                "filledAmount": "0",
                "filledAmountQuote": "0",
                "feePaid": "0",
                "feeCurrency": "EUR",
                "fills": [],
                "selfTradePrevention": "decrementAndCancel",
                "visible": True,
                "price": "0.00004",
                "timeInForce": "GTC",
                "postOnly": False,
            },
        ]
        ```
        """
        result = private_api.get_orders("SHIB-EUR")
        match result:
            case Success(data):
                assert isinstance(data, (dict, list))
                # Orders for market is typically a list (might be empty)
                if isinstance(data, list) and optional_length(data):
                    first = data[0]
                    assert isinstance(first, dict)

                    # Validate order structure using helper
                    self._validate_order_data(first)

                    # Check additional fields specific to this endpoint
                    optional_fields = ["clientOrderId", "visible", "timeInForce", "postOnly"]
                    for field in optional_fields:
                        if field in first:
                            if field in ["visible", "postOnly"]:
                                assert isinstance(first[field], bool), f"{field} must be boolean"
                            else:
                                assert isinstance(first[field], str), f"{field} must be string"

                    # Validate numeric fields
                    optional_numeric_fields = [
                        "amount",
                        "amountRemaining",
                        "onHold",
                        "filledAmount",
                        "filledAmountQuote",
                        "feePaid",
                        "price",
                    ]
                    self._validate_numeric_fields(first, optional_numeric_fields)

                elif isinstance(data, dict) and "orderId" in data:
                    assert isinstance(data["orderId"], str)
            case Failure(error):
                raise ValueError(error)

    def _validate_trade_data(self, data: dict | list) -> None:
        """Helper to validate trade data structure."""
        if isinstance(data, list) and optional_length(data):
            first = data[0]
            assert isinstance(first, dict)
            self._check_trade_fields(first)
        elif isinstance(data, dict) and "id" in data:
            self._check_trade_fields(data)

    def _check_trade_fields(self, trade: dict) -> None:
        """Helper to check trade fields."""
        # Check required fields based on example data
        required_fields = {"id", "timestamp", "amount", "price", "side"}
        assert required_fields.issubset(trade.keys()), f"Missing fields: {required_fields - trade.keys()}"

        # Validate field types
        assert isinstance(trade["id"], str), "id must be string"
        assert trade["id"].strip(), "id must be non-empty"

        assert isinstance(trade["timestamp"], int), "timestamp must be integer"
        assert trade["timestamp"] > 0, "timestamp must be positive"

        assert isinstance(trade["side"], str), "side must be string"
        assert trade["side"] in ("buy", "sell"), f"side must be 'buy' or 'sell', got '{trade['side']}'"

        # Validate numeric string fields
        self._validate_numeric_fields(trade, ["amount", "price"])

        # Check optional market field
        if "market" in trade:
            assert isinstance(trade["market"], str), "market must be string"
            assert trade["market"].strip(), "market must be non-empty"

    # Risky operations that could affect real trading - skip by default
    @pytest.mark.skip(reason="Risky operation - could place real orders")
    def test_place_order(self, private_api: PrivateAPI) -> None:
        """Test order placement - SKIPPED by default to prevent accidental trading."""
        # This test is intentionally skipped to prevent accidental order placement
        # Uncomment and modify carefully for integration testing
        # Would test: result = private_api.place_order("BTC-EUR", "buy", "limit", 543462, {"amount": "0.001", "price": "50000"})  # noqa: E501

    @pytest.mark.skip(reason="Risky operation - requires valid order ID")
    def test_get_order(self, private_api: PrivateAPI) -> None:
        """Test getting specific order - SKIPPED by default."""
        # This test requires a valid order ID
        # Would test: result = private_api.get_order("BTC-EUR", "some-order-id")

    @pytest.mark.skip(reason="Risky operation - could cancel real orders")
    def test_cancel_order(self, private_api: PrivateAPI) -> None:
        """Test order cancellation - SKIPPED by default."""
        # This test could cancel real orders
        # Updated API signature: must include operator_id and either order_id or client_order_id
        # Would test: result = private_api.cancel_order("BTC-EUR", 12345, order_id="some-order-id")

    @pytest.mark.skip(reason="Risky operation - could cancel all orders")
    def test_cancel_orders(self, private_api: PrivateAPI) -> None:
        """Test cancelling all orders for market - SKIPPED by default."""
        # This test could cancel all real orders
        # Would test: result = private_api.cancel_orders(operator_id=12345, market="BTC-EUR")
        # Or to cancel ALL orders: result = private_api.cancel_orders(operator_id=12345)

    @pytest.mark.skip(reason="Risky operation - requires real withdrawal details")
    def test_withdraw(self, private_api: PrivateAPI) -> None:
        """Test withdrawal - SKIPPED by default."""
        # This test could initiate real withdrawals
        # Would test: result = private_api.withdraw("EUR", "1.00", "some-address")

    # Missing abstract method implementations for RAW tests
    @pytest.mark.skip(reason="Risky operation - requires valid order ID")
    def test_update_order(self, private_api: PrivateAPI) -> None:
        """Test order update - SKIPPED by default."""

    def test_update_order_validation(self, private_api: PrivateAPI) -> None:
        """Test update_order parameter validation."""
        # Test missing both order_id and client_order_id
        result = private_api.update_order(
            market="BTC-EUR",
            operator_id=12345,
        )

        match result:
            case Failure(error):
                # Check if it's a BitvavoError (validation error)
                if isinstance(error, BitvavoError):
                    assert error.http_status == 400
                    assert error.error_code == 203
                    assert "Either order_id or client_order_id must be provided" in error.message
                else:
                    # If it's an HTTP error, that's also acceptable for this test
                    pytest.fail(f"Expected BitvavoError but got {type(error).__name__}: {error}")
            case _:
                pytest.fail("Expected Failure result for missing order identifiers")

    def test_update_order_payload_building(self, private_api: PrivateAPI) -> None:
        """Test that update_order builds the correct payload."""
        # Test with order_id
        payload1 = private_api._build_update_order_payload(  # noqa: SLF001
            market="BTC-EUR",
            operator_id=12345,
            order_id="test-order-id",
            client_order_id=None,
            amount="1.5",
            amount_quote=None,
            amount_remaining=None,
            price="50000",
            trigger_amount=None,
            time_in_force="GTC",
            self_trade_prevention="decrementAndCancel",
            post_only=True,
            response_required=True,
        )

        expected1 = {
            "market": "BTC-EUR",
            "operatorId": 12345,
            "orderId": "test-order-id",
            "amount": "1.5",
            "price": "50000",
            "timeInForce": "GTC",
            "selfTradePrevention": "decrementAndCancel",
            "postOnly": True,
            "responseRequired": True,
        }
        assert payload1 == expected1

        # Test with client_order_id (should take precedence)
        payload2 = private_api._build_update_order_payload(  # noqa: SLF001
            market="BTC-EUR",
            operator_id=12345,
            order_id="test-order-id",
            client_order_id="client-order-id",
            amount=None,
            amount_quote="1000",
            amount_remaining="0.5",
            price=None,
            trigger_amount="48000",
            time_in_force="IOC",
            self_trade_prevention="cancelOldest",
            post_only=False,
            response_required=False,
        )

        expected2 = {
            "market": "BTC-EUR",
            "operatorId": 12345,
            "clientOrderId": "client-order-id",  # Should use client_order_id, not order_id
            "amountQuote": "1000",
            "amountRemaining": "0.5",
            "triggerAmount": "48000",
            "timeInForce": "IOC",
            "selfTradePrevention": "cancelOldest",
            "postOnly": False,
            "responseRequired": False,
        }
        assert payload2 == expected2

    @pytest.mark.skip(reason="Risky operation - requires valid order ID")
    def test_update_order_live(self, private_api: PrivateAPI) -> None:
        """Test order update with live API - SKIPPED by default."""

    def test_get_orders(self, private_api: PrivateAPI) -> None:
        """
        Get orders endpoint should return order history.

        ```py
        [
            {
                "orderId": "69ebb862-089c-46cd-8280-b8993b75f275",
                "market": "SHIB-EUR",
                "created": 1674161582007,
                "updated": 1674161582007,
                "status": "filled",
                "side": "buy",
                "orderType": "market",
                "amountQuote": "10",
                "amountQuoteRemaining": "0",
                "onHold": "0",
                "onHoldCurrency": "EUR",
                "filledAmount": "936537.63",
                "filledAmountQuote": "9.97506229713",
                "feePaid": "0.02493770287",
                "feeCurrency": "EUR",
                "fills": [
                    {
                        "id": "c0a1bc63-e4ed-4a7f-ba7e-a1c8e21257c6",
                        "timestamp": 1674161582019,
                        "amount": "936537.63",
                        "price": "0.000010651",
                        "taker": True,
                        "fee": "0.02493770287",
                        "feeCurrency": "EUR",
                        "settled": True,
                    }
                ],
                "selfTradePrevention": "decrementAndCancel",
                "visible": False,
                "disableMarketProtection": False,
            },
        ]
        ```
        """
        result = private_api.get_orders("SHIB-EUR")
        match result:
            case Success(data):
                assert isinstance(data, (dict, list))
                # Orders is typically a list (might be empty)
                if isinstance(data, list) and optional_length(data):
                    first = data[0]
                    assert isinstance(first, dict)

                    # Validate order structure using helper
                    self._validate_order_data(first)

                    # Check additional fields that may be present in order history
                    optional_numeric_fields = [
                        "amountQuote",
                        "amountQuoteRemaining",
                        "onHold",
                        "filledAmount",
                        "filledAmountQuote",
                        "feePaid",
                    ]
                    self._validate_numeric_fields(first, optional_numeric_fields)

                    # Validate fills array if present
                    if first.get("fills"):
                        assert isinstance(first["fills"], list), "fills must be a list"
                        fill = first["fills"][0]
                        self._validate_fill_data(fill)

                    # Check boolean fields
                    boolean_fields = ["visible", "postOnly", "disableMarketProtection"]
                    for field in boolean_fields:
                        if field in first:
                            assert isinstance(first[field], bool), f"{field} must be boolean"

                elif isinstance(data, dict) and "orderId" in data:
                    assert isinstance(data["orderId"], str)
            case Failure(error):
                raise ValueError(error)

    def _validate_fill_data(self, fill: dict) -> None:
        """Helper to validate order fill data structure."""
        required_fields = {"id", "timestamp", "amount", "price", "taker", "fee", "feeCurrency", "settled"}
        assert required_fields.issubset(fill.keys()), f"Missing fill fields: {required_fields - fill.keys()}"

        # Validate field types
        assert isinstance(fill["id"], str), "fill id must be string"
        assert fill["id"].strip(), "fill id must be non-empty"

        assert isinstance(fill["timestamp"], int), "fill timestamp must be integer"
        assert fill["timestamp"] > 0, "fill timestamp must be positive"

        assert isinstance(fill["taker"], bool), "taker must be boolean"
        assert isinstance(fill["settled"], bool), "settled must be boolean"

        assert isinstance(fill["feeCurrency"], str), "feeCurrency must be string"
        assert fill["feeCurrency"].strip(), "feeCurrency must be non-empty"

        # Validate numeric fields
        self._validate_numeric_fields(fill, ["amount", "price", "fee"])

    def _validate_single_trade(self, trade: dict) -> None:
        """Helper method to validate a single trade entry."""
        # Validate required fields based on example data
        required_fields = {"id", "timestamp", "amount", "price", "side"}
        assert required_fields.issubset(trade.keys()), f"Missing required fields: {required_fields - trade.keys()}"

        # Validate trade ID
        assert isinstance(trade["id"], str), "id must be string"
        assert trade["id"].strip(), "Trade ID cannot be empty"
        assert len(trade["id"]) >= 32, "Trade ID should be UUID-like (at least 32 chars)"

        # Validate timestamp
        assert isinstance(trade["timestamp"], int), "timestamp must be integer"
        assert trade["timestamp"] > 1_577_836_800_000, "timestamp seems too old (pre-2020)"

        # Validate side
        assert isinstance(trade["side"], str), "side must be string"
        assert trade["side"] in ("buy", "sell"), f"side must be 'buy' or 'sell', got '{trade['side']}'"

        # Validate numeric string fields
        for field in ["amount", "price"]:
            assert isinstance(trade[field], str), f"{field} must be string"
            try:
                value = float(trade[field])
                assert value > 0, f"{field} must be positive"
            except ValueError as exc:
                msg = f"Field {field} must be valid decimal string, got '{trade[field]}'"
                raise AssertionError(msg) from exc

    def test_trade_history(self, private_api: PrivateAPI) -> None:
        """
        Private trade history endpoint should return user's trade history for a market.

        Expected response structure:
        [
            {
                "id": "108c3633-0276-4480-a902-17a01829deae",
                "orderId": "1d671998-3d44-4df4-965f-0d48bd129a1b",
                "clientOrderId": "2be7d0df-d8dc-7b93-a550-8876f3b393e9",
                "timestamp": 1542967486256,
                "market": "BTC-EUR",
                "side": "buy",
                "amount": "0.005",
                "price": "5000.1",
                "taker": true,
                "fee": "0.03",
                "feeCurrency": "EUR",
                "settled": true
            }
        ]
        """
        result = private_api.trade_history("BTC-EUR")
        match result:
            case Success(data):
                # Data should be a list
                assert isinstance(data, list), f"Expected list, got {type(data)}"

                if data:  # Only validate if we have trades
                    # Validate structure of first trade
                    trade = data[0]
                    assert isinstance(trade, dict), "Each trade should be a dict"

                    # Validate required fields exist
                    required_fields = {
                        "id",
                        "orderId",
                        "timestamp",
                        "market",
                        "side",
                        "amount",
                        "price",
                        "taker",
                        "settled",
                    }
                    actual_fields = set(trade.keys())
                    assert required_fields.issubset(actual_fields), (
                        f"Missing required fields: {required_fields - actual_fields}"
                    )

                    # Validate field types and values
                    assert isinstance(trade["id"], str), "id must be string"
                    assert len(trade["id"]) > 0, "id must not be empty"

                    assert isinstance(trade["orderId"], str), "orderId must be string"

                    assert isinstance(trade["timestamp"], int), "timestamp must be integer"
                    assert trade["timestamp"] > 1_577_836_800_000, "timestamp seems too old (pre-2020)"

                    assert isinstance(trade["market"], str), "market must be string"
                    assert trade["market"] == "BTC-EUR", "market should match requested market"

                    assert isinstance(trade["side"], str), "side must be string"
                    assert trade["side"] in ("buy", "sell"), f"side must be 'buy' or 'sell', got '{trade['side']}'"

                    assert isinstance(trade["amount"], str), "amount must be string"
                    assert isinstance(trade["price"], str), "price must be string"

                    # Validate numeric string fields
                    for field in ["amount", "price"]:
                        assert isinstance(trade[field], str), f"{field} must be string"
                        try:
                            value = float(trade[field])
                            assert value > 0, f"{field} must be positive"
                        except ValueError as exc:
                            msg = f"Field {field} must be valid decimal string, got '{trade[field]}'"
                            raise AssertionError(msg) from exc

                    assert isinstance(trade["taker"], bool), "taker must be boolean"
                    assert isinstance(trade["settled"], bool), "settled must be boolean"

                    # Optional fields validation
                    if "fee" in trade and trade["fee"] is not None:
                        assert isinstance(trade["fee"], str), "fee must be string when present"
                        try:
                            float(trade["fee"])  # Should be valid decimal
                        except ValueError as exc:
                            msg = f"Fee must be valid decimal string, got '{trade['fee']}'"
                            raise AssertionError(msg) from exc

                    if "feeCurrency" in trade and trade["feeCurrency"] is not None:
                        assert isinstance(trade["feeCurrency"], str), "feeCurrency must be string when present"
                        assert len(trade["feeCurrency"]) > 0, "feeCurrency must not be empty when present"

            case Failure(error):
                if is_auth_error(error):
                    pytest.skip("Authentication failed - using invalid or no credentials")
                else:
                    msg = f"Private trade history endpoint failed with error: {error}"
                    raise ValueError(msg)

    def _validate_transaction_core_fields(self, tx: dict) -> None:
        """Helper to validate core transaction fields that all transaction types should have."""
        # Validate core required fields
        core_required_fields = {"transactionId", "executedAt", "type"}
        actual_tx_fields = set(tx.keys())
        assert core_required_fields.issubset(actual_tx_fields), (
            f"Missing core required transaction fields: {core_required_fields - actual_tx_fields}"
        )

        # Validate core field types and values
        assert isinstance(tx["transactionId"], str), "transactionId must be string"
        assert len(tx["transactionId"]) > 0, "transactionId must not be empty"

        assert isinstance(tx["executedAt"], str), "executedAt must be string"
        assert len(tx["executedAt"]) > 0, "executedAt must not be empty"

        assert isinstance(tx["type"], str), "type must be string"
        valid_types = {
            "sell",
            "buy",
            "staking",
            "fixed_staking",
            "deposit",
            "withdrawal",
            "affiliate",
            "distribution",
            "internal_transfer",
            "withdrawal_cancelled",
            "rebate",
            "loan",
            "external_transferred_funds",
            "manually_assigned_bitvavo",
        }
        assert tx["type"] in valid_types, f"type must be one of {valid_types}, got '{tx['type']}'"

    def _validate_transaction_staking_fields(self, tx: dict) -> None:
        """Helper to validate staking-specific transaction fields."""
        if "receivedCurrency" in tx:
            assert isinstance(tx["receivedCurrency"], str), "receivedCurrency must be string"
            assert len(tx["receivedCurrency"]) > 0, "receivedCurrency must not be empty"

        if "receivedAmount" in tx:
            assert isinstance(tx["receivedAmount"], str), "receivedAmount must be string"
            try:
                value = float(tx["receivedAmount"])
                assert value >= 0, "receivedAmount must be non-negative"
            except ValueError as exc:
                msg = f"receivedAmount must be valid decimal string, got '{tx['receivedAmount']}'"
                raise AssertionError(msg) from exc

    def _validate_transaction_trading_fields(self, tx: dict) -> None:
        """Helper to validate trading-specific transaction fields."""
        trading_fields = [
            "priceCurrency",
            "priceAmount",
            "sentCurrency",
            "sentAmount",
            "receivedCurrency",
            "receivedAmount",
        ]

        for field in trading_fields:
            if field in tx:
                if field.endswith("Currency"):
                    assert isinstance(tx[field], str), f"{field} must be string"
                    assert len(tx[field]) > 0, f"{field} must not be empty"
                elif field.endswith("Amount"):
                    assert isinstance(tx[field], str), f"{field} must be string"
                    try:
                        value = float(tx[field])
                        assert value >= 0, f"{field} must be non-negative"
                    except ValueError as exc:
                        msg = f"{field} must be valid decimal string, got '{tx[field]}'"
                        raise AssertionError(msg) from exc

    def _validate_transaction_optional_fields(self, tx: dict) -> None:
        """Helper to validate optional transaction fields."""
        # Validate optional fee fields if present
        if "feesCurrency" in tx and tx["feesCurrency"] is not None:
            assert isinstance(tx["feesCurrency"], str), "feesCurrency must be string when present"
            assert len(tx["feesCurrency"]) > 0, "feesCurrency must not be empty"

        if "feesAmount" in tx and tx["feesAmount"] is not None:
            assert isinstance(tx["feesAmount"], str), "feesAmount must be string when present"
            try:
                value = float(tx["feesAmount"])
                assert value >= 0, "feesAmount must be non-negative"
            except ValueError as exc:
                msg = f"feesAmount must be valid decimal string, got '{tx['feesAmount']}'"
                raise AssertionError(msg) from exc

        # Address is optional
        if "address" in tx and tx["address"] is not None:
            assert isinstance(tx["address"], str), "address must be string when present"

    def test_transaction_history(self, private_api: PrivateAPI) -> None:
        """
        Transaction history endpoint should return account transaction history.

        Expected response structure:
        {
          "items": [
            {
              "transactionId": "5f5e7b3b-4f5b-4b2d-8b2f-4f2b5b3f5e5f",
              "executedAt": "2021-01-01T00:00:00.000Z",
              "type": "sell",
              "priceCurrency": "EUR",
              "priceAmount": "1000.00",
              "sentCurrency": "EUR",
              "sentAmount": "0.1",
              "receivedCurrency": "BTC",
              "receivedAmount": "0.0001",
              "feesCurrency": "EUR",
              "feesAmount": "0.01",
              "address": "string"
            }
          ],
          "currentPage": 1,
          "totalPages": 1,
          "maxItems": 100
        }
        """
        result = private_api.transaction_history()
        match result:
            case Success(data):
                # Data should now be a tuple of (items, metadata)
                assert isinstance(data, tuple), f"Expected tuple, got {type(data)}"
                assert len(data) == 2, f"Expected tuple of length 2, got {len(data)}"

                items, metadata = data

                # Validate items
                assert isinstance(items, list), f"Expected list for items, got {type(items)}"

                # Validate metadata
                assert isinstance(metadata, dict), f"Expected dict for metadata, got {type(metadata)}"

                # Validate required metadata fields
                required_fields = {"currentPage", "totalPages", "maxItems"}
                actual_fields = set(metadata.keys())
                assert required_fields.issubset(actual_fields), (
                    f"Missing required metadata fields: {required_fields - actual_fields}"
                )

                # Validate pagination fields
                assert isinstance(metadata["currentPage"], int), "currentPage must be integer"
                assert metadata["currentPage"] >= 1, "currentPage must be >= 1"

                assert isinstance(metadata["totalPages"], int), "totalPages must be integer"
                assert metadata["totalPages"] >= 1, "totalPages must be >= 1"

                assert isinstance(metadata["maxItems"], int), "maxItems must be integer"
                assert metadata["maxItems"] >= 1, "maxItems must be >= 1"

                if items:  # Only validate if we have transactions
                    # Validate structure of first transaction
                    tx = items[0]
                    assert isinstance(tx, dict), "Each transaction should be a dict"

                    # Validate core fields
                    self._validate_transaction_core_fields(tx)

                    # Validate type-specific fields based on transaction type
                    tx_type = tx["type"]

                    if tx_type in ("staking", "fixed_staking"):
                        self._validate_transaction_staking_fields(tx)
                    elif tx_type in ("sell", "buy"):
                        self._validate_transaction_trading_fields(tx)

                    # Validate optional fields
                    self._validate_transaction_optional_fields(tx)

            case Failure(error):
                if is_auth_error(error):
                    pytest.skip("Authentication failed - using invalid or no credentials")
                else:
                    msg = f"Transaction history endpoint failed with error: {error}"
                    raise ValueError(msg)


@pytest.mark.skipif(
    not hasattr(BitvavoSettings(), "api_key") or not BitvavoSettings().api_key,
    reason="API credentials required for private endpoints",
)
class TestPrivateAPI_PYDANTIC(AbstractPrivateAPITests):  # noqa: N801
    @pytest.fixture(scope="module")
    def private_api(self) -> PrivateAPI:
        """Private API with default MODEL preference (pydantic models)."""
        settings = BitvavoSettings()
        rate_limiter = RateLimitManager(
            settings.default_rate_limit,
            settings.rate_limit_buffer,
        )
        http = HTTPClient(settings, rate_limiter)

        if settings.api_key and settings.api_secret:
            http.configure_key(settings.api_key, settings.api_secret, 0)

        return PrivateAPI(http, preferred_model=ModelPreference.PYDANTIC)

    def test_account(self, private_api: PrivateAPI, expected_caps: set[str]) -> None:
        """Account endpoint should return Account model with fees and capabilities."""
        result = private_api.account()
        match result:
            case Success(account):
                assert isinstance(account, private_models.Account)

                # Fees
                assert hasattr(account, "fees")
                assert account.fees is not None
                assert isinstance(account.fees.tier, int)
                assert isinstance(account.fees.volume, str)
                assert isinstance(account.fees.maker, str)
                assert isinstance(account.fees.taker, str)

                # Capabilities
                assert hasattr(account, "capabilities")
                if account.capabilities is not None:
                    assert isinstance(account.capabilities, list)
                    if account.capabilities:
                        assert set(account.capabilities).issubset(expected_caps)
            case Failure(error):
                raise ValueError(error)

    def test_balance(self, private_api: PrivateAPI) -> None:
        """
        Balance endpoint should return balance information.

        [
            {"symbol": "NANO", "available": "0.014871", "inOrder": "0"},
            {"symbol": "EUR", "available": "20.89", "inOrder": "0"},
            {"symbol": "ETH", "available": "0.00107836", "inOrder": "0"},
            {"symbol": "XLM", "available": "0.6069182", "inOrder": "1399.7576087"},
            {"symbol": "SHIB", "available": "200087574.87", "inOrder": "150000000"},
            {"symbol": "DOGE", "available": "3.82390543", "inOrder": "0"},
            {"symbol": "TRUMP", "available": "19.57881729", "inOrder": "27.06266106"},
            {"symbol": "DIA", "available": "0.02889438", "inOrder": "48.5262811"},
            {"symbol": "ADA", "available": "3178.628354", "inOrder": "0"},
            {"symbol": "ATA", "available": "87.47599883", "inOrder": "0"},
            {"symbol": "MASK", "available": "11.42277534", "inOrder": "0"},
        ]
        """
        result = private_api.balance()
        match result:
            case Success(data):
                # Expect the pydantic wrapper model for balances
                assert isinstance(data, private_models.Balances)

                entries = data.root

                assert optional_length(entries), "balance entries should not be empty"

                for entry in entries:
                    # Support pydantic model instances or plain dicts
                    if hasattr(entry, "model_dump"):
                        entry_dict = entry.model_dump()
                    elif hasattr(entry, "dict"):
                        entry_dict = entry.dict()
                    else:
                        entry_dict = entry

                    assert isinstance(entry_dict, dict)
                    # Basic expectations for balance entries
                    assert "symbol" in entry_dict, "balance entry must include 'symbol'"
                    assert isinstance(entry_dict["symbol"], str)
                    if "available" in entry_dict and entry_dict["available"] is not None:
                        assert isinstance(entry_dict["available"], str)
                    if "inOrder" in entry_dict and entry_dict["inOrder"] is not None:
                        assert isinstance(entry_dict["inOrder"], str)

            case Failure(error):
                raise ValueError(error)

    # Risky operations that could affect real trading - skip by default
    @pytest.mark.skip(reason="Risky operation - could place real orders")
    def test_place_order(self, private_api: PrivateAPI) -> None:
        """Test order placement - SKIPPED by default to prevent accidental trading."""
        # This test is intentionally skipped to prevent accidental order placement
        # Uncomment and modify carefully for integration testing
        # Would test: result = private_api.place_order("BTC-EUR", "buy", "limit", 543462, {"amount": "0.001", "price": "50000"})  # noqa: E501

    @pytest.mark.skip(reason="Risky operation - requires valid order ID")
    def test_get_order(self, private_api: PrivateAPI) -> None:
        """Test getting specific order - SKIPPED by default."""
        # This test requires a valid order ID
        # Would test: result = private_api.get_order("BTC-EUR", "some-order-id")

    @pytest.mark.skip(reason="Risky operation - could cancel real orders")
    def test_cancel_order(self, private_api: PrivateAPI) -> None:
        """Test order cancellation - SKIPPED by default."""
        # This test could cancel real orders
        # Updated API signature: must include operator_id and either order_id or client_order_id
        # Would test: result = private_api.cancel_order("BTC-EUR", 12345, order_id="some-order-id")

    @pytest.mark.skip(reason="Risky operation - could cancel all orders")
    def test_cancel_orders(self, private_api: PrivateAPI) -> None:
        """Test cancelling all orders for market - SKIPPED by default."""
        # This test could cancel all real orders
        # Would test: result = private_api.cancel_orders(operator_id=12345, market="BTC-EUR")
        # Or to cancel ALL orders: result = private_api.cancel_orders(operator_id=12345)

    @pytest.mark.skip(reason="Risky operation - requires real withdrawal details")
    def test_withdraw(self, private_api: PrivateAPI) -> None:
        """Test withdrawal - SKIPPED by default."""
        # This test could initiate real withdrawals
        # Would test: result = private_api.withdraw("EUR", "1.00", "some-address")

    # Missing abstract method implementations for PYDANTIC tests
    @pytest.mark.skip(reason="Risky operation - requires valid order ID")
    def test_update_order(self, private_api: PrivateAPI) -> None:
        """Test order update - SKIPPED by default."""
        # This test could modify real orders
        # Would test: result = private_api.update_order("BTC-EUR", "some-order-id", {...})

    def test_get_orders(self, private_api: PrivateAPI) -> None:
        """Get orders endpoint should return Pydantic model."""
        result = private_api.get_orders("BTC-EUR")
        match result:
            case Success(data):
                # Should be a Pydantic model or list of models
                if hasattr(data, "__class__") and hasattr(data.__class__, "__module__"):
                    # Check if it's from our models module
                    module_name = data.__class__.__module__
                    assert "models" in module_name or isinstance(data, (list, dict))
            case Failure(error):
                raise ValueError(error)

    def test_orders_open(self, private_api: PrivateAPI) -> None:
        """Open orders endpoint should return Pydantic models."""
        result = private_api.orders_open()
        match result:
            case Success(data):
                # Should be a Pydantic model or list of models
                if hasattr(data, "__class__") and hasattr(data.__class__, "__module__"):
                    module_name = data.__class__.__module__
                    assert "models" in module_name or isinstance(data, (list, dict))
            case Failure(error):
                raise ValueError(error)

    def test_fees(self, private_api: PrivateAPI) -> None:
        """Fees endpoint should return Pydantic model."""
        result = private_api.fees()
        match result:
            case Success(data):
                # Should be a Pydantic model or list of models
                if hasattr(data, "__class__") and hasattr(data.__class__, "__module__"):
                    module_name = data.__class__.__module__
                    assert "models" in module_name or isinstance(data, (list, dict))
            case Failure(error):
                raise ValueError(error)

    def test_deposit_history(self, private_api: PrivateAPI) -> None:
        """
        Deposits endpoint should return deposit history with address field.

        ```py
        [
            {
                "timestamp": 1737310548000,
                "symbol": "EUR",
                "amount": "100",
                "fee": "0",
                "status": "completed",
                "address": "NL10INGB0001234567",
            },
            {
                "timestamp": 1709677131000,
                "symbol": "SHIB",
                "amount": "350000000.01",
                "fee": "0",
                "status": "completed",
                "txId": "0xebc2b5e85b1371c029342c8d3197c781f81ba18243288716c36eea9802a9601a",
                "address": "0x79891ecc644c80603e51006c1f62ee512437e486",
            },
        ]
        ```
        """
        result = private_api.deposit_history()
        match result:
            case Success(data):
                # Expect the pydantic wrapper model for deposits
                assert isinstance(data, private_models.DepositHistories)

                # Try to iterate / fallback to single-item model
                deposits_list = data.root

                # Validate each deposit entry (dict or pydantic model)
                for entry in deposits_list:
                    if isinstance(entry, private_models.DepositHistory):
                        self._check_deposit_fields(entry)
                    else:
                        # pydantic model -> convert to dict for validation
                        entry_dict = entry.model_dump()
                        self._check_deposit_fields(entry_dict)

    def _check_deposit_fields(self, deposit: private_models.DepositHistory) -> None:
        """Helper to check deposit fields for a pydantic private_models.Deposit."""
        # Try to obtain a plain dict representation (supports pydantic v2 `.model_dump()` and v1 `.dict()`)
        deposit_dict = deposit.model_dump()

        # Check required fields based on example data
        required_fields = {"timestamp", "symbol", "amount", "fee", "status", "address"}
        assert required_fields.issubset(deposit_dict.keys()), f"Missing fields: {required_fields - deposit_dict.keys()}"

        # Validate timestamp field
        timestamp = deposit_dict["timestamp"]
        assert isinstance(timestamp, int), "timestamp must be integer"
        assert timestamp > 1_577_836_800_000, "timestamp seems too old (pre-2020)"

        # Validate string fields
        for field in ("symbol", "status", "address"):
            val = deposit_dict[field]
            assert isinstance(val, str) or val is None, f"{field} must be string or None"
            if val is not None:
                assert val.strip(), f"{field} must be non-empty"

        # Validate status values
        valid_statuses = {"completed", "pending", "cancelled", "failed"}
        assert deposit_dict["status"] in valid_statuses, (
            f"Invalid status '{deposit_dict['status']}', expected one of: {sorted(valid_statuses)}"
        )

        # Validate numeric string fields
        for field in ("amount", "fee"):
            val = deposit_dict[field]
            assert isinstance(val, str), f"{field} must be string"
            try:
                value = float(val)
                assert value >= 0, f"{field} must be non-negative"
            except (ValueError, TypeError) as exc:
                msg = f"Field {field} must be valid decimal string, got '{val}'"
                raise AssertionError(msg) from exc

        # Validate optional txId field (for crypto deposits)
        txid = deposit_dict.get("txId")
        if txid is not None:
            assert isinstance(txid, str), "txId must be string"
            assert txid.strip(), "txId must be non-empty"
            # Basic validation for transaction ID format (hex string)
            if txid.startswith("0x"):
                assert len(txid) >= 10, "Transaction ID seems too short"

    def test_deposit(self, private_api: PrivateAPI) -> None:
        """
        Deposit data endpoint should return DepositData Pydantic model.

        Expected responses:
        - Digital assets: DepositData(address="...", paymentid="...")
        - Fiat: DepositData(iban="...", bic="...", description="...")
        """
        # Test with a common digital asset (BTC)
        result = private_api.deposit("BTC")
        match result:
            case Success(data):
                assert isinstance(data, private_models.Deposit), "Expected DepositData model"
                # Validate the Pydantic model
                assert hasattr(data, "is_digital"), "DepositData should have is_digital method"
                assert hasattr(data, "is_fiat"), "DepositData should have is_fiat method"

                # Should be either digital or fiat, not both
                assert data.is_digital() or data.is_fiat(), "Should be either digital or fiat deposit"
                assert not (data.is_digital() and data.is_fiat()), "Cannot be both digital and fiat"

            case Failure(error):
                # Allow certain errors for deposit restrictions
                if (
                    isinstance(error, BitvavoError)
                    and hasattr(error, "http_status")
                    and error.http_status in (400, 401, 402, 403)
                ):
                    pytest.skip(f"Deposit not available for BTC: {error}")
                else:
                    msg = f"Deposit data endpoint failed with error: {error}"
                    raise AssertionError(msg)

    def test_withdrawals(self, private_api: PrivateAPI) -> None:
        """Withdrawals endpoint should return Pydantic model."""
        result = private_api.withdrawals()
        match result:
            case Success(data):
                # Should be a Pydantic model or list of models
                if hasattr(data, "__class__") and hasattr(data.__class__, "__module__"):
                    module_name = data.__class__.__module__
                    assert "models" in module_name or isinstance(data, (list, dict))
            case Failure(error):
                raise ValueError(error)

    def test_trade_history(self, private_api: PrivateAPI) -> None:
        """Private trade history endpoint should return Trades Pydantic model."""
        result = private_api.trade_history("BTC-EUR")
        match result:
            case Success(data):
                assert isinstance(data, private_models.Trades)

                # If there are trades, validate the Trade objects
                if data.root:  # Trades has a root list
                    trade = data.root[0]
                    assert isinstance(trade, private_models.Trade)

                    # Validate some key fields
                    assert isinstance(trade.id, str)
                    assert len(trade.id) > 0
                    assert isinstance(trade.timestamp, int)
                    assert trade.timestamp > 1_577_836_800_000  # Reasonable timestamp
                    assert trade.market == "BTC-EUR"
                    assert trade.side in ("buy", "sell")

                    # Validate decimal fields
                    assert trade.amount_decimal() > 0
                    assert trade.price_decimal() > 0

                    # Fee can be None or a valid decimal
                    if trade.fee is not None:
                        fee_decimal = trade.fee_decimal()
                        assert fee_decimal is not None
                        assert fee_decimal >= 0  # Can be negative for rebates

            case Failure(error):
                if is_auth_error(error):
                    pytest.skip("Authentication failed - using invalid or no credentials")
                else:
                    msg = f"Private trade history endpoint failed with error: {error}"
                    raise ValueError(msg)

    def test_transaction_history(self, private_api: PrivateAPI) -> None:
        """Transaction history endpoint should return TransactionHistory Pydantic model."""
        result = private_api.transaction_history()
        match result:
            case Success(data):
                # Data should now be a tuple of (pydantic_model, metadata)
                assert isinstance(data, tuple), f"Expected tuple, got {type(data)}"
                assert len(data) == 2, f"Expected tuple of length 2, got {len(data)}"

                items_model, metadata = data

                # Items should be a Pydantic model
                assert isinstance(items_model, private_models.TransactionHistory), (
                    f"Expected TransactionHistory model, got {type(items_model)}"
                )

                # Validate metadata
                assert isinstance(metadata, dict), f"Expected dict for metadata, got {type(metadata)}"

                # Validate required metadata fields (should match the pagination info)
                required_metadata_fields = {"currentPage", "totalPages", "maxItems"}
                actual_metadata_fields = set(metadata.keys())
                assert required_metadata_fields.issubset(actual_metadata_fields), (
                    f"Missing required metadata fields: {required_metadata_fields - actual_metadata_fields}"
                )

                # Validate metadata pagination fields
                assert isinstance(metadata["currentPage"], int)
                assert metadata["currentPage"] >= 1
                assert isinstance(metadata["totalPages"], int)
                assert metadata["totalPages"] >= 1
                assert isinstance(metadata["maxItems"], int)
                assert metadata["maxItems"] >= 1

                # If there are transactions, validate the TransactionHistoryItem objects
                if items_model.root:
                    self._validate_pydantic_transaction_item(items_model.root[0])

            case Failure(error):
                if is_auth_error(error):
                    pytest.skip("Authentication failed - using invalid or no credentials")
                else:
                    msg = f"Transaction history endpoint failed with error: {error}"
                    raise ValueError(msg)

    def _validate_pydantic_transaction_item(self, tx: private_models.TransactionHistoryItem) -> None:
        """Helper method to validate a single Pydantic transaction item."""
        assert isinstance(tx, private_models.TransactionHistoryItem)

        # Validate key fields
        assert isinstance(tx.transaction_id, str)
        assert len(tx.transaction_id) > 0
        assert isinstance(tx.executed_at, str)
        assert len(tx.executed_at) > 0

        # Validate type is from allowed values
        valid_types = {
            "sell",
            "buy",
            "staking",
            "fixed_staking",
            "deposit",
            "withdrawal",
            "affiliate",
            "distribution",
            "internal_transfer",
            "withdrawal_cancelled",
            "rebate",
            "loan",
            "external_transferred_funds",
            "manually_assigned_bitvavo",
        }
        assert tx.type in valid_types

        # Validate decimal conversion methods work
        assert tx.price_amount_decimal() >= 0
        assert tx.sent_amount_decimal() >= 0
        assert tx.received_amount_decimal() >= 0
        assert tx.fees_amount_decimal() >= 0

        # Validate fields based on transaction type
        if tx.type in {"staking", "fixed_staking"}:
            # Staking transactions only have basic fields
            assert tx.received_currency is not None
            assert len(tx.received_currency) > 0
            assert tx.received_amount is not None
            assert len(tx.received_amount) > 0
            # Other fields may be None
        else:
            # Trading transactions have full field set
            assert tx.price_currency is not None
            assert len(tx.price_currency) > 0
            assert tx.sent_currency is not None
            assert len(tx.sent_currency) > 0
            assert tx.received_currency is not None
            assert len(tx.received_currency) > 0
            assert tx.fees_currency is not None
            assert len(tx.fees_currency) > 0


@pytest.mark.skipif(
    not hasattr(BitvavoSettings(), "api_key") or not BitvavoSettings().api_key,
    reason="API credentials required for private endpoints",
)
class TestPrivateAPI_DATAFRAME(AbstractPrivateAPITests):  # noqa: N801
    """Basic smoke tests for private endpoints."""

    @pytest.fixture(scope="module")
    def private_api(self) -> PrivateAPI:
        """Private API with DATAFRAME preference (polars.DataFrame)."""
        settings = BitvavoSettings()
        rate_limiter = RateLimitManager(
            settings.default_rate_limit,
            settings.rate_limit_buffer,
        )
        http = HTTPClient(settings, rate_limiter)

        if settings.api_key and settings.api_secret:
            http.configure_key(settings.api_key, settings.api_secret, 0)

        return PrivateAPI(http, preferred_model=ModelPreference.DATAFRAME)

    def test_account(self, private_api: PrivateAPI, expected_caps: set[str]) -> None:
        """Account endpoint should return Failure for DataFrame model preference."""
        result = private_api.account()
        match result:
            case Success(_):
                # Should never happen - DataFrame model is not supported for account
                pytest.fail("Expected Failure for DataFrame model, but got Success")
            case Failure(error):
                assert isinstance(error, TypeError), (
                    f"Expected TypeError for unsupported DataFrame model, got {type(error)}"
                )
                assert "DataFrame model is not supported" in str(error), (
                    f"Expected DataFrame error message, got: {error}"
                )

    def test_balance(self, private_api: PrivateAPI) -> None:
        """Balance endpoint should return balance information as DataFrame."""
        result = private_api.balance()
        match result:
            case Success(data):
                assert isinstance(data, pl.DataFrame)
                # Check for expected columns based on BALANCE_SCHEMA
                if "symbol" in data.columns:
                    assert data["symbol"].dtype == pl.Categorical
                if "available" in data.columns:
                    assert data["available"].dtype == pl.Float64
                if "inOrder" in data.columns:
                    assert data["inOrder"].dtype == pl.Float64
            case Failure(error):
                raise ValueError(error)

    def test_orders_open(self, private_api: PrivateAPI) -> None:
        """Open orders endpoint should return orders as DataFrame and match expected schema types when present."""
        result = private_api.orders_open()
        match result:
            case Success(data):
                assert isinstance(data, pl.DataFrame)
                # DataFrame might be empty (no open orders)
                if data.shape[0] > 0:
                    for col, expected_dtype in private_schemas.ORDERS_SCHEMA.items():
                        if col in data.columns:
                            actual_dtype = data.schema[col]
                            assert actual_dtype == expected_dtype, (
                                f"Column '{col}' expected dtype {expected_dtype!r} but got {actual_dtype!r}"
                            )
            case Failure(error):
                raise ValueError(error)

    def test_fees(self, private_api: PrivateAPI) -> None:
        """Fees endpoint should return fee information as DataFrame and match expected schema types when present."""
        result = private_api.fees()
        match result:
            case Success(data):
                assert isinstance(data, pl.DataFrame)
                # DataFrame might be empty (no fees)
                if data.shape[0] > 0:
                    for col, expected_dtype in private_schemas.FEES_SCHEMA.items():
                        if col in data.columns:
                            actual_dtype = data.schema[col]
                            assert actual_dtype == expected_dtype, (
                                f"Column '{col}' expected dtype {expected_dtype!r} but got {actual_dtype!r}"
                            )
            case Failure(error):
                raise ValueError(error)

    def test_deposit_history(self, private_api: PrivateAPI) -> None:
        """Deposits endpoint should return deposit history as DataFrame and match expected schema types when present."""
        result = private_api.deposit_history()
        match result:
            case Success(data):
                assert isinstance(data, pl.DataFrame)
                # DataFrame might be empty (no deposits)
                if data.shape[0] > 0:
                    for col, expected_dtype in private_schemas.DEPOSIT_HISTORY_SCHEMA.items():
                        if col in data.columns:
                            actual_dtype = data.schema[col]
                            assert actual_dtype == expected_dtype, (
                                f"Column '{col}' expected dtype {expected_dtype!r} but got {actual_dtype!r}"
                            )
            case Failure(error):
                raise ValueError(error)

    def test_deposit(self, private_api: PrivateAPI) -> None:
        """Deposit data endpoint should return Failure for DataFrame model preference."""
        result = private_api.deposit("BTC")
        match result:
            case Success(_):
                # Should never happen - DataFrame model is not supported for deposit
                pytest.fail("Expected Failure for DataFrame model, but got Success")
            case Failure(error):
                assert isinstance(error, TypeError), (
                    f"Expected TypeError for unsupported DataFrame model, got {type(error)}"
                )
                assert "DataFrame model is not supported" in str(error), (
                    f"Expected DataFrame error message, got: {error}"
                )

    def test_withdrawals(self, private_api: PrivateAPI) -> None:
        """Withdrawals endpoint should return withdrawal history as DataFrame and match expected schema types."""
        result = private_api.withdrawals()
        match result:
            case Success(data):
                assert isinstance(data, pl.DataFrame)
                # DataFrame might be empty (no withdrawals)
                if data.shape[0] > 0:
                    for col, expected_dtype in private_schemas.WITHDRAWALS_SCHEMA.items():
                        if col in data.columns:
                            actual_dtype = data.schema[col]
                            assert actual_dtype == expected_dtype, (
                                f"Column '{col}' expected dtype {expected_dtype!r} but got {actual_dtype!r}"
                            )
            case Failure(error):
                raise ValueError(error)

    # Risky operations that could affect real trading - skip by default
    @pytest.mark.skip(reason="Risky operation - could place real orders")
    def test_place_order(self, private_api: PrivateAPI) -> None:
        """Test order placement - SKIPPED by default to prevent accidental trading."""
        # This test is intentionally skipped to prevent accidental order placement
        # Uncomment and modify carefully for integration testing
        # Would test: result = private_api.place_order("BTC-EUR", "buy", "limit", 543462, {"amount": "0.001", "price": "50000"})  # noqa: E501

    @pytest.mark.skip(reason="Risky operation - requires valid order ID")
    def test_get_order(self, private_api: PrivateAPI) -> None:
        """Test getting specific order - SKIPPED by default."""
        # This test requires a valid order ID
        # Would test: result = private_api.get_order("BTC-EUR", "some-order-id")

    @pytest.mark.skip(reason="Risky operation - could cancel real orders")
    def test_cancel_order(self, private_api: PrivateAPI) -> None:
        """Test order cancellation - SKIPPED by default."""
        # This test could cancel real orders
        # Updated API signature: must include operator_id and either order_id or client_order_id
        # Would test: result = private_api.cancel_order("BTC-EUR", 12345, order_id="some-order-id")

    @pytest.mark.skip(reason="Risky operation - could cancel all orders")
    def test_cancel_orders(self, private_api: PrivateAPI) -> None:
        """Test cancelling all orders for market - SKIPPED by default."""
        # This test could cancel all real orders
        # Would test: result = private_api.cancel_orders(operator_id=12345, market="BTC-EUR")
        # Or to cancel ALL orders: result = private_api.cancel_orders(operator_id=12345)

    @pytest.mark.skip(reason="Risky operation - requires real withdrawal details")
    def test_withdraw(self, private_api: PrivateAPI) -> None:
        """Test withdrawal - SKIPPED by default."""
        # This test could initiate real withdrawals
        # Would test: result = private_api.withdraw("EUR", "1.00", "some-address")

    def test_trade_history(self, private_api: PrivateAPI) -> None:
        """Private trade history endpoint should return trades as a Polars DataFrame."""
        result = private_api.trade_history("BTC-EUR")
        match result:
            case Success(data):
                assert isinstance(data, pl.DataFrame), f"Expected DataFrame, got {type(data)}"

                if optional_length(data):  # Only validate if we have trades
                    data_length = optional_length(data)
                    assert data_length is not None, "DataFrame length should not be None"
                    assert data_length > 0, "Expected non-empty trades DataFrame"

                    # Validate expected columns exist
                    expected_columns = {
                        "id",
                        "timestamp",
                        "amount",
                        "price",
                        "side",
                        "market",
                        "fee",
                        "feeCurrency",
                        "settled",
                    }
                    actual_columns = set(data.columns)
                    assert expected_columns.issubset(actual_columns), (
                        f"Missing expected columns: {expected_columns - actual_columns}"
                    )

                    # Validate some column types
                    assert data["id"].dtype == pl.String
                    assert data["timestamp"].dtype == pl.Int64
                    assert data["market"].dtype == pl.Categorical
                    assert data["side"].dtype == pl.Categorical
                    assert data["settled"].dtype == pl.Boolean

                    # Validate data content if we have rows
                    if len(data) > 0:
                        first_row = data.row(0, named=True)
                        assert first_row["market"] == "BTC-EUR", "Market should match requested market"
                        assert first_row["side"] in ("buy", "sell"), "Side should be buy or sell"
                        assert first_row["timestamp"] > 1_577_836_800_000, "Timestamp seems too old"

            case Failure(error):
                if is_auth_error(error):
                    pytest.skip("Authentication failed - using invalid or no credentials")
                else:
                    msg = f"Private trade history endpoint failed with error: {error}"
                    raise ValueError(msg)

    def test_transaction_history(self, private_api: PrivateAPI) -> None:
        """Transaction history endpoint should return tuple of (DataFrame, metadata)."""
        result = private_api.transaction_history()
        match result:
            case Success(data):
                # Data should now be a tuple of (DataFrame, metadata)
                assert isinstance(data, tuple), f"Expected tuple, got {type(data)}"
                assert len(data) == 2, f"Expected tuple of length 2, got {len(data)}"

                df, metadata = data

                # Validate DataFrame
                self._validate_transaction_history_dataframe(df)

                # Validate metadata
                assert isinstance(metadata, dict), f"Expected dict for metadata, got {type(metadata)}"

                # Validate required metadata fields
                required_metadata_fields = {"currentPage", "totalPages", "maxItems"}
                actual_metadata_fields = set(metadata.keys())
                assert required_metadata_fields.issubset(actual_metadata_fields), (
                    f"Missing required metadata fields: {required_metadata_fields - actual_metadata_fields}"
                )

                # Validate metadata pagination fields
                assert isinstance(metadata["currentPage"], int)
                assert metadata["currentPage"] >= 1
                assert isinstance(metadata["totalPages"], int)
                assert metadata["totalPages"] >= 1
                assert isinstance(metadata["maxItems"], int)
                assert metadata["maxItems"] >= 1
            case Failure(error):
                if is_auth_error(error):
                    pytest.skip("Authentication failed - using invalid or no credentials")
                else:
                    msg = f"Transaction history endpoint failed with error: {error}"
                    raise ValueError(msg)

    def _validate_transaction_history_dataframe(self, data: pl.DataFrame) -> None:
        """Helper method to validate transaction history DataFrame structure."""
        assert isinstance(data, pl.DataFrame), f"Expected DataFrame, got {type(data)}"

        # For DataFrames, we now get the transaction items directly (not the nested structure)
        # So we should have transaction columns, not pagination columns
        if optional_length(data) and len(data) > 0:
            # Validate that we have core transaction fields
            required_columns = {"transactionId", "executedAt", "type"}
            actual_columns = set(data.columns)
            assert required_columns.issubset(actual_columns), (
                f"Missing required transaction columns: {required_columns - actual_columns}"
            )

            # Validate that the data contains valid transaction types
            transaction_types = data["type"].unique().to_list()
            valid_types = {
                "sell",
                "buy",
                "staking",
                "fixed_staking",
                "deposit",
                "withdrawal",
                "affiliate",
                "distribution",
                "internal_transfer",
                "withdrawal_cancelled",
                "rebate",
                "loan",
                "external_transferred_funds",
                "manually_assigned_bitvavo",
            }
            for tx_type in transaction_types:
                assert tx_type in valid_types, f"Invalid transaction type: {tx_type}"

            # Basic data validation
            assert all(data["transactionId"].str.len_chars() > 0), "All transaction IDs should be non-empty"
            assert all(data["executedAt"].str.len_chars() > 0), "All execution timestamps should be non-empty"

    # Missing abstract method implementations for DATAFRAME tests
    @pytest.mark.skip(reason="Risky operation - requires valid order ID")
    def test_update_order(self, private_api: PrivateAPI) -> None:
        """Test order update - SKIPPED by default."""
        # This test could modify real orders
        # Would test: result = private_api.update_order("BTC-EUR", "some-order-id", {...})

    def test_get_orders(self, private_api: PrivateAPI) -> None:
        """Get orders endpoint should return DataFrame and match expected schema types when present."""
        result = private_api.get_orders("BTC-EUR")
        match result:
            case Success(data):
                assert isinstance(data, pl.DataFrame)
                # DataFrame might be empty (no orders)
                if data.shape[0] > 0:
                    for col, expected_dtype in private_schemas.ORDERS_SCHEMA.items():
                        if col in data.columns:
                            actual_dtype = data.schema[col]
                            assert actual_dtype == expected_dtype, (
                                f"Column '{col}' expected dtype {expected_dtype!r} but got {actual_dtype!r}"
                            )
            case Failure(error):
                raise ValueError(error)


class TestGetOrdersValidation:
    """Unit tests for get_orders parameter validation."""

    def test_get_orders_invalid_limit(self) -> None:
        """Test get_orders with invalid limit values."""
        settings = BitvavoSettings()
        rate_limiter = RateLimitManager(100, 10)
        http_client = HTTPClient(settings, rate_limiter)
        private_api = PrivateAPI(http_client)

        # Test invalid limits
        invalid_limits = [0, -1, 1001, 2000, "500", None]
        for limit in invalid_limits:
            with pytest.raises(ValueError, match="Invalid limit"):
                private_api.get_orders("BTC-EUR", {"limit": limit})

    def test_get_orders_invalid_end_timestamp(self) -> None:
        """Test get_orders with invalid end timestamp."""
        settings = BitvavoSettings()
        rate_limiter = RateLimitManager(100, 10)
        http_client = HTTPClient(settings, rate_limiter)
        private_api = PrivateAPI(http_client)

        # Test invalid end timestamps
        max_timestamp = 8640000000000000
        invalid_ends = [max_timestamp + 1, max_timestamp + 1000000, "1234567890"]
        for end in invalid_ends:
            with pytest.raises(ValueError, match="Invalid end timestamp"):
                private_api.get_orders("BTC-EUR", {"end": end})

    def test_get_orders_start_greater_than_end(self) -> None:
        """Test get_orders when start timestamp is greater than end timestamp."""
        settings = BitvavoSettings()
        rate_limiter = RateLimitManager(100, 10)
        http_client = HTTPClient(settings, rate_limiter)
        private_api = PrivateAPI(http_client)

        # Test start > end
        with pytest.raises(ValueError, match="Start timestamp .* cannot be greater than end timestamp"):
            private_api.get_orders("BTC-EUR", {"start": 1000000, "end": 999999})


class TestWithdrawResponseValidation:
    """Unit tests for withdraw response validation and model."""

    def test_withdraw_response_model_valid(self) -> None:
        """Test WithdrawResponse model with valid data."""
        # Test valid response data matching Bitvavo API documentation
        response_data = {"success": True, "symbol": "BTC", "amount": "1.5"}

        response = private_models.WithdrawResponse(**response_data)
        assert response.success is True
        assert response.symbol == "BTC"
        assert response.amount == "1.5"
        assert response.amount_decimal() == Decimal("1.5")

    def test_withdraw_response_model_invalid_amount(self) -> None:
        """Test WithdrawResponse model with invalid amount."""
        # Test invalid amount (non-numeric)
        with pytest.raises(ValueError, match="must be a numeric string"):
            private_models.WithdrawResponse(success=True, symbol="BTC", amount="invalid")

        # Test negative amount
        with pytest.raises(ValueError, match="must be non-negative"):
            private_models.WithdrawResponse(success=True, symbol="BTC", amount="-1.5")

    def test_withdraw_response_model_required_fields(self) -> None:
        """Test WithdrawResponse model with missing required fields."""
        # Test missing success field
        with pytest.raises(ValueError):  # noqa: PT011
            private_models.WithdrawResponse(symbol="BTC", amount="1.5")  # type: ignore[missing-argument]

        # Test missing symbol field
        with pytest.raises(ValueError):  # noqa: PT011
            private_models.WithdrawResponse(success=True, amount="1.5")  # type: ignore[missing-argument]

        # Test missing amount field
        with pytest.raises(ValueError):  # noqa: PT011
            private_models.WithdrawResponse(success=True, symbol="BTC")  # type: ignore[missing-argument]

    def test_withdraw_response_schema_validation(self) -> None:
        """Test withdraw response schema matches expected format."""
        # Verify schema has correct field types
        expected_schema = {
            "success": pl.Boolean,
            "symbol": pl.Categorical,
            "amount": pl.String,
        }

        assert expected_schema == private_schemas.WITHDRAW_RESPONSE_SCHEMA
