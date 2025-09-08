"""Tests for bitvavo_client.adapters.returns_adapter module."""

from __future__ import annotations

from typing import Any
from unittest.mock import Mock, patch

import httpx
import pytest
from pydantic import BaseModel, ValidationError
from returns.result import Failure, Success

from bitvavo_client.adapters.returns_adapter import (
    BitvavoError,
    BitvavoErrorPayload,
    BitvavoReturnsSettings,
    _enhance_dataframe_error,
    _json_from_response,
    _map_error,
    _validation_failure,
    decode_response_result,
    get_json_result,
    post_json_result,
    settings,
)


class TestBitvavoReturnsSettings:
    """Test BitvavoReturnsSettings configuration."""

    def test_default_settings(self) -> None:
        """Test default settings values."""
        default_settings = BitvavoReturnsSettings()

        assert default_settings.base_url == "https://api.bitvavo.com/v2"
        assert default_settings.timeout_seconds == 10.0

    def test_custom_settings(self) -> None:
        """Test custom settings values."""
        custom_settings = BitvavoReturnsSettings(
            base_url="https://custom.api.com/v3",
            timeout_seconds=30.0,
        )

        assert custom_settings.base_url == "https://custom.api.com/v3"
        assert custom_settings.timeout_seconds == 30.0

    def test_environment_variable_prefix(self) -> None:
        """Test that environment variables use BITVAVO_ prefix."""
        # The model_config should have env_prefix set to "BITVAVO_"
        assert BitvavoReturnsSettings.model_config.get("env_prefix") == "BITVAVO_"

    def test_settings_singleton(self) -> None:
        """Test that the module-level settings instance exists."""
        assert isinstance(settings, BitvavoReturnsSettings)
        assert settings.base_url == "https://api.bitvavo.com/v2"


class TestBitvavoErrorPayload:
    """Test BitvavoErrorPayload model."""

    def test_valid_error_payload(self) -> None:
        """Test parsing a valid error payload."""
        data = {"errorCode": 205, "error": "Invalid parameter value."}
        payload = BitvavoErrorPayload.model_validate(data)

        assert payload.error_code == 205
        assert payload.error == "Invalid parameter value."

    def test_error_payload_with_alias(self) -> None:
        """Test that errorCode alias works correctly."""
        data = {"errorCode": 404, "error": "Not found"}
        payload = BitvavoErrorPayload.model_validate(data)

        assert payload.error_code == 404
        assert payload.error == "Not found"

    def test_error_payload_missing_fields(self) -> None:
        """Test error payload with missing fields."""
        with pytest.raises(ValidationError):
            BitvavoErrorPayload.model_validate({"errorCode": 500})

        with pytest.raises(ValidationError):
            BitvavoErrorPayload.model_validate({"error": "Some error"})


class TestBitvavoError:
    """Test BitvavoError model."""

    def test_bitvavo_error_creation(self) -> None:
        """Test creating a BitvavoError instance."""
        error = BitvavoError(
            http_status=400,
            error_code=205,
            reason="Invalid parameter value",
            message="The value provided is not valid",
            raw={"errorCode": 205, "error": "Invalid parameter value"},
        )

        assert error.http_status == 400
        assert error.error_code == 205
        assert error.reason == "Invalid parameter value"
        assert error.message == "The value provided is not valid"
        assert error.raw == {"errorCode": 205, "error": "Invalid parameter value"}


class TestJsonFromResponse:
    """Test _json_from_response function."""

    def test_valid_json_response(self) -> None:
        """Test parsing valid JSON response."""
        mock_response = Mock(spec=httpx.Response)
        mock_response.json.return_value = {"key": "value", "number": 42}

        result = _json_from_response(mock_response)

        assert result == {"key": "value", "number": 42}
        mock_response.json.assert_called_once()

    def test_invalid_json_response(self) -> None:
        """Test handling invalid JSON response."""
        mock_response = Mock(spec=httpx.Response)
        mock_response.json.side_effect = ValueError("Invalid JSON")
        mock_response.text = "Not valid JSON"

        result = _json_from_response(mock_response)

        assert result == {"raw": "Not valid JSON"}

    def test_non_dict_json_response(self) -> None:
        """Test handling JSON response that's not a dictionary."""
        mock_response = Mock(spec=httpx.Response)
        mock_response.json.return_value = ["array", "response"]
        mock_response.text = '["array", "response"]'

        with pytest.raises(AssertionError, match="Expected JSON response to be a dictionary"):
            _json_from_response(mock_response)


