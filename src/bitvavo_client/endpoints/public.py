"""Public API endpoints that don't require authentication."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Literal, TypeVar

from returns.result import Failure, Success

from bitvavo_client.adapters.returns_adapter import BitvavoError
from bitvavo_client.core import public_models
from bitvavo_client.core.model_preferences import ModelPreference
from bitvavo_client.endpoints.common import create_postfix
from bitvavo_client.schemas.public_schemas import DEFAULT_SCHEMAS

# Valid intervals for candlestick data according to Bitvavo API documentation
CandleInterval = Literal["1m", "5m", "15m", "30m", "1h", "2h", "4h", "6h", "8h", "12h", "1d", "1W", "1M"]

# API parameter limits according to Bitvavo documentation
MAX_CANDLE_LIMIT = 1440  # Maximum number of candlesticks that can be requested
MAX_TRADES_LIMIT = 1000  # Maximum number of trades that can be requested
MAX_24_HOUR_MS = 86400000  # 24 hours in milliseconds
MAX_END_TIMESTAMP = 8640000000000000  # Maximum end timestamp value
MAX_TIMESTAMP_VALUE = 8640000000000000  # Maximum allowed timestamp value
MAX_BOOK_DEPTH = 1000  # Maximum depth for order book
MAX_BOOK_REPORT_DEPTH = 1000  # Maximum depth for order book report

# DataFrames preference to library mapping
_DATAFRAME_LIBRARY_MAP = {
    ModelPreference.POLARS: ("polars", "pl.DataFrame"),
    ModelPreference.PANDAS: ("pandas", "pd.DataFrame"),
    ModelPreference.PYARROW: ("pyarrow", "pa.Table"),
    ModelPreference.DASK: ("dask", "dd.DataFrame"),
    ModelPreference.MODIN: ("modin", "mpd.DataFrame"),
    ModelPreference.CUDF: ("cudf", "cudf.DataFrame"),
    ModelPreference.IBIS: ("ibis", "ibis.Table"),
}

if TYPE_CHECKING:  # pragma: no cover
    from collections.abc import Mapping

    import httpx
    from returns.result import Result

    from bitvavo_client.core.types import AnyDict
    from bitvavo_client.transport.http import HTTPClient

T = TypeVar("T")


class PublicAPI:
    """Handles all public Bitvavo API endpoints."""

    def __init__(
        self,
        http_client: HTTPClient,
        *,
        preferred_model: ModelPreference | str | None = None,
        default_schema: Mapping[str, object] | None = None,
    ) -> None:
        """Initialize public API handler.

        Args:
            http_client: HTTP client for making requests
            preferred_model: Preferred model format for responses
            default_schema: Default schema for DataFrame conversion
        """
        self.http: HTTPClient = http_client

        # Handle preferred_model parameter - try to convert strings to ModelPreference,
        # but allow arbitrary strings to pass through for custom handling
        if preferred_model is None:
            self.preferred_model = None
        elif isinstance(preferred_model, ModelPreference):
            self.preferred_model = preferred_model
        elif isinstance(preferred_model, str):
            try:
                self.preferred_model = ModelPreference(preferred_model)
            except ValueError:
                # If string doesn't match a valid ModelPreference, store as-is
                self.preferred_model = preferred_model
        else:
            self.preferred_model = preferred_model

        # If using DATAFRAME preference without a default schema, we could provide sensible defaults
        # But keep it explicit for now - users can import and use schemas as needed
        self.default_schema = default_schema

    def _get_effective_model(
        self,
        endpoint_type: str,
        model: type[T] | Any | None,
        schema: Mapping[str, object] | None,
    ) -> tuple[type[T] | Any | None, Mapping[str, object] | None]:
        """Get the effective model and schema to use for a request.

        Args:
            endpoint_type: Type of endpoint (e.g., 'time', 'markets', 'assets')
            model: Model explicitly passed to method (overrides preference)
            schema: Schema explicitly passed to method

        Returns:
            Tuple of (effective_model, effective_schema)
        """
        # If model is explicitly provided, use it
        if model is not None:
            return model, schema

        # If no preferred model is set, return Any (raw response)
        if self.preferred_model is None:
            return Any, schema

        # Apply preference based on enum value
        if self.preferred_model == ModelPreference.RAW:
            return Any, schema

        # Handle all DataFrame preferences
        if self.preferred_model in _DATAFRAME_LIBRARY_MAP:
            # Use the provided schema, fallback to instance default, then to endpoint-specific default
            effective_schema = schema or self.default_schema or DEFAULT_SCHEMAS.get(endpoint_type)
            # Return the preference itself, not a specific DataFrame class
            return self.preferred_model, effective_schema

        if self.preferred_model == ModelPreference.PYDANTIC:
            # Map endpoint types to appropriate Pydantic models
            endpoint_model_map = {
                "time": public_models.ServerTime,
                "markets": public_models.Markets,
                "assets": public_models.Assets,
                "book": public_models.OrderBook,
                "trades": public_models.Trades,
                "candles": public_models.Candles,
                "ticker_price": public_models.TickerPrices,
                "ticker_book": public_models.TickerBooks,
                "ticker_24h": public_models.Ticker24hs,
                "report_book": public_models.OrderBookReport,
                "report_trades": public_models.TradesReport,
            }
            return endpoint_model_map.get(endpoint_type, dict), schema

        # Default case (AUTO or unknown)
        return None, schema

    def _convert_raw_result(
        self,
        raw_result: Result[Any, BitvavoError | httpx.HTTPError],
        endpoint_type: str,
        model: type[T] | Any | None,
        schema: Mapping[str, object] | None,
    ) -> Result[Any, BitvavoError | httpx.HTTPError]:
        """Convert raw API result to the desired model format.

        Args:
            raw_result: Raw result from HTTP client
            endpoint_type: Type of endpoint (e.g., 'time', 'markets', 'assets')
            model: Model explicitly passed to method (overrides preference)
            schema: Schema explicitly passed to method

        Returns:
            Result with converted data or original error
        """
        # If the raw result is an error, return it as-is
        if isinstance(raw_result, Failure):
            return raw_result

        # Get the effective model and schema to use
        effective_model, effective_schema = self._get_effective_model(endpoint_type, model, schema)

        # If no conversion needed (raw data requested), return as-is
        if effective_model is Any or effective_model is None or effective_model == ModelPreference.RAW:
            return raw_result

        # Extract the raw data
        raw_data = raw_result.unwrap()

        # Perform conversion
        try:
            # Handle DataFrame preferences specially
            if isinstance(effective_model, ModelPreference) and effective_model in _DATAFRAME_LIBRARY_MAP:
                parsed = self._create_dataframe(raw_data, effective_model, effective_schema)
            elif hasattr(effective_model, "model_validate"):
                # Pydantic model
                parsed = effective_model.model_validate(raw_data)  # type: ignore[misc]
            else:
                # Simple constructor call - this handles dict and other simple types
                parsed = effective_model(raw_data)  # type: ignore[misc]

            return Success(parsed)
        except (ValueError, TypeError, AttributeError) as exc:
            # If conversion fails, return a structured error
            error = BitvavoError(
                http_status=500,
                error_code=-1,
                reason="Model conversion failed",
                message=str(exc),
                raw=raw_data if isinstance(raw_data, dict) else {"raw": raw_data},
            )
            return Failure(error)

    def _create_dataframe(
        self,
        data: Any,
        preference: ModelPreference,
        schema: Mapping[str, object] | None,
    ) -> Any:
        """Create a DataFrame from raw data using the specified preference.

        Args:
            data: Raw data to convert
            preference: DataFrame preference (POLARS, PANDAS, etc.)
            schema: Schema for DataFrame conversion

        Returns:
            DataFrame instance

        Raises:
            ImportError: If the required DataFrame library is not available
            ValueError: If DataFrame creation fails
        """
        if preference == ModelPreference.POLARS:
            import polars as pl

            return self._create_polars_dataframe(data, schema, pl)

        if preference == ModelPreference.PANDAS:
            import pandas as pd

            return pd.DataFrame(data)

        if preference == ModelPreference.PYARROW:
            import pyarrow as pa

            return pa.Table.from_pylist(data if isinstance(data, list) else [data])

        # For other DataFrame types, try basic conversion
        msg = f"DataFrame preference {preference} not yet fully implemented"
        raise NotImplementedError(msg)

    def _create_polars_dataframe(
        self,
        data: Any,
        schema: Mapping[str, object] | None,
        pl: Any,  # polars module
    ) -> Any:
        """Create a Polars DataFrame with proper schema handling.

        Args:
            data: Raw data to convert
            schema: Schema for DataFrame conversion
            pl: Polars module

        Returns:
            Polars DataFrame
        """
        if schema is None:
            return pl.DataFrame(data)

        # For Polars, we need to handle the schema with strict=False for compatibility
        try:
            return pl.DataFrame(data, schema=schema, strict=False)
        except Exception:
            # Fallback to basic DataFrame creation if schema fails
            return pl.DataFrame(data)

    def time(
        self,
        *,
        model: type[T] | Any | None = None,
        schema: dict | None = None,
    ) -> Result[T, BitvavoError | httpx.HTTPError]:
        """Get server time.

        Args:
            model: Optional Pydantic model to validate response
            schema: Optional schema for DataFrame conversion

        Returns:
            Result containing server time or error
        """
        # Get raw data from API
        raw_result = self.http.request("GET", "/time", weight=1)
        # Convert to desired format
        return self._convert_raw_result(raw_result, "time", model, schema)

    def markets(
        self,
        options: AnyDict | None = None,
        *,
        model: type[T] | Any | None = None,
        schema: dict | None = None,
    ) -> Result[T, BitvavoError | httpx.HTTPError]:
        """Get market information.

        Args:
            options: Optional query parameters
            model: Optional Pydantic model to validate response
            schema: Optional schema for DataFrame conversion

        Returns:
            Result containing market information or error
        """
        # Get raw data from API
        postfix = create_postfix(options)
        raw_result = self.http.request("GET", f"/markets{postfix}", weight=1)
        # Convert to desired format
        return self._convert_raw_result(raw_result, "markets", model, schema)

    def assets(
        self,
        options: AnyDict | None = None,
        *,
        model: type[T] | Any | None = None,
        schema: dict | None = None,
    ) -> Result[T, BitvavoError | httpx.HTTPError]:
        """Get asset information.

        Returns information about the specified assets including deposit/withdrawal
        fees, confirmations required, status, and supported networks.

        Endpoint: GET /v2/assets
        Rate limit weight: 1

        Args:
            options: Optional query parameters:
                - symbol (str): The asset symbol (e.g., 'BTC'). If not specified,
                  all supported assets are returned.
            model: Optional Pydantic model to validate response
            schema: Optional schema for DataFrame conversion

        Returns:
            Result containing asset information array:
            [
                {
                    "symbol": "BTC",
                    "name": "Bitcoin",
                    "decimals": 8,
                    "depositFee": "0",
                    "depositConfirmations": 10,
                    "depositStatus": "OK",
                    "withdrawalFee": "0.2",
                    "withdrawalMinAmount": "0.2",
                    "withdrawalStatus": "OK",
                    "networks": ["Mainnet"],
                    "message": ""
                }
            ]

        Note:
            This is a public endpoint but authenticating gives higher rate limits.
            Status values can be: "OK", "MAINTENANCE", "DELISTED".
        """
        postfix = create_postfix(options)
        raw_result = self.http.request("GET", f"/assets{postfix}", weight=1)
        return self._convert_raw_result(raw_result, "assets", model, schema)

    def book(
        self,
        market: str,
        options: AnyDict | None = None,
        *,
        model: type[T] | Any | None = None,
        schema: dict | None = None,
    ) -> Result[T, BitvavoError | httpx.HTTPError]:
        """Get order book for a market.

        Returns the list of up to 1000 bids and asks per request for the specified
        market, sorted by price.

        Endpoint: GET /v2/{market}/book
        Rate limit weight: 1

        Args:
            market: Market symbol (e.g., 'BTC-EUR')
            options: Optional query parameters:
                - depth (int): Number of bids and asks to return (default: 1000, max: 1000)
            model: Optional Pydantic model to validate response
            schema: Optional schema for DataFrame conversion

        Returns:
            Result containing order book data with structure:
            {
                "market": "BTC-EUR",
                "nonce": 438524,
                "bids": [["4999.9","0.015"], ...],
                "asks": [["5001.1","0.015"], ...],
                "timestamp": 1542967486256
            }

        Note:
            This is a public endpoint but authenticating gives higher rate limits.
        """
        # Validate depth parameter if provided
        if options and "depth" in options:
            depth = options["depth"]
            if not isinstance(depth, int) or not (1 <= depth <= MAX_BOOK_DEPTH):
                msg = f"depth must be an integer between 1 and {MAX_BOOK_DEPTH} (inclusive)"
                raise ValueError(msg)

        postfix = create_postfix(options)
        raw_result = self.http.request("GET", f"/{market}/book{postfix}", weight=1)
        return self._convert_raw_result(raw_result, "book", model, schema)

    def trades(
        self,
        market: str,
        options: AnyDict | None = None,
        *,
        model: type[T] | Any | None = None,
        schema: dict | None = None,
    ) -> Result[T, BitvavoError | httpx.HTTPError]:
        """Get public trades for a market.

        Returns the list of trades from the specified market and time period made by all Bitvavo users.
        The returned trades are sorted by their timestamp in descending order (latest to earliest).

        Endpoint: GET /v2/{market}/trades
        Rate limit weight: 5

        Args:
            market: Market symbol (e.g., 'BTC-EUR')
            options: Optional query parameters:
                - limit: int (1-1000, default 500) - Maximum number of trades to return
                - start: int - Unix timestamp in milliseconds to start from
                - end: int - Unix timestamp in milliseconds to end at (max 24h after start)
                - tradeIdFrom: str - Trade ID to start from
                - tradeIdTo: str - Trade ID to end at
            model: Optional Pydantic model to validate response
            schema: Optional schema for DataFrame conversion

        Returns:
            Result containing public trades data or error.
            Each trade contains: id, timestamp, amount, price, side

        Example:
            >>> client.public.trades("BTC-EUR")
            >>> client.public.trades("BTC-EUR", {"limit": 100})
            >>> client.public.trades("BTC-EUR", {"start": 1577836800000, "end": 1577836900000})
        """
        # Validate options if provided
        if options:
            self._validate_trades_options(options)

        postfix = create_postfix(options)
        raw_result = self.http.request("GET", f"/{market}/trades{postfix}", weight=5)
        return self._convert_raw_result(raw_result, "trades", model, schema)

    def candles(
        self,
        market: str,
        interval: CandleInterval,
        options: AnyDict | None = None,
        *,
        model: type[T] | Any | None = None,
        schema: dict | None = None,
    ) -> Result[T, BitvavoError | httpx.HTTPError]:
        """Get candlestick data for a market.

        Args:
            market: Market symbol
            interval: Time interval - must be one of: 1m, 5m, 15m, 30m, 1h, 2h, 4h, 6h, 8h, 12h, 1d, 1W, 1M
            options: Optional query parameters (limit, start, end)
            model: Optional Pydantic model to validate response
            schema: Optional schema for DataFrame conversion

        Returns:
            Result containing candlestick data or error

        Raises:
            ValueError: If interval is invalid or limit is not in range 1-1440 or timestamps are invalid
        """
        # Validate interval parameter at runtime
        valid_intervals = {"1m", "5m", "15m", "30m", "1h", "2h", "4h", "6h", "8h", "12h", "1d", "1W", "1M"}
        if interval not in valid_intervals:
            msg = f"interval must be one of: {', '.join(sorted(valid_intervals))}"
            raise ValueError(msg)

        if options is None:
            options = {}

        # Validate optional parameters according to Bitvavo API documentation
        if "limit" in options:
            limit = options["limit"]
            if not isinstance(limit, int) or not (1 <= limit <= MAX_CANDLE_LIMIT):
                msg = f"limit must be an integer between 1 and {MAX_CANDLE_LIMIT} (inclusive)"
                raise ValueError(msg)

        if "start" in options:
            start = options["start"]
            if not isinstance(start, int) or start < 0:
                msg = "start must be a non-negative unix timestamp in milliseconds"
                raise ValueError(msg)

        if "end" in options:
            end = options["end"]
            if not isinstance(end, int) or end < 0 or end > MAX_TIMESTAMP_VALUE:
                msg = f"end must be a unix timestamp in milliseconds <= {MAX_TIMESTAMP_VALUE}"
                raise ValueError(msg)

        options["interval"] = interval
        postfix = create_postfix(options)
        raw_result = self.http.request("GET", f"/{market}/candles{postfix}", weight=1)
        return self._convert_raw_result(raw_result, "candles", model, schema)

    def ticker_price(
        self,
        options: AnyDict | None = None,
        *,
        model: type[T] | Any | None = None,
        schema: dict | None = None,
    ) -> Result[T, BitvavoError | httpx.HTTPError]:
        """Get ticker prices for markets.

        Returns prices of the latest trades on Bitvavo for all markets or a single market.
        A tick in a market is any change in the price of a digital asset.

        Endpoint: GET /v2/ticker/price
        Rate limit weight: 1

        Args:
            options: Optional query parameters:
                - market (str): The market for which to return the latest information.
                  For the list of all markets, use the markets() method.
                  Example: 'BTC-EUR'
            model: Optional Pydantic model to validate response
            schema: Optional schema for DataFrame conversion

        Returns:
            Result containing ticker price data array:
            [
                {
                    "market": "BTC-EUR",
                    "price": "34243"
                }
            ]

        Note:
            This is a public endpoint but authenticating gives higher rate limits.
        """
        # Validate market parameter if provided
        if options and "market" in options:
            market = options["market"]
            if not isinstance(market, str) or not market.strip():
                msg = "market must be a non-empty string"
                raise ValueError(msg)

        postfix = create_postfix(options)
        raw_result = self.http.request("GET", f"/ticker/price{postfix}", weight=1)
        return self._convert_raw_result(raw_result, "ticker_price", model, schema)

    def ticker_book(
        self,
        options: AnyDict | None = None,
        *,
        model: type[T] | Any | None = None,
        schema: dict | None = None,
    ) -> Result[T, BitvavoError | httpx.HTTPError]:
        """Get ticker book.

        Args:
            options: Optional query parameters
            model: Optional Pydantic model to validate response
            schema: Optional schema for DataFrame conversion

        Returns:
            Result containing ticker book data or error
        """
        postfix = create_postfix(options)
        raw_result = self.http.request("GET", f"/ticker/book{postfix}", weight=1)
        return self._convert_raw_result(raw_result, "ticker_book", model, schema)

    def ticker_24h(
        self,
        options: AnyDict | None = None,
        *,
        model: type[T] | Any | None = None,
        schema: dict | None = None,
    ) -> Result[T, BitvavoError | httpx.HTTPError]:
        """Get 24h ticker statistics.

        Rate limit weight points:
        - All markets: 25

        Args:
            options: Optional query parameters
            model: Optional Pydantic model to validate response
            schema: Optional schema for DataFrame conversion

        Returns:
            Result containing 24h ticker statistics or error
        """
        if options and "market" in options:
            msg = "Market parameter is not allowed for 24h ticker statistics; yes, the API supports it, but I don't"
            raise ValueError(msg)

        postfix = create_postfix(options)
        raw_result = self.http.request("GET", f"/ticker/24h{postfix}", weight=25)
        return self._convert_raw_result(raw_result, "ticker_24h", model, schema)

    def report_book(
        self,
        market: str,
        options: AnyDict | None = None,
        *,
        model: type[T] | Any | None = None,
        schema: dict | None = None,
    ) -> Result[T, BitvavoError | httpx.HTTPError]:
        """Get MiCA-compliant order book report for a market.

        Returns the list of all bids and asks for the specified market, sorted by price.
        Includes data compliant with the European Markets in Crypto-Assets (MiCA) regulation.

        Endpoint: GET /v2/report/{market}/book
        Rate limit weight: 1

        Args:
            market: Market symbol (e.g., 'BTC-EUR')
            options: Optional query parameters:
                - depth (int): Number of bids and asks to return (default: 1000, max: 1000)
            model: Optional Pydantic model to validate response
            schema: Optional schema for DataFrame conversion

        Returns:
            Result containing MiCA-compliant order book report with enhanced structure:
            {
                "submissionTimestamp": "2025-05-02T14:23:11.123456Z",
                "assetCode": "4K6P57CMJ",
                "assetName": "Bitcoin",
                "bids": [
                    {
                        "side": "BUYI",
                        "price": "28500.12",
                        "quantity": "0.5",
                        "numOrders": 12
                    }
                ],
                "asks": [
                    {
                        "side": "SELL",
                        "price": "28510.00",
                        "quantity": "0.4",
                        "numOrders": 9
                    }
                ],
                "priceCurrency": "4K6P57CMJ",
                "priceNotation": "MONE",
                "quantityCurrency": "EUR",
                "quantityNotation": "CRYP",
                "venue": "VAVO",
                "tradingSystem": "VAVO",
                "publicationTimestamp": "2025-05-02T14:23:11.123456Z"
            }

        Note:
            This is a public endpoint but authenticating gives higher rate limits.
            The response structure is different from the regular order book endpoint
            and includes additional MiCA compliance fields.
        """
        # Validate depth parameter if provided
        if options and "depth" in options:
            depth = options["depth"]
            if not isinstance(depth, int) or not (1 <= depth <= MAX_BOOK_REPORT_DEPTH):
                msg = f"depth must be an integer between 1 and {MAX_BOOK_REPORT_DEPTH} (inclusive)"
                raise ValueError(msg)

        postfix = create_postfix(options)
        raw_result = self.http.request("GET", f"/report/{market}/book{postfix}", weight=1)
        return self._convert_raw_result(raw_result, "report_book", model, schema)

    def report_trades(
        self,
        market: str,
        options: AnyDict | None = None,
        *,
        model: type[T] | Any | None = None,
        schema: dict | None = None,
    ) -> Result[T, BitvavoError | httpx.HTTPError]:
        """Get MiCA-compliant trades report for a market.

        Returns trades from the specified market and time period made by all Bitvavo users.
        The returned trades are sorted by timestamp in descending order (latest to earliest).
        Includes data compliant with the European Markets in Crypto-Assets (MiCA) regulation.

        Endpoint: GET /v2/report/{market}/trades
        Rate limit weight: 5

        Args:
            market: Market symbol (e.g., 'BTC-EUR')
            options: Optional query parameters:
                - limit: int (1-1000, default 500) - Maximum number of trades to return
                - start: int - Unix timestamp in milliseconds to start from
                - end: int - Unix timestamp in milliseconds to end at (max 24h after start)
                - tradeIdFrom: str - Trade ID to start from
                - tradeIdTo: str - Trade ID to end at
            model: Optional Pydantic model to validate response
            schema: Optional schema for DataFrame conversion

        Returns:
            Result containing MiCA-compliant trades report with enhanced structure:
            - tradeId: Unique identifier of the trade
            - transactTimestamp: ISO 8601 timestamp when trade was added to database
            - assetCode: DTI code or symbol of the asset
            - assetName: Full name of the asset
            - price: Price of 1 unit of base currency in quote currency
            - missingPrice: Indicates if price is pending (PNDG) or not applicable (NOAP)
            - priceNotation: Price expression type (MONE)
            - priceCurrency: Currency in which price is expressed
            - quantity: Quantity of the asset
            - quantityCurrency: Currency in which quantity is expressed
            - quantityNotation: Quantity expression type (CRYP)
            - venue: Market Identifier Code of Bitvavo trading platform (VAVO)
            - publicationTimestamp: ISO 8601 timestamp when trade was published
            - publicationVenue: Market Identifier Code of publishing platform (VAVO)

        Example:
            >>> client.public.report_trades("BTC-EUR", {"limit": 100})
            Success([...])
        """
        postfix = create_postfix(options)
        raw_result = self.http.request("GET", f"/report/{market}/trades{postfix}", weight=5)
        return self._convert_raw_result(raw_result, "report_trades", model, schema)

    def _validate_trades_options(self, options: AnyDict) -> None:
        """Validate options for the trades endpoint according to Bitvavo API documentation.

        Args:
            options: Dictionary of query parameters to validate

        Raises:
            ValueError: If any parameter violates Bitvavo's constraints
        """
        if "limit" in options:
            limit = options["limit"]
            if not isinstance(limit, int) or limit < 1 or limit > MAX_TRADES_LIMIT:
                msg = f"limit must be an integer between 1 and {MAX_TRADES_LIMIT}"
                raise ValueError(msg)

        if "start" in options and "end" in options:
            start = options["start"]
            end = options["end"]
            # Check 24-hour constraint combined with type check
            if isinstance(start, int) and isinstance(end, int) and end - start > MAX_24_HOUR_MS:
                msg = "end timestamp cannot be more than 24 hours after start timestamp"
                raise ValueError(msg)

        if "end" in options:
            end = options["end"]
            if isinstance(end, int) and end > MAX_END_TIMESTAMP:
                msg = f"end timestamp cannot exceed {MAX_END_TIMESTAMP}"
                raise ValueError(msg)
