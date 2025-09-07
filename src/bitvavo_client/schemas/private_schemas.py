"""Polars DataFrame schemas for private API endpoints."""

from __future__ import annotations

from typing import TYPE_CHECKING

import polars as pl

if TYPE_CHECKING:  # pragma: no cover
    from collections.abc import Mapping


# Balance endpoint schema
BALANCE_SCHEMA: dict[str, type[pl.Categorical | pl.Float64]] = {
    "symbol": pl.Categorical,
    "available": pl.Float64,
    "inOrder": pl.Float64,
}

# Order endpoint schema (for individual orders)
ORDER_SCHEMA: dict[str, type[pl.String | pl.Int64 | pl.Boolean | pl.Categorical | pl.Float64] | pl.List] = {
    "orderId": pl.String,
    "market": pl.Categorical,
    "created": pl.Int64,
    "updated": pl.Int64,
    "status": pl.Categorical,
    "side": pl.Categorical,
    "orderType": pl.Categorical,
    "clientOrderId": pl.String,
    "selfTradePrevention": pl.Categorical,
    "visible": pl.Boolean,
    "onHold": pl.Float64,
    "onHoldCurrency": pl.Categorical,
    "fills": pl.List(
        pl.Struct(
            {
                "id": pl.String,
                "timestamp": pl.Int64,
                "amount": pl.Float64,
                "price": pl.Float64,
                "taker": pl.Boolean,
                "fee": pl.String,
                "feeCurrency": pl.Categorical,
                "settled": pl.Boolean,
            }
        )
    ),
    "feePaid": pl.Float64,
    "feeCurrency": pl.Categorical,
    "operatorId": pl.Int64,
    "price": pl.Float64,
    "timeInForce": pl.Categorical,
    "postOnly": pl.Boolean,
    "amount": pl.Float64,
    "amountRemaining": pl.Float64,
    "filledAmount": pl.Float64,
    "filledAmountQuote": pl.Float64,
    "createdNs": pl.Int64,
    "updatedNs": pl.Int64,
}

# Orders endpoint schema (for lists of orders)
ORDERS_SCHEMA = ORDER_SCHEMA.copy()

# Cancel order response schema
CANCEL_ORDER_SCHEMA: dict[str, type[pl.String | pl.Int64]] = {
    "orderId": pl.String,
    "clientOrderId": pl.String,
    "operatorId": pl.Int64,
}

# Trade endpoint schema (for private trades)
TRADE_SCHEMA: dict[str, type[pl.String | pl.Int64 | pl.Categorical | pl.Boolean]] = {
    "id": pl.String,
    "timestamp": pl.Int64,
    "amount": pl.String,
    "price": pl.String,
    "side": pl.Categorical,
    "market": pl.Categorical,
    "fee": pl.String,
    "feeCurrency": pl.Categorical,
    "settled": pl.Boolean,
}

# Trades endpoint schema (for lists of trades)
TRADES_SCHEMA = TRADE_SCHEMA.copy()

# Fees endpoint schema
FEES_SCHEMA: dict[str, type[pl.Int32 | pl.String]] = {
    "tier": pl.Int32,
    "volume": pl.String,
    "maker": pl.String,
    "taker": pl.String,
}

# Deposit endpoint schema
DEPOSIT_SCHEMA: dict[str, type[pl.String | pl.Int64 | pl.Categorical]] = {
    "timestamp": pl.Int64,
    "symbol": pl.Categorical,
    "amount": pl.String,
    "fee": pl.String,
    "status": pl.Categorical,
    "address": pl.String,
    "paymentId": pl.String,
    "txId": pl.String,
}

# Deposits endpoint schema (for lists of deposits)
DEPOSIT_HISTORY_SCHEMA = DEPOSIT_SCHEMA.copy()

# Withdrawal endpoint schema (for withdrawal history)
WITHDRAWAL_SCHEMA: dict[str, type[pl.String | pl.Int64 | pl.Categorical]] = {
    "timestamp": pl.Int64,
    "symbol": pl.Categorical,
    "amount": pl.String,
    "fee": pl.String,
    "status": pl.Categorical,
    "address": pl.String,
    "txId": pl.String,
}

# Withdraw response schema (for withdraw operation response)
WITHDRAW_RESPONSE_SCHEMA: dict[str, type[pl.String | pl.Boolean | pl.Categorical]] = {
    "success": pl.Boolean,
    "symbol": pl.Categorical,
    "amount": pl.String,
}

# Withdrawals endpoint schema (for lists of withdrawals)
WITHDRAWALS_SCHEMA = WITHDRAWAL_SCHEMA.copy()

# Deposit data endpoint schema (for deposit information)
DEPOSIT_DATA_SCHEMA: dict[str, type[pl.String]] = {
    "address": pl.String,
    "paymentid": pl.String,
    "iban": pl.String,
    "bic": pl.String,
    "description": pl.String,
}

# Transaction history item schema (minimal - only core fields that are always present)
TRANSACTION_HISTORY_ITEM_SCHEMA: dict[str, type[pl.String | pl.Categorical]] = {
    "transactionId": pl.String,
    "executedAt": pl.String,
    "type": pl.Categorical,
    # Optional fields that may or may not be present depending on transaction type:
    # priceCurrency, priceAmount, sentCurrency, sentAmount,
    # receivedCurrency, receivedAmount, feesCurrency, feesAmount, address
}

# Alternative comprehensive schema for cases where all fields are known to be present
TRANSACTION_HISTORY_ITEM_FULL_SCHEMA: dict[str, type[pl.String | pl.Categorical]] = {
    "transactionId": pl.String,
    "executedAt": pl.String,
    "type": pl.Categorical,
    "priceCurrency": pl.Categorical,
    "priceAmount": pl.String,
    "sentCurrency": pl.Categorical,
    "sentAmount": pl.String,
    "receivedCurrency": pl.Categorical,
    "receivedAmount": pl.String,
    "feesCurrency": pl.Categorical,
    "feesAmount": pl.String,
    "address": pl.String,
}

# Transaction history response schema (for DataFrame containing transaction items)
# Since transaction_history now returns tuple(items_df, metadata_dict),
# the DataFrame contains transaction items, not pagination metadata
TRANSACTION_HISTORY_SCHEMA = TRANSACTION_HISTORY_ITEM_SCHEMA.copy()

# Default schemas mapping for each private endpoint
# note that it doesn't always make sense for certain schemas to exist.
DEFAULT_SCHEMAS: dict[str, Mapping[str, object]] = {
    "account": {},  # placeholder - method will return Failure for DataFrame requests
    "balance": BALANCE_SCHEMA,
    "order": ORDER_SCHEMA,
    "orders": ORDERS_SCHEMA,
    "cancel_order": CANCEL_ORDER_SCHEMA,
    "trade_history": TRADES_SCHEMA,
    "transaction_history": TRANSACTION_HISTORY_SCHEMA,
    "fees": FEES_SCHEMA,
    "deposit": {},  # placeholder - method will return Failure for DataFrame requests
    "deposit_history": DEPOSIT_HISTORY_SCHEMA,
    "withdraw": WITHDRAW_RESPONSE_SCHEMA,
    "withdrawal": WITHDRAWAL_SCHEMA,
    "withdrawals": WITHDRAWALS_SCHEMA,
}

# Combined default schema for when you want all endpoints to use DataFrames
COMBINED_DEFAULT_SCHEMA: dict[str, Mapping[str, object]] = DEFAULT_SCHEMAS.copy()
