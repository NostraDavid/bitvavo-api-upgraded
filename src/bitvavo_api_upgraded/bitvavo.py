from __future__ import annotations

import contextlib
import datetime as dt
import hashlib
import hmac
import json
import time
from pathlib import Path
from threading import Thread
from typing import Any, Callable

import websocket as ws_lib
from requests import delete, get, post, put
from structlog.stdlib import get_logger
from websocket import WebSocketApp  # missing stubs for WebSocketApp

from bitvavo_api_upgraded.dataframe_utils import convert_candles_to_dataframe, convert_to_dataframe
from bitvavo_api_upgraded.helper_funcs import configure_loggers, time_ms, time_to_wait
from bitvavo_api_upgraded.settings import bitvavo_settings, bitvavo_upgraded_settings
from bitvavo_api_upgraded.type_aliases import OutputFormat, anydict, errordict, intdict, ms, s_f, strdict, strintdict

configure_loggers()

logger = get_logger(__name__)


def create_signature(timestamp: ms, method: str, url: str, body: anydict | None, api_secret: str) -> str:
    string = f"{timestamp}{method}/v2{url}"
    if body is not None and len(body.keys()) > 0:
        string += json.dumps(body, separators=(",", ":"))
    signature = hmac.new(api_secret.encode("utf-8"), string.encode("utf-8"), hashlib.sha256).hexdigest()
    return signature


def create_postfix(options: anydict | None) -> str:
    """Generate a URL postfix, based on the `options` dict.

    ---
    Args:
        options (anydict): [description]

    ---
    Returns:
        str: [description]
    """
    options = _default(options, {})
    params = [f"{key}={options[key]}" for key in options]
    postfix = "&".join(params)  # intersperse
    return f"?{postfix}" if len(options) > 0 else postfix


def _default(value: anydict | None, fallback: anydict) -> anydict:
    """
    Note that is close, but not actually equal to:

    `return value or fallback`

    I checked this with a temporary hypothesis test.

    This note is all you will get out of me.
    """
    return value if value is not None else fallback


def _epoch_millis(dt: dt.datetime) -> int:
    return int(dt.timestamp() * 1000)


def asks_compare(a: float, b: float) -> bool:
    return a < b


def bids_compare(a: float, b: float) -> bool:
    return a > b


def sort_and_insert(
    asks_or_bids: list[list[str]],
    update: list[list[str]],
    compareFunc: Callable[[float, float], bool],
) -> list[list[str]] | errordict:
    for updateEntry in update:
        entrySet: bool = False
        for j in range(len(asks_or_bids)):
            bookItem = asks_or_bids[j]
            if compareFunc(float(updateEntry[0]), float(bookItem[0])):
                asks_or_bids.insert(j, updateEntry)
                entrySet = True
                break
            if float(updateEntry[0]) == float(bookItem[0]):
                if float(updateEntry[1]) > 0.0:
                    asks_or_bids[j] = updateEntry
                    entrySet = True
                    break
                asks_or_bids.pop(j)
                entrySet = True
                break
        if not entrySet:
            asks_or_bids.append(updateEntry)
    return asks_or_bids


def process_local_book(ws: Bitvavo.WebSocketAppFacade, message: anydict) -> None:
    market: str = ""
    if "action" in message:
        if message["action"] == "getBook":
            market = message["response"]["market"]
            ws.localBook[market]["bids"] = message["response"]["bids"]
            ws.localBook[market]["asks"] = message["response"]["asks"]
            ws.localBook[market]["nonce"] = message["response"]["nonce"]
            ws.localBook[market]["market"] = market
    elif "event" in message and message["event"] == "book":
        market = message["market"]

        if message["nonce"] != ws.localBook[market]["nonce"] + 1:
            # I think I've fixed this, by looking at the other Bitvavo repos (search for 'nonce' or '!=' 😆)
            ws.subscription_book(market, ws.callbacks[market])
            return
        ws.localBook[market]["bids"] = sort_and_insert(ws.localBook[market]["bids"], message["bids"], bids_compare)
        ws.localBook[market]["asks"] = sort_and_insert(ws.localBook[market]["asks"], message["asks"], asks_compare)
        ws.localBook[market]["nonce"] = message["nonce"]

    if market != "":
        ws.callbacks["subscriptionBookUser"][market](ws.localBook[market])


class ReceiveThread(Thread):
    """This used to be `class rateLimitThread`."""

    def __init__(self, ws: WebSocketApp, ws_facade: Bitvavo.WebSocketAppFacade) -> None:
        self.ws = ws
        self.ws_facade = ws_facade
        Thread.__init__(self)

    def run(self) -> None:
        """This used to be `self.waitForReset`."""
        try:
            while self.ws_facade.keepAlive:
                self.ws.run_forever()
                self.ws_facade.reconnect = True
                self.ws_facade.authenticated = False
                time.sleep(self.ws_facade.reconnectTimer)
                if self.ws_facade.bitvavo.debugging:
                    msg = f"we have just set reconnect to true and have waited for {self.ws_facade.reconnectTimer}"
                    logger.debug(msg)
                self.ws_facade.reconnectTimer = self.ws_facade.reconnectTimer * 2
        except KeyboardInterrupt:
            if self.ws_facade.bitvavo.debugging:
                logger.debug("keyboard-interrupt")

    def stop(self) -> None:
        self.ws_facade.keepAlive = False


def callback_example(response: Any) -> None:
    """
    You can use this example as a starting point, for the websocket code, IF you want to

    I  made this so you can see what kind of function you'll need to stick into the websocket functions.
    """
    if isinstance(response, dict):
        # instead of printing, you could save the object to a file:
        HERE = Path.cwd()  # root of your project folder
        filepath = HERE / "your_output.json"
        # a = append; figure out yourself to create multiple callback functions, probably one for each type of call that
        # you want to make
        with filepath.open("a") as file:
            file.write(json.dumps(response))
    elif isinstance(response, list):
        # Whether `item` is a list or a dict doesn't matter to print
        for item in response:
            print(item)
        # You can also copy-paste stuff to write it to a file or something
        # of maybe mess around with sqlite. ¯\_(ツ)_/¯
    else:
        # Normally, I would raise an exception here, but the websocket Thread would just eat it up anyway :/
        # I don't even know if this log will be shown to you.
        # Yes, I haven't tested this function; it's just some off-the-cuff example to get you started.
        logger.critical("what in the blazes did I just receive!?")


def error_callback_example(msg: errordict) -> None:
    """
    When using the websocket, I really REALLY recommend using `ws.setErrorCallback(error_callback_example)`, instead of
    using the default (yes, there is a default on_error function, but that just prints the error, which in practice
    means it won't show for the user, as the websocket has a tendency to silently fail printing).

    I would recommand adding some alerting mechanism, where the error isn't written to a log,
    but to some external system instead, like Discord, Slack, Email, Signal, Telegram, etc
    As I said, this is due to the websocket silently dropping python Exceptions and Bitvavo Errors.

    I can't speak for all options (yet), but the Discord one was VERY easy (mostly due to me already having a Discord channel :p)

    ```shell
    pip install discord-webhook
    ```

    Create a webhook for some channel (look for the cog icon) and copy it into a `DISCORD_WEBHOOK` variable

    ```python
    from discord_webhook import DiscordWebhook

    # send the message directly to your discord channel! :D
    DiscordWebhook(
        url=DISCORD_WEBHOOK,
        rate_limit_retry=True,
        content=f"{msg}",
    ).execute()
    ```
    """  # noqa: E501
    # easiest thing is to use the logger, but there's a good chance this message gets silently eaten.
    logger.error("error", msg=msg)


