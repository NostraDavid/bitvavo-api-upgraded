# License notice from LICENSE.txt:
# Copyright (c) 2024, Bitvavo B.V.

"""Tests for bitvavo_client.core.validation_helpers module."""

from __future__ import annotations

import pytest
from pydantic import BaseModel, ValidationError, field_validator

from bitvavo_client.core.validation_helpers import format_validation_error, safe_validate


class ValidationModel(BaseModel):
    """Test model for validation testing."""

    name: str
    age: int
    price: str

    @field_validator("price")
    @classmethod
    def validate_price(cls, v: str) -> str:
        """Validate price format."""
        if not v.replace(".", "").replace("-", "").isdigit():
            msg = "Price must be a decimal string"
            raise ValueError(msg)
        return v


class OrderModel(BaseModel):
    """Test model for order validation testing."""

    side: str
    amount: str
    price: str

    @field_validator("side")
    @classmethod
    def validate_side(cls, v: str) -> str:
        """Validate order side."""
        if v not in ["BUY", "SELL"]:
            msg = "Order side must be 'BUY' or 'SELL'"
            raise ValueError(msg)
        return v


class TestFormatValidationError:
    """Test format_validation_error function."""

    def test_format_single_validation_error(self) -> None:
        """Test formatting a single validation error."""

        try:
            ValidationModel(name="John", age="not_an_int", price="10.50")  # type: ignore[arg-type]
        except ValidationError as e:
            result = format_validation_error(e)

            assert "🚫 Validation failed for ValidationModel:" in result
            assert "📍 Field 'age':" in result
            assert "Type: int_parsing" in result
            assert "Input: 'not_an_int'" in result

    def test_format_multiple_validation_errors(self) -> None:
        """Test formatting multiple validation errors."""
        try:
            ValidationModel(name=123, age="not_an_int", price="invalid_price")  # type: ignore[arg-type]
        except ValidationError as e:
            result = format_validation_error(e)

            assert "🚫 Validation failed for ValidationModel:" in result
            assert "📍 Field 'name':" in result
            assert "📍 Field 'age':" in result
            assert "📍 Field 'price':" in result

    def test_format_missing_field_error(self) -> None:
        """Test formatting missing field validation error."""
        try:
            ValidationModel(name="John", age=25)  # type: ignore[call-arg] # Missing 'price' field
        except ValidationError as e:
            result = format_validation_error(e)

            assert "🚫 Validation failed for ValidationModel:" in result
            assert "📍 Field 'price':" in result
            assert "Type: missing" in result
            assert "💡 This field is required" in result

    def test_format_error_with_input_data(self) -> None:
        """Test formatting error with input data included."""
        input_data = {"name": "John", "age": "not_an_int", "price": "10.50"}

        try:
            ValidationModel(**input_data)  # type: ignore[arg-type]
        except ValidationError as e:
            result = format_validation_error(e, input_data)

            assert "📋 Original input data:" in result
            assert '"name": "John"' in result
            assert '"age": "not_an_int"' in result
            assert '"price": "10.50"' in result

    def test_format_error_with_large_input_data(self) -> None:
        """Test formatting error with large input data (should be truncated)."""
        # Create large input data
        large_data = {
            "name": "John",
            "age": "not_an_int",
            "price": "10.50",
            "large_field": "x" * 1000,  # Very long string
        }

        try:
            ValidationModel(**large_data)  # type: ignore[arg-type]
        except ValidationError as e:
            result = format_validation_error(e, large_data)
            assert "📋 Original input data:" in result
            assert "...\n  (truncated)" in result

    def test_format_error_with_non_serializable_input(self) -> None:
        """Test formatting error with non-JSON-serializable input data."""

        class NonSerializable:
            def __repr__(self) -> str:
                return "NonSerializable()"

        input_data = {"name": "John", "age": NonSerializable(), "price": "10.50"}

        try:
            ValidationModel(**input_data)  # type: ignore[arg-type]
        except ValidationError as e:
            result = format_validation_error(e, input_data)
            assert "📋 Original input data:" in result
            assert "NonSerializable()" in result

    def test_format_error_with_large_non_serializable_input(self) -> None:
        """Test formatting error with large non-serializable input (should be truncated)."""

        class LargeNonSerializable:
            def __repr__(self) -> str:
                return "LargeNonSerializable(" + "x" * 300 + ")"

        input_data = {"name": "John", "age": LargeNonSerializable(), "price": "10.50"}

        try:
            ValidationModel(**input_data)  # type: ignore[arg-type]
        except ValidationError as e:
            result = format_validation_error(e, input_data)
            assert "📋 Original input data:" in result

    def test_format_string_type_error_suggestion(self) -> None:
        """Test that string type errors get helpful suggestions."""
        try:
            ValidationModel(name=123, age=25, price="10.50")  # type: ignore[arg-type]
        except ValidationError as e:
            result = format_validation_error(e)
            assert "💡 Expected a string value" in result

    def test_format_decimal_error_suggestion(self) -> None:
        """Test that decimal/numeric errors get helpful suggestions."""
        try:
            ValidationModel(name="John", age=25, price="invalid_decimal")
        except ValidationError as e:
            result = format_validation_error(e)
            # Should detect decimal-related error and provide suggestion
            assert "💡 Check the value format and constraints" in result

    def test_format_order_side_error_suggestion(self) -> None:
        """Test that order side errors get helpful suggestions."""
        try:
            OrderModel(side="INVALID", amount="1.0", price="100.0")  # type: ignore[arg-type]
        except ValidationError as e:
            result = format_validation_error(e)
            assert "📍 Field 'side': Value error, Order side must be 'BUY' or 'SELL'" in result

    def test_format_error_no_input_data(self) -> None:
        """Test formatting error without input data."""
        try:
            ValidationModel(name="John", age="not_an_int", price="10.50")  # type: ignore[arg-type]
        except ValidationError as e:
            result = format_validation_error(e, None)

            assert "🚫 Validation failed for ValidationModel:" in result
            assert "📋 Original input data:" not in result

    def test_format_error_empty_input_data(self) -> None:
        """Test formatting error with empty input data."""
        try:
            ValidationModel(name="John", age="not_an_int", price="10.50")  # type: ignore[arg-type]
        except ValidationError as e:
            result = format_validation_error(e, {})

            assert "📋 Original input data:" in result
            assert "{}" in result

    def test_format_error_nested_field_path(self) -> None:
        """Test formatting error with nested field paths."""

        class NestedModel(BaseModel):
            user: ValidationModel

        try:
            NestedModel(user={"name": 123, "age": 25, "price": "10.50"})  # type: ignore[arg-type]
        except ValidationError as e:
            result = format_validation_error(e)

            assert "📍 Field 'user -> name':" in result


