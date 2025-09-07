"""Pydantic models for validating API responses."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, RootModel, field_validator


class ServerTime(BaseModel):
    """Example Pydantic model for server time response."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        str_strip_whitespace=True,
    )

    time: int = Field(..., description="Server timestamp in milliseconds", gt=0)
    time_ns: int = Field(..., alias="timeNs", description="Server timestamp in nanoseconds", gt=0)


class Market(BaseModel):
    """Pydantic model for a single market entry from the /markets endpoint."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        populate_by_name=True,  # Allows using both field names and aliases
        str_strip_whitespace=True,
        validate_assignment=True,  # Re-validate on assignment (useful for frozen=True)
    )

    market: str = Field(..., description="Market symbol (e.g., 'BTC-EUR')", min_length=1)
    status: str = Field(..., description="Market status (e.g., 'trading', 'halted')")
    base: str = Field(..., description="Base asset symbol", min_length=1)
    quote: str = Field(..., description="Quote asset symbol", min_length=1)
    price_precision: int = Field(..., alias="pricePrecision", description="Price precision", ge=0)
    min_order_in_base_asset: str = Field(
        ...,
        alias="minOrderInBaseAsset",
        description="Minimum order size in base asset",
    )
    min_order_in_quote_asset: str = Field(
        ...,
        alias="minOrderInQuoteAsset",
        description="Minimum order size in quote asset",
    )
    max_order_in_base_asset: str = Field(
        ...,
        alias="maxOrderInBaseAsset",
        description="Maximum order size in base asset",
    )
    max_order_in_quote_asset: str = Field(
        ...,
        alias="maxOrderInQuoteAsset",
        description="Maximum order size in quote asset",
    )
    quantity_decimals: int = Field(..., alias="quantityDecimals", description="Quantity decimal places", ge=0)
    notional_decimals: int = Field(..., alias="notionalDecimals", description="Notional decimal places", ge=0)
    tick_size: str | None = Field(default=None, alias="tickSize", description="Minimum price increment")
    max_open_orders: int = Field(..., alias="maxOpenOrders", description="Maximum open orders", ge=0)
    fee_category: str = Field(..., alias="feeCategory", description="Fee category")
    order_types: list[str] = Field(..., alias="orderTypes", description="Supported order types", min_length=1)

    @field_validator("order_types")
    @classmethod
    def validate_order_types(cls, v: list[str]) -> list[str]:
        """Ensure all order types are non-empty strings."""
        if not all(isinstance(order_type, str) and order_type.strip() for order_type in v):
            msg = "All order types must be non-empty strings"
            raise ValueError(msg)
        return v


class Markets(RootModel[list[Market]]):
    """Wrapper model representing a list of Market objects (API /markets response)."""

    model_config = ConfigDict(
        frozen=True,
        populate_by_name=True,
        validate_assignment=True,
    )

    def __len__(self) -> int:
        """Return the number of markets."""
        return len(self.root)

    def __getitem__(self, index: int) -> Market:
        """Allow indexing into the markets list."""
        return self.root[index]

    @property
    def markets(self) -> list[Market]:
        """Get the underlying list of markets."""
        return self.root

    def get_market(self, symbol: str) -> Market | None:
        """Get a market by symbol.

        Args:
            symbol: Market symbol (e.g., 'BTC-EUR')

        Returns:
            Market model if found, None otherwise
        """
        for market in self.root:
            if market.market == symbol:
                return market
        return None

    def filter_by_status(self, status: str) -> list[Market]:
        """Filter markets by status.

        Args:
            status: Status to filter by (e.g., 'trading')

        Returns:
            List of markets with the specified status
        """
        return [market for market in self.root if market.status == status]

    def get_base_assets(self) -> set[str]:
        """Get all unique base assets.

        Returns:
            Set of base asset symbols
        """
        return {market.base for market in self.root}

    def get_quote_assets(self) -> set[str]:
        """Get all unique quote assets.

        Returns:
            Set of quote asset symbols
        """
        return {market.quote for market in self.root}


class Asset(BaseModel):
    """Pydantic model for a single asset/currency entry (from the /assets endpoint)."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        str_strip_whitespace=True,
        validate_assignment=True,
    )

    symbol: str = Field(
        ...,
        description="Asset symbol (e.g. 'BTC')",
        min_length=1,
    )
    name: str = Field(
        ...,
        description="Human readable name",
    )
    decimals: int = Field(
        ...,
        description="Decimal places supported",
        ge=0,
    )
    deposit_fee: str = Field(
        ...,
        alias="depositFee",
        description="Deposit fee as string (e.g. '0')",
    )
    deposit_confirmations: int = Field(
        ...,
        alias="depositConfirmations",
        description="Required confirmations for deposit",
        ge=0,
    )
    deposit_status: str = Field(
        ...,
        alias="depositStatus",
        description="Deposit status (e.g. 'OK', 'MAINTENANCE', 'DELISTED')",
    )
    withdrawal_fee: str = Field(..., alias="withdrawalFee", description="Withdrawal fee as string")
    withdrawal_min_amount: str = Field(
        ...,
        alias="withdrawalMinAmount",
        description="Minimum withdrawal amount as string",
    )
    withdrawal_status: str = Field(
        ...,
        alias="withdrawalStatus",
        description="Withdrawal status (e.g. 'OK', 'MAINTENANCE', 'DELISTED')",
    )
    networks: list[str] = Field(
        ...,
        description="List of supported networks (e.g. ['Mainnet', 'ETH'])",
    )
    message: str = Field(
        ...,
        description="Optional message from the API",
        min_length=0,
    )

    @field_validator("symbol", "name")
    @classmethod
    def non_empty_str(cls, v: str) -> str:
        if not v or not v.strip():
            msg = "must be a non-empty string"
            raise ValueError(msg)
        return v

    @field_validator("networks")
    @classmethod
    def validate_networks(cls, v: list[str]) -> list[str]:
        """Ensure all networks are non-empty strings."""
        if not all(isinstance(network, str) and network.strip() for network in v):
            msg = "All networks must be non-empty strings"
            raise ValueError(msg)
        return v

    @field_validator("deposit_fee", "withdrawal_fee", "withdrawal_min_amount", "deposit_confirmations", mode="before")
    @classmethod
    def normalize_fee_strings(cls, v: Any) -> Any:
        # keep fees/min-amounts as strings as the API returns them,
        # but ensure they are not None. Leave validation of numeric format
        # to higher-level code/tests if needed.
        if v is None:
            msg = "fee/min-amount fields must be provided"
            raise ValueError(msg)
        return v


