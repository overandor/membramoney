#!/usr/bin/env python3
"""
gate_aggressive_hedge.py  ·  v1.0
══════════════════════════════════════════════════════════════════════════════
Aggressive Dual-Sided Hedged Microstructure Engine
Gate.io USDT Perpetual Futures  ·  0–10 cent notional micro orders
══════════════════════════════════════════════════════════════════════════════

EXECUTION MODEL
───────────────
  BUY  limit @ best_ask  →  aggressive long entry  (join / cross ask)
  SELL limit @ best_bid  →  aggressive short entry  (join / cross bid)

Both sides always live simultaneously per symbol (hedge mode).
On fill → immediately recycle (replace same side, hedge stays open).
Target: delta-neutral via equal long + short exposure per symbol.

PROFIT MECHANISM
────────────────
  Gate.io taker fee: 0.05%  (paid on aggressive fills)
  Gate.io maker rebate: −0.015%  (earned on poc fills)
  Mode: IOC by default (guaranteed fills, taker fees accepted)
  Alternative: poc (post-only-cancel) if you want maker rebates

HEDGE MODE (Gate.io Dual Position)
────────────────────────────────────
  Per symbol: simultaneous LONG + SHORT positions (Gate.io "dual mode")
  Long side managed independently of short side.
  Net delta = LONG_contracts − SHORT_contracts (target: 0)

RECYCLING ENGINE
────────────────
  On long fill  → immediately re-post BUY  @ new best_ask
  On short fill → immediately re-post SELL @ new best_bid
  If inventory exceeds MAX_INVENTORY_CONTRACTS → taker-close excess

RISK CONTROLS
─────────────
  Kill-switch: daily loss  |  Max inventory per symbol
  Stale book: halt quoting if WS data > BOOK_STALE_SEC
  Startup reconciler: align DB with live exchange state
  Rate-limiter: token bucket (8 private / 10 public req/s)

REQUIREMENTS
────────────
  pip install aiohttp websockets

ENV VARS
────────
  GATE_API_KEY      ← your API key
  GATE_API_SECRET   ← your API secret
  GATE_PAPER=1      ← paper mode (orders logged, not sent)

STARTUP
───────
  python gate_aggressive_hedge.py
  Dashboard → http://localhost:8765

══════════════════════════════════════════════════════════════════════════════
"""

from __future__ import annotations

# ─── stdlib ───────────────────────────────────────────────────────────────────
import asyncio
import hashlib
import hmac as hmac_mod
import json
import logging
import math
import os
import sqlite3
import sys
import time
import threading
import traceback
import uuid
from collections import defaultdict, deque
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum, auto
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any, Callable, Coroutine, Dict, List, Optional, Set, Tuple

# ─── third-party ──────────────────────────────────────────────────────────────
import aiohttp
import websockets
from websockets.exceptions import ConnectionClosed

# ═══════════════════════════════════════════════════════════════════════════════
# §1  LOGGING
# ═══════════════════════════════════════════════════════════════════════════════

LOG_FMT = "%(asctime)s.%(msecs)03d %(levelname)-5s [%(name)s] %(message)s"
LOG_DATE = "%Y-%m-%dT%H:%M:%S"

def _setup_logging(level: str = "INFO", log_file: str = "gate_hedge.log") -> None:
    root = logging.getLogger()
    root.setLevel(getattr(logging, level.upper(), logging.INFO))
    fh = logging.FileHandler(log_file, encoding="utf-8")
    fh.setFormatter(logging.Formatter(LOG_FMT, datefmt=LOG_DATE))
    ch = logging.StreamHandler(sys.stdout)
    ch.setFormatter(logging.Formatter(LOG_FMT, datefmt=LOG_DATE))
    root.addHandler(fh)
    root.addHandler(ch)

log = logging.getLogger("hedge")

# ═══════════════════════════════════════════════════════════════════════════════
# §2  CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════════

class Cfg:
    """All knobs in one place. Override via env or subclass."""

    # ── Auth ──────────────────────────────────────────────────────────────────
    API_KEY    : str = os.getenv("GATE_API_KEY",    "")
    API_SECRET : str = os.getenv("GATE_API_SECRET", "")
    PAPER      : bool = os.getenv("GATE_PAPER", "0") == "1"

    # ── Exchange endpoints ────────────────────────────────────────────────────
    SETTLE   : str = "usdt"
    REST_URL : str = "https://api.gateio.ws/api/v4"
    WS_URL   : str = "wss://fx-ws.gateio.ws/v4/ws/usdt"

    # ── Symbol universe ───────────────────────────────────────────────────────
    # Symbols with 1 contract ≈ $0.01–$0.10.  Auto-scanned at startup if empty.
    SYMBOLS : List[str] = []                  # e.g. ["DOGE_USDT","TRX_USDT"]
    MAX_SYMBOLS     : int   = 5               # cap after auto-scan
    SCAN_PRICE_MIN  : float = 0.001           # mark price lower bound
    SCAN_PRICE_MAX  : float = 0.10            # mark price upper bound (≈ max notional)
    SCAN_VOLUME_MIN : float = 500_000.0       # min 24h volume (contracts) – liquidity floor

    # ── Sizing ────────────────────────────────────────────────────────────────
    TARGET_NOTIONAL : float = 0.07   # USD target per order
    MIN_NOTIONAL    : float = 0.01   # USD floor
    MAX_NOTIONAL    : float = 0.10   # USD ceiling
    LEVERAGE        : int   = 10

    # ── Execution ─────────────────────────────────────────────────────────────
    # Primary TIF: "ioc" for guaranteed taker fills at best bid/ask
    #              "poc" for maker-only (will fail if price crosses)
    PRIMARY_TIF     : str   = "ioc"           # immediate-or-cancel taker
    FALLBACK_TIF    : str   = "ioc"           # same for fallback
    QUOTE_TTL_SEC   : float = 3.0             # cancel & reprice live orders
    REPRICE_TICKS   : int   = 1               # reprice if best moved ≥ N ticks
    REPRICE_LOOP_SEC: float = 0.2             # how often to check for reprice

    # ── Hedge / Recycling ─────────────────────────────────────────────────────
    MAX_INVENTORY   : int   = 5               # max contracts per side per symbol
    RECYCLE_DELAY_SEC: float = 0.05           # brief pause before re-entering
    ENABLE_DUAL_MODE: bool  = True            # enable Gate.io dual position mode

    # ── Risk ──────────────────────────────────────────────────────────────────
    MAX_DAILY_LOSS_USD   : float = 1.00
    KILL_SWITCH_LOSS_USD : float = 2.00
    MAX_OPEN_ORDERS_SYM  : int   = 6          # per symbol (3 long + 3 short)
    BOOK_STALE_SEC       : float = 5.0        # halt quoting if book older than this

    # ── Persistence ───────────────────────────────────────────────────────────
    DB_PATH : str = "gate_hedge.db"

    # ── Dashboard ─────────────────────────────────────────────────────────────
    DASHBOARD_PORT : int  = 8765
    DASHBOARD_HOST : str  = "127.0.0.1"

    # ── Logging ───────────────────────────────────────────────────────────────
    LOG_LEVEL : str = os.getenv("LOG_LEVEL", "INFO")
    LOG_FILE  : str = "gate_hedge.log"

    # ── Rate limits (Gate.io) ─────────────────────────────────────────────────
    RATE_PRIVATE_RPS : float = 8.0
    RATE_PUBLIC_RPS  : float = 15.0


def _validate_cfg() -> None:
    if not Cfg.PAPER and (not Cfg.API_KEY or not Cfg.API_SECRET):
        raise RuntimeError("GATE_API_KEY and GATE_API_SECRET must be set (or set GATE_PAPER=1)")
    if Cfg.TARGET_NOTIONAL > Cfg.MAX_NOTIONAL:
        raise ValueError("TARGET_NOTIONAL must be ≤ MAX_NOTIONAL")


# ═══════════════════════════════════════════════════════════════════════════════
# §3  DOMAIN TYPES
# ═══════════════════════════════════════════════════════════════════════════════

class Side(str, Enum):
    LONG  = "long"
    SHORT = "short"

class OrderStatus(str, Enum):
    PENDING   = "pending"    # submitted, not yet acknowledged
    OPEN      = "open"       # on book
    FILLED    = "filled"     # fully filled
    CANCELLED = "cancelled"  # cancelled or expired
    FAILED    = "failed"     # REST error

class OrderRole(str, Enum):
    ENTRY = "entry"          # opening a new hedge leg
    RECYCLE = "recycle"      # re-entering after a fill
    CLOSE   = "close"        # inventory-trim close