class TestSafeValidate:
    """Test safe_validate function."""

    def test_safe_validate_success(self) -> None:
        """Test successful validation with safe_validate."""
        data = {"name": "John", "age": 25, "price": "10.50"}
        result = safe_validate(ValidationModel, data)

        assert isinstance(result, ValidationModel)
        assert result.name == "John"
        assert result.age == 25
        assert result.price == "10.50"

    def test_safe_validate_failure_default_operation_name(self) -> None:
        """Test validation failure with default operation name."""
        data = {"name": "John", "age": "not_an_int", "price": "10.50"}

        with pytest.raises(ValueError, match="❌ Validation failed:"):
            safe_validate(ValidationModel, data)  # type: ignore[arg-type]

    def test_safe_validate_failure_custom_operation_name(self) -> None:
        """Test validation failure with custom operation name."""
        data = {"name": "John", "age": "not_an_int", "price": "10.50"}

        with pytest.raises(ValueError, match="❌ Order Creation failed:"):
            safe_validate(ValidationModel, data, "order creation")  # type: ignore[arg-type]

    def test_safe_validate_enhanced_error_message(self) -> None:
        """Test that safe_validate provides enhanced error messages."""
        data = {"name": "John", "age": "not_an_int", "price": "10.50"}

        with pytest.raises(ValueError) as exc_info:  # noqa: PT011
            safe_validate(ValidationModel, data, "test operation")  # type: ignore[arg-type]

        error_message = str(exc_info.value)
        assert "❌ Test Operation failed:" in error_message
        assert "🚫 Validation failed for ValidationModel:" in error_message
        assert "📍 Field 'age':" in error_message
        assert "Type: int_parsing" in error_message

    def test_safe_validate_preserves_original_exception(self) -> None:
        """Test that safe_validate preserves the original ValidationError as __cause__."""
        data = {"name": "John", "age": "not_an_int", "price": "10.50"}

        with pytest.raises(ValueError) as exc_info:  # noqa: PT011
            safe_validate(ValidationModel, data)  # type: ignore[arg-type]

        assert isinstance(exc_info.value.__cause__, ValidationError)

    def test_safe_validate_with_missing_fields(self) -> None:
        """Test safe_validate with missing required fields."""
        data = {"name": "John"}  # Missing age and price

        with pytest.raises(ValueError) as exc_info:  # noqa: PT011
            safe_validate(ValidationModel, data, "incomplete data test")  # type: ignore[arg-type]

        error_message = str(exc_info.value)
        assert "❌ Incomplete Data Test failed:" in error_message
        assert "💡 This field is required" in error_message

    def test_safe_validate_with_complex_validation_error(self) -> None:
        """Test safe_validate with complex validation errors."""
        data = {"side": "INVALID_SIDE", "amount": "not_numeric", "price": "100.0"}

        with pytest.raises(ValueError) as exc_info:  # noqa: PT011
            safe_validate(OrderModel, data, "order validation")  # type: ignore[arg-type]

        error_message = str(exc_info.value)
        assert "❌ Order Validation failed:" in error_message
        assert "📍 Field 'side':" in error_message
        assert "💡 Check the value format and constraints" in error_message


