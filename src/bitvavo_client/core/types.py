"""Type definitions for bitvavo_client."""

from __future__ import annotations

from typing import Any

# Type aliases for better readability
Result = dict[str, Any] | list[dict[str, Any]]
ErrorDict = dict[str, Any]
AnyDict = dict[str, Any]
StrDict = dict[str, str]
IntDict = dict[str, int]
StrIntDict = dict[str, str | int]
