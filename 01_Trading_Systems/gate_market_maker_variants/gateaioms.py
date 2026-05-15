#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

"""
gate_multi_ticker_mm_prod.py

Production-style multi-ticker Gate.io USDT perpetual maker engine for low-nominal contracts.

What this file does:
- scans Gate USDT perpetual contracts and filters low nominal symbols (default: mark price 0 to 0.10 USDT)
- maintains best bid/ask snapshots over WebSocket
- computes a lightweight alpha signal from microstructure + trend/mean-reversion features
- places maker-only entries and maker-only take-profit exits
- tracks local orders/positions in SQLite
- reconciles local state against exchange state
- includes an execution-aware backtester with fees, spread proxy, queue/fill probability, slippage, and cooldowns
- supports PAPER and LIVE modes

Important:
- This is a software foundation, not a guarantee of profit.
- A truly tick-perfect execution backtest requires historical L2/order-book and trade data. The included backtester is execution-aware, but still a model.
- Keep LIVE_TRADING=false until you verify endpoints, permissions, sizing, and contract specifics on your own account.

Install:
    pip install aiohttp websockets pandas numpy python-dotenv

Run examples:
    python gate_multi_ticker_mm_prod.py --mode backtest
    python gate_multi_ticker_mm_prod.py --mode paper
    python gate_multi_ticker_mm_prod.py --mode live
    python gate_multi_ticker_mm_prod.py --mode scan

Environment:
    GATE_API_KEY=...
    GATE_API_SECRET=...
    GATE_BASE_URL=https://fx-api.gateio.ws/api/v4
    GATE_WS_URL=wss://fx-ws.gateio.ws/v4/ws/usdt
    GATE_SETTLE=usdt
    LIVE_TRADING=false
    DB_PATH=gate_mm_prod.db
    APP_SYMBOLS=0                 # optional comma-separated symbols; 0 means auto-scan
    MIN_MARK_PRICE=0.0
    MAX_MARK_PRICE=0.10
    MIN_24H_QUOTE_VOL=100000
    MAX_SYMBOLS=12
    LOOP_SECONDS=2.0
    CONTRACT_RISK_USD=15
    LEVERAGE=2
    MAKER_FEE_BPS=0.0
    TAKER_FEE_BPS=5.0
    ENTRY_EDGE_BPS=5.0
    EXIT_EDGE_BPS=4.0
    STOP_ATR_MULT=1.6
    TAKE_ATR_MULT=1.0
    INVENTORY_LIMIT_PER_SYMBOL=1
    BAR_INTERVAL=1m
    BAR_LIMIT=400
    COOLDOWN_SECONDS=45
    REQUEST_TIMEOUT=15
    ENABLE_UI=false
    APP_HOST=127.0.0.1
    APP_PORT=8788
"""

import argparse
import asyncio
import contextlib
import dataclasses
import hashlib
import hmac
import json
import logging
import math
import os
import random
import signal
import sqlite3
import sys
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Deque, Dict, Iterable, List, Optional, Tuple
from urllib.parse import urlencode

import aiohttp
import numpy as np
import pandas as pd
import websockets
from dotenv import load_dotenv

load_dotenv()


# ============================================================
# Helpers
# ============================================================

def now_ts() -> float:
    return time.time()


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def safe_float(x: Any, default: float = 0.0) -> float:
    try:
        if x is None:
            return default
        if isinstance(x, float) and math.isnan(x):
            return default
        return float(x)
    except Exception:
        return default


def safe_int(x: Any, default: int = 0) -> int:
    try:
        return int(float(x))
    except Exception:
        return default


def clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


def sign(x: float) -> int:
    return 1 if x > 0 else (-1 if x < 0 else 0)


def json_s(x: Any) -> str:
    return json.dumps(x, ensure_ascii=False, separators=(",", ":"), default=str)


def chunks(seq: List[str], n: int) -> Iterable[List[str]]:
    for i in range(0, len(seq), n):
        yield seq[i:i+n]


# ============================================================
# Config
# ============================================================

@dataclass
class Config:
    gate_api_key: str = os.getenv("GATE_API_KEY", "")
    gate_api_secret: str = os.getenv("GATE_API_SECRET", "")
    gate_base_url: str = os.getenv("GATE_BASE_URL", "https://fx-api.gateio.ws/api/v4").rstrip("/")
    gate_ws_url: str = os.getenv("GATE_WS_URL", "wss://fx-ws.gateio.ws/v4/ws/usdt")
    settle: str = os.getenv("GATE_SETTLE", "usdt").lower()
    live_trading: bool = os.getenv("LIVE_TRADING", "false").lower() == "true"
    db_path: str = os.getenv("DB_PATH", "gate_mm_prod.db")

    min_mark_price: float = float(os.getenv("MIN_MARK_PRICE", "0.0"))
    max_mark_price: float = float(os.getenv("MAX_MARK_PRICE", "0.10"))
    min_24h_quote_vol: float = float(os.getenv("MIN_24H_QUOTE_VOL", "100000"))
    max_symbols: int = int(os.getenv("MAX_SYMBOLS", "12"))
    app_symbols_raw: str = os.getenv("APP_SYMBOLS", "0")

    loop_seconds: float = float(os.getenv("LOOP_SECONDS", "2.0"))
    contract_risk_usd: float = float(os.getenv("CONTRACT_RISK_USD", "15"))
    leverage: int = int(os.getenv("LEVERAGE", "2"))
    maker_fee_bps: float = float(os.getenv("MAKER_FEE_BPS", "0.0"))
    taker_fee_bps: float = float(os.getenv("TAKER_FEE_BPS", "5.0"))
    entry_edge_bps: float = float(os.getenv("ENTRY_EDGE_BPS", "5.0"))
    exit_edge_bps: float = float(os.getenv("EXIT_EDGE_BPS", "4.0"))
    stop_atr_mult: float = float(os.getenv("STOP_ATR_MULT", "1.6"))
    take_atr_mult: float = float(os.getenv("TAKE_ATR_MULT", "1.0"))
    inventory_limit_per_symbol: int = int(os.getenv("INVENTORY_LIMIT_PER_SYMBOL", "1"))
    bar_interval: str = os.getenv("BAR_INTERVAL", "1m")
    bar_limit: int = int(os.getenv("BAR_LIMIT", "400"))
    cooldown_seconds: int = int(os.getenv("COOLDOWN_SECONDS", "45"))
    request_timeout: int = int(os.getenv("REQUEST_TIMEOUT", "15"))

    enable_ui: bool = os.getenv("ENABLE_UI", "false").lower() == "true"
    app_host: str = os.getenv("APP_HOST", "127.0.0.1")
    app_port: int = int(os.getenv("APP_PORT", "8788"))

    log_level: str = os.getenv("LOG_LEVEL", "INFO")

    @property
    def app_symbols(self) -> List[str]:
        raw = self.app_symbols_raw.strip()
        if not raw or raw == "0":
            return []
        return [x.strip().upper() for x in raw.split(",") if x.strip()]


