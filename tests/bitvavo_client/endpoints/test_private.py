# License notice from LICENSE.txt:
# Copyright (c) 2024, Bitvavo B.V.

"""Private SDK contracts against a local, schema-validated Bitvavo provider."""

from __future__ import annotations

import time
from decimal import Decimal
from io import BytesIO
from typing import TYPE_CHECKING, Any
from unittest.mock import patch
from urllib.parse import urlsplit

import niquests as http
import polars as pl
import pytest
from returns.result import Failure, Success

from bitvavo_api_upgraded import bitvavo as legacy_module
from bitvavo_api_upgraded.bitvavo import Bitvavo
from bitvavo_client.auth.rate_limit import RateLimitManager
from bitvavo_client.core import private_models
from bitvavo_client.core.model_preferences import ModelPreference
from bitvavo_client.core.settings import BitvavoSettings
from bitvavo_client.endpoints.private import PrivateAPI
from bitvavo_client.schemas import private_schemas
from bitvavo_client.transport.http import HTTPClient
from tests.bitvavo_client.endpoints.bitvavo_stub import (
    API_KEY,
    API_SECRET,
    BASE_URL,
    CLIENT_ORDER_ID,
    NOW_MS,
    OPERATOR_ID,
    ORDER_ID,
    FakeBitvavo,
    load_specification,
)

if TYPE_CHECKING:
    from collections.abc import Iterator


@pytest.fixture
def exchange(monkeypatch: pytest.MonkeyPatch) -> Iterator[FakeBitvavo]:
    provider = FakeBitvavo()
    monkeypatch.setattr(time, "time", lambda: NOW_MS / 1000)
    monkeypatch.setattr(legacy_module, "time_ms", lambda: NOW_MS)
    session_class = http.Session

    def local_session(**kwargs: Any) -> http.Session:
        session = session_class(**kwargs)
        session.trust_env = False
        return session

    monkeypatch.setattr(http.api.sessions, "Session", local_session)
    with provider.app.test_client() as client:

        def send(adapter: http.adapters.HTTPAdapter, request: http.PreparedRequest, **kwargs: Any) -> http.Response:
            assert urlsplit(request.url).netloc == "bitvavo.invalid", "Unexpected network destination"
            response = client.request(request.method, request.url, headers=dict(request.headers), content=request.body)
            raw = http.packages.urllib3.HTTPResponse(
                body=BytesIO(response.content),
                status=response.status_code,
                headers=dict(response.headers),
                preload_content=False,
            )
            return adapter.build_response(request, raw)

        monkeypatch.setattr(http.adapters.HTTPAdapter, "send", send)
        yield provider


@pytest.fixture
def private_api(exchange: FakeBitvavo) -> PrivateAPI:
    settings = BitvavoSettings(
        api_keys=[{"key": API_KEY, "secret": API_SECRET}],
        rest_url=BASE_URL,
        _env_file=None,
    )
    manager = RateLimitManager(settings.default_rate_limit, settings.rate_limit_buffer)
    return PrivateAPI(HTTPClient(settings, manager), preferred_model=ModelPreference.RAW)


@pytest.fixture
def legacy(exchange: FakeBitvavo) -> Bitvavo:
    return Bitvavo({"APIKEY": API_KEY, "APISECRET": API_SECRET, "RESTURL": BASE_URL, "DEBUGGING": False})


READ_CASES = [
    ("account", (), "/account", "GET /account", private_models.Account),
    ("balance", (), "/balance", "GET /balance", private_models.Balances),
    ("get_order", ("BTC-EUR", ORDER_ID), "/order", "order", private_models.Order),
    ("get_orders", ("BTC-EUR",), "/orders", "orders", private_models.Orders),
    ("orders_open", (), "/ordersOpen", "orders", private_models.Orders),
    ("fees", (), "/account/fees", "GET /account/fees", private_models.Fees),
    ("deposit", ("BTC",), "/deposit", "GET /deposit", private_models.Deposit),
    ("deposit_history", (), "/depositHistory", "GET /depositHistory", private_models.DepositHistories),
    ("withdrawals", (), "/withdrawalHistory", "GET /withdrawalHistory", private_models.Withdrawals),
    ("trade_history", ("BTC-EUR",), "/trades", "GET /trades", private_models.Trades),
    ("transaction_history", (), "/account/history", "GET /account/history", private_models.TransactionHistory),
]


@pytest.mark.parametrize("case", READ_CASES, ids=[case[0] for case in READ_CASES])
def test_private_read_contract(private_api: PrivateAPI, exchange: FakeBitvavo, case: tuple) -> None:
    method, args, path, fixture, _model = case
    result = getattr(private_api, method)(*args)
    assert isinstance(result, Success), result
    data = result.unwrap()
    if method == "transaction_history":
        rows, metadata = data
        assert rows == exchange.responses[fixture]["items"]
        assert metadata == {"currentPage": 1, "totalPages": 1, "maxItems": 100}
    elif fixture == "orders":
        assert data == list(exchange.orders.values())
    else:
        assert data == exchange.responses[fixture]
    assert exchange.requests[-1]["path"] == path