class Assets(RootModel[list[Asset]]):
    """Wrapper model representing a list of Asset objects (API /assets response)."""

    model_config = ConfigDict(
        frozen=True,
        validate_assignment=True,
    )

    def __len__(self) -> int:
        return len(self.root)

    def __getitem__(self, index: int) -> Asset:
        return self.root[index]

    @property
    def assets(self) -> list[Asset]:
        return self.root

    def get_asset(self, symbol: str) -> Asset | None:
        """Return the Asset with matching symbol or None."""
        for asset in self.root:
            if asset.symbol == symbol:
                return asset
        return None

    def filter_by_deposit_status(self, status: str) -> list[Asset]:
        """Return assets filtered by depositStatus."""
        return [a for a in self.root if a.deposit_status == status]

    def filter_by_withdrawal_status(self, status: str) -> list[Asset]:
        """Return assets filtered by withdrawalStatus."""
        return [a for a in self.root if a.withdrawal_status == status]


class PriceLevel(RootModel[list[str]]):
    """A single price level represented as a list (e.g. [price, amount, ...]).

    The Bitvavo API returns bids/asks as nested lists. We normalize each inner
    list to a list of stripped strings and require at least price and amount.
    """

    model_config = ConfigDict(frozen=True, str_strip_whitespace=True)

    @field_validator("root", mode="before")
    @classmethod
    def _ensure_list_of_str(cls, v: Any) -> list[str]:
        # Accept tuples/lists and also already-parsed PriceLevel instances.
        if isinstance(v, PriceLevel):
            return v.root
        try:
            items = list(v)
        except TypeError as exc:
            msg = "price level must be an iterable"
            raise ValueError(msg) from exc
        if len(items) < 2:  # noqa: PLR2004
            msg = "price level must contain at least price and amount"
            raise ValueError(msg)
        # Convert all items to strings and strip whitespace
        return [("" if it is None else str(it)).strip() for it in items]

    def price(self) -> str:
        return self.root[0]

    def amount(self) -> str:
        return self.root[1]

    def extras(self) -> list[str]:
        return self.root[2:]


