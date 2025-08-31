"""Main facade for the Bitvavo client."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, TypeVar

from bitvavo_client.auth.rate_limit import RateLimitManager
from bitvavo_client.core import models
from bitvavo_client.core.settings import BitvavoSettings
from bitvavo_client.endpoints.private import PrivateAPI
from bitvavo_client.endpoints.public import PublicAPI
from bitvavo_client.transport.http import HTTPClient

if TYPE_CHECKING:
    import httpx
    from returns.result import Result

    from bitvavo_client.adapters.returns_adapter import BitvavoError
    from bitvavo_client.core.types import AnyDict

T = TypeVar("T")


class BitvavoClient:
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
    def time(self, model: type[T] = models.ServerTime) -> Result[T, BitvavoError | httpx.HTTPError]:
        """Get server time."""
        return self.public.time(model=model)

    def markets(
        self,
        options: AnyDict | None = None,
        *,
        model: type[T] | Any | None = models.Markets,
        schema: dict | None = None,
    ) -> Result[T, BitvavoError | httpx.HTTPError]:
        """Get market information."""
        return self.public.markets(options, model=model, schema=schema)

    def assets(
        self,
        options: AnyDict | None = None,
        *,
        model: type[T] | Any | None = models.Assets,
        schema: dict | None = None,
    ) -> Result[T, BitvavoError | httpx.HTTPError]:
        """Get asset information."""
        return self.public.assets(options, model=model, schema=schema)

    def book(
        self,
        market: str,
        options: AnyDict | None = None,
        *,
        model: type[T] | Any | None = models.OrderBook,
        schema: dict | None = None,
    ) -> Result[T, BitvavoError | httpx.HTTPError]:
        """Get order book for a market."""
        return self.public.book(market, options, model=model, schema=schema)

    def public_trades(
        self,
        market: str,
        options: AnyDict | None = None,
        *,
        model: type[T] | Any | None = models.Trades,
        schema: dict | None = None,
    ) -> Result[T, BitvavoError | httpx.HTTPError]:
        """Get public trades for a market."""
        return self.public.public_trades(market, options, model=model, schema=schema)

    def candles(
        self,
        market: str,
        interval: str,
        options: AnyDict | None = None,
        *,
        model: type[T] | Any | None = models.Candles,
        schema: dict | None = None,
    ) -> Result[T, BitvavoError | httpx.HTTPError]:
        """Get candlestick data for a market."""
        return self.public.candles(market, interval, options, model=model, schema=schema)

    def ticker_price(
        self,
        options: AnyDict | None = None,
        *,
        model: type[T] | Any | None = models.TickerPrices,
        schema: dict | None = None,
    ) -> Result[T, BitvavoError | httpx.HTTPError]:
        """Get ticker prices."""
        return self.public.ticker_price(options, model=model, schema=schema)

    def ticker_book(
        self,
        options: AnyDict | None = None,
        *,
        model: type[T] | Any | None = models.TickerBooks,
        schema: dict | None = None,
    ) -> Result[T, BitvavoError | httpx.HTTPError]:
        """Get ticker book information."""
        return self.public.ticker_book(options, model=model, schema=schema)

    def ticker_24h(
        self,
        options: AnyDict | None = None,
        *,
        model: type[T] | Any | None = models.Ticker24hs,
        schema: dict | None = None,
    ) -> Result[T, BitvavoError | httpx.HTTPError]:
        """Get 24h ticker statistics."""
        return self.public.ticker_24h(options, model=model, schema=schema)

    # TODO(NostraDavid): fix the private part of the API.
    # Backward-compatible private methods
    def account(self) -> Result[dict[str, object], BitvavoError]:
        """Get account information."""
        return self.private.account()

    def balance(
        self,
        options: AnyDict | None = None,
    ) -> Result[list[dict[str, object]] | dict[str, object], BitvavoError]:
        """Get account balance."""
        return self.private.balance(options)

    def place_order(
        self,
        market: str,
        side: str,
        order_type: str,
        body: AnyDict,
    ) -> Result[dict[str, object], BitvavoError]:
        """Place a new order."""
        return self.private.place_order(market, side, order_type, body)

    def get_order(self, market: str, order_id: str) -> Result[dict[str, object], BitvavoError]:
        """Get order by ID."""
        return self.private.get_order(market, order_id)

    def update_order(
        self,
        market: str,
        order_id: str,
        body: AnyDict,
    ) -> Result[dict[str, object], BitvavoError]:
        """Update an existing order."""
        return self.private.update_order(market, order_id, body)

    def cancel_order(self, market: str, order_id: str) -> Result[dict[str, object], BitvavoError]:
        """Cancel an order."""
        return self.private.cancel_order(market, order_id)

    def get_orders(self, market: str, options: AnyDict | None = None) -> Result[dict[str, object], BitvavoError]:
        """Get orders for a market."""
        return self.private.get_orders(market, options)

    def cancel_orders(self, market: str) -> Result[dict[str, object], BitvavoError]:
        """Cancel all orders for a market."""
        return self.private.cancel_orders(market)

    def orders_open(self, options: AnyDict | None = None) -> Result[dict[str, object], BitvavoError]:
        """Get all open orders."""
        return self.private.orders_open(options)

    def trades(self, market: str, options: AnyDict | None = None) -> Result[dict[str, object], BitvavoError]:
        """Get trades for a market."""
        return self.private.trades(market, options)

    def fees(self, options: AnyDict | None = None) -> Result[dict[str, object], BitvavoError]:
        """Get trading fees."""
        return self.private.fees(options)

    def deposits(self, options: AnyDict | None = None) -> Result[dict[str, object], BitvavoError]:
        """Get deposit history."""
        return self.private.deposits(options)

    def withdrawals(self, options: AnyDict | None = None) -> Result[dict[str, object], BitvavoError]:
        """Get withdrawal history."""
        return self.private.withdrawals(options)

    def withdraw(
        self,
        symbol: str,
        amount: str,
        address: str,
        options: AnyDict | None = None,
    ) -> Result[dict[str, object], BitvavoError]:
        """Withdraw assets."""
        return self.private.withdraw(symbol, amount, address, options)