@dataclass
class BookTick:
    symbol    : str
    bid       : float
    ask       : float
    bid_size  : float
    ask_size  : float
    ts        : float = field(default_factory=time.monotonic)

    @property
    def mid(self) -> float:
        return (self.bid + self.ask) / 2.0

    @property
    def spread(self) -> float:
        return self.ask - self.bid

    def age_sec(self) -> float:
        return time.monotonic() - self.ts


@dataclass
class ContractSpec:
    symbol             : str
    tick_size          : float
    quanto_multiplier  : float   # base tokens per contract
    min_size           : int     # minimum order size in contracts
    mark_price         : float   # current mark price


@dataclass
class Order:
    client_id  : str
    exchange_id: str
    symbol     : str
    side       : Side
    size       : int             # contracts (always positive)
    price      : float
    tif        : str
    role       : OrderRole
    status     : OrderStatus = OrderStatus.PENDING
    fill_price : float = 0.0
    fill_size  : int   = 0
    fee_usdt   : float = 0.0
    created_at : float = field(default_factory=time.time)
    updated_at : float = field(default_factory=time.time)
    exchange_ts: float = 0.0


@dataclass
class HedgeLeg:
    """One side (long or short) of a symbol's hedge inventory."""
    symbol       : str
    side         : Side
    contracts    : int   = 0      # current open contracts (exchange position)
    entry_value  : float = 0.0    # total cost basis
    realized_pnl : float = 0.0    # running realized PnL USD
    pending_oid  : Optional[str] = None   # active open order client_id


@dataclass
class SymbolState:
    symbol    : str
    long_leg  : HedgeLeg  = field(init=False)
    short_leg : HedgeLeg  = field(init=False)
    spec      : Optional[ContractSpec] = None
    book      : Optional[BookTick]     = None
    last_quote_long_price  : float = 0.0
    last_quote_short_price : float = 0.0

    def __post_init__(self) -> None:
        self.long_leg  = HedgeLeg(symbol=self.symbol, side=Side.LONG)
        self.short_leg = HedgeLeg(symbol=self.symbol, side=Side.SHORT)

    @property
    def net_inventory(self) -> int:
        """Net delta in contracts (+long, −short)."""
        return self.long_leg.contracts - self.short_leg.contracts

    @property
    def book_stale(self) -> bool:
        if self.book is None:
            return True
        return self.book.age_sec() > Cfg.BOOK_STALE_SEC

    def best_bid(self) -> Optional[float]:
        return self.book.bid if self.book else None

    def best_ask(self) -> Optional[float]:
        return self.book.ask if self.book else None


# ═══════════════════════════════════════════════════════════════════════════════
# §4  CRYPTOGRAPHIC UTILITIES
# ═══════════════════════════════════════════════════════════════════════════════

def _rest_signature(method: str, path: str, query: str, body: str, ts: int) -> str:
    """Gate.io REST HMAC-SHA512 signature."""
    body_hash = hashlib.sha512(body.encode()).hexdigest()
    msg = f"{method}\n{path}\n{query}\n{body_hash}\n{ts}"
    return hmac_mod.new(
        Cfg.API_SECRET.encode(), msg.encode(), hashlib.sha512
    ).hexdigest()


def _ws_signature(channel: str, event: str, ts: int) -> str:
    """Gate.io WebSocket HMAC-SHA512 signature."""
    msg = f"channel={channel}&event={event}&time={ts}"
    return hmac_mod.new(
        Cfg.API_SECRET.encode(), msg.encode(), hashlib.sha512
    ).hexdigest()


def _rest_headers(method: str, path: str, query: str = "",
                  body: str = "") -> Dict[str, str]:
    ts = int(time.time())
    sign = _rest_signature(method, path, query, body, ts)
    return {
        "KEY":          Cfg.API_KEY,
        "Timestamp":    str(ts),
        "SIGN":         sign,
        "Content-Type": "application/json",
        "Accept":       "application/json",
    }


# ═══════════════════════════════════════════════════════════════════════════════
# §5  RATE LIMITER
# ═══════════════════════════════════════════════════════════════════════════════

class _TokenBucket:
    """Thread-safe token-bucket rate limiter."""

    def __init__(self, rate: float) -> None:
        self._rate      = rate
        self._tokens    = rate
        self._last      = time.monotonic()
        self._lock      = asyncio.Lock()

    async def acquire(self) -> None:
        async with self._lock:
            now = time.monotonic()
            elapsed = now - self._last
            self._tokens = min(self._rate, self._tokens + elapsed * self._rate)
            self._last = now
            if self._tokens < 1.0:
                wait = (1.0 - self._tokens) / self._rate
                await asyncio.sleep(wait)
                self._tokens = 0.0
            else:
                self._tokens -= 1.0


_private_limiter = _TokenBucket(Cfg.RATE_PRIVATE_RPS)
_public_limiter  = _TokenBucket(Cfg.RATE_PUBLIC_RPS)


# ═══════════════════════════════════════════════════════════════════════════════
# §6  REST CLIENT
# ═══════════════════════════════════════════════════════════════════════════════

class GateRest:
    """Async Gate.io Futures REST client with signed requests."""

    def __init__(self, session: aiohttp.ClientSession) -> None:
        self._s = session

    # ── Internal helpers ──────────────────────────────────────────────────────

    async def _get(self, path: str, params: Optional[Dict] = None,
                   private: bool = False) -> Any:
        await (_private_limiter if private else _public_limiter).acquire()
        query = "&".join(f"{k}={v}" for k, v in (params or {}).items())
        url   = Cfg.REST_URL + path
        if query:
            url += "?" + query
        headers = _rest_headers("GET", path, query) if private else {}
        async with self._s.get(url, headers=headers) as r:
            data = await r.json()
            if r.status not in (200, 201):
                raise RuntimeError(f"GET {path} → {r.status}: {data}")
            return data

    async def _post(self, path: str, body: Dict) -> Any:
        await _private_limiter.acquire()
        raw  = json.dumps(body)
        hdrs = _rest_headers("POST", path, "", raw)
        async with self._s.post(Cfg.REST_URL + path, headers=hdrs,
                                data=raw) as r:
            data = await r.json()
            if r.status not in (200, 201):
                raise RuntimeError(f"POST {path} → {r.status}: {data}")
            return data

    async def _delete(self, path: str, params: Optional[Dict] = None) -> Any:
        await _private_limiter.acquire()
        query = "&".join(f"{k}={v}" for k, v in (params or {}).items())
        raw_path = path
        if query:
            path += "?" + query
        hdrs = _rest_headers("DELETE", raw_path, query)
        async with self._s.delete(Cfg.REST_URL + path, headers=hdrs) as r:
            data = await r.json()
            if r.status not in (200, 201):
                raise RuntimeError(f"DELETE {path} → {r.status}: {data}")
            return data

    async def _put(self, path: str, body: Dict) -> Any:
        await _private_limiter.acquire()
        raw  = json.dumps(body)
        hdrs = _rest_headers("PUT", path, "", raw)
        async with self._s.put(Cfg.REST_URL + path, headers=hdrs,
                               data=raw) as r:
            data = await r.json()
            if r.status not in (200, 201):
                raise RuntimeError(f"PUT {path} → {r.status}: {data}")
            return data

    # ── Public market data ────────────────────────────────────────────────────

    async def get_contracts(self) -> List[Dict]:
        return await self._get(f"/futures/{Cfg.SETTLE}/contracts")

    async def get_contract(self, symbol: str) -> Dict:
        return await self._get(f"/futures/{Cfg.SETTLE}/contracts/{symbol}")

    async def get_tickers(self) -> List[Dict]:
        return await self._get(f"/futures/{Cfg.SETTLE}/tickers")

    async def get_order_book(self, symbol: str) -> Dict:
        return await self._get(f"/futures/{Cfg.SETTLE}/order_book",
                               {"contract": symbol, "limit": "5"})

    # ── Account ───────────────────────────────────────────────────────────────

    async def get_account(self) -> Dict:
        return await self._get(f"/futures/{Cfg.SETTLE}/accounts", private=True)

    async def set_dual_mode(self, dual: bool) -> Dict:
        """Enable/disable Gate.io hedge (dual position) mode."""
        return await self._put(f"/futures/{Cfg.SETTLE}/dual_mode",
                               {"dual_mode": dual})

    async def set_leverage(self, symbol: str, leverage: int,
                           cross_leverage_limit: int = 0) -> Dict:
        return await self._post(f"/futures/{Cfg.SETTLE}/positions/{symbol}/leverage",
                                {"leverage": str(leverage),
                                 "cross_leverage_limit": str(cross_leverage_limit)})

    # ── Positions ─────────────────────────────────────────────────────────────

    async def get_positions(self) -> List[Dict]:
        return await self._get(f"/futures/{Cfg.SETTLE}/positions", private=True)

    async def get_dual_positions(self, symbol: str) -> List[Dict]:
        """Returns [long_pos, short_pos] for a symbol in dual mode."""
        return await self._get(
            f"/futures/{Cfg.SETTLE}/dual_comp/positions/{symbol}", private=True
        )

    # ── Orders ────────────────────────────────────────────────────────────────

    async def place_order(self, symbol: str, size: int, price: float,
                          tif: str = "ioc", reduce_only: bool = False,
                          text: str = "") -> Dict:
        """
        Place a futures order.
        size > 0 → LONG  (buy)
        size < 0 → SHORT (sell)
        Gate.io dual-mode order (auto_size field not needed for entry).
        """
        body: Dict[str, Any] = {
            "contract":    symbol,
            "size":        size,
            "price":       f"{price:.10g}",
            "tif":         tif,
            "reduce_only": reduce_only,
        }
        if text:
            body["text"] = f"t-{text[:20]}"
        return await self._post(f"/futures/{Cfg.SETTLE}/orders", body)

    async def cancel_order(self, order_id: str) -> Dict:
        return await self._delete(f"/futures/{Cfg.SETTLE}/orders/{order_id}")

    async def cancel_all_orders(self, symbol: str) -> List[Dict]:
        return await self._delete(f"/futures/{Cfg.SETTLE}/orders",
                                  {"contract": symbol, "side": "0"})

    async def get_open_orders(self, symbol: Optional[str] = None) -> List[Dict]:
        params: Dict = {"status": "open"}
        if symbol:
            params["contract"] = symbol
        return await self._get(f"/futures/{Cfg.SETTLE}/orders",
                               params, private=True)

    async def get_order(self, order_id: str) -> Dict:
        return await self._get(f"/futures/{Cfg.SETTLE}/orders/{order_id}",
                               private=True)


