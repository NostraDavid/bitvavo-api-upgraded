"""Adapter utilities that return `returns.result.Result` types.

This integrates clean Result-based decoding and lightweight request helpers on top
of httpx, mapping Bitvavo errors to a structured model.

The adapter is optional and doesn't alter the existing facade. Users who prefer
functional error handling can import and use these utilities directly.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, ClassVar, TypeVar

import httpx
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from returns.result import Failure, Result, Success
from structlog.stdlib import get_logger

if TYPE_CHECKING:  # pragma: no cover
    from collections.abc import Mapping

T = TypeVar("T")

logger = get_logger("bitvavo.adapter")


# ---------------------------------------------------------------------------
# Settings (pydantic v2)
# ---------------------------------------------------------------------------


class BitvavoReturnsSettings(BaseSettings):
    """Settings for the returns-based adapter.

    These are intentionally separate from the core BitvavoSettings to avoid
    coupling and to let users override independently via environment vars.
    """

    model_config: ClassVar[SettingsConfigDict] = SettingsConfigDict(
        env_prefix="BITVAVO_",
        extra="ignore",
        env_file=".env",
        env_file_encoding="utf-8",
    )

    base_url: str = "https://api.bitvavo.com/v2"
    timeout_seconds: float = 10.0


settings = BitvavoReturnsSettings()


# ---------------------------------------------------------------------------
# Domain models
# ---------------------------------------------------------------------------


class BitvavoErrorPayload(BaseModel):
    """Typical Bitvavo error payload.

    Example:
        {"errorCode": 205, "error": "Invalid parameter value."}
    """

    error_code: int = Field(alias="errorCode")
    error: str


class BitvavoError(BaseModel):
    http_status: int
    error_code: int
    reason: str
    message: str
    raw: dict[str, Any]


# ---------------------------------------------------------------------------
# Error code directory (from Bitvavo docs)
# ---------------------------------------------------------------------------

_BITVAVO_ERROR_REASONS: dict[int, dict[int, str]] = {
    400: {
        102: "The JSON object you sent is invalid.",
        200: "Path parameters are not accepted for this endpoint.",
        201: "Body parameters are not accepted for this endpoint.",
        202: "A parameter is not supported for this orderType.",
        203: "Missing or incompatible parameters in your request.",
        204: "You used a parameter that is not valid for this endpoint.",
        205: "Invalid parameter value.",
        206: "Incompatible parameters in your call.",
        210: "amount exceeds the maximum allowed for the market.",
        211: "price exceeds the maximum allowed.",
        212: "amount is lower than the minimum allowed for the market.",
        213: "price is too low.",
        214: "price has too many significant digits.",
        215: "price has more than 15 decimal places.",
        216: "Insufficient balance to perform this operation.",
        217: "amountQuote is lower than the minimum allowed for the market.",
        218: "triggerAmount has too many significant digits.",
        219: "The market is no longer listed on Bitvavo.",
        220: "clientOrderId conflict within the market.",
        231: "timeInForce must be set to GTC when markets are paused.",
        232: "Changes required for a successful update to your order.",
        234: "Cannot update a market order type.",
        235: "Maximum of 100 open orders per market exceeded.",
        236: "Only one of amount, amountRemaining, or amountQuote is allowed.",
        237: "Required parameters missing for stopLoss order type.",
        238: "Required parameters missing for stopLossLimit order type.",
        239: "Cannot switch between amount and amountQuote during an update.",
        401: "Deposits for this asset are not available.",
        402: "Verify your identity to deposit or withdraw assets.",
        403: "Verify your phone number to deposit or withdraw assets.",
        404: "Could not complete the operation due to an internal error.",
        405: "Withdrawal not allowed during the cooldown period.",
        406: "amount is below the minimum allowed value.",
        407: "Internal transfer is not possible.",
        408: "Insufficient balance to perform this operation.",
        409: "Verify your bank account and try again.",
        410: "Withdrawals for this asset are not available.",
        411: "You cannot transfer assets to yourself.",
        412: "Error during deposit or withdrawal.",
        413: "IP address not in your whitelist.",
        414: "Cannot withdraw assets within 2 minutes of logging in.",
        422: "Invalid price tick size.",
        423: "Market halted due to maintenance or other reasons.",
        424: "Market is in cancelOnly status.",
        425: "Market is in an auction phase.",
        426: "Market is in auctionMatching status.",
        429: "Too many decimal places in a parameter value.",
    },
    403: {
        300: "Authentication required to call this endpoint.",
        301: "Invalid API key length.",
        302: "Timestamp for authentication must be in milliseconds.",
        303: "Access window must be between 100 and 60000 milliseconds.",
        304: "Request not received within the access window.",
        305: "API key is not active.",
        306: "API key activation not confirmed.",
        307: "IP not whitelisted for this API key.",
        308: "Invalid signature format.",
        309: "Invalid signature.",
        310: "API key lacks trading endpoint permissions.",
        311: "API key lacks account endpoint permissions.",
        312: "API key lacks withdrawal permissions.",
        313: "Invalid Bitvavo session.",
        316: "Public asset information only via this WebSocket.",
        317: "Account locked. Contact support.",
        318: "Account verification required for API use.",
        319: "Feature unavailable in your region.",
        320: "Operation forbidden. Please contact support.",
    },
    404: {
        240: "Order not found or no longer active.",
        415: "Unknown WebSocket action. Verify against the API reference.",
    },
    409: {
        431: "Cannot get market data; market is halted/auction/auctionMatching.",
    },
    429: {
        105: "Rate limit exceeded. Account or IP address blocked temporarily.",
        112: "Rate limit exceeded for WebSocket requests per second.",
    },
    500: {
        101: "Unknown server error. Operation success uncertain.",
        400: "Unknown server error. Contact support.",
    },
    503: {
        107: "Bitvavo is overloaded. Retry after 500ms.",
        108: "Processing issue. Increase execution window or retry after 500ms.",
        109: "Timeout. Operation success uncertain.",
        111: "Matching engine temporarily unavailable.",
        419: "The server is unavailable.",
        430: "Connection timed out due to no new market data events.",
    },
}


# HTTP status helpers
HTTP_STATUS_OK_MIN = 200
HTTP_STATUS_OK_MAX = 299


# ---------------------------------------------------------------------------
# Core decoding → Result
# ---------------------------------------------------------------------------


def _json_from_response(resp: httpx.Response) -> dict[str, Any]:
    try:
        data = resp.json()  # type: ignore[no-any-return]
        assert isinstance(data, dict), "Expected JSON response to be a dictionary"
    except ValueError:
        return {"raw": resp.text}
    else:
        return data


def _map_error(resp: httpx.Response) -> BitvavoError:
    payload = _json_from_response(resp)
    code = int(payload.get("errorCode", -1))
    message = str(payload.get("error", payload.get("message", "")) or "")
    reason_dir = _BITVAVO_ERROR_REASONS.get(resp.status_code, {})
    reason = reason_dir.get(code, message or "Unknown error")
    return BitvavoError(
        http_status=resp.status_code,
        error_code=code,
        reason=reason,
        message=message or reason,
        raw=payload if isinstance(payload, dict) else {"raw": payload},
    )


def _validation_failure(reason: str, payload: dict[str, Any]) -> BitvavoError:
    return BitvavoError(
        http_status=500,
        error_code=-1,
        reason="Model validation failed",
        message=reason,
        raw=payload,
    )


def _enhance_dataframe_error(exc: Exception, data: Any, schema: Mapping[str, object] | None, model: type) -> str:
    """Create enhanced error message for DataFrame schema mismatches."""
    error_msg = str(exc)

    if "column-schema names do not match the data dictionary" not in error_msg:
        return error_msg

    # Extract actual field names from the data
    if isinstance(data, dict):
        actual_fields = list(data.keys())
    elif isinstance(data, list) and data and isinstance(data[0], dict):
        actual_fields = list(data[0].keys())
    else:
        actual_fields = []

    # Extract expected field names from schema
    expected_fields = list(schema.keys()) if schema else []

    model_name = getattr(model, "__name__", "DataFrame")
    return (
        f"DataFrame schema mismatch for {model_name}:\n"
        f"  Expected fields: {expected_fields}\n"
        f"  Actual fields:   {actual_fields}\n"
        f"  Missing fields:  {set(expected_fields) - set(actual_fields)}\n"
        f"  Extra fields:    {set(actual_fields) - set(expected_fields)}\n"
        f"  Original error:  {error_msg}"
    )


def decode_response_result(  # noqa: C901 (complexity)
    resp: httpx.Response,
    model: type[T] | None,
    schema: Mapping[str, object] | None = None,
) -> Result[T | Any, BitvavoError]:
    if not (HTTP_STATUS_OK_MIN <= resp.status_code <= HTTP_STATUS_OK_MAX):
        return Failure(_map_error(resp))

    try:
        data = resp.json()  # type: ignore[no-any-return]
    except ValueError:
        data: Any = {"raw": resp.text}

    if model is Any:
        # data is invalid (an error of sorts)
        if isinstance(data, dict) and any(key in data for key in ["errorCode", "error", "message"]):
            return Failure(_map_error(resp))

        # return the raw (valid) JSON
        return Success(data)

    assert model is not None, "Model must be provided or set to Any"
    assert isinstance(data, (dict, list)), "Expected JSON response to be a dictionary or list"

    try:
        # Support pydantic model classes/instances and common DataFrame libraries
        # (pandas / polars). Also fall back to calling a constructor if provided.
        if (isinstance(model, type) and issubclass(model, BaseModel)) or isinstance(model, BaseModel):
            parsed = model.model_validate(data)
        elif schema is None:
            parsed = model(data)  # type: ignore[arg-type]
        else:
            # I don't like the complexity of this piece, but it's needed because the data from ticker_book may return an
            # int when it should be a float... Why is their DB such a damned mess? Fuck me, man...
            try:
                # Check if model is a polars DataFrame specifically by checking module and class name
                if hasattr(model, "__name__") and "polars" in str(model.__module__) and "DataFrame" in str(model):
                    parsed = model(data, schema=schema, strict=False)  # type: ignore[arg-type]
                else:
                    parsed = model(data, schema=schema)  # type: ignore[arg-type]
            except (ImportError, AttributeError):
                parsed = model(data, schema=schema)  # type: ignore[arg-type]
        return Success(parsed)
    except Exception as exc:  # noqa: BLE001
        # If the payload looks like a Bitvavo error, map it so callers get a structured error.
        if isinstance(data, dict) and any(key in data for key in ["errorCode", "error", "message"]):
            return Failure(_map_error(resp))

        # Enhanced error message for DataFrame schema mismatches
        enhanced_error = _enhance_dataframe_error(exc, data, schema, model)

        logger.warning(
            "model_validation-failed",
            error=enhanced_error,
            exception_type=type(exc).__name__,
            payload=data,
        )
        return Failure(_validation_failure(enhanced_error, data if isinstance(data, dict) else {"raw": data}))


# ---------------------------------------------------------------------------
# Sync request wrappers returning Result
# ---------------------------------------------------------------------------


def get_json_result(
    client: httpx.Client,
    path: str,
    *,
    model: type[T],
) -> Result[T | dict[str, Any], BitvavoError]:
    url = f"{settings.base_url.rstrip('/')}/{path.lstrip('/')}"
    try:
        resp = client.get(url, timeout=settings.timeout_seconds)
    except httpx.HTTPError as exc:
        logger.error("HTTP request failed: %s", exc)
        return Failure(
            BitvavoError(
                http_status=0,
                error_code=-1,
                reason="Transport error",
                message=str(exc),
                raw={},
            ),
        )
    return decode_response_result(resp, model=model)


def post_json_result(
    client: httpx.Client,
    path: str,
    payload: dict[str, Any] | None = None,
    *,
    model: type[T] | None = None,
) -> Result[T | dict[str, Any], BitvavoError]:
    url = f"{settings.base_url.rstrip('/')}/{path.lstrip('/')}"
    try:
        resp = client.post(url, json=payload or {}, timeout=settings.timeout_seconds)
    except httpx.HTTPError as exc:
        logger.error("HTTP request failed: %s", exc)
        return Failure(
            BitvavoError(
                http_status=0,
                error_code=-1,
                reason="Transport error",
                message=str(exc),
                raw={"payload": payload or {}},
            ),
        )
    return decode_response_result(resp, model=model)
