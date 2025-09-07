"""Pydantic models for validating API responses."""

from __future__ import annotations

from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, RootModel, field_validator, model_validator


class PlaceOrderRequest(BaseModel):
    """Request model for creating a new order."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        str_strip_whitespace=True,
        validate_assignment=True,
    )

    # Required fields
    market: str = Field(..., description="Market symbol (e.g., 'BTC-EUR')")
    side: Literal["buy", "sell"] = Field(..., description="Order side")
    order_type: str = Field(..., alias="orderType", description="Order type")
    operator_id: int = Field(..., alias="operatorId", description="Operator ID", ge=1)

    # Optional fields
    client_order_id: str | None = Field(None, alias="clientOrderId", description="Client-provided order ID")
    amount: str | None = Field(None, description="Base currency amount as string")
    amount_quote: str | None = Field(None, alias="amountQuote", description="Quote currency amount as string")
    price: str | None = Field(None, description="Price as string (for limit orders)")
    trigger_amount: str | None = Field(None, alias="triggerAmount", description="Trigger amount as string")
    trigger_type: str | None = Field(None, alias="triggerType", description="Trigger type")
    trigger_reference: str | None = Field(None, alias="triggerReference", description="Trigger reference")
    time_in_force: str | None = Field(None, alias="timeInForce", description="Time in force")
    post_only: bool | None = Field(None, alias="postOnly", description="Post-only flag")
    self_trade_prevention: str | None = Field(None, alias="selfTradePrevention", description="Self-trade prevention")
    disable_market_protection: bool | None = Field(
        None, alias="disableMarketProtection", description="Disable market protection (deprecated, must be false)"
    )
    response_required: bool | None = Field(None, alias="responseRequired", description="Response required flag")

    @field_validator("side")
    @classmethod
    def _validate_side(cls, v: str) -> Literal["buy", "sell"]:
        if v not in ("buy", "sell"):
            msg = f"side must be 'buy' or 'sell', got '{v}'"
            raise ValueError(msg)
        return v  # type: ignore[return-value]

    @field_validator("order_type")
    @classmethod
    def _validate_order_type(cls, v: str) -> str:
        valid_types = {"market", "limit", "stopLoss", "stopLossLimit", "takeProfit", "takeProfitLimit"}
        if v not in valid_types:
            msg = f"order_type must be one of {valid_types}, got '{v}'"
            raise ValueError(msg)
        return v

    @field_validator("amount", "amount_quote", "price", "trigger_amount")
    @classmethod
    def _validate_numeric_strings(cls, v: str | None) -> str | None:
        if v is None:
            return v
        try:
            d = Decimal(v)
        except Exception as exc:
            msg = "must be a valid numeric string"
            raise ValueError(msg) from exc
        if d <= 0:
            msg = "must be positive"
            raise ValueError(msg)
        return v

    @field_validator("disable_market_protection")
    @classmethod
    def _validate_market_protection(cls, v: bool | None) -> bool | None:  # noqa: FBT001 (bool as arg)
        if v is True:
            msg = "disable_market_protection must be false (market protection cannot be disabled)"
            raise ValueError(msg)
        return v


class UpdateOrderRequest(BaseModel):
    """Request model for updating an existing order."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        str_strip_whitespace=True,
        validate_assignment=True,
    )

    # Required fields
    market: str = Field(..., description="Market symbol (e.g., 'BTC-EUR')")
    operator_id: int = Field(..., alias="operatorId", description="Your identifier for the trader or bot", ge=1)

    # Either orderId or clientOrderId must be provided
    order_id: str | None = Field(None, alias="orderId", description="Bitvavo identifier of the order to update")
    client_order_id: str | None = Field(
        None, alias="clientOrderId", description="Your identifier of the order to update"
    )

    # Optional update fields
    amount: str | None = Field(None, description="Base currency amount as string")
    amount_quote: str | None = Field(None, alias="amountQuote", description="Quote currency amount as string")
    amount_remaining: str | None = Field(None, alias="amountRemaining", description="Remaining amount of base currency")
    price: str | None = Field(None, description="Price as string")
    trigger_amount: str | None = Field(None, alias="triggerAmount", description="Trigger amount as string")
    time_in_force: Literal["GTC", "IOC", "FOK"] | None = Field(None, alias="timeInForce", description="Time in force")
    self_trade_prevention: Literal["decrementAndCancel", "cancelOldest", "cancelNewest", "cancelBoth"] | None = Field(
        None, alias="selfTradePrevention", description="Self-trade prevention"
    )
    post_only: bool | None = Field(None, alias="postOnly", description="Post-only flag")
    response_required: bool | None = Field(None, alias="responseRequired", description="Response required flag")

    @model_validator(mode="after")
    def _validate_order_identifier(self) -> UpdateOrderRequest:
        """Ensure either order_id or client_order_id is provided."""
        if not self.order_id and not self.client_order_id:
            msg = "Either order_id or client_order_id must be provided"
            raise ValueError(msg)
        return self

    @field_validator("amount", "amount_quote", "amount_remaining", "price", "trigger_amount")
    @classmethod
    def _validate_numeric_strings(cls, v: str | None) -> str | None:
        if v is None:
            return v
        try:
            d = Decimal(v)
        except Exception as exc:
            msg = "must be a valid numeric string"
            raise ValueError(msg) from exc
        if d <= 0:
            msg = "must be positive"
            raise ValueError(msg)
        return v


