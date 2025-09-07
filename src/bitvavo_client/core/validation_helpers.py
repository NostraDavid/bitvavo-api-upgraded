"""Simple validation utilities for better error reporting."""

from __future__ import annotations

import json
from typing import Any

from pydantic import ValidationError


def format_validation_error(error: ValidationError, input_data: Any = None) -> str:  # noqa: C901 (too complex)
    """
    Format a Pydantic ValidationError into a human-readable message.

    Args:
        error: The ValidationError to format
        input_data: Optional input data that caused the error

    Returns:
        Formatted error message with context
    """
    # Get model name from the error title or use a default
    model_name = getattr(error, "title", "Model")
    error_lines = [f"🚫 Validation failed for {model_name}:"]

    for err in error.errors():
        location = " -> ".join(str(loc) for loc in err["loc"])
        error_type = err["type"]
        message = err["msg"]

        # Add context about the input value if available
        input_value = err.get("input", "N/A")

        error_lines.append(f"  📍 Field '{location}': {message}")
        error_lines.append(f"     Type: {error_type}")
        error_lines.append(f"     Input: {input_value!r}")

        # Add suggestions for common errors
        if error_type == "string_type":
            error_lines.append("     💡 Expected a string value")
        elif error_type == "value_error":
            error_lines.append("     💡 Check the value format and constraints")
        elif error_type == "missing":
            error_lines.append("     💡 This field is required")
        elif "decimal" in message.lower() or "numeric" in message.lower():
            error_lines.append("     💡 Use a decimal string like '123.45'")
        elif "side" in location.lower():
            error_lines.append("     💡 Order side must be 'BUY' or 'SELL'")

        error_lines.append("")  # Empty line between errors

    # Add the original input data if provided (truncated for readability)
    if input_data is not None:
        error_lines.append("📋 Original input data:")
        try:
            data_str = json.dumps(input_data, indent=2, default=str)
            # Truncate if too long
            if len(data_str) > 500:  # noqa: PLR2004 (magic var)
                data_str = data_str[:500] + "...\n  (truncated)"
            error_lines.append(data_str)
        except (TypeError, ValueError):
            data_repr = repr(input_data)
            if len(data_repr) > 200:  # noqa: PLR2004 (magic var)
                data_repr = data_repr[:200] + "...(truncated)"
            error_lines.append(data_repr)

    return "\n".join(error_lines)


def safe_validate(model_class: Any, data: Any, operation_name: str = "validation") -> Any:
    """
    Safely validate data with enhanced error reporting.

    Args:
        model_class: The Pydantic model class to validate against
        data: The data to validate
        operation_name: Name of the operation for error context

    Returns:
        Validated model instance

    Raises:
        ValueError: With enhanced error message if validation fails
    """
    try:
        return model_class.model_validate(data)
    except ValidationError as e:
        enhanced_error = format_validation_error(e, data)
        msg = f"❌ {operation_name.title()} failed:\n{enhanced_error}"
        raise ValueError(msg) from e
