"""Common utilities for endpoints."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:  # pragma: no cover
    import datetime as dt
    from collections.abc import Callable

    from bitvavo_client.core.types import AnyDict


def default(value: AnyDict | None, fallback: AnyDict) -> AnyDict:
    """Return value if not None, otherwise fallback.

    Note that this is close, but not actually equal to:
    `return value or fallback`

    Args:
        value: Value to check
        fallback: Fallback value if value is None

    Returns:
        The value or fallback
    """
    return value if value is not None else fallback


def create_postfix(options: AnyDict | None) -> str:
    """Generate a URL postfix based on the options dict.

    Args:
        options: Dictionary of query parameters

    Returns:
        Query string with '?' prefix if options exist, empty string otherwise
    """
    options = default(options, {})
    params = [f"{key}={options[key]}" for key in options]
    postfix = "&".join(params)
    return f"?{postfix}" if len(options) > 0 else postfix


def epoch_millis(dt_obj: dt.datetime) -> int:
    """Convert datetime to milliseconds since epoch.

    Args:
        dt_obj: Datetime object to convert

    Returns:
        Milliseconds since Unix epoch
    """
    return int(dt_obj.timestamp() * 1000)


def asks_compare(a: float, b: float) -> bool:
    return a < b


def bids_compare(a: float, b: float) -> bool:
    return a > b


def sort_and_insert(
    asks_or_bids: list[list[str]],
    update: list[list[str]],
    compareFunc: Callable[[float, float], bool],
) -> list[list[str]] | dict[str, Any]:
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
