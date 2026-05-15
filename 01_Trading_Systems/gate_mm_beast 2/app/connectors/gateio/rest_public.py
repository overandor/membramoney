from __future__ import annotations
import json
import aiohttp
import pandas as pd
from app.config import Settings

class GatePublicRest:
    def __init__(self, cfg: Settings) -> None:
        self.cfg = cfg
        self.session: aiohttp.ClientSession | None = None

    async def ensure(self) -> None:
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=self.cfg.request_timeout))

    async def get_json(self, path: str, params: dict | None = None):
        await self.ensure()
        assert self.session
        async with self.session.get(f"{self.cfg.gate_base_url}{path}", params=params or {}) as r:
            text = await r.text()
            if r.status >= 400:
                raise RuntimeError(f"GET {path} {r.status}: {text[:300]}")
            return json.loads(text) if text.strip() else {}

    async def candles(self, symbol: str, interval: str, limit: int) -> pd.DataFrame:
        data = await self.get_json(f"/futures/{self.cfg.gate_settle}/candlesticks", {"contract": symbol, "interval": interval, "limit": min(limit, 2000)})
        rows = []
        for item in data or []:
            if isinstance(item, dict):
                rows.append({"t": item.get("t"), "o": item.get("o"), "h": item.get("h"), "l": item.get("l"), "c": item.get("c"), "v": item.get("v")})
        df = pd.DataFrame(rows)
        if df.empty:
            return df
        for c in ["o","h","l","c","v"]:
            df[c] = pd.to_numeric(df[c], errors="coerce")
        df["timestamp"] = pd.to_datetime(df["t"], unit="s", utc=True)
        return df.rename(columns={"o":"open","h":"high","l":"low","c":"close","v":"volume"})[["timestamp","open","high","low","close","volume"]].dropna().reset_index(drop=True)

    async def list_tickers(self):
        return await self.get_json(f"/futures/{self.cfg.gate_settle}/tickers")

    async def list_contracts(self):
        return await self.get_json(f"/futures/{self.cfg.gate_settle}/contracts")

    async def order_book(self, symbol: str, limit: int = 5):
        return await self.get_json(f"/futures/{self.cfg.gate_settle}/order_book", {"contract": symbol, "limit": limit})

    async def close(self):
        if self.session and not self.session.closed:
            await self.session.close()
