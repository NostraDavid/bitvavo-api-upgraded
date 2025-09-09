"""
Most of these tests check the keys of the response, the size of the response,
the types of the response, which type those values can be cast to (as quite a
few responses return strings which are obviously int or float types, but those
usually can also return "none")

If you see `pytest.mark.skipif`, you can flip the Bool to enable the test.
"""

from __future__ import annotations

import datetime as dt
import json
import logging
from time import sleep
from typing import TYPE_CHECKING, Any
from unittest.mock import MagicMock, patch

import pytest

from bitvavo_api_upgraded.bitvavo import (
    Bitvavo,
    asks_compare,
    bids_compare,
    error_callback_example,
)
from bitvavo_api_upgraded.settings import bitvavo_settings
from bitvavo_client.endpoints.common import create_postfix

if TYPE_CHECKING:
    from bitvavo_api_upgraded.type_aliases import anydict, errordict

logger = logging.getLogger("test_bitvavo")
"""
* This is an example utilising all functions of the python Bitvavo API wrapper.
* The APIKEY and APISECRET should be replaced by your own key and secret.
* For public functions the APIKEY and SECRET can be removed.
* Documentation: https://docs.bitvavo.com
* Bitvavo: https://bitvavo.com
* README: https://github.com/bitvavo/php-bitvavo-api
"""


def test_createPostfix_happy_path() -> None:
    postfix_input = {
        "option1": "value1",
        "option2": "value2",
        "option3": 3,
        "option4": ["yeet", "yote"],
    }

    output = create_postfix(postfix_input)

    assert output == "?option1=value1&option2=value2&option3=3&option4=['yeet', 'yote']"


def test_createPostfix_empty_input() -> None:
    postfix_input: anydict = {}

    output = create_postfix(postfix_input)

    assert output == ""


def test_asksCompare() -> None:
    """asksCompare() returns a bool, so I'm asserting directly"""
    assert asks_compare(-1, -1) is False
    assert asks_compare(-1, 0)
    assert asks_compare(-1, 1)
    assert asks_compare(0, -1) is False
    assert asks_compare(0, 0) is False
    assert asks_compare(0, 1)
    assert asks_compare(1, -1) is False
    assert asks_compare(1, 0) is False
    assert asks_compare(1, 1) is False


def test_bidsCompare() -> None:
    """asksCompare() returns a bool, so I'm asserting directly"""
    assert bids_compare(-1, -1) is False
    assert bids_compare(-1, 0) is False
    assert bids_compare(-1, 1) is False
    assert bids_compare(0, -1)
    assert bids_compare(0, 0) is False
    assert bids_compare(0, 1) is False
    assert bids_compare(1, -1)
    assert bids_compare(1, 0)
    assert bids_compare(1, 1) is False