class TestValidationHelpersIntegration:
    """Test integration scenarios for validation helpers."""

    def test_end_to_end_validation_workflow(self) -> None:
        """Test complete validation workflow from error to formatted message."""

        # Test data with multiple validation errors
        invalid_data = {
            "name": 123,  # Should be string
            "age": "not_a_number",  # Should be int
            "price": "invalid_decimal",  # Should be valid decimal string
        }

        # Test that safe_validate fails appropriately
        with pytest.raises(ValueError) as exc_info:  # noqa: PT011
            safe_validate(ValidationModel, invalid_data, "comprehensive test")  # type: ignore[arg-type]

        error_message = str(exc_info.value)

        # Verify all expected elements are in the error message
        assert "❌ Comprehensive Test failed:" in error_message
        assert "🚫 Validation failed for ValidationModel:" in error_message
        assert "📍 Field 'name':" in error_message
        assert "📍 Field 'age':" in error_message
        assert "📍 Field 'price':" in error_message
        assert "💡 Expected a string value" in error_message

        # Test that format_validation_error can be used independently
        try:
            ValidationModel(**invalid_data)
        except ValidationError as e:
            formatted = format_validation_error(e, invalid_data)
            assert "📋 Original input data:" in formatted
            assert '"name": 123' in formatted

    def test_validation_helpers_with_real_world_data(self) -> None:
        """Test validation helpers with realistic API data scenarios."""
        # Simulate malformed API response data
        api_response_data = {
            "side": "BUY",
            "amount": "1.5",
            "price": None,  # API returned None instead of string
        }

        with pytest.raises(ValueError) as exc_info:  # noqa: PT011
            safe_validate(OrderModel, api_response_data, "API response parsing")  # type: ignore[arg-type]

        error_message = str(exc_info.value)
        assert "❌ Api Response Parsing failed:" in error_message
        assert "Input: None" in error_message

    def test_validation_helpers_performance_with_large_errors(self) -> None:
        """Test that validation helpers handle large validation errors efficiently."""

        # Create a model with many fields to generate many errors
        class LargeModel(BaseModel):
            field1: str
            field2: str
            field3: str
            field4: str
            field5: str
            field6: str
            field7: str
            field8: str
            field9: str
            field10: str

        # Pass all wrong types to generate many errors
        invalid_data = {f"field{i}": i for i in range(1, 11)}

        try:
            LargeModel(**invalid_data)  # type: ignore[arg-type]
        except ValidationError as e:
            # This should complete without hanging or excessive memory usage
            result = format_validation_error(e, invalid_data)
            assert "🚫 Validation failed for LargeModel:" in result
            assert len(result.split("📍 Field")) == 11  # 10 fields + original line
