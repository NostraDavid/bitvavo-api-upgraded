"""Type definitions for bitvavo_client."""

from typing import Any  # pragma: no cover

# Type aliases for better readability
Result = dict[str, Any] | list[dict[str, Any]]  # pragma: no cover
ErrorDict = dict[str, Any]  # pragma: no cover
AnyDict = dict[str, Any]  # pragma: no cover
StrDict = dict[str, str]  # pragma: no cover
IntDict = dict[str, int]  # pragma: no cover
StrIntDict = dict[str, str | int]  # pragma: no cover
