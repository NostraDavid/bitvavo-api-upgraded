"""Public API endpoints that don't require authentication."""

from __future__ import annotations

from typing import TYPE_CHECKING

from bitvavo_client.endpoints.common import create_postfix

if TYPE_CHECKING:
    from bitvavo_client.core.types import AnyDict
    from bitvavo_client.transport.http import HTTPClient


class PublicAPI:
    """Handles all public Bitvavo API endpoints."""

    def __init__(self, http_client: HTTPClient) -> None:
        """Initialize public API handler.

        Args:
            http_client: HTTP client for making requests
        """
        self.http: HTTPClient = http_client

    def time(self) -> dict[str, object]:
        """Get server time.

        Returns:
            Server time information
        """
        return self.http.request("GET", "/time", weight=1)

    def markets(self, options: AnyDict | None = None) -> list[dict[str, object]] | dict[str, object]:
        """Get market information.

        Args:
            options: Optional query parameters

        Returns:
            Market information as list or single market dict
        """
        postfix = create_postfix(options)
        return self.http.request("GET", f"/markets{postfix}", weight=1)

    def assets(self, options: AnyDict | None = None) -> list[dict[str, object]] | dict[str, object]:
        """Get asset information.

        Args:
            options: Optional query parameters

        Returns:
            Asset information as list or single asset dict
        """
        postfix = create_postfix(options)
        return self.http.request("GET", f"/assets{postfix}", weight=1)

    def book(self, market: str, options: AnyDict | None = None) -> dict[str, object]:
        """Get order book for a market.

        Args:
            market: Market symbol (e.g., 'BTC-EUR')
            options: Optional query parameters

        Returns:
            Order book data
        """
        postfix = create_postfix(options)
        return self.http.request("GET", f"/{market}/book{postfix}", weight=1)

    def public_trades(self, market: str, options: AnyDict | None = None) -> dict[str, object]:
        """Get public trades for a market.

        Args:
            market: Market symbol
            options: Optional query parameters

        Returns:
            Public trades data
        """
        postfix = create_postfix(options)
        return self.http.request("GET", f"/{market}/trades{postfix}", weight=5)

    def candles(self, market: str, interval: str, options: AnyDict | None = None) -> dict[str, object]:
        """Get candlestick data for a market.

        Args:
            market: Market symbol
            interval: Time interval (1m, 5m, 1h, 1d, etc.)
            options: Optional query parameters

        Returns:
            Candlestick data
        """
        # Add interval to options
        if options is None:
            options = {}
        options["interval"] = interval

        postfix = create_postfix(options)
        return self.http.request("GET", f"/{market}/candles{postfix}", weight=1)

    def ticker_price(self, options: AnyDict | None = None) -> list[dict[str, object]] | dict[str, object]:
        """Get ticker prices.

        Args:
            options: Optional query parameters

        Returns:
            Ticker price information
        """
        postfix = create_postfix(options)
        return self.http.request("GET", f"/ticker/price{postfix}", weight=1)

    def ticker_book(self, options: AnyDict | None = None) -> list[dict[str, object]] | dict[str, object]:
        """Get ticker book information.

        Args:
            options: Optional query parameters

        Returns:
            Ticker book information
        """
        postfix = create_postfix(options)
        return self.http.request("GET", f"/ticker/book{postfix}", weight=1)

    def ticker_24h(self, options: AnyDict | None = None) -> list[dict[str, object]] | dict[str, object]:
        """Get 24h ticker statistics.

        Args:
            options: Optional query parameters

        Returns:
            24h ticker statistics
        """
        postfix = create_postfix(options)
        return self.http.request("GET", f"/ticker/24h{postfix}", weight=1)
