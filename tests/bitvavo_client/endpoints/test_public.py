from __future__ import annotations

from typing import Any

import polars as pl
import pytest
from returns.result import Failure, Success

from bitvavo_client.auth.rate_limit import RateLimitManager
from bitvavo_client.core import models
from bitvavo_client.core.settings import BitvavoSettings
from bitvavo_client.endpoints.public import PublicAPI
from bitvavo_client.transport.http import HTTPClient


def optional_length(obj: Any) -> int | None:
    """Helper to get length of an object if possible."""
    try:
        return len(obj)
    except TypeError:
        return None


# for printing Polars
pl.Config.set_tbl_width_chars(200)
pl.Config.set_tbl_cols(15)


class TestPublicAPI:
    """Basic smoke tests for public endpoints."""

    @pytest.fixture(scope="module")
    def public_api(self) -> PublicAPI:
        self.settings: BitvavoSettings = BitvavoSettings()
        self.rate_limiter: RateLimitManager = RateLimitManager(
            self.settings.default_rate_limit,
            self.settings.rate_limit_buffer,
        )
        self.http: HTTPClient = HTTPClient(self.settings, self.rate_limiter)
        return PublicAPI(self.http)

    def test_time_model(self, public_api: PublicAPI) -> None:
        """Time endpoint should return server time as a ServerTime model."""
        result = public_api.time()
        match result:
            case Success(data):
                assert isinstance(data, models.ServerTime)
                assert isinstance(data.time, int)
                assert isinstance(data.time_ns, int)
            case Failure(error):
                msg = f"Markets endpoint failed with error: {error}"
                raise AssertionError(msg)

    def test_time_with_pydantic_model(self, public_api: PublicAPI) -> None:
        """Test that the model parameter works for Pydantic validation."""
        result = public_api.time(model=models.ServerTime)
        match result:
            case Success(data):
                # If model validation succeeds, data should be the Pydantic model instance
                if isinstance(data, models.ServerTime):
                    assert isinstance(data.time, int)
                    assert isinstance(data.time_ns, int)
                else:
                    # If validation fails, it falls back to dict
                    assert isinstance(data, dict)
                    assert "time" in data
            case Failure(error):
                # Could fail due to API issues or validation errors
                assert hasattr(error, "http_status")

    def test_markets_raw(self, public_api: PublicAPI) -> None:
        result = public_api.markets(model=Any)
        match result:
            case Success(data):
                assert isinstance(data, list)
                assert optional_length(data)

                if optional_length(data):
                    first = data[0]
                    # Support both dict items and Pydantic model instances
                    assert isinstance(first, dict)
                    # Pydantic model: access attributes directly
                    assert "market" in first
                    assert isinstance(first["market"], str)
                    # common fields that should exist on a market entry
                    assert "base" in first
                    assert isinstance(first["base"], str)
                    assert "quote" in first
                    assert isinstance(first["quote"], str)
            case Failure(error):
                msg = f"Markets endpoint failed with error: {error}"
                raise AssertionError(msg)

    def test_markets_model(self, public_api: PublicAPI) -> None:
        result = public_api.markets()
        match result:
            case Success(data):
                # Expect a Markets model (typically a list-like collection of market entries)
                assert isinstance(data, models.Markets)
                assert optional_length(data)

                if optional_length(data):
                    first = data[0]
                    # Support both dict items and Pydantic model instances
                    assert isinstance(first, models.Market)
                    # Pydantic model: access attributes directly
                    assert hasattr(first, "market")
                    assert isinstance(first.market, str)
                    # common fields that should exist on a market entry
                    assert hasattr(first, "base")
                    assert isinstance(first.base, str)
                    assert hasattr(first, "quote")
                    assert isinstance(first.quote, str)

            case Failure(error):
                msg = f"Markets endpoint failed with error: {error}"
                raise AssertionError(msg)

    def test_markets_dataframe(self, public_api: PublicAPI) -> None:
        """
        # TODO(NostraDavid): Verify Narwhals IntoFrame functionality here.
        """
        result = public_api.markets(
            model=pl.DataFrame,
            schema={
                "market": pl.Categorical,
                "status": pl.Categorical,
                "base": pl.Categorical,
                "quote": pl.Categorical,
                "pricePrecision": pl.Int8,
                "minOrderInBaseAsset": pl.Float64,
                "minOrderInQuoteAsset": pl.Float64,
                "maxOrderInBaseAsset": pl.Float64,
                "maxOrderInQuoteAsset": pl.Float64,
                "quantityDecimals": pl.Int8,
                "notionalDecimals": pl.Int8,
                "tickSize": pl.Float64,
                "maxOpenOrders": pl.Int8,
                "feeCategory": pl.Categorical,
                "orderTypes": pl.List(pl.Utf8),
            },
        )
        match result:
            case Success(data):
                assert isinstance(data, pl.DataFrame)
                assert optional_length(data)

                if optional_length(data):
                    # Convert DataFrame to a list of dicts so rows can be inspected as dicts
                    rows = data.to_dicts()
                    assert optional_length(rows)

                    first = rows[0]
                    # Support dict items representing a market entry
                    assert isinstance(first, dict)
                    # Pydantic model: access attributes directly
                    assert "market" in first
                    assert isinstance(first["market"], str)
                    # common fields that should exist on a market entry
                    assert "base" in first
                    assert isinstance(first["base"], str)
                    assert "quote" in first
                    assert isinstance(first["quote"], str)
            case Failure(error):
                msg = f"Markets endpoint failed with error: {error}"
                raise AssertionError(msg)

    def test_market_with_options(self, public_api: PublicAPI) -> None:
        """Test single market endpoint with query options."""
        # Test with market filter
        result = public_api.markets(options={"market": "BTC-EUR"}, model=Any)
        match result:
            case Success(data):
                assert isinstance(data, (dict, list))
                # With specific market filter, should get dict or single-item list
                if isinstance(data, dict):
                    assert "market" in data
                    assert data["market"] == "BTC-EUR"
                elif isinstance(data, list) and len(data) > 0:
                    assert data[0]["market"] == "BTC-EUR"
            case Failure(error):
                assert hasattr(error, "http_status")

    def test_assets_raw(self, public_api: PublicAPI) -> None:
        """Assets endpoint should return asset information."""
        result = public_api.assets(model=Any)
        match result:
            case Success(data):
                assert isinstance(data, (dict, list))
                # Normalize to a single dict for assertions whether we receive a list or a single dict
                if isinstance(data, list):
                    assert len(data) > 0
                    first = data[0]
                else:
                    first = data

                assert isinstance(first, dict)
                # Basic required fields and their expected types based on the sample payload
                assert "symbol" in first
                assert isinstance(first["symbol"], str)
                assert "name" in first
                assert isinstance(first["name"], str)
                assert "decimals" in first
                assert isinstance(first["decimals"], int)
                # depositFee/withdrawalFee may be returned as strings or numbers depending on the API
                assert "depositFee" in first
                assert isinstance(first["depositFee"], (str, int, float))
                assert "withdrawalFee" in first
                assert isinstance(first["withdrawalFee"], (str, int, float))
                assert "networks" in first
                assert isinstance(first["networks"], list)
            case Failure(error):
                msg = f"Assets endpoint failed with error: {error}"
                raise AssertionError(msg)

    def test_assets_model(self, public_api: PublicAPI) -> None:
        """Assets endpoint should return asset information as models or dicts."""
        result = public_api.assets()
        match result:
            case Success(data):
                # Accept Pydantic models, lists of dicts, or dict
                if isinstance(data, models.Assets):
                    # Models collection (list-like)
                    assert optional_length(data)
                    if optional_length(data):
                        first = data[0]
                        assert isinstance(first, models.Asset)
                        assert isinstance(first.symbol, str)
                        assert isinstance(first.name, str)
                        assert isinstance(first.decimals, int)
                        assert isinstance(first.networks, list)
            case Failure(error):
                msg = f"Assets endpoint failed with error: {error}"
                raise AssertionError(msg)

    def test_assets_dataframe(self, public_api: PublicAPI) -> None:
        """Assets endpoint should return asset information as a Polars DataFrame when requested."""
        result = public_api.assets(
            model=pl.DataFrame,
            schema={
                "symbol": pl.Categorical,
                "name": pl.Utf8,
                "decimals": pl.Int8,
                "depositFee": pl.Int8,
                "depositConfirmations": pl.Int16,
                "depositStatus": pl.Categorical,
                "withdrawalFee": pl.Float64,
                "withdrawalMinAmount": pl.Float64,
                "withdrawalStatus": pl.Categorical,
                "networks": pl.List(pl.Categorical),
                "message": pl.Utf8,
            },
        )
        match result:
            case Success(data):
                # Expect a Polars DataFrame
                assert isinstance(data, pl.DataFrame)
                assert optional_length(data)

                if optional_length(data):
                    rows = data.to_dicts()
                    assert optional_length(rows)

                    first = rows[0]
                    assert isinstance(first, dict)
                    # Basic required fields and their expected types
                    assert "symbol" in first
                    assert isinstance(first["symbol"], str)
                    assert "name" in first
                    assert isinstance(first["name"], str)
                    assert "decimals" in first
                    assert isinstance(first["decimals"], int)
                    # networks column should contain list-like values (represented as list in dicts)
                    assert "networks" in first
                    assert isinstance(first["networks"], list)
            case Failure(error):
                msg = f"Assets endpoint failed with error: {error}"
                raise AssertionError(msg)

    def test_book_with_market_raw(self, public_api: PublicAPI) -> None:
        """Book endpoint should return raw order book for a market and validate structure."""
        result = public_api.book("BTC-EUR", model=Any)
        match result:
            case Success(data):
                # Expect a dict-like order book
                assert isinstance(data, dict)
                # At least one of the sides should be present
                assert "bids" in data or "asks" in data

                def validate_side(side: str) -> None:
                    if side in data:
                        side_val = data[side]
                        assert isinstance(side_val, list)
                        # If non-empty, each entry should be a price/amount pair (or tuple/list)
                        if optional_length(side_val):
                            first = side_val[0]
                            assert isinstance(first, (list, tuple))
                            assert len(first) >= 2
                            price, amount, *rest = first
                            assert isinstance(price, (str, float, int))
                            assert isinstance(amount, (str, float, int))

                validate_side("bids")
                validate_side("asks")
            case Failure(error):
                msg = f"book endpoint failed with error: {error}"
                raise AssertionError(msg)

    def test_book_with_market_model(self, public_api: PublicAPI) -> None:
        """Book endpoint should return an OrderBook model and validate its structure."""
        result = public_api.book("BTC-EUR", model=models.OrderBook)
        match result:
            case Success(data):
                # Expect a Pydantic model instance when requesting models.OrderBook,
                # but tolerate dict-like fallbacks and validate the order book shape.
                assert isinstance(data, (models.OrderBook, dict))

                # Obtain sides in a flexible way (attribute or mapping)
                def get_side(obj: Any, name: str) -> Any:
                    if isinstance(obj, dict):
                        return obj.get(name)
                    return getattr(obj, name, None)

                bids = get_side(data, "bids")
                asks = get_side(data, "asks")

                assert bids is not None or asks is not None

                def validate_side(side_val: Any) -> None:
                    if side_val is None:
                        return
                    assert isinstance(side_val, list)
                    if optional_length(side_val):
                        first = side_val[0]
                        # Accept list/tuple (price, amount, ...)
                        if isinstance(first, (list, tuple)):
                            assert len(first) >= 2
                            price, amount, *rest = first
                            assert isinstance(price, (str, float, int))
                            assert isinstance(amount, (str, float, int))
                        # Accept dict-like entries with common keys
                        elif isinstance(first, dict):
                            assert any(k in first for k in ("price", "amount", "qty", "volume"))
                        # Accept model-like entries with attributes
                        else:
                            assert any(hasattr(first, attr) for attr in ("price", "amount", "qty", "volume"))

                validate_side(bids)
                validate_side(asks)
            case Failure(error):
                msg = f"book endpoint failed with error: {error}"
                raise AssertionError(msg)

    def test_book_with_market_dataframe(self, public_api: PublicAPI) -> None:
        """Book endpoint should return raw order book for a market and validate structure."""
        result = public_api.book(
            "BTC-EUR",
            model=pl.DataFrame,
            schema={
                "market": pl.Utf8,
                "nonce": pl.Int32,
                "bids": pl.List(pl.Utf8),
                "asks": pl.List(pl.Utf8),
                "timestamp": pl.Int64,
            },
        )
        match result:
            case Success(data):
                # Expect a DataFrame-like order book
                assert isinstance(data, pl.DataFrame)
                # At least one of the sides should be present (check columns for Polars DataFrame)
                assert "bids" in data.columns or "asks" in data.columns

                def validate_side(side: str) -> None:
                    if side in data.columns:
                        side_series = data[side]
                        # Polars returns a Series; convert to Python list for inspection
                        side_list = side_series.to_list() if isinstance(side_series, pl.Series) else side_series

                        # If non-empty, each entry should be a price/amount pair (or tuple/list)
                        if optional_length(side_list):
                            first = side_list[0]
                            assert isinstance(first, (list, tuple))
                            assert len(first) >= 2
                            price, amount, *rest = first
                            assert isinstance(price, (str, float, int))
                            assert isinstance(amount, (str, float, int))

                validate_side("bids")
                validate_side("asks")
            case Failure(error):
                msg = f"book endpoint failed with error: {error}"
                raise AssertionError(msg)

    def test_public_trades_raw(self, public_api: PublicAPI) -> None:
        """Public trades endpoint should return raw trades for a market and validate structure."""
        result = public_api.public_trades("BTC-EUR", model=Any)
        match result:
            case Success(data):
                # Accept either a list of trades or a single trade dict
                if isinstance(data, list):
                    assert optional_length(data)
                    first = data[0]
                else:
                    first = data

                assert isinstance(first, dict)
                # Validate expected trade fields
                assert "id" in first
                assert isinstance(first["id"], str)
                assert "timestamp" in first
                assert isinstance(first["timestamp"], int)
                assert "amount" in first
                assert isinstance(first["amount"], (str, float, int))
                assert "price" in first
                assert isinstance(first["price"], (str, float, int))
                assert "side" in first
                assert isinstance(first["side"], str)
            case Failure(error):
                msg = f"public_trades endpoint failed with error: {error}"
                raise AssertionError(msg)

    def test_public_trades_model(self, public_api: PublicAPI) -> None:
        """Public trades endpoint should return a Trades model (list-like of Trade)."""
        result = public_api.public_trades("BTC-EUR", model=models.Trades)
        match result:
            case Success(data):
                assert isinstance(data, (models.Trades, list))
                assert optional_length(data)

                if optional_length(data):
                    first = data[0]
                    assert isinstance(first.id, str)
                    assert isinstance(first.timestamp, int)
                    assert isinstance(first.amount, (str, float, int))
                    assert isinstance(first.price, (str, float, int))
                    assert isinstance(first.side, str)
            case Failure(error):
                msg = f"public_trades endpoint failed with error: {error}"
                raise AssertionError(msg)

    def test_public_trades_dataframe(self, public_api: PublicAPI) -> None:
        """Public trades endpoint should return trades as a Polars DataFrame."""
        result = public_api.public_trades(
            "BTC-EUR",
            model=pl.DataFrame,
            schema={
                "id": pl.Utf8,
                "timestamp": pl.Int64,
                "amount": pl.Float64,
                "price": pl.Float64,
                "side": pl.Categorical,
            },
        )
        match result:
            case Success(data):
                assert isinstance(data, pl.DataFrame)
                assert optional_length(data)

                if optional_length(data):
                    rows = data.to_dicts()
                    assert optional_length(rows)

                    first = rows[0]
                    assert isinstance(first, dict)

                    assert "id" in first
                    assert isinstance(first["id"], str)

                    assert "timestamp" in first
                    assert isinstance(first["timestamp"], int)

                    assert "amount" in first
                    assert isinstance(first["amount"], (int, float, str))

                    assert "price" in first
                    assert isinstance(first["price"], (int, float, str))

                    assert "side" in first
                    assert isinstance(first["side"], str)
            case Failure(error):
                msg = f"public_trades endpoint failed with error: {error}"
                raise AssertionError(msg)

    def test_candles_raw(self, public_api: PublicAPI) -> None:
        """Public candles endpoint should return a list of candle rows (list of lists/tuples)."""
        result = public_api.candles("BTC-EUR", "1m", model=Any)
        match result:
            case Success(data):
                # Expect a list of candles
                assert isinstance(data, list)
                assert optional_length(data)

                if optional_length(data):
                    first = data[0]
                    # Each candle should be a list/tuple like:
                    # [timestamp, open, high, low, close, volume, ...]  # noqa: ERA001
                    assert isinstance(first, (list, tuple))
                    assert len(first) >= 5

                    ts = first[0]
                    assert isinstance(ts, (int, float))

                    # Validate OHLC values
                    for val in first[1:5]:
                        assert isinstance(val, (str, int, float))

                    # Optional volume and additional fields
                    if len(first) > 5:
                        vol = first[5]
                        assert isinstance(vol, (str, int, float))
            case Failure(error):
                msg = f"candles endpoint failed with error: {error}"
                raise AssertionError(msg)

    def test_candles_model(self, public_api: PublicAPI) -> None:
        """Public candles endpoint should return a Candles model (list-like of Candle entries)."""
        result = public_api.candles("BTC-EUR", "1m", model=models.Candles)
        match result:
            case Success(data):
                assert isinstance(data, (models.Candles, list))
                assert optional_length(data)

                if optional_length(data):
                    first = data[0]
                    # Model-like candle
                    ts = getattr(first, "timestamp", getattr(first, "time", None))
                    assert isinstance(ts, (int, float))
                    for attr in ("open", "high", "low", "close"):
                        assert hasattr(first, attr)
                        assert isinstance(getattr(first, attr), (str, int, float))
                    if hasattr(first, "volume"):
                        assert isinstance(first.volume, (str, int, float))
            case Failure(error):
                msg = f"candles endpoint failed with error: {error}"
                raise AssertionError(msg)

    def test_candles_dataframe(self, public_api: PublicAPI) -> None:
        """Public candles endpoint should return candles as a Polars DataFrame."""
        result = public_api.candles(
            "ADA-EUR",
            "1m",
            model=pl.DataFrame,
            schema={
                "timestamp": pl.Int64,
                "open": pl.Float64,
                "high": pl.Float64,
                "low": pl.Float64,
                "close": pl.Float64,
                "volume": pl.Float64,
            },
        )
        match result:
            case Success(data):
                assert isinstance(data, pl.DataFrame)
                assert optional_length(data)

                if optional_length(data):
                    rows = data.to_dicts()
                    assert optional_length(rows)

                    first = rows[0]
                    assert isinstance(first, dict)

                    # Timestamp may be labeled "timestamp" (preferred) or "time"
                    ts_key = "timestamp" if "timestamp" in first else "time"
                    assert ts_key in first
                    assert isinstance(first[ts_key], (int, float))

                    for key in ("open", "high", "low", "close"):
                        assert key in first
                        assert isinstance(first[key], (int, float, str))

                    # Volume can be missing or null depending on API, tolerate None
                    if "volume" in first:
                        vol = first["volume"]
                        assert vol is None or isinstance(vol, (int, float, str))
            case Failure(error):
                msg = f"candles endpoint failed with error: {error}"
                raise AssertionError(msg)

    def test_ticker_price_raw(self, public_api: PublicAPI) -> None:
        """Ticker price endpoint should return price information in multiple formats."""
        # Raw (Any) response
        result = public_api.ticker_price(model=Any)
        match result:
            case Success(data):
                assert isinstance(data, (dict, list))
                if isinstance(data, list):
                    assert optional_length(data)
                    first = data[0]
                else:
                    first = data

                assert isinstance(first, dict)
                assert "market" in first
                assert isinstance(first["market"], str)
                assert "price" in first
                assert isinstance(first["price"], (str, float, int))
            case Failure(error):
                msg = f"ticker_price endpoint failed with error: {error}"
                raise AssertionError(msg)

    def test_ticker_price_model(self, public_api: PublicAPI) -> None:
        """Ticker price endpoint should return price information with explicit TickerPrices model."""
        result = public_api.ticker_price(model=models.TickerPrices)
        match result:
            case Success(data):
                # Expect a TickerPrices model (list-like collection of ticker entries)
                assert isinstance(data, models.TickerPrices)
                assert optional_length(data)

                if optional_length(data):
                    first = data[0]
                    assert isinstance(first, models.TickerPrice)
                    assert isinstance(first.market, str)
                    assert isinstance(first.price, str)
            case Failure(error):
                msg = f"ticker_price endpoint failed with error: {error}"
                raise AssertionError(msg)

    def test_ticker_price_dataframe(self, public_api: PublicAPI) -> None:
        """Ticker price endpoint should return price information in multiple formats."""
        # Polars DataFrame representation
        result = public_api.ticker_price(
            model=pl.DataFrame,
            schema={
                "market": pl.Utf8,
                "price": pl.Float64,
            },
        )
        match result:
            case Success(data):
                assert isinstance(data, pl.DataFrame)
                assert optional_length(data)
                if optional_length(data):
                    rows = data.to_dicts()
                    assert optional_length(rows)
                    first = rows[0]
                    assert isinstance(first, dict)
                    assert "market" in first
                    assert isinstance(first["market"], str)
                    assert "price" in first
                    assert isinstance(first["price"], (str, float, int))
            case Failure(error):
                msg = f"ticker_price endpoint failed with error: {error}"
                raise AssertionError(msg)

    def test_ticker_book_raw(self, public_api: PublicAPI) -> None:
        """
        Ticker book endpoint should return best bid/ask (or price) information in raw formats, including sizes if
        present.
        """
        result = public_api.ticker_book(model=Any)
        match result:
            case Success(data):
                assert isinstance(data, (dict, list))
                first = data[0] if isinstance(data, list) else data

                assert isinstance(first, dict)
                assert "market" in first
                assert isinstance(first["market"], str)

                # Accept either a single 'price' or separate 'bid'/'ask' fields
                assert any(k in first for k in ("price", "bid", "ask"))

                if "price" in first:
                    assert isinstance(first["price"], (str, float, int))
                if "bid" in first:
                    assert isinstance(first["bid"], (str, float, int))
                if "ask" in first:
                    assert isinstance(first["ask"], (str, float, int))

                # Also validate optional size fields in both snake_case and camelCase
                if "bid_size" in first or "bidSize" in first:
                    bid_size = first.get("bid_size", first.get("bidSize"))
                    assert isinstance(bid_size, (str, float, int))
                if "ask_size" in first or "askSize" in first:
                    ask_size = first.get("ask_size", first.get("askSize"))
                    assert isinstance(ask_size, (str, float, int))
            case Failure(error):
                msg = f"ticker_book endpoint failed with error: {error}"
                raise AssertionError(msg)

    def test_ticker_book_model(self, public_api: PublicAPI) -> None:
        """Ticker book endpoint should return best bid/ask data with explicit TickerBooks model."""
        result = public_api.ticker_book(model=models.TickerBooks)
        match result:
            case Success(data):
                # Expect a TickerBooks model (list-like collection)
                assert isinstance(data, (models.TickerBooks, list))
                assert optional_length(data)

                if optional_length(data):
                    first = data[0]
                    # Support both model instances and dicts
                    assert isinstance(first.market, str)
                    # Ensure at least one price-like field exists
                    assert isinstance(first.bid, (str, float, int))
                    assert isinstance(first.ask, (str, float, int))
                    assert isinstance(first.bid_size, (str, float, int))
                    assert isinstance(first.ask_size, (str, float, int))
            case Failure(error):
                msg = f"ticker_book endpoint failed with error: {error}"
                raise AssertionError(msg)

    def test_ticker_book_dataframe(self, public_api: PublicAPI) -> None:
        """Ticker book endpoint should return best bid/ask data as a Polars DataFrame."""
        result = public_api.ticker_book(
            model=pl.DataFrame,
            schema={
                "market": pl.Categorical,
                "bid": pl.Float64,
                "bidSize": pl.Float64,
                "ask": pl.Float64,
                "askSize": pl.Float64,
            },
        )
        match result:
            case Success(data):
                assert isinstance(data, pl.DataFrame)
                assert optional_length(data)

                if optional_length(data):
                    rows = data.to_dicts()
                    assert optional_length(rows)

                    first = rows[0]
                    assert isinstance(first, dict)
                    assert isinstance(first["market"], str)

                    # Accept either a single 'price' or separate 'bid'/'ask' fields
                    assert any(k in first for k in ("price", "bid", "ask", "bid_size", "ask_size"))

                    assert isinstance(first["bid"], (str, float, int))
                    assert isinstance(first["ask"], (str, float, int))
                    assert isinstance(first["bidSize"], (str, float, int))
                    assert isinstance(first["askSize"], (str, float, int))

                    # Optional size fields in both snake_case and camelCase
                    bid_size = first.get("bid_size", first.get("bidSize"))
                    assert isinstance(bid_size, (str, float, int))
                    ask_size = first.get("ask_size", first.get("askSize"))
                    assert isinstance(ask_size, (str, float, int))
            case Failure(error):
                msg = f"ticker_book endpoint failed with error: {error}"
                raise AssertionError(msg)

    def test_ticker_24h_raw(self, public_api: PublicAPI) -> None:
        """
        Ticker_24h endpoint should return best bid/ask (or price) information in raw formats, including sizes if
        present.
        """
        result = public_api.ticker_24h(model=Any)
        match result:
            case Success(data):
                assert isinstance(data, (dict, list))
                first = data[0] if isinstance(data, list) else data

                assert isinstance(first, dict)
                assert "market" in first
                assert isinstance(first["market"], str)

                # Accept either a single 'price' or separate 'bid'/'ask' fields
                assert any(k in first for k in ("price", "bid", "ask"))

                if "price" in first:
                    assert isinstance(first["price"], (str, float, int))
                if "bid" in first:
                    assert isinstance(first["bid"], (str, float, int))
                if "ask" in first:
                    assert isinstance(first["ask"], (str, float, int))

                # Also validate optional size fields in both snake_case and camelCase
                if "bid_size" in first or "bidSize" in first:
                    bid_size = first.get("bid_size", first.get("bidSize"))
                    assert isinstance(bid_size, (str, float, int))
                if "ask_size" in first or "askSize" in first:
                    ask_size = first.get("ask_size", first.get("askSize"))
                    assert isinstance(ask_size, (str, float, int))
            case Failure(error):
                msg = f"ticker_book endpoint failed with error: {error}"
                raise AssertionError(msg)

    def test_ticker_24h_model(self, public_api: PublicAPI) -> None:
        """Ticker_24h endpoint should return a Ticker24hs model collection."""
        result = public_api.ticker_24h(model=models.Ticker24hs)
        match result:
            case Success(data):
                assert isinstance(data, (models.Ticker24hs, list))
                assert optional_length(data)

                if optional_length(data):
                    first = data[0]

                    # Expect model-like attributes
                    assert hasattr(first, "market")
                    assert isinstance(first.market, str)

                    # At least one price-like field should be present
                    has_price_like = any(hasattr(first, attr) for attr in ("last", "price", "bid", "ask"))
                    assert has_price_like

                    for attr in ("last", "price", "bid", "ask"):
                        if hasattr(first, attr):
                            val = getattr(first, attr)
                            assert isinstance(val, (str, float, int))

                    # Optional size fields
                    for attr in ("bid_size", "ask_size"):
                        if hasattr(first, attr):
                            val = getattr(first, attr)
                            assert isinstance(val, (str, float, int))

                    # Optional 24h stats fields
                    optional_fields: list[tuple[str, type | tuple[type, ...]]] = [
                        ("open", (str, float, int)),
                        ("high", (str, float, int)),
                        ("low", (str, float, int)),
                        ("volume", (str, float, int)),
                        ("volume_quote", (str, float, int)),
                        ("timestamp", int),
                    ]
                    for attr, typ in optional_fields:
                        if hasattr(first, attr):
                            assert isinstance(getattr(first, attr), typ)
            case Failure(error):
                msg = f"ticker_24h endpoint failed with error: {error}"
                raise AssertionError(msg)

    def test_ticker_24h_dataframe(self, public_api: PublicAPI) -> None:
        """Ticker_24h endpoint should return 24h ticker stats as a Polars DataFrame."""
        result = public_api.ticker_24h(
            model=pl.DataFrame,
            schema={
                "market": pl.Categorical,
                "startTimestamp": pl.Int64,
                "timestamp": pl.Int64,
                "open": pl.Float64,
                "openTimestamp": pl.Int64,
                "high": pl.Float64,
                "low": pl.Float64,
                "last": pl.Float64,
                "closeTimestamp": pl.Int64,
                "bid": pl.Float64,
                "bidSize": pl.Float64,
                "ask": pl.Float64,
                "askSize": pl.Float64,
                "volume": pl.Float64,
                "volumeQuote": pl.Float64,
            },
        )
        match result:
            case Success(data):
                assert isinstance(data, pl.DataFrame)
                assert optional_length(data)

                if optional_length(data):
                    rows = data.to_dicts()
                    assert optional_length(rows)
                    first = rows[0]
                    assert isinstance(first, dict)
                    assert "market" in first
                    assert isinstance(first["market"], str)

                    # At least one price-like field should be present
                    assert any(k in first for k in ("last", "price", "bid", "ask"))

                    for key in ("last", "price", "bid", "ask"):
                        if key in first:
                            assert isinstance(first[key], (str, float, int))

                    # Optional size fields (snake_case and camelCase)
                    for key in ("bid_size", "bidSize", "ask_size", "askSize"):
                        if key in first:
                            assert isinstance(first[key], (str, float, int))

                    # Optional 24h stats fields
                    optional_fields: list[tuple[str, type | tuple[type, ...]]] = [
                        ("open", (str, float, int)),
                        ("high", (str, float, int)),
                        ("low", (str, float, int)),
                        ("volume", (str, float, int)),
                        ("volumeQuote", (str, float, int)),
                        ("timestamp", int),
                    ]
                    for key, typ in optional_fields:
                        if key in first:
                            assert isinstance(first[key], typ)
            case Failure(error):
                msg = f"ticker_24h endpoint failed with error: {error}"
                raise AssertionError(msg)