class OrderBook(BaseModel):
    """Model for the order book snapshot returned by the API.

    Example input:
    {'market': 'BTC-EUR', 'nonce': 91722611, 'bids': [[...], ...], 'asks': [[...], ...], 'timestamp': 1756...}
    """

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        str_strip_whitespace=True,
        populate_by_name=True,
        validate_assignment=True,
    )

    market: str = Field(..., description="Market symbol (e.g. 'BTC-EUR')", min_length=1)
    nonce: int = Field(..., description="Snapshot nonce", ge=0)
    bids: list[PriceLevel] = Field(..., description="List of bid price levels (each is a list)")
    asks: list[PriceLevel] = Field(..., description="List of ask price levels (each is a list)")
    timestamp: int = Field(..., description="Server timestamp (likely in nanoseconds)", ge=0)

    @field_validator("bids", "asks", mode="before")
    @classmethod
    def _normalize_levels(cls, v: Any) -> list[PriceLevel]:
        # Ensure iterable -> list and let PriceLevel parse each inner entry
        try:
            return list(v)
        except TypeError as exc:
            msg = "bids/asks must be iterable of price levels"
            raise ValueError(msg) from exc

    def best_bid(self) -> PriceLevel | None:
        return self.bids[0] if self.bids else None

    def best_ask(self) -> PriceLevel | None:
        return self.asks[0] if self.asks else None


class TickerPrice(BaseModel):
    """Model representing a single market ticker price entry."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        str_strip_whitespace=True,
        validate_assignment=True,
    )

    market: str = Field(..., description="Market symbol (e.g. 'BTC-EUR')", min_length=1)
    price: str = Field(..., description="Price as returned by the API (string)")

    @field_validator("market", "price")
    @classmethod
    def _non_empty_str(cls, v: str) -> str:
        if not isinstance(v, str) or not v.strip():
            msg = "must be a non-empty string"
            raise ValueError(msg)
        return v

    @field_validator("price")
    @classmethod
    def _validate_price_is_numeric(cls, v: str) -> str:
        # Keep the original string value but ensure it is a numeric representation
        try:
            d = Decimal(v)
        except Exception as exc:
            msg = "price must be a numeric string"
            raise ValueError(msg) from exc
        if d < 0:
            msg = "price must be non-negative"
            raise ValueError(msg)
        return v


class TickerPrices(RootModel[list[TickerPrice]]):
    """Wrapper for a list of TickerPrice items (e.g. API tickers response)."""

    model_config = ConfigDict(
        frozen=True,
        validate_assignment=True,
    )

    def __len__(self) -> int:
        return len(self.root)

    def __getitem__(self, index: int) -> TickerPrice:
        return self.root[index]

    @property
    def prices(self) -> list[TickerPrice]:
        return self.root

    def get_price(self, market: str) -> TickerPrice | None:
        """Return the TickerPrice for the given market or None if not found."""
        for tp in self.root:
            if tp.market == market:
                return tp
        return None

    def to_serializable(self) -> list[dict]:
        """Return a list of dicts suitable for JSON serialization."""
        return [tp.model_dump() for tp in self.root]


class TickerBook(BaseModel):
    """Model representing best bid/ask for a single market (API /ticker/book)."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        str_strip_whitespace=True,
        validate_assignment=True,
    )

    market: str = Field(..., description="Market symbol (e.g. 'BTC-EUR')", min_length=1)
    bid: str | None = Field(..., description="Best bid price as string")
    bid_size: str | None = Field(..., alias="bidSize", description="Size available at best bid as string")
    ask: str | None = Field(..., description="Best ask price as string")
    ask_size: str | None = Field(..., alias="askSize", description="Size available at best ask as string")

    @field_validator("market")
    @classmethod
    def _non_empty_str(cls, v: str) -> str:
        if not isinstance(v, str) or not v.strip():
            msg = "must be a non-empty string"
            raise ValueError(msg)
        return v

    @field_validator("bid", "ask", "bid_size", "ask_size")
    @classmethod
    def _validate_numeric_str(cls, v: str | None) -> str | None:
        if v is None:
            return v
        try:
            d = Decimal(v)
        except Exception as exc:
            msg = "must be a numeric string"
            raise ValueError(msg) from exc
        if d < 0:
            msg = "must be non-negative"
            raise ValueError(msg)
        return v