class TestMapError:
    """Test _map_error function."""

    def test_map_error_with_known_error_code(self) -> None:
        """Test mapping error with known error code and status."""
        mock_response = Mock(spec=httpx.Response)
        mock_response.status_code = 400
        mock_response.json.return_value = {"errorCode": 205, "error": "Invalid parameter value."}

        error = _map_error(mock_response)

        assert error.http_status == 400
        assert error.error_code == 205
        assert error.reason == "Invalid parameter value."
        assert error.message == "Invalid parameter value."
        assert error.raw == {"errorCode": 205, "error": "Invalid parameter value."}

    def test_map_error_with_unknown_error_code(self) -> None:
        """Test mapping error with unknown error code."""
        mock_response = Mock(spec=httpx.Response)
        mock_response.status_code = 400
        mock_response.json.return_value = {"errorCode": 999, "error": "Unknown error"}

        error = _map_error(mock_response)

        assert error.http_status == 400
        assert error.error_code == 999
        assert error.reason == "Unknown error"
        assert error.message == "Unknown error"

    def test_map_error_with_unknown_status_code(self) -> None:
        """Test mapping error with unknown HTTP status code."""
        mock_response = Mock(spec=httpx.Response)
        mock_response.status_code = 999
        mock_response.json.return_value = {"errorCode": 205, "error": "Some error"}

        error = _map_error(mock_response)

        assert error.http_status == 999
        assert error.error_code == 205
        assert error.reason == "Some error"  # Falls back to message when status unknown
        assert error.message == "Some error"

    def test_map_error_missing_error_fields(self) -> None:
        """Test mapping error with missing error fields."""
        mock_response = Mock(spec=httpx.Response)
        mock_response.status_code = 500
        mock_response.json.return_value = {}

        error = _map_error(mock_response)

        assert error.http_status == 500
        assert error.error_code == -1
        assert error.reason == "Unknown error"
        assert error.message == "Unknown error"

    def test_map_error_with_message_field(self) -> None:
        """Test mapping error that uses 'message' instead of 'error'."""
        mock_response = Mock(spec=httpx.Response)
        mock_response.status_code = 500
        mock_response.json.return_value = {"errorCode": 101, "message": "Server error"}

        error = _map_error(mock_response)

        assert error.http_status == 500
        assert error.error_code == 101
        assert error.message == "Server error"

    def test_map_error_invalid_json_response(self) -> None:
        """Test mapping error when response is not valid JSON."""
        mock_response = Mock(spec=httpx.Response)
        mock_response.status_code = 500
        mock_response.json.side_effect = ValueError("Invalid JSON")
        mock_response.text = "Internal Server Error"

        error = _map_error(mock_response)

        assert error.http_status == 500
        assert error.error_code == -1
        assert error.reason == "Unknown error"
        assert error.message == "Unknown error"
        assert error.raw == {"raw": "Internal Server Error"}


class TestValidationFailure:
    """Test _validation_failure function."""

    def test_validation_failure_creation(self) -> None:
        """Test creating a validation failure error."""
        payload = {"field": "invalid_value"}
        error = _validation_failure("Field validation failed", payload)

        assert error.http_status == 500
        assert error.error_code == -1
        assert error.reason == "Model validation failed"
        assert error.message == "Field validation failed"
        assert error.raw == payload


