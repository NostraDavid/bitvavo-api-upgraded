"""Schema definitions for bitvavo_client."""

from bitvavo_client.schemas import private_schemas, public_schemas
from bitvavo_client.schemas.private_schemas import (
    BALANCE_SCHEMA,
    DEPOSIT_HISTORY_SCHEMA,
    DEPOSIT_SCHEMA,
    FEES_SCHEMA,
    ORDER_SCHEMA,
    ORDERS_SCHEMA,
    WITHDRAWAL_SCHEMA,
    WITHDRAWALS_SCHEMA,
)
from bitvavo_client.schemas.public_schemas import (
    ASSETS_SCHEMA,
    BOOK_SCHEMA,
    CANDLES_SCHEMA,
    COMBINED_DEFAULT_SCHEMA,
    DEFAULT_SCHEMAS,
    MARKETS_SCHEMA,
    TICKER_24H_SCHEMA,
    TICKER_BOOK_SCHEMA,
    TICKER_PRICE_SCHEMA,
    TIME_SCHEMA,
    TRADES_SCHEMA,
)

__all__ = [
    "ASSETS_SCHEMA",
    "BALANCE_SCHEMA",
    "BOOK_SCHEMA",
    "CANDLES_SCHEMA",
    "COMBINED_DEFAULT_SCHEMA",
    "DEFAULT_SCHEMAS",
    "DEPOSIT_HISTORY_SCHEMA",
    "DEPOSIT_SCHEMA",
    "FEES_SCHEMA",
    "MARKETS_SCHEMA",
    "ORDERS_SCHEMA",
    "ORDER_SCHEMA",
    "TICKER_24H_SCHEMA",
    "TICKER_BOOK_SCHEMA",
    "TICKER_PRICE_SCHEMA",
    "TIME_SCHEMA",
    "TRADES_SCHEMA",
    "WITHDRAWALS_SCHEMA",
    "WITHDRAWAL_SCHEMA",
    "private_schemas",
    "public_schemas",
]
