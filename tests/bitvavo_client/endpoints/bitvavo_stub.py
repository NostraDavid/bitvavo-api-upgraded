# License notice from LICENSE.txt:
# Copyright (c) 2024, Bitvavo B.V.

"""An in-process Bitvavo provider validated against an independent OpenAPI snapshot."""

from __future__ import annotations

import hashlib
import hmac
import json
from copy import deepcopy
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import TYPE_CHECKING, Any
from uuid import UUID

import connexion
from connexion.exceptions import BadRequestProblem
from connexion.lifecycle import ConnexionResponse
from connexion.middleware import MiddlewarePosition
from connexion.options import SwaggerUIOptions
from connexion.resolver import Resolver
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

if TYPE_CHECKING:
    from starlette.middleware.base import RequestResponseEndpoint
    from starlette.requests import Request
    from starlette.responses import Response

CONTRACT_ROOT = Path(__file__).resolve().parents[2] / "contracts" / "bitvavo"
API_KEY = "a" * 64
API_SECRET = "offline-test-secret"
BASE_URL = "http://bitvavo.invalid/v2"
NOW_MS = 1794700000000
OPERATOR_ID = 123
ORDER_ID = "00000000-0000-4000-8000-000000000001"
CLIENT_ORDER_ID = "00000000-0000-4000-8000-000000000002"


def load_manifest() -> dict[str, Any]:
    return json.loads((CONTRACT_ROOT / "manifest.json").read_text())


def load_specification() -> dict[str, Any]:
    manifest = load_manifest()
    specification = json.loads((CONTRACT_ROOT / manifest["schema"]).read_text())
    # Reviewed upstream schema errata are documented next to the snapshot.
    for path, method in (("/order", "post"), ("/order", "put"), ("/deposit", "get"), ("/depositHistory", "get")):
        schema = specification["paths"][path][method]["responses"]["200"]["content"]["application/json"]["schema"]
        schema["anyOf"] = schema.pop("oneOf")
    for path in ("/ordersOpen", "/depositHistory", "/withdrawalHistory"):
        response = specification["paths"][path]["get"]["responses"]["200"]["content"]["application/json"]
        response["schema"] = {"type": "array", "items": response["schema"]}
    for parameter in specification["paths"]["/order"]["delete"]["parameters"]:
        if parameter["name"] == "orderId":
            parameter["required"] = False
    trades = specification["paths"]["/trades"]["get"]
    trades["parameters"] = [parameter for parameter in trades["parameters"] if parameter["name"] != "tradeId"]
    for path, methods in specification["paths"].items():
        for method, operation in methods.items():
            operation["operationId"] = f"{method}_{path}"
            # Authentication below verifies the raw request, independently of the SDK signer.
            operation["security"] = []
    return specification


def invalid_parameters(_request: object, exception: Exception) -> ConnexionResponse:
    return ConnexionResponse(
        status_code=400,
        content_type="application/json",
        body=json.dumps({"errorCode": 203, "error": str(exception)}),
    )


class AuthenticationMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: Any, exchange: FakeBitvavo) -> None:
        super().__init__(app)
        self.exchange = exchange

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        body = await request.body()
        path = request.url.path.removeprefix("/v2")
        self.exchange.requests.append(
            {
                "method": request.method,
                "path": path,
                "query": dict(request.query_params),
                "body": body,
            },
        )
        key = request.headers.get("bitvavo-access-key", "")
        for invalid, code, message in (
            (not key, 300, "Authentication is required."),
            (len(key) != 64, 301, "The API key length is not valid."),
            (key != API_KEY, 305, "The API key is not active."),
        ):
            if invalid:
                return JSONResponse({"errorCode": code, "error": message}, status_code=403)
        try:
            timestamp = int(request.headers["bitvavo-access-timestamp"])
            window = int(request.headers.get("bitvavo-access-window", "10000"))
        except (KeyError, ValueError):
            return JSONResponse({"errorCode": 302, "error": "The timestamp is not valid."}, status_code=403)
        if not 100 <= window <= 60000:
            return JSONResponse({"errorCode": 303, "error": "The access window is out of range."}, status_code=403)
        if abs(NOW_MS - timestamp) > window:
            return JSONResponse(
                {"errorCode": 304, "error": "The request is outside its access window."},
                status_code=403,
            )
        target = request.scope.get("raw_path", request.scope["path"].encode()).decode()
        if request.scope["query_string"]:
            target += "?" + request.scope["query_string"].decode()
        message = f"{timestamp}{request.method}{target}".encode() + body
        expected = hmac.new(API_SECRET.encode(), message, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(request.headers.get("bitvavo-access-signature", ""), expected):
            return JSONResponse({"errorCode": 309, "error": "The signature is not valid."}, status_code=403)
        response = await call_next(request)
        weight = self.exchange.weights.get(f"{request.method} {path}", 1)
        if isinstance(weight, dict):
            weight = weight["market" if request.query_params.get("market") else "all"]
        self.exchange.remaining -= weight
        response.headers["bitvavo-ratelimit-remaining"] = str(self.exchange.remaining)
        response.headers["bitvavo-ratelimit-resetat"] = str(NOW_MS + 60000)
        return response


class FakeBitvavo:
    # shortcut: no matching or settlement engine; extend only when tests need fills or ledger effects.
    def __init__(self) -> None:
        manifest = load_manifest()
        directory = CONTRACT_ROOT / manifest["contract_version"]
        self.responses: dict[str, Any] = json.loads((directory / "responses.json").read_text())
        self.orders = {ORDER_ID: deepcopy(self.responses["order"])}
        self.requests: list[dict[str, Any]] = []
        self.weights = manifest["rate_limit_weights"]
        self.remaining = 1000
        self.sequence = 10
        self.app = connexion.AsyncApp(__name__, swagger_ui_options=SwaggerUIOptions(swagger_ui=False))
        self.app.add_api(
            load_specification(),
            resolver=Resolver(lambda _operation: self.handle),
            validate_responses=True,
            strict_validation=True,
        )
        self.app.add_middleware(AuthenticationMiddleware, exchange=self, position=MiddlewarePosition.BEFORE_ROUTING)
        self.app.add_error_handler(BadRequestProblem, invalid_parameters)

    @staticmethod
    def not_found() -> tuple[dict[str, Any], int]:
        return {"errorCode": 240, "error": "Order not found."}, 404

    def find_order(self, parameters: dict[str, Any]) -> dict[str, Any] | None:
        for order in self.orders.values():
            if order["market"] != parameters.get("market"):
                continue
            if parameters.get("clientOrderId"):
                if order.get("clientOrderId") == parameters["clientOrderId"]:
                    return order
            elif order["orderId"] == parameters.get("orderId"):
                return order
        return None

    def change_order(self, method: str, body: dict[str, Any]) -> Any:
        if "price" in body:
            try:
                invalid_price = Decimal(body["price"]) % Decimal("0.01") != 0
            except InvalidOperation:
                invalid_price = True
            if invalid_price:
                return {"errorCode": 422, "error": "Price must be a multiple of tickSize."}, 400
        if method == "POST":
            order = deepcopy(self.responses["order"])
            self.sequence += 1
            order["orderId"] = str(UUID(int=self.sequence))
            order.pop("clientOrderId", None)
            order.update(body)
            order.pop("responseRequired", None)
            self.orders[order["orderId"]] = order
        else:
            order = self.find_order(body)
            if order is None or order["status"] == "canceled":
                return self.not_found()
            order.update({key: value for key, value in body.items() if key != "responseRequired"})
        order["updated"] += 1
        order["updatedNs"] = order["updated"] * 1000000
        if body.get("responseRequired") is False:
            return {key: order[key] for key in ("market", "orderId", "created", "updated", "createdNs", "updatedNs")}
        return deepcopy(order)

    def order_request(self, method: str, body: dict | None, parameters: dict) -> Any:
        identifiers = body if body is not None else parameters
        if method != "POST" and not any(identifiers.get(name) for name in ("orderId", "clientOrderId")):
            return {"errorCode": 203, "error": "Either orderId or clientOrderId is required."}, 400
        if method in {"POST", "PUT"}:
            return self.change_order(method, body or {})
        order = self.find_order(parameters)
        if order is None:
            return self.not_found()
        if method == "DELETE":
            if order["status"] == "canceled":
                return self.not_found()
            order["status"] = "canceled"
            return {"orderId": order["orderId"], "operatorId": parameters["operatorId"]}
        return deepcopy(order)

    def order_list(self, method: str, path: str, parameters: dict) -> Any:
        orders = [
            order
            for order in self.orders.values()
            if not parameters.get("market") or order["market"] == parameters["market"]
        ]
        if method == "DELETE":
            canceled = []
            for order in orders:
                if order["status"] != "canceled":
                    order["status"] = "canceled"
                    canceled.append({"orderId": order["orderId"], "operatorId": parameters["operatorId"]})
            return canceled
        if path == "/ordersOpen":
            orders = [order for order in orders if order["status"] != "canceled"]
        return deepcopy(orders)

    def withdraw(self, body: dict) -> dict:
        self.responses["GET /withdrawalHistory"].insert(
            0,
            {
                "timestamp": NOW_MS,
                "symbol": body["symbol"],
                "amount": body["amount"],
                "address": body["address"],
                "fee": "0",
                "status": "awaiting_processing",
            },
        )
        return {"success": True, "symbol": body["symbol"], "amount": body["amount"]}

    def transaction_history(self, parameters: dict) -> dict:
        response = deepcopy(self.responses["GET /account/history"])
        rows = response["items"]
        if parameters.get("type"):
            rows = [rows[0] | {"type": parameters["type"]}]
        page = parameters.get("page", 1)
        maximum = parameters.get("maxItems", 100)
        response.update(
            items=rows[(page - 1) * maximum : page * maximum],
            currentPage=page,
            totalPages=(len(rows) + maximum - 1) // maximum,
            maxItems=maximum,
        )
        return response

    async def handle(self, body: dict[str, Any] | None = None, **parameters: Any) -> Any:
        method = connexion.request.method
        path = connexion.request.url.path.removeprefix("/v2")
        if path == "/order":
            return self.order_request(method, body, parameters)
        if path in {"/orders", "/ordersOpen"}:
            return self.order_list(method, path, parameters)
        if method == "POST" and path == "/withdrawal":
            assert body is not None
            return self.withdraw(body)
        if path == "/account/history":
            return self.transaction_history(parameters)
        response = deepcopy(self.responses[f"{method} {path}"])
        if path in {"/balance", "/depositHistory", "/withdrawalHistory"} and parameters.get("symbol"):
            response = [row for row in response if row["symbol"] == parameters["symbol"]]
        return response