class Bitvavo:
    """
    Example code to get your started:

    ```python
    # Single API key (backward compatible)
    bitvavo = Bitvavo(
        {
            "APIKEY": "$YOUR_API_KEY",
            "APISECRET": "$YOUR_API_SECRET",
            "RESTURL": "https://api.bitvavo.com/v2",
            "WSURL": "wss://ws.bitvavo.com/v2/",
            "ACCESSWINDOW": 10000,
            "DEBUGGING": True,
        },
    )
    time_dict = bitvavo.time()

    # Multiple API keys with keyless preference
    bitvavo = Bitvavo(
        {
            "APIKEYS": [
                {"key": "$YOUR_API_KEY_1", "secret": "$YOUR_API_SECRET_1"},
                {"key": "$YOUR_API_KEY_2", "secret": "$YOUR_API_SECRET_2"},
                {"key": "$YOUR_API_KEY_3", "secret": "$YOUR_API_SECRET_3"},
            ],
            "PREFER_KEYLESS": True,  # Use keyless requests first, then API keys
            "RESTURL": "https://api.bitvavo.com/v2",
            "WSURL": "wss://ws.bitvavo.com/v2/",
            "ACCESSWINDOW": 10000,
            "DEBUGGING": True,
        },
    )
    time_dict = bitvavo.time()

    # Keyless only (no API keys)
    bitvavo = Bitvavo(
        {
            "PREFER_KEYLESS": True,
            "RESTURL": "https://api.bitvavo.com/v2",
            "WSURL": "wss://ws.bitvavo.com/v2/",
            "ACCESSWINDOW": 10000,
            "DEBUGGING": True,
        },
    )
    markets = bitvavo.markets()  # Only public endpoints will work
    ```
    """

    def __init__(self, options: dict[str, str | int | list[dict[str, str]]] | None = None) -> None:
        if options is None:
            options = {}
        _options = {k.upper(): v for k, v in options.items()}

        # Options take precedence over settings
        self.base: str = str(_options.get("RESTURL", bitvavo_settings.RESTURL))
        self.wsUrl: str = str(_options.get("WSURL", bitvavo_settings.WSURL))
        self.ACCESSWINDOW: int = int(_options.get("ACCESSWINDOW", bitvavo_settings.ACCESSWINDOW))

        # Support for multiple API keys - options take absolute precedence
        if "APIKEY" in _options and "APISECRET" in _options:
            # Single API key explicitly provided in options - takes precedence
            single_key = str(_options["APIKEY"])
            single_secret = str(_options["APISECRET"])
            self.api_keys: list[dict[str, str]] = [{"key": single_key, "secret": single_secret}]
        elif "APIKEYS" in _options:
            # Multiple API keys provided in options - takes precedence
            api_keys = _options["APIKEYS"]
            if isinstance(api_keys, list) and api_keys:
                self.api_keys = api_keys
            else:
                self.api_keys = []
        else:
            # Fall back to settings only if no API key options provided
            api_keys = bitvavo_settings.APIKEYS
            if isinstance(api_keys, list) and api_keys:
                self.api_keys = api_keys
            else:
                # Single API key from settings (backward compatibility)
                single_key = str(bitvavo_settings.APIKEY)
                single_secret = str(bitvavo_settings.APISECRET)
                if single_key and single_secret:
                    self.api_keys = [{"key": single_key, "secret": single_secret}]
                else:
                    self.api_keys = []

        # Current API key index and keyless preference - options take precedence
        self.current_api_key_index: int = 0
        self.prefer_keyless: bool = bool(_options.get("PREFER_KEYLESS", bitvavo_upgraded_settings.PREFER_KEYLESS))

        # Rate limiting per API key (keyless has index -1)
        self.rate_limits: dict[int, dict[str, int | ms]] = {}
        # Get default rate limit from options or settings
        default_rate_limit_option = _options.get("DEFAULT_RATE_LIMIT", bitvavo_upgraded_settings.DEFAULT_RATE_LIMIT)
        default_rate_limit = (
            int(default_rate_limit_option)
            if isinstance(default_rate_limit_option, (int, str))
            else bitvavo_upgraded_settings.DEFAULT_RATE_LIMIT
        )

        self.rate_limits[-1] = {"remaining": default_rate_limit, "resetAt": ms(0)}  # keyless
        for i in range(len(self.api_keys)):
            self.rate_limits[i] = {"remaining": default_rate_limit, "resetAt": ms(0)}

        # Legacy properties for backward compatibility
        self.APIKEY: str = self.api_keys[0]["key"] if self.api_keys else ""
        self.APISECRET: str = self.api_keys[0]["secret"] if self.api_keys else ""
        self._current_api_key: str = self.APIKEY
        self._current_api_secret: str = self.APISECRET
        self.rateLimitRemaining: int = default_rate_limit
        self.rateLimitResetAt: ms = 0

        # Options take precedence over settings for debugging
        self.debugging: bool = bool(_options.get("DEBUGGING", bitvavo_settings.DEBUGGING))

    def get_best_api_key_config(self, rateLimitingWeight: int = 1) -> tuple[str, str, int]:
        """
        Get the best API key configuration to use for a request.

        Returns:
            tuple: (api_key, api_secret, key_index) where key_index is -1 for keyless
        """
        # If prefer keyless and keyless has enough rate limit, use keyless
        if self.prefer_keyless and self._has_rate_limit_available(-1, rateLimitingWeight):
            return "", "", -1

        # Try to find an API key with enough rate limit
        for i in range(len(self.api_keys)):
            if self._has_rate_limit_available(i, rateLimitingWeight):
                return self.api_keys[i]["key"], self.api_keys[i]["secret"], i

        # If keyless is available, use it as fallback
        if self._has_rate_limit_available(-1, rateLimitingWeight):
            return "", "", -1

        # No keys available, use current key and let rate limiting handle the wait
        if self.api_keys:
            return (
                self.api_keys[self.current_api_key_index]["key"],
                self.api_keys[self.current_api_key_index]["secret"],
                self.current_api_key_index,
            )
        return "", "", -1

    def _has_rate_limit_available(self, key_index: int, weight: int) -> bool:
        """Check if a specific API key (or keyless) has enough rate limit."""
        if key_index not in self.rate_limits:
            return False
        remaining = self.rate_limits[key_index]["remaining"]
        return (remaining - weight) > bitvavo_upgraded_settings.RATE_LIMITING_BUFFER

    def _update_rate_limit_for_key(self, key_index: int, response: anydict | errordict) -> None:
        """Update rate limit for a specific API key index."""
        if key_index not in self.rate_limits:
            self.rate_limits[key_index] = {"remaining": 1000, "resetAt": ms(0)}

        if "errorCode" in response and response["errorCode"] == 105:  # noqa: PLR2004
            self.rate_limits[key_index]["remaining"] = 0
            # rateLimitResetAt is a value that's stripped from a string.
            reset_time_str = str(response.get("error", "")).split(" at ")
            if len(reset_time_str) > 1:
                try:
                    reset_time = ms(int(reset_time_str[1].split(".")[0]))
                    self.rate_limits[key_index]["resetAt"] = reset_time
                except (ValueError, IndexError):
                    # Fallback to current time + 60 seconds if parsing fails
                    self.rate_limits[key_index]["resetAt"] = ms(time_ms() + 60000)
            else:
                self.rate_limits[key_index]["resetAt"] = ms(time_ms() + 60000)

            timeToWait = time_to_wait(ms(self.rate_limits[key_index]["resetAt"]))
            key_name = f"API_KEY_{key_index}" if key_index >= 0 else "KEYLESS"
            logger.warning(
                "api-key-banned",
                info={
                    "key_name": key_name,
                    "wait_time_seconds": timeToWait + 1,
                    "until": (dt.datetime.now(tz=dt.timezone.utc) + dt.timedelta(seconds=timeToWait + 1)).isoformat(),
                },
            )

        if "bitvavo-ratelimit-remaining" in response:
            with contextlib.suppress(ValueError, TypeError):
                self.rate_limits[key_index]["remaining"] = int(response["bitvavo-ratelimit-remaining"])

        if "bitvavo-ratelimit-resetat" in response:
            with contextlib.suppress(ValueError, TypeError):
                self.rate_limits[key_index]["resetAt"] = ms(int(response["bitvavo-ratelimit-resetat"]))

    def _sleep_for_key(self, key_index: int) -> None:
        """Sleep until the specified API key's rate limit resets."""
        if key_index not in self.rate_limits:
            return

        reset_at = ms(self.rate_limits[key_index]["resetAt"])
        napTime = time_to_wait(reset_at)
        key_name = f"API_KEY_{key_index}" if key_index >= 0 else "KEYLESS"

        logger.warning(
            "rate-limit-reached", key_name=key_name, rateLimitRemaining=self.rate_limits[key_index]["remaining"]
        )
        logger.info(
            "napping-until-reset",
            key_name=key_name,
            napTime=napTime,
            currentTime=dt.datetime.now(tz=dt.timezone.utc).isoformat(),
            targetDatetime=dt.datetime.fromtimestamp(reset_at / 1000.0, tz=dt.timezone.utc).isoformat(),
        )
        time.sleep(napTime + 1)  # +1 to add a tiny bit of buffer time

    def calc_lag(self) -> ms:
        """
        Calculate the time difference between the client and server; use this value with BITVAVO_API_UPGRADED_LAG,
        when you make an api call, to precent 304 errors.

        Raises KeyError if time() returns an error dict.
        """
        lag_list = [
            self.time()["time"] - time_ms(),
            self.time()["time"] - time_ms(),
            self.time()["time"] - time_ms(),
            self.time()["time"] - time_ms(),
            self.time()["time"] - time_ms(),
            self.time()["time"] - time_ms(),
            self.time()["time"] - time_ms(),
            self.time()["time"] - time_ms(),
            self.time()["time"] - time_ms(),
            self.time()["time"] - time_ms(),
        ]

        return ms(sum(lag_list) / len(lag_list))

    def get_remaining_limit(self) -> int:
        """Get the remaining rate limit

        ---
        Returns:
        ```python
        1000  # or lower
        ```
        """
        return self.rateLimitRemaining

    def update_rate_limit(self, response: anydict | errordict) -> None:
        """
        Update the rate limited

        If you're banned, use the errordict to sleep until you're not banned

        If you're not banned, then use the received headers to update the variables.

        This method maintains backward compatibility by updating the legacy properties.
        """
        # Update rate limit for the current API key being used
        current_key = self.current_api_key_index if self.APIKEY else -1
        self._update_rate_limit_for_key(current_key, response)

        # Update legacy properties for backward compatibility
        if current_key in self.rate_limits:
            self.rateLimitRemaining = int(self.rate_limits[current_key]["remaining"])
            self.rateLimitResetAt = ms(self.rate_limits[current_key]["resetAt"])

        # Handle ban with sleep (legacy behavior)
        if "errorCode" in response and response["errorCode"] == 105:  # noqa: PLR2004
            timeToWait = time_to_wait(self.rateLimitResetAt)
            logger.warning(
                "banned",
                info={
                    "wait_time_seconds": timeToWait + 1,
                    "until": (dt.datetime.now(tz=dt.timezone.utc) + dt.timedelta(seconds=timeToWait + 1)).isoformat(),
                },
            )
            logger.info("napping-until-ban-lifted")
            time.sleep(timeToWait + 1)  # plus one second to ENSURE we're able to run again.

    def public_request(
        self,
        url: str,
        rateLimitingWeight: int = 1,
    ) -> list[anydict] | list[list[str]] | intdict | strdict | anydict | errordict:
        """Execute a request to the public part of the API; no API key and/or SECRET necessary.
        Will return the reponse as one of three types.

        ---
        Args:
        ```python
        url: str = "https://api.bitvavo.com/v2/time" # example of how the url looks like
        ```

        ---
        Returns:
        ```python
        # either of one:
        dict[str, Any]
        list[dict[str, Any]]
        list[list[str]]
        ```
        """
        # Get the best API key configuration (keyless preferred, then available keys)
        api_key, api_secret, key_index = self.get_best_api_key_config(rateLimitingWeight)

        # Check if we need to wait for rate limit
        if not self._has_rate_limit_available(key_index, rateLimitingWeight):
            self._sleep_for_key(key_index)

        # Update current API key for legacy compatibility
        if api_key:
            self._current_api_key = api_key
            self._current_api_secret = api_secret
            self.current_api_key_index = key_index
        else:
            # Using keyless
            self._current_api_key = ""
            self._current_api_secret = ""

        if self.debugging:
            logger.debug(
                "api-request",
                info={
                    "url": url,
                    "with_api_key": bool(api_key != ""),
                    "public_or_private": "public",
                    "key_index": key_index,
                },
            )

        if api_key:
            now = time_ms() + bitvavo_upgraded_settings.LAG
            sig = create_signature(now, "GET", url.replace(self.base, ""), None, api_secret)
            headers = {
                "bitvavo-access-key": api_key,
                "bitvavo-access-signature": sig,
                "bitvavo-access-timestamp": str(now),
                "bitvavo-access-window": str(self.ACCESSWINDOW),
            }
            r = get(url, headers=headers, timeout=(self.ACCESSWINDOW / 1000))
        else:
            r = get(url, timeout=(self.ACCESSWINDOW / 1000))

        # Update rate limit for the specific key used
        if "error" in r.json():
            self._update_rate_limit_for_key(key_index, r.json())
        else:
            self._update_rate_limit_for_key(key_index, dict(r.headers))

        # Also update legacy rate limit tracking
        self.update_rate_limit(r.json() if "error" in r.json() else dict(r.headers))

        return r.json()  # type:ignore[no-any-return]

    def private_request(
        self,
        endpoint: str,
        postfix: str,
        body: anydict | None = None,
        method: str = "GET",
        rateLimitingWeight: int = 1,
    ) -> list[anydict] | list[list[str]] | intdict | strdict | anydict | errordict:
        """Execute a request to the private  part of the API. API key and SECRET are required.
        Will return the reponse as one of three types.

        ---
        Args:
        # TODO(NostraDavid) fill these in
        ```python
        endpoint: str = "/order"
        postfix: str = ""  # ?key=value&key2=another_value&...
        body: anydict = {"market" = "BTC-EUR", "side": "buy", "orderType": "limit"}  # for example
        method: Optional[str] = "POST"  # Defaults to "GET"
        ```

        ---
        Returns:
        ```python
        # either of one:
        dict[str, Any]
        list[dict[str, Any]]
        list[list[str]]
        ```
        """
        # Private requests require an API key, so get the best available one
        api_key, api_secret, key_index = self.get_best_api_key_config(rateLimitingWeight)

        # If no API keys available, use the configured one (may fail)
        if not api_key and self.api_keys:
            api_key = self.api_keys[self.current_api_key_index]["key"]
            api_secret = self.api_keys[self.current_api_key_index]["secret"]
            key_index = self.current_api_key_index
        elif not api_key:
            # No API keys configured at all
            api_key = self.APIKEY
            api_secret = self.APISECRET
            key_index = 0 if api_key else -1

        # Check if we need to wait for rate limit
        if not self._has_rate_limit_available(key_index, rateLimitingWeight):
            self._sleep_for_key(key_index)

        # Update current API key for legacy compatibility
        self._current_api_key = api_key
        self._current_api_secret = api_secret

        now = time_ms() + bitvavo_upgraded_settings.LAG
        sig = create_signature(now, method, (endpoint + postfix), body, api_secret)
        url = self.base + endpoint + postfix
        headers = {
            "bitvavo-access-key": api_key,
            "bitvavo-access-signature": sig,
            "bitvavo-access-timestamp": str(now),
            "bitvavo-access-window": str(self.ACCESSWINDOW),
        }
        if self.debugging:
            logger.debug(
                "api-request",
                info={
                    "url": url,
                    "with_api_key": bool(api_key != ""),
                    "public_or_private": "private",
                    "method": method,
                    "key_index": key_index,
                },
            )
        if method == "DELETE":
            r = delete(url, headers=headers, timeout=(self.ACCESSWINDOW / 1000))
        elif method == "POST":
            r = post(url, headers=headers, json=body, timeout=(self.ACCESSWINDOW / 1000))
        elif method == "PUT":
            r = put(url, headers=headers, json=body, timeout=(self.ACCESSWINDOW / 1000))
        else:  # method == "GET"
            r = get(url, headers=headers, timeout=(self.ACCESSWINDOW / 1000))

        # Update rate limit for the specific key used
        if "error" in r.json():
            self._update_rate_limit_for_key(key_index, r.json())
        else:
            self._update_rate_limit_for_key(key_index, dict(r.headers))

        # Also update legacy rate limit tracking
        self.update_rate_limit(r.json() if "error" in r.json() else dict(r.headers))

        return r.json()

    def sleep_until_can_continue(self) -> None:
        napTime = time_to_wait(self.rateLimitResetAt)
        logger.warning("rate-limit-reached", rateLimitRemaining=self.rateLimitRemaining)
        logger.info(
            "napping-until-reset",
            napTime=napTime,
            currentTime=dt.datetime.now(tz=dt.timezone.utc).isoformat(),
            targetDatetime=dt.datetime.fromtimestamp(self.rateLimitResetAt / 1000.0, tz=dt.timezone.utc).isoformat(),
        )
        time.sleep(napTime + 1)  # +1 to add a tiny bit of buffer time

    def time(self) -> intdict:
        """Get server-time, in milliseconds, since 1970-01-01

        ---
        Examples:
        * https://api.bitvavo.com/v2/time

        ---
        Rate Limit Weight:
        ```python
        1
        ```

        ---
        Returns:
        ```python
        {"time": 1539180275424 }
        ```
        """
        return self.public_request(f"{self.base}/time")  # type: ignore[return-value]

    def markets(
        self,
        options: strdict | None = None,
        output_format: OutputFormat = OutputFormat.DICT,
    ) -> list[anydict] | anydict | errordict | Any:
        """Get all available markets with some meta-information, unless options is given a `market` key.
        Then you will get a single market, instead of a list of markets.

        ---
        Examples:
        * https://api.bitvavo.com/v2/markets
        * https://api.bitvavo.com/v2/markets?market=BTC-EUR
        * https://api.bitvavo.com/v2/markets?market=SHIB-EUR

        ---
        Args:
        ```python
        # Choose one:
        options={}  # returns all markets
        options={"market": "BTC-EUR"}  # returns only the BTC-EUR market
        # If you want multiple markets, but not all, make multiple calls

        # Output format selection:
        output_format=OutputFormat.DICT      # Default: returns standard Python dict/list
        output_format=OutputFormat.PANDAS    # Returns pandas DataFrame
        output_format=OutputFormat.POLARS    # Returns polars DataFrame
        output_format=OutputFormat.CUDF      # Returns NVIDIA cuDF (GPU-accelerated)
        output_format=OutputFormat.MODIN     # Returns modin (distributed pandas)
        output_format=OutputFormat.PYARROW   # Returns Apache Arrow Table
        output_format=OutputFormat.DASK      # Returns Dask DataFrame (distributed)
        output_format=OutputFormat.DUCKDB    # Returns DuckDB relation
        output_format=OutputFormat.IBIS      # Returns Ibis expression
        output_format=OutputFormat.PYSPARK   # Returns PySpark DataFrame
        output_format=OutputFormat.PYSPARK_CONNECT  # Returns PySpark Connect DataFrame
        output_format=OutputFormat.SQLFRAME  # Returns SQLFrame DataFrame

        # Note: DataFrame formats require narwhals and the respective library to be installed.
        # Install with: pip install 'bitvavo-api-upgraded[pandas]' or similar for other formats.
        ```

        ---
        Rate Limit Weight:
        ```python
        1
        ```

        ---
        Returns:
        ```python
        # When output_format=OutputFormat.DICT (default):
        [
          {
            "market": "BTC-EUR",
            "status": "trading",
            "base": "BTC",
            "quote": "EUR",
            "pricePrecision": "5",
            "minOrderInQuoteAsset": "10",
            "minOrderInBaseAsset": "0.001",
            "orderTypes": [
            "market",
            "limit",
            "stopLoss",
            "stopLossLimit",
            "takeProfit",
            "takeProfitLimit"
            ]
          }
        ]

        # When output_format is any DataFrame format (pandas, polars, cudf, etc.):
        # Returns a DataFrame with columns: market, status, base, quote, pricePrecision,
        # minOrderInQuoteAsset, minOrderInBaseAsset, orderTypes
        # The specific DataFrame type depends on the selected format.
        ```
        """
        postfix = create_postfix(options)
        result = self.public_request(f"{self.base}/markets{postfix}")  # type: ignore[return-value]
        return convert_to_dataframe(result, output_format)

    def assets(
        self,
        options: strdict | None = None,
        output_format: OutputFormat = OutputFormat.DICT,
    ) -> list[anydict] | anydict | Any:
        """Get all available assets, unless `options` is given a `symbol` key.
        Then you will get a single asset, instead of a list of assets.

        ---
        Examples:
        * https://api.bitvavo.com/v2/assets
        * https://api.bitvavo.com/v2/assets?symbol=BTC
        * https://api.bitvavo.com/v2/assets?symbol=SHIB
        * https://api.bitvavo.com/v2/assets?symbol=ADA
        * https://api.bitvavo.com/v2/assets?symbol=EUR

        ---
        Args:
        ```python
        # pick one
        options={}  # returns all assets
        options={"symbol": "BTC"} # returns a single asset (the one of Bitcoin)

        # Output format selection:
        output_format=OutputFormat.DICT      # Default: returns standard Python dict/list
        output_format=OutputFormat.PANDAS    # Returns pandas DataFrame
        output_format=OutputFormat.POLARS    # Returns polars DataFrame
        output_format=OutputFormat.CUDF      # Returns NVIDIA cuDF (GPU-accelerated)
        output_format=OutputFormat.MODIN     # Returns modin (distributed pandas)
        output_format=OutputFormat.PYARROW   # Returns Apache Arrow Table
        output_format=OutputFormat.DASK      # Returns Dask DataFrame (distributed)
        output_format=OutputFormat.DUCKDB    # Returns DuckDB relation
        output_format=OutputFormat.IBIS      # Returns Ibis expression
        output_format=OutputFormat.PYSPARK   # Returns PySpark DataFrame
        output_format=OutputFormat.PYSPARK_CONNECT  # Returns PySpark Connect DataFrame
        output_format=OutputFormat.SQLFRAME  # Returns SQLFrame DataFrame

        # Note: DataFrame formats require narwhals and the respective library to be installed.
        # Install with: pip install 'bitvavo-api-upgraded[pandas]' or similar for other formats.
        ```

        ---
        Rate Limit Weight:
        ```python
        1
        ```

        ---
        Returns:
        ```python
        # When output_format=OutputFormat.DICT (default):
        [
          {
            "symbol": "BTC",
            "name": "Bitcoin",
            "decimals": 8,
            "depositFee": "0",
            "depositConfirmations": 10,
            "depositStatus": "OK",
            "withdrawalFee": "0.2",
            "withdrawalMinAmount": "0.2",
            "withdrawalStatus": "OK",
            "networks": ["Mainnet"],
            "message": ""
          }
        ]

        # When output_format is any DataFrame format (pandas, polars, cudf, etc.):
        # Returns a DataFrame with columns: symbol, name, decimals, depositFee,
        # depositConfirmations, depositStatus, withdrawalFee, withdrawalMinAmount,
        # withdrawalStatus, networks, message
        # The specific DataFrame type depends on the selected format.
        ```
        """
        postfix = create_postfix(options)
        result = self.public_request(f"{self.base}/assets{postfix}")  # type: ignore[return-value]
        return convert_to_dataframe(result, output_format)

    def book(self, market: str, options: intdict | None = None) -> dict[str, str | int | list[str]] | errordict:
        """Get a book (with two lists: asks and bids, as they're called)

        ---
        Examples:
        * https://api.bitvavo.com/v2/BTC-EUR/book
        * https://api.bitvavo.com/v2/SHIB-EUR/book?depth=10
        * https://api.bitvavo.com/v2/ADA-EUR/book?depth=0

        ---
        Args:
        ```python
        market="ADA-EUR"
        options={"depth": 3}  # returns the best 3 asks and 3 bids
        options={}  # same as `{"depth": 0}`; returns all bids and asks for that book
        ```

        ---
        Rate Limit Weight:
        ```python
        1
        ```

        ---
        Returns:
        ```python
        {
          "market": "ADA-EUR",
          "nonce": 10378032,
          "bids": [["1.1908", "600"], ["1.1902", "4091.359809"], ["1.1898", "7563"]],
          "asks": [["1.1917", "2382.166997"], ["1.1919", "440.7"], ["1.192", "600"]],
          "timestamp": 1700000000000,
        }

        # Notice how each bid and ask is also a list
        bid = ["1.1908", "600"]  # the first bid from the bids list
        price = bid[0] # the price for one coin/token
        size = bid[1]  # how many tokens are asked (or bidded, in this case)
        result = price * size
        assert result == 714.48  # EUR can be gained from this bid if it's sold (minus the fee)
        ```
        """
        postfix = create_postfix(options)
        return self.public_request(f"{self.base}/{market}/book{postfix}")  # type: ignore[return-value]

    def public_trades(
        self,
        market: str,
        options: strintdict | None = None,
        output_format: OutputFormat = OutputFormat.DICT,
    ) -> list[anydict] | errordict | Any:
        """Publically available trades

        ---
        Examples:
        * https://api.bitvavo.com/v2/BTC-EUR/trades
        * https://api.bitvavo.com/v2/SHIB-EUR/trades?limit=10
        * https://api.bitvavo.com/v2/ADA-EUR/trades?tradeIdFrom=532f4d4d-f545-4a2d-a175-3d37919cb73c
        * https://api.bitvavo.com/v2/NANO-EUR/trades

        ---
        Args:
        ```python
        market="NANO-EUR"
        # note that any of these `options` are optional
        # use `int(time.time() * 1000)` to get current timestamp in milliseconds
        # or `int(datetime.datetime.now().timestamp()*1000)`
        options={
            "limit": [ 1 .. 1000 ], default 500
            "start": int timestamp in ms >= 0
            # (that's somewhere in the year 2243, or near the number 2^52)
            "end": int timestamp in ms <= 8_640_000_000_000_000
            "tradeIdFrom": ""  # if you get a list and want everything AFTER a certain id, put that id here
            "tradeIdTo": ""  # if you get a list and want everything BEFORE a certain id, put that id here
        }

        # Output format selection:
        output_format=OutputFormat.DICT      # Default: returns standard Python dict/list
        output_format=OutputFormat.PANDAS    # Returns pandas DataFrame
        output_format=OutputFormat.POLARS    # Returns polars DataFrame
        output_format=OutputFormat.CUDF      # Returns NVIDIA cuDF (GPU-accelerated)
        output_format=OutputFormat.MODIN     # Returns modin (distributed pandas)
        output_format=OutputFormat.PYARROW   # Returns Apache Arrow Table
        output_format=OutputFormat.DASK      # Returns Dask DataFrame (distributed)
        output_format=OutputFormat.DUCKDB    # Returns DuckDB relation
        output_format=OutputFormat.IBIS      # Returns Ibis expression
        output_format=OutputFormat.PYSPARK   # Returns PySpark DataFrame
        output_format=OutputFormat.PYSPARK_CONNECT  # Returns PySpark Connect DataFrame
        output_format=OutputFormat.SQLFRAME  # Returns SQLFrame DataFrame

        # Note: DataFrame formats require narwhals and the respective library to be installed.
        # Install with: pip install 'bitvavo-api-upgraded[pandas]' or similar for other formats.
        ```

        ---
        Rate Limit Weight:
        ```python
        5
        ```

        ---
        Returns:
        ```python
        # When output_format='dict' (default):
        [
          {
            "timestamp": 1542967486256,
            "id": "57b1159b-6bf5-4cde-9e2c-6bd6a5678baf",
            "amount": "0.1",
            "price": "5012",
            "side": "sell"
          }
        ]

        # When output_format is any DataFrame format:
        # Returns the above data as a DataFrame in the requested format (pandas, polars, etc.)
        ```
        """
        postfix = create_postfix(options)
        result = self.public_request(f"{self.base}/{market}/trades{postfix}", 5)  # type: ignore[return-value]
        return convert_to_dataframe(result, output_format)

    def candles(
        self,
        market: str,
        interval: str,
        options: strintdict | None = None,
        limit: int | None = None,
        start: dt.datetime | None = None,
        end: dt.datetime | None = None,
        output_format: OutputFormat = OutputFormat.DICT,
    ) -> list[list[str]] | errordict | Any:
        """Get up to 1440 candles for a market, with a specific interval (candle size)

        Extra reading material: https://en.wikipedia.org/wiki/Candlestick_chart

        ## WARNING: RETURN TYPE IS WEIRD - CHECK BOTTOM OF THIS TEXT FOR EXPLANATION

        ---
        Examples:
        * https://api.bitvavo.com/v2/BTC-EUR/candles?interval=1h&limit=100

        ---
        Args:
        ```python
        market="BTC-EUR"
        interval="1h"  # Choose: 1m, 5m, 15m, 30m, 1h, 2h, 4h, 6h, 8h, 12h, 1d
        # use `int(time.time() * 1000)` to get current timestamp in milliseconds
        # or `int(datetime.datetime.now().timestamp()*1000)`
        options={
            "limit": [ 1 .. 1440 ], default 1440
            "start": int timestamp in ms >= 0
            "end": int timestamp in ms <= 8640000000000000
        }

        # Output format selection:
        output_format=OutputFormat.DICT      # Default: returns standard Python list/dict
        output_format=OutputFormat.PANDAS    # Returns pandas DataFrame
        output_format=OutputFormat.POLARS    # Returns polars DataFrame
        output_format=OutputFormat.CUDF      # Returns NVIDIA cuDF (GPU-accelerated)
        output_format=OutputFormat.MODIN     # Returns modin (distributed pandas)
        output_format=OutputFormat.PYARROW   # Returns Apache Arrow Table
        output_format=OutputFormat.DASK      # Returns Dask DataFrame (distributed)
        output_format=OutputFormat.DUCKDB    # Returns DuckDB relation
        output_format=OutputFormat.IBIS      # Returns Ibis expression
        output_format=OutputFormat.PYSPARK   # Returns PySpark DataFrame
        output_format=OutputFormat.PYSPARK_CONNECT  # Returns PySpark Connect DataFrame
        output_format=OutputFormat.SQLFRAME  # Returns SQLFrame DataFrame

        # Note: DataFrame formats require narwhals and the respective library to be installed.
        # Install with: pip install 'bitvavo-api-upgraded[pandas]' or similar for other formats.
        ```

        ---
        Rate Limit Weight:
        ```python
        1
        ```

        ---
        Returns:
        ```python
        # When output_format='dict' (default):
        [
          # For whatever reason, you're getting a list of lists; no keys,
          # so here is the explanation of what's what.
          # timestamp,     open,    high,    low,     close,   volume
          [1640815200000, "41648", "41859", "41519", "41790", "12.1926685"],
          [1640811600000, "41771", "41780", "41462", "41650", "13.90917427"],
          [1640808000000, "41539", "42083", "41485", "41771", "14.39770267"],
          [1640804400000, "41937", "41955", "41449", "41540", "23.64498292"],
          [1640800800000, "41955", "42163", "41807", "41939", "10.40093845"],
        ]

        # When output_format is any DataFrame format:
        # Returns the above data as a DataFrame in the requested format (pandas, polars, etc.)
        # with columns: timestamp, open, high, low, close, volume
        # timestamp is converted to datetime, numeric columns to float
        ```
        """
        options = _default(options, {})
        options["interval"] = interval
        if limit is not None:
            options["limit"] = limit
        if start is not None:
            options["start"] = _epoch_millis(start)
        if end is not None:
            options["end"] = _epoch_millis(end)
        postfix = create_postfix(options)
        result = self.public_request(f"{self.base}/{market}/candles{postfix}")  # type: ignore[return-value]
        return convert_candles_to_dataframe(result, output_format)

    def ticker_price(
        self,
        options: strdict | None = None,
        output_format: OutputFormat = OutputFormat.DICT,
    ) -> list[strdict] | strdict | Any:
        """Get the current price for each market

        ---
        Examples:
        * https://api.bitvavo.com/v2/ticker/price
        * https://api.bitvavo.com/v2/ticker/price?market=BTC-EUR
        * https://api.bitvavo.com/v2/ticker/price?market=ADA-EUR
        * https://api.bitvavo.com/v2/ticker/price?market=SHIB-EUR
        * https://api.bitvavo.com/v2/ticker/price?market=DOGE-EUR
        * https://api.bitvavo.com/v2/ticker/price?market=NANO-EUR

        ---
        Args:
        ```python
        options={}
        options={"market": "BTC-EUR"}

        # Output format selection:
        output_format=OutputFormat.DICT      # Default: returns standard Python dict/list
        output_format=OutputFormat.PANDAS    # Returns pandas DataFrame
        output_format=OutputFormat.POLARS    # Returns polars DataFrame
        output_format=OutputFormat.CUDF      # Returns NVIDIA cuDF (GPU-accelerated)
        output_format=OutputFormat.MODIN     # Returns modin (distributed pandas)
        output_format=OutputFormat.PYARROW   # Returns Apache Arrow Table
        output_format=OutputFormat.DASK      # Returns Dask DataFrame (distributed)
        output_format=OutputFormat.DUCKDB    # Returns DuckDB relation
        output_format=OutputFormat.IBIS      # Returns Ibis expression
        output_format=OutputFormat.PYSPARK   # Returns PySpark DataFrame
        output_format=OutputFormat.PYSPARK_CONNECT  # Returns PySpark Connect DataFrame
        output_format=OutputFormat.SQLFRAME  # Returns SQLFrame DataFrame

        # Note: DataFrame formats require narwhals and the respective library to be installed.
        # Install with: pip install 'bitvavo-api-upgraded[pandas]' or similar for other formats.
        ```

        ---
        Rate Limit Weight:
        ```python
        1
        ```

        ---
        Returns:
        ```python
        # When output_format=OutputFormat.DICT (default):
        # Note that `price` is unconverted
        [
          {"market": "1INCH-EUR", "price": "2.1594"},
          {"market": "AAVE-EUR", "price": "214.42"},
          {"market": "ADA-BTC", "price": "0.000021401"},
          {"market": "ADA-EUR", "price": "1.2011"},
          {"market": "ADX-EUR", "price": "0.50357"},
          {"market": "AE-BTC", "price": "0.0000031334"},
          {"market": "AE-EUR", "price": "0.064378"},
          {"market": "AION-BTC", "price": "0.000004433"},
          {"market": "AION-EUR", "price": "0.1258"},
          {"market": "AKRO-EUR", "price": "0.020562"},
          {"market": "ALGO-EUR", "price": "1.3942"},
          # and another 210 markets below this point
        ]

        # When output_format is any DataFrame format (pandas, polars, cudf, etc.):
        # Returns a DataFrame with columns: market, price
        ```
        """
        postfix = create_postfix(options)
        result = self.public_request(f"{self.base}/ticker/price{postfix}")  # type: ignore[return-value]
        return convert_to_dataframe(result, output_format)

    def ticker_book(
        self,
        options: strdict | None = None,
        output_format: OutputFormat = OutputFormat.DICT,
    ) -> list[strdict] | strdict | Any:
        """Get current bid/ask, bidsize/asksize per market

        ---
        Examples:
        * https://api.bitvavo.com/v2/ticker/book
        * https://api.bitvavo.com/v2/ticker/book?market=BTC-EUR
        * https://api.bitvavo.com/v2/ticker/book?market=ADA-EUR
        * https://api.bitvavo.com/v2/ticker/book?market=SHIB-EUR
        * https://api.bitvavo.com/v2/ticker/book?market=DOGE-EUR
        * https://api.bitvavo.com/v2/ticker/book?market=NANO-EUR

        ---
        Args:
        ```python
        options={}
        options={"market": "BTC-EUR"}

        # Output format selection:
        output_format=OutputFormat.DICT      # Default: returns standard Python dict/list
        output_format=OutputFormat.PANDAS    # Returns pandas DataFrame
        output_format=OutputFormat.POLARS    # Returns polars DataFrame
        output_format=OutputFormat.CUDF      # Returns NVIDIA cuDF (GPU-accelerated)
        output_format=OutputFormat.MODIN     # Returns modin (distributed pandas)
        output_format=OutputFormat.PYARROW   # Returns Apache Arrow Table
        output_format=OutputFormat.DASK      # Returns Dask DataFrame (distributed)
        output_format=OutputFormat.DUCKDB    # Returns DuckDB relation
        output_format=OutputFormat.IBIS      # Returns Ibis expression
        output_format=OutputFormat.PYSPARK   # Returns PySpark DataFrame
        output_format=OutputFormat.PYSPARK_CONNECT  # Returns PySpark Connect DataFrame
        output_format=OutputFormat.SQLFRAME  # Returns SQLFrame DataFrame

        # Note: DataFrame formats require narwhals and the respective library to be installed.
        # Install with: pip install 'bitvavo-api-upgraded[pandas]' or similar for other formats.
        ```

        ---
        Rate Limit Weight:
        ```python
        1
        ```

        ---
        Returns:
        ```python
        # When output_format=OutputFormat.DICT (default):
        [
          {"market": "1INCH-EUR", "bid": "2.1534", "ask": "2.1587", "bidSize": "194.8", "askSize": "194.8"},
          {"market": "AAVE-EUR", "bid": "213.7", "ask": "214.05", "bidSize": "212.532", "askSize": "4.77676965"},
          {"market": "ADA-EUR", "bid": "1.2", "ask": "1.2014", "bidSize": "415.627597", "askSize": "600"},
          {"market": "ADX-EUR", "bid": "0.49896", "ask": "0.50076", "bidSize": "1262.38216882", "askSize": "700.1"},
          {"market": "AION-EUR", "bid": "0.12531", "ask": "0.12578", "bidSize": "3345", "askSize": "10958.49228653"},
          # and another 215 markets below this point
        ]

        # When output_format is any DataFrame format (pandas, polars, cudf, etc.):
        # Returns a DataFrame with columns: market, bid, ask, bidSize, askSize
        ```
        """
        postfix = create_postfix(options)
        result = self.public_request(f"{self.base}/ticker/book{postfix}")  # type: ignore[return-value]
        return convert_to_dataframe(result, output_format)

    def ticker24h(
        self,
        options: strdict | None = None,
        output_format: OutputFormat = OutputFormat.DICT,
    ) -> list[anydict] | anydict | errordict | Any:
        """Get current bid/ask, bidsize/asksize per market

        ---
        Examples:
        * https://api.bitvavo.com/v2/ticker/24h
        * https://api.bitvavo.com/v2/ticker/24h?market=BTC-EUR
        * https://api.bitvavo.com/v2/ticker/24h?market=ADA-EUR
        * https://api.bitvavo.com/v2/ticker/24h?market=SHIB-EUR
        * https://api.bitvavo.com/v2/ticker/24h?market=DOGE-EUR
        * https://api.bitvavo.com/v2/ticker/24h?market=NANO-EUR

        ---
        Args:
        ```python
        options={}
        options={"market": "BTC-EUR"}

        # Output format selection:
        output_format=OutputFormat.DICT      # Default: returns standard Python dict/list
        output_format=OutputFormat.PANDAS    # Returns pandas DataFrame
        output_format=OutputFormat.POLARS    # Returns polars DataFrame
        output_format=OutputFormat.CUDF      # Returns NVIDIA cuDF (GPU-accelerated)
        output_format=OutputFormat.MODIN     # Returns modin (distributed pandas)
        output_format=OutputFormat.PYARROW   # Returns Apache Arrow Table
        output_format=OutputFormat.DASK      # Returns Dask DataFrame (distributed)
        output_format=OutputFormat.DUCKDB    # Returns DuckDB relation
        output_format=OutputFormat.IBIS      # Returns Ibis expression
        output_format=OutputFormat.PYSPARK   # Returns PySpark DataFrame
        output_format=OutputFormat.PYSPARK_CONNECT  # Returns PySpark Connect DataFrame
        output_format=OutputFormat.SQLFRAME  # Returns SQLFrame DataFrame

        # Note: DataFrame formats require narwhals and the respective library to be installed.
        # Install with: pip install 'bitvavo-api-upgraded[pandas]' or similar for other formats.
        ```
        ---
        Rate Limit Weight:
        ```python
        25  # if no market option is used
        1  # if a market option is used
        ```
        ---
        Returns:
        ```python
        [
          {
            "market": "1INCH-EUR",
            "open": "2.2722",
            "high": "2.2967",
            "low": "2.1258",
            "last": "2.1552",
            "volume": "92921.3792573",
            "volumeQuote": "204118.95",
            "bid": "2.1481",
            "bidSize": "392.46514457",
            "ask": "2.1513",
            "askSize": "195.3",
            "timestamp": 1640819573777
          },
          {
            "market": "AAVE-EUR",
            "open": "224.91",
            "high": "228.89",
            "low": "210.78",
            "last": "213.83",
            "volume": "5970.52391148",
            "volumeQuote": "1307777.47",
            "bid": "213.41",
            "bidSize": "2.61115011",
            "ask": "213.85",
            "askSize": "1.864",
            "timestamp": 1640819573285
          },
          # and then 219 more markets
        ]
        ```
        """
        options = _default(options, {})
        rateLimitingWeight = 25
        if "market" in options:
            rateLimitingWeight = 1
        postfix = create_postfix(options)
        result = self.public_request(f"{self.base}/ticker/24h{postfix}", rateLimitingWeight)  # type: ignore[return-value]
        return convert_to_dataframe(result, output_format)

    def report_trades(
        self,
        market: str,
        options: strintdict | None = None,
        output_format: OutputFormat = OutputFormat.DICT,
    ) -> list[anydict] | errordict | Any:
        """Get MiCA-compliant trades report for a specific market

        Returns trades from the specified market and time period made by all Bitvavo users.
        The returned trades are sorted by timestamp in descending order (latest to earliest).
        Includes data compliant with the European Markets in Crypto-Assets (MiCA) regulation.

        ---
        Examples:
        * https://api.bitvavo.com/v2/report/BTC-EUR/trades
        * https://api.bitvavo.com/v2/report/BTC-EUR/trades?limit=100&start=1640995200000

        ---
        Args:
        ```python
        market="BTC-EUR"
        options={
          "limit": [ 1 .. 1000 ], default 500
          "start": int timestamp in ms >= 0
          "end": int timestamp in ms <= 8_640_000_000_000_000  # Cannot be more than 24 hours after start
          "tradeIdFrom": ""  # if you get a list and want everything AFTER a certain id, put that id here
          "tradeIdTo": ""  # if you get a list and want everything BEFORE a certain id, put that id here
        }

        # Output format selection:
        output_format=OutputFormat.DICT      # Default: returns standard Python dict/list
        output_format=OutputFormat.PANDAS    # Returns pandas DataFrame
        output_format=OutputFormat.POLARS    # Returns polars DataFrame
        output_format=OutputFormat.CUDF      # Returns NVIDIA cuDF (GPU-accelerated)
        output_format=OutputFormat.MODIN     # Returns modin (distributed pandas)
        output_format=OutputFormat.PYARROW   # Returns Apache Arrow Table
        output_format=OutputFormat.DASK      # Returns Dask DataFrame (distributed)
        output_format=OutputFormat.DUCKDB    # Returns DuckDB relation
        output_format=OutputFormat.IBIS      # Returns Ibis expression
        output_format=OutputFormat.PYSPARK   # Returns PySpark DataFrame
        output_format=OutputFormat.PYSPARK_CONNECT  # Returns PySpark Connect DataFrame
        output_format=OutputFormat.SQLFRAME  # Returns SQLFrame DataFrame
        ```
        ---
        Rate Limit Weight:
        ```python
        5
        ```

        ---
        Returns:
        ```python
        [
          {
          "timestamp": 1542967486256,
          "id": "57b1159b-6bf5-4cde-9e2c-6bd6a5678baf",
          "amount": "0.1",
          "price": "5012",
          "side": "sell"
          }
        ]
        ```
        """
        postfix = create_postfix(options)
        result = self.public_request(f"{self.base}/report/{market}/trades{postfix}", 5)  # type: ignore[return-value]
        return convert_to_dataframe(result, output_format)

    def report_book(self, market: str, options: intdict | None = None) -> dict[str, str | int | list[str]] | errordict:
        """Get MiCA-compliant order book report for a specific market

        Returns the list of all bids and asks for the specified market, sorted by price.
        Includes data compliant with the European Markets in Crypto-Assets (MiCA) regulation.

        ---
        Examples:
        * https://api.bitvavo.com/v2/report/BTC-EUR/book
        * https://api.bitvavo.com/v2/report/BTC-EUR/book?depth=100

        ---
        Args:
        ```python
        market="BTC-EUR"
        options={"depth": 100}  # returns the best 100 asks and 100 bids, default 1000
        options={}  # returns up to 1000 bids and asks for that book
        ```

        ---
        Rate Limit Weight:
        ```python
        1
        ```

        ---
        Returns:
        ```python
        {
          "market": "BTC-EUR",
          "nonce": 10378032,
          "bids": [["41648", "0.12"], ["41647", "0.25"], ["41646", "0.33"]],
          "asks": [["41649", "0.15"], ["41650", "0.28"], ["41651", "0.22"]],
          "timestamp": 1700000000000,
        }
        ```
        """
        postfix = create_postfix(options)
        return self.public_request(f"{self.base}/report/{market}/book{postfix}")  # type: ignore[return-value]

    def place_order(self, market: str, side: str, orderType: str, operatorId: int, body: anydict) -> anydict:
        """Place a new order on the exchange

        ---
        Args:
        ```python
        market="SHIB-EUR"
        side="buy" # Choose: buy, sell
        # For market orders either `amount` or `amountQuote` is required
        orderType="market"  # Choose: market, limit, stopLoss, stopLossLimit, takeProfit, takeProfitLimit
        operatorId=123  # Your identifier for the trader or bot that made the request
        body={
          "amount": "1.567",
          "amountQuote": "5000",
          "clientOrderId": "2be7d0df-d8dc-7b93-a550-8876f3b393e9",  # Optional: your identifier for the order
          # GTC orders will remain on the order book until they are filled or canceled.
          # IOC orders will fill against existing orders, but will cancel any remaining amount after that.
          # FOK orders will fill against existing orders in its entirety, or will be canceled (if the entire order cannot be filled).
          "timeInForce": "GTC",  # Choose: GTC, IOC, FOK. Good-Til-Canceled (GTC), Immediate-Or-Cancel (IOC), Fill-Or-Kill (FOK)
          # 'decrementAndCancel' decrements both orders by the amount that would have been filled, which in turn cancels the smallest of the two orders.
          # 'cancelOldest' will cancel the entire older order and places the new order.
          # 'cancelNewest' will cancel the order that is submitted.
          # 'cancelBoth' will cancel both the current and the old order.
          "selfTradePrevention": "decrementAndCancel",  # decrementAndCancel, cancelOldest, cancelNewest, cancelBoth
          "disableMarketProtection": false,
          "responseRequired": true  # setting this to `false` will return only an 'acknowledged', and be faster
        }

        # For limit orders `amount` and `price` are required.
        orderType="limit"  # Choose: market, limit, stopLoss, stopLossLimit, takeProfit, takeProfitLimit
        operatorId=123
        body={
          "amount": "1.567",
          "price": "6000",
          "timeInForce": "GTC",  # GTC, IOC, FOK. Good-Til-Canceled (GTC), Immediate-Or-Cancel (IOC), Fill-Or-Kill (FOK)
          "selfTradePrevention": "decrementAndCancel",  # decrementAndCancel, cancelOldest, cancelNewest, cancelBoth
          "postOnly": false,  # Only for limit orders
          "responseRequired": True
        }

        orderType="stopLoss"
        # or
        orderType="takeProfit"
        operatorId=123
        body={
          "amount": "1.567",
          "amountQuote": "5000",
          "triggerAmount": "4000",
          "triggerType": "price",
          "triggerReference": "lastTrade",
          "timeInForce": "GTC",  # GTC, IOC, FOK. Good-Til-Canceled (GTC), Immediate-Or-Cancel (IOC), Fill-Or-Kill (FOK)
          "selfTradePrevention": "decrementAndCancel",  # decrementAndCancel, cancelOldest, cancelNewest, cancelBoth
          "disableMarketProtection": false,
          "responseRequired": true
        }

        orderType="stopLossLimit"
        # or
        orderType="takeProfitLimit"
        operatorId=123
        body={
          "amount": "1.567",
          "price": "6000",
          "triggerAmount": "4000",
          "triggerType": "price",
          "triggerReference": "lastTrade",
          "timeInForce": "GTC",  # GTC, IOC, FOK. Good-Til-Canceled (GTC), Immediate-Or-Cancel (IOC), Fill-Or-Kill (FOK)
          "selfTradePrevention": "decrementAndCancel",  # decrementAndCancel, cancelOldest, cancelNewest, cancelBoth
          "postOnly": false,  # Only for limit orders
          "responseRequired": true
        }
        ```

        ---
        Rate Limit Weight:
        ```python
        1
        ```

        ---
        Returns:
        ```python
        {
          "orderId": "1be6d0df-d5dc-4b53-a250-3376f3b393e6",
          "market": "BTC-EUR",
          "created": 1542621155181,
          "updated": 1542621155181,
          "status": "new",
          "side": "buy",
          "orderType": "limit",
          "amount": "10",
          "amountRemaining": "10",
          "price": "7000",
          "amountQuote": "5000",
          "amountQuoteRemaining": "5000",
          "onHold": "9109.61",
          "onHoldCurrency": "BTC",
          "triggerPrice": "4000",
          "triggerAmount": "4000",
          "triggerType": "price",
          "triggerReference": "lastTrade",
          "filledAmount": "0",
          "filledAmountQuote": "0",
          "feePaid": "0",
          "feeCurrency": "EUR",
          "fills": [
            {
              "id": "371c6bd3-d06d-4573-9f15-18697cd210e5",
              "timestamp": 1542967486256,
              "amount": "0.005",
              "price": "5000.1",
              "taker": true,
              "fee": "0.03",
              "feeCurrency": "EUR",
              "settled": true
            }
          ],
          "selfTradePrevention": "decrementAndCancel",
          "visible": true,
          "timeInForce": "GTC",
          "postOnly": false,
          "disableMarketProtection": true
        }
        ```
        """  # noqa: E501
        body["market"] = market
        body["side"] = side
        body["orderType"] = orderType
        body["operatorId"] = operatorId
        return self.private_request("/order", "", body, "POST")  # type: ignore[return-value]

    def update_order(self, market: str, orderId: str, operatorId: int, body: anydict) -> anydict:
        """Update an existing order for a specific market. Make sure that at least one of the optional parameters is set, otherwise nothing will be updated.

        ---
        Args:
        ```python
        market="BTC-EUR"
        orderId="95d92d6c-ecf0-4960-a608-9953ef71652e"
        operatorId=123  # Your identifier for the trader or bot that made the request
        body={
          "amount": "1.567",
          "amountRemaining": "1.567",
          "price": "6000",
          "triggerAmount": "4000",  # only for stop orders
          "clientOrderId": "2be7d0df-d8dc-7b93-a550-8876f3b393e9",  # Optional: your identifier for the order
          # GTC orders will remain on the order book until they are filled or canceled.
          # IOC orders will fill against existing orders, but will cancel any remaining amount after that.
          # FOK orders will fill against existing orders in its entirety, or will be canceled (if the entire order cannot be filled).
          "timeInForce": "GTC",  # Choose: GTC, IOC, FOK. Good-Til-Canceled (GTC), Immediate-Or-Cancel (IOC), Fill-Or-Kill (FOK)
          # 'decrementAndCancel' decrements both orders by the amount that would have been filled, which in turn cancels the smallest of the two orders.
          # 'cancelOldest' will cancel the entire older order and places the new order.
          # 'cancelNewest' will cancel the order that is submitted.
          # 'cancelBoth' will cancel both the current and the old order.
          "selfTradePrevention": "decrementAndCancel",  # decrementAndCancel, cancelOldest, cancelNewest, cancelBoth
          "postOnly": false,  # Only for limit orders
          "responseRequired": true  # setting this to `false` will return only an 'acknowledged', and be faster
        }
        ```

        ---
        Rate Limit Weight:
        ```python
        1
        ```

        ---
        Returns:
        ```python
        {
          "orderId": "1be6d0df-d5dc-4b53-a250-3376f3b393e6",
          "market": "BTC-EUR",
          "created": 1542621155181,
          "updated": 1542621155181,
          "status": "new",
          "side": "buy",
          "orderType": "limit",
          "amount": "10",
          "amountRemaining": "10",
          "price": "7000",
          "amountQuote": "5000",
          "amountQuoteRemaining": "5000",
          "onHold": "9109.61",
          "onHoldCurrency": "BTC",
          "triggerPrice": "4000",
          "triggerAmount": "4000",
          "triggerType": "price",
          "triggerReference": "lastTrade",
          "filledAmount": "0",
          "filledAmountQuote": "0",
          "feePaid": "0",
          "feeCurrency": "EUR",
          "fills": [
            {
              "id": "371c6bd3-d06d-4573-9f15-18697cd210e5",
              "timestamp": 1542967486256,
              "amount": "0.005",
              "price": "5000.1",
              "taker": true,
              "fee": "0.03",
              "feeCurrency": "EUR",
              "settled": true
            }
          ],
          "selfTradePrevention": "decrementAndCancel",
          "visible": true,
          "timeInForce": "GTC",
          "postOnly": true,
          "disableMarketProtection": true
        }
        ```
        """  # noqa: E501
        body["market"] = market
        body["orderId"] = orderId
        body["operatorId"] = operatorId
        return self.private_request("/order", "", body, "PUT")  # type: ignore[return-value]

    def cancel_order(
        self,
        market: str,
        operatorId: int,
        orderId: str | None = None,
        clientOrderId: str | None = None,
    ) -> strdict:
        """Cancel an existing order for a specific market

        ---
        Args:
        ```python
        market="BTC-EUR"
        operatorId=123  # Your identifier for the trader or bot that made the request
        orderId="a4a5d310-687c-486e-a3eb-1df832405ccd"  # Either orderId or clientOrderId required
        clientOrderId="2be7d0df-d8dc-7b93-a550-8876f3b393e9"  # Either orderId or clientOrderId required
        # If both orderId and clientOrderId are provided, clientOrderId takes precedence
        ```

        ---
        Rate Limit Weight:
        ```python
        N/A
        ```

        ---
        Returns:
        ```python
        {"orderId": "2e7ce7fc-44e2-4d80-a4a7-d079c4750b61"}
        ```
        """
        if orderId is None and clientOrderId is None:
            msg = "Either orderId or clientOrderId must be provided"
            raise ValueError(msg)

        params = {
            "market": market,
            "operatorId": operatorId,
        }

        # clientOrderId takes precedence if both are provided
        if clientOrderId is not None:
            params["clientOrderId"] = clientOrderId
        elif orderId is not None:
            params["orderId"] = orderId

        postfix = create_postfix(params)
        return self.private_request("/order", postfix, {}, "DELETE")  # type: ignore[return-value]

    def get_order(self, market: str, orderId: str) -> list[anydict] | errordict:
        """Get an existing order for a specific market

        ---
        Args:
        ```python
        market="BTC-EUR"
        orderId="ff403e21-e270-4584-bc9e-9c4b18461465"
        ```

        ---
        Rate Limit Weight:
        ```python
        1
        ```

        ---
        Returns:
        ```python
        {
          "orderId": "1be6d0df-d5dc-4b53-a250-3376f3b393e6",
          "market": "BTC-EUR",
          "created": 1542621155181,
          "updated": 1542621155181,
          "status": "new",
          "side": "buy",
          "orderType": "limit",
          "amount": "10",
          "amountRemaining": "10",
          "price": "7000",
          "amountQuote": "5000",
          "amountQuoteRemaining": "5000",
          "onHold": "9109.61",
          "onHoldCurrency": "BTC",
          "triggerPrice": "4000",
          "triggerAmount": "4000",
          "triggerType": "price",
          "triggerReference": "lastTrade",
          "filledAmount": "0",
          "filledAmountQuote": "0",
          "feePaid": "0",
          "feeCurrency": "EUR",
          "fills": [
            {
              "id": "371c6bd3-d06d-4573-9f15-18697cd210e5",
              "timestamp": 1542967486256,
              "amount": "0.005",
              "price": "5000.1",
              "taker": true,
              "fee": "0.03",
              "feeCurrency": "EUR",
              "settled": true
            }
          ],
          "selfTradePrevention": "decrementAndCancel",
          "visible": true,
          "timeInForce": "GTC",
          "postOnly": true,
          "disableMarketProtection": true
        }
        ```
        """
        postfix = create_postfix({"market": market, "orderId": orderId})
        return self.private_request("/order", postfix, {}, "GET")  # type: ignore[return-value]

    def get_orders(self, market: str, options: anydict | None = None) -> list[anydict] | errordict:
        """Get multiple existing orders for a specific market

        ---
        Args:
        ```python
        market="BTC-EUR"
        options={
            "limit": [ 1 .. 1000 ], default 500
            "start": int timestamp in ms >= 0
            "end": int timestamp in ms <= 8_640_000_000_000_000 # (that's somewhere in the year 2243, or near the number 2^52)
            "tradeIdFrom": ""  # if you get a list and want everything AFTER a certain id, put that id here
            "tradeIdTo": ""  # if you get a list and want everything BEFORE a certain id, put that id here
        }
        ```

        ---
        Rate Limit Weight:
        ```python
        5
        ```

        ---
        Returns:
        ```python
        # A whole list of these
        [
          {
            "orderId": "1be6d0df-d5dc-4b53-a250-3376f3b393e6",
            "market": "BTC-EUR",
            "created": 1542621155181,
            "updated": 1542621155181,
            "status": "new",
            "side": "buy",
            "orderType": "limit",
            "amount": "10",
            "amountRemaining": "10",
            "price": "7000",
            "amountQuote": "5000",
            "amountQuoteRemaining": "5000",
            "onHold": "9109.61",
            "onHoldCurrency": "BTC",
            "triggerPrice": "4000",
            "triggerAmount": "4000",
            "triggerType": "price",
            "triggerReference": "lastTrade",
            "filledAmount": "0",
            "filledAmountQuote": "0",
            "feePaid": "0",
            "feeCurrency": "EUR",
            "fills": [
              {
                "id": "371c6bd3-d06d-4573-9f15-18697cd210e5",
                "timestamp": 1542967486256,
                "amount": "0.005",
                "price": "5000.1",
                "taker": true,
                "fee": "0.03",
                "feeCurrency": "EUR",
                "settled": true
              }
            ],
            "selfTradePrevention": "decrementAndCancel",
            "visible": true,
            "timeInForce": "GTC",
            "postOnly": true,
            "disableMarketProtection": true
          }
        ]
        ```
        """  # noqa: E501
        options = _default(options, {})
        options["market"] = market
        postfix = create_postfix(options)
        return self.private_request("/orders", postfix, {}, "GET", 5)  # type: ignore[return-value]

    def cancel_orders(self, options: anydict | None = None) -> list[strdict] | errordict:
        """Cancel all existing orders for a specific market (or account)

        ---
        Args:
        ```python
        options={} # WARNING - WILL REMOVE ALL OPEN ORDERS ON YOUR ACCOUNT!
        options={"market":"BTC-EUR"}  # Removes all open orders for this market
        ```

        ---
        Rate Limit Weight:
        ```python
        1
        ```

        ---
        Returns:
        ```python
        # A whole list of these
        [
          {"orderId": "1be6d0df-d5dc-4b53-a250-3376f3b393e6"}
        ]
        ```
        """
        postfix = create_postfix(options)
        return self.private_request("/orders", postfix, {}, "DELETE")  # type: ignore[return-value]

    def orders_open(self, options: anydict | None = None) -> list[anydict] | errordict:
        """Get all open orders, either for all markets, or a single market

        ---
        Args:
        ```python
        options={} # Gets all open orders for all markets
        options={"market":"BTC-EUR"}  # Get open orders for this market
        ```

        ---
        Rate Limit Weight:
        ```python
        25  # if no market option is used
        1  # if a market option is used
        ```

        ---
        Returns:
        ```python
        [
          {
            "orderId": "1be6d0df-d5dc-4b53-a250-3376f3b393e6",
            "market": "BTC-EUR",
            "created": 1542621155181,
            "updated": 1542621155181,
            "status": "new",
            "side": "buy",
            "orderType": "limit",
            "amount": "10",
            "amountRemaining": "10",
            "price": "7000",
            "amountQuote": "5000",
            "amountQuoteRemaining": "5000",
            "onHold": "9109.61",
            "onHoldCurrency": "BTC",
            "triggerPrice": "4000",
            "triggerAmount": "4000",
            "triggerType": "price",
            "triggerReference": "lastTrade",
            "filledAmount": "0",
            "filledAmountQuote": "0",
            "feePaid": "0",
            "feeCurrency": "EUR",
            "fills": [
              {
                "id": "371c6bd3-d06d-4573-9f15-18697cd210e5",
                "timestamp": 1542967486256,
                "amount": "0.005",
                "price": "5000.1",
                "taker": true,
                "fee": "0.03",
                "feeCurrency": "EUR",
                "settled": true
              }
            ],
            "selfTradePrevention": "decrementAndCancel",
            "visible": true,
            "timeInForce": "GTC",
            "postOnly": true,
            "disableMarketProtection": true
          }
        ]
        ```
        """
        options = _default(options, {})
        rateLimitingWeight = 25
        if "market" in options:
            rateLimitingWeight = 1
        postfix = create_postfix(options)
        return self.private_request("/ordersOpen", postfix, {}, "GET", rateLimitingWeight)  # type: ignore[return-value]

    def trades(
        self,
        market: str,
        options: anydict | None = None,
        output_format: OutputFormat = OutputFormat.DICT,
    ) -> list[anydict] | errordict | Any:
        """Get all historic trades from this account

        ---
        Args:
        ```python
        market="BTC-EUR"
        options={
          "limit": [ 1 .. 1000 ], default 500
          "start": int timestamp in ms >= 0
          "end": int timestamp in ms <= 8_640_000_000_000_000 # (that's somewhere in the year 2243, or near the number 2^52)
          "tradeIdFrom": ""  # if you get a list and want everything AFTER a certain id, put that id here
          "tradeIdTo": ""  # if you get a list and want everything BEFORE a certain id, put that id here
        }

        # Output format selection:
        output_format=OutputFormat.DICT      # Default: returns standard Python dict/list
        output_format=OutputFormat.PANDAS    # Returns pandas DataFrame
        output_format=OutputFormat.POLARS    # Returns polars DataFrame
        output_format=OutputFormat.CUDF      # Returns NVIDIA cuDF (GPU-accelerated)
        output_format=OutputFormat.MODIN     # Returns modin (distributed pandas)
        output_format=OutputFormat.PYARROW   # Returns Apache Arrow Table
        output_format=OutputFormat.DASK      # Returns Dask DataFrame (distributed)
        output_format=OutputFormat.DUCKDB    # Returns DuckDB relation
        output_format=OutputFormat.IBIS      # Returns Ibis expression
        output_format=OutputFormat.PYSPARK   # Returns PySpark DataFrame
        output_format=OutputFormat.PYSPARK_CONNECT  # Returns PySpark Connect DataFrame
        output_format=OutputFormat.SQLFRAME  # Returns SQLFrame DataFrame
        ```
        ---
        Rate Limit Weight:
        ```python
        5
        ```
        ---
        Returns:
        ```python
        [
          {
          "id": "108c3633-0276-4480-a902-17a01829deae",
          "orderId": "1d671998-3d44-4df4-965f-0d48bd129a1b",
          "timestamp": 1542967486256,
          "market": "BTC-EUR",
          "side": "buy",
          "amount": "0.005",
          "price": "5000.1",
          "taker": true,
          "fee": "0.03",
          "feeCurrency": "EUR",
          "settled": true
          }
        ]
        ```
        """  # noqa: E501
        options = _default(options, {})
        options["market"] = market
        postfix = create_postfix(options)
        result = self.private_request("/trades", postfix, {}, "GET", 5)  # type: ignore[return-value]
        return convert_to_dataframe(result, output_format)

    def account(self) -> dict[str, strdict]:
        """Get all fees for this account

        ---
        Rate Limit Weight:
        ```python
        1
        ```

        ---
        Returns:
        ```python
        {
          "fees": {
            "taker": "0.0025",
            "maker": "0.0015",
            "volume": "10000.00"
          }
        }
        ```
        """
        return self.private_request("/account", "", {}, "GET")  # type: ignore[return-value]

    def fees(self, market: str | None = None, quote: str | None = None) -> list[strdict] | errordict:
        """Get market fees for a specific market or quote currency

        ---
        Args:
        ```python
        market="BTC-EUR"  # Optional: get fees for specific market
        quote="EUR"       # Optional: get fees for all markets with EUR as quote currency
        # If both are provided, market takes precedence
        # If neither are provided, returns fees for all markets
        ```

        ---
        Rate Limit Weight:
        ```python
        1
        ```

        ---
        Returns:
        ```python
        [
          {
            "market": "BTC-EUR",
            "maker": "0.0015",
            "taker": "0.0025"
          }
        ]
        ```
        """
        options = {}
        if market is not None:
            options["market"] = market
        if quote is not None:
            options["quote"] = quote
        postfix = create_postfix(options)
        return self.private_request("/account/fees", postfix, {}, "GET")  # type: ignore[return-value]

    def balance(
        self,
        options: strdict | None = None,
        output_format: OutputFormat = OutputFormat.DICT,
    ) -> list[strdict] | errordict | Any:
        """Get the balance for this account

        ---
        Args:
        ```python
        options={}  # return all balances
        options={symbol="BTC"} # return a single balance

        # Output format selection:
        output_format=OutputFormat.DICT      # Default: returns standard Python dict/list
        output_format=OutputFormat.PANDAS    # Returns pandas DataFrame
        output_format=OutputFormat.POLARS    # Returns polars DataFrame
        output_format=OutputFormat.CUDF      # Returns NVIDIA cuDF (GPU-accelerated)
        output_format=OutputFormat.MODIN     # Returns modin (distributed pandas)
        output_format=OutputFormat.PYARROW   # Returns Apache Arrow Table
        output_format=OutputFormat.DASK      # Returns Dask DataFrame (distributed)
        output_format=OutputFormat.DUCKDB    # Returns DuckDB relation
        output_format=OutputFormat.IBIS      # Returns Ibis expression
        output_format=OutputFormat.PYSPARK   # Returns PySpark DataFrame
        output_format=OutputFormat.PYSPARK_CONNECT  # Returns PySpark Connect DataFrame
        output_format=OutputFormat.SQLFRAME  # Returns SQLFrame DataFrame

        # Note: DataFrame formats require narwhals and the respective library to be installed.
        # Install with: pip install 'bitvavo-api-upgraded[pandas]' or similar for other formats.
        ```

        ---
        Rate Limit Weight:
        ```python
        5
        ```

        ---
        Returns:
        ```python
        # When output_format='dict' (default):
        [
          {
            "symbol": "BTC",
            "available": "1.57593193",
            "inOrder": "0.74832374"
          }
        ]

        # When output_format is any DataFrame format:
        # Returns the above data as a DataFrame in the requested format (pandas, polars, etc.)
        # with columns: symbol, available, inOrder
        ```
        """
        postfix = create_postfix(options)
        result = self.private_request("/balance", postfix, {}, "GET", 5)  # type: ignore[return-value]
        return convert_to_dataframe(result, output_format)

    def account_history(self, options: strintdict | None = None) -> anydict | errordict:
        """Get all past transactions for your account

        ---
        Args:
        ```python
        options={
            "fromDate": int timestamp in ms >= 0,  # Starting timestamp to return transactions from
            "toDate": int timestamp in ms <= 8_640_000_000_000_000,  # Timestamp up to which to return transactions
            "maxItems": [ 1 .. 100 ], default 100,  # Maximum number of transactions per page
            "page": 1,  # Page number to return (1-indexed)
        }
        ```

        ---
        Rate Limit Weight:
        ```python
        1
        ```

        ---
        Returns:
        ```python
        {
          "items": [
            {
              "transactionId": "5f5e7b3b-4f5b-4b2d-8b2f-4f2b5b3f5e5f",
              "timestamp": 1542967486256,
              "type": "deposit",
              "symbol": "BTC",
              "amount": "0.99994",
              "description": "Deposit via bank transfer",
              "status": "completed",
              "feesCurrency": "EUR",
              "feesAmount": "0.01",
              "address": "BitcoinAddress"
            }
          ],
          "currentPage": 1,
          "totalPages": 1,
          "maxItems": 100
        }
        ```
        """
        postfix = create_postfix(options)
        return self.private_request("/account/history", postfix, {}, "GET")  # type: ignore[return-value]

    def deposit_assets(self, symbol: str) -> strdict:
        """Get the deposit address (with paymentId for some assets) or bank account information to increase your balance

        ---
        Args:
        ```python
        symbol="BTC"
        symbol="SHIB"
        symbol="EUR"
        ```

        ---
        Rate Limit Weight:
        ```python
        1
        ```

        ---
        Returns:
        ```python
        {
          "address": "CryptoCurrencyAddress",
          "paymentId": "10002653"
        }
        # or
        {
          "iban": "NL32BUNQ2291234129",
          "bic": "BUNQNL2A",
          "description": "254D20CC94"
        }
        ```
        """
        postfix = create_postfix({"symbol": symbol})
        return self.private_request("/deposit", postfix, {}, "GET")  # type: ignore[return-value]

    def deposit_history(self, options: anydict | None = None) -> list[anydict] | errordict:
        """Get the deposit history of the account

        Even when you want something from a single `symbol`, you'll still receive a list with multiple deposits.

        ---
        Args:
        ```python
        options={
            "symbol":"EUR"
            "limit": [ 1 .. 1000 ], default 500
            "start": int timestamp in ms >= 0
            "end": int timestamp in ms <= 8_640_000_000_000_000 # (that's somewhere in the year 2243, or near the number 2^52)
        }
        ```

        ---
        Rate Limit Weight:
        ```python
        5
        ```

        ---
        Returns:
        ```python
        [
          {
            "timestamp": 1542967486256,
            "symbol": "BTC",
            "amount": "0.99994",
            "address": "BitcoinAddress",
            "paymentId": "10002653",
            "txId": "927b3ea50c5bb52c6854152d305dfa1e27fc01d10464cf10825d96d69d235eb3",
            "fee": "0"
          }
        ]
        # or
        [
          {
            "timestamp": 1542967486256,
            "symbol": "BTC",
            "amount": "500",
            "address": "NL32BITV0001234567",
            "fee": "0"
          }
        ]
        ```
        """  # noqa: E501
        postfix = create_postfix(options)
        return self.private_request("/depositHistory", postfix, {}, "GET", 5)  # type: ignore[return-value]

    def withdraw_assets(self, symbol: str, amount: str, address: str, body: anydict) -> anydict:
        """Withdraw a coin/token to an external crypto address or bank account.

        ---
        Args:
        ```python
        symbol="SHIB"
        amount=10
        address="BitcoinAddress",  # Wallet address or IBAN
        options={
          "paymentId": "10002653",  # For digital assets only. Should be set when withdrawing straight to another exchange or merchants that require payment id's.
          "internal": false,  # For digital assets only. Should be set to true if the withdrawal must be sent to another Bitvavo user internally
          "addWithdrawalFee": false  # If set to true, the fee will be added on top of the requested amount, otherwise the fee is part of the requested amount and subtracted from the withdrawal.
        }
        ```

        ---
        Rate Limit Weight:
        ```python
        1
        ```

        ---
        Returns:
        ```python
        {
          "success": true,
          "symbol": "BTC",
          "amount": "1.5"
        }
        ```
        """  # noqa: E501
        body["symbol"] = symbol
        body["amount"] = amount
        body["address"] = address
        return self.private_request("/withdrawal", "", body, "POST")  # type: ignore[return-value]

    def withdrawal_history(
        self,
        options: anydict | None = None,
        output_format: OutputFormat = OutputFormat.DICT,
    ) -> list[anydict] | errordict | Any:
        """Get the withdrawal history

        ---
        Args:
        ```python
        options={
            "symbol":"SHIB"
            "limit": [ 1 .. 1000 ], default 500
            "start": int timestamp in ms >= 0
            "end": int timestamp in ms <= 8_640_000_000_000_000 # (that's somewhere in the year 2243, or near the number 2^52)
        }

        # Output format selection:
        output_format=OutputFormat.DICT      # Default: returns standard Python dict/list
        output_format=OutputFormat.PANDAS    # Returns pandas DataFrame
        output_format=OutputFormat.POLARS    # Returns polars DataFrame
        output_format=OutputFormat.CUDF      # Returns NVIDIA cuDF (GPU-accelerated)
        output_format=OutputFormat.MODIN     # Returns modin (distributed pandas)
        output_format=OutputFormat.PYARROW   # Returns Apache Arrow Table
        output_format=OutputFormat.DASK      # Returns Dask DataFrame (distributed)
        output_format=OutputFormat.DUCKDB    # Returns DuckDB relation
        output_format=OutputFormat.IBIS      # Returns Ibis expression
        output_format=OutputFormat.PYSPARK   # Returns PySpark DataFrame
        output_format=OutputFormat.PYSPARK_CONNECT  # Returns PySpark Connect DataFrame
        output_format=OutputFormat.SQLFRAME  # Returns SQLFrame DataFrame

        # Note: DataFrame formats require narwhals and the respective library to be installed.
        # Install with: pip install 'bitvavo-api-upgraded[pandas]' or similar for other formats.
        ```
        ---
        Rate Limit Weight:
        ```python
        5
        ```

        ---
        Returns:
        ```python
        [
          {
            "timestamp": 1542967486256,
            "symbol": "BTC",
            "amount": "0.99994",
            "address": "BitcoinAddress",
            "paymentId": "10002653",
            "txId": "927b3ea50c5bb52c6854152d305dfa1e27fc01d10464cf10825d96d69d235eb3",
            "fee": "0.00006",
            "status": "awaiting_processing"
          }
        ]
        ```
        """  # noqa: E501
        postfix = create_postfix(options)
        result = self.private_request("/withdrawalHistory", postfix, {}, "GET", 5)  # type: ignore[return-value]
        return convert_to_dataframe(result, output_format)

    # API Key Management Helper Methods

    def add_api_key(self, api_key: str, api_secret: str) -> None:
        """Add a new API key to the available keys.

        Args:
            api_key: The API key to add
            api_secret: The corresponding API secret
        """
        new_key = {"key": api_key, "secret": api_secret}
        self.api_keys.append(new_key)

        # Initialize rate limit tracking for this key using settings default
        key_index = len(self.api_keys) - 1
        default_rate_limit = bitvavo_upgraded_settings.DEFAULT_RATE_LIMIT
        self.rate_limits[key_index] = {"remaining": default_rate_limit, "resetAt": ms(0)}

        logger.info("api-key-added", key_index=key_index)

    def remove_api_key(self, api_key: str) -> bool:
        """Remove an API key from the available keys.

        Args:
            api_key: The API key to remove

        Returns:
            bool: True if the key was found and removed, False otherwise
        """
        for i, key_data in enumerate(self.api_keys):
            if key_data["key"] == api_key:
                _ = self.api_keys.pop(i)
                # Remove rate limit tracking for this key
                if i in self.rate_limits:
                    del self.rate_limits[i]
                # Update rate limit tracking indices (shift them down)
                new_rate_limits = {}
                for key_idx, limits in self.rate_limits.items():
                    if key_idx == -1 or key_idx < i:  # keyless
                        new_rate_limits[key_idx] = limits
                    elif key_idx > i:
                        new_rate_limits[key_idx - 1] = limits
                self.rate_limits = new_rate_limits

                # Update current index if needed
                if self.current_api_key_index >= i:
                    self.current_api_key_index = max(0, self.current_api_key_index - 1)

                logger.info("api-key-removed", key_index=i)
                return True
        return False

    def get_api_key_status(self) -> dict[str, dict[str, int | str | bool]]:
        """Get the current status of all API keys including rate limits.

        Returns:
            dict: Status information for keyless and all API keys
        """
        status = {}

        # Keyless status
        keyless_limits = self.rate_limits.get(-1, {"remaining": 0, "resetAt": ms(0)})
        status["keyless"] = {
            "remaining": int(keyless_limits["remaining"]),
            "resetAt": int(keyless_limits["resetAt"]),
            "available": self._has_rate_limit_available(-1, 1),
        }

        # API key status
        for i, key_data in enumerate(self.api_keys):
            key_limits = self.rate_limits.get(i, {"remaining": 0, "resetAt": ms(0)})
            KEY_LENGTH = 12
            key_masked = (
                key_data["key"][:8] + "..." + key_data["key"][-4:]
                if len(key_data["key"]) > KEY_LENGTH
                else key_data["key"]
            )
            status[f"api_key_{i}"] = {
                "key": key_masked,
                "remaining": int(key_limits["remaining"]),
                "resetAt": int(key_limits["resetAt"]),
                "available": self._has_rate_limit_available(i, 1),
            }

        return status

    def set_keyless_preference(self, prefer_keyless: bool) -> None:  # noqa: FBT001 (Boolean-typed positional argument in function definition)
        """Set whether to prefer keyless requests.

        Args:
            prefer_keyless: If True, use keyless requests first when available
        """
        self.prefer_keyless = prefer_keyless
        logger.info("keyless-preference-changed", prefer_keyless=prefer_keyless)

    def get_current_config(self) -> dict[str, str | bool | int]:
        """Get the current configuration.

        Returns:
            dict: Current configuration including key count and preferences
        """
        KEY_LENGTH = 12
        return {
            "api_key_count": len(self.api_keys),
            "prefer_keyless": self.prefer_keyless,
            "current_api_key_index": self.current_api_key_index,
            "current_api_key": self._current_api_key[:8] + "..." + self._current_api_key[-4:]
            if len(self._current_api_key) > KEY_LENGTH
            else self._current_api_key,
            "rate_limit_remaining": self.rateLimitRemaining,
            "rate_limit_reset_at": int(self.rateLimitResetAt),
        }

    def new_websocket(self) -> Bitvavo.WebSocketAppFacade:
        return Bitvavo.WebSocketAppFacade(self.APIKEY, self.APISECRET, self.ACCESSWINDOW, self.wsUrl, self)

    class WebSocketAppFacade:
        """
        I gave this 'websocket' class a better name: WebSocketAppFacade.

        It's a facade for the WebSocketApp class, with its own implementation for the on_* methods
        """

        def __init__(
            self,
            APIKEY: str,
            APISECRET: str,
            ACCESSWINDOW: int,
            WSURL: str,
            bitvavo: Bitvavo,
        ) -> None:
            self.APIKEY = APIKEY
            self.APISECRET = APISECRET
            self.ACCESSWINDOW = ACCESSWINDOW
            self.WSURL = WSURL
            self.open = False
            self.callbacks: anydict = {}
            self.keepAlive = True
            self.reconnect = False
            self.reconnectTimer: s_f = 0.1
            self.bitvavo = bitvavo

            self.subscribe()

        def subscribe(self) -> None:
            ws_lib.enableTrace(False)
            self.ws = WebSocketApp(
                self.WSURL,
                on_message=self.on_message,
                on_error=self.on_error,
                on_close=self.on_close,
                on_open=self.on_open,
            )

            self.receiveThread = ReceiveThread(self.ws, self)
            self.receiveThread.daemon = True
            self.receiveThread.start()

            self.authenticated = False
            self.keepBookCopy = False
            self.localBook: anydict = {}

        def close_socket(self) -> None:
            self.ws.close()
            self.keepAlive = False
            self.receiveThread.join()

        def wait_for_socket(self, ws: WebSocketApp, message: str, private: bool) -> None:  # noqa: ARG002, FBT001
            while self.keepAlive:
                if (not private and self.open) or (private and self.authenticated and self.open):
                    return
                time.sleep(0.1)

        def do_send(self, ws: WebSocketApp, message: str, private: bool = False) -> None:  # noqa: FBT001, FBT002
            # TODO(NostraDavid): add nap-time to the websocket, or do it here; I don't know yet.
            if private and self.APIKEY == "":
                logger.error(
                    "no-apikey",
                    tip="set the API key to be able to make private API calls",
                )
                return
            self.wait_for_socket(ws, message, private)
            ws.send(message)
            if self.bitvavo.debugging:
                logger.debug("message-sent", message=message)

        def on_message(self, ws: Any, msg: str) -> None:  # noqa: C901, PLR0912, PLR0915, ARG002 (too-complex)
            if self.bitvavo.debugging:
                logger.debug("message-received", message=msg)
            msg_dict: anydict = json.loads(msg)
            callbacks = self.callbacks

            if "error" in msg_dict:
                if msg_dict["errorCode"] == 105:  # noqa: PLR2004
                    self.bitvavo.update_rate_limit(msg_dict)
                if "error" in callbacks:
                    callbacks["error"](msg_dict)
                else:
                    logger.error("error", msg_dict=msg_dict)

            if "action" in msg_dict:
                if msg_dict["action"] == "getTime":
                    callbacks["time"](msg_dict["response"])
                elif msg_dict["action"] == "getMarkets":
                    callbacks["markets"](msg_dict["response"])
                elif msg_dict["action"] == "getAssets":
                    callbacks["assets"](msg_dict["response"])
                elif msg_dict["action"] == "getTrades":
                    callbacks["publicTrades"](msg_dict["response"])
                elif msg_dict["action"] == "getCandles":
                    callbacks["candles"](msg_dict["response"])
                elif msg_dict["action"] == "getTicker24h":
                    callbacks["ticker24h"](msg_dict["response"])
                elif msg_dict["action"] == "getTickerPrice":
                    callbacks["tickerPrice"](msg_dict["response"])
                elif msg_dict["action"] == "getTickerBook":
                    callbacks["tickerBook"](msg_dict["response"])
                elif msg_dict["action"] == "privateCreateOrder":
                    callbacks["placeOrder"](msg_dict["response"])
                elif msg_dict["action"] == "privateUpdateOrder":
                    callbacks["updateOrder"](msg_dict["response"])
                elif msg_dict["action"] == "privateGetOrder":
                    callbacks["getOrder"](msg_dict["response"])
                elif msg_dict["action"] == "privateCancelOrder":
                    callbacks["cancelOrder"](msg_dict["response"])
                elif msg_dict["action"] == "privateGetOrders":
                    callbacks["getOrders"](msg_dict["response"])
                elif msg_dict["action"] == "privateGetOrdersOpen":
                    callbacks["ordersOpen"](msg_dict["response"])
                elif msg_dict["action"] == "privateGetTrades":
                    callbacks["trades"](msg_dict["response"])
                elif msg_dict["action"] == "privateGetAccount":
                    callbacks["account"](msg_dict["response"])
                elif msg_dict["action"] == "privateGetFees":
                    callbacks["fees"](msg_dict["response"])
                elif msg_dict["action"] == "privateGetBalance":
                    callbacks["balance"](msg_dict["response"])
                elif msg_dict["action"] == "privateDepositAssets":
                    callbacks["depositAssets"](msg_dict["response"])
                elif msg_dict["action"] == "privateWithdrawAssets":
                    callbacks["withdrawAssets"](msg_dict["response"])
                elif msg_dict["action"] == "privateGetDepositHistory":
                    callbacks["depositHistory"](msg_dict["response"])
                elif msg_dict["action"] == "privateGetWithdrawalHistory":
                    callbacks["withdrawalHistory"](msg_dict["response"])
                elif msg_dict["action"] == "privateCancelOrders":
                    callbacks["cancelOrders"](msg_dict["response"])
                elif msg_dict["action"] == "getBook":
                    market = msg_dict["response"]["market"]
                    if "book" in callbacks:
                        callbacks["book"](msg_dict["response"])
                    if self.keepBookCopy and market in callbacks["subscriptionBook"]:
                        callbacks["subscriptionBook"][market](self, msg_dict)

            elif "event" in msg_dict:
                if msg_dict["event"] == "authenticate":
                    self.authenticated = True
                elif msg_dict["event"] == "fill" or msg_dict["event"] == "order":
                    market = msg_dict["market"]
                    callbacks["subscriptionAccount"][market](msg_dict)
                elif msg_dict["event"] == "ticker":
                    market = msg_dict["market"]
                    callbacks["subscriptionTicker"][market](msg_dict)
                elif msg_dict["event"] == "ticker24h":
                    for entry in msg_dict["data"]:
                        callbacks["subscriptionTicker24h"][entry["market"]](entry)
                elif msg_dict["event"] == "candle":
                    market = msg_dict["market"]
                    interval = msg_dict["interval"]
                    callbacks["subscriptionCandles"][market][interval](msg_dict)
                elif msg_dict["event"] == "book":
                    market = msg_dict["market"]
                    if "subscriptionBookUpdate" in callbacks and market in callbacks["subscriptionBookUpdate"]:
                        callbacks["subscriptionBookUpdate"][market](msg_dict)
                    if self.keepBookCopy and market in callbacks["subscriptionBook"]:
                        callbacks["subscriptionBook"][market](self, msg_dict)
                elif msg_dict["event"] == "trade":
                    market = msg_dict["market"]
                    if "subscriptionTrades" in callbacks:
                        callbacks["subscriptionTrades"][market](msg_dict)

        def on_error(self, ws: Any, error: Any) -> None:  # noqa: ARG002
            # Stop the receive thread on error to prevent hanging
            self.receiveThread.stop()
            if "error" in self.callbacks:
                self.callbacks["error"](error)
            else:
                logger.error(error)

        def on_close(self, ws: Any) -> None:  # noqa: ARG002
            self.receiveThread.stop()
            if self.bitvavo.debugging:
                logger.debug("websocket-closed")

        def check_reconnect(self) -> None:  # noqa: C901, PLR0912 (too-complex)
            if "subscriptionTicker" in self.callbacks:
                for market in self.callbacks["subscriptionTicker"]:
                    self.subscription_ticker(market, self.callbacks["subscriptionTicker"][market])
            if "subscriptionTicker24h" in self.callbacks:
                for market in self.callbacks["subscriptionTicker24h"]:
                    self.subscription_ticker(market, self.callbacks["subscriptionTicker24h"][market])
            if "subscriptionAccount" in self.callbacks:
                for market in self.callbacks["subscriptionAccount"]:
                    self.subscription_account(market, self.callbacks["subscriptionAccount"][market])
            if "subscriptionCandles" in self.callbacks:
                for market in self.callbacks["subscriptionCandles"]:
                    for interval in self.callbacks["subscriptionCandles"][market]:
                        self.subscription_candles(
                            market,
                            interval,
                            self.callbacks["subscriptionCandles"][market][interval],
                        )
            if "subscriptionTrades" in self.callbacks:
                for market in self.callbacks["subscriptionTrades"]:
                    self.subscription_trades(market, self.callbacks["subscriptionTrades"][market])
            if "subscriptionBookUpdate" in self.callbacks:
                for market in self.callbacks["subscriptionBookUpdate"]:
                    self.subscription_book_update(market, self.callbacks["subscriptionBookUpdate"][market])
            if "subscriptionBookUser" in self.callbacks:
                for market in self.callbacks["subscriptionBookUser"]:
                    self.subscription_book(market, self.callbacks["subscriptionBookUser"][market])

        def on_open(self, ws: Any) -> None:  # noqa: ARG002
            now = time_ms() + bitvavo_upgraded_settings.LAG
            self.open = True
            self.reconnectTimer = 0.5
            if self.APIKEY != "":
                self.do_send(
                    self.ws,
                    json.dumps(
                        {
                            "window": str(self.ACCESSWINDOW),
                            "action": "authenticate",
                            "key": self.APIKEY,
                            "signature": create_signature(now, "GET", "/websocket", {}, self.APISECRET),
                            "timestamp": now,
                        },
                    ),
                )
            if self.reconnect:
                if self.bitvavo.debugging:
                    logger.debug("reconnecting")
                thread = Thread(target=self.check_reconnect)
                thread.start()

        def set_error_callback(self, callback: Callable[[Any], None]) -> None:
            self.callbacks["error"] = callback

        def time(self, callback: Callable[[Any], None]) -> None:
            """Get server-time, in milliseconds, since 1970-01-01

            ---
            Non-websocket examples:
            * https://api.bitvavo.com/v2/time

            ---
            Args:
            ```python
            callback=callback_example
            ```
            ---
            Rate Limit Weight:
            ```python
            1
            ```

            ---
            Returns this to `callback`:
            ```python
            {"time": 1539180275424 }
            ```
            """
            self.callbacks["time"] = callback
            self.do_send(self.ws, json.dumps({"action": "getTime"}))

        def markets(self, options: anydict, callback: Callable[[Any], None]) -> None:
            """Get all available markets with some meta-information, unless options is given a `market` key.
            Then you will get a single market, instead of a list of markets.

            ---
            Examples:
            * https://api.bitvavo.com/v2/markets
            * https://api.bitvavo.com/v2/markets?market=BTC-EUR
            * https://api.bitvavo.com/v2/markets?market=SHIB-EUR

            ---
            Args:
            ```python
            # Choose one:
            options={}  # returns all markets
            options={"market": "BTC-EUR"}  # returns only the BTC-EUR market
            # If you want multiple markets, but not all, make multiple calls
            callback=callback_example
            ```

            ---
            Rate Limit Weight:
            ```python
            1
            ```

            ---
            Returns this to `callback`:
            ```python
            [
              {
                "market": "BTC-EUR",
                "status": "trading",
                "base": "BTC",
                "quote": "EUR",
                "pricePrecision": "5",
                "minOrderInQuoteAsset": "10",
                "minOrderInBaseAsset": "0.001",
                "orderTypes": [
                "market",
                "limit",
                "stopLoss",
                "stopLossLimit",
                "takeProfit",
                "takeProfitLimit"
                ]
              }
            ]
            ```
            """
            self.callbacks["markets"] = callback
            options["action"] = "getMarkets"
            self.do_send(self.ws, json.dumps(options))

        def assets(self, options: anydict, callback: Callable[[Any], None]) -> None:
            """Get all available assets, unless `options` is given a `symbol` key.
            Then you will get a single asset, instead of a list of assets.

            ---
            Examples:
            * https://api.bitvavo.com/v2/assets
            * https://api.bitvavo.com/v2/assets?symbol=BTC
            * https://api.bitvavo.com/v2/assets?symbol=SHIB
            * https://api.bitvavo.com/v2/assets?symbol=ADA
            * https://api.bitvavo.com/v2/assets?symbol=EUR

            ---
            Args:
            ```python
            # pick one
            options={}  # returns all assets
            options={"symbol": "BTC"} # returns a single asset (the one of Bitcoin)
            callback=callback_example
            ```

            ---
            Rate Limit Weight:
            ```python
            1
            ```

            ---
            Returns this to `callback`:
            ```python
            [
              {
                "symbol": "BTC",
                "name": "Bitcoin",
                "decimals": 8,
                "depositFee": "0",
                "depositConfirmations": 10,
                "depositStatus": "OK",
                "withdrawalFee": "0.2",
                "withdrawalMinAmount": "0.2",
                "withdrawalStatus": "OK",
                "networks": ["Mainnet"],
                "message": ""
              }
            ]
            ```
            """
            self.callbacks["assets"] = callback
            options["action"] = "getAssets"
            self.do_send(self.ws, json.dumps(options))

        def book(self, market: str, options: anydict, callback: Callable[[Any], None]) -> None:
            """Get a book (with two lists: asks and bids, as they're called)

            ---
            Examples:
            * https://api.bitvavo.com/v2/BTC-EUR/book
            * https://api.bitvavo.com/v2/SHIB-EUR/book?depth=10
            * https://api.bitvavo.com/v2/ADA-EUR/book?depth=0

            ---
            Args:
            ```python
            market="ADA-EUR"
            options={"depth": 3}  # returns the best 3 asks and 3 bids
            options={}  # same as `{"depth": 0}`; returns all bids and asks for that book
            callback=callback_example
            ```

            ---
            Rate Limit Weight:
            ```python
            1
            ```

            ---
            Returns this to `callback`:
            ```python
            {
                "market": "ADA-EUR",
                "nonce": 10378032,
                "bids": [["1.1908", "600"], ["1.1902", "4091.359809"], ["1.1898", "7563"]],
                "asks": [["1.1917", "2382.166997"], ["1.1919", "440.7"], ["1.192", "600"]],
            }

            # Notice how each bid and ask is also a list
            bid = ["1.1908", "600"]  # the first bid from the bids list
            price = bid[0] # the price for one coin/token
            size = bid[1]  # how many tokens are asked (or bidded, in this case)
            result = price * size
            assert result == 714.48  # EUR can be gained from this bid if it's sold (minus the fee)
            ```
            """
            self.callbacks["book"] = callback
            options["market"] = market
            options["action"] = "getBook"
            self.do_send(self.ws, json.dumps(options))

        def publicTrades(self, market: str, options: anydict, callback: Callable[[Any], None]) -> None:
            """Publically available trades

            ---
            Examples:
            * https://api.bitvavo.com/v2/BTC-EUR/trades
            * https://api.bitvavo.com/v2/SHIB-EUR/trades?limit=10
            * https://api.bitvavo.com/v2/ADA-EUR/trades?tradeIdFrom=532f4d4d-f545-4a2d-a175-3d37919cb73c
            * https://api.bitvavo.com/v2/NANO-EUR/trades

            ---
            Args:
            ```python
            market="NANO-EUR"
            # note that any of these `options` are optional
            # use `int(time.time() * 1000)` to get current timestamp in milliseconds
            # or `int(datetime.datetime.now().timestamp()*1000)`
            options={
                "limit": [ 1 .. 1000 ], default 500
                "start": int timestamp in ms >= 0
                "end": int timestamp in ms <= 8_640_000_000_000_000 # (that's somewhere in the year 2243, or near the number 2^52)
                "tradeIdFrom": ""  # if you get a list and want everything AFTER a certain id, put that id here
                "tradeIdTo": ""  # if you get a list and want everything BEFORE a certain id, put that id here
            }
            callback=callback_example
            ```

            ---
            Rate Limit Weight:
            ```python
            5
            ```

            ---
            Returns this to `callback`:
            ```python
            [
              {
                "timestamp": 1542967486256,
                "id": "57b1159b-6bf5-4cde-9e2c-6bd6a5678baf",
                "amount": "0.1",
                "price": "5012",
                "side": "sell"
              }
            ]
            ```
            """  # noqa: E501
            self.callbacks["publicTrades"] = callback
            options["market"] = market
            options["action"] = "getTrades"
            self.do_send(self.ws, json.dumps(options))

        def candles(
            self,
            market: str,
            interval: str,
            options: anydict,
            callback: Callable[[Any], None],
        ) -> None:
            """Get up to 1440 candles for a market, with a specific interval (candle size)

            Extra reading material: https://en.wikipedia.org/wiki/Candlestick_chart

            ## WARNING: RETURN TYPE IS WEIRD - CHECK BOTTOM OF THIS TEXT FOR EXPLANATION

            ---
            Examples:
            * https://api.bitvavo.com/v2/BTC-EUR/candles?interval=1h&limit=100

            ---
            Args:
            ```python
            market="BTC-EUR"
            interval="1h"  # Choose: 1m, 5m, 15m, 30m, 1h, 2h, 4h, 6h, 8h, 12h, 1d
            # use `int(time.time() * 1000)` to get current timestamp in milliseconds
            # or `int(datetime.datetime.now().timestamp()*1000)`
            options={
                "limit": [ 1 .. 1440 ], default 1440
                "start": int timestamp in ms >= 0
                "end": int timestamp in ms <= 8640000000000000
            }
            callback=callback_example
            ```

            ---
            Rate Limit Weight:
            ```python
            1
            ```

            ---
            Returns this to `callback`:
            ```python
            [
                # For whatever reason, you're getting a list of lists; no keys,
                # so here is the explanation of what's what.
                # timestamp,     open,    high,    low,     close,   volume
                [1640815200000, "41648", "41859", "41519", "41790", "12.1926685"],
                [1640811600000, "41771", "41780", "41462", "41650", "13.90917427"],
                [1640808000000, "41539", "42083", "41485", "41771", "14.39770267"],
                [1640804400000, "41937", "41955", "41449", "41540", "23.64498292"],
                [1640800800000, "41955", "42163", "41807", "41939", "10.40093845"],
            ]
            ```
            """
            self.callbacks["candles"] = callback
            options["market"] = market
            options["interval"] = interval
            options["action"] = "getCandles"
            self.do_send(self.ws, json.dumps(options))

        def ticker_price(self, options: anydict, callback: Callable[[Any], None]) -> None:
            """Get the current price for each market

            ---
            Examples:
            * https://api.bitvavo.com/v2/ticker/price
            * https://api.bitvavo.com/v2/ticker/price?market=BTC-EUR
            * https://api.bitvavo.com/v2/ticker/price?market=ADA-EUR
            * https://api.bitvavo.com/v2/ticker/price?market=SHIB-EUR
            * https://api.bitvavo.com/v2/ticker/price?market=DOGE-EUR
            * https://api.bitvavo.com/v2/ticker/price?market=NANO-EUR

            ---
            Args:
            ```python
            options={}
            options={"market": "BTC-EUR"}
            callback=callback_example
            ```

            ---
            Rate Limit Weight:
            ```python
            1
            ```

            ---
            Returns this to `callback`:
            ```python
            # Note that `price` is unconverted
            [
                {"market": "1INCH-EUR", "price": "2.1594"},
                {"market": "AAVE-EUR", "price": "214.42"},
                {"market": "ADA-BTC", "price": "0.000021401"},
                {"market": "ADA-EUR", "price": "1.2011"},
                {"market": "ADX-EUR", "price": "0.50357"},
                {"market": "AE-BTC", "price": "0.0000031334"},
                {"market": "AE-EUR", "price": "0.064378"},
                {"market": "AION-BTC", "price": "0.000004433"},
                {"market": "AION-EUR", "price": "0.1258"},
                {"market": "AKRO-EUR", "price": "0.020562"},
                {"market": "ALGO-EUR", "price": "1.3942"},
                # and another 210 markets below this point
            ]
            ```
            """
            self.callbacks["tickerPrice"] = callback
            options["action"] = "getTickerPrice"
            self.do_send(self.ws, json.dumps(options))

        def ticker_book(self, options: anydict, callback: Callable[[Any], None]) -> None:
            """Get current bid/ask, bidsize/asksize per market

            ---
            Examples:
            * https://api.bitvavo.com/v2/ticker/book
            * https://api.bitvavo.com/v2/ticker/book?market=BTC-EUR
            * https://api.bitvavo.com/v2/ticker/book?market=ADA-EUR
            * https://api.bitvavo.com/v2/ticker/book?market=SHIB-EUR
            * https://api.bitvavo.com/v2/ticker/book?market=DOGE-EUR
            * https://api.bitvavo.com/v2/ticker/book?market=NANO-EUR

            ---
            Args:
            ```python
            options={}
            options={"market": "BTC-EUR"}
            callback=callback_example
            ```

            ---
            Rate Limit Weight:
            ```python
            1
            ```

            ---
            Returns this to `callback`:
            ```python
            [
                {"market": "1INCH-EUR", "bid": "2.1534", "ask": "2.1587", "bidSize": "194.8", "askSize": "194.8"},
                {"market": "AAVE-EUR", "bid": "213.7", "ask": "214.05", "bidSize": "212.532", "askSize": "4.77676965"},
                {"market": "ADA-EUR", "bid": "1.2", "ask": "1.2014", "bidSize": "415.627597", "askSize": "600"},
                {"market": "ADX-EUR", "bid": "0.49896", "ask": "0.50076", "bidSize": "1262.38216882", "askSize": "700.1"},
                {"market": "AION-EUR", "bid": "0.12531", "ask": "0.12578", "bidSize": "3345", "askSize": "10958.49228653"},
                # and another 215 markets below this point
            ]
            ```
            """  # noqa: E501
            self.callbacks["tickerBook"] = callback
            options["action"] = "getTickerBook"
            self.do_send(self.ws, json.dumps(options))

        def ticker24h(self, options: anydict, callback: Callable[[Any], None]) -> None:
            """Get current bid/ask, bidsize/asksize per market

            ---
            Examples:
            * https://api.bitvavo.com/v2/ticker/24h
            * https://api.bitvavo.com/v2/ticker/24h?market=BTC-EUR
            * https://api.bitvavo.com/v2/ticker/24h?market=ADA-EUR
            * https://api.bitvavo.com/v2/ticker/24h?market=SHIB-EUR
            * https://api.bitvavo.com/v2/ticker/24h?market=DOGE-EUR
            * https://api.bitvavo.com/v2/ticker/24h?market=NANO-EUR

            ---
            Args:
            ```python
            options={}
            options={"market": "BTC-EUR"}
            callback=callback_example
            ```

            ---
            Rate Limit Weight:
            ```python
            25  # if no market option is used
            1  # if a market option is used
            ```

            ---
            Returns this to `callback`:
            ```python
            [
              {
                "market": "1INCH-EUR",
                "open": "2.2722",
                "high": "2.2967",
                "low": "2.1258",
                "last": "2.1552",
                "volume": "92921.3792573",
                "volumeQuote": "204118.95",
                "bid": "2.1481",
                "bidSize": "392.46514457",
                "ask": "2.1513",
                "askSize": "195.3",
                "timestamp": 1640819573777
              },
              {
                "market": "AAVE-EUR",
                "open": "224.91",
                "high": "228.89",
                "low": "210.78",
                "last": "213.83",
                "volume": "5970.52391148",
                "volumeQuote": "1307777.47",
                "bid": "213.41",
                "bidSize": "2.61115011",
                "ask": "213.85",
                "askSize": "1.864",
                "timestamp": 1640819573285
              },
              # and then 219 more markets
            ]
            ```
            """
            self.callbacks["ticker24h"] = callback
            options["action"] = "getTicker24h"
            self.do_send(self.ws, json.dumps(options))

        def place_order(
            self,
            market: str,
            side: str,
            orderType: str,
            operatorId: int,
            body: anydict,
            callback: Callable[[Any], None],
        ) -> None:
            """Place a new order on the exchange

            ---
            Args:
            ```python
            market="SHIB-EUR"
            side="buy" # Choose: buy, sell
            # For market orders either `amount` or `amountQuote` is required
            orderType="market"  # Choose: market, limit, stopLoss, stopLossLimit, takeProfit, takeProfitLimit
            operatorId=123  # Your identifier for the trader or bot that made the request
            body={
              "amount": "1.567",
              "amountQuote": "5000",
              "clientOrderId": "2be7d0df-d8dc-7b93-a550-8876f3b393e9",  # Optional: your identifier for the order
              # GTC orders will remain on the order book until they are filled or canceled.
              # IOC orders will fill against existing orders, but will cancel any remaining amount after that.
              # FOK orders will fill against existing orders in its entirety, or will be canceled (if the entire order cannot be filled).
              "timeInForce": "GTC",  # Choose: GTC, IOC, FOK. Good-Til-Canceled (GTC), Immediate-Or-Cancel (IOC), Fill-Or-Kill (FOK)
              # 'decrementAndCancel' decrements both orders by the amount that would have been filled, which in turn cancels the smallest of the two orders.
              # 'cancelOldest' will cancel the entire older order and places the new order.
              # 'cancelNewest' will cancel the order that is submitted.
              # 'cancelBoth' will cancel both the current and the old order.
              "selfTradePrevention": "decrementAndCancel",  # decrementAndCancel, cancelOldest, cancelNewest, cancelBoth
              "disableMarketProtection": false,
              "responseRequired": true  # setting this to `false` will return only an 'acknowledged', and be faster
            }

            # For limit orders `amount` and `price` are required.
            orderType="limit"  # Choose: market, limit, stopLoss, stopLossLimit, takeProfit, takeProfitLimit
            operatorId=123
            body={
              "amount": "1.567",
              "price": "6000",
              "timeInForce": "GTC",  # GTC, IOC, FOK. Good-Til-Canceled (GTC), Immediate-Or-Cancel (IOC), Fill-Or-Kill (FOK)
              "selfTradePrevention": "decrementAndCancel",  # decrementAndCancel, cancelOldest, cancelNewest, cancelBoth
              "postOnly": false,  # Only for limit orders
              "responseRequired": True
            }

            orderType="stopLoss"
            # or
            orderType="takeProfit"
            operatorId=123
            body={
              "amount": "1.567",
              "amountQuote": "5000",
              "triggerAmount": "4000",
              "triggerType": "price",
              "triggerReference": "lastTrade",
              "timeInForce": "GTC",  # GTC, IOC, FOK. Good-Til-Canceled (GTC), Immediate-Or-Cancel (IOC), Fill-Or-Kill (FOK)
              "selfTradePrevention": "decrementAndCancel",  # decrementAndCancel, cancelOldest, cancelNewest, cancelBoth
              "disableMarketProtection": false,
              "responseRequired": true
            }

            orderType="stopLossLimit"
            # or
            orderType="takeProfitLimit"
            operatorId=123
            body={
              "amount": "1.567",
              "price": "6000",
              "triggerAmount": "4000",
              "triggerType": "price",
              "triggerReference": "lastTrade",
              "timeInForce": "GTC",  # GTC, IOC, FOK. Good-Til-Canceled (GTC), Immediate-Or-Cancel (IOC), Fill-Or-Kill (FOK)
              "selfTradePrevention": "decrementAndCancel",  # decrementAndCancel, cancelOldest, cancelNewest, cancelBoth
              "postOnly": false,  # Only for limit orders
              "responseRequired": true
            }
            callback=callback_example
            ```

            ---
            Rate Limit Weight:
            ```python
            1
            ```

            ---
            Returns this to `callback`:
            ```python
            {
              "orderId": "1be6d0df-d5dc-4b53-a250-3376f3b393e6",
              "market": "BTC-EUR",
              "created": 1542621155181,
              "updated": 1542621155181,
              "status": "new",
              "side": "buy",
              "orderType": "limit",
              "amount": "10",
              "amountRemaining": "10",
              "price": "7000",
              "amountQuote": "5000",
              "amountQuoteRemaining": "5000",
              "onHold": "9109.61",
              "onHoldCurrency": "BTC",
              "triggerPrice": "4000",
              "triggerAmount": "4000",
              "triggerType": "price",
              "triggerReference": "lastTrade",
              "filledAmount": "0",
              "filledAmountQuote": "0",
              "feePaid": "0",
              "feeCurrency": "EUR",
              "fills": [
                {
                  "id": "371c6bd3-d06d-4573-9f15-18697cd210e5",
                  "timestamp": 1542967486256,
                  "amount": "0.005",
                  "price": "5000.1",
                  "taker": true,
                  "fee": "0.03",
                  "feeCurrency": "EUR",
                  "settled": true
                }
              ],
              "selfTradePrevention": "decrementAndCancel",
              "visible": true,
              "timeInForce": "GTC",
              "postOnly": false,
              "disableMarketProtection": true
            }
            ```
            """  # noqa: E501
            self.callbacks["placeOrder"] = callback
            body["market"] = market
            body["side"] = side
            body["orderType"] = orderType
            body["operatorId"] = operatorId
            body["action"] = "privateCreateOrder"
            self.do_send(self.ws, json.dumps(body), True)

        def update_order(
            self,
            market: str,
            orderId: str,
            operatorId: int,
            body: anydict,
            callback: Callable[[Any], None],
        ) -> None:
            """
            Update an existing order for a specific market. Make sure that at least one of the optional parameters
            is set, otherwise nothing will be updated.

            ---
            Args:
            ```python
            market="BTC-EUR"
            orderId="95d92d6c-ecf0-4960-a608-9953ef71652e"
            operatorId=123  # Your identifier for the trader or bot that made the request
            body={
              "amount": "1.567",
              "amountRemaining": "1.567",
              "price": "6000",
              "triggerAmount": "4000",  # only for stop orders
              "clientOrderId": "2be7d0df-d8dc-7b93-a550-8876f3b393e9",  # Optional: your identifier for the order
              # GTC orders will remain on the order book until they are filled or canceled.
              # IOC orders will fill against existing orders, but will cancel any remaining amount after that.
              # FOK orders will fill against existing orders in its entirety, or will be canceled (if the entire order cannot be filled).
              "timeInForce": "GTC",  # Choose: GTC, IOC, FOK. Good-Til-Canceled (GTC), Immediate-Or-Cancel (IOC), Fill-Or-Kill (FOK)
              # 'decrementAndCancel' decrements both orders by the amount that would have been filled, which in turn cancels the smallest of the two orders.
              # 'cancelOldest' will cancel the entire older order and places the new order.
              # 'cancelNewest' will cancel the order that is submitted.
              # 'cancelBoth' will cancel both the current and the old order.
              "selfTradePrevention": "decrementAndCancel",  # decrementAndCancel, cancelOldest, cancelNewest, cancelBoth
              "postOnly": false,  # Only for limit orders
              "responseRequired": true  # setting this to `false` will return only an 'acknowledged', and be faster
            }
            callback=callback_example
            ```

            ---
            Rate Limit Weight:
            ```python
            1
            ```

            ---
            Returns this to `callback`:
            ```python
            {
              "orderId": "1be6d0df-d5dc-4b53-a250-3376f3b393e6",
              "market": "BTC-EUR",
              "created": 1542621155181,
              "updated": 1542621155181,
              "status": "new",
              "side": "buy",
              "orderType": "limit",
              "amount": "10",
              "amountRemaining": "10",
              "price": "7000",
              "amountQuote": "5000",
              "amountQuoteRemaining": "5000",
              "onHold": "9109.61",
              "onHoldCurrency": "BTC",
              "triggerPrice": "4000",
              "triggerAmount": "4000",
              "triggerType": "price",
              "triggerReference": "lastTrade",
              "filledAmount": "0",
              "filledAmountQuote": "0",
              "feePaid": "0",
              "feeCurrency": "EUR",
              "fills": [
                {
                  "id": "371c6bd3-d06d-4573-9f15-18697cd210e5",
                  "timestamp": 1542967486256,
                  "amount": "0.005",
                  "price": "5000.1",
                  "taker": true,
                  "fee": "0.03",
                  "feeCurrency": "EUR",
                  "settled": true
                }
              ],
              "selfTradePrevention": "decrementAndCancel",
              "visible": true,
              "timeInForce": "GTC",
              "postOnly": true,
              "disableMarketProtection": true
            }
            ```
            """  # noqa: E501
            self.callbacks["updateOrder"] = callback
            body["market"] = market
            body["orderId"] = orderId
            body["operatorId"] = operatorId
            body["action"] = "privateUpdateOrder"
            self.do_send(self.ws, json.dumps(body), True)

        def cancel_order(
            self,
            market: str,
            operatorId: int,
            callback: Callable[[Any], None],
            orderId: str | None = None,
            clientOrderId: str | None = None,
        ) -> None:
            """Cancel an existing order for a specific market

            ---
            Args:
            ```python
            market="BTC-EUR"
            operatorId=123  # Your identifier for the trader or bot that made the request
            callback=callback_example
            orderId="a4a5d310-687c-486e-a3eb-1df832405ccd"  # Either orderId or clientOrderId required
            clientOrderId="2be7d0df-d8dc-7b93-a550-8876f3b393e9"  # Either orderId or clientOrderId required
            # If both orderId and clientOrderId are provided, clientOrderId takes precedence
            ```

            ---
            Rate Limit Weight:
            ```python
            N/A
            ```

            ---
            Returns this to `callback`:
            ```python
            {"orderId": "2e7ce7fc-44e2-4d80-a4a7-d079c4750b61"}
            ```
            """
            if orderId is None and clientOrderId is None:
                msg = "Either orderId or clientOrderId must be provided"
                raise ValueError(msg)

            self.callbacks["cancelOrder"] = callback
            options = {
                "action": "privateCancelOrder",
                "market": market,
                "operatorId": operatorId,
            }

            # clientOrderId takes precedence if both are provided
            if clientOrderId is not None:
                options["clientOrderId"] = clientOrderId
            elif orderId is not None:
                options["orderId"] = orderId

            self.do_send(self.ws, json.dumps(options), True)

        def get_order(self, market: str, orderId: str, callback: Callable[[Any], None]) -> None:
            """Get an existing order for a specific market

            ---
            Args:
            ```python
            market="BTC-EUR"
            orderId="ff403e21-e270-4584-bc9e-9c4b18461465"
            callback=callback_example
            ```

            ---
            Rate Limit Weight:
            ```python
            1
            ```

            ---
            Returns this to `callback`:
            ```python
            {
              "orderId": "1be6d0df-d5dc-4b53-a250-3376f3b393e6",
              "market": "BTC-EUR",
              "created": 1542621155181,
              "updated": 1542621155181,
              "status": "new",
              "side": "buy",
              "orderType": "limit",
              "amount": "10",
              "amountRemaining": "10",
              "price": "7000",
              "amountQuote": "5000",
              "amountQuoteRemaining": "5000",
              "onHold": "9109.61",
              "onHoldCurrency": "BTC",
              "triggerPrice": "4000",
              "triggerAmount": "4000",
              "triggerType": "price",
              "triggerReference": "lastTrade",
              "filledAmount": "0",
              "filledAmountQuote": "0",
              "feePaid": "0",
              "feeCurrency": "EUR",
              "fills": [
                {
                  "id": "371c6bd3-d06d-4573-9f15-18697cd210e5",
                  "timestamp": 1542967486256,
                  "amount": "0.005",
                  "price": "5000.1",
                  "taker": true,
                  "fee": "0.03",
                  "feeCurrency": "EUR",
                  "settled": true
                }
              ],
              "selfTradePrevention": "decrementAndCancel",
              "visible": true,
              "timeInForce": "GTC",
              "postOnly": true,
              "disableMarketProtection": true
            }
            ```
            """
            self.callbacks["getOrder"] = callback
            options = {
                "action": "privateGetOrder",
                "market": market,
                "orderId": orderId,
            }
            self.do_send(self.ws, json.dumps(options), True)

        def get_orders(self, market: str, options: anydict, callback: Callable[[Any], None]) -> None:
            """Get multiple existing orders for a specific market

            ---
            Args:
            ```python
            market="BTC-EUR"
            options={
                "limit": [ 1 .. 1000 ], default 500
                "start": int timestamp in ms >= 0
                # (that's somewhere in the year 2243, or near the number 2^52)
                "end": int timestamp in ms <= 8_640_000_000_000_000
                # if you get a list and want everything AFTER a certain id, put that id here
                "tradeIdFrom": ""
                # if you get a list and want everything BEFORE a certain id, put that id here
                "tradeIdTo": ""
            }
            callback=callback_example
            ```

            ---
            Rate Limit Weight:
            ```python
            5
            ```

            ---
            Returns this to `callback`:
            ```python
            # A whole list of these
            [
              {
                "orderId": "1be6d0df-d5dc-4b53-a250-3376f3b393e6",
                "market": "BTC-EUR",
                "created": 1542621155181,
                "updated": 1542621155181,
                "status": "new",
                "side": "buy",
                "orderType": "limit",
                "amount": "10",
                "amountRemaining": "10",
                "price": "7000",
                "amountQuote": "5000",
                "amountQuoteRemaining": "5000",
                "onHold": "9109.61",
                "onHoldCurrency": "BTC",
                "triggerPrice": "4000",
                "triggerAmount": "4000",
                "triggerType": "price",
                "triggerReference": "lastTrade",
                "filledAmount": "0",
                "filledAmountQuote": "0",
                "feePaid": "0",
                "feeCurrency": "EUR",
                "fills": [
                  {
                    "id": "371c6bd3-d06d-4573-9f15-18697cd210e5",
                    "timestamp": 1542967486256,
                    "amount": "0.005",
                    "price": "5000.1",
                    "taker": true,
                    "fee": "0.03",
                    "feeCurrency": "EUR",
                    "settled": true
                  }
                ],
                "selfTradePrevention": "decrementAndCancel",
                "visible": true,
                "timeInForce": "GTC",
                "postOnly": true,
                "disableMarketProtection": true
              }
            ]
            ```
            """
            self.callbacks["getOrders"] = callback
            options["action"] = "privateGetOrders"
            options["market"] = market
            self.do_send(self.ws, json.dumps(options), True)

        def cancel_orders(self, options: anydict, callback: Callable[[Any], None]) -> None:
            """Cancel all existing orders for a specific market (or account)

            ---
            Args:
            ```python
            options={} # WARNING - WILL REMOVE ALL OPEN ORDERS ON YOUR ACCOUNT!
            options={"market":"BTC-EUR"}  # Removes all open orders for this market
            callback=callback_example
            ```

            ---
            Rate Limit Weight:
            ```python
            1
            ```

            ---
            Returns this to `callback`:
            ```python
            # A whole list of these
            [
              {"orderId": "1be6d0df-d5dc-4b53-a250-3376f3b393e6"}
            ]
            ```
            """
            self.callbacks["cancelOrders"] = callback
            options["action"] = "privateCancelOrders"
            self.do_send(self.ws, json.dumps(options), True)

        def orders_open(self, options: anydict, callback: Callable[[Any], None]) -> None:
            """Get all open orders, either for all markets, or a single market

            ---
            Args:
            ```python
            options={} # Gets all open orders for all markets
            options={"market":"BTC-EUR"}  # Get open orders for this market
            callback=callback_example
            ```

            ---
            Rate Limit Weight:
            ```python
            25  # if no market option is used
            1  # if a market option is used
            ```

            ---
            Returns this to `callback`:
            ```python
            [
              {
                "orderId": "1be6d0df-d5dc-4b53-a250-3376f3b393e6",
                "market": "BTC-EUR",
                "created": 1542621155181,
                "updated": 1542621155181,
                "status": "new",
                "side": "buy",
                "orderType": "limit",
                "amount": "10",
                "amountRemaining": "10",
                "price": "7000",
                "amountQuote": "5000",
                "amountQuoteRemaining": "5000",
                "onHold": "9109.61",
                "onHoldCurrency": "BTC",
                "triggerPrice": "4000",
                "triggerAmount": "4000",
                "triggerType": "price",
                "triggerReference": "lastTrade",
                "filledAmount": "0",
                "filledAmountQuote": "0",
                "feePaid": "0",
                "feeCurrency": "EUR",
                "fills": [
                  {
                    "id": "371c6bd3-d06d-4573-9f15-18697cd210e5",
                    "timestamp": 1542967486256,
                    "amount": "0.005",
                    "price": "5000.1",
                    "taker": true,
                    "fee": "0.03",
                    "feeCurrency": "EUR",
                    "settled": true
                  }
                ],
                "selfTradePrevention": "decrementAndCancel",
                "visible": true,
                "timeInForce": "GTC",
                "postOnly": true,
                "disableMarketProtection": true
              }
            ]
            ```
            """
            self.callbacks["ordersOpen"] = callback
            options["action"] = "privateGetOrdersOpen"
            self.do_send(self.ws, json.dumps(options), True)

        def trades(self, market: str, options: anydict, callback: Callable[[Any], None]) -> None:
            """Get all historic trades from this account

            ---
            Args:
            ```python
            market="BTC-EUR"
            options={
                "limit": [ 1 .. 1000 ], default 500
                "start": int timestamp in ms >= 0
                # (that's somewhere in the year 2243, or near the number 2^52)
                "end": int timestamp in ms <= 8_640_000_000_000_000
                "tradeIdFrom": ""  # if you get a list and want everything AFTER a certain id, put that id here
                "tradeIdTo": ""  # if you get a list and want everything BEFORE a certain id, put that id here
            }
            callback=callback_example
            ```

            ---
            Rate Limit Weight:
            ```python
            5
            ```

            ---
            Returns this to `callback`:
            ```python
            [
              {
                "id": "108c3633-0276-4480-a902-17a01829deae",
                "orderId": "1d671998-3d44-4df4-965f-0d48bd129a1b",
                "timestamp": 1542967486256,
                "market": "BTC-EUR",
                "side": "buy",
                "amount": "0.005",
                "price": "5000.1",
                "taker": true,
                "fee": "0.03",
                "feeCurrency": "EUR",
                "settled": true
              }
            ]
            ```
            """
            self.callbacks["trades"] = callback
            options["action"] = "privateGetTrades"
            options["market"] = market
            self.do_send(self.ws, json.dumps(options), True)

        def account(self, callback: Callable[[Any], None]) -> None:
            """Get all fees for this account

            ---
            Args:
            ```python
            callback=callback_example
            ```

            ---
            Rate Limit Weight:
            ```python
            1
            ```

            ---
            Returns this to `callback`:
            ```python
            {
              "fees": {
                "taker": "0.0025",
                "maker": "0.0015",
                "volume": "10000.00"
              }
            }
            ```
            """
            self.callbacks["account"] = callback
            self.do_send(self.ws, json.dumps({"action": "privateGetAccount"}), True)

        def balance(self, options: anydict, callback: Callable[[Any], None]) -> None:
            """Get the balance for this account

            ---
            Args:
            ```python
            options={}  # return all balances
            options={symbol="BTC"} # return a single balance
            callback=callback_example
            ```

            ---
            Rate Limit Weight:
            ```python
            5
            ```

            ---
            Returns this to `callback`:
            ```python
            [
              {
                "symbol": "BTC",
                "available": "1.57593193",
                "inOrder": "0.74832374"
              }
            ]
            ```
            """
            options["action"] = "privateGetBalance"
            self.callbacks["balance"] = callback
            self.do_send(self.ws, json.dumps(options), True)

        def deposit_assets(self, symbol: str, callback: Callable[[Any], None]) -> None:
            """
            Get the deposit address (with paymentId for some assets) or bank account information to increase your
            balance.

            ---
            Args:
            ```python
            symbol="BTC"
            symbol="SHIB"
            symbol="EUR"
            callback=callback_example
            ```

            ---
            Rate Limit Weight:
            ```python
            1
            ```

            ---
            Returns this to `callback`:
            ```python
            {
              "address": "CryptoCurrencyAddress",
              "paymentId": "10002653"
            }
            # or
            {
              "iban": "NL32BUNQ2291234129",
              "bic": "BUNQNL2A",
              "description": "254D20CC94"
            }
            ```
            """
            self.callbacks["depositAssets"] = callback
            self.do_send(
                self.ws,
                json.dumps({"action": "privateDepositAssets", "symbol": symbol}),
                True,
            )

        def deposit_history(self, options: anydict, callback: Callable[[Any], None]) -> None:
            """Get the deposit history of the account

            Even when you want something from a single `symbol`, you'll still receive a list with multiple deposits.

            ---
            Args:
            ```python
            options={
                "symbol":"EUR"
                "limit": [ 1 .. 1000 ], default 500
                "start": int timestamp in ms >= 0
                # (that's somewhere in the year 2243, or near the number 2^52)
                "end": int timestamp in ms <= 8_640_000_000_000_000
            }
            callback=callback_example
            ```

            ---
            Rate Limit Weight:
            ```python
            5
            ```

            ---
            Returns this to `callback`:
            ```python
            [
              {
                "timestamp": 1542967486256,
                "symbol": "BTC",
                "amount": "0.99994",
                "address": "BitcoinAddress",
                "paymentId": "10002653",
                "txId": "927b3ea50c5bb52c6854152d305dfa1e27fc01d10464cf10825d96d69d235eb3",
                "fee": "0"
              }
            ]
            # or
            [
              {
                "timestamp": 1542967486256,
                "symbol": "BTC",
                "amount": "500",
                "address": "NL32BITV0001234567",
                "fee": "0"
              }
            ]
            ```
            """
            self.callbacks["depositHistory"] = callback
            options["action"] = "privateGetDepositHistory"
            self.do_send(self.ws, json.dumps(options), True)

        def withdraw_assets(
            self,
            symbol: str,
            amount: str,
            address: str,
            body: anydict,
            callback: Callable[[Any], None],
        ) -> None:
            """Withdraw a coin/token to an external crypto address or bank account.

            ---
            Args:
            ```python
            symbol="SHIB"
            amount=10
            address="BitcoinAddress",  # Wallet address or IBAN
            options={
              # For digital assets only. Should be set when withdrawing straight to another exchange or merchants that
              # require payment id's.
              "paymentId": "10002653",
              # For digital assets only. Should be set to true if the withdrawal must be sent to another Bitvavo user
              # internally
              "internal": false,
              # If set to true, the fee will be added on top of the requested amount, otherwise the fee is part of the
              # requested amount and subtracted from the withdrawal.
              "addWithdrawalFee": false
            }
            callback=callback_example
            ```

            ---
            Rate Limit Weight:
            ```python
            1
            ```

            ---
            Returns this to `callback`:
            ```python
            {
              "success": true,
              "symbol": "BTC",
              "amount": "1.5"
            }
            ```
            """
            self.callbacks["withdrawAssets"] = callback
            body["action"] = "privateWithdrawAssets"
            body["symbol"] = symbol
            body["amount"] = amount
            body["address"] = address
            self.do_send(self.ws, json.dumps(body), True)

        def withdrawal_history(self, options: anydict, callback: Callable[[Any], None]) -> None:
            """Get the withdrawal history

            ---
            Args:
            ```python
            options={
                "symbol":"SHIB"
                "limit": [ 1 .. 1000 ], default 500
                "start": int timestamp in ms >= 0
                # (that's somewhere in the year 2243, or near the number 2^52)
                "end": int timestamp in ms <= 8_640_000_000_000_000
            }
            callback=callback_example
            ```

            ---
            Rate Limit Weight:
            ```python
            5
            ```

            ---
            Returns this to `callback`:
            ```python
            [
              {
                "timestamp": 1542967486256,
                "symbol": "BTC",
                "amount": "0.99994",
                "address": "BitcoinAddress",
                "paymentId": "10002653",
                "txId": "927b3ea50c5bb52c6854152d305dfa1e27fc01d10464cf10825d96d69d235eb3",
                "fee": "0.00006",
                "status": "awaiting_processing"
              }
            }
            ```
            """
            self.callbacks["withdrawalHistory"] = callback
            options["action"] = "privateGetWithdrawalHistory"
            self.do_send(self.ws, json.dumps(options), True)

        def subscription_ticker(self, market: str, callback: Callable[[Any], None]) -> None:
            # TODO(NostraDavid): one possible improvement here is to turn `market` into a list of markets, so we can sub
            # to all of them at once. Same goes for other `subscription*()`
            """
            Subscribe to the ticker channel, which means `callback` gets passed the new best bid or ask whenever they
            change (server-side).


            ---
            Args:
            ```python
            market="BTC-EUR"
            callback=callback_example
            ```

            ---
            Returns this to `callback`:
            ```python
            # first
            {
              "event": "subscribed",
              "subscriptions": {
                "ticker": [
                  "BTC-EUR"
                ]
              }
            }
            # and after that:
            {
              "event": "ticker",
              "market": "BTC-EUR",
              "bestBid": "9156.8",
              "bestBidSize": "0.12840531",
              "bestAsk": "9157.9",
              "bestAskSize": "0.1286605",
              "lastPrice": "9156.9"
            }
            ```
            """
            if "subscriptionTicker" not in self.callbacks:
                self.callbacks["subscriptionTicker"] = {}
            self.callbacks["subscriptionTicker"][market] = callback
            self.do_send(
                self.ws,
                json.dumps(
                    {
                        "action": "subscribe",
                        "channels": [{"name": "ticker", "markets": [market]}],
                    },
                ),
            )

        def subscription_ticker24h(self, market: str, callback: Callable[[Any], None]) -> None:
            """
            Subscribe to the ticker-24-hour channel, which means `callback` gets passed the new object every second, if
            values have changed.

            ---
            Args:
            ```python
            market="BTC-EUR"
            callback=callback_example
            ```

            ---
            Returns this to `callback`:
            ```python
            # first
            {
              "event": "subscribed",
              "subscriptions": {
                "ticker": [
                  "BTC-EUR"
                ]
              }
            }
            # and after that:
            {
              "event": "ticker24h",
              "data": {
                "market": "BTC-EUR",
                "open": "9072.9",
                "high": "9263.6",
                "low": "9062.8",
                "last": "9231.8",
                "volume": "85.70530211",
                "volumeQuote": "785714.14",
                "bid": "9225",
                "bidSize": "1.14732373",
                "ask": "9225.1",
                "askSize": "0.65371786",
                "timestamp": 1566564813057
              }
            }
            ```
            """
            if "subscriptionTicker24h" not in self.callbacks:
                self.callbacks["subscriptionTicker24h"] = {}
            self.callbacks["subscriptionTicker24h"][market] = callback
            self.do_send(
                self.ws,
                json.dumps(
                    {
                        "action": "subscribe",
                        "channels": [{"name": "ticker24h", "markets": [market]}],
                    },
                ),
            )

        def subscription_account(self, market: str, callback: Callable[[Any], None]) -> None:
            """
            Subscribes to the account channel, which sends an update whenever an event happens which is related to
            the account. These are 'order' events (create, update, cancel) or 'fill' events (a trade occurred).

            ---
            Args:
            ```python
            market="BTC-EUR"
            callback=callback_example
            ```

            ---
            Returns this to `callback`:
            ```python
            # first
            {
              "event": "subscribed",
              "subscriptions": {
                "account": [
                  "BTC-EUR"
                ]
              }
            }
            # and after that, either
            {
              "event": "order",
              "orderId": "80b5f04d-21fc-4ebe-9c5f-6d34f78ee477",
              "market": "BTC-EUR",
              "created": 1548684420771,
              "updated": 1548684420771,
              "status": "new",
              "side": "buy",
              "orderType": "limit",
              "amount": "1",
              "amountRemaining": "0.567",
              "price": "9225.1",
              "onHold": "9225.1",
              "onHoldCurrency": "EUR",
              "triggerPrice": "4000",
              "triggerAmount": "4000",
              "triggerType": "price",
              "triggerReference": "lastTrade",
              "timeInForce": "GTC",
              "postOnly": false,
              "selfTradePrevention": "decrementAndCancel",
              "visible": true
            }
            # or
            {
              "event": "fill",
              "market": "BTC-EUR",
              "orderId": "80b5f04d-21fc-4ebe-9c5f-6d34f78ee477",
              "fillId": "15d14b09-389d-4f83-9413-de9d0d8e7715",
              "timestamp": 1542967486256,
              "amount": "0.005",
              "side": "sell",
              "price": "5000.1",
              "taker": true,
              "fee": "0.03",
              "feeCurrency": "EUR"
            }
            ```
            """
            if "subscriptionAccount" not in self.callbacks:
                self.callbacks["subscriptionAccount"] = {}
            self.callbacks["subscriptionAccount"][market] = callback
            self.do_send(
                self.ws,
                json.dumps(
                    {
                        "action": "subscribe",
                        "channels": [{"name": "account", "markets": [market]}],
                    },
                ),
                True,
            )

        def subscription_candles(self, market: str, interval: str, callback: Callable[[Any], None]) -> None:
            """Subscribes to candles and returns a candle each time a new one is formed, depending on the interval

            ---
            Args:
            ```python
            market="BTC-EUR"
            interval="1h"  # Choose: 1m, 5m, 15m, 30m, 1h, 2h, 4h, 6h, 8h, 12h, 1d
            callback=callback_example
            ```

            ---
            Returns this to `callback`:
            ```python
            # first
            {
              "event": "subscribed",
              "subscriptions": {
                "candles": {
                  "1h": [
                    "BTC-EUR"
                  ]
                }
              }
            }
            # and after that:
            {
              "event": "candle",
              "market": "BTC-EUR",
              "interval": "1h",
              "candle": [
                [
                  1538784000000,
                  "4999",
                  "5012",
                  "4999",
                  "5012",
                  "0.45"
                ]
              ]
            }
            ```
            """
            if "subscriptionCandles" not in self.callbacks:
                self.callbacks["subscriptionCandles"] = {}
            if market not in self.callbacks["subscriptionCandles"]:
                self.callbacks["subscriptionCandles"][market] = {}
            self.callbacks["subscriptionCandles"][market][interval] = callback
            self.do_send(
                self.ws,
                json.dumps(
                    {
                        "action": "subscribe",
                        "channels": [
                            {
                                "name": "candles",
                                "interval": [interval],
                                "markets": [market],
                            },
                        ],
                    },
                ),
            )

        def subscription_trades(self, market: str, callback: Callable[[Any], None]) -> None:
            """Subscribes to trades, which sends an object whenever a trade has occurred.

            ---
            Args:
            ```python
            market="BTC-EUR"
            callback=callback_example
            ```

            ---
            Returns this to `callback`:
            ```python
            # first
            {
              "event": "subscribed",
              "subscriptions": {
                "trades": [
                  "BTC-EUR"
                ]
              }
            }
            # and after that:
            {
              "event": "trade",
              "timestamp": 1566817150381,
              "market": "BTC-EUR",
              "id": "391f4d94-485f-4fb0-b11f-39da1cfcfc2d",
              "amount": "0.00096361",
              "price": "9311.2",
              "side": "sell"
            }
            ```
            """
            if "subscriptionTrades" not in self.callbacks:
                self.callbacks["subscriptionTrades"] = {}
            self.callbacks["subscriptionTrades"][market] = callback
            self.do_send(
                self.ws,
                json.dumps(
                    {
                        "action": "subscribe",
                        "channels": [{"name": "trades", "markets": [market]}],
                    },
                ),
            )

        def subscription_book_update(self, market: str, callback: Callable[[Any], None]) -> None:
            """Subscribes to the book and returns a delta on every change to the book.

            ---
            Args:
            ```python
            market="BTC-EUR"
            callback=callback_example
            ```

            ---
            Returns this to `callback`:
            ```python
            # first
            {
              "event": "subscribed",
              "subscriptions": {
                "book": [
                  "BTC-EUR"
                ]
              }
            }
            # and after that:
            {
              "event": "book",
              "market": "BTC-EUR",
              "nonce": 0,
              "bids": [
                ["9209.3", "0"],
                ["9207.7", "0"],
                ["9206.1", "0"],
                ["9204.6", "0.09173282"],
                ["9206.3", "0.08142723"],
                ["9209.5", "0.1015792"],
                ["9207.9", "0.09120002"],
              ],
              "asks": [
                ["9220.2", "0"],
                ["9223.4", "0"],
                ["9225.1", "0"],
                ["9228.1", "0"],
                ["9231.8", "0"],
                ["9233.6", "0"],
                ["9235.1", "0.51598389"],
                ["9233.1", "0.40684114"],
                ["9230.6", "0.33906266"],
                ["9227.2", "0.40078234"],
                ["9221.8", "0.30485309"],
                ["9225.4", "0.36040168"],
                ["9229", "0.36070097"],
              ],
            }
            ```
            """
            if "subscriptionBookUpdate" not in self.callbacks:
                self.callbacks["subscriptionBookUpdate"] = {}
            self.callbacks["subscriptionBookUpdate"][market] = callback
            self.do_send(
                self.ws,
                json.dumps(
                    {
                        "action": "subscribe",
                        "channels": [{"name": "book", "markets": [market]}],
                    },
                ),
            )

        def subscription_book(self, market: str, callback: Callable[[Any], None]) -> None:
            """Subscribes to the book and returns a delta on every change to the book.

            ---
            Args:
            ```python
            market="BTC-EUR"
            callback=callback_example
            ```

            ---
            Returns this to `callback`:
            ```python
            # first
            {
              "event": "subscribed",
              "subscriptions": {
                "book": [
                  "BTC-EUR"
                ]
              }
            }
            # and after that:
            {
              "event": "book",
              "market": "BTC-EUR",
              "nonce": 0,
              "bids": [
                ["9209.3", "0"],
                ["9207.7", "0"],
                ["9206.1", "0"],
                ["9204.6", "0.09173282"],
                ["9206.3", "0.08142723"],
                ["9209.5", "0.1015792"],
                ["9207.9", "0.09120002"],
              ],
              "asks": [
                ["9220.2", "0"],
                ["9223.4", "0"],
                ["9225.1", "0"],
                ["9228.1", "0"],
                ["9231.8", "0"],
                ["9233.6", "0"],
                ["9235.1", "0.51598389"],
                ["9233.1", "0.40684114"],
                ["9230.6", "0.33906266"],
                ["9227.2", "0.40078234"],
                ["9221.8", "0.30485309"],
                ["9225.4", "0.36040168"],
                ["9229", "0.36070097"],
              ],
            }
            ```
            """
            self.keepBookCopy = True
            if "subscriptionBookUser" not in self.callbacks:
                self.callbacks["subscriptionBookUser"] = {}
            self.callbacks["subscriptionBookUser"][market] = callback
            if "subscriptionBook" not in self.callbacks:
                self.callbacks["subscriptionBook"] = {}
            self.callbacks["subscriptionBook"][market] = process_local_book
            self.do_send(
                self.ws,
                json.dumps(
                    {
                        "action": "subscribe",
                        "channels": [{"name": "book", "markets": [market]}],
                    },
                ),
            )

            self.localBook[market] = {}
            self.do_send(self.ws, json.dumps({"action": "getBook", "market": market}))