class Fees(BaseModel):
    """Account fee information as returned by Bitvavo."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        str_strip_whitespace=True,
        validate_assignment=True,
    )

    tier: int = Field(..., description="Fee tier", ge=0)
    volume: str = Field(..., description="30d trading volume as string")
    maker: str = Field(..., description="Maker fee as string (e.g. '0.0015')")
    taker: str = Field(..., description="Taker fee as string (e.g. '0.0025')")

    @field_validator("volume", "maker", "taker")
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

    def maker_decimal(self) -> Decimal:
        return Decimal(self.maker)

    def taker_decimal(self) -> Decimal:
        return Decimal(self.taker)

    def volume_decimal(self) -> Decimal:
        return Decimal(self.volume)


class Account(BaseModel):
    """Bitvavo account model (mirrors /account response)."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        str_strip_whitespace=True,
        validate_assignment=True,
    )

    fees: Fees = Field(..., description="Account fee information")
    capabilities: list[str] = Field(..., description="Enabled account capabilities", min_length=0)

    @field_validator("capabilities")
    @classmethod
    def _validate_capabilities(cls, v: list[str]) -> list[str]:
        if not isinstance(v, list):
            msg = "capabilities must be a list of strings"
            raise TypeError(msg)
        if not all(isinstance(x, str) and x.strip() for x in v):
            msg = "capabilities entries must be non-empty strings"
            raise ValueError(msg)
        return [s.strip() for s in v]

    def has_capability(self, capability: str) -> bool:
        return capability in self.capabilities


class Balance(BaseModel):
    """Asset balance as returned by GET /balance."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        str_strip_whitespace=True,
        validate_assignment=True,
    )

    symbol: str = Field(..., description="Asset symbol (e.g. 'BTC')")
    available: str = Field(..., description="Available amount as string")
    in_order: str = Field(..., alias="inOrder", description="Amount currently in open orders as string")

    @field_validator("symbol")
    @classmethod
    def _validate_symbol(cls, v: str) -> str:
        if not isinstance(v, str) or not v.strip():
            msg = "symbol must be a non-empty string"
            raise ValueError(msg)
        return v.strip()

    @field_validator("available", "in_order")
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

    def available_decimal(self) -> Decimal:
        return Decimal(self.available)

    def in_order_decimal(self) -> Decimal:
        return Decimal(self.in_order)

    def total_decimal(self) -> Decimal:
        return self.available_decimal() + self.in_order_decimal()


class Balances(RootModel[list[Balance]]):
    """List model for GET /balance response."""

    model_config = ConfigDict(
        frozen=True,
        str_strip_whitespace=True,
        validate_assignment=True,
    )

    @field_validator("root")
    @classmethod
    def _validate_unique_symbols(cls, v: list[Balance]) -> list[Balance]:
        seen: set[str] = set()
        for b in v:
            if b.symbol in seen:
                msg = f"duplicate balance for symbol '{b.symbol}'"
                raise ValueError(msg)
            seen.add(b.symbol)
        return v

    def by_symbol(self, symbol: str) -> Balance | None:
        s = symbol.strip()
        for b in self.root:
            if b.symbol == s:
                return b
        return None

    def as_dict(self) -> dict[str, Balance]:
        return {b.symbol: b for b in self.root}

    def totals(self) -> dict[str, Decimal]:
        return {b.symbol: b.total_decimal() for b in self.root}


class OrderFill(BaseModel):
    """Fill details for an order."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        str_strip_whitespace=True,
        validate_assignment=True,
    )

    id: str = Field(..., description="Fill ID")
    timestamp: int = Field(..., description="Fill timestamp in milliseconds")
    amount: str = Field(..., description="Fill amount as string")
    price: str = Field(..., description="Fill price as string")
    taker: bool = Field(..., description="Whether this was a taker order")
    fee: str = Field(..., description="Fee paid as string")
    fee_currency: str = Field(..., alias="feeCurrency", description="Currency of the fee")
    settled: bool = Field(..., description="Whether the fill is settled")

    @field_validator("amount", "price", "fee")
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

    def amount_decimal(self) -> Decimal:
        return Decimal(self.amount)

    def price_decimal(self) -> Decimal:
        return Decimal(self.price)

    def fee_decimal(self) -> Decimal:
        return Decimal(self.fee)