class TestEnhanceDataframeError:
    """Test _enhance_dataframe_error function."""

    def test_enhance_dataframe_error_with_schema_mismatch(self) -> None:
        """Test enhancing DataFrame error with schema mismatch."""
        exc = Exception("column-schema names do not match the data dictionary")
        data = {"price": "50000", "volume": "1.5", "extra_field": "value"}
        schema = {"price": float, "volume": float, "timestamp": int}

        class MockModel:
            __name__ = "TestModel"

        enhanced = _enhance_dataframe_error(exc, data, schema, MockModel)

        assert "DataFrame schema mismatch for MockModel:" in enhanced
        assert "Expected fields: ['price', 'volume', 'timestamp']" in enhanced
        assert "Actual fields:   ['price', 'volume', 'extra_field']" in enhanced
        assert "Missing fields:  {'timestamp'}" in enhanced
        assert "Extra fields:    {'extra_field'}" in enhanced

    def test_enhance_dataframe_error_with_list_data(self) -> None:
        """Test enhancing DataFrame error with list data."""
        exc = Exception("column-schema names do not match the data dictionary")
        data = [{"price": "50000", "volume": "1.5"}]
        schema = {"price": float, "volume": float, "timestamp": int}

        class MockModel:
            __name__ = "TestModel"

        enhanced = _enhance_dataframe_error(exc, data, schema, MockModel)

        assert "DataFrame schema mismatch for MockModel:" in enhanced
        assert "Expected fields: ['price', 'volume', 'timestamp']" in enhanced
        assert "Actual fields:   ['price', 'volume']" in enhanced

    def test_enhance_dataframe_error_non_schema_error(self) -> None:
        """Test enhancing non-schema DataFrame error."""
        exc = Exception("Some other error")
        data = {"price": "50000"}
        schema = {"price": float}

        class MockModel:
            __name__ = "TestModel"

        enhanced = _enhance_dataframe_error(exc, data, schema, MockModel)

        assert enhanced == "Some other error"

    def test_enhance_dataframe_error_empty_data(self) -> None:
        """Test enhancing DataFrame error with empty data."""
        exc = Exception("column-schema names do not match the data dictionary")
        data = []
        schema = {"price": float}

        class MockModel:
            __name__ = "TestModel"

        enhanced = _enhance_dataframe_error(exc, data, schema, MockModel)

        assert "Actual fields:   []" in enhanced

    def test_enhance_dataframe_error_no_schema(self) -> None:
        """Test enhancing DataFrame error with no schema."""
        exc = Exception("column-schema names do not match the data dictionary")
        data = {"price": "50000"}
        schema = None

        class MockModel:
            __name__ = "TestModel"

        enhanced = _enhance_dataframe_error(exc, data, schema, MockModel)

        assert "Expected fields: []" in enhanced