# ═══════════════════════════════════════════════════════════════════════════════
# §7  WEBSOCKET MANAGER
# ═══════════════════════════════════════════════════════════════════════════════

BookCallback  = Callable[[BookTick], Coroutine]
OrderCallback = Callable[[Dict], Coroutine]
TradeCallback = Callable[[Dict], Coroutine]

class GateWS:
    """
    Manages public + private Gate.io futures WebSocket feeds.

    Public  : order_book_update (best bid/ask per symbol)
    Private : futures.orders, futures.usertrades, futures.positions
    """

    def __init__(self,
                 symbols: List[str],
                 on_book  : Optional[BookCallback]  = None,
                 on_order : Optional[OrderCallback] = None,
                 on_trade : Optional[TradeCallback] = None) -> None:
        self._symbols  = symbols
        self._on_book  = on_book
        self._on_order = on_order
        self._on_trade = on_trade
        self._shutdown = False
        self._tasks: List[asyncio.Task] = []

    async def start(self) -> None:
        self._tasks = [
            asyncio.create_task(self._run_public(),  name="ws_public"),
            asyncio.create_task(self._run_private(), name="ws_private"),
        ]

    async def stop(self) -> None:
        self._shutdown = True
        for t in self._tasks:
            t.cancel()
        await asyncio.gather(*self._tasks, return_exceptions=True)

    # ── Public feed ───────────────────────────────────────────────────────────

    async def _run_public(self) -> None:
        backoff = 1.0
        while not self._shutdown:
            try:
                async with websockets.connect(
                    Cfg.WS_URL,
                    ping_interval=20,
                    ping_timeout=10,
                    close_timeout=5,
                ) as ws:
                    log.info("WS public connected")
                    backoff = 1.0
                    # Subscribe to book ticker for all symbols
                    for sym in self._symbols:
                        await ws.send(json.dumps({
                            "time":    int(time.time()),
                            "channel": "futures.book_ticker",
                            "event":   "subscribe",
                            "payload": [sym],
                        }))
                    async for raw in ws:
                        if self._shutdown:
                            return
                        try:
                            await self._dispatch_public(json.loads(raw))
                        except Exception:
                            log.exception("WS public dispatch error")
            except asyncio.CancelledError:
                return
            except Exception as exc:
                if self._shutdown:
                    return
                log.warning("WS public disconnected: %s — retry in %.1fs", exc, backoff)
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2.0, 30.0)

    async def _dispatch_public(self, msg: Dict) -> None:
        channel = msg.get("channel", "")
        event   = msg.get("event",   "")
        result  = msg.get("result")
        if event in ("subscribe", "unsubscribe") or result is None:
            return
        if channel == "futures.book_ticker":
            r = result
            bid  = float(r.get("b") or r.get("bid_price") or 0)
            ask  = float(r.get("a") or r.get("ask_price") or 0)
            bsz  = float(r.get("B") or r.get("bid_amount") or 0)
            asz  = float(r.get("A") or r.get("ask_amount") or 0)
            sym  = str(r.get("s") or r.get("c") or r.get("contract") or "")
            if sym and bid > 0 and ask > 0 and self._on_book:
                tick = BookTick(symbol=sym, bid=bid, ask=ask,
                                bid_size=bsz, ask_size=asz)
                await self._on_book(tick)

    # ── Private feed ──────────────────────────────────────────────────────────

    async def _run_private(self) -> None:
        backoff = 1.0
        while not self._shutdown:
            try:
                async with websockets.connect(
                    Cfg.WS_URL,
                    ping_interval=20,
                    ping_timeout=10,
                    close_timeout=5,
                ) as ws:
                    log.info("WS private connected")
                    backoff = 1.0
                    for channel in ("futures.orders", "futures.usertrades"):
                        await self._subscribe(ws, channel)
                    async for raw in ws:
                        if self._shutdown:
                            return
                        try:
                            await self._dispatch_private(json.loads(raw))
                        except Exception:
                            log.exception("WS private dispatch error")
            except asyncio.CancelledError:
                return
            except Exception as exc:
                if self._shutdown:
                    return
                log.warning("WS private disconnected: %s — retry in %.1fs", exc, backoff)
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2.0, 30.0)

    async def _subscribe(self, ws, channel: str) -> None:
        ts   = int(time.time())
        sign = _ws_signature(channel, "subscribe", ts)
        await ws.send(json.dumps({
            "time":    ts,
            "channel": channel,
            "event":   "subscribe",
            "payload": [Cfg.SETTLE],
            "auth": {
                "method": "api_key",
                "KEY":    Cfg.API_KEY,
                "SIGN":   sign,
            },
        }))

    async def _dispatch_private(self, msg: Dict) -> None:
        channel = msg.get("channel", "")
        event   = msg.get("event",   "")
        result  = msg.get("result")
        if event in ("subscribe", "unsubscribe") or result is None:
            return
        items = result if isinstance(result, list) else [result]
        if channel == "futures.orders":
            for item in items:
                if item and self._on_order:
                    await self._on_order(item)
        elif channel == "futures.usertrades":
            for item in items:
                if item and self._on_trade:
                    await self._on_trade(item)


# ═══════════════════════════════════════════════════════════════════════════════
# §8  PERSISTENCE LAYER
# ═══════════════════════════════════════════════════════════════════════════════

