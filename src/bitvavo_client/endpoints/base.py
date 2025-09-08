"""Shared endpoint utilities for model resolution and DataFrame handling."""

from __future__ import annotations

import contextlib
from typing import TYPE_CHECKING, Any, TypeVar

from returns.result import Failure, Result, Success

from bitvavo_client.adapters.returns_adapter import BitvavoError
from bitvavo_client.core.model_preferences import ModelPreference

if TYPE_CHECKING:
    from collections.abc import Mapping

T = TypeVar("T")


# DataFrames preference to library mapping
_DATAFRAME_LIBRARY_MAP = {
    ModelPreference.POLARS: ("polars", "pl.DataFrame"),
    ModelPreference.PANDAS: ("pandas", "pd.DataFrame"),
    ModelPreference.PYARROW: ("pyarrow", "pa.Table"),
    ModelPreference.DASK: ("dask", "dd.DataFrame"),
    ModelPreference.MODIN: ("modin", "mpd.DataFrame"),
    ModelPreference.CUDF: ("cudf", "cudf.DataFrame"),
    ModelPreference.IBIS: ("ibis", "ibis.Table"),
}


def _extract_dataframe_data(data: Any, *, items_key: str | None = None) -> list[dict] | dict:
    """Extract the meaningful data for DataFrame creation from API responses."""
    if items_key and isinstance(data, dict) and items_key in data:
        items = data[items_key]
        if not isinstance(items, list):
            msg = f"Expected {items_key} to be a list, got {type(items)}"
            raise ValueError(msg)
        return items
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        return [data]
    msg = f"Unexpected data type for DataFrame creation: {type(data)}"
    raise ValueError(msg)


def _get_dataframe_constructor(preference: ModelPreference) -> tuple[Any, str]:  # noqa: PLR0911 (Too many return statements)
    """Get the appropriate dataframe constructor and library name based on preference."""
    if preference not in _DATAFRAME_LIBRARY_MAP:
        msg = f"Unsupported dataframe preference: {preference}"
        raise ValueError(msg)

    library_name, _ = _DATAFRAME_LIBRARY_MAP[preference]

    try:
        if preference == ModelPreference.POLARS:
            import polars as pl  # noqa: PLC0415

            return pl.DataFrame, library_name
        if preference == ModelPreference.PANDAS:
            import pandas as pd  # noqa: PLC0415

            return pd.DataFrame, library_name
        if preference == ModelPreference.PYARROW:
            import pyarrow as pa  # noqa: PLC0415

            return pa.Table.from_pylist, library_name
        if preference == ModelPreference.DASK:
            import dask.dataframe as dd  # noqa: PLC0415
            import pandas as pd  # noqa: PLC0415

            return lambda data, **_: dd.from_pandas(pd.DataFrame(data), npartitions=1), library_name
        if preference == ModelPreference.MODIN:
            import modin.pandas as mpd  # noqa: PLC0415

            return mpd.DataFrame, library_name
        if preference == ModelPreference.CUDF:
            import cudf  # noqa: PLC0415

            return cudf.DataFrame, library_name
        import ibis  # noqa: PLC0415

        return lambda data, **_: ibis.memtable(data), library_name
    except ImportError as e:  # pragma: no cover - import failure is environment dependent
        msg = f"{library_name} is not installed. Install with appropriate package manager."
        raise ImportError(msg) from e


def _create_dataframe_with_constructor(  # noqa: C901 (is too complex)
    constructor: Any, library_name: str, df_data: list | dict, empty_schema: dict | None
) -> Any:
    """Create DataFrame with data using the appropriate constructor."""

    # Helper function to check if data is array-like and schema exists
    def _is_array_data_with_schema() -> bool:
        return bool(empty_schema and isinstance(df_data, list) and df_data and isinstance(df_data[0], (list, tuple)))

    if library_name == "polars":
        # Handle special case for array data (like candles) with schema
        if _is_array_data_with_schema() and empty_schema:
            # Transform array data into named columns based on schema
            column_names = list(empty_schema.keys())
            if len(df_data[0]) == len(column_names):  # type: ignore[index]
                # Create DataFrame with explicit column names
                import polars as pl  # noqa: PLC0415

                df = pl.DataFrame(df_data, schema=column_names, orient="row")
                df = _apply_polars_schema(df, empty_schema)
                return df

        df = constructor(df_data, strict=False)
        if empty_schema:
            df = _apply_polars_schema(df, empty_schema)
        return df

    if library_name in ("pandas", "modin", "cudf"):
        # Handle special case for array data (like candles) with schema
        if _is_array_data_with_schema() and empty_schema:
            # Transform array data into named columns based on schema
            column_names = list(empty_schema.keys())
            if len(df_data[0]) == len(column_names):  # type: ignore[index]
                # Create DataFrame with explicit column names
                df = constructor(df_data, columns=column_names)
                if empty_schema:
                    df = _apply_pandas_like_schema(df, empty_schema)
                return df

        df = constructor(df_data)
        if empty_schema:
            df = _apply_pandas_like_schema(df, empty_schema)
        return df

    if library_name in ("pyarrow", "dask"):
        return constructor(df_data)

    return constructor(df_data)


def _create_empty_dataframe(constructor: Any, library_name: str, empty_schema: dict | None) -> Any:
    """Create empty DataFrame using the appropriate constructor."""
    if empty_schema is None:
        empty_schema = {"id": str} if library_name != "polars" else {"id": "pl.String"}

    if library_name == "polars":
        import polars as pl  # noqa: PLC0415

        schema = {k: pl.String if v == "pl.String" else v for k, v in empty_schema.items()}
        return constructor([], schema=schema)
    if library_name in ("pandas", "modin", "cudf", "dask") or library_name == "pyarrow":
        return constructor([])
    return constructor([dict.fromkeys(empty_schema.keys())])