class TestDecodeResponseResult:
    """Test decode_response_result function."""

    def test_decode_successful_response_with_pydantic_model(self) -> None:
        """Test decoding successful response with Pydantic model."""

        class TestModel(BaseModel):
            name: str
            value: int

        mock_response = Mock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = {"name": "test", "value": 42}

        result = decode_response_result(mock_response, TestModel)

        assert isinstance(result, Success)
        parsed = result.unwrap()
        assert isinstance(parsed, TestModel)
        assert parsed.name == "test"
        assert parsed.value == 42

    def test_decode_successful_response_with_any_model(self) -> None:
        """Test decoding successful response with Any model."""
        mock_response = Mock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = {"arbitrary": "data", "number": 123}

        result = decode_response_result(mock_response, Any)  # type: ignore[arg-type]

        assert isinstance(result, Success)
        data = result.unwrap()
        assert data == {"arbitrary": "data", "number": 123}

    def test_decode_successful_response_with_any_model_error_like_data(self) -> None:
        """Test decoding response with Any model but error-like data."""
        mock_response = Mock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = {"errorCode": 205, "error": "Some error"}

        result = decode_response_result(mock_response, Any)  # type: ignore[arg-type]

        assert isinstance(result, Failure)
        error = result.failure()
        assert error.error_code == 205

    def test_decode_error_response(self) -> None:
        """Test decoding error response."""
        mock_response = Mock(spec=httpx.Response)
        mock_response.status_code = 400
        mock_response.json.return_value = {"errorCode": 205, "error": "Invalid parameter"}

        result = decode_response_result(mock_response, dict)

        assert isinstance(result, Failure)
        error = result.failure()
        assert error.http_status == 400
        assert error.error_code == 205

    def test_decode_response_invalid_json(self) -> None:
        """Test decoding response with invalid JSON."""
        mock_response = Mock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.side_effect = ValueError("Invalid JSON")

        result = decode_response_result(mock_response, dict)

        assert isinstance(result, Success)
        data = result.unwrap()
        assert "raw" in data

    def test_decode_response_model_validation_error(self) -> None:
        """Test decoding response with model validation error."""

        class TestModel(BaseModel):
            required_field: str

        mock_response = Mock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = {"wrong_field": "value"}

        result = decode_response_result(mock_response, TestModel)

        assert isinstance(result, Failure)
        error = result.failure()
        assert error.reason == "Model validation failed"
        assert error.http_status == 500

    def test_decode_response_model_validation_error_with_bitvavo_error_data(self) -> None:
        """Test model validation error when data looks like a Bitvavo error."""

        class TestModel(BaseModel):
            required_field: str

        mock_response = Mock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = {"errorCode": 205, "error": "Some error"}

        result = decode_response_result(mock_response, TestModel)

        assert isinstance(result, Failure)
        error = result.failure()
        # Should map as Bitvavo error, not validation error
        assert error.error_code == 205

    def test_decode_response_with_custom_constructor(self) -> None:
        """Test decoding response with custom constructor."""

        def custom_constructor(data: dict[str, Any]) -> dict[str, str]:
            return {k: str(v) for k, v in data.items()}

        mock_response = Mock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = {"number": 42, "bool": True}

        result = decode_response_result(mock_response, custom_constructor)  # type: ignore[arg-type]

        assert isinstance(result, Success)
        data = result.unwrap()
        assert data == {"number": "42", "bool": "True"}

    def test_decode_response_with_schema_parameter(self) -> None:
        """Test decoding response with schema parameter."""
        mock_response = Mock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = [{"price": "50000", "volume": "1.5"}]

        def mock_constructor(data: Any, schema: dict[str, type]) -> dict[str, Any]:
            return {"processed": True, "data": data, "schema": schema}

        schema = {"price": float, "volume": float}
        result = decode_response_result(mock_response, mock_constructor, schema)  # type: ignore[arg-type]

        assert isinstance(result, Success)
        processed = result.unwrap()
        assert processed["processed"] is True
        assert processed["schema"] == schema

    def test_decode_response_with_polars_dataframe(self) -> None:
        """Test decoding response with Polars DataFrame."""
        mock_df = Mock()

        # Create a mock class that looks like polars.DataFrame
        mock_polars_dataframe = Mock()
        # Configure mock to pass the polars detection check
        mock_polars_dataframe.configure_mock(__name__="DataFrame", __module__="polars.dataframe")
        mock_polars_dataframe.return_value = mock_df

        mock_response = Mock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = [{"price": 50000, "volume": 1.5}]

        schema = {"price": float, "volume": float}
        result = decode_response_result(mock_response, mock_polars_dataframe, schema)  # type: ignore[arg-type]

        assert isinstance(result, Success)
        assert result.unwrap() is mock_df
        mock_polars_dataframe.assert_called_once_with([{"price": 50000, "volume": 1.5}], schema=schema)

    def test_decode_response_with_polars_import_error(self) -> None:
        """Test decoding response when Polars import fails."""
        mock_response = Mock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = [{"price": 50000, "volume": 1.5}]

        def mock_constructor(data: Any, schema: dict[str, type]) -> dict[str, Any]:
            return {"fallback": True, "data": data}

        # Polars import should fail, falling back to regular constructor
        with patch("builtins.__import__", side_effect=ImportError("No module named 'polars'")):
            schema = {"price": float, "volume": float}
            result = decode_response_result(mock_response, mock_constructor, schema)  # type: ignore[arg-type]

        assert isinstance(result, Success)
        processed = result.unwrap()
        assert processed["fallback"] is True

    def test_decode_response_dataframe_schema_mismatch_error(self) -> None:
        """Test decoding response with DataFrame schema mismatch."""

        class DataFrameSchemaMismatchError(Exception):
            """Custom exception for DataFrame schema mismatch tests."""

        mock_response = Mock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = [{"wrong_field": "value"}]

        def failing_constructor(data: Any, schema: dict[str, type]) -> None:
            error_msg = "column-schema names do not match the data dictionary"
            raise DataFrameSchemaMismatchError(error_msg)

        failing_constructor.__name__ = "TestDataFrame"

        schema = {"expected_field": str}
        result = decode_response_result(mock_response, failing_constructor, schema)  # type: ignore[arg-type]

        assert isinstance(result, Failure)
        error = result.failure()
        assert "DataFrame schema mismatch for TestDataFrame:" in error.message
        assert "Expected fields: ['expected_field']" in error.message
        assert "Actual fields:   ['wrong_field']" in error.message

    def test_decode_response_assert_model_not_none(self) -> None:
        """Test that assertion fails when model is None but not Any."""
        mock_response = Mock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = {"data": "value"}

        with pytest.raises(AssertionError, match="Model must be provided or set to Any"):
            decode_response_result(mock_response, None)

    def test_decode_response_assert_data_is_dict_or_list(self) -> None:
        """Test that assertion fails when JSON data is not dict or list."""
        mock_response = Mock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = "string_data"

        with pytest.raises(AssertionError, match="Expected JSON response to be a dictionary or list"):
            decode_response_result(mock_response, dict)