class Order(BaseModel):
    """Order details from various order endpoints."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        str_strip_whitespace=True,
        validate_assignment=True,
    )

    order_id: str = Field(..., alias="orderId", description="Order ID")
    market: str = Field(..., description="Market symbol (e.g. 'BTC-EUR')")
    created: int = Field(..., description="Creation timestamp in milliseconds")
    updated: int = Field(..., description="Last update timestamp in milliseconds")
    status: str = Field(..., description="Order status (new, filled, partiallyFilled, canceled)")
    side: Literal["buy", "sell"] = Field(..., description="Order side")
    order_type: str = Field(..., alias="orderType", description="Order type (limit, market, stopLoss, etc.)")

    # Optional fields that may not be present in all order responses
    client_order_id: str | None = Field(None, alias="clientOrderId", description="Client-provided order ID")
    self_trade_prevention: str | None = Field(
        None, alias="selfTradePrevention", description="Self trade prevention setting"
    )
    visible: bool | None = Field(None, description="Whether order is visible in order book")
    on_hold: str | None = Field(None, alias="onHold", description="Amount on hold as string")
    on_hold_currency: str | None = Field(None, alias="onHoldCurrency", description="Currency of the on hold amount")
    fills: list[OrderFill] = Field(default_factory=list, description="Order fills")
    fee_paid: str | None = Field(None, alias="feePaid", description="Total fee paid as string")
    fee_currency: str | None = Field(None, alias="feeCurrency", description="Currency of the fee")
    operator_id: int | None = Field(None, alias="operatorId", description="Operator ID")
    price: str | None = Field(None, description="Order price as string (for limit orders)")
    time_in_force: str | None = Field(None, alias="timeInForce", description="Time in force (GTC, IOC, FOK)")
    post_only: bool | None = Field(None, alias="postOnly", description="Whether order is post-only")
    amount: str | None = Field(None, description="Order amount as string")
    amount_remaining: str | None = Field(None, alias="amountRemaining", description="Remaining amount as string")
    filled_amount: str | None = Field(None, alias="filledAmount", description="Filled amount as string")
    filled_amount_quote: str | None = Field(
        None, alias="filledAmountQuote", description="Filled quote amount as string"
    )
    amount_quote: str | None = Field(
        None, alias="amountQuote", description="Quote amount as string (for market orders)"
    )
    amount_quote_remaining: str | None = Field(
        None, alias="amountQuoteRemaining", description="Remaining quote amount as string"
    )
    created_ns: int | None = Field(None, alias="createdNs", description="Creation timestamp in nanoseconds")
    updated_ns: int | None = Field(None, alias="updatedNs", description="Last update timestamp in nanoseconds")
    disable_market_protection: bool | None = Field(
        None, alias="disableMarketProtection", description="Whether market protection is disabled"
    )
    trigger_price: str | None = Field(None, alias="triggerPrice", description="Calculated trigger price as string")
    trigger_amount: str | None = Field(
        None, alias="triggerAmount", description="User-specified trigger amount as string"
    )
    trigger_type: str | None = Field(None, alias="triggerType", description="Type of trigger (e.g., 'price')")
    trigger_reference: str | None = Field(
        None,
        alias="triggerReference",
        description="Price reference for triggering (lastTrade, bestBid, bestAsk, midPrice)",
    )
    restatement_reason: str | None = Field(
        None, alias="restatementReason", description="Reason for order status change (e.g., cancellation reason)"
    )

    @field_validator("side")
    @classmethod
    def _validate_side(cls, v: str) -> Literal["buy", "sell"]:
        if v not in ("buy", "sell"):
            msg = f"side must be 'buy' or 'sell', got '{v}'"
            raise ValueError(msg)
        return v  # type: ignore[return-value]

    @field_validator(
        "on_hold",
        "fee_paid",
        "price",
        "amount",
        "amount_remaining",
        "filled_amount",
        "filled_amount_quote",
        "amount_quote",
        "amount_quote_remaining",
        "trigger_price",
        "trigger_amount",
    )
    @classmethod
    def _numeric_str_optional(cls, v: str | None) -> str | None:
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

    def price_decimal(self) -> Decimal | None:
        return Decimal(self.price) if self.price else None

    def amount_decimal(self) -> Decimal | None:
        return Decimal(self.amount) if self.amount else None

    def filled_amount_decimal(self) -> Decimal | None:
        return Decimal(self.filled_amount) if self.filled_amount else None

    def trigger_price_decimal(self) -> Decimal | None:
        return Decimal(self.trigger_price) if self.trigger_price else None

    def trigger_amount_decimal(self) -> Decimal | None:
        return Decimal(self.trigger_amount) if self.trigger_amount else None


class Orders(RootModel[list[Order]]):
    """List model for order responses."""

    model_config = ConfigDict(
        frozen=True,
        str_strip_whitespace=True,
        validate_assignment=True,
    )

    def by_id(self, order_id: str) -> Order | None:
        for order in self.root:
            if order.order_id == order_id:
                return order
        return None

    def by_market(self, market: str) -> list[Order]:
        return [order for order in self.root if order.market == market]

    def open_orders(self) -> list[Order]:
        return [order for order in self.root if order.status in ("new", "partiallyFilled")]


class CancelOrderResponse(BaseModel):
    """Response model for order cancellation."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        str_strip_whitespace=True,
        validate_assignment=True,
    )

    order_id: str = Field(..., alias="orderId", description="Bitvavo identifier of the cancelled order")
    client_order_id: str | None = Field(
        None, alias="clientOrderId", description="Your identifier of the cancelled order"
    )
    operator_id: int = Field(..., alias="operatorId", description="Operator ID")


