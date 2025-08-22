"""Main facade for the Bitvavo client."""

from __future__ import annotations

from typing import TYPE_CHECKING

from bitvavo_client.auth.rate_limit import RateLimitManager
from bitvavo_client.core.settings import BitvavoSettings
from bitvavo_client.endpoints.private import PrivateAPI
from bitvavo_client.endpoints.public import PublicAPI
from bitvavo_client.transport.http import HTTPClient

if TYPE_CHECKING:
    from bitvavo_client.core.types import AnyDict


class Bitvavo:
    """Main Bitvavo API client facade providing backward-compatible interface."""

    def __init__(self, settings: BitvavoSettings | None = None) -> None:
        """Initialize Bitvavo client.

        Args:
            settings: Optional settings override. If None, uses defaults.
        """
        self.settings: BitvavoSettings = settings or BitvavoSettings()
        self.rate_limiter: RateLimitManager = RateLimitManager(
            self.settings.default_rate_limit,
            self.settings.rate_limit_buffer,
        )
        self.http: HTTPClient = HTTPClient(self.settings, self.rate_limiter)

        # Initialize API endpoint handlers
        self.public: PublicAPI = PublicAPI(self.http)
        self.private: PrivateAPI = PrivateAPI(self.http)

        # Configure API keys if available
        self._configure_api_keys()

    def _configure_api_keys(self) -> None:
        """Configure API keys for authentication."""
        if self.settings.api_key and self.settings.api_secret:
            # Single API key configuration
            self.http.configure_key(self.settings.api_key, self.settings.api_secret, 0)
            self.rate_limiter.ensure_key(0)
        elif self.settings.api_keys:
            # Multiple API keys - configure the first one by default
            if self.settings.api_keys:
                first_key = self.settings.api_keys[0]
                self.http.configure_key(first_key["key"], first_key["secret"], 0)
                self.rate_limiter.ensure_key(0)

    # Backward-compatible public methods
    def time(self) -> dict[str, object]:
        """Get server time."""
        return self.public.time()

    def markets(self, options: AnyDict | None = None) -> list[dict[str, object]] | dict[str, object]:
        """Get market information."""
        return self.public.markets(options)

    def assets(self, options: AnyDict | None = None) -> list[dict[str, object]] | dict[str, object]:
        """Get asset information."""
        return self.public.assets(options)

    def book(self, market: str, options: AnyDict | None = None) -> dict[str, object]:
        """Get order book for a market."""
        return self.public.book(market, options)

    def public_trades(self, market: str, options: AnyDict | None = None) -> dict[str, object]:
        """Get public trades for a market."""
        return self.public.public_trades(market, options)

    def candles(self, market: str, interval: str, options: AnyDict | None = None) -> dict[str, object]:
        """Get candlestick data for a market."""
        return self.public.candles(market, interval, options)

    def ticker_price(self, options: AnyDict | None = None) -> list[dict[str, object]] | dict[str, object]:
        """Get ticker prices."""
        return self.public.ticker_price(options)

    def ticker_book(self, options: AnyDict | None = None) -> list[dict[str, object]] | dict[str, object]:
        """Get ticker book information."""
        return self.public.ticker_book(options)

    def ticker_24h(self, options: AnyDict | None = None) -> list[dict[str, object]] | dict[str, object]:
        """Get 24h ticker statistics."""
        return self.public.ticker_24h(options)

    # Backward-compatible private methods
    def account(self) -> dict[str, object]:
        """Get account information."""
        return self.private.account()

    def balance(self, options: AnyDict | None = None) -> list[dict[str, object]] | dict[str, object]:
        """Get account balance."""
        return self.private.balance(options)

    def place_order(
        self,
        market: str,
        side: str,
        order_type: str,
        body: AnyDict,
    ) -> dict[str, object]:
        """Place a new order."""
        return self.private.place_order(market, side, order_type, body)

    def get_order(self, market: str, order_id: str) -> dict[str, object]:
        """Get order by ID."""
        return self.private.get_order(market, order_id)

    def update_order(
        self,
        market: str,
        order_id: str,
        body: AnyDict,
    ) -> dict[str, object]:
        """Update an existing order."""
        return self.private.update_order(market, order_id, body)

    def cancel_order(self, market: str, order_id: str) -> dict[str, object]:
        """Cancel an order."""
        return self.private.cancel_order(market, order_id)

    def get_orders(self, market: str, options: AnyDict | None = None) -> dict[str, object]:
        """Get orders for a market."""
        return self.private.get_orders(market, options)

    def cancel_orders(self, market: str) -> dict[str, object]:
        """Cancel all orders for a market."""
        return self.private.cancel_orders(market)

    def orders_open(self, options: AnyDict | None = None) -> dict[str, object]:
        """Get all open orders."""
        return self.private.orders_open(options)

    def trades(self, market: str, options: AnyDict | None = None) -> dict[str, object]:
        """Get trades for a market."""
        return self.private.trades(market, options)

    def fees(self, options: AnyDict | None = None) -> dict[str, object]:
        """Get trading fees."""
        return self.private.fees(options)

    def deposits(self, options: AnyDict | None = None) -> dict[str, object]:
        """Get deposit history."""
        return self.private.deposits(options)

    def withdrawals(self, options: AnyDict | None = None) -> dict[str, object]:
        """Get withdrawal history."""
        return self.private.withdrawals(options)

    def withdraw(self, symbol: str, amount: str, address: str, options: AnyDict | None = None) -> dict[str, object]:
        """Withdraw assets."""
        return self.private.withdraw(symbol, amount, address, options)
