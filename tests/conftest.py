"""
run `pytest --fixtures` to see what's available within a test_* function
"""

import logging
from typing import Any

import pytest

from bitvavo_api_upgraded.bitvavo import Bitvavo
from bitvavo_api_upgraded.settings import bitvavo_settings

logger = logging.getLogger("conftest")


@pytest.fixture(scope="session")
def bitvavo() -> Bitvavo:
    return Bitvavo(bitvavo_settings.model_dump())


@pytest.fixture(scope="session")
def websocket(bitvavo: Bitvavo) -> Bitvavo.WebSocketAppFacade:
    def error_callback(error: Any) -> None:
        msg = f"Error callback: {error}"
        logger.error(msg)

    bitvavo = Bitvavo(bitvavo_settings.model_dump())

    websocket: Bitvavo.WebSocketAppFacade = bitvavo.new_websocket()
    websocket.set_error_callback(error_callback)
    return websocket


@pytest.fixture(autouse=True)
def wrap_public_request(monkeypatch: pytest.MonkeyPatch, bitvavo: Bitvavo) -> None:
    """
    The reason for this wrapper fixture, is that the Bitvavo API has changed a
    bit and is now generating output that doesn't conform to my tests, but since
    I presume that this output does not matter - typically it contains markets
    that are not in use anymore - I can remove them.

    2024-12-24: I kinda fixed the tests, so this may not be necessary anymore.
    Maybe.
    """
    # Market exceptions to remove, as of 2024-11-11
    market_exceptions = [
        "BABYDOGE-EUR",  # left as example
    ]
    original_public_request = bitvavo.public_request

    def wrapped_public_request(*args: Any, **kwargs: Any) -> Any:
        # Call the original method
        response = original_public_request(*args, **kwargs)

        if isinstance(response, list):
            for idx, item in enumerate(response):
                if isinstance(item, list):
                    continue
                if item.get("market", None) and item["market"] in market_exceptions:
                    # remove the market item
                    del response[idx]
        return response

    # Monkeypatch the `publicRequest` method of the Bitvavo instance
    monkeypatch.setattr(bitvavo, "public_request", wrapped_public_request)