class TestBitvavo:
    """this class functions as a grouping of tests, as the code is"""

    def test_remaining_limit(self, bitvavo: Bitvavo) -> None:
        limit = bitvavo.get_remaining_limit()
        assert 0 < limit <= 1000, "default remaining limit should be between 1000 and 0"

    def test_no_error(self, bitvavo: Bitvavo) -> None:
        """
        Any call to bitvavo should produce no errors.

        Below here is a giant list of undocumented error codes - source is CCTX:
        https://github.com/ccxt/ccxt/blob/master/python/ccxt/bitvavo.py

        101: Unknown error. Operation may or may not have succeeded.
        102: Invalid JSON.
        103: You have been rate limited. Please observe the bitvavo-ratelimit-resetat header to see when you can send requests again. Failure to respect self limit will result in an IP ban. The default value is 1000 weighted requests per minute. Please contact support if you wish to increase self limit.
        104: You have been rate limited by the number of new orders. The default value is 100 new orders per second or 100.000 new orders per day. Please update existing orders instead of cancelling and creating orders. Please contact support if you wish to increase self limit.
        105: Your IP or API key has been banned for not respecting the rate limit. The ban expires at ${expiryInMs}.
        107: The matching engine is overloaded. Please wait 500ms and resubmit your order.
        108: The matching engine could not process your order in time. Please consider increasing the access window or resubmit your order.
        109: The matching engine did not respond in time. Operation may or may not have succeeded.
        110: Invalid endpoint. Please check url and HTTP method.
        200: ${param} url parameter is not supported. Please note that parameters are case-sensitive and use body parameters for PUT and POST requests.
        201: ${param} body parameter is not supported. Please note that parameters are case-sensitive and use url parameters for GET and DELETE requests.
        202: ${param} order parameter is not supported. Please note that certain parameters are only allowed for market or limit orders.
        203: {"errorCode":203,"error":"symbol parameter is required."}
        204: ${param} parameter is not supported.
        205: ${param} parameter is invalid.
        206: Use either ${paramA} or ${paramB}. The usage of both parameters at the same time is not supported.
        210: Amount exceeds the maximum allowed amount(1000000000).
        211: Price exceeds the maximum allowed amount(100000000000).
        212: Amount is below the minimum allowed amount for self asset.
        213: Price is below the minimum allowed amount(0.000000000000001).
        214: Price is too detailed
        215: Price is too detailed. A maximum of 15 digits behind the decimal point are allowed.
        216: {"errorCode":216,"error":"You do not have sufficient balance to complete self operation."}
        217: {"errorCode":217,"error":"Minimum order size in quote currency is 5 EUR or 0.001 BTC."}
        230: The order is rejected by the matching engine.
        231: The order is rejected by the matching engine. TimeInForce must be GTC when markets are paused.
        232: You must change at least one of amount, amountRemaining, price, timeInForce, selfTradePrevention or postOnly.
        233: {"errorCode":233,"error":"Order must be active(status new or partiallyFilled) to allow updating/cancelling."}
        234: Market orders cannot be updated.
        235: You can only have 100 open orders on each book.
        236: You can only update amount or amountRemaining, not both.
        240: {"errorCode":240,"error":"No order found. Please be aware that simultaneously updating the same order may return self error."}
        300: Authentication is required for self endpoint.
        301: {"errorCode":301,"error":"API Key must be of length 64."}
        302: Timestamp is invalid. This must be a timestamp in ms. See bitvavo-access-timestamp header or timestamp parameter for websocket.
        303: Window must be between 100 and 60000 ms.
        304: Request was not received within acceptable window(default 30s, or custom with bitvavo-access-window header) of bitvavo-access-timestamp header(or timestamp parameter for websocket).
        304: Authentication is required for self endpoint.
        305: {"errorCode":305,"error":"No active API key found."}
        306: No active API key found. Please ensure that you have confirmed the API key by e-mail.
        307: This key does not allow access from self IP.
        308: {"errorCode":308,"error":"The signature length is invalid(HMAC-SHA256 should return a 64 length hexadecimal string)."}
        309: {"errorCode":309,"error":"The signature is invalid."}
        310: This key does not allow trading actions.
        311: This key does not allow showing account information.
        312: This key does not allow withdrawal of funds.
        315: Websocket connections may not be used in a browser. Please use REST requests for self.
        317: This account is locked. Please contact support.
        400: Unknown error. Please contact support with a copy of your request.
        401: Deposits for self asset are not available at self time.
        402: You need to verify your identitiy before you can deposit and withdraw digital assets.
        403: You need to verify your phone number before you can deposit and withdraw digital assets.
        404: Could not complete self operation, because our node cannot be reached. Possibly under maintenance.
        405: You cannot withdraw digital assets during a cooldown period. This is the result of newly added bank accounts.
        406: {"errorCode":406,"error":"Your withdrawal is too small."}
        407: Internal transfer is not possible.
        408: {"errorCode":408,"error":"You do not have sufficient balance to complete self operation."}
        409: {"errorCode":409,"error":"This is not a verified bank account."}
        410: Withdrawals for self asset are not available at self time.
        411: You can not transfer assets to yourself.
        412: {"errorCode":412,"error":"eth_address_invalid."}
        413: This address violates the whitelist.
        414: You cannot withdraw assets within 2 minutes of logging in.
        """  # noqa: E501 (Line too long)
        response = bitvavo.time()
        assert "error" not in response
        assert "errorCode" not in response

    def test_time(self, bitvavo: Bitvavo) -> None:
        response = bitvavo.time()
        assert isinstance(response, dict)
        assert "time" in response
        assert isinstance(response["time"], int)

    def test_markets_all(self, bitvavo: Bitvavo) -> None:
        response = bitvavo.markets(options={})

        assert isinstance(response, list)

        for market in response:
            # Assert that each market contains these keys
            assert "market" in market
            assert "status" in market
            assert "base" in market
            assert "quote" in market
            assert "pricePrecision" in market
            assert "minOrderInBaseAsset" in market
            assert "minOrderInQuoteAsset" in market
            assert "orderTypes" in market

        for market in response:
            # Assert that each market contains these keys
            assert isinstance(market["market"], str)
            assert isinstance(market["status"], str)
            assert isinstance(market["base"], str)
            assert isinstance(market["quote"], str)
            assert isinstance(market["pricePrecision"], int)
            assert isinstance(market["minOrderInBaseAsset"], str)
            assert isinstance(market["minOrderInQuoteAsset"], str)
            assert isinstance(market["orderTypes"], list)

        for market in response:
            # Assert that each market contains these keys
            assert market["status"] in ["trading", "halted", "auction"]
            assert float(market["minOrderInBaseAsset"]) >= 0
            assert float(market["minOrderInQuoteAsset"]) >= 0

    def test_markets_single(self, bitvavo: Bitvavo) -> None:
        response = bitvavo.markets(options={"market": "BTC-EUR"})

        assert isinstance(response, dict)

        # Assert that each market contains these keys
        assert "market" in response
        assert "status" in response
        assert "base" in response
        assert "quote" in response
        assert "pricePrecision" in response
        assert "minOrderInBaseAsset" in response
        assert "minOrderInQuoteAsset" in response
        assert "orderTypes" in response

        # Assert that each market contains these keys
        assert isinstance(response["market"], str)
        assert isinstance(response["status"], str)
        assert isinstance(response["base"], str)
        assert isinstance(response["quote"], str)
        assert isinstance(response["pricePrecision"], int)
        assert isinstance(response["minOrderInBaseAsset"], str)
        assert isinstance(response["minOrderInQuoteAsset"], str)
        assert isinstance(response["orderTypes"], list)

        # Assert that each market contains these keys
        assert response["status"] in ["trading", "halted", "auction"]
        assert float(response["minOrderInBaseAsset"]) >= 0
        assert float(response["minOrderInQuoteAsset"]) >= 0

    def test_assets(self, bitvavo: Bitvavo) -> None:
        response = bitvavo.assets(options={})
        assert isinstance(response, list)
        if len(response) > 0:
            assert isinstance(response[0], dict)

        # check all assets for the expected keys
        for asset in response:
            assert len(asset) == 11
            assert "symbol" in asset
            assert "name" in asset
            assert "decimals" in asset
            assert "depositFee" in asset
            assert "depositConfirmations" in asset
            assert "depositStatus" in asset
            assert "withdrawalFee" in asset
            assert "withdrawalMinAmount" in asset
            assert "withdrawalStatus" in asset
            assert "networks" in asset
            assert "message" in asset

        # check all assets for expected types
        for asset in response:
            assert isinstance(asset["symbol"], str)
            assert isinstance(asset["name"], str)
            assert isinstance(asset["decimals"], int)
            assert isinstance(
                asset["depositFee"],
                str,
            )  # this can also return a "none" string. That's why this isn't a number type
            assert isinstance(asset["depositConfirmations"], int)
            assert isinstance(asset["depositStatus"], str)
            assert isinstance(asset["withdrawalFee"], str)
            assert isinstance(asset["withdrawalMinAmount"], str)
            assert isinstance(asset["withdrawalStatus"], str)
            assert isinstance(asset["networks"], list)  # so far it's always a list of one string.
            assert isinstance(asset["message"], str)

    def test_book(self, bitvavo: Bitvavo) -> None:
        response = bitvavo.book(market="BTC-EUR", options={})

        assert isinstance(response, dict)

        assert len(response) == 5
        assert "market" in response
        assert "nonce" in response
        assert "asks" in response
        assert "bids" in response
        assert "timestamp" in response

        assert response["market"] == "BTC-EUR"

        assert isinstance(response["market"], str)
        assert isinstance(response["nonce"], int)  # not a value that should ever be 0
        assert isinstance(response["asks"], list)
        if len(response["asks"]) > 0:
            ask: list[str] = response["asks"][0]  # grab the 0th ask
            assert isinstance(ask, list)  # for some weird reason, asks and bids are lists
            assert isinstance(ask[0], str)
        assert isinstance(response["bids"], list)
        if len(response["bids"]) > 0:
            bid: list[str] = response["bids"][0]  # grab the 0th bid
            assert isinstance(bid, list)
            assert isinstance(bid[0], str)

        # check data conversion possibilities
        if len(response["asks"]) > 0:
            # first item in asks list is ALSO a list!
            ask: list[str] = response["asks"][0]  # grab the 0th ask
            assert int(ask[0]) >= 0, "zeroth item should be an int"
            assert float(ask[1]) >= 0, "oneth item should be a float"
        if len(response["bids"]) > 0:
            # first item in bids list is ALSO a list!
            bid: list[str] = response["bids"][0]  # grab the 0th bid
            assert int(bid[0]) >= 0, "zeroth item should be an int"
            assert float(bid[1]) >= 0, "oneth item should be a float"

    def test_public_trades(self, bitvavo: Bitvavo) -> None:
        response = bitvavo.public_trades(market="BTC-EUR", options={})

        assert isinstance(response, list)

        for public_trade in response:
            assert len(public_trade) == 5
            assert "id" in public_trade
            assert "timestamp" in public_trade
            assert "amount" in public_trade
            assert "price" in public_trade
            assert "side" in public_trade

        for public_trade in response:
            assert isinstance(public_trade["id"], str)
            assert isinstance(public_trade["timestamp"], int)
            assert isinstance(public_trade["amount"], str)
            assert isinstance(public_trade["price"], str)
            assert isinstance(public_trade["side"], str)

        for public_trade in response:
            # these are strings that can convert to another value
            assert float(public_trade["amount"]) >= 0
            assert float(public_trade["price"]) >= 0

    def test_candle(self, bitvavo: Bitvavo) -> None:
        """This is one of the weirder results: a list of lists"""
        # Timestamp: candle[0], open: candle[1], high: candle[2], low: candle[3], close: candle[4], volume: candle[5]
        response = bitvavo.candles(market="BTC-EUR", interval="1h", options={})
        for candle in response:
            assert len(candle) == 6
            assert isinstance(candle, list)
            assert isinstance(candle[0], int)  # timestamp
            assert isinstance(candle[1], str)  # open
            assert isinstance(candle[2], str)  # high
            assert isinstance(candle[3], str)  # low
            assert isinstance(candle[4], str)  # close
            assert isinstance(candle[5], str)  # volume

        for candle in response:
            assert int(candle[1]) >= 0  # open
            assert int(candle[2]) >= 0  # high
            assert int(candle[3]) >= 0  # low
            assert int(candle[4]) >= 0  # close
            assert float(candle[5]) >= 0  # volume

    @pytest.mark.skipif(True, reason="This test is not working as expected, needs to be fixed")
    def test_candle_with_options(self) -> None:
        """
        https://api.bitvavo.com/v2/AAVE-EUR/candles?interval=1m&limit=1440&start=1755759103631&end=1755759112502
        """
        bitvavo = Bitvavo(bitvavo_settings.model_dump())
        response = bitvavo.candles(
            market="AAVE-EUR",
            interval="1m",
            start=dt.datetime(2025, 8, 21, 6, 51, 43, 631544, tzinfo=dt.timezone.utc),
            end=dt.datetime(2025, 8, 21, 6, 51, 52, 502166, tzinfo=dt.timezone.utc),
            limit=1440,  # Max per request
        )
        if "errorCode" in response:
            assert response["errorCode"] == 203
            assert response["error"] == "symbol parameter is required."
            return

    def test_ticker_price_all(self, bitvavo: Bitvavo) -> None:
        """
        This is another one of those tests where the output is a bit of a mess.
        """
        response = bitvavo.ticker_price(options={})

        assert isinstance(response, list)

        # assert keys
        for ticker_price in response:
            assert len(ticker_price) == 2 or len(ticker_price) == 1
            assert "market" in ticker_price
            if len(ticker_price) == 2:
                assert "price" in ticker_price

        # assert types
        for ticker_price in response:
            assert isinstance(ticker_price["market"], str)
            if len(ticker_price) == 2:
                assert isinstance(ticker_price["price"], str)

    def test_ticker_price_single(self, bitvavo: Bitvavo) -> None:
        response = bitvavo.ticker_price(options={"market": "BTC-EUR"})

        assert isinstance(response, dict)

        # assert keys
        assert len(response) == 2
        assert "market" in response
        assert "price" in response

        # assert types
        assert isinstance(response["market"], str)
        assert isinstance(response["price"], str)

        # convertable types
        assert float(response["price"]) >= 0

    def test_ticker_book_all(self, bitvavo: Bitvavo) -> None:
        """
        Don't worry too much about the *-BTC markets, as they are not used (and thus not visible on the website)
        """
        response = bitvavo.ticker_book(options={})

        assert isinstance(response, list)

        # assert keys
        for ticker_book in response:
            # All non *-BTC markets should have 5 keys
            if not ticker_book["market"].endswith("BTC"):
                assert len(ticker_book) == 5
                assert "market" in ticker_book
                assert "bid" in ticker_book
                assert "ask" in ticker_book
                assert "bidSize" in ticker_book
                assert "askSize" in ticker_book
            else:
                assert len(ticker_book) == 5 or len(ticker_book) == 4
                assert "market" in ticker_book
                assert "bid" in ticker_book
                assert "ask" in ticker_book
                assert "askSize" in ticker_book

        # assert types
        for ticker_book in response:
            if not ticker_book["market"].endswith("BTC"):
                assert isinstance(ticker_book["market"], str)
                assert isinstance(ticker_book["bid"], str) or ticker_book["bid"] is None
                assert isinstance(ticker_book["ask"], str) or ticker_book["ask"] is None
                assert isinstance(ticker_book["bidSize"], str) or ticker_book["bidSize"] is None
                assert isinstance(ticker_book["askSize"], str) or ticker_book["askSize"] is None
            else:
                assert isinstance(ticker_book["market"], str)
                assert isinstance(ticker_book["ask"], str)
                assert isinstance(ticker_book["askSize"], str)

        # convertable types
        for ticker_book in response:
            if not ticker_book["market"].endswith("BTC"):
                assert float(ticker_book["bid"] if ticker_book["bid"] else 1) >= 0
                assert float(ticker_book["ask"] if ticker_book["ask"] else 1) >= 0
                assert float(ticker_book["bidSize"] if ticker_book["bidSize"] else 1) >= 0
                assert float(ticker_book["askSize"] if ticker_book["askSize"] else 1) >= 0
            else:
                assert float(ticker_book["ask"]) >= 0
                assert float(ticker_book["askSize"]) >= 0

    def test_ticker_book_single(self, bitvavo: Bitvavo) -> None:
        """
        Don't worry too much about the *-BTC markets, as they are not used (and thus not visible on the website)
        """
        response = bitvavo.ticker_book(options={"market": "BTC-EUR"})

        assert isinstance(response, dict)

        # assert keys
        # All non *-BTC markets should have 5 keys
        if not response["market"].endswith("BTC"):
            assert len(response) == 5
            assert "market" in response
            assert "bid" in response
            assert "ask" in response
            assert "bidSize" in response
            assert "askSize" in response
        else:
            assert len(response) == 5 or len(response) == 4
            assert "market" in response
            assert "bid" in response
            assert "ask" in response
            assert "askSize" in response

        # assert types
        if not response["market"].endswith("BTC"):
            assert isinstance(response["market"], str)
            assert isinstance(response["bid"], str)
            assert isinstance(response["ask"], str)
            assert isinstance(response["bidSize"], str)
            assert isinstance(response["askSize"], str)
        else:
            assert isinstance(response["market"], str)
            assert isinstance(response["ask"], str)
            assert isinstance(response["askSize"], str)

        # convertable types
        if not response["market"].endswith("BTC"):
            assert float(response["bid"]) >= 0
            assert float(response["ask"]) >= 0
            assert float(response["bidSize"]) >= 0
            assert float(response["askSize"]) >= 0
        else:
            assert float(response["ask"]) >= 0
            assert float(response["askSize"]) >= 0

    def test_ticker_24h_all(self, bitvavo: Bitvavo) -> None:  # noqa: C901, PLR0912, PLR0915
        """
        All this tests for is that the output from Bitvavo is a damned mess.
        """
        response = bitvavo.ticker24h(options={})

        assert isinstance(response, list)

        for ticker_24h in response:
            assert "market" in ticker_24h
            assert "open" in ticker_24h
            assert "high" in ticker_24h
            assert "low" in ticker_24h
            assert "last" in ticker_24h or "last" not in ticker_24h
            assert "volume" in ticker_24h
            assert "volumeQuote" in ticker_24h
            assert "bid" in ticker_24h
            assert "bidSize" in ticker_24h
            assert "ask" in ticker_24h
            assert "askSize" in ticker_24h
            assert "timestamp" in ticker_24h
            # these three were added late 2024
            assert "startTimestamp" in ticker_24h or "startTimestamp" not in ticker_24h
            assert "openTimestamp" in ticker_24h or "openTimestamp" not in ticker_24h
            assert "closeTimestamp" in ticker_24h or "closeTimestamp" not in ticker_24h

        for ticker_24h in response:
            # test all *-EUR markets (and any other non -BTC/-EUR markets that may be added in the future)
            if not ticker_24h["market"].endswith("BTC"):
                assert isinstance(ticker_24h["market"], str)
                assert isinstance(ticker_24h["open"], str) or ticker_24h["open"] is None
                assert isinstance(ticker_24h["high"], str) or ticker_24h["high"] is None
                assert isinstance(ticker_24h["low"], str) or ticker_24h["low"] is None
                if "last" in ticker_24h:
                    assert isinstance(ticker_24h["last"], str) or ticker_24h["last"] is None
                assert isinstance(ticker_24h["volume"], str) or ticker_24h["volume"] is None
                assert isinstance(ticker_24h["volumeQuote"], str) or ticker_24h["volumeQuote"] is None
                assert isinstance(ticker_24h["bid"], str) or ticker_24h["bid"] is None
                assert isinstance(ticker_24h["bidSize"], str) or ticker_24h["bidSize"] is None
                assert isinstance(ticker_24h["ask"], str) or ticker_24h["ask"] is None
                assert isinstance(ticker_24h["askSize"], str) or ticker_24h["askSize"] is None
                assert isinstance(ticker_24h["timestamp"], int)
                # these three were added late 2024
                if "startTimestamp" in ticker_24h:
                    assert isinstance(ticker_24h["startTimestamp"], int)
                if "openTimestamp" in ticker_24h:
                    assert isinstance(ticker_24h["openTimestamp"], int) or ticker_24h["openTimestamp"] is None
                if "closeTimestamp" in ticker_24h:
                    assert isinstance(ticker_24h["closeTimestamp"], int) or ticker_24h["openTimestamp"] is None

        for ticker_24h in response:
            # test unused -BTC markets
            if not ticker_24h["market"].endswith("BTC"):
                assert float(ticker_24h["open"] if ticker_24h["open"] else 1) >= 0  # else 1, because 1 is truthy
                assert float(ticker_24h["high"] if ticker_24h["high"] else 1) >= 0
                assert float(ticker_24h["low"] if ticker_24h["low"] else 1) >= 0
                if "last" in ticker_24h:
                    assert float(ticker_24h["last"] if ticker_24h["last"] else 1) >= 0
                assert float(ticker_24h["volume"] if ticker_24h["volume"] else 1) >= 0
                assert float(ticker_24h["volumeQuote"] if ticker_24h["volumeQuote"] else 1) >= 0
                assert float(ticker_24h["bid"] if ticker_24h["bid"] else 1) >= 0
                assert float(ticker_24h["bidSize"] if ticker_24h["bidSize"] else 1) >= 0
                assert float(ticker_24h["ask"] if ticker_24h["ask"] else 1) >= 0
                assert float(ticker_24h["askSize"] if ticker_24h["askSize"] else 1) >= 0
                assert int(ticker_24h["timestamp"])
                # these three were added late 2024
                if "startTimestamp" in ticker_24h:
                    assert ticker_24h["startTimestamp"] >= 0
                if "openTimestamp" in ticker_24h:
                    assert int(ticker_24h["openTimestamp"] if ticker_24h["volumeQuote"] else 1) >= 0
                if "closeTimestamp" in ticker_24h:
                    assert int(ticker_24h["closeTimestamp"] if ticker_24h["volumeQuote"] else 1) >= 0

    def test_ticker_24h_single(self, bitvavo: Bitvavo) -> None:
        response = bitvavo.ticker24h(options={"market": "BTC-EUR"})

        assert isinstance(response, dict)

        assert len(response) == 15
        assert "market" in response
        assert "open" in response
        assert "high" in response
        assert "low" in response
        assert "last" in response
        assert "volume" in response
        assert "volumeQuote" in response
        assert "bid" in response
        assert "bidSize" in response
        assert "ask" in response
        assert "askSize" in response
        assert "timestamp" in response
        assert "startTimestamp" in response
        assert "openTimestamp" in response
        assert "closeTimestamp" in response

        # test all *-EUR markets (and any other non -BTC/-EUR markets that may be added in the future)
        if not response["market"].endswith("BTC"):
            assert isinstance(response["market"], str)
            assert isinstance(response["open"], str) or response["open"] is None
            assert isinstance(response["high"], str) or response["high"] is None
            assert isinstance(response["low"], str) or response["low"] is None
            assert isinstance(response["last"], str) or response["last"] is None
            assert isinstance(response["volume"], str) or response["volume"] is None
            assert isinstance(response["volumeQuote"], str) or response["volumeQuote"] is None
            assert isinstance(response["bid"], str)
            assert isinstance(response["bidSize"], str)
            assert isinstance(response["ask"], str)
            assert isinstance(response["askSize"], str)
            assert isinstance(response["timestamp"], int)

        # test unused -BTC markets
        if not response["market"].endswith("BTC"):
            assert float(response["open"] if response["open"] else 1) >= 0  # else 1, because 1 is truthy
            assert float(response["high"] if response["high"] else 1) >= 0
            assert float(response["low"] if response["low"] else 1) >= 0
            assert float(response["last"] if response["last"] else 1) >= 0
            assert float(response["volume"] if response["volume"] else 1) >= 0
            assert float(response["volumeQuote"] if response["volumeQuote"] else 1) >= 0
            assert float(response["bid"]) >= 0
            assert float(response["bidSize"]) >= 0
            assert float(response["ask"]) >= 0
            assert float(response["askSize"]) >= 0
            assert int(response["timestamp"])

    @pytest.mark.skipif(True, reason="I'm not touching methods where I can accidentally sell all my shit")
    def test_place_order_buy(self, bitvavo: Bitvavo) -> None:
        response = bitvavo.place_order(
            market="BTC-EUR",
            side="buy",
            orderType="limit",
            body={"amount": "0.1", "price": "2000"},
            operatorId=12345,
        )
        print(json.dumps(response, indent=2))

    @pytest.mark.skipif(True, reason="I'm not touching methods where I can accidentally sell all my shit")
    def test_place_order_sell(self, bitvavo: Bitvavo) -> None:
        response = bitvavo.place_order(
            market="BTC-EUR",
            side="sell",
            orderType="stopLoss",
            body={
                "amount": "0.1",
                "triggerType": "price",
                "triggerReference": "lastTrade",
                "triggerAmount": "5000",
            },
            operatorId=12345,
        )
        print(json.dumps(response, indent=2))

    @pytest.mark.skipif(True, reason="This test is very sensitive to the data on the account, so I'm skipping it")
    def test_get_order(self, bitvavo: Bitvavo) -> None:
        response = bitvavo.get_order(market="BTC-EUR", orderId="dd055772-0f02-493c-a049-f4356fa0d221")

        assert isinstance(response, dict)  # errordict

        assert len(response) == 2
        assert "error" in response
        assert "errorCode" in response
        long_str = "No order found. Please be aware that simultaneously updating the same order may return this error."
        assert response["error"] == long_str
        assert response["errorCode"] == 240

    @pytest.mark.skipif(True, reason="This test is very sensitive to the data on the account, so I'm skipping it")
    def test_update_order(self, bitvavo: Bitvavo) -> None:
        response = bitvavo.update_order(
            market="BTC-EUR",
            orderId="dd055772-0f02-493c-a049-f4356fa0d221",
            body={"amount": "0.2"},
            operatorId=12345,
        )
        assert len(response) == 2
        assert "errorCode" in response
        assert "error" in response
        assert response["errorCode"] == 240
        assert (
            response["error"]
            == "No order found. Please be aware that simultaneously updating the same order may return this error."
        )

    @pytest.mark.skipif(True, reason="This test is very sensitive to the data on the account, so I'm skipping it")
    def test_cancel_order(self, bitvavo: Bitvavo) -> None:
        response = bitvavo.cancel_order(
            market="BTC-EUR",
            orderId="dd055772-0f02-493c-a049-f4356fa0d221",
            operatorId=12345,
        )
        assert len(response) == 2
        assert "errorCode" in response
        assert "error" in response
        assert response["errorCode"] == 240
        assert (
            response["error"]
            == "No order found. Please be aware that simultaneously updating the same order may return this error."
        )

    def test_get_orders(self, bitvavo: Bitvavo) -> None:
        response = bitvavo.get_orders(market="BTC-EUR", options={})
        assert response == []  # at least it's not an error or something

    @pytest.mark.skipif(True, reason="I'm not touching methods where I can accidentally cancel all my orders")
    def test_cancel_orders_all(self, bitvavo: Bitvavo) -> None:
        response = bitvavo.cancel_orders(options={})

        assert isinstance(response, dict)  # errordict

        assert "errorCode" in response
        assert "error" in response
        assert response["errorCode"] == 311
        assert response["error"] == "This key does not allowing showing account information."

    @pytest.mark.skipif(True, reason="I'm not touching methods where I can accidentally cancel all my orders")
    def test_cancel_orders_one_market(self, bitvavo: Bitvavo) -> None:
        response = bitvavo.cancel_orders(options={"market": "BTC-EUR"})

        assert isinstance(response, dict)  # errordict

        assert "errorCode" in response
        assert "error" in response
        assert response["errorCode"] == 311
        assert response["error"] == "This key does not allowing showing account information."

    def test_orders_open_list_all(self, bitvavo: Bitvavo) -> None:  # noqa: PLR0915
        response = bitvavo.orders_open(options={})

        if isinstance(response, list):
            for item in response:
                item: list[anydict] | anydict
                assert len(item) == 24
                assert "orderId" in item
                assert "market" in item
                assert "created" in item
                assert "updated" in item
                assert "status" in item
                assert "side" in item
                assert "orderType" in item
                assert "amount" in item
                assert "amountRemaining" in item
                assert "price" in item
                assert "onHold" in item
                assert "onHoldCurrency" in item
                assert "filledAmount" in item
                assert "filledAmountQuote" in item
                assert "feePaid" in item
                assert "feeCurrency" in item
                assert "fills" in item
                assert "selfTradePrevention" in item
                assert "visible" in item
                assert "timeInForce" in item
                assert "postOnly" in item
                assert "operatorId" in item
                assert "createdNs" in item
                assert "updatedNs" in item

            for item in response:
                assert isinstance(item["orderId"], str)
                assert isinstance(item["market"], str)
                assert isinstance(item["created"], int)
                assert isinstance(item["updated"], int)
                assert isinstance(item["status"], str)
                assert isinstance(item["side"], str)
                assert isinstance(item["orderType"], str)
                assert isinstance(item["amount"], str)
                assert isinstance(item["amountRemaining"], str)
                assert isinstance(item["price"], str)
                assert isinstance(item["onHold"], str)
                assert isinstance(item["onHoldCurrency"], str)
                assert isinstance(item["filledAmount"], str)
                assert isinstance(item["filledAmountQuote"], str)
                assert isinstance(item["feePaid"], str)
                assert isinstance(item["feeCurrency"], str)
                assert isinstance(item["fills"], list)
                assert isinstance(item["selfTradePrevention"], str)
                assert isinstance(item["visible"], bool)
                assert isinstance(item["timeInForce"], str)
                assert isinstance(item["postOnly"], bool)
                assert isinstance(item["operatorId"], int)
                assert isinstance(item["createdNs"], int)
                assert isinstance(item["updatedNs"], int)

            for item in response:
                assert item["status"] in ["new"]
                assert item["side"] in ["sell", "buy"]
                assert item["orderType"] in ["limit"]
                assert float(item["amount"]) >= 0
                assert float(item["amountRemaining"]) >= 0
                assert float(item["price"]) >= 0
                assert float(item["onHold"]) >= 0
                assert float(item["filledAmount"]) >= 0
                assert float(item["filledAmountQuote"]) >= 0
                assert float(item["feePaid"]) >= 0
                assert item["selfTradePrevention"] in ["decrementAndCancel"]
                assert item["timeInForce"] in ["GTC"]

    def test_orders_open_list_single(self, bitvavo: Bitvavo) -> None:  # noqa: PLR0915
        response = bitvavo.orders_open(options={"market": "DIA-EUR"})

        if isinstance(response, list):
            for item in response:
                item: list[anydict] | anydict
                assert len(item) == 24
                assert "orderId" in item
                assert "market" in item
                assert "created" in item
                assert "updated" in item
                assert "status" in item
                assert "side" in item
                assert "orderType" in item
                assert "amount" in item
                assert "amountRemaining" in item
                assert "price" in item
                assert "onHold" in item
                assert "onHoldCurrency" in item
                assert "filledAmount" in item
                assert "filledAmountQuote" in item
                assert "feePaid" in item
                assert "feeCurrency" in item
                assert "fills" in item
                assert "selfTradePrevention" in item
                assert "visible" in item
                assert "timeInForce" in item
                assert "postOnly" in item
                assert "operatorId" in item
                assert "createdNs" in item
                assert "updatedNs" in item

            for item in response:
                assert isinstance(item["orderId"], str)
                assert isinstance(item["market"], str)
                assert isinstance(item["created"], int)
                assert isinstance(item["updated"], int)
                assert isinstance(item["status"], str)
                assert isinstance(item["side"], str)
                assert isinstance(item["orderType"], str)
                assert isinstance(item["amount"], str)
                assert isinstance(item["amountRemaining"], str)
                assert isinstance(item["price"], str)
                assert isinstance(item["onHold"], str)
                assert isinstance(item["onHoldCurrency"], str)
                assert isinstance(item["filledAmount"], str)
                assert isinstance(item["filledAmountQuote"], str)
                assert isinstance(item["feePaid"], str)
                assert isinstance(item["feeCurrency"], str)
                assert isinstance(item["fills"], list)
                assert isinstance(item["selfTradePrevention"], str)
                assert isinstance(item["visible"], bool)
                assert isinstance(item["timeInForce"], str)
                assert isinstance(item["postOnly"], bool)
                assert isinstance(item["operatorId"], int)
                assert isinstance(item["createdNs"], int)
                assert isinstance(item["updatedNs"], int)

            for item in response:
                assert item["status"] in ["new"]
                assert item["side"] in ["sell", "buy"]
                assert item["orderType"] in ["limit"]
                assert float(item["amount"]) >= 0
                assert float(item["amountRemaining"]) >= 0
                assert float(item["price"]) >= 0
                assert float(item["onHold"]) >= 0
                assert float(item["filledAmount"]) >= 0
                assert float(item["filledAmountQuote"]) >= 0
                assert float(item["feePaid"]) >= 0
                assert item["selfTradePrevention"] in ["decrementAndCancel"]
                assert item["timeInForce"] in ["GTC"]

    def test_trades(self, bitvavo: Bitvavo) -> None:
        response = bitvavo.trades(market="BTC-EUR", options={})
        assert response == []

    def test_account(self, bitvavo: Bitvavo) -> None:
        response = bitvavo.account()

        assert len(response) == 2
        assert "fees" in response
        assert "capabilities" in response

        assert isinstance(response["fees"], dict)
        assert isinstance(response["capabilities"], list)

        assert len(response["fees"]) == 4
        assert "tier" in response["fees"]
        assert "volume" in response["fees"]
        assert "maker" in response["fees"]
        assert "taker" in response["fees"]
        assert float(response["fees"]["tier"]) >= 0
        assert float(response["fees"]["volume"]) >= 0
        assert float(response["fees"]["maker"]) >= 0
        assert float(response["fees"]["taker"]) >= 0

        assert len(response["capabilities"]) == 6
        assert response["capabilities"] == [
            "buy",
            "sell",
            "depositCrypto",
            "depositFiat",
            "withdrawCrypto",
            "withdrawFiat",
        ]

    def test_fees(self, bitvavo: Bitvavo) -> None:
        response = bitvavo.fees()

        assert isinstance(response, dict)

        assert len(response) == 4
        assert "tier" in response
        assert "volume" in response
        assert "maker" in response
        assert "taker" in response

        assert isinstance(response["tier"], int)
        assert isinstance(response["volume"], str)
        assert isinstance(response["maker"], str)
        assert isinstance(response["taker"], str)

        assert float(response["volume"]) >= 0
        assert float(response["maker"]) >= 0
        assert float(response["taker"]) >= 0

    def test_fees_with_market(self, bitvavo: Bitvavo) -> None:
        response = bitvavo.fees(market="BTC-EUR")

        assert isinstance(response, dict)

        assert len(response) == 4
        assert "tier" in response
        assert "volume" in response
        assert "maker" in response
        assert "taker" in response

        assert isinstance(response["tier"], int)
        assert isinstance(response["volume"], str)
        assert isinstance(response["maker"], str)
        assert isinstance(response["taker"], str)

        assert float(response["volume"]) >= 0
        assert float(response["maker"]) >= 0
        assert float(response["taker"]) >= 0

    def test_fees_with_quote(self, bitvavo: Bitvavo) -> None:
        response = bitvavo.fees(quote="EUR")

        assert isinstance(response, dict)

        assert len(response) == 4
        assert "tier" in response
        assert "volume" in response
        assert "maker" in response
        assert "taker" in response

        assert isinstance(response["tier"], int)
        assert isinstance(response["volume"], str)
        assert isinstance(response["maker"], str)
        assert isinstance(response["taker"], str)

        assert float(response["volume"]) >= 0
        assert float(response["maker"]) >= 0
        assert float(response["taker"]) >= 0

    def test_balance_all(self, bitvavo: Bitvavo) -> None:
        response = bitvavo.balance(options={})

        assert isinstance(response, list)

        for item in response:
            assert len(item) == 3
            assert "symbol" in item
            assert "available" in item
            assert "inOrder" in item

        for item in response:
            assert isinstance(item["symbol"], str)
            assert isinstance(item["available"], str)
            assert isinstance(item["inOrder"], str)

        for item in response:
            assert float(item["available"]) >= 0
            assert float(item["inOrder"]) >= 0

    def test_balance_single(self, bitvavo: Bitvavo) -> None:
        """
        `balance()` is weird, as even if you return only one item, you still get it in a list, when the other methods
        would only return a single item. So yeah, this is the only `_single` method that gets a list, with one item...
        """
        # change this symbol if you don't have any SHIB and this test fails
        response = bitvavo.balance(options={"symbol": "SHIB"})

        assert isinstance(response, list)

        # even when requesting a single item/symbol, it still returns a list, but with only one item
        assert len(response) == 1

        item = response[0]
        assert len(item) == 3
        assert "symbol" in item
        assert "available" in item
        assert "inOrder" in item

        assert isinstance(item["symbol"], str)
        assert isinstance(item["available"], str)
        assert isinstance(item["inOrder"], str)

        assert float(item["available"]) >= 0
        assert float(item["inOrder"]) >= 0

    def test_deposit_assets_coin(self, bitvavo: Bitvavo) -> None:
        response = bitvavo.deposit_assets("BTC")

        assert isinstance(response, dict)

        assert "address" in response
        assert isinstance(response["address"], str)

    def test_deposit_assets_token(self, bitvavo: Bitvavo) -> None:
        response = bitvavo.deposit_assets("SHIB")

        assert isinstance(response, dict)

        assert "address" in response
        assert isinstance(response["address"], str)
        assert response["address"].startswith("0x")  # only counts for SHIB (?)

    @pytest.mark.skipif(
        True,
        reason="{'errorCode': 400, 'error': 'Unknown error. Please contact support with a copy of your request.'}",
    )
    def test_deposit_assets_fiat(self, bitvavo: Bitvavo) -> None:
        """
        2024-11-11: This functionality seems to have changed completely?
        """
        # This should be Bitvavo's EUR address, not a personal one
        response = bitvavo.deposit_assets("EUR")

        assert isinstance(response, dict)

        assert "iban" in response
        assert "bic" in response
        assert "description" in response
        assert "qr" in response

        assert isinstance(response["iban"], str)
        assert isinstance(response["bic"], str)
        assert isinstance(response["description"], str)
        assert isinstance(response["qr"], str)

        assert response["qr"].startswith("data:image/png;base64,")

    def test_withdraw_assets(self, bitvavo: Bitvavo) -> None:
        """
        2024-11-11: test later with different key
        """
        # Keep `bitcoin_address` fake or non-existant, otherwise you're passing
        # money around when testing...
        bitcoin_address = "SomeBitcoinAddress"
        response = bitvavo.withdraw_assets("BTC", "1", bitcoin_address, {})

        assert "errorCode" in response
        assert "error" in response

        assert response["errorCode"] == 312
        assert response["error"] == "This key does not allowing withdrawal of funds."

    def test_deposit_history_all(self, bitvavo: Bitvavo) -> None:
        response = bitvavo.deposit_history(options={})

        assert isinstance(response, list)

        for item in response:
            assert "timestamp" in item
            assert "symbol" in item
            assert "amount" in item
            assert "fee" in item
            assert "status" in item
            assert "address" in item or "txId" in item

        for item in response:
            assert isinstance(item["timestamp"], int)
            assert isinstance(item["symbol"], str)
            assert isinstance(item["amount"], str)
            assert isinstance(item["fee"], str)
            assert isinstance(item["status"], str)
            if "address" in item:
                assert isinstance(item["address"], str)
            if "txId" in item:
                assert isinstance(item["txId"], str)

        for item in response:
            assert float(item["amount"]) >= 0
            assert float(item["fee"]) >= 0

    def test_deposit_history_single(self, bitvavo: Bitvavo) -> None:
        """
        Note That you'll still receive multiple results, as "symbol" is not unique within the deposit history.
        """
        # if this test fails, make sure you have EUR in your deposit history.
        # Debug the _all variant, with a breakpoint or `raise
        # ValueError(response)`, to see what you do have EUR (if any).
        response = bitvavo.deposit_history(options={"symbol": "EUR"})

        assert isinstance(response, list)

        # I had at least 5 EUR transfers on my account. This is not a special
        # number or anything ;)
        assert len(response) >= 5

        for item in response:
            assert "timestamp" in item
            assert "symbol" in item
            assert "amount" in item
            assert "fee" in item
            assert "status" in item
            assert "address" in item or "txId" in item

        for item in response:
            assert isinstance(item["timestamp"], int)
            assert isinstance(item["symbol"], str)
            assert isinstance(item["amount"], str)
            assert isinstance(item["fee"], str)
            assert isinstance(item["status"], str)
            if "address" in item:
                assert isinstance(item["address"], str)
            if "txId" in item:
                assert isinstance(item["txId"], str)

        for item in response:
            assert float(item["amount"]) >= 0
            assert float(item["fee"]) >= 0

    def test_withdrawal_history_all(self, bitvavo: Bitvavo) -> None:
        response = bitvavo.withdrawal_history(options={})
        assert isinstance(response, list)
        for item in response:
            if len(item) >= 6:
                assert "timestamp" in item
                assert "symbol" in item
                assert "amount" in item
                assert "address" in item
                assert "fee" in item
                assert "status" in item
            if len(item) == 7:
                assert "txId" in item

        for item in response:
            if len(item) >= 6:
                assert isinstance(item["timestamp"], int)
                assert isinstance(item["symbol"], str)
                assert isinstance(item["amount"], str)
                assert isinstance(item["address"], str)
                assert isinstance(item["fee"], str)
                assert isinstance(item["status"], str)
            if len(item) == 7:
                assert isinstance(item["txId"], str)

        for item in response:
            assert float(item["amount"]) >= 0
            assert float(item["fee"]) >= 0
            assert item["status"] in [
                "awaiting_processing",
                "awaiting_email_confirmation",
                "awaiting_bitvavo_inspection",
                "approved",
                "sending",
                "in_mempool",
                "processed",
                "completed",
                "canceled",
            ]  # from docs.bitvavo.com (hidden under "200 successful operation")

    def test_withdrawal_history_single(self, bitvavo: Bitvavo) -> None:
        response = bitvavo.withdrawal_history(options={"symbol": "SHIB"})
        assert isinstance(response, list)
        for item in response:
            assert "timestamp" in item
            assert "symbol" in item
            assert "amount" in item
            assert "address" in item
            assert "txId" in item
            assert "fee" in item
            assert "status" in item

        for item in response:
            assert isinstance(item["timestamp"], int)
            assert isinstance(item["symbol"], str)
            assert isinstance(item["amount"], str)
            assert isinstance(item["address"], str)
            assert isinstance(item["txId"], str)
            assert isinstance(item["fee"], str)
            assert isinstance(item["status"], str)

        for item in response:
            assert float(item["amount"]) >= 0
            assert float(item["fee"]) >= 0
            assert item["status"] in [
                "completed",
                "awaiting_processing",
            ]

    def test_account_history(self, bitvavo: Bitvavo) -> None:
        """Test the new accountHistory method for MiCA compliance."""
        response = bitvavo.account_history(options={})

        # Should return a list or an error dict
        assert isinstance(response, (list, dict))

        # If it's an error (likely due to permissions), check error structure
        if isinstance(response, dict) and "errorCode" in response:
            assert "error" in response
            assert isinstance(response["errorCode"], int)
            assert isinstance(response["error"], str)
        # If it's successful, check the list structure
        elif isinstance(response, list):
            for item in response:
                # Based on API docs, should have these fields
                assert isinstance(item, dict)
                # Can't assert specific fields without knowing the exact response structure

    def test_report_trades(self, bitvavo: Bitvavo) -> None:
        """Test the new reportTrades method for MiCA compliance."""
        # Using a date range that shouldn't have any trades
        response = bitvavo.report_trades(
            market="BTC-EUR",
            options={
                "startDate": "2020-01-01T00:00:00.000Z",
                "endDate": "2020-01-02T00:00:00.000Z",
            },
        )

        # Should return a list or an error dict
        assert isinstance(response, (list, dict))

        # If it's an error (likely due to permissions), check error structure
        if isinstance(response, dict) and "errorCode" in response:
            assert "error" in response
            assert isinstance(response["errorCode"], int)
            assert isinstance(response["error"], str)
        # If it's successful, check the list structure
        elif isinstance(response, list):
            for item in response:
                assert isinstance(item, dict)

    def test_report_book(self, bitvavo: Bitvavo) -> None:
        """Test the new reportBook method for MiCA compliance."""
        # Using a date range that shouldn't have any book changes
        response = bitvavo.report_book(
            market="BTC-EUR",
            options={
                "startDate": "2020-01-01T00:00:00.000Z",
                "endDate": "2020-01-02T00:00:00.000Z",
            },
        )

        # Should return a dict or an error dict
        assert isinstance(response, dict)

        # If it's an error (likely due to permissions), check error structure
        if "errorCode" in response:
            assert "error" in response
            assert isinstance(response["errorCode"], int)
            assert isinstance(response["error"], str)
        else:
            # If it's successful, should be a report response
            assert isinstance(response, dict)