@pytest.mark.parametrize("case", READ_CASES, ids=[case[0] for case in READ_CASES])
def test_private_read_models(private_api: PrivateAPI, case: tuple) -> None:
    method, args, _path, _fixture, model = case
    result = getattr(private_api, method)(*args, model=model)
    assert isinstance(result, Success), result
    data = result.unwrap()[0] if method == "transaction_history" else result.unwrap()
    assert isinstance(data, model)
    if method == "trade_history":
        assert data.root[0].operator_id == OPERATOR_ID
        assert data.root[0].order_id == ORDER_ID
    if method == "get_order":
        assert data.operator_id == OPERATOR_ID


@pytest.mark.parametrize(
    ("method", "args"),
    [
        ("balance", ()),
        ("get_orders", ("BTC-EUR",)),
        ("orders_open", ()),
        ("trade_history", ("BTC-EUR",)),
        ("deposit_history", ()),
        ("withdrawals", ()),
    ],
)
def test_private_dataframe_output(private_api: PrivateAPI, method: str, args: tuple) -> None:
    result = getattr(private_api, method)(*args, model=pl.DataFrame)
    assert isinstance(result, Success), result
    frame = result.unwrap()
    assert isinstance(frame, pl.DataFrame)
    assert frame.height > 0


def test_order_lifecycle(private_api: PrivateAPI, exchange: FakeBitvavo) -> None:
    result = private_api.place_order("BTC-EUR", "buy", "limit", OPERATOR_ID, {"amount": "0.02", "price": "100.01"})
    assert isinstance(result, Success), result
    order = result.unwrap()
    assert order["orderId"] != ORDER_ID
    assert order["operatorId"] == OPERATOR_ID
    fetched = private_api.get_order("BTC-EUR", order["orderId"])
    assert isinstance(fetched, Success), fetched
    assert fetched.unwrap() == order
    updated = private_api.update_order("BTC-EUR", OPERATOR_ID, order_id=order["orderId"], price="101.01")
    assert isinstance(updated, Success), updated
    assert updated.unwrap()["price"] == "101.01"
    canceled = private_api.cancel_order("BTC-EUR", OPERATOR_ID, order_id=order["orderId"])
    assert isinstance(canceled, Success), canceled
    assert canceled.unwrap() == {"orderId": order["orderId"], "operatorId": OPERATOR_ID}
    assert exchange.orders[order["orderId"]]["status"] == "canceled"
    missing = private_api.update_order("BTC-EUR", OPERATOR_ID, order_id=order["orderId"], price="102")
    assert isinstance(missing, Failure)
    assert missing.failure().http_status == 404
    assert missing.failure().error_code == 240


def test_order_models(private_api: PrivateAPI) -> None:
    created = private_api.place_order(
        "BTC-EUR",
        "buy",
        "limit",
        OPERATOR_ID,
        {"amount": "0.02", "price": "100.01"},
        model=private_models.Order,
    )
    assert isinstance(created, Success), created
    order = created.unwrap()
    assert order.operator_id == OPERATOR_ID
    updated = private_api.update_order(
        "BTC-EUR",
        OPERATOR_ID,
        order_id=order.order_id,
        price="101.01",
        model=private_models.Order,
    )
    assert isinstance(updated, Success), updated
    assert updated.unwrap().price == "101.01"


def test_cancel_by_client_id(private_api: PrivateAPI) -> None:
    result = private_api.cancel_order("BTC-EUR", OPERATOR_ID, client_order_id=CLIENT_ORDER_ID)
    assert isinstance(result, Success), result
    assert result.unwrap()["orderId"] == ORDER_ID


def test_missing_order_identifier(private_api: PrivateAPI) -> None:
    result = private_api.http.request("DELETE", f"/order?market=BTC-EUR&operatorId={OPERATOR_ID}")
    assert isinstance(result, Failure)
    assert result.failure().error_code == 203


@pytest.mark.parametrize("market", [None, "BTC-EUR"])
def test_mass_cancel(private_api: PrivateAPI, exchange: FakeBitvavo, market: str | None) -> None:
    created = private_api.place_order("ETH-EUR", "sell", "limit", OPERATOR_ID, {"amount": "1", "price": "100"})
    assert isinstance(created, Success), created
    result = private_api.cancel_orders(OPERATOR_ID, market=market)
    assert isinstance(result, Success), result
    assert len(result.unwrap()) == (1 if market else 2)
    assert exchange.orders[ORDER_ID]["status"] == "canceled"
    assert exchange.orders[created.unwrap()["orderId"]]["status"] == ("new" if market else "canceled")


