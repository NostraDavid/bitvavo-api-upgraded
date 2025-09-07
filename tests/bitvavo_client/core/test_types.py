"""Tests for bitvavo_client.core.types module."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover
    from bitvavo_client.core.types import AnyDict


class TestAnyDict:
    """Test AnyDict type alias."""

    def test_anydict_type_alias(self) -> None:
        """Test that AnyDict is correctly aliased to dict[str, Any]."""

        # Test basic usage
        test_dict: AnyDict = {"key": "value", "number": 42, "nested": {"inner": True}}

        assert isinstance(test_dict, dict)
        assert test_dict["key"] == "value"
        assert test_dict["number"] == 42
        assert test_dict["nested"]["inner"] is True

    def test_anydict_accepts_any_values(self) -> None:
        """Test that AnyDict accepts various value types."""

        test_dict: AnyDict = {
            "string": "hello",
            "int": 123,
            "float": 45.67,
            "bool": True,
            "none": None,
            "list": [1, 2, 3],
            "dict": {"nested": "value"},
        }

        assert test_dict["string"] == "hello"
        assert test_dict["int"] == 123
        assert test_dict["float"] == 45.67
        assert test_dict["bool"] is True
        assert test_dict["none"] is None
        assert test_dict["list"] == [1, 2, 3]
        assert test_dict["dict"] == {"nested": "value"}

    def test_anydict_empty_dict(self) -> None:
        """Test that AnyDict works with empty dictionaries."""

        empty_dict: AnyDict = {}

        assert isinstance(empty_dict, dict)
        assert len(empty_dict) == 0

    def test_anydict_runtime_behavior(self) -> None:
        """Test runtime behavior of AnyDict."""

        # AnyDict is just a type alias, so at runtime it's still dict[str, Any]
        test_dict: AnyDict = {"key": "value"}

        # Should be able to add new items
        test_dict["new_key"] = "new_value"
        assert test_dict["new_key"] == "new_value"

        # Should be able to update existing items
        test_dict["key"] = 42
        assert test_dict["key"] == 42

        # Should work with dict methods
        assert "key" in test_dict
        assert "missing" not in test_dict
        assert list(test_dict.keys()) == ["key", "new_key"]