class TestGetJsonResult:
    """Test get_json_result function."""

    @patch("bitvavo_client.adapters.returns_adapter.settings")
    def test_get_json_result_success(self, mock_settings: Mock) -> None:
        """Test successful GET request."""
        mock_settings.base_url = "https://api.example.com/v2"
        mock_settings.timeout_seconds = 15.0

        mock_client = Mock(spec=httpx.Client)
        mock_response = Mock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = {"result": "success"}
        mock_client.get.return_value = mock_response

        result = get_json_result(mock_client, "/test", model=dict)

        assert isinstance(result, Success)
        data = result.unwrap()
        assert data == {"result": "success"}

        mock_client.get.assert_called_once_with(
            "https://api.example.com/v2/test",
            timeout=15.0,
        )

    @patch("bitvavo_client.adapters.returns_adapter.settings")
    def test_get_json_result_strips_slashes(self, mock_settings: Mock) -> None:
        """Test that URL construction handles leading/trailing slashes correctly."""
        mock_settings.base_url = "https://api.example.com/v2/"
        mock_settings.timeout_seconds = 10.0

        mock_client = Mock(spec=httpx.Client)
        mock_response = Mock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = {}
        mock_client.get.return_value = mock_response

        get_json_result(mock_client, "/test/endpoint", model=dict)

        mock_client.get.assert_called_once_with(
            "https://api.example.com/v2/test/endpoint",
            timeout=10.0,
        )

    @patch("bitvavo_client.adapters.returns_adapter.settings")
    def test_get_json_result_http_error(self, mock_settings: Mock) -> None:
        """Test GET request with HTTP error."""
        mock_settings.base_url = "https://api.example.com/v2"
        mock_settings.timeout_seconds = 10.0

        mock_client = Mock(spec=httpx.Client)
        mock_client.get.side_effect = httpx.ConnectError("Connection failed")

        result = get_json_result(mock_client, "/test", model=dict)

        assert isinstance(result, Failure)
        error = result.failure()
        assert error.http_status == 0
        assert error.error_code == -1
        assert error.reason == "Transport error"
        assert "Connection failed" in error.message

    @patch("bitvavo_client.adapters.returns_adapter.settings")
    def test_get_json_result_api_error_response(self, mock_settings: Mock) -> None:
        """Test GET request returning API error."""
        mock_settings.base_url = "https://api.example.com/v2"
        mock_settings.timeout_seconds = 10.0

        mock_client = Mock(spec=httpx.Client)
        mock_response = Mock(spec=httpx.Response)
        mock_response.status_code = 400
        mock_response.json.return_value = {"errorCode": 205, "error": "Invalid parameter"}
        mock_client.get.return_value = mock_response

        result = get_json_result(mock_client, "/test", model=dict)

        assert isinstance(result, Failure)
        error = result.failure()
        assert error.http_status == 400
        assert error.error_code == 205

    @patch("bitvavo_client.adapters.returns_adapter.settings")
    def test_get_json_result_with_pydantic_model(self, mock_settings: Mock) -> None:
        """Test GET request with Pydantic model parsing."""
        mock_settings.base_url = "https://api.example.com/v2"
        mock_settings.timeout_seconds = 10.0

        class TestModel(BaseModel):
            name: str
            value: int

        mock_client = Mock(spec=httpx.Client)
        mock_response = Mock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = {"name": "test", "value": 42}
        mock_client.get.return_value = mock_response

        result = get_json_result(mock_client, "/test", model=TestModel)

        assert isinstance(result, Success)
        parsed = result.unwrap()
        assert isinstance(parsed, TestModel)
        assert parsed.name == "test"
        assert parsed.value == 42