# Normally you would define a separate callback for every function.
def generic_callback(response: Any | errordict) -> None:
    """The `Any` type is when the server successfully returns data.

    That's usually either a `dict`, `list[dict]`, or `list[list[str]]` type.
    Check the return type of the function you're using to see what you may expect.

    ---
    The `anydict` type is when the API returns an error object from the server side.

    That error object always looks something like:
    ```python
    # see also `test_no_error()`
    {
        "errorCode": 110,
        "error": "Invalid endpoint. Please check url and HTTP method."
    }
    ```
    """
    print(f"generic_callback: {json.dumps(response, indent=2)}")


@pytest.mark.skip(reason="broken; code seems to freeze when calling the API.")
class TestWebsocket:
    """
    Since this method has to take another Python Thread into account, we'll check output and such via caplog and capsys.
    I'll be honest: I have no idea when one or the other is used, so I included them both, in case I ever change some
    setting that is going to switch the outputs or something (right now, capsys is used most often).

    This is also due to experience in another project, where sometimes caplog, sometimes capsys and sometimes both were
    used, depending on the settings of the logger (structlog, in that case). I'm using the regular logging for now, for
    this project, to keep dependencies at a minimum.

    Yes, these are kinda badly tested, but I've used the websocket for a bit and all I got was pain.
    Having to use `sleep()` after calls in the *hope* that data got ingested in time, and errors being thrown by the
    websocket and being silently dropped due to unknown reasons (probably because the logs are created by a separate thread).

    My recommendation is to stick to using the regular Bitvavo object and ignore the websocket, unless you have a ton
    of experience and *need* to use a websocket for your use case :)
    """  # noqa: E501

    def wait(self) -> None:
        """
        Helper method that you must run after making a websocket call.
        This method waits for some time in the hopes that the websocket is done within that time.
        If you do not have this waiting time, the logs won't print because those are created by a separate thread,
        which would not be able to actually print the logs, because the main thread will be done running before receiving the logs.
        """  # noqa: E501
        # If all websocket tests fail, just up this number
        sleep(1)