@pytest.mark.parametrize(
    ("method", "args", "kwargs", "weight"),
    [
        ("cancel_orders", (OPERATOR_ID,), {}, 100),
        ("cancel_orders", (OPERATOR_ID,), {"market": "BTC-EUR"}, 25),
        ("orders_open", (), {}, 100),
        ("orders_open", ({"market": "BTC-EUR"},), {}, 5),
        ("orders_open", ({"base": "BTC"},), {}, 100),
        ("withdrawals", (), {}, 5),
    ],
)
def test_documented_rate_limit_weights(
    private_api: PrivateAPI,
    method: str,
    args: tuple,
    kwargs: dict,
    weight: int,
) -> None:
    limiter = private_api.http.rate_limiter
    with patch.object(limiter, "record_call", wraps=limiter.record_call) as record:
        result = getattr(private_api, method)(*args, **kwargs)
    assert isinstance(result, Success), result
    assert record.call_args.args == (0, weight)


def test_withdrawal_is_local(private_api: PrivateAPI, exchange: FakeBitvavo) -> None:
    result = private_api.withdraw("BTC", "0.02", "offline-recipient", model=private_models.WithdrawResponse)
    assert isinstance(result, Success), result
    assert result.unwrap().success is True
    history = private_api.withdrawals({"symbol": "BTC"})
    assert isinstance(history, Success), history
    assert history.unwrap()[0]["address"] == "offline-recipient"
    assert history.unwrap()[0]["amount"] == "0.02"
    assert exchange.requests[-2]["path"] == "/withdrawal"


def test_pagination(private_api: PrivateAPI) -> None:
    result = private_api.transaction_history({"page": 2, "maxItems": 1})
    assert isinstance(result, Success), result
    rows, metadata = result.unwrap()
    assert len(rows) == 1
    assert rows[0]["type"] == "withdrawal"
    assert metadata == {"currentPage": 2, "totalPages": 2, "maxItems": 1}


TRANSACTION_TYPES = next(
    parameter["schema"]["enum"]
    for parameter in load_specification()["paths"]["/account/history"]["get"]["parameters"]
    if parameter["name"] == "type"
)


@pytest.mark.parametrize("transaction_type", TRANSACTION_TYPES)
def test_documented_transaction_types(private_api: PrivateAPI, transaction_type: str) -> None:
    result = private_api.transaction_history({"type": transaction_type}, model=private_models.TransactionHistory)
    assert isinstance(result, Success), result
    assert result.unwrap()[0].root[0].type == transaction_type


def test_signature_is_verified(private_api: PrivateAPI, exchange: FakeBitvavo) -> None:
    private_api.http.configure_key(API_KEY, "wrong-secret", 0)
    result = private_api.balance()
    assert isinstance(result, Failure)
    assert result.failure().http_status == 403
    assert result.failure().error_code == 309
    assert len(exchange.orders) == 1