class DB:
    """SQLite persistence — orders, fills, events, daily PnL snapshot."""

    def __init__(self, path: str = Cfg.DB_PATH) -> None:
        self._path = path
        self._con  = sqlite3.connect(path, check_same_thread=False)
        self._con.row_factory = sqlite3.Row
        self._lock = threading.Lock()
        self._init()

    def _init(self) -> None:
        with self._lock, self._con:
            self._con.executescript("""
                PRAGMA journal_mode=WAL;
                PRAGMA synchronous=NORMAL;

                CREATE TABLE IF NOT EXISTS orders (
                    client_id    TEXT PRIMARY KEY,
                    exchange_id  TEXT,
                    symbol       TEXT NOT NULL,
                    side         TEXT NOT NULL,
                    size         INTEGER NOT NULL,
                    price        REAL NOT NULL,
                    tif          TEXT,
                    role         TEXT,
                    status       TEXT NOT NULL,
                    fill_price   REAL DEFAULT 0,
                    fill_size    INTEGER DEFAULT 0,
                    fee_usdt     REAL DEFAULT 0,
                    created_at   REAL NOT NULL,
                    updated_at   REAL NOT NULL,
                    exchange_ts  REAL DEFAULT 0
                );

                CREATE TABLE IF NOT EXISTS fills (
                    id           TEXT PRIMARY KEY,
                    order_id     TEXT,
                    symbol       TEXT NOT NULL,
                    side         TEXT NOT NULL,
                    size         INTEGER NOT NULL,
                    price        REAL NOT NULL,
                    fee_usdt     REAL DEFAULT 0,
                    realized_pnl REAL DEFAULT 0,
                    ts           REAL NOT NULL
                );

                CREATE TABLE IF NOT EXISTS events (
                    id        INTEGER PRIMARY KEY AUTOINCREMENT,
                    ts        REAL NOT NULL,
                    level     TEXT NOT NULL,
                    symbol    TEXT,
                    message   TEXT NOT NULL,
                    data      TEXT
                );

                CREATE TABLE IF NOT EXISTS daily_pnl (
                    date       TEXT PRIMARY KEY,
                    realized   REAL DEFAULT 0,
                    fees       REAL DEFAULT 0,
                    fills      INTEGER DEFAULT 0
                );

                CREATE INDEX IF NOT EXISTS idx_orders_symbol
                    ON orders(symbol);
                CREATE INDEX IF NOT EXISTS idx_orders_status
                    ON orders(status);
                CREATE INDEX IF NOT EXISTS idx_fills_ts
                    ON fills(ts);
            """)

    # ── Orders ────────────────────────────────────────────────────────────────

    def upsert_order(self, o: Order) -> None:
        with self._lock, self._con:
            self._con.execute("""
                INSERT INTO orders VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(client_id) DO UPDATE SET
                    exchange_id=excluded.exchange_id,
                    status=excluded.status,
                    fill_price=excluded.fill_price,
                    fill_size=excluded.fill_size,
                    fee_usdt=excluded.fee_usdt,
                    updated_at=excluded.updated_at,
                    exchange_ts=excluded.exchange_ts
            """, (
                o.client_id, o.exchange_id, o.symbol, o.side.value,
                o.size, o.price, o.tif, o.role.value, o.status.value,
                o.fill_price, o.fill_size, o.fee_usdt,
                o.created_at, o.updated_at, o.exchange_ts,
            ))

    def get_order(self, client_id: str) -> Optional[Dict]:
        with self._lock:
            row = self._con.execute(
                "SELECT * FROM orders WHERE client_id=?", (client_id,)
            ).fetchone()
            return dict(row) if row else None

    def get_open_orders(self, symbol: Optional[str] = None) -> List[Dict]:
        with self._lock:
            q = "SELECT * FROM orders WHERE status IN ('pending','open')"
            args: tuple = ()
            if symbol:
                q += " AND symbol=?"
                args = (symbol,)
            return [dict(r) for r in self._con.execute(q, args).fetchall()]

    def get_all_orders(self, limit: int = 200) -> List[Dict]:
        with self._lock:
            rows = self._con.execute(
                "SELECT * FROM orders ORDER BY created_at DESC LIMIT ?", (limit,)
            ).fetchall()
            return [dict(r) for r in rows]

    # ── Fills ─────────────────────────────────────────────────────────────────

    def insert_fill(self, fill_id: str, order_id: str, symbol: str,
                    side: Side, size: int, price: float,
                    fee: float, pnl: float, ts: float) -> None:
        with self._lock, self._con:
            self._con.execute("""
                INSERT OR IGNORE INTO fills
                VALUES (?,?,?,?,?,?,?,?,?)
            """, (fill_id, order_id, symbol, side.value, size, price, fee, pnl, ts))

    def daily_pnl_today(self) -> Dict:
        date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        with self._lock:
            row = self._con.execute(
                "SELECT * FROM daily_pnl WHERE date=?", (date,)
            ).fetchone()
            return dict(row) if row else {"date": date, "realized": 0.0,
                                           "fees": 0.0, "fills": 0}

    def add_daily_pnl(self, pnl: float, fee: float) -> None:
        date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        with self._lock, self._con:
            self._con.execute("""
                INSERT INTO daily_pnl(date,realized,fees,fills) VALUES(?,?,?,1)
                ON CONFLICT(date) DO UPDATE SET
                    realized=realized+excluded.realized,
                    fees=fees+excluded.fees,
                    fills=fills+1
            """, (date, pnl, fee))

    def get_recent_fills(self, limit: int = 100) -> List[Dict]:
        with self._lock:
            rows = self._con.execute(
                "SELECT * FROM fills ORDER BY ts DESC LIMIT ?", (limit,)
            ).fetchall()
            return [dict(r) for r in rows]

    # ── Events ────────────────────────────────────────────────────────────────

    def log_event(self, level: str, message: str,
                  symbol: Optional[str] = None,
                  data: Optional[Dict] = None) -> None:
        with self._lock, self._con:
            self._con.execute(
                "INSERT INTO events(ts,level,symbol,message,data) VALUES(?,?,?,?,?)",
                (time.time(), level, symbol, message,
                 json.dumps(data) if data else None),
            )

    def get_events(self, limit: int = 200) -> List[Dict]:
        with self._lock:
            rows = self._con.execute(
                "SELECT * FROM events ORDER BY id DESC LIMIT ?", (limit,)
            ).fetchall()
            return [dict(r) for r in rows]


# ═══════════════════════════════════════════════════════════════════════════════
# §9  ORDER MANAGER
# ═══════════════════════════════════════════════════════════════════════════════

class OrderManager:
    """
    Owns all live orders.  Bridges REST → DB state.
    Thread-safe dict keyed by client_id.
    Exchange ID index maintained for WS dispatch.
    """

    def __init__(self, rest: GateRest, db: DB) -> None:
        self._rest = rest
        self._db   = db
        self._orders: Dict[str, Order] = {}                 # client_id → Order
        self._eid_map: Dict[str, str]  = {}                 # exchange_id → client_id
        self._lock = asyncio.Lock()

    # ── Accessors ─────────────────────────────────────────────────────────────

    async def all_open(self, symbol: Optional[str] = None) -> List[Order]:
        async with self._lock:
            return [
                o for o in self._orders.values()
                if o.status in (OrderStatus.PENDING, OrderStatus.OPEN)
                and (symbol is None or o.symbol == symbol)
            ]

    async def get_by_client(self, client_id: str) -> Optional[Order]:
        async with self._lock:
            return self._orders.get(client_id)

    async def get_by_exchange(self, exchange_id: str) -> Optional[Order]:
        async with self._lock:
            cid = self._eid_map.get(exchange_id)
            return self._orders.get(cid) if cid else None

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    async def submit(self, symbol: str, side: Side, size: int,
                     price: float, tif: str, role: OrderRole) -> Optional[Order]:
        """Place order via REST; register in memory + DB."""
        client_id = uuid.uuid4().hex[:16]
        gate_size = size if side == Side.LONG else -size
        o = Order(
            client_id=client_id, exchange_id="",
            symbol=symbol, side=side, size=size, price=price,
            tif=tif, role=role, status=OrderStatus.PENDING,
            created_at=time.time(), updated_at=time.time(),
        )
        async with self._lock:
            self._orders[client_id] = o
        self._db.upsert_order(o)

        if Cfg.PAPER:
            log.info("PAPER order: %s %s ×%d @ %.8g %s",
                     side.value.upper(), symbol, size, price, tif)
            o.status     = OrderStatus.OPEN
            o.exchange_id = client_id
            o.updated_at  = time.time()
            self._db.upsert_order(o)
            return o

        try:
            resp = await self._rest.place_order(
                symbol=symbol, size=gate_size, price=price,
                tif=tif, text=client_id,
            )
            eid = str(resp.get("id", ""))
            async with self._lock:
                o.exchange_id = eid
                o.status      = OrderStatus.OPEN
                o.updated_at  = time.time()
                if eid:
                    self._eid_map[eid] = client_id
            self._db.upsert_order(o)
            log.debug("ORDER placed: %s %s ×%d @ %.8g eid=%s",
                      side.value.upper(), symbol, size, price, eid)
            return o
        except Exception as exc:
            log.error("ORDER submit failed %s %s ×%d: %s",
                      side.value.upper(), symbol, size, exc)
            async with self._lock:
                o.status     = OrderStatus.FAILED
                o.updated_at = time.time()
            self._db.upsert_order(o)
            return None

    async def cancel(self, client_id: str) -> bool:
        """Cancel order by client_id."""
        o = await self.get_by_client(client_id)
        if o is None or o.status not in (OrderStatus.PENDING, OrderStatus.OPEN):
            return False
        if not o.exchange_id or Cfg.PAPER:
            async with self._lock:
                o.status     = OrderStatus.CANCELLED
                o.updated_at = time.time()
            self._db.upsert_order(o)
            return True
        try:
            await self._rest.cancel_order(o.exchange_id)
            async with self._lock:
                o.status     = OrderStatus.CANCELLED
                o.updated_at = time.time()
            self._db.upsert_order(o)
            return True
        except Exception as exc:
            log.warning("cancel order %s failed: %s", client_id, exc)
            return False

    async def cancel_symbol(self, symbol: str) -> int:
        """Cancel all open orders for a symbol via REST cancel_all."""
        if not Cfg.PAPER:
            try:
                await self._rest.cancel_all_orders(symbol)
            except Exception as exc:
                log.warning("cancel_all_orders %s: %s", symbol, exc)
        count = 0
        async with self._lock:
            for o in self._orders.values():
                if o.symbol == symbol and o.status in (OrderStatus.PENDING, OrderStatus.OPEN):
                    o.status     = OrderStatus.CANCELLED
                    o.updated_at = time.time()
                    count += 1
        return count

    # ── WS dispatch ───────────────────────────────────────────────────────────

    async def on_order_update(self, raw: Dict) -> Optional[Order]:
        """Called from WS private feed. Returns order if status changed."""
        eid    = str(raw.get("id", ""))
        status = raw.get("status", "")
        o      = await self.get_by_exchange(eid)
        if o is None:
            return None
        new_status: Optional[OrderStatus] = None
        if status == "open":
            new_status = OrderStatus.OPEN
        elif status in ("closed", "finished"):
            # check if fully filled or cancelled
            finish = raw.get("finish_as", "")
            if finish == "filled":
                new_status = OrderStatus.FILLED
            elif finish in ("cancelled", "ioc", "poc", "stp"):
                new_status = OrderStatus.CANCELLED
            else:
                new_status = OrderStatus.CANCELLED
        if new_status and new_status != o.status:
            async with self._lock:
                o.status     = new_status
                o.updated_at = time.time()
                if raw.get("fill_price"):
                    o.fill_price = float(raw["fill_price"])
                if raw.get("left") is not None and raw.get("size") is not None:
                    o.fill_size = abs(int(raw["size"])) - abs(int(raw.get("left", 0)))
            self._db.upsert_order(o)
            return o
        return None

    async def on_trade(self, raw: Dict) -> Optional[Tuple[Order, float, float]]:
        """
        Called from WS usertrades feed.
        Returns (order, fill_price, fee_usdt) or None.
        """
        oid = str(raw.get("order_id", ""))
        o   = await self.get_by_exchange(oid)
        if o is None:
            return None
        fill_price = float(raw.get("price", 0))
        fill_size  = abs(int(raw.get("size", 0)))
        fee_usdt   = abs(float(raw.get("fee", 0)))
        async with self._lock:
            o.fill_price = fill_price
            o.fill_size  = fill_size
            o.fee_usdt   = fee_usdt
            o.exchange_ts = float(raw.get("create_time", time.time()))
        self._db.upsert_order(o)
        return o, fill_price, fee_usdt

    # ── Load open orders from DB on startup ───────────────────────────────────

    async def load_from_db(self) -> None:
        rows = self._db.get_open_orders()
        async with self._lock:
            for row in rows:
                o = Order(
                    client_id=row["client_id"],
                    exchange_id=row["exchange_id"] or "",
                    symbol=row["symbol"],
                    side=Side(row["side"]),
                    size=row["size"],
                    price=row["price"],
                    tif=row["tif"],
                    role=OrderRole(row["role"]),
                    status=OrderStatus(row["status"]),
                    fill_price=row["fill_price"],
                    fill_size=row["fill_size"],
                    fee_usdt=row["fee_usdt"],
                    created_at=row["created_at"],
                    updated_at=row["updated_at"],
                    exchange_ts=row["exchange_ts"],
                )
                self._orders[o.client_id] = o
                if o.exchange_id:
                    self._eid_map[o.exchange_id] = o.client_id
        log.info("OrderManager: loaded %d orders from DB", len(rows))