class TestPostJsonResult:
    """Test post_json_result function."""

    @patch("bitvavo_client.adapters.returns_adapter.settings")
    def test_post_json_result_success(self, mock_settings: Mock) -> None:
        """Test successful POST request."""
        mock_settings.base_url = "https://api.example.com/v2"
        mock_settings.timeout_seconds = 15.0

        mock_client = Mock(spec=httpx.Client)
        mock_response = Mock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = {"result": "created"}
        mock_client.post.return_value = mock_response

        payload = {"key": "value", "number": 123}
        result = post_json_result(mock_client, "/create", payload, model=dict)

        assert isinstance(result, Success)
        data = result.unwrap()
        assert data == {"result": "created"}

        mock_client.post.assert_called_once_with(
            "https://api.example.com/v2/create",
            json=payload,
            timeout=15.0,
        )

    @patch("bitvavo_client.adapters.returns_adapter.settings")
    def test_post_json_result_no_payload(self, mock_settings: Mock) -> None:
        """Test POST request with no payload."""
        mock_settings.base_url = "https://api.example.com/v2"
        mock_settings.timeout_seconds = 10.0

        mock_client = Mock(spec=httpx.Client)
        mock_response = Mock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = {"result": "ok"}
        mock_client.post.return_value = mock_response

        result = post_json_result(mock_client, "/create", model=dict)

        assert isinstance(result, Success)

        mock_client.post.assert_called_once_with(
            "https://api.example.com/v2/create",
            json={},
            timeout=10.0,
        )

    @patch("bitvavo_client.adapters.returns_adapter.settings")
    def test_post_json_result_none_payload(self, mock_settings: Mock) -> None:
        """Test POST request with None payload."""
        mock_settings.base_url = "https://api.example.com/v2"
        mock_settings.timeout_seconds = 10.0

        mock_client = Mock(spec=httpx.Client)
        mock_response = Mock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = {"result": "ok"}
        mock_client.post.return_value = mock_response

        result = post_json_result(mock_client, "/create", None, model=dict)

        assert isinstance(result, Success)

        mock_client.post.assert_called_once_with(
            "https://api.example.com/v2/create",
            json={},
            timeout=10.0,
        )

    @patch("bitvavo_client.adapters.returns_adapter.settings")
    def test_post_json_result_strips_slashes(self, mock_settings: Mock) -> None:
        """Test that URL construction handles leading/trailing slashes correctly."""
        mock_settings.base_url = "https://api.example.com/v2/"
        mock_settings.timeout_seconds = 10.0

        mock_client = Mock(spec=httpx.Client)
        mock_response = Mock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = {}
        mock_client.post.return_value = mock_response

        post_json_result(mock_client, "/create/order", {}, model=dict)

        mock_client.post.assert_called_once_with(
            "https://api.example.com/v2/create/order",
            json={},
            timeout=10.0,
        )

    @patch("bitvavo_client.adapters.returns_adapter.settings")
    def test_post_json_result_http_error(self, mock_settings: Mock) -> None:
        """Test POST request with HTTP error."""
        mock_settings.base_url = "https://api.example.com/v2"
        mock_settings.timeout_seconds = 10.0

        mock_client = Mock(spec=httpx.Client)
        mock_client.post.side_effect = httpx.TimeoutException("Request timeout")

        payload = {"key": "value"}
        result = post_json_result(mock_client, "/create", payload, model=dict)

        assert isinstance(result, Failure)
        error = result.failure()
        assert error.http_status == 0
        assert error.error_code == -1
        assert error.reason == "Transport error"
        assert "Request timeout" in error.message
        assert error.raw == {"payload": payload}

    @patch("bitvavo_client.adapters.returns_adapter.settings")
    def test_post_json_result_api_error_response(self, mock_settings: Mock) -> None:
        """Test POST request returning API error."""
        mock_settings.base_url = "https://api.example.com/v2"
        mock_settings.timeout_seconds = 10.0

        mock_client = Mock(spec=httpx.Client)
        mock_response = Mock(spec=httpx.Response)
        mock_response.status_code = 403
        mock_response.json.return_value = {"errorCode": 300, "error": "Authentication required"}
        mock_client.post.return_value = mock_response

        result = post_json_result(mock_client, "/private", model=dict)

        assert isinstance(result, Failure)
        error = result.failure()
        assert error.http_status == 403
        assert error.error_code == 300

    @patch("bitvavo_client.adapters.returns_adapter.settings")
    def test_post_json_result_no_model_specified(self, mock_settings: Mock) -> None:
        """Test POST request with no model specified."""
        mock_settings.base_url = "https://api.example.com/v2"
        mock_settings.timeout_seconds = 10.0

        mock_client = Mock(spec=httpx.Client)
        mock_response = Mock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = {"result": "ok"}
        mock_client.post.return_value = mock_response

        result = post_json_result(mock_client, "/create", model=dict)

        assert isinstance(result, Success)
        data = result.unwrap()
        assert data == {"result": "ok"}

    @patch("bitvavo_client.adapters.returns_adapter.settings")
    def test_post_json_result_with_pydantic_model(self, mock_settings: Mock) -> None:
        """Test POST request with Pydantic model parsing."""
        mock_settings.base_url = "https://api.example.com/v2"
        mock_settings.timeout_seconds = 10.0

        class ResponseModel(BaseModel):
            order_id: str
            status: str

        mock_client = Mock(spec=httpx.Client)
        mock_response = Mock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = {"order_id": "12345", "status": "created"}
        mock_client.post.return_value = mock_response

        payload = {"symbol": "BTC-EUR", "amount": "1.0"}
        result = post_json_result(mock_client, "/order", payload, model=ResponseModel)

        assert isinstance(result, Success)
        parsed = result.unwrap()
        assert isinstance(parsed, ResponseModel)
        assert parsed.order_id == "12345"
        assert parsed.status == "created"