class TickerBooks(RootModel[list[TickerBook]]):
    """Wrapper for a list of TickerBook items (e.g. API /ticker/book response).

    Handles both list responses (when no market is specified) and single object
    responses (when a specific market is requested via query parameter).
    """

    model_config = ConfigDict(
        frozen=True,
        validate_assignment=True,
    )

    @field_validator("root", mode="before")
    @classmethod
    def _normalize_input(cls, v: Any) -> list[dict]:
        """Convert single TickerBook dict to list for consistent handling."""
        if isinstance(v, dict):
            # Single ticker book object - wrap in list
            return [v]
        if isinstance(v, list):
            # Already a list of ticker books
            return v
        msg = "Input must be a dict or list of dicts"
        raise TypeError(msg)

    def __len__(self) -> int:
        return len(self.root)

    def __getitem__(self, index: int) -> TickerBook:
        return self.root[index]

    @property
    def books(self) -> list[TickerBook]:
        return self.root

    def get_book(self, market: str) -> TickerBook | None:
        """Return the TickerBook for the given market or None if not found."""
        for tb in self.root:
            if tb.market == market:
                return tb
        return None

    def to_serializable(self) -> list[dict]:
        """Return a list of dicts suitable for JSON serialization."""
        return [tb.model_dump() for tb in self.root]


class Trade(BaseModel):
    """Public trade entry (as returned by Bitvavo /trades)."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        str_strip_whitespace=True,
        validate_assignment=True,
    )

    id: str = Field(..., description="Trade identifier", min_length=1)
    timestamp: int = Field(..., description="Trade timestamp in milliseconds", ge=0)
    amount: str = Field(..., description="Traded amount (base asset) as string")
    price: str = Field(..., description="Trade price as string")
    side: str = Field(..., description="Trade side ('buy' or 'sell')")

    @field_validator("id")
    @classmethod
    def _non_empty_id(cls, v: str) -> str:
        if not isinstance(v, str) or not v.strip():
            msg = "must be a non-empty string"
            raise ValueError(msg)
        return v

    @field_validator("amount", "price")
    @classmethod
    def _numeric_str(cls, v: str) -> str:
        try:
            d = Decimal(v)
        except Exception as exc:
            msg = "must be a numeric string"
            raise ValueError(msg) from exc
        if d < 0:
            msg = "must be non-negative"
            raise ValueError(msg)
        return v

    @field_validator("side")
    @classmethod
    def _validate_side(cls, v: str) -> str:
        if not isinstance(v, str) or not v.strip():
            msg = "must be a non-empty string"
            raise ValueError(msg)
        side = v.strip().lower()
        if side not in {"buy", "sell"}:
            msg = "side must be 'buy' or 'sell'"
            raise ValueError(msg)
        return side


class Trades(RootModel[list[Trade]]):
    """Wrapper for a list of Trade items."""

    model_config = ConfigDict(
        frozen=True,
        validate_assignment=True,
    )

    def __len__(self) -> int:
        return len(self.root)

    def __getitem__(self, index: int) -> Trade:
        return self.root[index]

    @property
    def trades(self) -> list[Trade]:
        return self.root

    def filter_by_side(self, side: str) -> list[Trade]:
        s = side.strip().lower()
        if s not in {"buy", "sell"}:
            return []
        return [t for t in self.root if t.side == s]

    def buys(self) -> list[Trade]:
        return self.filter_by_side("buy")

    def sells(self) -> list[Trade]:
        return self.filter_by_side("sell")

    def latest(self) -> Trade | None:
        return max(self.root, key=lambda t: t.timestamp) if self.root else None

    def to_serializable(self) -> list[dict]:
        return [t.model_dump() for t in self.root]


class Candle(BaseModel):
    """Single OHLCV candle: [timestamp, open, high, low, close, volume]."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        str_strip_whitespace=True,
        validate_assignment=True,
    )

    timestamp: int = Field(..., description="Candle open time in milliseconds", ge=0)
    open: str = Field(..., description="Open price as string")
    high: str = Field(..., description="High price as string")
    low: str = Field(..., description="Low price as string")
    close: str = Field(..., description="Close price as string")
    volume: str = Field(..., description="Volume as string")

    @field_validator("open", "high", "low", "close", "volume")
    @classmethod
    def _validate_numeric_str(cls, v: str) -> str:
        try:
            d = Decimal(v)
        except Exception as exc:
            msg = "must be a numeric string"
            raise ValueError(msg) from exc
        if d < 0:
            msg = "must be non-negative"
            raise ValueError(msg)
        return v

    @classmethod
    def from_ohlcv(cls, ohlcv: list | tuple) -> Candle:
        """Create Candle from a 6-item sequence."""
        if not isinstance(ohlcv, (list, tuple)) or len(ohlcv) < 6:  # noqa: PLR2004
            msg = "ohlcv must be a sequence [timestamp, open, high, low, close, volume]"
            raise ValueError(msg)
        timestamp, open, high, low, close, volume = ohlcv[:6]  # noqa: A001
        return cls(
            timestamp=int(timestamp), open=str(open), high=str(high), low=str(low), close=str(close), volume=str(volume)
        )

    def to_ohlcv(self) -> list:
        """Return as [timestamp, open, high, low, close, volume]."""
        return [self.timestamp, self.open, self.high, self.low, self.close, self.volume]