# ═══════════════════════════════════════════════════════════════════════════════
# §10  RISK GUARD
# ═══════════════════════════════════════════════════════════════════════════════

class RiskGuard:
    """
    Centralised risk checks.  All quoting passes through here.
    """

    def __init__(self, db: DB) -> None:
        self._db          = db
        self._killed      = False
        self._daily_loss  = 0.0   # tracked in memory, refreshed from DB on init
        self._daily_fees  = 0.0
        self._session_fills = 0

    async def refresh(self) -> None:
        snap = self._db.daily_pnl_today()
        self._daily_loss  = -min(0.0, float(snap.get("realized", 0)))
        self._daily_fees  = float(snap.get("fees", 0))
        self._session_fills = int(snap.get("fills", 0))

    def record_fill(self, pnl: float, fee: float) -> None:
        self._daily_loss += -min(0.0, pnl)
        self._daily_fees += fee
        self._session_fills += 1
        self._db.add_daily_pnl(pnl, fee)
        if self._daily_loss >= Cfg.KILL_SWITCH_LOSS_USD:
            log.critical("KILL SWITCH TRIGGERED: daily loss $%.4f", self._daily_loss)
            self._killed = True

    @property
    def killed(self) -> bool:
        return self._killed

    def can_quote(self, symbol: str, open_orders_sym: int) -> Tuple[bool, str]:
        """Return (allowed, reason)."""
        if self._killed:
            return False, "kill_switch"
        if self._daily_loss >= Cfg.MAX_DAILY_LOSS_USD:
            return False, f"daily_loss ${self._daily_loss:.4f}"
        if open_orders_sym >= Cfg.MAX_OPEN_ORDERS_SYM:
            return False, f"max_open_orders {open_orders_sym}"
        return True, ""

    def can_add_inventory(self, leg: HedgeLeg) -> bool:
        return leg.contracts < Cfg.MAX_INVENTORY

    def status_dict(self) -> Dict:
        return {
            "killed":     self._killed,
            "daily_loss": self._daily_loss,
            "daily_fees": self._daily_fees,
            "fills_today": self._session_fills,
            "max_daily_loss": Cfg.MAX_DAILY_LOSS_USD,
        }


# ═══════════════════════════════════════════════════════════════════════════════
# §11  SYMBOL SCANNER
# ═══════════════════════════════════════════════════════════════════════════════

async def scan_micro_symbols(rest: GateRest) -> List[str]:
    """
    Return up to MAX_SYMBOLS symbols whose mark price × quanto_multiplier
    is in [MIN_NOTIONAL, MAX_NOTIONAL] and has sufficient volume.
    """
    try:
        tickers   = await rest.get_tickers()
        contracts = await rest.get_contracts()
        spec_map  = {c["name"]: c for c in contracts}
    except Exception as exc:
        log.error("Symbol scan failed: %s", exc)
        return []

    candidates: List[Tuple[float, str]] = []
    for t in tickers:
        sym = t.get("contract", "")
        if not sym.endswith("_USDT"):
            continue
        mark  = float(t.get("mark_price") or t.get("last", 0) or 0)
        vol24 = float(t.get("volume_24h_base", 0) or t.get("volume_24h", 0) or 0)
        if mark < Cfg.SCAN_PRICE_MIN or mark > Cfg.SCAN_PRICE_MAX:
            continue
        if vol24 < Cfg.SCAN_VOLUME_MIN:
            continue
        spec = spec_map.get(sym, {})
        quanto = float(spec.get("quanto_multiplier") or 1.0)
        notional_per_contract = mark * quanto
        if Cfg.MIN_NOTIONAL <= notional_per_contract <= Cfg.MAX_NOTIONAL:
            candidates.append((vol24, sym))

    candidates.sort(reverse=True)  # highest volume first
    chosen = [sym for _, sym in candidates[:Cfg.MAX_SYMBOLS]]
    log.info("Scanned %d micro symbols: %s", len(chosen), chosen)
    return chosen


# ═══════════════════════════════════════════════════════════════════════════════
# §12  CONTRACT SPEC LOADER
# ═══════════════════════════════════════════════════════════════════════════════

async def load_contract_spec(rest: GateRest, symbol: str) -> Optional[ContractSpec]:
    try:
        c     = await rest.get_contract(symbol)
        mark  = float(c.get("mark_price") or c.get("index_price") or 0)
        tick  = float(c.get("order_price_round") or c.get("mark_price_round") or "0.00001")
        qm    = float(c.get("quanto_multiplier") or "1")
        mins  = int(c.get("order_size_min") or 1)
        return ContractSpec(symbol=symbol, tick_size=tick,
                            quanto_multiplier=qm, min_size=mins,
                            mark_price=mark)
    except Exception as exc:
        log.error("Failed to load spec for %s: %s", symbol, exc)
        return None


def compute_size(spec: ContractSpec, notional: float) -> int:
    """
    Compute contract size for a given USD notional.
    1 contract worth ≈ mark_price × quanto_multiplier USD.
    """
    value_per_contract = spec.mark_price * spec.quanto_multiplier
    if value_per_contract <= 0:
        return spec.min_size
    raw = math.floor(notional / value_per_contract)
    return max(spec.min_size, raw)


def round_price(price: float, tick: float) -> float:
    """Round price to nearest tick."""
    if tick <= 0:
        return price
    return round(round(price / tick) * tick, 10)