class Trade(BaseModel):
    """Trade details from trade endpoints."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        str_strip_whitespace=True,
        validate_assignment=True,
    )

    id: str = Field(..., description="Trade ID")
    timestamp: int = Field(..., description="Trade timestamp in milliseconds")
    amount: str = Field(..., description="Trade amount as string")
    price: str = Field(..., description="Trade price as string")
    side: Literal["buy", "sell"] = Field(..., description="Trade side")

    # Optional fields
    market: str | None = Field(None, description="Market symbol (e.g. 'BTC-EUR')")
    fee: str | None = Field(None, description="Fee paid as string")
    fee_currency: str | None = Field(None, alias="feeCurrency", description="Currency of the fee")
    settled: bool | None = Field(None, description="Whether the trade is settled")

    @field_validator("side")
    @classmethod
    def _validate_side(cls, v: str) -> Literal["buy", "sell"]:
        if v not in ("buy", "sell"):
            msg = f"side must be 'buy' or 'sell', got '{v}'"
            raise ValueError(msg)
        return v  # type: ignore[return-value]

    @field_validator("amount", "price", "fee")
    @classmethod
    def _numeric_str_optional(cls, v: str | None) -> str | None:
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

    def amount_decimal(self) -> Decimal:
        return Decimal(self.amount)

    def price_decimal(self) -> Decimal:
        return Decimal(self.price)

    def fee_decimal(self) -> Decimal | None:
        return Decimal(self.fee) if self.fee else None


class Trades(RootModel[list[Trade]]):
    """List model for trade responses."""

    model_config = ConfigDict(
        frozen=True,
        str_strip_whitespace=True,
        validate_assignment=True,
    )

    def by_market(self, market: str) -> list[Trade]:
        return [trade for trade in self.root if trade.market == market]

    def by_side(self, side: Literal["buy", "sell"]) -> list[Trade]:
        return [trade for trade in self.root if trade.side == side]


class DepositHistory(BaseModel):
    """Deposit details from deposit history."""

    model_config = ConfigDict(
        frozen=True,
        str_strip_whitespace=True,
        validate_assignment=True,
    )

    timestamp: int = Field(..., description="Deposit timestamp in milliseconds")
    symbol: str = Field(..., description="Asset symbol (e.g. 'EUR', 'BTC')")
    amount: str = Field(..., description="Deposit amount as string")
    fee: str = Field(..., description="Deposit fee as string")
    status: str = Field(..., description="Deposit status (completed, pending, etc.)")
    address: str | None = Field(None, description="Deposit address")

    # Optional fields
    payment_id: str | None = Field(None, alias="paymentId", description="Payment ID if required (for crypto deposits)")
    tx_id: str | None = Field(None, alias="txId", description="Transaction ID (for crypto deposits)")

    @field_validator("amount", "fee")
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

    def amount_decimal(self) -> Decimal:
        return Decimal(self.amount)

    def fee_decimal(self) -> Decimal:
        return Decimal(self.fee)

    def get_address(self) -> str:
        """Get deposit address, falling back to txId or 'unknown' if neither is available."""
        return self.address or self.tx_id or "unknown"


class DepositHistories(RootModel[list[DepositHistory]]):
    """List model for deposit history responses."""

    model_config = ConfigDict(
        frozen=True,
        str_strip_whitespace=True,
        validate_assignment=True,
    )

    def by_symbol(self, symbol: str) -> list[DepositHistory]:
        return [deposit for deposit in self.root if deposit.symbol == symbol]

    def by_status(self, status: str) -> list[DepositHistory]:
        return [deposit for deposit in self.root if deposit.status == status]


class Withdrawal(BaseModel):
    """Withdrawal details from withdrawal history."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        str_strip_whitespace=True,
        validate_assignment=True,
    )

    timestamp: int = Field(..., description="Withdrawal timestamp in milliseconds")
    symbol: str = Field(..., description="Asset symbol (e.g. 'EUR', 'BTC')")
    amount: str = Field(..., description="Withdrawal amount as string")
    fee: str = Field(..., description="Withdrawal fee as string")
    status: str = Field(..., description="Withdrawal status (completed, pending, etc.)")
    address: str = Field(..., description="Withdrawal address")

    # Optional fields
    tx_id: str | None = Field(None, alias="txId", description="Transaction ID (for crypto withdrawals)")

    @field_validator("amount", "fee")
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

    def amount_decimal(self) -> Decimal:
        return Decimal(self.amount)

    def fee_decimal(self) -> Decimal:
        return Decimal(self.fee)


