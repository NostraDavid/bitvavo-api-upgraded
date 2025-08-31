"""DataFrame conversion utilities using Narwhals for multi-library support."""

from __future__ import annotations

from typing import Any


def is_narwhals_available() -> bool:
    """Check if narwhals is available."""
    try:
        import narwhals  # noqa: F401, PLC0415
    except ImportError:
        return False
    else:
        return True


def convert_to_dataframe(data: Any, output_format: str = "default") -> Any:
    """Convert API response data to DataFrame using narwhals.

    Args:
        data: Response data from Bitvavo API
        output_format: Target DataFrame library ('pandas', 'polars', etc.)

    Returns:
        DataFrame in the requested format or original data if narwhals unavailable

    Raises:
        ImportError: If narwhals or target library is not available
    """
    if not is_narwhals_available() or output_format == "default":
        return data

    # Convert dict to list for DataFrame conversion
    if isinstance(data, dict):
        data = [data]

    try:
        # Try to detect and use the requested library
        if output_format == "pandas":
            import pandas as pd  # noqa: PLC0415

            return pd.DataFrame(data)
        if output_format == "polars":
            import polars as pl  # noqa: PLC0415

            return pl.DataFrame(data)
        # For other formats, try pandas as fallback
        import pandas as pd  # noqa: PLC0415

        return pd.DataFrame(data)

    except ImportError as e:
        # If the target library is not available, return original data
        msg = f"Library {output_format} not available: {e}"
        raise ImportError(msg) from e


def convert_candles_to_dataframe(data: Any, output_format: str = "default") -> Any:
    """Convert candlestick data to DataFrame with proper column names.

    Args:
        data: Candlestick data from Bitvavo API
        output_format: Target DataFrame library

    Returns:
        DataFrame with columns: timestamp, open, high, low, close, volume
    """
    if not is_narwhals_available() or output_format == "default":
        return data

    # Convert to dict format with proper column names
    candle_dicts = [
        {
            "timestamp": candle[0],
            "open": candle[1],
            "high": candle[2],
            "low": candle[3],
            "close": candle[4],
            "volume": candle[5],
        }
        for candle in data
        if len(candle) >= 6  # noqa: PLR2004
    ]

    return convert_to_dataframe(candle_dicts, output_format)