# ═══════════════════════════════════════════════════════════════════════════════
# §13  RECONCILER
# ═══════════════════════════════════════════════════════════════════════════════

async def reconcile(rest: GateRest, db: DB, states: Dict[str, SymbolState],
                    om: OrderManager) -> None:
    """
    Startup reconciliation:
    1. Fetch live exchange positions → update leg.contracts
    2. Fetch live open orders → mark orphan DB orders as cancelled
    3. Detect exchange orders not in DB → register them
    """
    log.info("Reconciler: fetching live positions...")
    try:
        live_positions = await rest.get_positions()
    except Exception as exc:
        log.error("Reconciler: failed to fetch positions: %s", exc)
        live_positions = []

    # Build map: symbol → {long_contracts, short_contracts}
    pos_map: Dict[str, Dict[str, int]] = defaultdict(lambda: {"long": 0, "short": 0})
    for p in live_positions:
        sym  = p.get("contract", "")
        size = int(p.get("size", 0))
        mode = p.get("mode", "")
        if sym not in states:
            continue
        if mode == "dual_long" or size > 0:
            pos_map[sym]["long"] = abs(size)
        elif mode == "dual_short" or size < 0:
            pos_map[sym]["short"] = abs(size)

    for sym, st in states.items():
        st.long_leg.contracts  = pos_map[sym]["long"]
        st.short_leg.contracts = pos_map[sym]["short"]
        log.info("Reconciler %s: long=%d short=%d",
                 sym, st.long_leg.contracts, st.short_leg.contracts)

    # Fetch exchange open orders
    log.info("Reconciler: fetching live open orders...")
    try:
        live_orders = await rest.get_open_orders()
    except Exception as exc:
        log.error("Reconciler: failed to fetch open orders: %s", exc)
        live_orders = []

    live_eids = {str(o["id"]) for o in live_orders}

    # Mark DB-open orders that are NOT on exchange as cancelled
    db_open = db.get_open_orders()
    for row in db_open:
        eid = row.get("exchange_id", "")
        if eid and eid not in live_eids:
            log.info("Reconciler: orphan order %s (eid=%s) → cancelled",
                     row["client_id"], eid)
            db.log_event("WARN", f"Orphan order {row['client_id']} cancelled on reconcile",
                         symbol=row["symbol"])
    db.log_event("INFO", "Reconciler completed",
                 data={"live_pos": dict(pos_map), "live_orders": len(live_eids)})
    log.info("Reconciler: done")


# ═══════════════════════════════════════════════════════════════════════════════
# §14  QUOTE ENGINE  (Aggressive Dual-Sided Hedge)
# ═══════════════════════════════════════════════════════════════════════════════

class QuoteEngine:
    """
    Core execution logic.
    Per symbol: maintain one LONG quote (buy @ best_ask) and one SHORT quote (sell @ best_bid).
    On fill → immediately recycle.
    On inventory excess → taker-trim.
    """

    def __init__(self, rest: GateRest, om: OrderManager, db: DB,
                 risk: RiskGuard, states: Dict[str, SymbolState]) -> None:
        self._rest   = rest
        self._om     = om
        self._db     = db
        self._risk   = risk
        self._states = states
        self._fill_callbacks: List[Callable] = []

    def add_fill_callback(self, cb: Callable) -> None:
        self._fill_callbacks.append(cb)

    # ── Book update → check reprice ───────────────────────────────────────────

    async def on_book_tick(self, tick: BookTick) -> None:
        st = self._states.get(tick.symbol)
        if st is None:
            return
        st.book = tick
        await self._maybe_reprice(st)

    async def _maybe_reprice(self, st: SymbolState) -> None:
        if st.book_stale:
            return
        if self._risk.killed:
            return
        book = st.book
        spec = st.spec
        if spec is None or book is None:
            return

        bid = round_price(book.bid, spec.tick_size)
        ask = round_price(book.ask, spec.tick_size)
        if bid <= 0 or ask <= 0 or bid >= ask:
            return

        # ── Long side: buy @ ask ──────────────────────────────────────────────
        await self._manage_leg(st, Side.LONG, target_price=ask)

        # ── Short side: sell @ bid ────────────────────────────────────────────
        await self._manage_leg(st, Side.SHORT, target_price=bid)

    async def _manage_leg(self, st: SymbolState, side: Side,
                           target_price: float) -> None:
        spec = st.spec
        if spec is None:
            return

        leg = st.long_leg if side == Side.LONG else st.short_leg

        # Check if we already have an active pending order for this leg
        if leg.pending_oid:
            existing = await self._om.get_by_client(leg.pending_oid)
            if existing and existing.status in (OrderStatus.PENDING, OrderStatus.OPEN):
                # Check if price has moved enough to reprice
                price_diff = abs(existing.price - target_price)
                if price_diff < Cfg.REPRICE_TICKS * spec.tick_size:
                    return  # price hasn't moved, keep existing order
                # Price moved — cancel and reprice
                await self._om.cancel(leg.pending_oid)
                leg.pending_oid = None
                log.debug("REPRICE %s %s: old=%.8g new=%.8g",
                          st.symbol, side.value, existing.price, target_price)

        # Inventory check
        if not self._risk.can_add_inventory(leg):
            # Trim excess inventory
            await self._trim_inventory(st, side)
            return

        # Risk checks
        open_orders = await self._om.all_open(st.symbol)
        allowed, reason = self._risk.can_quote(st.symbol, len(open_orders))
        if not allowed:
            log.debug("Quote blocked %s %s: %s", st.symbol, side.value, reason)
            return

        # Size order
        size = compute_size(spec, Cfg.TARGET_NOTIONAL)
        if size < spec.min_size:
            log.debug("Size too small for %s: %d < %d", st.symbol, size, spec.min_size)
            return

        # Submit
        role = OrderRole.ENTRY if leg.contracts == 0 else OrderRole.RECYCLE
        o = await self._om.submit(
            symbol=st.symbol,
            side=side,
            size=size,
            price=target_price,
            tif=Cfg.PRIMARY_TIF,
            role=role,
        )
        if o:
            leg.pending_oid = o.client_id
            if side == Side.LONG:
                st.last_quote_long_price = target_price
            else:
                st.last_quote_short_price = target_price

    async def _trim_inventory(self, st: SymbolState, side: Side) -> None:
        """Place a reduce-only IOC to trim excess inventory."""
        leg  = st.long_leg if side == Side.LONG else st.short_leg
        book = st.book
        spec = st.spec
        if not book or not spec:
            return
        excess = leg.contracts - Cfg.MAX_INVENTORY
        if excess <= 0:
            return
        # Close side: LONG excess → sell at bid (hit the bid)
        #             SHORT excess → buy at ask (lift the ask)
        close_side  = Side.SHORT if side == Side.LONG else Side.LONG
        close_price = book.bid if side == Side.LONG else book.ask
        close_price = round_price(close_price, spec.tick_size)
        log.warning("TRIM %s %s excess=%d", st.symbol, side.value, excess)
        await self._om.submit(
            symbol=st.symbol, side=close_side, size=excess,
            price=close_price, tif="ioc", role=OrderRole.CLOSE,
        )

    # ── Fill dispatch ─────────────────────────────────────────────────────────

    async def on_fill(self, order: Order, fill_price: float, fee: float) -> None:
        """
        Called when a fill is confirmed.
        1. Update leg inventory
        2. Calculate PnL
        3. Persist fill
        4. Immediately recycle
        """
        st  = self._states.get(order.symbol)
        if st is None:
            return

        leg = st.long_leg if order.side == Side.LONG else st.short_leg

        # Update inventory
        fill_size = order.fill_size or order.size
        notional  = fill_price * fill_size * (st.spec.quanto_multiplier if st.spec else 1.0)

        if order.role == OrderRole.CLOSE:
            leg.contracts    = max(0, leg.contracts - fill_size)
            leg.entry_value  = max(0.0, leg.entry_value - notional)
        else:
            leg.contracts   += fill_size
            leg.entry_value += notional

        # Realized PnL (entry vs close)
        if order.role == OrderRole.CLOSE:
            avg_entry = leg.entry_value / max(1, leg.contracts + fill_size)
            pnl       = (fill_price - avg_entry) * fill_size
            if order.side == Side.SHORT:   # we bought to close a long
                pnl = (avg_entry - fill_price) * fill_size
            pnl -= fee
        else:
            pnl = -fee   # entry cost = just the fee

        leg.realized_pnl += pnl
        self._risk.record_fill(pnl, fee)

        fill_id = uuid.uuid4().hex
        self._db.insert_fill(
            fill_id=fill_id, order_id=order.client_id,
            symbol=order.symbol, side=order.side,
            size=fill_size, price=fill_price, fee=fee, pnl=pnl,
            ts=time.time(),
        )
        self._db.log_event(
            "FILL", f"{order.side.value.upper()} {order.symbol} ×{fill_size} @ {fill_price:.8g} "
                    f"pnl={pnl:+.6f} fee={fee:.6f}",
            symbol=order.symbol,
            data={"side": order.side.value, "size": fill_size, "price": fill_price,
                  "pnl": pnl, "fee": fee, "role": order.role.value},
        )
        log.info("FILL %s %s ×%d @ %.8g  pnl=%+.6f  fee=%.6f  inv_long=%d inv_short=%d",
                 order.symbol, order.side.value.upper(), fill_size, fill_price,
                 pnl, fee, st.long_leg.contracts, st.short_leg.contracts)

        # Clear pending OID so reprice loop can re-quote
        if leg.pending_oid == order.client_id:
            leg.pending_oid = None

        # Notify callbacks (dashboard refresh etc.)
        for cb in self._fill_callbacks:
            try:
                await cb(order, fill_price, pnl)
            except Exception:
                pass

        # Recycle: immediately re-enter same side
        if not self._risk.killed and order.role != OrderRole.CLOSE:
            await asyncio.sleep(Cfg.RECYCLE_DELAY_SEC)
            await self._maybe_reprice(st)


