"""Tests for bitvavo_client.df.convert module."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import Mock, patch

import pytest

from bitvavo_client.df.convert import (
    convert_candles_to_dataframe,
    convert_to_dataframe,
    is_narwhals_available,
)

if TYPE_CHECKING:  # pragma: no cover
    from typing import Any


class TestIsNarwhalsAvailable:
    """Test the is_narwhals_available function."""

    def test_narwhals_available(self) -> None:
        """Test when narwhals is available."""
        # Mock successful import
        with patch("builtins.__import__") as mock_import:
            mock_import.return_value = Mock()
            result = is_narwhals_available()
            assert result is True
            mock_import.assert_called_once()

    def test_narwhals_not_available(self) -> None:
        """Test when narwhals is not available."""
        # Mock ImportError
        with patch("builtins.__import__", side_effect=ImportError("No module named 'narwhals'")):
            result = is_narwhals_available()
            assert result is False

    def test_actual_narwhals_availability(self) -> None:
        """Test actual narwhals availability in current environment."""
        # This will test the actual state of the environment
        result = is_narwhals_available()
        assert isinstance(result, bool)


class TestConvertToDataframe:
    """Test the convert_to_dataframe function."""

    def test_convert_with_narwhals_unavailable(self) -> None:
        """Test conversion when narwhals is unavailable."""
        test_data = [{"key": "value"}]

        with patch("bitvavo_client.df.convert.is_narwhals_available", return_value=False):
            result = convert_to_dataframe(test_data, "pandas")
            assert result == test_data

    def test_convert_with_default_format(self) -> None:
        """Test conversion with default format."""
        test_data = [{"key": "value"}]

        with patch("bitvavo_client.df.convert.is_narwhals_available", return_value=True):
            result = convert_to_dataframe(test_data, "default")
            assert result == test_data

    def test_convert_dict_to_list(self) -> None:
        """Test that single dict gets converted to list."""
        test_data = {"key": "value"}
        mock_pandas = Mock()
        mock_dataframe = Mock()
        mock_pandas.DataFrame.return_value = mock_dataframe

        with (
            patch("bitvavo_client.df.convert.is_narwhals_available", return_value=True),
            patch.dict("sys.modules", {"pandas": mock_pandas}),
        ):
            result = convert_to_dataframe(test_data, "pandas")

            # Verify pandas.DataFrame was called with list
            mock_pandas.DataFrame.assert_called_once_with([test_data])
            assert result == mock_dataframe

    def test_convert_to_pandas(self) -> None:
        """Test conversion to pandas DataFrame."""
        test_data = [{"key1": "value1"}, {"key2": "value2"}]
        mock_pandas = Mock()
        mock_dataframe = Mock()
        mock_pandas.DataFrame.return_value = mock_dataframe

        with (
            patch("bitvavo_client.df.convert.is_narwhals_available", return_value=True),
            patch.dict("sys.modules", {"pandas": mock_pandas}),
        ):
            result = convert_to_dataframe(test_data, "pandas")

            mock_pandas.DataFrame.assert_called_once_with(test_data)
            assert result == mock_dataframe

    def test_convert_to_polars(self) -> None:
        """Test conversion to polars DataFrame."""
        test_data = [{"key1": "value1"}, {"key2": "value2"}]
        mock_polars = Mock()
        mock_dataframe = Mock()
        mock_polars.DataFrame.return_value = mock_dataframe

        with (
            patch("bitvavo_client.df.convert.is_narwhals_available", return_value=True),
            patch.dict("sys.modules", {"polars": mock_polars}),
        ):
            result = convert_to_dataframe(test_data, "polars")

            mock_polars.DataFrame.assert_called_once_with(test_data)
            assert result == mock_dataframe

    def test_convert_unknown_format_fallback_to_pandas(self) -> None:
        """Test that unknown formats fall back to pandas."""
        test_data = [{"key": "value"}]
        mock_pandas = Mock()
        mock_dataframe = Mock()
        mock_pandas.DataFrame.return_value = mock_dataframe

        with (
            patch("bitvavo_client.df.convert.is_narwhals_available", return_value=True),
            patch.dict("sys.modules", {"pandas": mock_pandas}),
        ):
            result = convert_to_dataframe(test_data, "unknown_format")

            mock_pandas.DataFrame.assert_called_once_with(test_data)
            assert result == mock_dataframe

    def test_convert_pandas_import_error(self) -> None:
        """Test ImportError when pandas is not available."""
        test_data = [{"key": "value"}]

        with (
            patch("bitvavo_client.df.convert.is_narwhals_available", return_value=True),
            patch("builtins.__import__", side_effect=ImportError("No module named 'pandas'")),
            pytest.raises(ImportError, match="Library pandas not available"),
        ):
            convert_to_dataframe(test_data, "pandas")

    def test_convert_polars_import_error(self) -> None:
        """Test ImportError when polars is not available."""
        test_data = [{"key": "value"}]

        with (
            patch("bitvavo_client.df.convert.is_narwhals_available", return_value=True),
            patch("builtins.__import__", side_effect=ImportError("No module named 'polars'")),
            pytest.raises(ImportError, match="Library polars not available"),
        ):
            convert_to_dataframe(test_data, "polars")

    def test_convert_empty_data(self) -> None:
        """Test conversion with empty data."""
        test_data: list[dict[str, Any]] = []
        mock_pandas = Mock()
        mock_dataframe = Mock()
        mock_pandas.DataFrame.return_value = mock_dataframe

        with (
            patch("bitvavo_client.df.convert.is_narwhals_available", return_value=True),
            patch.dict("sys.modules", {"pandas": mock_pandas}),
        ):
            result = convert_to_dataframe(test_data, "pandas")

            mock_pandas.DataFrame.assert_called_once_with(test_data)
            assert result == mock_dataframe

    def test_convert_complex_data(self) -> None:
        """Test conversion with complex nested data."""
        test_data = [
            {
                "timestamp": 1234567890,
                "market": "BTC-EUR",
                "price": "50000.00",
                "nested": {"value": 123},
            },
            {
                "timestamp": 1234567891,
                "market": "ETH-EUR",
                "price": "3000.00",
                "nested": {"value": 456},
            },
        ]
        mock_pandas = Mock()
        mock_dataframe = Mock()
        mock_pandas.DataFrame.return_value = mock_dataframe

        with (
            patch("bitvavo_client.df.convert.is_narwhals_available", return_value=True),
            patch.dict("sys.modules", {"pandas": mock_pandas}),
        ):
            result = convert_to_dataframe(test_data, "pandas")

            mock_pandas.DataFrame.assert_called_once_with(test_data)
            assert result == mock_dataframe


class TestConvertCandlesToDataframe:
    """Test the convert_candles_to_dataframe function."""

    def test_convert_candles_narwhals_unavailable(self) -> None:
        """Test candle conversion when narwhals is unavailable."""
        test_data = [[1234567890, "50000", "51000", "49000", "50500", "10.5"]]

        with patch("bitvavo_client.df.convert.is_narwhals_available", return_value=False):
            result = convert_candles_to_dataframe(test_data, "pandas")
            assert result == test_data

    def test_convert_candles_default_format(self) -> None:
        """Test candle conversion with default format."""
        test_data = [[1234567890, "50000", "51000", "49000", "50500", "10.5"]]

        with patch("bitvavo_client.df.convert.is_narwhals_available", return_value=True):
            result = convert_candles_to_dataframe(test_data, "default")
            assert result == test_data

    def test_convert_candles_to_pandas(self) -> None:
        """Test converting candlestick data to pandas DataFrame."""
        test_data = [
            [1234567890, "50000", "51000", "49000", "50500", "10.5"],
            [1234567891, "50500", "52000", "50000", "51000", "8.2"],
        ]

        expected_dict_data = [
            {
                "timestamp": 1234567890,
                "open": "50000",
                "high": "51000",
                "low": "49000",
                "close": "50500",
                "volume": "10.5",
            },
            {
                "timestamp": 1234567891,
                "open": "50500",
                "high": "52000",
                "low": "50000",
                "close": "51000",
                "volume": "8.2",
            },
        ]

        mock_pandas = Mock()
        mock_dataframe = Mock()
        mock_pandas.DataFrame.return_value = mock_dataframe

        with (
            patch("bitvavo_client.df.convert.is_narwhals_available", return_value=True),
            patch.dict("sys.modules", {"pandas": mock_pandas}),
        ):
            result = convert_candles_to_dataframe(test_data, "pandas")

            mock_pandas.DataFrame.assert_called_once_with(expected_dict_data)
            assert result == mock_dataframe

    def test_convert_candles_to_polars(self) -> None:
        """Test converting candlestick data to polars DataFrame."""
        test_data = [[1234567890, "50000", "51000", "49000", "50500", "10.5"]]

        expected_dict_data = [
            {
                "timestamp": 1234567890,
                "open": "50000",
                "high": "51000",
                "low": "49000",
                "close": "50500",
                "volume": "10.5",
            }
        ]

        mock_polars = Mock()
        mock_dataframe = Mock()
        mock_polars.DataFrame.return_value = mock_dataframe

        with (
            patch("bitvavo_client.df.convert.is_narwhals_available", return_value=True),
            patch.dict("sys.modules", {"polars": mock_polars}),
        ):
            result = convert_candles_to_dataframe(test_data, "polars")

            mock_polars.DataFrame.assert_called_once_with(expected_dict_data)
            assert result == mock_dataframe

    def test_convert_candles_incomplete_data(self) -> None:
        """Test converting candlestick data with incomplete candles."""
        test_data = [
            [1234567890, "50000", "51000", "49000", "50500", "10.5"],  # Complete
            [1234567891, "50500", "52000"],  # Incomplete (< 6 elements)
            [1234567892, "51000", "53000", "50500", "52000", "5.1"],  # Complete
        ]

        # Only complete candles should be included
        expected_dict_data = [
            {
                "timestamp": 1234567890,
                "open": "50000",
                "high": "51000",
                "low": "49000",
                "close": "50500",
                "volume": "10.5",
            },
            {
                "timestamp": 1234567892,
                "open": "51000",
                "high": "53000",
                "low": "50500",
                "close": "52000",
                "volume": "5.1",
            },
        ]

        mock_pandas = Mock()
        mock_dataframe = Mock()
        mock_pandas.DataFrame.return_value = mock_dataframe

        with (
            patch("bitvavo_client.df.convert.is_narwhals_available", return_value=True),
            patch.dict("sys.modules", {"pandas": mock_pandas}),
        ):
            result = convert_candles_to_dataframe(test_data, "pandas")

            mock_pandas.DataFrame.assert_called_once_with(expected_dict_data)
            assert result == mock_dataframe

    def test_convert_candles_empty_data(self) -> None:
        """Test converting empty candlestick data."""
        test_data: list[list[Any]] = []

        mock_pandas = Mock()
        mock_dataframe = Mock()
        mock_pandas.DataFrame.return_value = mock_dataframe

        with (
            patch("bitvavo_client.df.convert.is_narwhals_available", return_value=True),
            patch.dict("sys.modules", {"pandas": mock_pandas}),
        ):
            result = convert_candles_to_dataframe(test_data, "pandas")

            mock_pandas.DataFrame.assert_called_once_with([])
            assert result == mock_dataframe

    def test_convert_candles_with_extra_fields(self) -> None:
        """Test converting candlestick data with extra fields (> 6 elements)."""
        test_data = [[1234567890, "50000", "51000", "49000", "50500", "10.5", "extra1", "extra2"]]

        # Should still work, only first 6 elements are used
        expected_dict_data = [
            {
                "timestamp": 1234567890,
                "open": "50000",
                "high": "51000",
                "low": "49000",
                "close": "50500",
                "volume": "10.5",
            }
        ]

        mock_pandas = Mock()
        mock_dataframe = Mock()
        mock_pandas.DataFrame.return_value = mock_dataframe

        with (
            patch("bitvavo_client.df.convert.is_narwhals_available", return_value=True),
            patch.dict("sys.modules", {"pandas": mock_pandas}),
        ):
            result = convert_candles_to_dataframe(test_data, "pandas")

            mock_pandas.DataFrame.assert_called_once_with(expected_dict_data)
            assert result == mock_dataframe

    def test_convert_candles_import_error(self) -> None:
        """Test ImportError when target library is not available."""
        test_data = [[1234567890, "50000", "51000", "49000", "50500", "10.5"]]

        with (
            patch("bitvavo_client.df.convert.is_narwhals_available", return_value=True),
            patch("builtins.__import__", side_effect=ImportError("No module named 'pandas'")),
            pytest.raises(ImportError, match="Library pandas not available"),
        ):
            convert_candles_to_dataframe(test_data, "pandas")

    def test_convert_candles_numeric_values(self) -> None:
        """Test converting candlestick data with numeric values."""
        test_data = [
            [1234567890, 50000.0, 51000.0, 49000.0, 50500.0, 10.5],
            [1234567891, 50500.5, 52000.25, 50000.1, 51000.75, 8.2],
        ]

        expected_dict_data = [
            {
                "timestamp": 1234567890,
                "open": 50000.0,
                "high": 51000.0,
                "low": 49000.0,
                "close": 50500.0,
                "volume": 10.5,
            },
            {
                "timestamp": 1234567891,
                "open": 50500.5,
                "high": 52000.25,
                "low": 50000.1,
                "close": 51000.75,
                "volume": 8.2,
            },
        ]

        mock_pandas = Mock()
        mock_dataframe = Mock()
        mock_pandas.DataFrame.return_value = mock_dataframe

        with (
            patch("bitvavo_client.df.convert.is_narwhals_available", return_value=True),
            patch.dict("sys.modules", {"pandas": mock_pandas}),
        ):
            result = convert_candles_to_dataframe(test_data, "pandas")

            mock_pandas.DataFrame.assert_called_once_with(expected_dict_data)
            assert result == mock_dataframe
