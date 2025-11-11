"""Async Phemex client facade used by the autotrader.

The real integration is intentionally lightweight so that higher level modules
can be tested in isolation. For local development and automated tests we ship a
fully in-memory paper client that honours idempotency semantics, order state
transitions and simple exposure tracking.
"""

from __future__ import annotations

import asyncio
import json
import os
import time
import uuid
from dataclasses import dataclass
from typing import Dict, List, Optional

try:  # Optional dependency. Only required for live trading.
    import httpx
except Exception:  # pragma: no cover - optional dependency.
    httpx = None


@dataclass
class _OrderRecord:
    order: Dict[str, object]
    idempotency_key: str
    order_id: str
    status: str
    filled_qty: float
    avg_price: Optional[float]
    created_ts: float


class _BaseClient:
    async def place(self, order: Dict[str, object], idempotency_key: str) -> Dict[str, object]:
        raise NotImplementedError

    async def amend(self, order_id: str, params: Dict[str, object]) -> Dict[str, object]:
        raise NotImplementedError

    async def cancel(self, order_id: str) -> Dict[str, object]:
        raise NotImplementedError

    async def fetch_order(self, order_id: str) -> Dict[str, object]:
        raise NotImplementedError

    async def fetch_positions(self, symbol: str | None = None) -> List[Dict[str, object]]:
        raise NotImplementedError


class PaperPhemexClient(_BaseClient):
    """A deterministic in-memory exchange simulator."""

    def __init__(self) -> None:
        self._orders: Dict[str, _OrderRecord] = {}
        self._id_map: Dict[str, str] = {}
        self._lock = asyncio.Lock()

    async def place(self, order: Dict[str, object], idempotency_key: str) -> Dict[str, object]:
        async with self._lock:
            if idempotency_key in self._id_map:
                return self._serialise(self._orders[self._id_map[idempotency_key]])

            order_id = str(uuid.uuid4())
            record = _OrderRecord(
                order=dict(order),
                idempotency_key=idempotency_key,
                order_id=order_id,
                status="working" if order.get("type") in {"LIMIT", "STOP"} else "filled",
                filled_qty=0.0,
                avg_price=None,
                created_ts=time.time(),
            )
            self._orders[order_id] = record
            self._id_map[idempotency_key] = order_id
            return self._serialise(record)

    async def amend(self, order_id: str, params: Dict[str, object]) -> Dict[str, object]:
        async with self._lock:
            record = self._orders.get(order_id)
            if not record:
                raise ValueError(f"Unknown order_id: {order_id}")
            record.order.update(params)
            record.status = "amended"
            return self._serialise(record)

    async def cancel(self, order_id: str) -> Dict[str, object]:
        async with self._lock:
            record = self._orders.get(order_id)
            if not record:
                raise ValueError(f"Unknown order_id: {order_id}")
            record.status = "canceled"
            return self._serialise(record)

    async def fetch_order(self, order_id: str) -> Dict[str, object]:
        async with self._lock:
            record = self._orders.get(order_id)
            if not record:
                raise ValueError(f"Unknown order_id: {order_id}")
            return self._serialise(record)

    async def fetch_positions(self, symbol: str | None = None) -> List[Dict[str, object]]:
        async with self._lock:
            positions: Dict[str, Dict[str, object]] = {}
            for record in self._orders.values():
                ord_symbol = str(record.order.get("symbol"))
                if symbol and ord_symbol != symbol:
                    continue
                entry = positions.setdefault(
                    ord_symbol,
                    {"symbol": ord_symbol, "netQty": 0.0, "notional": 0.0},
                )
                qty = float(record.order.get("quantity", 0.0))
                price = float(record.order.get("price") or record.order.get("stopPx") or 0.0)
                if record.order.get("side", "").upper() == "SELL":
                    qty *= -1
                entry["netQty"] += qty
                entry["notional"] += qty * price
            return list(positions.values())

    def _serialise(self, record: _OrderRecord) -> Dict[str, object]:
        payload = dict(record.order)
        payload.update(
            {
                "orderID": record.order_id,
                "idempotencyKey": record.idempotency_key,
                "status": record.status,
                "filledQty": record.filled_qty,
                "avgPx": record.avg_price,
                "timestamp": record.created_ts,
            }
        )
        return payload