class TestWebSocketAppFacadeInit:
    """Tests for WebSocketAppFacade initialization that are safe to run without actual WebSocket connections."""

    def wait(self) -> None:
        """
        Helper method that you must run after making a websocket call.
        This method waits for some time in the hopes that the websocket is done within that time.
        If you do not have this waiting time, the logs won't print because those are created by a separate thread,
        which would not be able to actually print the logs, because the main thread will be done running before receiving the logs.
        """  # noqa: E501
        # If all websocket tests fail, just up this number
        sleep(0.5)

    def test_websocket_app_facade_init(self) -> None:
        """Test the WebSocketAppFacade.__init__ method initialization.

        This test verifies that all attributes are properly set during initialization
        and that the subscribe method is called to set up the WebSocket connection.
        """
        # Create a mock Bitvavo instance
        mock_bitvavo = MagicMock(spec=Bitvavo)
        mock_bitvavo.debugging = False

        # Mock WebSocketApp and ReceiveThread to avoid actual network operations
        with (
            patch("bitvavo_api_upgraded.bitvavo.WebSocketApp") as mock_ws_app,
            patch("bitvavo_api_upgraded.bitvavo.ReceiveThread") as mock_receive_thread,
            patch("bitvavo_api_upgraded.bitvavo.ws_lib.enableTrace") as mock_enable_trace,
        ):
            # Configure mock objects
            mock_ws_instance = MagicMock()
            mock_ws_app.return_value = mock_ws_instance

            mock_thread_instance = MagicMock()
            mock_receive_thread.return_value = mock_thread_instance

            # Test parameters
            api_key = "test_api_key"
            api_secret = "test_api_secret"  # Test data, not actual secret
            access_window = 10000
            ws_url = "wss://ws.bitvavo.com/v2/"

            # Create WebSocketAppFacade instance
            facade = Bitvavo.WebSocketAppFacade(
                APIKEY=api_key,
                APISECRET=api_secret,
                ACCESSWINDOW=access_window,
                WSURL=ws_url,
                bitvavo=mock_bitvavo,
            )

            # Verify instance attributes are set correctly
            assert api_key == facade.APIKEY
            assert api_secret == facade.APISECRET
            assert access_window == facade.ACCESSWINDOW
            assert ws_url == facade.WSURL
            assert mock_bitvavo is facade.bitvavo

            # Verify initial state attributes
            assert facade.open is False
            assert isinstance(facade.callbacks, dict)
            assert len(facade.callbacks) == 0
            assert facade.keepAlive is True
            assert facade.reconnect is False
            assert facade.reconnectTimer == 0.1

            # Verify subscribe() was called and set up WebSocket correctly
            mock_enable_trace.assert_called_once_with(False)
            mock_ws_app.assert_called_once_with(
                ws_url,
                on_message=facade.on_message,
                on_error=facade.on_error,
                on_close=facade.on_close,
                on_open=facade.on_open,
            )

            # Verify WebSocketApp instance is stored
            assert mock_ws_instance is facade.ws

            # Verify ReceiveThread is created and configured
            mock_receive_thread.assert_called_once_with(mock_ws_instance, facade)
            assert mock_thread_instance is facade.receiveThread
            mock_thread_instance.start.assert_called_once()
            assert mock_thread_instance.daemon is True

            # Verify WebSocket state attributes from subscribe()
            assert facade.authenticated is False
            assert facade.keepBookCopy is False
            assert isinstance(facade.localBook, dict)
            assert len(facade.localBook) == 0

    def test_set_error_callback(self, websocket: Bitvavo.WebSocketAppFacade) -> None:
        websocket.set_error_callback(error_callback_example)

        assert "error" in websocket.callbacks
        assert websocket.callbacks["error"] == error_callback_example

    def test_time(
        self,
        caplog: pytest.LogCaptureFixture,
        capsys: pytest.CaptureFixture[str],
        websocket: Bitvavo.WebSocketAppFacade,
    ) -> None:
        print("error")
        websocket.time(generic_callback)
        self.wait()
        assert caplog.text == ""
        stdout, stderr = capsys.readouterr()
        assert 'generic_callback: {\n  "time":' in stdout
        assert stderr == ""

    def test_markets(
        self,
        caplog: pytest.LogCaptureFixture,
        capsys: pytest.CaptureFixture[str],
        websocket: Bitvavo.WebSocketAppFacade,
    ) -> None:
        websocket.markets(options={"market": "BTC-EUR"}, callback=generic_callback)
        self.wait()

        assert caplog.text == ""
        stdout, stderr = capsys.readouterr()
        assert stderr == ""
        assert 'generic_callback: {\n  "market": "BTC-EUR",\n  "status": "trading"' in stdout

    def test_assets(
        self,
        caplog: pytest.LogCaptureFixture,
        capsys: pytest.CaptureFixture[str],
        websocket: Bitvavo.WebSocketAppFacade,
    ) -> None:
        websocket.assets(options={}, callback=generic_callback)
        self.wait()

        assert caplog.text == ""
        stdout, stderr = capsys.readouterr()
        assert stderr == ""
        assert 'generic_callback: [\n  {\n    "symbol": "1INCH",\n    "name": "1inch"' in stdout

    def test_book(
        self,
        caplog: pytest.LogCaptureFixture,
        capsys: pytest.CaptureFixture[str],
        websocket: Bitvavo.WebSocketAppFacade,
    ) -> None:
        websocket.book(market="BTC-EUR", options={}, callback=generic_callback)
        self.wait()
        self.wait()  # slower function; needs a bit more time

        assert caplog.text == ""
        stdout, stderr = capsys.readouterr()
        assert stderr == ""
        assert 'generic_callback: {\n  "market": "BTC-EUR",\n  "nonce":' in stdout

    def test_public_trades(
        self,
        caplog: pytest.LogCaptureFixture,
        capsys: pytest.CaptureFixture[str],
        websocket: Bitvavo.WebSocketAppFacade,
    ) -> None:
        websocket.publicTrades(market="BTC-EUR", options={}, callback=generic_callback)
        self.wait()

        assert caplog.text == ""
        stdout, stderr = capsys.readouterr()
        assert stderr == ""
        assert 'generic_callback: [\n  {\n    "id": "' in stdout

    def test_candles(
        self,
        caplog: pytest.LogCaptureFixture,
        capsys: pytest.CaptureFixture[str],
        websocket: Bitvavo.WebSocketAppFacade,
    ) -> None:
        websocket.candles(market="BTC-EUR", interval="1h", options={}, callback=generic_callback)
        self.wait()

        assert caplog.text == ""
        stdout, stderr = capsys.readouterr()
        assert stderr == ""
        assert "generic_callback: [\n  [\n    " in stdout

    def test_ticker_24h(
        self,
        caplog: pytest.LogCaptureFixture,
        capsys: pytest.CaptureFixture[str],
        websocket: Bitvavo.WebSocketAppFacade,
    ) -> None:
        websocket.ticker24h(options={}, callback=generic_callback)
        self.wait()

        assert caplog.text == ""
        stdout, stderr = capsys.readouterr()
        assert stderr == ""
        assert 'generic_callback: [\n  {\n    "market": "1INCH-EUR",\n    "startTimestamp":' in stdout

    def test_ticker_price(
        self,
        caplog: pytest.LogCaptureFixture,
        capsys: pytest.CaptureFixture[str],
        websocket: Bitvavo.WebSocketAppFacade,
    ) -> None:
        websocket.ticker_price(options={}, callback=generic_callback)
        self.wait()

        assert caplog.text == ""
        stdout, stderr = capsys.readouterr()
        assert stderr == ""
        assert 'generic_callback: [\n  {\n    "market": "1INCH-EUR",\n    "price": ' in stdout

    def test_ticker_book(
        self,
        caplog: pytest.LogCaptureFixture,
        capsys: pytest.CaptureFixture[str],
        websocket: Bitvavo.WebSocketAppFacade,
    ) -> None:
        websocket.ticker_book(options={}, callback=generic_callback)
        self.wait()

        assert caplog.text == ""
        stdout, stderr = capsys.readouterr()
        assert stderr == ""
        assert 'generic_callback: [\n  {\n    "market": "1INCH-EUR",\n    "bid": ' in stdout

    @pytest.mark.skipif(True, reason="I'm not touching methods where I can accidentally sell all my shit")
    def test_place_order(
        self,
        caplog: pytest.LogCaptureFixture,
        capsys: pytest.CaptureFixture[str],
        websocket: Bitvavo.WebSocketAppFacade,
    ) -> None:
        websocket.place_order(
            market="BTC-EUR",
            side="buy",
            orderType="limit",
            body={"amount": "1", "price": "3000"},
            operatorId=12345,
            callback=generic_callback,
        )

    @pytest.mark.skipif(True, reason="This test is very sensitive to the data on the account, so I'm skipping it")
    def test_get_order(
        self,
        caplog: pytest.LogCaptureFixture,
        capsys: pytest.CaptureFixture[str],
        websocket: Bitvavo.WebSocketAppFacade,
    ) -> None:
        websocket.get_order(
            market="BTC-EUR",
            orderId="6d0dffa7-07fe-448e-9928-233821e7cdb5",
            callback=generic_callback,
        )
        self.wait()

        assert "'errorCode': 240" in caplog.text
        assert (
            "'error': 'No order found. Please be aware that simultaneously updating"
            " the same order may return this error.'"
        ) in caplog.text
        stdout, stderr = capsys.readouterr()
        assert stderr == ""
        assert stdout == ""

    @pytest.mark.skipif(True, reason="I'm not touching methods where I can accidentally sell all my shit")
    def test_update_order(
        self,
        caplog: pytest.LogCaptureFixture,
        capsys: pytest.CaptureFixture[str],
        websocket: Bitvavo.WebSocketAppFacade,
    ) -> None:
        websocket.update_order(
            market="BTC-EUR",
            orderId="6d0dffa7-07fe-448e-9928-233821e7cdb5",
            body={"amount": "1.1"},
            operatorId=12345,
            callback=generic_callback,
        )

    @pytest.mark.skipif(True, reason="I'm not touching methods where I can accidentally sell all my shit")
    def test_cancel_order(
        self,
        caplog: pytest.LogCaptureFixture,
        capsys: pytest.CaptureFixture[str],
        websocket: Bitvavo.WebSocketAppFacade,
    ) -> None:
        websocket.cancel_order(
            market="BTC-EUR",
            orderId="6d0dffa7-07fe-448e-9928-233821e7cdb5",
            operatorId=12345,
            callback=generic_callback,
        )

    def test_get_orders(
        self,
        caplog: pytest.LogCaptureFixture,
        capsys: pytest.CaptureFixture[str],
        websocket: Bitvavo.WebSocketAppFacade,
    ) -> None:
        websocket.get_orders(market="BTC-EUR", options={}, callback=generic_callback)
        self.wait()

        assert caplog.text == ""
        stdout, stderr = capsys.readouterr()
        assert stderr == ""
        assert "generic_callback: []\n" in stdout

    @pytest.mark.skipif(True, reason="I'm not touching methods where I can accidentally sell all my shit")
    def test_cancel_orders(
        self,
        caplog: pytest.LogCaptureFixture,
        capsys: pytest.CaptureFixture[str],
        websocket: Bitvavo.WebSocketAppFacade,
    ) -> None:
        websocket.cancel_orders(options={"market": "BTC-EUR"}, callback=generic_callback)

    def test_orders_open(
        self,
        caplog: pytest.LogCaptureFixture,
        capsys: pytest.CaptureFixture[str],
        websocket: Bitvavo.WebSocketAppFacade,
    ) -> None:
        websocket.orders_open(options={}, callback=generic_callback)
        self.wait()

        assert caplog.text == ""
        stdout, stderr = capsys.readouterr()
        assert stderr == ""
        assert 'generic_callback: [\n  {\n    "orderId": ' in stdout

    def test_trades(
        self,
        caplog: pytest.LogCaptureFixture,
        capsys: pytest.CaptureFixture[str],
        websocket: Bitvavo.WebSocketAppFacade,
    ) -> None:
        websocket.trades(market="BTC-EUR", options={}, callback=generic_callback)
        self.wait()

        assert caplog.text == ""
        stdout, stderr = capsys.readouterr()
        assert stderr == ""
        assert "generic_callback: []\n" in stdout

    def test_account(
        self,
        caplog: pytest.LogCaptureFixture,
        capsys: pytest.CaptureFixture[str],
        websocket: Bitvavo.WebSocketAppFacade,
    ) -> None:
        websocket.account(callback=generic_callback)
        self.wait()

        assert caplog.text == ""
        stdout, stderr = capsys.readouterr()
        assert stderr == ""
        assert 'generic_callback: {\n  "fees": {\n    "tier": 0,\n   ' in stdout

    def test_balance(
        self,
        caplog: pytest.LogCaptureFixture,
        capsys: pytest.CaptureFixture[str],
        websocket: Bitvavo.WebSocketAppFacade,
    ) -> None:
        websocket.balance(options={}, callback=generic_callback)
        self.wait()

        assert caplog.text == ""
        stdout, stderr = capsys.readouterr()
        assert stderr == ""
        assert 'generic_callback: [\n  {\n    "symbol": ' in stdout

    @pytest.mark.skipif(True, reason="I'm not touching methods where I can accidentally sell all my shit")
    def test_deposit_assets(
        self,
        caplog: pytest.LogCaptureFixture,
        capsys: pytest.CaptureFixture[str],
        websocket: Bitvavo.WebSocketAppFacade,
    ) -> None:
        websocket.deposit_assets("BTC", callback=generic_callback)

    @pytest.mark.skipif(True, reason="I'm not touching methods where I can accidentally sell all my shit")
    def test_withdraw_assets(
        self,
        caplog: pytest.LogCaptureFixture,
        capsys: pytest.CaptureFixture[str],
        websocket: Bitvavo.WebSocketAppFacade,
    ) -> None:
        websocket.withdraw_assets(
            symbol="BTC",
            amount="1",
            address="BitcoinAddress",
            body={},
            callback=generic_callback,
        )

    def test_deposit_history(
        self,
        caplog: pytest.LogCaptureFixture,
        capsys: pytest.CaptureFixture[str],
        websocket: Bitvavo.WebSocketAppFacade,
    ) -> None:
        websocket.deposit_history(options={}, callback=generic_callback)
        self.wait()

        assert caplog.text == ""
        stdout, stderr = capsys.readouterr()
        assert stderr == ""
        assert 'generic_callback: [\n  {\n    "timestamp": ' in stdout

    def test_withdrawal_history(
        self,
        caplog: pytest.LogCaptureFixture,
        capsys: pytest.CaptureFixture[str],
        websocket: Bitvavo.WebSocketAppFacade,
    ) -> None:
        websocket.withdrawal_history(options={}, callback=generic_callback)
        self.wait()

        assert caplog.text == ""
        stdout, stderr = capsys.readouterr()
        assert stderr == ""
        assert 'generic_callback: [\n  {\n    "timestamp":' in stdout

    @pytest.mark.skipif(True, reason="It's really hard to test a method that may or may not return data")
    def test_subscription_ticker(
        self,
        caplog: pytest.LogCaptureFixture,
        capsys: pytest.CaptureFixture[str],
        websocket: Bitvavo.WebSocketAppFacade,
    ) -> None:
        websocket.subscription_ticker(market="BTC-EUR", callback=generic_callback)
        self.wait()
        self.wait()
        self.wait()

        assert caplog.text == ""
        stdout, stderr = capsys.readouterr()
        assert stderr == ""
        assert 'generic_callback: {\n  "event": "ticker",\n  "market": "BTC-EUR",\n  "bestAsk": ' in stdout

    @pytest.mark.skipif(True, reason="It's really hard to test a method that may or may not return data")
    def test_subscription_ticker_24h(
        self,
        caplog: pytest.LogCaptureFixture,
        capsys: pytest.CaptureFixture[str],
        websocket: Bitvavo.WebSocketAppFacade,
    ) -> None:
        websocket.subscription_ticker24h(market="BTC-EUR", callback=generic_callback)
        self.wait()
        self.wait()
        self.wait()

        assert caplog.text == ""
        stdout, stderr = capsys.readouterr()
        assert stderr == ""
        assert 'generic_callback: {\n  "market": "BTC-EUR",\n  "open": "' in stdout

    @pytest.mark.skipif(True, reason="It's really hard to test a method that may or may not return data")
    def test_subscription_ticker_account(
        self,
        caplog: pytest.LogCaptureFixture,
        capsys: pytest.CaptureFixture[str],
        websocket: Bitvavo.WebSocketAppFacade,
    ) -> None:
        websocket.subscription_account(market="BTC-EUR", callback=generic_callback)
        self.wait()
        self.wait()
        self.wait()

        assert caplog.text == ""
        stdout, stderr = capsys.readouterr()
        assert stderr == ""
        assert "" in stdout  # no output found manually ;_;

    @pytest.mark.skipif(True, reason="It's really hard to test a method that may or may not return data")
    def test_subscription_ticker_candles(
        self,
        caplog: pytest.LogCaptureFixture,
        capsys: pytest.CaptureFixture[str],
        websocket: Bitvavo.WebSocketAppFacade,
    ) -> None:
        websocket.subscription_candles(market="BTC-EUR", interval="1h", callback=generic_callback)
        self.wait()
        self.wait()
        self.wait()

        assert caplog.text == ""
        stdout, stderr = capsys.readouterr()
        assert stderr == ""
        assert (
            'generic_callback: {\n  "event": "candle",\n  "market": "BTC-EUR",\n  "interval": "1h",\n  "candle": [\n   '
            in stdout
        )

    @pytest.mark.skipif(True, reason="It's really hard to test a method that may or may not return data")
    def test_subscription_trades(
        self,
        caplog: pytest.LogCaptureFixture,
        capsys: pytest.CaptureFixture[str],
        websocket: Bitvavo.WebSocketAppFacade,
    ) -> None:
        websocket.subscription_trades(market="BTC-EUR", callback=generic_callback)
        self.wait()
        self.wait()
        self.wait()

        assert caplog.text == ""
        stdout, stderr = capsys.readouterr()
        assert stderr == ""
        assert 'generic_callback: {\n  "event": "trade",\n  "timestamp": ' in stdout

    @pytest.mark.skipif(True, reason="It's really hard to test a method that may or may not return data")
    def test_subscription_book_update(
        self,
        caplog: pytest.LogCaptureFixture,
        capsys: pytest.CaptureFixture[str],
        websocket: Bitvavo.WebSocketAppFacade,
    ) -> None:
        websocket.subscription_book_update(market="BTC-EUR", callback=generic_callback)
        self.wait()
        self.wait()
        self.wait()

        assert caplog.text == ""
        stdout, stderr = capsys.readouterr()
        assert stderr == ""
        assert 'generic_callback: {\n  "event": "book",\n  "market": "BTC-EUR",\n  "nonce": ' in stdout

    @pytest.mark.skipif(True, reason="It's really hard to test a method that may or may not return data")
    def test_subscription_book(
        self,
        caplog: pytest.LogCaptureFixture,
        capsys: pytest.CaptureFixture[str],
        websocket: Bitvavo.WebSocketAppFacade,
    ) -> None:
        websocket.subscription_book(market="BTC-EUR", callback=generic_callback)
        self.wait()
        self.wait()
        self.wait()

        assert caplog.text == ""
        stdout, stderr = capsys.readouterr()
        assert stderr == ""
        assert 'generic_callback: {\n  "bids": [\n    [\n      "' in stdout
