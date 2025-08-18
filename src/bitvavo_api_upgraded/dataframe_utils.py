"""
Dataframe utilities for comprehensive dataframe library support using Narwhals.

This module provides utilities for converting API responses to dataframes
using Narwhals as a unified interface across multiple dataframe libraries:
pandas, polars, cuDF, modin, pyarrow, dask, duckdb, ibis, pyspark, and more.
"""

from __future__ import annotations

from typing import Any

from bitvavo_api_upgraded.type_aliases import OutputFormat


def is_narwhals_available() -> bool:
    """Check if narwhals is available."""
    try:
        import narwhals  # noqa: PLC0415, F401
    except ImportError:
        return False
    else:
        return True


def is_library_available(library_name: str) -> bool:
    """Check if a specific dataframe library is available."""
    import_mapping = {
        "pandas": "pandas",
        "polars": "polars",
        "cudf": "cudf",
        "modin": "modin.pandas",
        "pyarrow": "pyarrow",
        "dask": "dask.dataframe",
        "duckdb": "duckdb",
        "ibis": "ibis",
        "pyspark": "pyspark.sql",
        "pyspark-connect": "pyspark.sql.connect",
        "sqlframe": "sqlframe",
    }

    module_path = import_mapping.get(library_name)
    if not module_path:
        return False

    try:
        __import__(module_path)
    except ImportError:
        return False
    else:
        return True


def _normalize_output_format(output_format: str | OutputFormat) -> OutputFormat:
    """Convert string input to OutputFormat enum if needed."""
    if isinstance(output_format, OutputFormat):
        return output_format

    # Convert string to enum
    valid_formats = {fmt.value: fmt for fmt in OutputFormat}
    if output_format not in valid_formats:
        valid_values = list(valid_formats.keys())
        msg = f"Invalid output_format: {output_format}. Valid options: {valid_values}"
        raise ValueError(msg)

    return valid_formats[output_format]


def validate_output_format(output_format: str | OutputFormat) -> None:
    """Validate the output format and check if required libraries are available."""
    # Normalize input to enum format
    format_enum = _normalize_output_format(output_format)
    format_str = format_enum.value

    # Dict format doesn't need any special libraries
    if format_str == OutputFormat.DICT.value:
        return

    # All dataframe formats require narwhals
    if not is_narwhals_available():
        msg = f"narwhals is not available. Install with: pip install 'bitvavo-api-upgraded[{format_str}]'"
        raise ImportError(msg)

    # Check if the specific library is available
    if not is_library_available(format_str):
        msg = f"{format_str} is not available. Install with: pip install 'bitvavo-api-upgraded[{format_str}]'"
        raise ImportError(msg)


def convert_to_dataframe(data: Any, output_format: str | OutputFormat) -> Any:
    """Convert data to the specified dataframe format."""
    # Normalize the output format first
    format_enum = _normalize_output_format(output_format)

    validate_output_format(format_enum)

    if format_enum == OutputFormat.DICT:
        return data

    if not isinstance(data, list) or not data:
        # If it's not a list or empty, return as-is for dict format compatibility
        return data

    # Use Narwhals for conversion - it handles all supported libraries automatically
    import narwhals as nw  # noqa: PLC0415

    # Create a native dataframe - for most libraries, we can let narwhals handle the details
    # We'll create a simple pandas dataframe and let narwhals convert to the target format
    if format_enum in (OutputFormat.DASK, OutputFormat.DUCKDB):
        # Special handling for dask and duckdb
        native_df = _create_special_dataframe(data, format_enum)
    else:
        # Use pandas as intermediate format for most cases
        import pandas as pd  # noqa: PLC0415

        native_df = pd.DataFrame(data)

    # Convert through narwhals to ensure compatibility
    nw_df = nw.from_native(native_df)
    return nw_df.to_native()


def _create_special_dataframe(data: Any, output_format: OutputFormat) -> Any:
    """Create special dataframes that need custom handling."""
    if output_format == OutputFormat.DASK:
        import dask.dataframe as dd  # noqa: PLC0415
        import pandas as pd  # noqa: PLC0415

        # Create pandas df first, then convert to dask
        pdf = pd.DataFrame(data)
        return dd.from_pandas(pdf, npartitions=1)

    if output_format == OutputFormat.DUCKDB:
        import duckdb  # noqa: PLC0415
        import pandas as pd  # noqa: PLC0415

        # DuckDB works with relations - create via pandas first
        conn = duckdb.connect()
        pdf = pd.DataFrame(data)
        return conn.from_df(pdf)

    # Fallback to pandas
    import pandas as pd  # noqa: PLC0415

    return pd.DataFrame(data)


def convert_candles_to_dataframe(data: Any, output_format: str | OutputFormat) -> Any:
    """Convert candlestick data to the requested format.

    Candlestick data comes as list of lists:
    [[timestamp, open, high, low, close, volume], ...]
    """
    # Normalize the output format first
    format_enum = _normalize_output_format(output_format)

    validate_output_format(format_enum)

    if format_enum == OutputFormat.DICT:
        return data

    if not isinstance(data, list) or not data:
        return data

    # Convert list of lists to list of dicts first
    columns = ["timestamp", "open", "high", "low", "close", "volume"]
    dict_data = [
        dict(zip(columns, candle)) for candle in data if isinstance(candle, list) and len(candle) >= len(columns)
    ]

    if not dict_data:
        return data

    # Reuse the standard conversion function for consistency
    return convert_to_dataframe(dict_data, format_enum)
