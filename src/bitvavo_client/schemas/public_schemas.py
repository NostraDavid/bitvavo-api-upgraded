"""Polars DataFrame schemas for public API endpoints."""

from __future__ import annotations

from typing import TYPE_CHECKING

import polars as pl

if TYPE_CHECKING:  # pragma: no cover
    from collections.abc import Mapping

# Time endpoint schema
TIME_SCHEMA: dict[str, type[pl.Int64]] = {
    "time": pl.Int64,
    "timeNs": pl.Int64,
}

# Markets endpoint schema
MARKETS_SCHEMA: dict[str, type[pl.Categorical | pl.Int8 | pl.Float64] | pl.List] = {
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
    "orderTypes": pl.List(pl.String),
}

# Assets endpoint schema
ASSETS_SCHEMA: dict[str, type[pl.Categorical | pl.String | pl.Int8 | pl.Int16 | pl.Float64] | pl.List] = {
    "symbol": pl.Categorical,
    "name": pl.String,
    "decimals": pl.Int8,
    "depositFee": pl.Int8,
    "depositConfirmations": pl.Int16,
    "depositStatus": pl.Categorical,
    "withdrawalFee": pl.Float64,
    "withdrawalMinAmount": pl.Float64,
    "withdrawalStatus": pl.Categorical,
    "networks": pl.List(pl.Categorical),
    "message": pl.String,
}

# Order book endpoint schema
BOOK_SCHEMA: dict[str, type[pl.Categorical | pl.Int32 | pl.Int64] | pl.List] = {
    "market": pl.Categorical,
    "nonce": pl.Int32,
    "bids": pl.List(pl.String),
    "asks": pl.List(pl.String),
    "timestamp": pl.Int64,
}
# Public trades endpoint schema
TRADES_SCHEMA: dict[str, type[pl.String | pl.Int64 | pl.Float64 | pl.Categorical]] = {
    "id": pl.String,
    "timestamp": pl.Int64,
    "amount": pl.Float64,
    "price": pl.Float64,
    "side": pl.Categorical,
}

# Candles endpoint schema
CANDLES_SCHEMA: dict[str, type[pl.Int64 | pl.Float64]] = {
    "timestamp": pl.Int64,
    "open": pl.Float64,
    "high": pl.Float64,
    "low": pl.Float64,
    "close": pl.Float64,
    "volume": pl.Float64,
}

# Ticker price endpoint schema
TICKER_PRICE_SCHEMA: dict[str, type[pl.Categorical | pl.Float64]] = {
    "market": pl.Categorical,
    "price": pl.Float64,
}

# Ticker book endpoint schema
TICKER_BOOK_SCHEMA: dict[str, type[pl.Categorical | pl.Float64]] = {
    "market": pl.Categorical,
    "bid": pl.Float64,
    "bidSize": pl.Float64,
    "ask": pl.Float64,
    "askSize": pl.Float64,
}

# Ticker 24h endpoint schema
TICKER_24H_SCHEMA: dict[str, type[pl.Categorical | pl.Int64 | pl.Float64]] = {
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
}

# Order book report endpoint schema (MiCA-compliant)
# Note: This uses the API field names (camelCase) since DataFrames are created
# directly from the raw API response, not from Pydantic model instances
# Note: bids and asks are complex nested structures that may need flattening for DataFrame use
REPORT_BOOK_SCHEMA: dict[str, type | object] = {
    "submissionTimestamp": pl.String,  # ISO 8601 timestamp
    "assetCode": pl.Categorical,
    "assetName": pl.String,
    "priceCurrency": pl.Categorical,
    "priceNotation": pl.Categorical,  # Always "MONE"
    "quantityCurrency": pl.Categorical,
    "quantityNotation": pl.Categorical,  # Always "CRYP"
    "venue": pl.Categorical,  # Always "VAVO"
    "tradingSystem": pl.Categorical,  # Always "VAVO"
    "publicationTimestamp": pl.String,  # ISO 8601 timestamp
    # Note: Nested structures for bids/asks - Polars will handle these as struct arrays
    "bids": pl.Object,  # Complex nested structure
    "asks": pl.Object,  # Complex nested structure
}

# Default schemas mapping for each endpoint
DEFAULT_SCHEMAS: dict[str, Mapping[str, object]] = {
    "time": TIME_SCHEMA,
    "markets": MARKETS_SCHEMA,
    "assets": ASSETS_SCHEMA,
    "book": BOOK_SCHEMA,
    "trades": TRADES_SCHEMA,
    "candles": CANDLES_SCHEMA,
    "ticker_price": TICKER_PRICE_SCHEMA,
    "ticker_book": TICKER_BOOK_SCHEMA,
    "ticker_24h": TICKER_24H_SCHEMA,
    "report_book": REPORT_BOOK_SCHEMA,
}

# Combined default schema for when you want all endpoints to use DataFrames
COMBINED_DEFAULT_SCHEMA: dict[str, Mapping[str, object]] = DEFAULT_SCHEMAS.copy()
COMBINED_DEFAULT_SCHEMA = DEFAULT_SCHEMAS.copy()
