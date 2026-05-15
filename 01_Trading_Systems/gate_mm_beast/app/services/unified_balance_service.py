from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from datetime import datetime, timezone
from urllib.parse import urlencode

import aiohttp

from app.config import Settings
from app.connectors.gateio.signing import build_headers as gate_build_headers


class UnifiedBalanceService:
    def __init__(self, cfg: Settings) -> None:
        self.cfg = cfg
        self.session: aiohttp.ClientSession | None = None
        self.snapshot: dict = {
            "ts": "",
            "total_usd": 0.0,
            "exchanges": {},
        }

    async def ensure(self) -> None:
        if self.session is None or self.session.closed:
            timeout = aiohttp.ClientTimeout(total=self.cfg.request_timeout)
            self.session = aiohttp.ClientSession(timeout=timeout)

    async def close(self) -> None:
        if self.session and not self.session.closed:
            await self.session.close()

    async def refresh(self) -> dict:
        await self.ensure()
        assert self.session

        results = {
            "gate": await self._fetch_gate(),
            "binance": await self._fetch_binance(),
            "okx": await self._fetch_okx(),
            "bybit": await self._fetch_bybit(),
            "xt": await self._fetch_xt(),
        }
        total_usd = round(sum(float(v.get("total_usd", 0.0)) for v in results.values()), 8)
        self.snapshot = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "total_usd": total_usd,
            "exchanges": results,
        }
        return self.snapshot

    def get_snapshot(self) -> dict:
        return self.snapshot

    @staticmethod
    def _usd_sum(assets: list[dict]) -> float:
        usd_like = {"USD", "USDT", "USDC", "BUSD", "FDUSD", "TUSD"}
        total = 0.0
        for asset in assets:
            ccy = str(asset.get("asset", "")).upper()
            amt = float(asset.get("free", 0.0)) + float(asset.get("locked", 0.0))
            if ccy in usd_like:
                total += amt
        return round(total, 8)

    @staticmethod
    def _ok(exchange: str, assets: list[dict], note: str = "") -> dict:
        return {
            "exchange": exchange,
            "status": "ok",
            "note": note,
            "total_usd": UnifiedBalanceService._usd_sum(assets),
            "assets": assets,
        }

    @staticmethod
    def _error(exchange: str, message: str) -> dict:
        return {
            "exchange": exchange,
            "status": "error",
            "error": message,
            "total_usd": 0.0,
            "assets": [],
        }

    async def _fetch_gate(self) -> dict:
        if not (self.cfg.gate_api_key and self.cfg.gate_api_secret):
            return self._error("gate", "missing_credentials")
        try:
            path = f"/futures/{self.cfg.gate_settle}/accounts"
            headers = gate_build_headers(self.cfg.gate_api_key, self.cfg.gate_api_secret, "GET", path)
            url = f"{self.cfg.gate_base_url}{path}"
            async with self.session.get(url, headers=headers) as r:
                text = await r.text()
                if r.status >= 400:
                    return self._error("gate", f"http_{r.status}:{text[:200]}")
                data = json.loads(text) if text.strip() else {}
                total = float(data.get("available", 0.0)) + float(data.get("total", 0.0))
                assets = [{"asset": "USDT", "free": total, "locked": 0.0}]
                return {
                    "exchange": "gate",
                    "status": "ok",
                    "total_usd": round(total, 8),
                    "assets": assets,
                }
        except Exception as exc:
            return self._error("gate", str(exc))

    async def _fetch_binance(self) -> dict:
        if not (self.cfg.binance_api_key and self.cfg.binance_api_secret):
            return self._error("binance", "missing_credentials")
        try:
            ts = int(time.time() * 1000)
            qs = urlencode({"timestamp": ts})
            sig = hmac.new(self.cfg.binance_api_secret.encode(), qs.encode(), hashlib.sha256).hexdigest()
            url = f"https://api.binance.com/api/v3/account?{qs}&signature={sig}"
            headers = {"X-MBX-APIKEY": self.cfg.binance_api_key}
            async with self.session.get(url, headers=headers) as r:
                text = await r.text()
                if r.status >= 400:
                    return self._error("binance", f"http_{r.status}:{text[:200]}")
                data = json.loads(text) if text.strip() else {}
                assets = []
                for b in data.get("balances", []):
                    free = float(b.get("free", 0.0))
                    locked = float(b.get("locked", 0.0))
                    if free or locked:
                        assets.append({"asset": b.get("asset"), "free": free, "locked": locked})
                return self._ok("binance", assets)
        except Exception as exc:
            return self._error("binance", str(exc))

    async def _fetch_okx(self) -> dict:
        if not (self.cfg.okx_api_key and self.cfg.okx_api_secret and self.cfg.okx_passphrase):
            return self._error("okx", "missing_credentials")
        try:
            path = "/api/v5/account/balance"
            ts = datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")
            prehash = f"{ts}GET{path}"
            sign = base64.b64encode(hmac.new(self.cfg.okx_api_secret.encode(), prehash.encode(), hashlib.sha256).digest()).decode()
            headers = {
                "OK-ACCESS-KEY": self.cfg.okx_api_key,
                "OK-ACCESS-SIGN": sign,
                "OK-ACCESS-TIMESTAMP": ts,
                "OK-ACCESS-PASSPHRASE": self.cfg.okx_passphrase,
            }
            async with self.session.get(f"https://www.okx.com{path}", headers=headers) as r:
                text = await r.text()
                if r.status >= 400:
                    return self._error("okx", f"http_{r.status}:{text[:200]}")
                data = json.loads(text) if text.strip() else {}
                assets = []
                for row in data.get("data", []):
                    for d in row.get("details", []):
                        free = float(d.get("availBal", 0.0))
                        locked = max(float(d.get("cashBal", 0.0)) - free, 0.0)
                        if free or locked:
                            assets.append({"asset": d.get("ccy"), "free": free, "locked": locked})
                return self._ok("okx", assets)
        except Exception as exc:
            return self._error("okx", str(exc))

    async def _fetch_bybit(self) -> dict:
        if not (self.cfg.bybit_api_key and self.cfg.bybit_api_secret):
            return self._error("bybit", "missing_credentials")
        try:
            path = "/v5/account/wallet-balance"
            recv_window = "5000"
            ts = str(int(time.time() * 1000))
            qs = urlencode({"accountType": "UNIFIED"})
            payload = f"{ts}{self.cfg.bybit_api_key}{recv_window}{qs}"
            sign = hmac.new(self.cfg.bybit_api_secret.encode(), payload.encode(), hashlib.sha256).hexdigest()
            headers = {
                "X-BAPI-API-KEY": self.cfg.bybit_api_key,
                "X-BAPI-SIGN": sign,
                "X-BAPI-SIGN-TYPE": "2",
                "X-BAPI-TIMESTAMP": ts,
                "X-BAPI-RECV-WINDOW": recv_window,
            }
            async with self.session.get(f"https://api.bybit.com{path}?{qs}", headers=headers) as r:
                text = await r.text()
                if r.status >= 400:
                    return self._error("bybit", f"http_{r.status}:{text[:200]}")
                data = json.loads(text) if text.strip() else {}
                assets = []
                for acct in data.get("result", {}).get("list", []):
                    for coin in acct.get("coin", []):
                        free = float(coin.get("walletBalance", 0.0))
                        locked = float(coin.get("locked", 0.0))
                        if free or locked:
                            assets.append({"asset": coin.get("coin"), "free": free, "locked": locked})
                return self._ok("bybit", assets)
        except Exception as exc:
            return self._error("bybit", str(exc))

    async def _fetch_xt(self) -> dict:
        if not (self.cfg.xt_api_key and self.cfg.xt_api_secret):
            return self._error("xt", "missing_credentials")
        try:
            path = "/v4/private/wallet/balances"
            ts = str(int(time.time() * 1000))
            sign_raw = f"{ts}GET{path}"
            sign = hmac.new(self.cfg.xt_api_secret.encode(), sign_raw.encode(), hashlib.sha256).hexdigest()
            headers = {
                "validate-algorithms": "HmacSHA256",
                "validate-appkey": self.cfg.xt_api_key,
                "validate-recvwindow": "5000",
                "validate-timestamp": ts,
                "validate-signature": sign,
            }
            async with self.session.get(f"https://sapi.xt.com{path}", headers=headers) as r:
                text = await r.text()
                if r.status >= 400:
                    return self._error("xt", f"http_{r.status}:{text[:200]}")
                data = json.loads(text) if text.strip() else {}
                rows = data.get("result", []) if isinstance(data, dict) else []
                assets = []
                for item in rows:
                    free = float(item.get("availableAmount", 0.0))
                    locked = float(item.get("frozenAmount", 0.0))
                    if free or locked:
                        assets.append({"asset": item.get("currency"), "free": free, "locked": locked})
                return self._ok("xt", assets, "xt endpoint/signature can vary by account type")
        except Exception as exc:
            return self._error("xt", str(exc))