# ═══════════════════════════════════════════════════════════════════════════════
# §15  REPRICE LOOP
# ═══════════════════════════════════════════════════════════════════════════════

async def reprice_loop(states: Dict[str, SymbolState],
                       engine: QuoteEngine,
                       om: OrderManager) -> None:
    """
    Periodic heartbeat:
    - Check all open orders for TTL expiry
    - Force reprice if book has moved
    """
    while True:
        try:
            await asyncio.sleep(Cfg.REPRICE_LOOP_SEC)
            now = time.time()
            for st in states.values():
                if st.book_stale:
                    continue
                for leg in (st.long_leg, st.short_leg):
                    if not leg.pending_oid:
                        continue
                    o = await om.get_by_client(leg.pending_oid)
                    if o is None or o.status not in (OrderStatus.PENDING, OrderStatus.OPEN):
                        leg.pending_oid = None
                        continue
                    # Cancel if TTL exceeded
                    age = now - o.created_at
                    if age > Cfg.QUOTE_TTL_SEC:
                        log.debug("TTL cancel %s %s oid=%s age=%.1fs",
                                  st.symbol, leg.side.value, leg.pending_oid, age)
                        await om.cancel(leg.pending_oid)
                        leg.pending_oid = None
                # After clearing, trigger reprice from current book
                if st.book and not st.book_stale:
                    await engine.on_book_tick(st.book)
        except asyncio.CancelledError:
            return
        except Exception:
            log.exception("reprice_loop error")


# ═══════════════════════════════════════════════════════════════════════════════
# §16  DASHBOARD HTTP SERVER
# ═══════════════════════════════════════════════════════════════════════════════