class Candles(RootModel[list[Candle]]):
    """Wrapper for list of Candle items (API /candles response)."""

    model_config = ConfigDict(
        frozen=True,
        validate_assignment=True,
    )

    @field_validator("root", mode="before")
    @classmethod
    def _normalize_ohlcv(cls, v: Any) -> Any:
        # Accept list of lists/tuples and convert each to Candle
        try:
            items = list(v)
        except TypeError:
            return v
        out: list[Candle | dict] = []
        for item in items:
            if isinstance(item, Candle):
                out.append(item)
            elif isinstance(item, (list, tuple)):
                timestamp, open, high, low, close, volume = (item + [None] * 6)[:6]  # noqa: A001
                if None in (timestamp, open, high, low, close, volume):
                    msg = "each candle must have 6 elements"
                    raise ValueError(msg)
                out.append(
                    {
                        "timestamp": int(timestamp),
                        "open": str(open),
                        "high": str(high),
                        "low": str(low),
                        "close": str(close),
                        "volume": str(volume),
                    }
                )
            else:
                out.append(item)
        return out

    def __len__(self) -> int:
        return len(self.root)

    def __getitem__(self, index: int) -> Candle:
        return self.root[index]

    @property
    def candles(self) -> list[Candle]:
        return self.root

    def to_ohlcv(self) -> list[list]:
        """Return list of [timestamp, open, high, low, close, volume]."""
        return [c.to_ohlcv() for c in self.root]

    def earliest(self) -> Candle | None:
        return min(self.root, key=lambda c: c.timestamp) if self.root else None

    def latest(self) -> Candle | None:
        return max(self.root, key=lambda c: c.timestamp) if self.root else None