class HttpPhemexClient(_BaseClient):
    """Minimal REST implementation of the Phemex private API."""

    def __init__(self, base_url: str, api_key: str, api_secret: str) -> None:
        if not httpx:  # pragma: no cover - optional path
            raise RuntimeError("httpx is required for live trading but is not installed")
        self._client = httpx.AsyncClient(base_url=base_url.rstrip("/"))
        self._api_key = api_key
        self._api_secret = api_secret

    async def _request(self, method: str, path: str, payload: Optional[Dict[str, object]] = None) -> Dict[str, object]:
        payload = payload or {}
        expires = int(time.time() * 1000) + 60_000
        if method == "GET":
            body = ""
        else:
            body = json.dumps(payload, separators=(",", ":"), sort_keys=True)
        signature_payload = f"{path}{expires}{body}".encode()
        import hmac
        import hashlib

        signature = hmac.new(self._api_secret.encode(), signature_payload, hashlib.sha256).hexdigest()
        headers = {
            "x-phemex-request-signature": signature,
            "x-phemex-request-expiry": str(expires),
            "x-phemex-access-token": self._api_key,
        }
        response = await self._client.request(
            method,
            path,
            json=payload if method != "GET" else None,
            params=payload if method == "GET" else None,
            headers=headers,
        )
        response.raise_for_status()
        data = response.json()
        return data.get("data", data)

    async def place(self, order: Dict[str, object], idempotency_key: str) -> Dict[str, object]:
        payload = dict(order)
        payload["clOrdID"] = idempotency_key
        return await self._request("POST", "/orders", payload)

    async def amend(self, order_id: str, params: Dict[str, object]) -> Dict[str, object]:
        payload = {"orderID": order_id, **params}
        return await self._request("PUT", "/orders/replace", payload)

    async def cancel(self, order_id: str) -> Dict[str, object]:
        payload = {"orderID": order_id}
        return await self._request("DELETE", "/orders/cancel", payload)

    async def fetch_order(self, order_id: str) -> Dict[str, object]:
        return await self._request("GET", "/orders/query", {"orderID": order_id})

    async def fetch_positions(self, symbol: str | None = None) -> List[Dict[str, object]]:
        payload = {"symbol": symbol} if symbol else None
        data = await self._request("GET", "/positions", payload or {})
        return data if isinstance(data, list) else [data]


_active_client: _BaseClient | None = None


def configure_client(client: _BaseClient) -> None:
    """Override the active client.

    Primarily used in tests where we want deterministic behaviour.
    """

    global _active_client
    _active_client = client


def _default_client() -> _BaseClient:
    global _active_client
    if _active_client:
        return _active_client

    mode = os.getenv("AUTOTRADE_MODE", "paper").lower()
    if mode == "paper":
        _active_client = PaperPhemexClient()
        return _active_client

    api_key = os.getenv("PHEMEX_API_KEY")
    api_secret = os.getenv("PHEMEX_API_SECRET")
    base_url = os.getenv("PHEMEX_API_URL", "https://api.phemex.com")
    if not all([api_key, api_secret]):
        raise RuntimeError("Live trading requested but Phemex credentials are missing")
    _active_client = HttpPhemexClient(base_url, api_key, api_secret)
    return _active_client


async def place(order: Dict[str, object], idempotency_key: str) -> Dict[str, object]:
    return await _default_client().place(order, idempotency_key)


async def amend(order_id: str, params: Dict[str, object]) -> Dict[str, object]:
    return await _default_client().amend(order_id, params)


async def cancel(order_id: str) -> Dict[str, object]:
    return await _default_client().cancel(order_id)


async def fetch_order(order_id: str) -> Dict[str, object]:
    return await _default_client().fetch_order(order_id)


async def fetch_positions(symbol: str | None = None) -> List[Dict[str, object]]:
    return await _default_client().fetch_positions(symbol)


__all__ = [
    "PaperPhemexClient",
    "HttpPhemexClient",
    "configure_client",
    "place",
    "amend",
    "cancel",
    "fetch_order",
    "fetch_positions",
]