def _apply_polars_schema(df: Any, schema: dict) -> Any:
    """Apply schema to polars DataFrame."""
    import polars as pl  # noqa: PLC0415

    for col, expected_dtype in schema.items():
        if col in df.columns:
            with contextlib.suppress(Exception):
                df = df.with_columns(pl.col(col).cast(expected_dtype))
    return df


def _apply_pandas_like_schema(df: Any, schema: dict) -> Any:
    """Apply schema to pandas-like DataFrame."""
    pandas_schema = {}
    for col, dtype in schema.items():
        if col in df.columns:
            if "String" in str(dtype) or "Utf8" in str(dtype):
                pandas_schema[col] = "string"
            elif "Int" in str(dtype):
                pandas_schema[col] = "int64"
            elif "Float" in str(dtype):
                pandas_schema[col] = "float64"

    if pandas_schema and hasattr(df, "astype"):
        with contextlib.suppress(Exception):
            df = df.astype(pandas_schema)
    return df


def _create_dataframe_from_data(
    data: Any, preference: ModelPreference, *, items_key: str | None = None, empty_schema: dict[str, Any] | None = None
) -> Result[Any, BitvavoError]:
    """Create a DataFrame from API response data using the specified preference."""
    try:
        df_data = _extract_dataframe_data(data, items_key=items_key)
        constructor, library_name = _get_dataframe_constructor(preference)

        if df_data:
            df = _create_dataframe_with_constructor(constructor, library_name, df_data, empty_schema)
            return Success(df)  # type: ignore[return-value]

        df = _create_empty_dataframe(constructor, library_name, empty_schema)
        return Success(df)  # type: ignore[return-value]

    except (ValueError, TypeError, ImportError) as exc:
        error = BitvavoError(
            http_status=500,
            error_code=-1,
            reason="DataFrame creation failed",
            message=f"Failed to create DataFrame from API response: {exc}",
            raw={"data_type": type(data).__name__, "data_sample": str(data)[:200]},
        )
        return Failure(error)


class BaseAPI:
    """Base class for API endpoint handlers providing model conversion utilities."""

    _endpoint_models: Mapping[str, Any] = {}
    _default_schemas: Mapping[str, object] = {}

    def __init__(
        self,
        http_client: Any,
        *,
        preferred_model: ModelPreference | str | None = None,
        default_schema: Mapping[str, object] | None = None,
    ) -> None:
        self.http = http_client

        if preferred_model is None:
            self.preferred_model = None
        elif isinstance(preferred_model, ModelPreference):
            self.preferred_model = preferred_model
        elif isinstance(preferred_model, str):
            try:
                self.preferred_model = ModelPreference(preferred_model)
            except ValueError:
                self.preferred_model = preferred_model
        else:
            self.preferred_model = preferred_model

        self.default_schema = default_schema

    def _get_effective_model(
        self,
        endpoint_type: str,
        model: type[T] | Any | None,
        schema: Mapping[str, object] | None,
    ) -> tuple[type[T] | Any | None, Mapping[str, object] | None]:
        if model is not None:
            return model, schema

        if self.preferred_model is None or self.preferred_model == ModelPreference.RAW:
            return Any, schema

        if isinstance(self.preferred_model, ModelPreference) and self.preferred_model in _DATAFRAME_LIBRARY_MAP:
            effective_schema = schema or self.default_schema or self._default_schemas.get(endpoint_type)
            if effective_schema is not None and not isinstance(effective_schema, dict):
                effective_schema = dict(effective_schema)
            return self.preferred_model, effective_schema

        if self.preferred_model == ModelPreference.PYDANTIC:
            model_cls = self._endpoint_models.get(endpoint_type, dict)
            return model_cls, schema

        return None, schema

    def _convert_raw_result(
        self,
        raw_result: Result[Any, BitvavoError | Any],
        endpoint_type: str,
        model: type[T] | Any | None,
        schema: Mapping[str, object] | None,
        *,
        items_key: str | None = None,
    ) -> Result[Any, BitvavoError | Any]:
        if isinstance(raw_result, Failure):
            return raw_result

        effective_model, effective_schema = self._get_effective_model(endpoint_type, model, schema)

        if effective_model is Any or effective_model is None:
            return raw_result

        raw_data = raw_result.unwrap()

        if isinstance(effective_model, ModelPreference) and effective_model in _DATAFRAME_LIBRARY_MAP:
            return _create_dataframe_from_data(
                raw_data,
                effective_model,
                items_key=items_key,
                empty_schema=effective_schema,  # type: ignore[arg-type]
            )

        try:
            if hasattr(effective_model, "model_validate"):
                parsed = effective_model.model_validate(raw_data)  # type: ignore[misc]
            elif effective_schema is None:
                parsed = effective_model(raw_data)  # type: ignore[misc]
            else:
                parsed = effective_model(raw_data, schema=effective_schema)  # type: ignore[misc]
            return Success(parsed)
        except (ValueError, TypeError, AttributeError) as exc:
            error = BitvavoError(
                http_status=500,
                error_code=-1,
                reason="Model conversion failed",
                message=str(exc),
                raw=raw_data if isinstance(raw_data, dict) else {"raw": raw_data},
            )
            return Failure(error)