class Ticker24h(BaseModel):
    """24h ticker stats for a single market (mirrors Bitvavo /ticker/24h item)."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        str_strip_whitespace=True,
        validate_assignment=True,
        populate_by_name=True,
    )

    market: str = Field(..., description="Market symbol (e.g. 'BTC-EUR')", min_length=1)
    start_timestamp: int = Field(..., alias="startTimestamp", description="Window start timestamp (ms)", ge=0)
    timestamp: int = Field(..., description="Current server timestamp (ms)", ge=0)
    open: str | None = Field(..., description="Open price as string")
    open_timestamp: int | None = Field(..., alias="openTimestamp", description="Open price timestamp (ms)", ge=0)
    high: str | None = Field(..., description="High price as string")
    low: str | None = Field(..., description="Low price as string")
    last: str | None = Field(..., description="Last trade price as string")
    close_timestamp: int | None = Field(..., alias="closeTimestamp", description="Close price timestamp (ms)", ge=0)
    bid: str | None = Field(..., description="Best bid price as string")
    bid_size: str | None = Field(..., alias="bidSize", description="Size available at best bid as string")
    ask: str | None = Field(..., description="Best ask price as string")
    ask_size: str | None = Field(..., alias="askSize", description="Size available at best ask as string")
    volume: str | None = Field(..., description="Base asset volume in the last 24h as string")
    volume_quote: str | None = Field(
        ...,
        alias="volumeQuote",
        description="Quote asset volume in the last 24h as string",
    )

    @field_validator("market")
    @classmethod
    def _non_empty_str(cls, v: str) -> str:
        if not isinstance(v, str) or not v.strip():
            msg = "must be a non-empty string"
            raise ValueError(msg)
        return v


class Ticker24hs(RootModel[list[Ticker24h]]):
    """Wrapper for a list of Ticker24h items (API /ticker/24h response)."""

    model_config = ConfigDict(
        frozen=True,
        validate_assignment=True,
    )

    def __len__(self) -> int:
        return len(self.root)

    def __getitem__(self, index: int) -> Ticker24h:
        return self.root[index]

    @property
    def tickers(self) -> list[Ticker24h]:
        return self.root

    def get_ticker(self, market: str) -> Ticker24h | None:
        """Return the Ticker24h for the given market or None if not found."""
        for t in self.root:
            if t.market == market:
                return t
        return None

    def to_serializable(self) -> list[dict]:
        """Return a list of dicts suitable for JSON serialization."""
        return [t.model_dump(by_alias=True) for t in self.root]


class OrderBookReportEntry(BaseModel):
    """Individual order entry in a MiCA-compliant order book report."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        str_strip_whitespace=True,
        validate_assignment=True,
        # Enhanced error reporting configuration
        title="OrderBookReportEntry",
        validate_default=True,
        loc_by_alias=False,
    )

    side: str = Field(..., description="Order side: 'BUYI' for bids, 'SELL' for asks")
    price: str = Field(..., description="Price value as decimal string")
    quantity: str = Field(..., alias="size", description="Quantity value as decimal string")
    num_orders: int = Field(..., alias="numOrders", description="Number of orders at this price level", ge=1)

    @field_validator("side")
    @classmethod
    def _validate_side(cls, v: str) -> str:
        if not isinstance(v, str) or not v.strip():
            msg = f"Order side must be a non-empty string, got {type(v).__name__}: {v!r}"
            raise ValueError(msg)
        side = v.strip().upper()
        if side not in {"BUYI", "SELL"}:
            msg = (
                f"Order side must be 'BUY' or 'SELL', got: {side!r}. "
                "Valid values: BUYI (buy orders), SELL (sell orders)"
            )
            raise ValueError(msg)
        return side

    @field_validator("price", "quantity")
    @classmethod
    def _validate_numeric_str(cls, v: str) -> str:
        if not isinstance(v, str) or not v.strip():
            msg = f"Numeric field must be a non-empty string, got {type(v).__name__}: {v!r}"
            raise ValueError(msg)
        try:
            d = Decimal(v)
        except (ValueError, TypeError) as exc:
            msg = f"Numeric field must be a valid decimal string (e.g., '123.45'), got: {v!r}. Error: {exc}"
            raise ValueError(msg) from exc
        if d < 0:
            msg = f"Numeric field must be non-negative, got: {v!r} (value: {d})"
            raise ValueError(msg)
        return v