def test_access_window_is_verified(private_api: PrivateAPI, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(time, "time", lambda: NOW_MS / 1000 - 11)
    result = private_api.balance()
    assert isinstance(result, Failure)
    assert result.failure().error_code == 304


@pytest.mark.parametrize(("key", "code"), [("", 300), ("short", 301), ("b" * 64, 305)])
def test_invalid_credentials_are_rejected(private_api: PrivateAPI, key: str, code: int) -> None:
    private_api.http.configure_key(key, API_SECRET, 0)
    result = private_api.balance()
    assert isinstance(result, Failure)
    assert result.failure().error_code == code


@pytest.mark.parametrize("window", [99, 60001])
def test_invalid_access_window(private_api: PrivateAPI, window: int) -> None:
    private_api.http.settings.access_window_ms = window
    result = private_api.balance()
    assert isinstance(result, Failure)
    assert result.failure().error_code == 303


def test_pre_operator_id_responses_remain_readable(exchange: FakeBitvavo) -> None:
    trade = exchange.responses["GET /trades"][0].copy()
    trade.pop("operatorId")
    assert private_models.Trade.model_validate(trade).operator_id is None
    order = exchange.responses["order"].copy()
    order.pop("operatorId")
    assert private_models.Order.model_validate(order).operator_id is None


@pytest.mark.parametrize("model", [None, private_models.Order])
def test_minimal_order_response(private_api: PrivateAPI, model: type | None) -> None:
    result = private_api.place_order(
        "BTC-EUR",
        "buy",
        "limit",
        OPERATOR_ID,
        {"amount": "1", "price": "100"},
        response_required=False,
        model=model,
    )
    assert isinstance(result, Success), result
    assert {"market", "orderId", "created", "updated"} <= result.unwrap().keys()
    assert "amount" not in result.unwrap()


def test_minimal_update_response(private_api: PrivateAPI) -> None:
    result = private_api.update_order(
        "BTC-EUR",
        OPERATOR_ID,
        order_id=ORDER_ID,
        price="101",
        response_required=False,
        model=private_models.Order,
    )
    assert isinstance(result, Success), result
    assert result.unwrap()["orderId"] == ORDER_ID
    assert "price" not in result.unwrap()


def test_operator_id_required_by_contract(private_api: PrivateAPI) -> None:
    result = private_api.http.request(
        "POST",
        "/order",
        body={"market": "BTC-EUR", "side": "buy", "orderType": "limit", "amount": "1", "price": "100"},
    )
    assert isinstance(result, Failure)
    assert result.failure().http_status == 400
    assert result.failure().error_code == 203


def test_tick_size_error(private_api: PrivateAPI, exchange: FakeBitvavo) -> None:
    result = private_api.place_order("BTC-EUR", "buy", "limit", OPERATOR_ID, {"amount": "1", "price": "100.005"})
    assert isinstance(result, Failure)
    assert result.failure().error_code == 422
    assert len(exchange.orders) == 1


def test_removed_order_pagination_parameter(private_api: PrivateAPI) -> None:
    result = private_api.get_orders("BTC-EUR", {"orderId": ORDER_ID})
    assert isinstance(result, Failure)
    assert result.failure().http_status == 400


def test_deprecated_sdk_trade_filter_uses_supported_parameter(private_api: PrivateAPI, exchange: FakeBitvavo) -> None:
    result = private_api.trade_history("BTC-EUR", {"tradeId": ORDER_ID})
    assert isinstance(result, Success), result
    assert exchange.requests[-1]["query"] == {"tradeIdTo": ORDER_ID, "market": "BTC-EUR"}


def test_provider_rejects_invalid_response(private_api: PrivateAPI, exchange: FakeBitvavo) -> None:
    exchange.responses["GET /balance"][0]["available"] = 42
    result = private_api.balance()
    assert isinstance(result, Failure)
    assert result.failure().http_status == 500
    assert "not of type 'string'" in result.failure().raw["detail"]


def test_legacy_order_and_withdrawal(legacy: Bitvavo, exchange: FakeBitvavo) -> None:
    created = legacy.place_order("BTC-EUR", "buy", "limit", OPERATOR_ID, {"amount": "0.02", "price": "100.01"})
    assert "errorCode" not in created, created
    fetched = legacy.get_order("BTC-EUR", created["orderId"])
    assert fetched == created
    updated = legacy.update_order("BTC-EUR", created["orderId"], OPERATOR_ID, {"price": "101.01"})
    assert updated["price"] == "101.01"
    canceled = legacy.cancel_order("BTC-EUR", OPERATOR_ID, orderId=created["orderId"])
    assert canceled["orderId"] == created["orderId"]
    withdrawal = legacy.withdraw_assets("BTC", "0.02", "offline-recipient", {})
    assert withdrawal == {"success": True, "symbol": "BTC", "amount": "0.02"}
    assert exchange.responses["GET /withdrawalHistory"][0]["address"] == "offline-recipient"


@pytest.mark.parametrize(
    ("method", "options", "weight"),
    [
        ("cancel_orders", {"operatorId": OPERATOR_ID}, 100),
        ("cancel_orders", {"operatorId": OPERATOR_ID, "market": "BTC-EUR"}, 25),
        ("orders_open", {}, 100),
        ("orders_open", {"market": "BTC-EUR"}, 5),
    ],
)
def test_legacy_documented_weights(legacy: Bitvavo, method: str, options: dict, weight: int) -> None:
    with patch.object(legacy, "get_best_api_key_config", wraps=legacy.get_best_api_key_config) as select:
        result = getattr(legacy, method)(options)
    assert not isinstance(result, dict) or "errorCode" not in result, result
    assert select.call_args.args == (weight,)


class TestGetOrdersValidation:
    """Unit tests for get_orders parameter validation."""

    def test_get_orders_invalid_limit(self) -> None:
        """Test get_orders with invalid limit values."""
        settings = BitvavoSettings(api_keys=[{"key": "k", "secret": "s"}])
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
        settings = BitvavoSettings(api_keys=[{"key": "k", "secret": "s"}])
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
        settings = BitvavoSettings(api_keys=[{"key": "k", "secret": "s"}])
        rate_limiter = RateLimitManager(100, 10)
        http_client = HTTPClient(settings, rate_limiter)
        private_api = PrivateAPI(http_client)

        # Test start > end
        with pytest.raises(ValueError, match=r"Start timestamp .* cannot be greater than end timestamp"):
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
