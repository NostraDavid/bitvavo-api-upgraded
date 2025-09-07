"""Signature creation utilities for Bitvavo API authentication."""

from __future__ import annotations

import hashlib
import hmac
import json
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover
    from bitvavo_client.core.types import AnyDict


def create_signature(timestamp: int, method: str, url: str, body: AnyDict | None, api_secret: str) -> str:
    """Create HMAC-SHA256 signature for Bitvavo API authentication.

    Args:
        timestamp: Unix timestamp in milliseconds
        method: HTTP method (GET, POST, PUT, DELETE)
        url: API endpoint URL without base URL
        body: Request body as dictionary (optional)
        api_secret: API secret key

    Returns:
        HMAC-SHA256 signature as hexadecimal string
    """
    string = f"{timestamp}{method}/v2{url}"
    if body is not None and len(body) > 0:
        string += json.dumps(body, separators=(",", ":"))

    signature = hmac.new(api_secret.encode("utf-8"), string.encode("utf-8"), hashlib.sha256).hexdigest()

    return signature