class TestErrorCodeDirectory:
    """Test the error code directory functionality."""

    def test_known_error_codes_400_status(self) -> None:
        """Test mapping of known 400 status error codes."""
        mock_response = Mock(spec=httpx.Response)
        mock_response.status_code = 400
        mock_response.json.return_value = {"errorCode": 205, "error": "Invalid parameter value."}

        error = _map_error(mock_response)

        assert error.reason == "Invalid parameter value."

    def test_known_error_codes_403_status(self) -> None:
        """Test mapping of known 403 status error codes."""
        mock_response = Mock(spec=httpx.Response)
        mock_response.status_code = 403
        mock_response.json.return_value = {"errorCode": 300, "error": "Authentication required"}

        error = _map_error(mock_response)

        assert error.reason == "Authentication required to call this endpoint."

    def test_known_error_codes_429_status(self) -> None:
        """Test mapping of known 429 status error codes."""
        mock_response = Mock(spec=httpx.Response)
        mock_response.status_code = 429
        mock_response.json.return_value = {"errorCode": 105, "error": "Rate limit exceeded"}

        error = _map_error(mock_response)

        assert error.reason == "Rate limit exceeded. Account or IP address blocked temporarily."

    def test_known_error_codes_500_status(self) -> None:
        """Test mapping of known 500 status error codes."""
        mock_response = Mock(spec=httpx.Response)
        mock_response.status_code = 500
        mock_response.json.return_value = {"errorCode": 101, "error": "Server error"}

        error = _map_error(mock_response)

        assert error.reason == "Unknown server error. Operation success uncertain."