class Withdrawals(RootModel[list[Withdrawal]]):
    """List model for withdrawal history responses."""

    model_config = ConfigDict(
        frozen=True,
        str_strip_whitespace=True,
        validate_assignment=True,
    )

    def by_symbol(self, symbol: str) -> list[Withdrawal]:
        return [withdrawal for withdrawal in self.root if withdrawal.symbol == symbol]

    def by_status(self, status: str) -> list[Withdrawal]:
        return [withdrawal for withdrawal in self.root if withdrawal.status == status]


class WithdrawResponse(BaseModel):
    """Response model for withdraw assets operation."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        str_strip_whitespace=True,
        validate_assignment=True,
    )

    success: bool = Field(..., description="Indicates if the withdrawal request was successful")
    symbol: str = Field(..., description="The asset that was withdrawn")
    amount: str = Field(..., description="The total amount deducted from your balance")

    @field_validator("amount")
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

    def amount_decimal(self) -> Decimal:
        return Decimal(self.amount)


class DepositDigital(BaseModel):
    """Digital asset deposit data response."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        str_strip_whitespace=True,
        validate_assignment=True,
    )

    address: str = Field(..., description="The address where to deposit assets")
    paymentid: str | None = Field(None, description="Payment ID if required (also called note, memo, or tag)")