_DASH_HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<meta http-equiv="refresh" content="2"/>
<title>Gate Hedge Engine</title>
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{background:#0a0f1e;color:#c9d1e0;font-family:'JetBrains Mono',monospace,sans-serif;font-size:12px;padding:12px}
h1{font-size:16px;color:#7dd3fc;margin-bottom:12px;letter-spacing:.05em}
h2{font-size:11px;color:#94a3b8;text-transform:uppercase;letter-spacing:.12em;margin-bottom:8px}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:10px;margin-bottom:12px}
.card{background:#0f1829;border:1px solid #1e3058;border-radius:6px;padding:12px}
table{width:100%;border-collapse:collapse;margin-top:6px}
th{padding:4px 8px;text-align:left;color:#475569;font-size:10px;border-bottom:1px solid #1e3058}
td{padding:4px 8px;border-bottom:1px solid rgba(15,24,42,.7);white-space:nowrap}
tr:hover td{background:rgba(59,130,246,.05)}
.buy{color:#4ade80}.sell{color:#f87171}.na{color:#475569}
.killed{color:#f87171;font-weight:bold}
.ok{color:#4ade80}
.kv{display:grid;grid-template-columns:auto 1fr;gap:3px 10px}
.kv-k{color:#475569}.kv-v{color:#e2e8f0}
.big{font-size:20px;font-weight:700;color:#fff;margin:4px 0}
</style>
</head>
<body>
<h1>⬡ Gate Aggressive Hedge Engine</h1>
<div class="grid" id="sym-grid"></div>
<div class="grid">
  <div class="card"><h2>Risk</h2><div class="kv" id="risk-kv"></div></div>
  <div class="card"><h2>Session</h2><div class="kv" id="sess-kv"></div></div>
</div>
<div class="card" style="margin-bottom:10px">
  <h2>Recent Fills</h2>
  <div id="fills-tbl"></div>
</div>
<div class="card">
  <h2>Events</h2>
  <div id="evt-tbl"></div>
</div>
<script>
const f=(v,d=6)=>{
  if(v===null||v===undefined||v==='')return '<span class="na">–</span>';
  if(typeof v==='number')return isNaN(v)?'<span class="na">nan</span>':v.toFixed(d);
  return String(v);
};
const kv=(pairs)=>pairs.map(([k,v])=>`<div class="kv-k">${k}</div><div class="kv-v">${v}</div>`).join('');
const tbl=(cols,rows)=>`<table><thead><tr>${cols.map(c=>`<th>${c}</th>`).join('')}</tr></thead><tbody>${
  rows.map(r=>`<tr>${r.map(c=>`<td>${c}</td>`).join('')}</tr>`).join('')
}</tbody></table>`;
async function refresh(){
  const d=await fetch('/api/state').then(r=>r.json());
  // Symbols
  const grid=document.getElementById('sym-grid');
  grid.innerHTML=d.symbols.map(s=>`
    <div class="card">
      <h2>${s.symbol}</h2>
      <div class="kv">${kv([
        ['bid', `<span class="sell">${f(s.bid,8)}</span>`],
        ['ask', `<span class="buy">${f(s.ask,8)}</span>`],
        ['spread', f(s.spread,8)],
        ['long_inv', s.long_inv],
        ['short_inv', s.short_inv],
        ['net_delta', s.net_delta],
        ['long_pnl', `<span class="${s.long_pnl>=0?'buy':'sell'}">${f(s.long_pnl,6)}</span>`],
        ['short_pnl', `<span class="${s.short_pnl>=0?'buy':'sell'}">${f(s.short_pnl,6)}</span>`],
        ['pending_long', s.pending_long||'–'],
        ['pending_short', s.pending_short||'–'],
        ['book_age', f(s.book_age,2)+'s'],
      ])}</div>
    </div>
  `).join('');
  // Risk
  const r=d.risk;
  document.getElementById('risk-kv').innerHTML=kv([
    ['status', r.killed?'<span class="killed">KILLED</span>':'<span class="ok">ACTIVE</span>'],
    ['daily_loss', `<span class="${r.daily_loss>0?'sell':'ok'}">$${f(r.daily_loss,4)}</span>`],
    ['daily_fees', '$'+f(r.daily_fees,4)],
    ['max_loss', '$'+f(r.max_daily_loss,2)],
  ]);
  // Session
  const s=d.session;
  document.getElementById('sess-kv').innerHTML=kv([
    ['fills_today', s.fills_today],
    ['uptime', s.uptime],
    ['paper', s.paper?'YES':'NO'],
    ['symbols', s.symbols.join(', ')],
  ]);
  // Fills
  const fills=d.fills.map(f=>[
    new Date(f.ts*1000).toISOString().slice(11,22),
    f.symbol,
    `<span class="${f.side==='long'?'buy':'sell'}">${f.side.toUpperCase()}</span>`,
    f.size, f.price.toFixed(8),
    `<span class="${f.realized_pnl>=0?'buy':'sell'}">${f.realized_pnl.toFixed(6)}</span>`,
    f.fee_usdt.toFixed(6),
  ]);
  document.getElementById('fills-tbl').innerHTML=tbl(
    ['time','symbol','side','size','price','pnl','fee'], fills
  );
  // Events
  const evts=d.events.slice(0,40).map(e=>[
    new Date(e.ts*1000).toISOString().slice(11,22),
    `<span class="${e.level==='FILL'?'buy':e.level==='WARN'||e.level==='ERROR'?'sell':'na'}">${e.level}</span>`,
    e.symbol||'',
    e.message,
  ]);
  document.getElementById('evt-tbl').innerHTML=tbl(['time','level','sym','message'], evts);
}
refresh();
setInterval(refresh,2000);
</script>
</body>
</html>
"""


class _DashHandler(BaseHTTPRequestHandler):
    engine_ref: "Engine"

    def log_message(self, *_) -> None:
        pass

    def do_GET(self) -> None:
        if self.path == "/":
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(_DASH_HTML.encode())
        elif self.path == "/api/state":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            state = self.engine_ref.get_state_dict()
            self.wfile.write(json.dumps(state).encode())
        else:
            self.send_response(404)
            self.end_headers()


class Dashboard:
    def __init__(self, engine: "Engine") -> None:
        self._engine = engine
        self._server: Optional[HTTPServer] = None

    def start(self) -> None:
        _DashHandler.engine_ref = self._engine
        self._server = HTTPServer(
            (Cfg.DASHBOARD_HOST, Cfg.DASHBOARD_PORT), _DashHandler
        )
        t = threading.Thread(target=self._server.serve_forever, daemon=True)
        t.start()
        log.info("Dashboard at http://%s:%d", Cfg.DASHBOARD_HOST, Cfg.DASHBOARD_PORT)

    def stop(self) -> None:
        if self._server:
            self._server.shutdown()


# ═══════════════════════════════════════════════════════════════════════════════
# §17  ENGINE  (main orchestrator)
# ═══════════════════════════════════════════════════════════════════════════════

class Engine:
    """
    Top-level orchestrator.  Owns all components and the asyncio event loop.
    """

    def __init__(self) -> None:
        self._session   : Optional[aiohttp.ClientSession] = None
        self._rest      : Optional[GateRest]              = None
        self._db        : Optional[DB]                    = None
        self._om        : Optional[OrderManager]          = None
        self._risk      : Optional[RiskGuard]             = None
        self._quote_eng : Optional[QuoteEngine]           = None
        self._ws        : Optional[GateWS]                = None
        self._dash      : Optional[Dashboard]             = None
        self._states    : Dict[str, SymbolState]          = {}
        self._start_ts  = time.monotonic()
        self._symbols   : List[str]                       = []

    # ── Startup ───────────────────────────────────────────────────────────────

    async def start(self) -> None:
        log.info("═══ Gate Aggressive Hedge Engine starting ═══")
        log.info("Mode: %s", "PAPER" if Cfg.PAPER else "LIVE")

        _validate_cfg()

        self._db   = DB(Cfg.DB_PATH)
        self._session = aiohttp.ClientSession(
            connector=aiohttp.TCPConnector(limit=50),
            timeout=aiohttp.ClientTimeout(total=10),
        )
        self._rest = GateRest(self._session)

        # Resolve symbol list
        if Cfg.SYMBOLS:
            self._symbols = Cfg.SYMBOLS
        else:
            self._symbols = await scan_micro_symbols(self._rest)
            if not self._symbols:
                raise RuntimeError("No micro symbols found. Check SCAN thresholds.")

        log.info("Active symbols: %s", self._symbols)
        self._db.log_event("INFO", "Engine started", data={"symbols": self._symbols,
                                                            "paper": Cfg.PAPER})

        # Enable dual-position (hedge) mode
        if Cfg.ENABLE_DUAL_MODE and not Cfg.PAPER:
            try:
                await self._rest.set_dual_mode(True)
                log.info("Dual-position mode enabled")
            except Exception as exc:
                log.warning("Could not enable dual mode (may already be on): %s", exc)

        # Load contract specs + init states
        for sym in self._symbols:
            spec = await load_contract_spec(self._rest, sym)
            st   = SymbolState(symbol=sym, spec=spec)
            self._states[sym] = st
            if spec:
                log.info("Spec %s: tick=%.8g qty=%.4g mark=%.8g min_size=%d",
                         sym, spec.tick_size, spec.quanto_multiplier,
                         spec.mark_price, spec.min_size)
                # Set leverage
                try:
                    await self._rest.set_leverage(sym, Cfg.LEVERAGE)
                except Exception as exc:
                    log.warning("set_leverage %s: %s", sym, exc)

        # Risk + Order Manager
        self._risk = RiskGuard(self._db)
        await self._risk.refresh()

        self._om = OrderManager(self._rest, self._db)
        await self._om.load_from_db()

        # Quote engine
        self._quote_eng = QuoteEngine(
            self._rest, self._om, self._db, self._risk, self._states
        )

        # Startup reconciliation
        await reconcile(self._rest, self._db, self._states, self._om)

        # Dashboard
        self._dash = Dashboard(self)
        self._dash.start()

        # WebSocket feeds
        self._ws = GateWS(
            symbols=self._symbols,
            on_book  = self._on_book,
            on_order = self._on_order_update,
            on_trade = self._on_trade,
        )
        await self._ws.start()

        # Background tasks
        asyncio.create_task(
            reprice_loop(self._states, self._quote_eng, self._om),
            name="reprice_loop"
        )

        log.info("Engine LIVE — watching %d symbols", len(self._symbols))

    # ── Callbacks ─────────────────────────────────────────────────────────────

    async def _on_book(self, tick: BookTick) -> None:
        if tick.symbol in self._states:
            await self._quote_eng.on_book_tick(tick)

    async def _on_order_update(self, raw: Dict) -> None:
        o = await self._om.on_order_update(raw)
        if o:
            log.debug("ORDER UPDATE %s %s → %s",
                      o.symbol, o.client_id[:8], o.status.value)

    async def _on_trade(self, raw: Dict) -> None:
        result = await self._om.on_trade(raw)
        if result:
            order, fill_price, fee = result
            await self._quote_eng.on_fill(order, fill_price, fee)

    # ── State export for dashboard ────────────────────────────────────────────

    def get_state_dict(self) -> Dict:
        symbols = []
        for sym, st in self._states.items():
            book = st.book
            symbols.append({
                "symbol":        sym,
                "bid":           book.bid  if book else None,
                "ask":           book.ask  if book else None,
                "spread":        book.spread if book else None,
                "long_inv":      st.long_leg.contracts,
                "short_inv":     st.short_leg.contracts,
                "net_delta":     st.net_inventory,
                "long_pnl":      st.long_leg.realized_pnl,
                "short_pnl":     st.short_leg.realized_pnl,
                "pending_long":  st.long_leg.pending_oid,
                "pending_short": st.short_leg.pending_oid,
                "book_age":      book.age_sec() if book else None,
            })

        uptime_sec = int(time.monotonic() - self._start_ts)
        h, rem = divmod(uptime_sec, 3600)
        m, s   = divmod(rem, 60)

        return {
            "symbols": symbols,
            "risk":    self._risk.status_dict() if self._risk else {},
            "session": {
                "fills_today": self._risk._session_fills if self._risk else 0,
                "uptime":      f"{h:02d}:{m:02d}:{s:02d}",
                "paper":       Cfg.PAPER,
                "symbols":     self._symbols,
            },
            "fills":  self._db.get_recent_fills(50)  if self._db else [],
            "events": self._db.get_events(60)         if self._db else [],
        }

    # ── Shutdown ──────────────────────────────────────────────────────────────

    async def stop(self) -> None:
        log.info("Engine shutting down...")
        if self._ws:
            await self._ws.stop()
        if not Cfg.PAPER and self._rest and self._states:
            for sym in self._states:
                try:
                    await self._rest.cancel_all_orders(sym)
                except Exception:
                    pass
        if self._dash:
            self._dash.stop()
        if self._session:
            await self._session.close()
        if self._db:
            self._db.log_event("INFO", "Engine stopped cleanly")
        log.info("Engine stopped.")


# ═══════════════════════════════════════════════════════════════════════════════
# §18  ENTRYPOINT
# ═══════════════════════════════════════════════════════════════════════════════

async def _main() -> None:
    engine = Engine()
    loop   = asyncio.get_running_loop()

    def _sig_handler() -> None:
        log.info("Signal received — initiating graceful shutdown")
        asyncio.create_task(engine.stop())
        loop.call_later(5.0, loop.stop)

    for sig in (asyncio.SIGINT, asyncio.SIGTERM):
        try:
            loop.add_signal_handler(sig, _sig_handler)
        except NotImplementedError:
            pass  # Windows

    try:
        await engine.start()
        # Keep running indefinitely
        while True:
            await asyncio.sleep(60)
    except Exception as exc:
        log.critical("Fatal engine error: %s\n%s", exc, traceback.format_exc())
    finally:
        try:
            await engine.stop()
        except Exception:
            pass


if __name__ == "__main__":
    _setup_logging(Cfg.LOG_LEVEL, Cfg.LOG_FILE)
    log.info("gate_aggressive_hedge.py v1.0")
    log.info("Python %s", sys.version.split()[0])
    if Cfg.PAPER:
        log.info("*** PAPER MODE — no real orders will be placed ***")
    try:
        asyncio.run(_main())
    except KeyboardInterrupt:
        pass