class OrderBookReport(BaseModel):
    """MiCA-compliant order book report model (API /report/{market}/book response)."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        str_strip_whitespace=True,
        validate_assignment=True,
        populate_by_name=True,
        # Enhanced error reporting configuration
        title="OrderBookReport",
        validate_default=True,
        loc_by_alias=False,
    )

    submission_timestamp: str = Field(
        ...,
        alias="submissionTimestamp",
        description="Timestamp when order book is submitted to database (ISO 8601)",
    )
    asset_code: str = Field(..., alias="assetCode", description="DTI code or symbol of the asset")
    asset_name: str = Field(..., alias="assetName", description="Full name of the asset")
    bids: list[OrderBookReportEntry] = Field(..., description="List of buy orders")
    asks: list[OrderBookReportEntry] = Field(..., description="List of sell orders")
    price_currency: str = Field(..., alias="priceCurrency", description="DTI code of price currency")
    price_notation: str = Field(..., alias="priceNotation", description="Price notation (always 'MONE')")
    quantity_currency: str = Field(..., alias="quantityCurrency", description="Currency for quantity expression")
    quantity_notation: str = Field(..., alias="quantityNotation", description="Quantity notation (always 'CRYP')")
    venue: str = Field(..., description="Market Identifier Code (always 'VAVO')")
    trading_system: str = Field(..., alias="tradingSystem", description="Trading system identifier (always 'VAVO')")
    publication_timestamp: str = Field(
        ...,
        alias="publicationTimestamp",
        description="Timestamp when book snapshot is added to database (ISO 8601)",
    )

    @field_validator("submission_timestamp", "publication_timestamp")
    @classmethod
    def _validate_timestamp(cls, v: str) -> str:
        if not isinstance(v, str):
            msg = "timestamp must be a string"
            raise TypeError(msg)

        # Allow empty timestamps
        if not v.strip():
            return v

        # Basic format validation - should be ISO 8601 format
        if not v.endswith("Z") or "T" not in v:
            msg = "timestamp must be in ISO 8601 format (e.g., '2025-05-02T14:23:11.123456Z') or empty"
            raise ValueError(msg)
        return v

    @field_validator("asset_code", "asset_name", "price_currency", "quantity_currency", "venue", "trading_system")
    @classmethod
    def _non_empty_str(cls, v: str) -> str:
        if not isinstance(v, str) or not v.strip():
            msg = "must be a non-empty string"
            raise ValueError(msg)
        return v

    @field_validator("price_notation")
    @classmethod
    def _validate_price_notation(cls, v: str) -> str:
        if not isinstance(v, str) or v.strip() != "MONE":
            msg = "price_notation must be 'MONE'"
            raise ValueError(msg)
        return v

    @field_validator("quantity_notation")
    @classmethod
    def _validate_quantity_notation(cls, v: str) -> str:
        if not isinstance(v, str) or v.strip() != "CRYP":
            msg = "quantity_notation must be 'CRYP'"
            raise ValueError(msg)
        return v

    @field_validator("venue", "trading_system")
    @classmethod
    def _validate_venue_system(cls, v: str) -> str:
        if not isinstance(v, str) or v.strip() not in ["VAVO", "CLOB"]:
            msg = "venue and trading_system must be 'VAVO' or 'CLOB'"
            raise ValueError(msg)
        return v

    def best_bid(self) -> OrderBookReportEntry | None:
        """Get the best (highest) bid."""
        if not self.bids:
            return None
        return max(self.bids, key=lambda bid: Decimal(bid.price))

    def best_ask(self) -> OrderBookReportEntry | None:
        """Get the best (lowest) ask."""
        if not self.asks:
            return None
        return min(self.asks, key=lambda ask: Decimal(ask.price))

    def spread(self) -> Decimal | None:
        """Calculate the spread between best bid and ask."""
        best_bid = self.best_bid()
        best_ask = self.best_ask()
        if best_bid and best_ask:
            return Decimal(best_ask.price) - Decimal(best_bid.price)
        return None


class TradeReportEntry(BaseModel):
    """Individual trade entry in a MiCA-compliant trades report."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        str_strip_whitespace=True,
        validate_assignment=True,
        populate_by_name=True,
    )

    trade_id: str = Field(
        ...,
        alias="tradeId",
        description="The unique identifier of the trade",
        min_length=1,
    )
    transact_timestamp: str = Field(
        ...,
        alias="transactTimestamp",
        description="The timestamp when the trade is added to the database (ISO 8601 format)",
    )
    asset_code: str = Field(
        ...,
        alias="assetCode",
        description="The DTI code or a symbol of the asset",
        min_length=1,
    )
    asset_name: str = Field(
        ...,
        alias="assetName",
        description="The full name of the asset",
        min_length=1,
    )
    price: str = Field(
        ...,
        description="The price of 1 unit of base currency in the amount of quote currency at the time of the trade",
    )
    missing_price: str = Field(
        "",
        alias="missingPrice",
        description="Indicates if the price is pending (PNDG) or not applicable (NOAP). May be empty.",
    )
    price_notation: str = Field(
        ...,
        alias="priceNotation",
        description="Indicates whether the price is expressed as a monetary value, percentage, yield, or basis points",
    )
    price_currency: str = Field(
        ...,
        alias="priceCurrency",
        description="The currency in which the price is expressed",
        min_length=1,
    )
    quantity: str = Field(
        ...,
        description="The quantity of the asset (decimal string)",
    )
    quantity_currency: str = Field(
        ...,
        alias="quantityCurrency",
        description="The currency in which the quantity of the crypto asset is expressed",
        min_length=1,
    )
    quantity_notation: str = Field(
        ...,
        alias="quantityNotation",
        description="Indicates whether the quantity is expressed as units, nominal value, monetary value, or crypto",
    )
    venue: str = Field(
        ...,
        description="The Market Identifier Code of the Bitvavo trading platform",
        min_length=1,
    )
    publication_timestamp: str = Field(
        ...,
        alias="publicationTimestamp",
        description="The timestamp when the trade is added to the database (ISO 8601 format)",
    )
    publication_venue: str = Field(
        ...,
        alias="publicationVenue",
        description="The Market Identifier Code of the trading platform that publishes the transaction",
        min_length=1,
    )

    @field_validator(
        "trade_id", "asset_code", "asset_name", "price_currency", "quantity_currency", "venue", "publication_venue"
    )
    @classmethod
    def _non_empty_str(cls, v: str) -> str:
        if not isinstance(v, str) or not v.strip():
            msg = "must be a non-empty string"
            raise ValueError(msg)
        return v

    @field_validator("price", "quantity")
    @classmethod
    def _numeric_str(cls, v: str) -> str:
        try:
            d = Decimal(v)
        except Exception as exc:
            msg = "must be a numeric string"
            raise ValueError(msg) from exc
        if d < 0:
            msg = "must be non-negative"
            raise ValueError(msg)
        return v

    @field_validator("transact_timestamp", "publication_timestamp")
    @classmethod
    def _iso_timestamp(cls, v: str) -> str:
        if not isinstance(v, str):
            msg = "timestamp must be a string"
            raise TypeError(msg)

        # Basic format validation - should be ISO 8601 format
        if not v.endswith("Z") or "T" not in v:
            msg = "timestamp must be in ISO 8601 format (e.g., '2024-05-02T14:43:11.123456Z')"
            raise ValueError(msg)
        return v

    @field_validator("price_notation")
    @classmethod
    def _validate_price_notation(cls, v: str) -> str:
        if not isinstance(v, str) or v.strip() != "MONE":
            msg = "price_notation must be 'MONE'"
            raise ValueError(msg)
        return v

    @field_validator("quantity_notation")
    @classmethod
    def _validate_quantity_notation(cls, v: str) -> str:
        if not isinstance(v, str) or v.strip() != "CRYP":
            msg = "quantity_notation must be 'CRYP'"
            raise ValueError(msg)
        return v

    @field_validator("venue", "publication_venue")
    @classmethod
    def _validate_venue(cls, v: str) -> str:
        if not isinstance(v, str) or v.strip() != "VAVO":
            msg = "venue must be 'VAVO'"
            raise ValueError(msg)
        return v

    @field_validator("missing_price")
    @classmethod
    def _validate_missing_price(cls, v: str) -> str:
        if not isinstance(v, str):
            msg = "missing_price must be a string"
            raise TypeError(msg)

        # Allow empty string or specific values
        if v and v.strip() not in ["PNDG", "NOAP"]:
            msg = "missing_price must be empty, 'PNDG', or 'NOAP'"
            raise ValueError(msg)
        return v


class TradesReport(RootModel[list[TradeReportEntry]]):
    """MiCA-compliant trades report model (API /report/{market}/trades response)."""

    model_config = ConfigDict(
        frozen=True,
        validate_assignment=True,
    )

    def __len__(self) -> int:
        return len(self.root)

    def __iter__(self) -> Any:
        return iter(self.root)

    def __getitem__(self, item: int) -> TradeReportEntry:
        return self.root[item]