class DepositFiat(BaseModel):
    """Fiat deposit data response."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        str_strip_whitespace=True,
        validate_assignment=True,
    )

    iban: str = Field(..., description="International bank account number where to deposit assets")
    bic: str = Field(..., description="Bank identification code sometimes necessary for international transfers")
    description: str = Field(..., description="Description which must be used for the deposit")


class Deposit(BaseModel):
    """Union type for deposit data responses that handles both digital and fiat deposit information."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        str_strip_whitespace=True,
        validate_assignment=True,
    )

    # For digital assets
    address: str | None = Field(None, description="The address where to deposit assets")
    paymentid: str | None = Field(None, description="Payment ID if required (also called note, memo, or tag)")

    # For fiat
    iban: str | None = Field(None, description="International bank account number where to deposit assets")
    bic: str | None = Field(
        None, description="Bank identification code sometimes necessary for international transfers"
    )
    description: str | None = Field(None, description="Description which must be used for the deposit")

    @field_validator("address", "iban", mode="before")
    @classmethod
    def _ensure_non_empty_strings(cls, v: str | None) -> str | None:
        """Ensure address and iban are non-empty if provided."""
        if v is not None and isinstance(v, str) and not v.strip():
            msg = "Address and IBAN cannot be empty strings"
            raise ValueError(msg)
        return v

    def is_digital(self) -> bool:
        """Check if this is digital asset deposit data."""
        return self.address is not None

    def is_fiat(self) -> bool:
        """Check if this is fiat deposit data."""
        return self.iban is not None


class TransactionHistoryItem(BaseModel):
    """Single transaction from account transaction history."""

    model_config = ConfigDict(
        frozen=True,
        str_strip_whitespace=True,
        validate_assignment=True,
    )

    transaction_id: str = Field(..., alias="transactionId", description="The unique identifier of the transaction")
    executed_at: str = Field(
        ..., alias="executedAt", description="The Unix timestamp when the transaction was executed"
    )
    type: Literal[
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
    ] = Field(..., description="The type of transaction")
    price_currency: str | None = Field(
        None, alias="priceCurrency", description="The currency in which the transaction was made"
    )
    price_amount: str | None = Field(None, alias="priceAmount", description="The amount of the transaction")
    sent_currency: str | None = Field(
        None, alias="sentCurrency", description="The currency that was sent in the transaction"
    )
    sent_amount: str | None = Field(None, alias="sentAmount", description="The amount that was sent in the transaction")
    received_currency: str | None = Field(
        None, alias="receivedCurrency", description="The currency that was received in the transaction"
    )
    received_amount: str | None = Field(
        None, alias="receivedAmount", description="The amount that was received in the transaction"
    )
    fees_currency: str | None = Field(
        None, alias="feesCurrency", description="The currency in which the fees were paid"
    )
    fees_amount: str | None = Field(None, alias="feesAmount", description="The amount of fees paid in the transaction")
    address: str | None = Field(None, description="The address where the transaction was made")

    @field_validator("price_amount", "sent_amount", "received_amount", "fees_amount")
    @classmethod
    def _numeric_str(cls, v: str | None) -> str | None:
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

    def price_amount_decimal(self) -> Decimal:
        return Decimal(self.price_amount) if self.price_amount is not None else Decimal(0)

    def sent_amount_decimal(self) -> Decimal:
        return Decimal(self.sent_amount) if self.sent_amount is not None else Decimal(0)

    def received_amount_decimal(self) -> Decimal:
        return Decimal(self.received_amount) if self.received_amount is not None else Decimal(0)

    def fees_amount_decimal(self) -> Decimal:
        return Decimal(self.fees_amount) if self.fees_amount is not None else Decimal(0)


class TransactionHistoryMetadata(BaseModel):
    """Metadata for transaction history pagination."""

    model_config = ConfigDict(
        frozen=True,
        str_strip_whitespace=True,
        validate_assignment=True,
    )

    current_page: int = Field(..., alias="currentPage", description="The current page number")
    total_pages: int = Field(..., alias="totalPages", description="The total number of returned pages")
    max_items: int = Field(..., alias="maxItems", description="The maximum number of transactions per page")

    @field_validator("current_page", "total_pages", "max_items")
    @classmethod
    def _positive_int(cls, v: int) -> int:
        if v < 1:
            msg = "must be positive"
            raise ValueError(msg)
        return v


class TransactionHistory(RootModel[list[TransactionHistoryItem]]):
    """List model for transaction history items."""

    model_config = ConfigDict(
        frozen=True,
        str_strip_whitespace=True,
        validate_assignment=True,
    )

    def by_type(self, transaction_type: str) -> list[TransactionHistoryItem]:
        """Filter transactions by type."""
        return [tx for tx in self.root if tx.type == transaction_type]

    def by_currency(self, currency: str) -> list[TransactionHistoryItem]:
        """Filter transactions involving a specific currency."""
        return [
            tx
            for tx in self.root
            if currency in (tx.price_currency, tx.sent_currency, tx.received_currency, tx.fees_currency)
        ]
