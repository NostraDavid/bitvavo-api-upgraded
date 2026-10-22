# License notice from LICENSE.txt:
# Copyright (c) 2024, Bitvavo B.V.

"""Keep unit tests independent of exchange services."""

import socket

import pytest


@pytest.fixture(autouse=True)
def block_network(monkeypatch: pytest.MonkeyPatch) -> None:
    def fail_connect(*args: object, **kwargs: object) -> None:
        pytest.fail("Unit tests must mock network connections")

    monkeypatch.setattr(socket.socket, "connect", fail_connect)
