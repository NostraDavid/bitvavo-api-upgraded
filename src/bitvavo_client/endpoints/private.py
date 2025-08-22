"""Private API endpoints that require authentication."""

from __future__ import annotations

from typing import TYPE_CHECKING

from bitvavo_client.endpoints.common import create_postfix

if TYPE_CHECKING:
    from bitvavo_client.core.types import AnyDict
    from bitvavo_client.transport.http import HTTPClient


class PrivateAPI:
    """Handles all private Bitvavo API endpoints requiring authentication."""

    def __init__(self, http_client: HTTPClient) -> None:
        """Initialize private API handler.

        Args:
            http_client: HTTP client for making requests
        """
        self.http: HTTPClient = http_client

    def account(self) -> dict[str, object]:
        """Get account information.

        Returns:
            Account information
        """
        return self.http.request("GET", "/account", weight=1)

    def balance(self, options: AnyDict | None = None) -> list[dict[str, object]] | dict[str, object]:
        """Get account balance.

        Args:
            options: Optional query parameters

        Returns:
            Balance information
        """
        postfix = create_postfix(options)
        return self.http.request("GET", f"/balance{postfix}", weight=1)

    def place_order(
        self,
        market: str,
        side: str,
        order_type: str,
        body: AnyDict,
    ) -> dict[str, object]:
        """Place a new order.

        Args:
            market: Market symbol
            side: Order side ('buy' or 'sell')
            order_type: Order type ('market', 'limit', etc.)
            body: Order parameters

        Returns:
            Order placement result
        """
        payload = {**body, "market": market, "side": side, "orderType": order_type}
        return self.http.request("POST", "/order", body=payload, weight=1)

    def get_order(self, market: str, order_id: str) -> dict[str, object]:
        """Get order by ID.

        Args:
            market: Market symbol
            order_id: Order ID

        Returns:
            Order information
        """
        return self.http.request("GET", f"/{market}/order", body={"orderId": order_id}, weight=1)

    def update_order(
        self,
        market: str,
        order_id: str,
        body: AnyDict,
    ) -> dict[str, object]:
        """Update an existing order.

        Args:
            market: Market symbol
            order_id: Order ID to update
            body: Update parameters

        Returns:
            Updated order information
        """
        payload = {**body, "market": market, "orderId": order_id}
        return self.http.request("PUT", f"/{market}/order", body=payload, weight=1)

    def cancel_order(self, market: str, order_id: str) -> dict[str, object]:
        """Cancel an order.

        Args:
            market: Market symbol
            order_id: Order ID to cancel

        Returns:
            Cancellation result
        """
        return self.http.request("DELETE", f"/{market}/order", body={"orderId": order_id}, weight=1)

    def get_orders(self, market: str, options: AnyDict | None = None) -> dict[str, object]:
        """Get orders for a market.

        Args:
            market: Market symbol
            options: Optional query parameters

        Returns:
            Orders data
        """
        postfix = create_postfix(options)
        return self.http.request("GET", f"/{market}/orders{postfix}", weight=1)

    def cancel_orders(self, market: str) -> dict[str, object]:
        """Cancel all orders for a market.

        Args:
            market: Market symbol

        Returns:
            Cancellation results
        """
        return self.http.request("DELETE", f"/{market}/orders", weight=1)

    def orders_open(self, options: AnyDict | None = None) -> dict[str, object]:
        """Get all open orders.

        Args:
            options: Optional query parameters

        Returns:
            Open orders data
        """
        postfix = create_postfix(options)
        return self.http.request("GET", f"/ordersOpen{postfix}", weight=25)

    def trades(self, market: str, options: AnyDict | None = None) -> dict[str, object]:
        """Get trades for a market.

        Args:
            market: Market symbol
            options: Optional query parameters

        Returns:
            Trades data
        """
        postfix = create_postfix(options)
        return self.http.request("GET", f"/{market}/trades{postfix}", weight=1)

    def fees(self, options: AnyDict | None = None) -> dict[str, object]:
        """Get trading fees.

        Args:
            options: Optional query parameters

        Returns:
            Fee information
        """
        postfix = create_postfix(options)
        return self.http.request("GET", f"/account/fees{postfix}", weight=1)

    def deposits(self, options: AnyDict | None = None) -> dict[str, object]:
        """Get deposit history.

        Args:
            options: Optional query parameters

        Returns:
            Deposits data
        """
        postfix = create_postfix(options)
        return self.http.request("GET", f"/depositHistory{postfix}", weight=1)

    def withdrawals(self, options: AnyDict | None = None) -> dict[str, object]:
        """Get withdrawal history.

        Args:
            options: Optional query parameters

        Returns:
            Withdrawals data
        """
        postfix = create_postfix(options)
        return self.http.request("GET", f"/withdrawalHistory{postfix}", weight=1)

    def withdraw(self, symbol: str, amount: str, address: str, options: AnyDict | None = None) -> dict[str, object]:
        """Withdraw assets.

        Args:
            symbol: Asset symbol
            amount: Amount to withdraw
            address: Withdrawal address
            options: Optional parameters

        Returns:
            Withdrawal result
        """
        body = {"symbol": symbol, "amount": amount, "address": address}
        if options:
            body.update(options)
        return self.http.request("POST", "/withdrawal", body=body, weight=1)
