"""Public API endpoints that don't require authentication."""

from __future__ import annotations

from typing import TYPE_CHECKING, TypeVar

from typing_extensions import Any

from bitvavo_client.core import models
from bitvavo_client.endpoints.common import create_postfix

if TYPE_CHECKING:
    import httpx
    from returns.result import Result

    from bitvavo_client.adapters.returns_adapter import BitvavoError
    from bitvavo_client.core.types import AnyDict
    from bitvavo_client.transport.http import HTTPClient

T = TypeVar("T")


class PublicAPI:
    """Handles all public Bitvavo API endpoints."""

    def __init__(self, http_client: HTTPClient) -> None:
        """Initialize public API handler.

        Args:
            http_client: HTTP client for making requests
        """
        self.http: HTTPClient = http_client

    def time(self, *, model: type[T] = models.ServerTime) -> Result[T, BitvavoError | httpx.HTTPError]:
        """Get server time.

        Args:
            model: Optional Pydantic model to validate response

        Returns:
            Result containing server time or error
        """
        return self.http.request("GET", "/time", weight=1, model=model)

    def markets(
        self,
        options: AnyDict | None = None,
        *,
        model: type[T] | Any | None = models.Markets,
        schema: dict | None = None,
    ) -> Result[T, BitvavoError | httpx.HTTPError]:
        """Get market information.

        Args:
            options: Optional query parameters
            model: Optional Pydantic model to validate response

        Returns:
            Result containing market information or error
        """
        postfix = create_postfix(options)
        return self.http.request("GET", f"/markets{postfix}", weight=1, model=model, schema=schema)

    def assets(
        self,
        options: AnyDict | None = None,
        *,
        model: type[T] | Any | None = models.Assets,
        schema: dict | None = None,
    ) -> Result[T, BitvavoError | httpx.HTTPError]:
        """Get asset information.

        Args:
            options: Optional query parameters
            model: Optional Pydantic model to validate response

        Returns:
            Result containing asset information or error
        """
        postfix = create_postfix(options)
        return self.http.request("GET", f"/assets{postfix}", weight=1, model=model, schema=schema)

    def book(
        self,
        market: str,
        options: AnyDict | None = None,
        *,
        model: type[T] | Any | None = models.OrderBook,
        schema: dict | None = None,
    ) -> Result[T, BitvavoError | httpx.HTTPError]:
        """Get order book for a market.

        Args:
            market: Market symbol (e.g., 'BTC-EUR')
            options: Optional query parameters
            model: Optional Pydantic model to validate response

        Returns:
            Result containing order book data or error
        """
        postfix = create_postfix(options)
        return self.http.request("GET", f"/{market}/book{postfix}", weight=1, model=model, schema=schema)

    def public_trades(
        self,
        market: str,
        options: AnyDict | None = None,
        *,
        model: type[T] | Any | None = models.Trades,
        schema: dict | None = None,
    ) -> Result[T, BitvavoError | httpx.HTTPError]:
        """Get public trades for a market.

        Args:
            market: Market symbol
            options: Optional query parameters
            model: Optional Pydantic model to validate response

        Returns:
            Result containing public trades data or error
        """
        postfix = create_postfix(options)
        return self.http.request("GET", f"/{market}/trades{postfix}", weight=5, model=model, schema=schema)

    def candles(
        self,
        market: str,
        interval: str,
        options: AnyDict | None = None,
        *,
        model: type[T] | Any | None = models.Candles,
        schema: dict | None = None,
    ) -> Result[T, BitvavoError | httpx.HTTPError]:
        """Get candlestick data for a market.

        Args:
            market: Market symbol
            interval: Time interval (e.g., '1h', '1d')
            options: Optional query parameters
            model: Optional Pydantic model to validate response

        Returns:
            Result containing candlestick data or error
        """
        if options is None:
            options = {}
        options["interval"] = interval
        postfix = create_postfix(options)
        return self.http.request("GET", f"/{market}/candles{postfix}", weight=1, model=model, schema=schema)

    def ticker_price(
        self,
        options: AnyDict | None = None,
        *,
        model: type[T] | Any | None = models.TickerPrices,
        schema: dict | None = None,
    ) -> Result[T, BitvavoError | httpx.HTTPError]:
        """Get ticker price.

        Args:
            options: Optional query parameters
            model: Optional Pydantic model to validate response

        Returns:
            Result containing ticker price data or error
        """
        postfix = create_postfix(options)
        return self.http.request("GET", f"/ticker/price{postfix}", weight=1, model=model, schema=schema)

    def ticker_book(
        self,
        options: AnyDict | None = None,
        *,
        model: type[T] | Any | None = models.TickerBooks,
        schema: dict | None = None,
    ) -> Result[T, BitvavoError | httpx.HTTPError]:
        """Get ticker book.

        Args:
            options: Optional query parameters
            model: Optional Pydantic model to validate response

        Returns:
            Result containing ticker book data or error
        """
        postfix = create_postfix(options)
        return self.http.request("GET", f"/ticker/book{postfix}", weight=1, model=model, schema=schema)

    def ticker_24h(
        self,
        options: AnyDict | None = None,
        *,
        model: type[T] | Any | None = models.Ticker24hs,
        schema: dict | None = None,
    ) -> Result[T, BitvavoError | httpx.HTTPError]:
        """Get 24h ticker statistics.

        Args:
            options: Optional query parameters
            model: Optional Pydantic model to validate response

        Returns:
            Result containing 24h ticker statistics or error
        """
        postfix = create_postfix(options)
        return self.http.request("GET", f"/ticker/24h{postfix}", weight=1, model=model, schema=schema)
