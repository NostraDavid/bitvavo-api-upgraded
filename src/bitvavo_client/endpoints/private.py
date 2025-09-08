"""Private API endpoints that require authentication."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, ClassVar, TypeVar

import httpx
from returns.result import Failure, Result, Success

from bitvavo_client.adapters.returns_adapter import BitvavoError
from bitvavo_client.core import private_models
from bitvavo_client.core.model_preferences import ModelPreference
from bitvavo_client.endpoints.base import (
    _DATAFRAME_LIBRARY_MAP,
    BaseAPI,
    _create_dataframe_from_data,
)
from bitvavo_client.endpoints.common import create_postfix, default
from bitvavo_client.schemas.private_schemas import DEFAULT_SCHEMAS

if TYPE_CHECKING:  # pragma: no cover
    from bitvavo_client.core.types import AnyDict
    from bitvavo_client.transport.http import HTTPClient

T = TypeVar("T")


class PrivateAPI(BaseAPI):
    """Handles all private Bitvavo API endpoints requiring authentication."""

    _endpoint_models: ClassVar[dict[str, Any]] = {
        "account": private_models.Account,
        "balance": private_models.Balances,
        "orders": private_models.Orders,
        "order": private_models.Order,
        "trade_history": private_models.Trades,
        "transaction_history": private_models.TransactionHistory,
        "fees": private_models.Fees,
        "deposit_history": private_models.DepositHistories,
        "deposit": private_models.Deposit,
        "withdrawals": private_models.Withdrawals,
        "withdraw": private_models.WithdrawResponse,
        "cancel_order": private_models.CancelOrderResponse,
    }

    _default_schemas = DEFAULT_SCHEMAS

    def __init__(
        self,
        http_client: HTTPClient,
        *,
        preferred_model: ModelPreference | str | None = None,
        default_schema: dict | None = None,
    ) -> None:
        """Initialize private API handler."""
        super().__init__(http_client, preferred_model=preferred_model, default_schema=default_schema)

    def account(
        self,
        *,
        model: type[T] | Any | None = None,
        schema: dict | None = None,
    ) -> Result[T, BitvavoError | httpx.HTTPError | TypeError]:
        """Get account information including fees and capabilities.

        Endpoint: GET /v2/account
        Rate limit weight: 1

        Args:
            model: Optional Pydantic model to validate response

        Returns:
            Result containing account information including fees and capabilities:
            {
                "fees": {
                    "tier": 0,
                    "volume": "0.00",
                    "maker": "0.0015",
                    "taker": "0.0025"
                },
                "capabilities": [
                    "buy", "sell", "depositCrypto", "depositFiat",
                    "withdrawCrypto", "withdrawFiat"
                ]
            }
        """
        # Check if DataFrame is requested - not supported for this endpoint
        effective_model, effective_schema = self._get_effective_model("account", model, schema)
        if effective_model in _DATAFRAME_LIBRARY_MAP:
            msg = "DataFrame model is not supported due to the shape of data"
            return Failure(TypeError(msg))

        # Get raw data from API
        raw_result = self.http.request("GET", "/account", weight=1)
        # Convert to desired format
        return self._convert_raw_result(raw_result, "account", model, schema)

    def balance(
        self,
        options: AnyDict | None = None,
        *,
        model: type[T] | Any | None = None,
        schema: dict | None = None,
    ) -> Result[T, BitvavoError | httpx.HTTPError]:
        """Get account balance.

        Args:
            options: Optional query parameters
            model: Optional Pydantic model to validate response

        Returns:
            Result containing balance information or error
        """
        postfix = create_postfix(options)

        # Get raw data from API
        raw_result = self.http.request("GET", f"/balance{postfix}", weight=5)
        # Convert to desired format
        return self._convert_raw_result(raw_result, "balance", model, schema)

    def place_order(
        self,
        market: str,
        side: str,
        order_type: str,
        operator_id: int,
        body: AnyDict,
        *,
        response_required: bool = True,
        model: type[T] | Any | None = None,
        schema: dict | None = None,
    ) -> Result[T, BitvavoError | httpx.HTTPError]:
        """Place a new order.

        Args:
            market: Market symbol
            side: Order side ('buy' or 'sell')
            order_type: Order type ('market', 'limit', etc.)
            operator_id: Your identifier for the trader or bot within your account
            body: Order parameters (amount, price, etc.)
            response_required: Whether to return full order details (True) or minimal response (False)

        Returns:
            Order placement result
        """
        effective_model, effective_schema = self._get_effective_model("order", model, schema)
        payload = {
            "market": market,
            "side": side,
            "orderType": order_type,
            "operatorId": operator_id,
            "responseRequired": response_required,
            **body,
        }
        return self.http.request("POST", "/order", body=payload, weight=1)

    def get_order(
        self,
        market: str,
        order_id: str,
        *,
        model: type[T] | Any | None = None,
        schema: dict | None = None,
    ) -> Result[T, BitvavoError | httpx.HTTPError]:
        """Get order by ID.

        Args:
            market: Market symbol
            order_id: Order ID
            model: Optional Pydantic model to validate response

        Returns:
            Result containing order information or error
        """
        # Get raw data from API
        raw_result = self.http.request(
            "GET",
            f"/{market}/order",
            body={"orderId": order_id},
            weight=1,
        )
        # Convert to desired format
        return self._convert_raw_result(raw_result, "order", model, schema)

    def update_order(
        self,
        market: str,
        operator_id: int,
        *,
        order_id: str | None = None,
        client_order_id: str | None = None,
        amount: str | None = None,
        amount_quote: str | None = None,
        amount_remaining: str | None = None,
        price: str | None = None,
        trigger_amount: str | None = None,
        time_in_force: str | None = None,
        self_trade_prevention: str | None = None,
        post_only: bool | None = None,
        response_required: bool | None = None,
        model: type[T] | Any | None = None,
        schema: dict | None = None,
    ) -> Result[T, BitvavoError | httpx.HTTPError]:
        """Update an existing limit or trigger order.

        Args:
            market: Market symbol (e.g., 'BTC-EUR')
            operator_id: Your identifier for the trader or bot within your account
            order_id: Bitvavo identifier of the order to update (required if client_order_id not provided)
            client_order_id: Your identifier of the order to update (required if order_id not provided)
            amount: Amount of base currency to update
            amount_quote: Amount of quote currency (market orders only)
            amount_remaining: Remaining amount of base currency to update
            price: Price for limit orders
            trigger_amount: Trigger price for stop orders
            time_in_force: Time in force ('GTC', 'IOC', 'FOK')
            self_trade_prevention: Self-trade prevention
                ('decrementAndCancel', 'cancelOldest', 'cancelNewest', 'cancelBoth')
            post_only: Whether order should only be maker
            response_required: Whether to return full response or just status code
            model: Optional Pydantic model to validate response
            schema: Optional schema for DataFrame conversion

        Returns:
            Result containing updated order information or error

        Note:
            - You must set either order_id or client_order_id
            - If both are set, client_order_id takes precedence
            - Updates are faster than canceling and creating new orders
            - Only works with limit or trigger orders
        """
        if not order_id and not client_order_id:
            error = BitvavoError(
                http_status=400,
                error_code=203,
                reason="Missing or incompatible parameters in your request.",
                message="Either order_id or client_order_id must be provided",
                raw={"provided": {"order_id": order_id, "client_order_id": client_order_id}},
            )
            return Failure(error)

        effective_model, effective_schema = self._get_effective_model("order", model, schema)
        payload = self._build_update_order_payload(
            market,
            operator_id,
            order_id,
            client_order_id,
            amount,
            amount_quote,
            amount_remaining,
            price,
            trigger_amount,
            time_in_force,
            self_trade_prevention,
            post_only=post_only,
            response_required=response_required,
        )

        return self.http.request("PUT", "/order", body=payload, weight=1)

    def _build_update_order_payload(
        self,
        market: str,
        operator_id: int,
        order_id: str | None,
        client_order_id: str | None,
        amount: str | None,
        amount_quote: str | None,
        amount_remaining: str | None,
        price: str | None,
        trigger_amount: str | None,
        time_in_force: str | None,
        self_trade_prevention: str | None,
        *,
        post_only: bool | None,
        response_required: bool | None,
    ) -> dict[str, Any]:
        """Build the payload for update order request."""
        payload = {
            "market": market,
            "operatorId": operator_id,
        }

        # Add order identifier - clientOrderId takes precedence if both provided
        if client_order_id:
            payload["clientOrderId"] = client_order_id
        elif order_id:
            payload["orderId"] = order_id

        # Add optional update parameters
        payload.update(
            {
                key: value
                for key, value in {
                    "amount": amount,
                    "amountQuote": amount_quote,
                    "amountRemaining": amount_remaining,
                    "price": price,
                    "triggerAmount": trigger_amount,
                    "timeInForce": time_in_force,
                    "selfTradePrevention": self_trade_prevention,
                    "postOnly": post_only,
                    "responseRequired": response_required,
                }.items()
                if value is not None
            }
        )

        return payload

    def cancel_order(
        self,
        market: str,
        operator_id: int,
        *,
        order_id: str | None = None,
        client_order_id: str | None = None,
        model: type[T] | Any | None = None,
        schema: dict | None = None,
    ) -> Result[T, BitvavoError | httpx.HTTPError]:
        """Cancel an order.

        Args:
            market: Market symbol
            operator_id: Your identifier for the trader or bot within your account
            order_id: Bitvavo identifier of the order (required if client_order_id not provided)
            client_order_id: Your identifier of the order (required if order_id not provided)
            model: Optional Pydantic model to validate response

        Returns:
            Result containing cancellation result or error

        Note:
            You must set either order_id or client_order_id. If you set both,
            client_order_id takes precedence as per Bitvavo documentation.
        """
        if not order_id and not client_order_id:
            # Create a validation error using httpx.HTTPError as a fallback
            error = httpx.RequestError("Either order_id or client_order_id must be provided")
            return Failure(error)

        # Build query parameters
        params = {
            "market": market,
            "operatorId": operator_id,
        }

        if client_order_id:
            params["clientOrderId"] = client_order_id
        elif order_id:
            params["orderId"] = order_id

        # Create query string
        postfix = create_postfix(params)

        effective_model, effective_schema = self._get_effective_model("cancel_order", model, schema)
        return self.http.request(
            "DELETE",
            f"/order{postfix}",
            weight=1,
        )

    def get_orders(
        self,
        market: str,
        options: AnyDict | None = None,
        *,
        model: type[T] | Any | None = None,
        schema: dict | None = None,
    ) -> Result[T, BitvavoError | httpx.HTTPError]:
        """Get orders for a market.

        Args:
            market: Market symbol (e.g., 'BTC-EUR')
            options: Optional query parameters:
                - limit (int): Max number of orders (1-1000, default: 500)
                - start (int): Unix timestamp in ms to start from
                - end (int): Unix timestamp in ms to end at (max: 8640000000000000)
                - orderIdFrom (str): UUID to start from
                - orderIdTo (str): UUID to end at
            model: Optional Pydantic model to validate response
            schema: Optional schema for DataFrame conversion

        Returns:
            Result containing list of orders or error

        Rate limit weight: 5
        """
        # Constants for validation
        MIN_LIMIT = 1
        MAX_LIMIT = 1000
        MAX_TIMESTAMP = 8640000000000000

        # Validate options if provided
        if options:
            # Validate limit parameter
            if "limit" in options:
                limit = options["limit"]
                if not isinstance(limit, int) or limit < MIN_LIMIT or limit > MAX_LIMIT:
                    msg = f"Invalid limit '{limit}'. Must be an integer between {MIN_LIMIT} and {MAX_LIMIT}"
                    raise ValueError(msg)

            # Validate end timestamp
            if "end" in options:
                end = options["end"]
                if not isinstance(end, int) or end > MAX_TIMESTAMP:
                    msg = f"Invalid end timestamp '{end}'. Must be <= {MAX_TIMESTAMP}"
                    raise ValueError(msg)

            # Validate start/end relationship
            if "start" in options and "end" in options and options["start"] > options["end"]:
                msg = f"Start timestamp ({options['start']}) cannot be greater than end timestamp ({options['end']})"
                raise ValueError(msg)

        effective_model, effective_schema = self._get_effective_model("orders", model, schema)
        options = default(options, {})
        options["market"] = market
        postfix = create_postfix(options)

        # Get raw data first
        raw_result = self.http.request("GET", f"/orders{postfix}", weight=5)

        # Convert using the shared method
        return self._convert_raw_result(raw_result, "orders", effective_model, effective_schema)

    def cancel_orders(
        self,
        operator_id: int,
        *,
        market: str | None = None,
        model: type[T] | Any | None = None,
        schema: dict | None = None,
    ) -> Result[T, BitvavoError | httpx.HTTPError]:
        """Cancel all orders for a market or the entire account.

        Args:
            operator_id: Your identifier for the trader or bot within your account
            market: Optional market symbol. If not specified, all open orders are canceled
            model: Optional Pydantic model to validate response

        Returns:
            Result containing array of cancellation results or error

        Example Response:
            [
                {
                    "orderId": "1be6d0df-d5dc-4b53-a250-3376f3b393e6",
                    "operatorId": 543462
                }
            ]
        """
        effective_model, effective_schema = self._get_effective_model("orders", model, schema)

        # Build query parameters
        params: dict[str, Any] = {"operatorId": operator_id}
        if market is not None:
            params["market"] = market

        postfix = create_postfix(params)
        return self.http.request("DELETE", f"/orders{postfix}", weight=1)

    def orders_open(
        self,
        options: AnyDict | None = None,
        *,
        model: type[T] | Any | None = None,
        schema: dict | None = None,
    ) -> Result[T, BitvavoError | httpx.HTTPError]:
        """Get all open orders.

        Args:
            options: Optional query parameters. Supports:
                - market (str): Filter by specific market (e.g., 'BTC-EUR')
                - base (str): Filter by base asset (e.g., 'BTC')
            model: Optional Pydantic model to validate response

        Returns:
            Result containing open orders data or error

        Rate limit: 25 points (without market), 1 point (with market)
        """
        effective_model, effective_schema = self._get_effective_model("orders", model, schema)
        postfix = create_postfix(options)

        # Rate limit is 1 point with market parameter, 25 points without
        weight = 1 if options and "market" in options else 25

        # Get raw data first
        raw_result = self.http.request("GET", f"/ordersOpen{postfix}", weight=weight)

        # Convert using the shared method
        return self._convert_raw_result(raw_result, "orders", effective_model, effective_schema)

    def fees(
        self,
        options: AnyDict | None = None,
        *,
        model: type[T] | Any | None = None,
        schema: dict | None = None,
    ) -> Result[T, BitvavoError | httpx.HTTPError]:
        """Get market-specific trading fees.

        Returns your current trading fees from the Category of the specified market
        based on the trading volume of your account. This is different from the
        account() method which returns general account information with fees wrapped
        in a "fees" object plus capabilities.

        Endpoint: GET /v2/account/fees
        Rate limit weight: 1

        Args:
            options: Optional query parameters:
                - market (str): Market symbol (e.g., 'BTC-EUR'). If not specified,
                  returns fees for your current tier in Category B.
                - quote (str): Quote currency ('EUR' or 'USDC'). If not specified,
                  returns fees for your current tier in Category B.
            model: Optional Pydantic model to validate response

        Returns:
            Result containing market fee information directly (no wrapper, includes tier):
            {
                "tier": "0",
                "volume": "10000.00",
                "taker": "0.0025",
                "maker": "0.0015"
            }

        Note:
            This differs from account() which returns:
            {
                "fees": {"tier": "0", "volume": "...", "maker": "...", "taker": "..."},
                "capabilities": [...]
            }
        """
        # Validate quote parameter if provided
        if options and "quote" in options:
            quote = options["quote"]
            valid_quotes = ["EUR", "USDC"]
            if quote not in valid_quotes:
                msg = f"Invalid quote currency '{quote}'. Must be one of: {valid_quotes}"
                raise ValueError(msg)

        effective_model, effective_schema = self._get_effective_model("fees", model, schema)
        postfix = create_postfix(options)

        # Get raw data first
        raw_result = self.http.request("GET", f"/account/fees{postfix}", weight=1)

        # Convert using the shared method
        return self._convert_raw_result(raw_result, "fees", effective_model, effective_schema)

    def deposit(
        self,
        symbol: str,
        *,
        model: type[T] | Any | None = None,
        schema: dict | None = None,
    ) -> Result[T, BitvavoError | httpx.HTTPError | TypeError]:
        """Get deposit data for making deposits.

        Returns wallet or bank account information required to deposit digital or fiat assets.

        Endpoint: GET /v2/deposit
        Rate limit weight: 1

        Args:
            symbol: The asset symbol you want to deposit (e.g., 'BTC', 'EUR')
            model: Optional Pydantic model to validate response
            schema: Optional schema for DataFrame conversion

        Returns:
            Result containing deposit information:
            - For digital assets: {"address": "string", "paymentid": "string"}
            - For fiat: {"iban": "string", "bic": "string", "description": "string"}
        """

        effective_model, effective_schema = self._get_effective_model("deposit", model, schema)

        if effective_model in _DATAFRAME_LIBRARY_MAP:
            msg = "DataFrame model is not supported due to the shape of data"
            return Failure(TypeError(msg))

        params = {"symbol": symbol}
        postfix = create_postfix(params)

        # Get raw data first
        raw_result = self.http.request(
            "GET",
            f"/deposit{postfix}",
            weight=1,
        )

        # Convert using the shared method
        return self._convert_raw_result(raw_result, "deposit", effective_model, effective_schema)

    def deposit_history(
        self,
        options: AnyDict | None = None,
        *,
        model: type[T] | Any | None = None,
        schema: dict | None = None,
    ) -> Result[T, BitvavoError | httpx.HTTPError]:
        """Get deposit history.

        Ensures every deposit dict includes a non-empty "address" key (fallback to txId or "unknown").

        Args:
            options: Optional query parameters
            model: Optional Pydantic model to validate response

        Returns:
            Result containing deposits data or error
        """
        effective_model, effective_schema = self._get_effective_model("deposit_history", model, schema)
        postfix = create_postfix(options)

        # Get raw data first
        raw_result = self.http.request("GET", f"/depositHistory{postfix}", weight=5)

        # Convert using the shared method
        return self._convert_raw_result(raw_result, "deposit_history", effective_model, effective_schema)

    def withdrawals(
        self,
        options: AnyDict | None = None,
        *,
        model: type[T] | Any | None = None,
        schema: dict | None = None,
    ) -> Result[T, BitvavoError | httpx.HTTPError]:
        """Get withdrawal history.

        Args:
            options: Optional query parameters
            model: Optional Pydantic model to validate response

        Returns:
            Result containing withdrawals data or error
        """
        effective_model, effective_schema = self._get_effective_model("withdrawals", model, schema)
        postfix = create_postfix(options)

        # Get raw data first
        raw_result = self.http.request("GET", f"/withdrawalHistory{postfix}", weight=1)

        # Convert using the shared method
        return self._convert_raw_result(raw_result, "withdrawals", effective_model, effective_schema)

    def _convert_transaction_items(
        self,
        items_data: list[dict],
        effective_model: type[T] | Any | None,
        effective_schema: dict | None,
    ) -> Result[Any, BitvavoError]:
        """Convert transaction items to the desired model format."""
        if effective_model in _DATAFRAME_LIBRARY_MAP and isinstance(effective_model, ModelPreference):
            # Convert items to DataFrame using the specific preference
            return _create_dataframe_from_data(
                items_data, effective_model, items_key=None, empty_schema=effective_schema
            )

        if effective_model is Any or effective_model is None:
            # Raw data - return items list directly
            return Success(items_data)

        # Handle Pydantic or other model types
        try:
            if hasattr(effective_model, "model_validate"):
                # Pydantic model - validate items list
                parsed_items = effective_model.model_validate(items_data)  # type: ignore[misc]
            elif effective_schema is None:
                # Simple constructor call
                parsed_items = effective_model(items_data)  # type: ignore[misc]
            else:
                # Other models with schema
                parsed_items = effective_model(items_data, schema=effective_schema)  # type: ignore[misc]

            return Success(parsed_items)
        except (ValueError, TypeError, AttributeError) as exc:
            # If conversion fails, return a structured error
            error = BitvavoError(
                http_status=500,
                error_code=-1,
                reason="Model conversion failed",
                message=str(exc),
                raw=items_data if isinstance(items_data, dict) else {"raw": items_data},
            )
            return Failure(error)

    def transaction_history(
        self,
        options: AnyDict | None = None,
        *,
        model: type[T] | Any | None = None,
        schema: dict | None = None,
    ) -> Result[tuple[Any, dict[str, Any]], BitvavoError | httpx.HTTPError]:
        """Get account transaction history.

        Returns all past transactions for your account with pagination support.

        Endpoint: GET /v2/account/history
        Rate limit weight: 1

        Args:
            options: Optional query parameters:
                - fromDate (int): Unix timestamp in ms to start from (>=0)
                - toDate (int): Unix timestamp in ms to end at (<=8640000000000000)
                - page (int): Page number for pagination (>=1)
                - maxItems (int): Max number of items per page (1-100, default: 100)
                - type (str): Transaction type filter:
                    'sell', 'buy', 'staking', 'fixed_staking', 'deposit', 'withdrawal',
                    'affiliate', 'distribution', 'internal_transfer', 'withdrawal_cancelled',
                    'rebate', 'loan', 'external_transferred_funds', 'manually_assigned_bitvavo'
            model: Optional Pydantic model to validate response
            schema: Optional schema for DataFrame conversion

        Returns:
            Result containing transaction history as tuple of (items_converted, metadata_dict):
            - For DataFrames: Returns tuple of (DataFrame of items, metadata dict)
            - For Pydantic models: Returns tuple of (Pydantic model of items, metadata dict)
            - For raw responses: Returns tuple of (list of items, metadata dict)

            Each transaction contains:
            - transactionId: Unique transaction identifier
            - executedAt: Execution timestamp (ISO format)
            - type: Transaction type
            - priceCurrency/priceAmount: Transaction price info (optional for staking)
            - sentCurrency/sentAmount: Sent amounts (optional for staking)
            - receivedCurrency/receivedAmount: Received amounts
            - feesCurrency/feesAmount: Fee information (optional for staking)
            - address: Transaction address (nullable)
        """
        postfix = create_postfix(options)

        # Get raw data first
        raw_result = self.http.request("GET", f"/account/history{postfix}", weight=1)

        # Always split the response into items and metadata for all model types
        match raw_result:
            case Success(raw_data):
                # Validate response structure
                if not isinstance(raw_data, dict) or "items" not in raw_data:
                    error = BitvavoError(
                        http_status=500,
                        error_code=-1,
                        reason="Response parsing failed",
                        message="Expected response to have 'items' key for transaction history",
                        raw=raw_data if isinstance(raw_data, dict) else {"raw": raw_data},
                    )
                    return Failure(error)

                # Extract items and metadata separately
                items_data = raw_data["items"]
                metadata = {k: v for k, v in raw_data.items() if k != "items"}

                effective_model, effective_schema = self._get_effective_model("transaction_history", model, schema)
                # Convert items using helper method
                items_result = self._convert_transaction_items(items_data, effective_model, effective_schema)
                match items_result:
                    case Success(converted_items):
                        return Success((converted_items, metadata))
                    case Failure(error):
                        return Failure(error)
                    case _:
                        # This case should never be reached, but satisfies type checker
                        msg = "Unexpected result type from _convert_transaction_items"
                        raise RuntimeError(msg)

            case Failure(error):
                return Failure(error)
            case _:
                # This case should never be reached, but satisfies type checker
                msg = "Unexpected result type from HTTP request"
                raise RuntimeError(msg)

    def trade_history(
        self,
        market: str,
        options: AnyDict | None = None,
        *,
        model: type[T] | Any | None = None,
        schema: dict | None = None,
    ) -> Result[T, BitvavoError | httpx.HTTPError]:
        """Get trade history for your account.

        Returns the specified number of past trades for your account, excluding Price Guarantee.
        The returned trades are sorted by their timestamp in descending order, from latest to earliest.

        Endpoint: GET /v2/trades
        Rate limit weight: 5

        Args:
            market: The market for which to return the past trades (e.g., 'BTC-EUR')
            options: Optional query parameters:
                - limit (int): Max number of trades (1-1000, default: 500)
                - start (int): Unix timestamp in ms to start from
                - end (int): Unix timestamp in ms to end at (max: 8640000000000000)
                - tradeIdFrom (str): Trade ID to start from
                - tradeIdTo (str): Trade ID to end at
                - tradeId (str, deprecated): Interpreted as tradeIdTo
            model: Optional Pydantic model to validate response
            schema: Optional schema for DataFrame conversion

        Returns:
            Result containing list of trade objects with fields like:
            - id: Trade identifier
            - orderId: Bitvavo order ID
            - clientOrderId: Your order ID
            - timestamp: Unix timestamp in ms
            - market: Market symbol
            - side: 'buy' or 'sell'
            - amount: Base currency amount
            - price: Price per unit
            - taker: Whether you were the taker
            - fee: Fee paid (negative for rebates)
            - feeCurrency: Currency of the fee
            - settled: Whether fee was deducted

        Note:
            This is a private endpoint that returns YOUR trades, different from the public
            trades endpoint which returns public market trades.
        """
        # Constants for validation
        MIN_LIMIT = 1
        MAX_LIMIT = 1000
        MAX_TIMESTAMP = 8640000000000000

        # Validate options if provided
        if options:
            # Validate limit parameter
            if "limit" in options:
                limit = options["limit"]
                if not isinstance(limit, int) or limit < MIN_LIMIT or limit > MAX_LIMIT:
                    msg = f"Invalid limit '{limit}'. Must be an integer between {MIN_LIMIT} and {MAX_LIMIT}"
                    raise ValueError(msg)

            # Validate end timestamp
            if "end" in options:
                end = options["end"]
                if not isinstance(end, int) or end > MAX_TIMESTAMP:
                    msg = f"Invalid end timestamp '{end}'. Must be <= {MAX_TIMESTAMP}"
                    raise ValueError(msg)

            # Validate start/end relationship
            if "start" in options and "end" in options and options["start"] > options["end"]:
                msg = f"Start timestamp ({options['start']}) cannot be greater than end timestamp ({options['end']})"
                raise ValueError(msg)

            # Handle deprecated tradeId parameter
            if "tradeId" in options and "tradeIdTo" not in options:
                # Move deprecated tradeId to tradeIdTo as per documentation
                options = options.copy()  # Don't mutate the original
                options["tradeIdTo"] = options.pop("tradeId")

        effective_model, effective_schema = self._get_effective_model("trade_history", model, schema)

        # Add market to options
        query_options = default(options, {})
        query_options["market"] = market

        postfix = create_postfix(query_options)

        # Get raw data first
        raw_result = self.http.request("GET", f"/trades{postfix}", weight=5)

        # Convert using the shared method
        return self._convert_raw_result(raw_result, "trade_history", effective_model, effective_schema)

    def withdraw(
        self,
        symbol: str,
        amount: str,
        address: str,
        options: AnyDict | None = None,
        *,
        model: type[T] | Any | None = None,
        schema: dict | None = None,
    ) -> Result[T, BitvavoError | httpx.HTTPError]:
        """Withdraw assets.

        Args:
            symbol: Asset symbol
            amount: Amount to withdraw
            address: Withdrawal address
            options: Optional parameters
            model: Optional Pydantic model to validate response

        Returns:
            Result containing withdrawal result or error
        """
        body = {"symbol": symbol, "amount": amount, "address": address}
        if options:
            body.update(options)
        raw_result = self.http.request("POST", "/withdrawal", body=body, weight=1)
        return self._convert_raw_result(raw_result, "withdraw", model, schema)
