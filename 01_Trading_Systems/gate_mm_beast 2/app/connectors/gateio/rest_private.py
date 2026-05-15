from __future__ import annotations
import json
from urllib.parse import urlencode
import aiohttp
from app.config import Settings
from app.connectors.gateio.signing import build_headers

class GatePrivateRest:
    def __init__(self, cfg: Settings) -> None:
        self.cfg = cfg
        self.session: aiohttp.ClientSession | None = None

    async def ensure(self) -> None:
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=self.cfg.request_timeout))

    async def request(self, method: str, path: str, params: dict | None = None, payload: dict | None = None):
        await self.ensure()
        assert self.session
        params = params or {}
        payload = payload or {}
        query_string = urlencode(params)
        body = json.dumps(payload, separators=(",", ":")) if payload else ""
        headers = build_headers(self.cfg.gate_api_key, self.cfg.gate_api_secret, method, path, query_string, body)
        async with self.session.request(method.upper(), f"{self.cfg.gate_base_url}{path}", params=params, data=body if body else None, headers=headers) as r:
            text = await r.text()
            if r.status >= 400:
                raise RuntimeError(f"{method} {path} {r.status}: {text[:400]}")
            return json.loads(text) if text.strip() else {}

    async def create_order(self, symbol: str, size: int, price: float, text: str, reduce_only: bool = False, tif: str = "poc"):
        return await self.request("POST", f"/futures/{self.cfg.gate_settle}/orders", payload={
            "contract": symbol,
            "size": size,
            "price": f"{price:.10f}",
            "tif": tif,
            "text": text[:28],
            "reduce_only": reduce_only,
        })

    async def cancel_order(self, order_id: str):
        return await self.request("DELETE", f"/futures/{self.cfg.gate_settle}/orders/{order_id}")

    async def get_order(self, order_id: str):
        return await self.request("GET", f"/futures/{self.cfg.gate_settle}/orders/{order_id}")

    async def list_open_orders(self, symbol: str | None = None):
        params = {"status":"open"}
        if symbol:
            params["contract"] = symbol
        return await self.request("GET", f"/futures/{self.cfg.gate_settle}/orders", params=params)

    async def list_positions(self):
        return await self.request("GET", f"/futures/{self.cfg.gate_settle}/positions")

    async def update_leverage(self, symbol: str, leverage: int):
        return await self.request("POST", f"/futures/{self.cfg.gate_settle}/positions/{symbol}/leverage", payload={"leverage": str(leverage)})

    async def close(self):
        if self.session and not self.session.closed:
            await self.session.close()