CFG = Config()
logging.basicConfig(
    level=getattr(logging, CFG.log_level.upper(), logging.INFO),
    format="%(asctime)s | %(levelname)s | %(message)s",
)
log = logging.getLogger("gate-mm-prod")


# ============================================================
# SQLite
# ============================================================

class DB:
    def __init__(self, path: str):
        self.path = path
        self._init()

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init(self) -> None:
        with self._conn() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS symbols (
                    symbol TEXT PRIMARY KEY,
                    mark_price REAL,
                    last_price REAL,
                    quote_volume REAL,
                    quanto_multiplier REAL,
                    order_price_round REAL,
                    order_size_min INTEGER,
                    order_size_max INTEGER,
                    updated_ts TEXT
                )
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ts TEXT,
                    level TEXT,
                    kind TEXT,
                    symbol TEXT,
                    payload_json TEXT
                )
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS decisions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ts TEXT,
                    symbol TEXT,
                    side TEXT,
                    score REAL,
                    confidence REAL,
                    alpha_json TEXT,
                    market_json TEXT,
                    backtest_json TEXT,
                    live_ok INTEGER,
                    notes TEXT
                )
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS orders (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ts TEXT,
                    symbol TEXT,
                    role TEXT,
                    side TEXT,
                    state TEXT,
                    text_tag TEXT,
                    reduce_only INTEGER,
                    requested_price REAL,
                    requested_size INTEGER,
                    exchange_order_id TEXT,
                    exchange_status TEXT,
                    fill_price REAL,
                    left_size INTEGER,
                    raw_request_json TEXT,
                    raw_response_json TEXT,
                    notes TEXT
                )
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS positions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ts_open TEXT,
                    ts_close TEXT,
                    symbol TEXT,
                    side TEXT,
                    status TEXT,
                    size INTEGER,
                    entry_price REAL,
                    exit_price REAL,
                    take_price REAL,
                    stop_price REAL,
                    realized_pnl_usd REAL,
                    reason_open TEXT,
                    reason_close TEXT,
                    meta_json TEXT
                )
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS kv_state (
                    k TEXT PRIMARY KEY,
                    v TEXT NOT NULL
                )
                """
            )
            conn.commit()

    def event(self, level: str, kind: str, symbol: str, payload: Dict[str, Any]) -> None:
        with self._conn() as conn:
            conn.execute(
                "INSERT INTO events (ts, level, kind, symbol, payload_json) VALUES (?, ?, ?, ?, ?)",
                (utc_now_iso(), level, kind, symbol, json_s(payload)),
            )
            conn.commit()

    def upsert_symbol(self, row: Dict[str, Any]) -> None:
        with self._conn() as conn:
            conn.execute(
                """
                INSERT INTO symbols(symbol, mark_price, last_price, quote_volume, quanto_multiplier,
                                    order_price_round, order_size_min, order_size_max, updated_ts)
                VALUES (:symbol, :mark_price, :last_price, :quote_volume, :quanto_multiplier,
                        :order_price_round, :order_size_min, :order_size_max, :updated_ts)
                ON CONFLICT(symbol) DO UPDATE SET
                    mark_price=excluded.mark_price,
                    last_price=excluded.last_price,
                    quote_volume=excluded.quote_volume,
                    quanto_multiplier=excluded.quanto_multiplier,
                    order_price_round=excluded.order_price_round,
                    order_size_min=excluded.order_size_min,
                    order_size_max=excluded.order_size_max,
                    updated_ts=excluded.updated_ts
                """,
                row,
            )
            conn.commit()

    def insert_decision(self, row: Dict[str, Any]) -> int:
        cols = list(row.keys())
        vals = [row[c] for c in cols]
        q = f"INSERT INTO decisions ({','.join(cols)}) VALUES ({','.join(['?']*len(cols))})"
        with self._conn() as conn:
            cur = conn.execute(q, vals)
            conn.commit()
            return int(cur.lastrowid)

    def insert_order(self, row: Dict[str, Any]) -> int:
        cols = list(row.keys())
        vals = [row[c] for c in cols]
        q = f"INSERT INTO orders ({','.join(cols)}) VALUES ({','.join(['?']*len(cols))})"
        with self._conn() as conn:
            cur = conn.execute(q, vals)
            conn.commit()
            return int(cur.lastrowid)

    def update_order(self, order_id: int, updates: Dict[str, Any]) -> None:
        if not updates:
            return
        keys = list(updates.keys())
        vals = [updates[k] for k in keys] + [order_id]
        set_clause = ",".join([f"{k}=?" for k in keys])
        with self._conn() as conn:
            conn.execute(f"UPDATE orders SET {set_clause} WHERE id=?", vals)
            conn.commit()

    def open_position(self, row: Dict[str, Any]) -> int:
        cols = list(row.keys())
        vals = [row[c] for c in cols]
        q = f"INSERT INTO positions ({','.join(cols)}) VALUES ({','.join(['?']*len(cols))})"
        with self._conn() as conn:
            cur = conn.execute(q, vals)
            conn.commit()
            return int(cur.lastrowid)

    def update_position(self, pos_id: int, updates: Dict[str, Any]) -> None:
        if not updates:
            return
        keys = list(updates.keys())
        vals = [updates[k] for k in keys] + [pos_id]
        set_clause = ",".join([f"{k}=?" for k in keys])
        with self._conn() as conn:
            conn.execute(f"UPDATE positions SET {set_clause} WHERE id=?", vals)
            conn.commit()

    def get_open_position(self, symbol: str) -> Optional[Dict[str, Any]]:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM positions WHERE symbol=? AND status='open' ORDER BY id DESC LIMIT 1",
                (symbol,),
            ).fetchone()
            return dict(row) if row else None

    def get_working_orders(self, symbol: Optional[str] = None) -> List[Dict[str, Any]]:
        with self._conn() as conn:
            if symbol:
                rows = conn.execute(
                    "SELECT * FROM orders WHERE symbol=? AND state IN ('working','submitted','paper_open') ORDER BY id DESC",
                    (symbol,),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM orders WHERE state IN ('working','submitted','paper_open') ORDER BY id DESC"
                ).fetchall()
            return [dict(r) for r in rows]

    def recent_events(self, limit: int = 100) -> List[Dict[str, Any]]:
        with self._conn() as conn:
            return [dict(r) for r in conn.execute("SELECT * FROM events ORDER BY id DESC LIMIT ?", (limit,)).fetchall()]

    def recent_decisions(self, limit: int = 100) -> List[Dict[str, Any]]:
        with self._conn() as conn:
            return [dict(r) for r in conn.execute("SELECT * FROM decisions ORDER BY id DESC LIMIT ?", (limit,)).fetchall()]

    def recent_orders(self, limit: int = 100) -> List[Dict[str, Any]]:
        with self._conn() as conn:
            return [dict(r) for r in conn.execute("SELECT * FROM orders ORDER BY id DESC LIMIT ?", (limit,)).fetchall()]

    def recent_positions(self, limit: int = 100) -> List[Dict[str, Any]]:
        with self._conn() as conn:
            return [dict(r) for r in conn.execute("SELECT * FROM positions ORDER BY id DESC LIMIT ?", (limit,)).fetchall()]

    def get_state(self, key: str, default: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        with self._conn() as conn:
            row = conn.execute("SELECT v FROM kv_state WHERE k=?", (key,)).fetchone()
            if not row:
                return default or {}
            try:
                return json.loads(row[0])
            except Exception:
                return default or {}

    def set_state(self, key: str, val: Dict[str, Any]) -> None:
        with self._conn() as conn:
            conn.execute(
                "INSERT INTO kv_state(k,v) VALUES (?,?) ON CONFLICT(k) DO UPDATE SET v=excluded.v",
                (key, json_s(val)),
            )
            conn.commit()


DBI = DB(CFG.db_path)


# ============================================================
# Gate REST
# ============================================================

class GateRest:
    def __init__(self, cfg: Config):
        self.cfg = cfg
        self.session: Optional[aiohttp.ClientSession] = None

    async def ensure(self) -> None:
        if self.session is None or self.session.closed:
            timeout = aiohttp.ClientTimeout(total=self.cfg.request_timeout)
            self.session = aiohttp.ClientSession(timeout=timeout)

    def _headers(self, method: str, path: str, query_string: str = "", body: str = "") -> Dict[str, str]:
        ts = str(int(time.time()))
        body_hash = hashlib.sha512(body.encode("utf-8")).hexdigest()
        sign_str = f"{method.upper()}\n/api/v4{path}\n{query_string}\n{body_hash}\n{ts}"
        sign = hmac.new(self.cfg.gate_api_secret.encode(), sign_str.encode(), hashlib.sha512).hexdigest()
        return {
            "KEY": self.cfg.gate_api_key,
            "Timestamp": ts,
            "SIGN": sign,
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    async def public(self, path: str, params: Optional[Dict[str, Any]] = None) -> Any:
        await self.ensure()
        assert self.session
        url = f"{self.cfg.gate_base_url}{path}"
        async with self.session.get(url, params=params or {}) as r:
            text = await r.text()
            if r.status >= 400:
                raise RuntimeError(f"public {path} {r.status}: {text[:400]}")
            return json.loads(text) if text.strip() else {}

    async def private(self, method: str, path: str, params: Optional[Dict[str, Any]] = None, payload: Optional[Dict[str, Any]] = None) -> Any:
        await self.ensure()
        assert self.session
        params = params or {}
        payload = payload or {}
        query_string = urlencode(params)
        body = json.dumps(payload, separators=(",", ":")) if payload else ""
        headers = self._headers(method, path, query_string, body)
        url = f"{self.cfg.gate_base_url}{path}"
        async with self.session.request(method.upper(), url, params=params, data=body if body else None, headers=headers) as r:
            text = await r.text()
            if r.status >= 400:
                raise RuntimeError(f"private {method} {path} {r.status}: {text[:500]}")
            return json.loads(text) if text.strip() else {}

    async def list_contracts(self) -> List[Dict[str, Any]]:
        data = await self.public(f"/futures/{self.cfg.settle}/contracts")
        return data if isinstance(data, list) else []

    async def list_tickers(self) -> List[Dict[str, Any]]:
        data = await self.public(f"/futures/{self.cfg.settle}/tickers")
        return data if isinstance(data, list) else []

    async def get_contract(self, contract: str) -> Dict[str, Any]:
        data = await self.public(f"/futures/{self.cfg.settle}/contracts/{contract}")
        return data if isinstance(data, dict) else {}

    async def get_candles(self, contract: str, interval: str, limit: int) -> pd.DataFrame:
        data = await self.public(
            f"/futures/{self.cfg.settle}/candlesticks",
            {"contract": contract, "interval": interval, "limit": min(limit, 2000)},
        )
        rows: List[Dict[str, Any]] = []
        for item in data or []:
            if isinstance(item, dict):
                rows.append({
                    "t": item.get("t"),
                    "o": item.get("o"),
                    "h": item.get("h"),
                    "l": item.get("l"),
                    "c": item.get("c"),
                    "v": item.get("v"),
                })
            elif isinstance(item, list) and len(item) >= 6:
                rows.append({"t": item[0], "v": item[1], "c": item[2], "h": item[3], "l": item[4], "o": item[5]})
        df = pd.DataFrame(rows)
        if df.empty:
            return df
        for c in ["o", "h", "l", "c", "v"]:
            df[c] = pd.to_numeric(df[c], errors="coerce")
        df["timestamp"] = pd.to_datetime(df["t"], unit="s", utc=True)
        df = df.rename(columns={"o": "open", "h": "high", "l": "low", "c": "close", "v": "volume"})
        return df[["timestamp", "open", "high", "low", "close", "volume"]].dropna().sort_values("timestamp").reset_index(drop=True)

    async def get_order_book(self, contract: str, limit: int = 5) -> Dict[str, Any]:
        data = await self.public(f"/futures/{self.cfg.settle}/order_book", {"contract": contract, "limit": limit})
        return data if isinstance(data, dict) else {}

    async def list_open_orders(self, contract: Optional[str] = None) -> List[Dict[str, Any]]:
        params = {"status": "open"}
        if contract:
            params["contract"] = contract
        data = await self.private("GET", f"/futures/{self.cfg.settle}/orders", params=params)
        return data if isinstance(data, list) else []

    async def get_order(self, order_id: str) -> Dict[str, Any]:
        data = await self.private("GET", f"/futures/{self.cfg.settle}/orders/{order_id}")
        return data if isinstance(data, dict) else {}

    async def cancel_order(self, order_id: str) -> Dict[str, Any]:
        data = await self.private("DELETE", f"/futures/{self.cfg.settle}/orders/{order_id}")
        return data if isinstance(data, dict) else {}

    async def list_positions(self) -> List[Dict[str, Any]]:
        data = await self.private("GET", f"/futures/{self.cfg.settle}/positions")
        return data if isinstance(data, list) else []

    async def update_leverage(self, contract: str, leverage: int) -> Dict[str, Any]:
        data = await self.private("POST", f"/futures/{self.cfg.settle}/positions/{contract}/leverage", payload={"leverage": str(leverage)})
        return data if isinstance(data, dict) else {}

    async def create_order(self, contract: str, size: int, price: float, text_tag: str, reduce_only: bool = False, tif: str = "poc") -> Dict[str, Any]:
        payload = {
            "contract": contract,
            "size": size,
            "price": f"{price:.10f}",
            "tif": tif,
            "text": text_tag[:28],
            "reduce_only": reduce_only,
        }
        data = await self.private("POST", f"/futures/{self.cfg.settle}/orders", payload=payload)
        return data if isinstance(data, dict) else {}

    async def close(self) -> None:
        if self.session and not self.session.closed:
            await self.session.close()


# ============================================================
# Market state and indicators
# ============================================================

@dataclass
class BookTop:
    bid: float = 0.0
    ask: float = 0.0
    bid_size: float = 0.0
    ask_size: float = 0.0
    ts: float = 0.0

    @property
    def mid(self) -> float:
        if self.bid > 0 and self.ask > 0:
            return (self.bid + self.ask) / 2.0
        return 0.0

    @property
    def spread(self) -> float:
        if self.bid > 0 and self.ask > 0 and self.ask >= self.bid:
            return self.ask - self.bid
        return 0.0


@dataclass
class SymbolSpec:
    symbol: str
    mark_price: float
    quote_volume: float
    quanto_multiplier: float
    order_price_round: float
    order_size_min: int
    order_size_max: int


@dataclass
class SymbolRuntime:
    symbol: str
    spec: SymbolSpec
    book: BookTop = field(default_factory=BookTop)
    candles: Optional[pd.DataFrame] = None
    last_signal_ts: float = 0.0
    last_trade_ts: float = 0.0
    state: str = "flat"
    recent_mid: Deque[float] = field(default_factory=lambda: deque(maxlen=120))


class MarketState:
    def __init__(self):
        self.by_symbol: Dict[str, SymbolRuntime] = {}
        self.lock = asyncio.Lock()

    async def set_symbols(self, runtimes: Dict[str, SymbolRuntime]) -> None:
        async with self.lock:
            self.by_symbol = runtimes

    async def get(self, symbol: str) -> Optional[SymbolRuntime]:
        async with self.lock:
            return self.by_symbol.get(symbol)

    async def symbols(self) -> List[str]:
        async with self.lock:
            return list(self.by_symbol.keys())

    async def items(self) -> List[Tuple[str, SymbolRuntime]]:
        async with self.lock:
            return list(self.by_symbol.items())


MARKET = MarketState()


def add_features(df: pd.DataFrame) -> pd.DataFrame:
    x = df.copy()
    x["ret1"] = x["close"].pct_change(1)
    x["ret3"] = x["close"].pct_change(3)
    x["ret12"] = x["close"].pct_change(12)
    x["ema8"] = x["close"].ewm(span=8, adjust=False).mean()
    x["ema21"] = x["close"].ewm(span=21, adjust=False).mean()
    x["ema55"] = x["close"].ewm(span=55, adjust=False).mean()
    x["vol20"] = x["ret1"].rolling(20).std()
    x["atr14"] = (pd.concat([
        (x["high"] - x["low"]),
        (x["high"] - x["close"].shift()).abs(),
        (x["low"] - x["close"].shift()).abs(),
    ], axis=1).max(axis=1)).rolling(14).mean()
    x["z20"] = (x["close"] - x["close"].rolling(20).mean()) / x["close"].rolling(20).std()
    x["volz"] = (x["volume"] - x["volume"].rolling(20).mean()) / x["volume"].rolling(20).std()
    x["dist_ema21_atr"] = (x["close"] - x["ema21"]) / x["atr14"].replace(0, np.nan)
    return x


def round_to_tick(price: float, tick: float) -> float:
    if tick <= 0:
        return price
    return round(round(price / tick) * tick, 10)


def best_bid_ask_from_book(book: Dict[str, Any]) -> Tuple[float, float]:
    bids = book.get("bids") or []
    asks = book.get("asks") or []
    if not bids or not asks:
        return 0.0, 0.0
    def get_price(row: Any) -> float:
        if isinstance(row, list):
            return safe_float(row[0])
        if isinstance(row, dict):
            return safe_float(row.get("p"))
        return 0.0
    return get_price(bids[0]), get_price(asks[0])


def compute_size(spec: SymbolSpec, mid: float, risk_usd: float, leverage: int, side: str) -> int:
    mult = max(spec.quanto_multiplier, 1e-9)
    notional = risk_usd * leverage
    contracts = max(int(notional / max(mid * mult, 1e-9)), spec.order_size_min or 1)
    if spec.order_size_max > 0:
        contracts = min(contracts, spec.order_size_max)
    return contracts if side == "buy" else -contracts


def estimate_micro_alpha(rt: SymbolRuntime) -> Dict[str, float]:
    df = rt.candles
    if df is None or len(df) < 80:
        return {"score": 0.0, "confidence": 0.0}
    row = df.iloc[-1]
    bid = rt.book.bid
    ask = rt.book.ask
    mid = rt.book.mid or safe_float(row["close"])
    spread = rt.book.spread
    tick = max(rt.spec.order_price_round, 1e-8)

    trend = np.clip((safe_float(row["ema8"]) - safe_float(row["ema21"])) / max(mid, 1e-9) * 2000.0, -1.0, 1.0)
    slow_trend = np.clip((safe_float(row["ema21"]) - safe_float(row["ema55"])) / max(mid, 1e-9) * 2000.0, -1.0, 1.0)
    reversion = np.clip(-safe_float(row["z20"]) / 2.5, -1.0, 1.0)
    flow = np.clip((rt.book.bid_size - rt.book.ask_size) / max(rt.book.bid_size + rt.book.ask_size, 1e-9), -1.0, 1.0)
    spread_score = np.clip((spread / tick - 1.0) / 5.0, -1.0, 1.0)
    volume = np.clip(safe_float(row["volz"]) / 2.0, -1.0, 1.0)
    recent = list(rt.recent_mid)
    micro_momo = 0.0
    if len(recent) >= 6 and recent[0] > 0:
        micro_momo = np.clip((recent[-1] / recent[0] - 1.0) * 400.0, -1.0, 1.0)

    score = (
        0.25 * trend +
        0.15 * slow_trend +
        0.20 * reversion +
        0.20 * flow +
        0.10 * spread_score +
        0.05 * volume +
        0.05 * micro_momo
    )
    confidence = min(abs(score), 0.95)
    return {
        "score": float(score),
        "confidence": float(confidence),
        "trend": float(trend),
        "slow_trend": float(slow_trend),
        "reversion": float(reversion),
        "flow": float(flow),
        "spread_score": float(spread_score),
        "volume": float(volume),
        "micro_momo": float(micro_momo),
        "mid": float(mid),
        "spread": float(spread),
        "tick": float(tick),
    }


# ============================================================
# Execution-aware backtest
# ============================================================

@dataclass
class BacktestResult:
    trades: int
    win_rate: float
    avg_pnl_usd: float
    avg_edge_bps: float
    pnl_usd: float
    max_drawdown_usd: float
    sharpe_like: float
    allowed: bool
    details: Dict[str, Any]


class Backtester:
    def __init__(self, cfg: Config):
        self.cfg = cfg

    def simulate(self, df: pd.DataFrame, spec: SymbolSpec) -> BacktestResult:
        if df is None or len(df) < 120:
            return BacktestResult(0, 0.0, 0.0, 0.0, 0.0, 0.0, -99.0, False, {"reason": "not_enough_data"})

        x = df.copy().reset_index(drop=True)
        x = add_features(x).dropna().reset_index(drop=True)
        if len(x) < 100:
            return BacktestResult(0, 0.0, 0.0, 0.0, 0.0, 0.0, -99.0, False, {"reason": "not_enough_features"})

        equity = 0.0
        peak = 0.0
        max_dd = 0.0
        pnls: List[float] = []
        edge_bps_arr: List[float] = []
        cooldown_until = -1

        for i in range(70, len(x) - 8):
            if i < cooldown_until:
                continue
            row = x.iloc[i]
            mid = safe_float(row["close"])
            atr = max(safe_float(row["atr14"]), mid * 0.002)
            spread = max(spec.order_price_round, mid * 0.0008)
            queue_fill_prob = clamp(0.28 + abs(safe_float(row["volz"])) * 0.07 + (spread / max(spec.order_price_round, 1e-8) - 1.0) * 0.03, 0.10, 0.85)
            trend = np.clip((safe_float(row["ema8"]) - safe_float(row["ema21"])) / max(mid, 1e-9) * 2000.0, -1.0, 1.0)
            rev = np.clip(-safe_float(row["z20"]) / 2.5, -1.0, 1.0)
            score = 0.6 * trend + 0.4 * rev
            if abs(score) < 0.23:
                continue
            side = "buy" if score > 0 else "sell"

            if random.random() > queue_fill_prob:
                continue

            entry = (mid - spread / 2.0) if side == "buy" else (mid + spread / 2.0)
            take = entry + atr * self.cfg.take_atr_mult if side == "buy" else entry - atr * self.cfg.take_atr_mult
            stop = entry - atr * self.cfg.stop_atr_mult if side == "buy" else entry + atr * self.cfg.stop_atr_mult
            contracts = compute_size(spec, mid, self.cfg.contract_risk_usd, self.cfg.leverage, side)
            qty = abs(contracts)
            gross = 0.0
            exit_reason = "timeout"

            for j in range(i + 1, min(i + 8, len(x))):
                bar = x.iloc[j]
                high = safe_float(bar["high"])
                low = safe_float(bar["low"])
                if side == "buy":
                    if low <= stop:
                        exit_px = stop - spread * 0.25
                        gross = (exit_px - entry) * qty * spec.quanto_multiplier
                        exit_reason = "stop"
                        break
                    if high >= take:
                        exit_px = take
                        gross = (exit_px - entry) * qty * spec.quanto_multiplier
                        exit_reason = "take"
                        break
                else:
                    if high >= stop:
                        exit_px = stop + spread * 0.25
                        gross = (entry - exit_px) * qty * spec.quanto_multiplier
                        exit_reason = "stop"
                        break
                    if low <= take:
                        exit_px = take
                        gross = (entry - exit_px) * qty * spec.quanto_multiplier
                        exit_reason = "take"
                        break
            else:
                exit_px = safe_float(x.iloc[min(i + 7, len(x) - 1)]["close"])
                if side == "buy":
                    gross = (exit_px - entry) * qty * spec.quanto_multiplier
                else:
                    gross = (entry - exit_px) * qty * spec.quanto_multiplier

            fees = qty * spec.quanto_multiplier * entry * (self.cfg.maker_fee_bps / 10000.0)
            fees += qty * spec.quanto_multiplier * exit_px * (self.cfg.maker_fee_bps / 10000.0)
            pnl = gross - fees
            edge_bps = ((take - entry) / max(entry, 1e-9) * 10000.0) if side == "buy" else ((entry - take) / max(entry, 1e-9) * 10000.0)
            edge_bps_arr.append(edge_bps)
            pnls.append(pnl)
            equity += pnl
            peak = max(peak, equity)
            max_dd = max(max_dd, peak - equity)
            cooldown_until = i + 2

        trades = len(pnls)
        win_rate = float(np.mean([1.0 if x > 0 else 0.0 for x in pnls])) if pnls else 0.0
        avg_pnl = float(np.mean(pnls)) if pnls else 0.0
        avg_edge = float(np.mean(edge_bps_arr)) if edge_bps_arr else 0.0
        pnl = float(np.sum(pnls)) if pnls else 0.0
        sharpe_like = float(np.mean(pnls) / (np.std(pnls) + 1e-9) * math.sqrt(max(len(pnls), 1))) if pnls else -99.0
        allowed = trades >= 10 and win_rate >= 0.50 and avg_pnl > 0 and max_dd < max(1.5 * abs(pnl), 15.0)
        return BacktestResult(
            trades=trades,
            win_rate=win_rate,
            avg_pnl_usd=avg_pnl,
            avg_edge_bps=avg_edge,
            pnl_usd=pnl,
            max_drawdown_usd=float(max_dd),
            sharpe_like=sharpe_like,
            allowed=allowed,
            details={"sample": trades, "equity": equity},
        )


# ============================================================
# WebSocket market data
# ============================================================

class BookTickerWS:
    def __init__(self, cfg: Config, market: MarketState):
        self.cfg = cfg
        self.market = market
        self.shutdown = False

    async def run(self) -> None:
        backoff = 1.0
        while not self.shutdown:
            try:
                syms = await self.market.symbols()
                if not syms:
                    await asyncio.sleep(1.0)
                    continue
                async with websockets.connect(self.cfg.gate_ws_url, ping_interval=20, ping_timeout=20, max_size=2**23) as ws:
                    log.info("WS connected to %s", self.cfg.gate_ws_url)
                    for batch in chunks(syms, 20):
                        msg = {
                            "time": int(time.time()),
                            "channel": "futures.book_ticker",
                            "event": "subscribe",
                            "payload": batch,
                        }
                        await ws.send(json.dumps(msg))
                    backoff = 1.0
                    async for raw in ws:
                        data = json.loads(raw)
                        channel = data.get("channel")
                        event = data.get("event")
                        if channel != "futures.book_ticker" or event not in {"update", "all"}:
                            continue
                        result = data.get("result") or data.get("payload")
                        if isinstance(result, list):
                            for item in result:
                                await self._apply(item)
                        elif isinstance(result, dict):
                            await self._apply(result)
            except asyncio.CancelledError:
                raise
            except Exception as e:
                log.warning("WS reconnect after error: %s", e)
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2.0, 20.0)

    async def _apply(self, item: Dict[str, Any]) -> None:
        symbol = str(item.get("s") or item.get("contract") or item.get("n") or "")
        if not symbol:
            return
        rt = await self.market.get(symbol)
        if not rt:
            return
        bid = safe_float(item.get("b") or item.get("bid_price"))
        ask = safe_float(item.get("a") or item.get("ask_price"))
        bid_size = safe_float(item.get("B") or item.get("bid_size") or item.get("bid_amount"))
        ask_size = safe_float(item.get("A") or item.get("ask_size") or item.get("ask_amount"))
        if bid <= 0 or ask <= 0 or ask < bid:
            return
        rt.book.bid = bid
        rt.book.ask = ask
        rt.book.bid_size = bid_size
        rt.book.ask_size = ask_size
        rt.book.ts = now_ts()
        rt.recent_mid.append(rt.book.mid)


# ============================================================
# Trader
# ============================================================

class Trader:
    def __init__(self, cfg: Config, db: DB, rest: GateRest, market: MarketState):
        self.cfg = cfg
        self.db = db
        self.rest = rest
        self.market = market
        self.backtester = Backtester(cfg)
        self.shutdown = False
        self.runtime = self.db.get_state("runtime", {"mode": "paper", "last_scan": [], "last_errors": []})

    async def scan_symbols(self) -> Dict[str, SymbolRuntime]:
        tickers = await self.rest.list_tickers()
        contracts = await self.rest.list_contracts()
        specs_by_symbol: Dict[str, Dict[str, Any]] = {str(c.get("name") or c.get("contract") or c.get("id") or ""): c for c in contracts}
        selected: List[SymbolRuntime] = []

        if self.cfg.app_symbols:
            tickers = [t for t in tickers if str(t.get("contract") or t.get("name") or "") in set(self.cfg.app_symbols)]

        for t in tickers:
            symbol = str(t.get("contract") or t.get("name") or "")
            if not symbol:
                continue
            mark_price = safe_float(t.get("mark_price") or t.get("last") or t.get("last_price"))
            quote_volume = safe_float(t.get("volume_24h_quote") or t.get("volume_24h_usd") or t.get("volume_24h_settle"))
            if not self.cfg.app_symbols:
                if not (self.cfg.min_mark_price <= mark_price <= self.cfg.max_mark_price):
                    continue
                if quote_volume < self.cfg.min_24h_quote_vol:
                    continue
            spec_raw = specs_by_symbol.get(symbol) or {}
            spec = SymbolSpec(
                symbol=symbol,
                mark_price=mark_price,
                quote_volume=quote_volume,
                quanto_multiplier=max(safe_float(spec_raw.get("quanto_multiplier"), 0.0001), 1e-9),
                order_price_round=max(safe_float(spec_raw.get("order_price_round"), 0.00000001), 1e-8),
                order_size_min=max(safe_int(spec_raw.get("order_size_min"), 1), 1),
                order_size_max=max(safe_int(spec_raw.get("order_size_max"), 0), 0),
            )
            selected.append(SymbolRuntime(symbol=symbol, spec=spec))

        selected = sorted(selected, key=lambda r: (r.spec.quote_volume, -r.spec.mark_price), reverse=True)[: self.cfg.max_symbols]
        for rt in selected:
            self.db.upsert_symbol({
                "symbol": rt.symbol,
                "mark_price": rt.spec.mark_price,
                "last_price": rt.spec.mark_price,
                "quote_volume": rt.spec.quote_volume,
                "quanto_multiplier": rt.spec.quanto_multiplier,
                "order_price_round": rt.spec.order_price_round,
                "order_size_min": rt.spec.order_size_min,
                "order_size_max": rt.spec.order_size_max,
                "updated_ts": utc_now_iso(),
            })
        self.runtime["last_scan"] = [r.symbol for r in selected]
        self.db.set_state("runtime", self.runtime)
        return {r.symbol: r for r in selected}

    async def hydrate_candles(self) -> None:
        for symbol, rt in await self.market.items():
            try:
                df = await self.rest.get_candles(symbol, self.cfg.bar_interval, self.cfg.bar_limit)
                if df.empty:
                    continue
                rt.candles = add_features(df).dropna().reset_index(drop=True)
            except Exception as e:
                self.db.event("ERROR", "hydrate_candles_failed", symbol, {"error": str(e)})

    async def reconcile_once(self) -> None:
        if not self.cfg.live_trading:
            return
        local_orders = self.db.get_working_orders()
        if not local_orders:
            return
        exchange_open = await self.rest.list_open_orders()
        exchange_open_ids = {str(x.get("id")) for x in exchange_open if x.get("id") is not None}

        for order in local_orders:
            ex_id = str(order.get("exchange_order_id") or "")
            if not ex_id:
                continue
            try:
                if ex_id in exchange_open_ids:
                    self.db.update_order(order["id"], {"state": "working", "exchange_status": "open"})
                    continue
                detail = await self.rest.get_order(ex_id)
                status = str(detail.get("status") or "")
                finish_as = str(detail.get("finish_as") or "")
                fill_price = safe_float(detail.get("fill_price") or detail.get("price"))
                left = safe_int(detail.get("left"), 0)
                update = {
                    "exchange_status": status,
                    "fill_price": fill_price,
                    "left_size": left,
                    "raw_response_json": json_s(detail),
                }
                if finish_as == "filled" or (status == "finished" and left == 0):
                    update["state"] = "filled"
                elif status == "cancelled":
                    update["state"] = "cancelled"
                elif status == "finished":
                    update["state"] = "done"
                self.db.update_order(order["id"], update)
                if update.get("state") == "filled":
                    await self._on_order_filled(order, fill_price)
            except Exception as e:
                self.db.event("ERROR", "reconcile_order_failed", order["symbol"], {"order_id": ex_id, "error": str(e)})

    async def _on_order_filled(self, order: Dict[str, Any], fill_price: float) -> None:
        symbol = order["symbol"]
        if order["role"] == "entry":
            pos = self.db.get_open_position(symbol)
            if pos:
                return
            side = order["side"]
            size = abs(safe_int(order["requested_size"], 0))
            rt = await self.market.get(symbol)
            atr = safe_float(rt.candles.iloc[-1]["atr14"]) if rt and rt.candles is not None else fill_price * 0.01
            take = fill_price + atr * self.cfg.take_atr_mult if side == "buy" else fill_price - atr * self.cfg.take_atr_mult
            stop = fill_price - atr * self.cfg.stop_atr_mult if side == "buy" else fill_price + atr * self.cfg.stop_atr_mult
            self.db.open_position({
                "ts_open": utc_now_iso(),
                "ts_close": None,
                "symbol": symbol,
                "side": side,
                "status": "open",
                "size": size,
                "entry_price": fill_price,
                "exit_price": None,
                "take_price": take,
                "stop_price": stop,
                "realized_pnl_usd": None,
                "reason_open": "entry_fill",
                "reason_close": None,
                "meta_json": json_s({"entry_order_id": order["id"]}),
            })
            self.db.event("INFO", "position_opened", symbol, {"side": side, "entry": fill_price, "take": take, "stop": stop})
            await self.ensure_exit_order(symbol)
        elif order["role"] == "exit":
            pos = self.db.get_open_position(symbol)
            if not pos:
                return
            mult = safe_float((await self.market.get(symbol)).spec.quanto_multiplier if await self.market.get(symbol) else 1.0, 1.0)
            pnl = ((fill_price - safe_float(pos["entry_price"])) if pos["side"] == "buy" else (safe_float(pos["entry_price"]) - fill_price)) * safe_int(pos["size"], 0) * mult
            self.db.update_position(pos["id"], {
                "ts_close": utc_now_iso(),
                "status": "closed",
                "exit_price": fill_price,
                "realized_pnl_usd": pnl,
                "reason_close": "maker_exit_fill",
            })
            self.db.event("INFO", "position_closed", symbol, {"exit": fill_price, "pnl_usd": pnl})

    async def ensure_exit_order(self, symbol: str) -> None:
        pos = self.db.get_open_position(symbol)
        if not pos:
            return
        existing = [o for o in self.db.get_working_orders(symbol) if o["role"] == "exit"]
        if existing:
            return
        rt = await self.market.get(symbol)
        if not rt or rt.book.bid <= 0 or rt.book.ask <= 0:
            return
        if pos["side"] == "buy":
            side = "sell"
            px = max(rt.book.ask, safe_float(pos["take_price"]))
            size = -abs(safe_int(pos["size"], 0))
        else:
            side = "buy"
            px = min(rt.book.bid, safe_float(pos["take_price"])) if rt.book.bid > 0 else safe_float(pos["take_price"])
            size = abs(safe_int(pos["size"], 0))
        px = round_to_tick(px, rt.spec.order_price_round)
        tag = f"x-{hashlib.sha1(f'{symbol}|exit|{time.time()}'.encode()).hexdigest()[:20]}"[:28]
        req = {"contract": symbol, "size": size, "price": px, "reduce_only": True, "tif": "poc", "text": tag}
        if not self.cfg.live_trading:
            self.db.insert_order({
                "ts": utc_now_iso(), "symbol": symbol, "role": "exit", "side": side, "state": "paper_open", "text_tag": tag,
                "reduce_only": 1, "requested_price": px, "requested_size": size, "exchange_order_id": None,
                "exchange_status": "paper", "fill_price": None, "left_size": abs(size),
                "raw_request_json": json_s(req), "raw_response_json": "{}", "notes": "paper_exit",
            })
            return
        resp = await self.rest.create_order(symbol, size, px, tag, reduce_only=True)
        self.db.insert_order({
            "ts": utc_now_iso(), "symbol": symbol, "role": "exit", "side": side, "state": "working", "text_tag": tag,
            "reduce_only": 1, "requested_price": px, "requested_size": size, "exchange_order_id": str(resp.get("id") or ""),
            "exchange_status": str(resp.get("status") or "submitted"), "fill_price": None, "left_size": abs(size),
            "raw_request_json": json_s(req), "raw_response_json": json_s(resp), "notes": "live_exit",
        })

    async def maybe_stop_position(self, symbol: str) -> None:
        pos = self.db.get_open_position(symbol)
        if not pos:
            return
        rt = await self.market.get(symbol)
        if not rt or rt.book.bid <= 0 or rt.book.ask <= 0:
            return
        stop = safe_float(pos["stop_price"])
        side = pos["side"]
        if side == "buy" and rt.book.bid <= stop:
            await self.force_close(symbol, reason="stop_cross")
        elif side == "sell" and rt.book.ask >= stop:
            await self.force_close(symbol, reason="stop_cross")

    async def force_close(self, symbol: str, reason: str) -> None:
        pos = self.db.get_open_position(symbol)
        rt = await self.market.get(symbol)
        if not pos or not rt:
            return
        if pos["side"] == "buy":
            exit_px = rt.book.bid
        else:
            exit_px = rt.book.ask
        mult = rt.spec.quanto_multiplier
        pnl = ((exit_px - safe_float(pos["entry_price"])) if pos["side"] == "buy" else (safe_float(pos["entry_price"]) - exit_px)) * safe_int(pos["size"], 0) * mult
        self.db.update_position(pos["id"], {
            "ts_close": utc_now_iso(),
            "status": "closed",
            "exit_price": exit_px,
            "realized_pnl_usd": pnl,
            "reason_close": reason,
        })
        self.db.event("WARNING", "position_force_closed_locally", symbol, {"exit_px": exit_px, "reason": reason, "pnl_usd": pnl})
        # NOTE: for a stricter live implementation you would place an IOC/market-like protective order if exchange supports it for the contract.

    async def maybe_place_entry(self, symbol: str, side: str, alpha: Dict[str, Any], bt: BacktestResult) -> None:
        if side not in {"buy", "sell"}:
            return
        rt = await self.market.get(symbol)
        if not rt or rt.book.bid <= 0 or rt.book.ask <= 0:
            return
        if self.db.get_open_position(symbol):
            return
        if any(o for o in self.db.get_working_orders(symbol) if o["role"] == "entry"):
            return
        if now_ts() - rt.last_trade_ts < self.cfg.cooldown_seconds:
            return

        mid = rt.book.mid
        expected_edge_bps = abs(alpha["score"]) * 10.0 + (rt.book.spread / max(mid, 1e-9) * 10000.0)
        if expected_edge_bps < self.cfg.entry_edge_bps:
            return
        size = compute_size(rt.spec, mid, self.cfg.contract_risk_usd, self.cfg.leverage, side)
        px = rt.book.bid if side == "buy" else rt.book.ask
        px = round_to_tick(px, rt.spec.order_price_round)
        tag = f"e-{hashlib.sha1(f'{symbol}|entry|{time.time()}'.encode()).hexdigest()[:20]}"[:28]
        req = {"contract": symbol, "size": size, "price": px, "reduce_only": False, "tif": "poc", "text": tag}

        if not self.cfg.live_trading:
            self.db.insert_order({
                "ts": utc_now_iso(), "symbol": symbol, "role": "entry", "side": side, "state": "paper_open", "text_tag": tag,
                "reduce_only": 0, "requested_price": px, "requested_size": size, "exchange_order_id": None,
                "exchange_status": "paper", "fill_price": None, "left_size": abs(size),
                "raw_request_json": json_s(req), "raw_response_json": json_s({"alpha": alpha, "backtest": dataclasses.asdict(bt)}), "notes": "paper_entry",
            })
            # paper model: immediate maker fill only when microstructure agrees strongly
            if abs(alpha["score"]) >= 0.38:
                fake_order = {"symbol": symbol, "role": "entry", "side": side, "requested_size": size, "id": -1}
                await self._on_order_filled(fake_order, px)
            rt.last_trade_ts = now_ts()
            return

        await self.rest.update_leverage(symbol, self.cfg.leverage)
        resp = await self.rest.create_order(symbol, size, px, tag, reduce_only=False)
        self.db.insert_order({
            "ts": utc_now_iso(), "symbol": symbol, "role": "entry", "side": side, "state": "working", "text_tag": tag,
            "reduce_only": 0, "requested_price": px, "requested_size": size, "exchange_order_id": str(resp.get("id") or ""),
            "exchange_status": str(resp.get("status") or "submitted"), "fill_price": None, "left_size": abs(size),
            "raw_request_json": json_s(req), "raw_response_json": json_s(resp), "notes": "live_entry",
        })
        rt.last_trade_ts = now_ts()

    async def cancel_stale_orders(self, symbol: str) -> None:
        rt = await self.market.get(symbol)
        if not rt:
            return
        for order in self.db.get_working_orders(symbol):
            try:
                created = datetime.fromisoformat(order["ts"]).timestamp()
            except Exception:
                created = now_ts()
            age = now_ts() - created
            stale = age > max(15.0, self.cfg.loop_seconds * 4.0)
            desired = rt.book.bid if order["side"] == "buy" else rt.book.ask
            drift = abs(safe_float(order["requested_price"]) - desired)
            repriced = drift >= max(rt.spec.order_price_round, 1e-8)
            if not stale and not repriced:
                continue
            if not self.cfg.live_trading or not order.get("exchange_order_id"):
                self.db.update_order(order["id"], {"state": "cancelled", "notes": "paper_stale"})
                continue
            try:
                resp = await self.rest.cancel_order(str(order["exchange_order_id"]))
                self.db.update_order(order["id"], {"state": "cancelled", "exchange_status": str(resp.get("status") or "cancelled"), "raw_response_json": json_s(resp)})
            except Exception as e:
                self.db.event("ERROR", "cancel_order_failed", symbol, {"order_id": order.get("exchange_order_id"), "error": str(e)})

    async def process_symbol(self, symbol: str) -> None:
        rt = await self.market.get(symbol)
        if not rt or rt.candles is None or len(rt.candles) < 80:
            return
        if rt.book.bid <= 0 or rt.book.ask <= 0:
            # bootstrap with REST if WS not ready
            try:
                book = await self.rest.get_order_book(symbol, limit=1)
                bid, ask = best_bid_ask_from_book(book)
                if bid > 0 and ask > 0:
                    rt.book.bid, rt.book.ask, rt.book.ts = bid, ask, now_ts()
            except Exception:
                pass
            if rt.book.bid <= 0 or rt.book.ask <= 0:
                return

        if rt.candles is not None and len(rt.recent_mid) > 0:
            latest_mid = rt.book.mid
            latest_ts = pd.Timestamp.utcnow().tz_localize("UTC") if pd.Timestamp.utcnow().tzinfo is None else pd.Timestamp.utcnow()
            if abs(latest_mid - safe_float(rt.candles.iloc[-1]["close"])) / max(latest_mid, 1e-9) > 0.0001:
                new_row = {
                    "timestamp": latest_ts,
                    "open": latest_mid,
                    "high": max(latest_mid, safe_float(rt.candles.iloc[-1]["close"])),
                    "low": min(latest_mid, safe_float(rt.candles.iloc[-1]["close"])),
                    "close": latest_mid,
                    "volume": max(safe_float(rt.candles.iloc[-1]["volume"]), 1.0),
                }
                rt.candles = pd.concat([rt.candles[["timestamp", "open", "high", "low", "close", "volume"]], pd.DataFrame([new_row])], ignore_index=True).tail(self.cfg.bar_limit)
                rt.candles = add_features(rt.candles).dropna().reset_index(drop=True)

        alpha = estimate_micro_alpha(rt)
        score = alpha.get("score", 0.0)
        confidence = alpha.get("confidence", 0.0)
        if abs(score) < 0.22:
            await self.maybe_stop_position(symbol)
            await self.cancel_stale_orders(symbol)
            return
        side = "buy" if score > 0 else "sell"
        bt = self.backtester.simulate(rt.candles[["timestamp", "open", "high", "low", "close", "volume"]], rt.spec)
        live_ok = bt.allowed and abs(score) >= 0.28

        self.db.insert_decision({
            "ts": utc_now_iso(),
            "symbol": symbol,
            "side": side,
            "score": score,
            "confidence": confidence,
            "alpha_json": json_s(alpha),
            "market_json": json_s({"bid": rt.book.bid, "ask": rt.book.ask, "mid": rt.book.mid, "spread": rt.book.spread}),
            "backtest_json": json_s(dataclasses.asdict(bt)),
            "live_ok": 1 if live_ok else 0,
            "notes": "auto",
        })

        await self.maybe_stop_position(symbol)
        await self.cancel_stale_orders(symbol)
        if live_ok or not self.cfg.live_trading:
            await self.maybe_place_entry(symbol, side, alpha, bt)
        await self.ensure_exit_order(symbol)

    async def run_loop(self) -> None:
        runtimes = await self.scan_symbols()
        await self.market.set_symbols(runtimes)
        await self.hydrate_candles()
        self.db.event("INFO", "startup_symbols", "*", {"symbols": list(runtimes.keys())})
        while not self.shutdown:
            try:
                for symbol in await self.market.symbols():
                    await self.process_symbol(symbol)
                await self.reconcile_once()
            except Exception as e:
                self.db.event("ERROR", "main_loop_error", "*", {"error": str(e)})
            await asyncio.sleep(self.cfg.loop_seconds)


# ============================================================
# CLI modes
# ============================================================

async def run_scan(rest: GateRest) -> int:
    trader = Trader(CFG, DBI, rest, MARKET)
    runtimes = await trader.scan_symbols()
    print(json.dumps({
        "count": len(runtimes),
        "symbols": [{
            "symbol": r.symbol,
            "mark_price": r.spec.mark_price,
            "quote_volume": r.spec.quote_volume,
            "tick": r.spec.order_price_round,
            "multiplier": r.spec.quanto_multiplier,
        } for r in runtimes.values()]
    }, indent=2))
    return 0


async def run_backtest(rest: GateRest) -> int:
    trader = Trader(CFG, DBI, rest, MARKET)
    runtimes = await trader.scan_symbols()
    out = []
    for symbol, rt in runtimes.items():
        df = await rest.get_candles(symbol, CFG.bar_interval, CFG.bar_limit)
        bt = trader.backtester.simulate(df, rt.spec)
        out.append({
            "symbol": symbol,
            "trades": bt.trades,
            "win_rate": round(bt.win_rate, 4),
            "avg_pnl_usd": round(bt.avg_pnl_usd, 6),
            "pnl_usd": round(bt.pnl_usd, 6),
            "max_dd_usd": round(bt.max_drawdown_usd, 6),
            "sharpe_like": round(bt.sharpe_like, 4),
            "allowed": bt.allowed,
        })
    out = sorted(out, key=lambda x: x["pnl_usd"], reverse=True)
    print(json.dumps(out, indent=2))
    return 0


async def run_engine(mode: str, rest: GateRest) -> int:
    if mode == "live" and not CFG.live_trading:
        raise RuntimeError("Mode live requested but LIVE_TRADING=false in environment.")
    trader = Trader(CFG, DBI, rest, MARKET)
    ws = BookTickerWS(CFG, MARKET)
    tasks = [
        asyncio.create_task(trader.run_loop(), name="trader"),
        asyncio.create_task(ws.run(), name="ws"),
    ]
    stop = asyncio.Event()

    def _handle_signal() -> None:
        trader.shutdown = True
        ws.shutdown = True
        stop.set()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        with contextlib.suppress(NotImplementedError):
            loop.add_signal_handler(sig, _handle_signal)

    await stop.wait()
    for t in tasks:
        t.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await t
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Gate low-nominal multi-ticker market maker")
    p.add_argument("--mode", choices=["scan", "backtest", "paper", "live"], default="scan")
    return p


async def amain() -> int:
    args = build_parser().parse_args()
    rest = GateRest(CFG)
    try:
        if args.mode == "scan":
            return await run_scan(rest)
        if args.mode == "backtest":
            return await run_backtest(rest)
        if args.mode == "paper":
            return await run_engine("paper", rest)
        if args.mode == "live":
            return await run_engine("live", rest)
        return 0
    finally:
        await rest.close()


def main() -> int:
    try:
        return asyncio.run(amain())
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    sys.exit(main())
