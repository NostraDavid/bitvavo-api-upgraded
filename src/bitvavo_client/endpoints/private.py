"""Private API endpoints that require authentication."""

from __future__ import annotations

from typing import TYPE_CHECKING, TypeVar

from bitvavo_client.endpoints.common import create_postfix

if TYPE_CHECKING:
    from returns.result import Result

    from bitvavo_client.adapters.returns_adapter import BitvavoError
    from bitvavo_client.core.types import AnyDict
    from bitvavo_client.transport.http import HTTPClient

T = TypeVar("T")


class PrivateAPI:
    """Handles all private Bitvavo API endpoints requiring authentication."""

    def __init__(self, http_client: HTTPClient) -> None:
        """Initialize private API handler.

        Args:
            http_client: HTTP client for making requests
        """
        self.http: HTTPClient = http_client

    def account(self, *, model: type[T] | None = None) -> Result[T | dict[str, object], BitvavoError]:
        """Get account information.

        Args:
            model: Optional Pydantic model to validate response

        Returns:
            Result containing account information or error
        """
        return self.http.request("GET", "/account", weight=1, model=model)

    def balance(
        self,
        options: AnyDict | None = None,
        *,
        model: type[T] | None = None,
    ) -> Result[T | list[dict[str, object]] | dict[str, object], BitvavoError]:
        """Get account balance.

        Args:
            options: Optional query parameters
            model: Optional Pydantic model to validate response

        Returns:
            Result containing balance information or error
        """
        postfix = create_postfix(options)
        return self.http.request("GET", f"/balance{postfix}", weight=1, model=model)

    def place_order(
        self,
        market: str,
        side: str,
        order_type: str,
        body: AnyDict,
        *,
        model: type[T] | None = None,
    ) -> Result[T | dict[str, object], BitvavoError]:
        """Place a new order.

        Args:
            market: Market symbol
            side: Order side ('buy' or 'sell')
            order_type: Order type ('market', 'limit', etc.)
            body: Order parameters

        Returns:
            Order placement result
        """
        payload = {"market": market, "side": side, "orderType": order_type, **body}
        return self.http.request("POST", "/order", body=payload, weight=1, model=model)

    def get_order(
        self,
        market: str,
        order_id: str,
        *,
        model: type[T] | None = None,
    ) -> Result[T | dict[str, object], BitvavoError]:
        """Get order by ID.

        Args:
            market: Market symbol
            order_id: Order ID
            model: Optional Pydantic model to validate response

        Returns:
            Result containing order information or error
        """
        return self.http.request("GET", f"/{market}/order", body={"orderId": order_id}, weight=1, model=model)

    def update_order(
        self,
        market: str,
        order_id: str,
        body: AnyDict,
        *,
        model: type[T] | None = None,
    ) -> Result[T | dict[str, object], BitvavoError]:
        """Update an existing order.

        Args:
            market: Market symbol
            order_id: Order ID to update
            body: Update parameters
            model: Optional Pydantic model to validate response

        Returns:
            Result containing updated order information or error
        """
        payload = {**body, "market": market, "orderId": order_id}
        return self.http.request("PUT", f"/{market}/order", body=payload, weight=1, model=model)

    def cancel_order(
        self,
        market: str,
        order_id: str,
        *,
        model: type[T] | None = None,
    ) -> Result[T | dict[str, object], BitvavoError]:
        """Cancel an order.

        Args:
            market: Market symbol
            order_id: Order ID to cancel
            model: Optional Pydantic model to validate response

        Returns:
            Result containing cancellation result or error
        """
        return self.http.request("DELETE", f"/{market}/order", body={"orderId": order_id}, weight=1, model=model)

    def get_orders(
        self,
        market: str,
        options: AnyDict | None = None,
        *,
        model: type[T] | None = None,
    ) -> Result[T | dict[str, object], BitvavoError]:
        """Get orders for a market.

        Args:
            market: Market symbol
            options: Optional query parameters
            model: Optional Pydantic model to validate response

        Returns:
            Result containing orders data or error
        """
        postfix = create_postfix(options)
        return self.http.request("GET", f"/{market}/orders{postfix}", weight=1, model=model)

    def cancel_orders(
        self,
        market: str,
        *,
        model: type[T] | None = None,
    ) -> Result[T | dict[str, object], BitvavoError]:
        """Cancel all orders for a market.

        Args:
            market: Market symbol
            model: Optional Pydantic model to validate response

        Returns:
            Result containing cancellation results or error
        """
        return self.http.request("DELETE", f"/{market}/orders", weight=1, model=model)

    def orders_open(
        self,
        options: AnyDict | None = None,
        *,
        model: type[T] | None = None,
    ) -> Result[T | dict[str, object], BitvavoError]:
        """Get all open orders.

        Args:
            options: Optional query parameters
            model: Optional Pydantic model to validate response

        Returns:
            Result containing open orders data or error
        """
        postfix = create_postfix(options)
        return self.http.request("GET", f"/ordersOpen{postfix}", weight=25, model=model)

    def trades(
        self,
        market: str,
        options: AnyDict | None = None,
        *,
        model: type[T] | None = None,
    ) -> Result[T | dict[str, object], BitvavoError]:
        """Get trades for a market.

        Args:
            market: Market symbol
            options: Optional query parameters
            model: Optional Pydantic model to validate response

        Returns:
            Result containing trades data or error
        """
        postfix = create_postfix(options)
        return self.http.request("GET", f"/{market}/trades{postfix}", weight=1, model=model)

    def fees(
        self,
        options: AnyDict | None = None,
        *,
        model: type[T] | None = None,
    ) -> Result[T | dict[str, object], BitvavoError]:
        """Get trading fees.

        Args:
            options: Optional query parameters
            model: Optional Pydantic model to validate response

        Returns:
            Result containing fee information or error
        """
        postfix = create_postfix(options)
        return self.http.request("GET", f"/account/fees{postfix}", weight=1, model=model)

    def deposits(
        self,
        options: AnyDict | None = None,
        *,
        model: type[T] | None = None,
    ) -> Result[T | dict[str, object], BitvavoError]:
        """Get deposit history.

        Args:
            options: Optional query parameters
            model: Optional Pydantic model to validate response

        Returns:
            Result containing deposits data or error
        """
        postfix = create_postfix(options)
        return self.http.request("GET", f"/depositHistory{postfix}", weight=1, model=model)

    def withdrawals(
        self,
        options: AnyDict | None = None,
        *,
        model: type[T] | None = None,
    ) -> Result[T | dict[str, object], BitvavoError]:
        """Get withdrawal history.

        Args:
            options: Optional query parameters
            model: Optional Pydantic model to validate response

        Returns:
            Result containing withdrawals data or error
        """
        postfix = create_postfix(options)
        return self.http.request("GET", f"/withdrawalHistory{postfix}", weight=1, model=model)

    def withdraw(
        self,
        symbol: str,
        amount: str,
        address: str,
        options: AnyDict | None = None,
        *,
        model: type[T] | None = None,
    ) -> Result[T | dict[str, object], BitvavoError]:
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
        return self.http.request("POST", "/withdrawal", body=body, weight=1, model=model)