class TestIntegrationScenarios:
    """Test integration scenarios combining multiple functions."""

    @patch("bitvavo_client.adapters.returns_adapter.settings")
    def test_end_to_end_successful_request(self, mock_settings: Mock) -> None:
        """Test complete end-to-end successful request flow."""
        mock_settings.base_url = "https://api.bitvavo.com/v2"
        mock_settings.timeout_seconds = 10.0

        class MarketModel(BaseModel):
            market: str
            status: str
            base: str
            quote: str

        mock_client = Mock(spec=httpx.Client)
        mock_response = Mock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "market": "BTC-EUR",
            "status": "trading",
            "base": "BTC",
            "quote": "EUR",
        }
        mock_client.get.return_value = mock_response

        result = get_json_result(mock_client, "markets/BTC-EUR", model=MarketModel)

        assert isinstance(result, Success)
        market = result.unwrap()
        assert isinstance(market, MarketModel)
        assert market.market == "BTC-EUR"
        assert market.status == "trading"

    @patch("bitvavo_client.adapters.returns_adapter.settings")
    def test_end_to_end_bitvavo_error_flow(self, mock_settings: Mock) -> None:
        """Test complete end-to-end error flow."""
        mock_settings.base_url = "https://api.bitvavo.com/v2"
        mock_settings.timeout_seconds = 10.0

        mock_client = Mock(spec=httpx.Client)
        mock_response = Mock(spec=httpx.Response)
        mock_response.status_code = 400
        mock_response.json.return_value = {"errorCode": 205, "error": "Invalid parameter value."}
        mock_client.post.return_value = mock_response

        result = post_json_result(
            mock_client,
            "order",
            {"market": "INVALID", "side": "buy", "amount": "abc"},
            model=dict,
        )

        assert isinstance(result, Failure)
        error = result.failure()
        assert isinstance(error, BitvavoError)
        assert error.http_status == 400
        assert error.error_code == 205
        assert error.reason == "Invalid parameter value."
        assert "Invalid parameter value." in error.message

    @patch("bitvavo_client.adapters.returns_adapter.settings")
    def test_end_to_end_transport_error_flow(self, mock_settings: Mock) -> None:
        """Test complete end-to-end transport error flow."""
        mock_settings.base_url = "https://api.bitvavo.com/v2"
        mock_settings.timeout_seconds = 10.0

        mock_client = Mock(spec=httpx.Client)
        mock_client.get.side_effect = httpx.ConnectError("DNS resolution failed")

        result = get_json_result(mock_client, "time", model=dict)

        assert isinstance(result, Failure)
        error = result.failure()
        assert isinstance(error, BitvavoError)
        assert error.http_status == 0
        assert error.error_code == -1
        assert error.reason == "Transport error"
        assert "DNS resolution failed" in error.message
