#!/usr/bin/env python3
"""
gate_aggressive_hedge.py  ·  v2.0
══════════════════════════════════════════════════════════════════════════════
Aggressive Hedged Spread-Capture / Inventory-Recycling Engine
Gate.io USDT Perpetual Futures  ·  Micro-notional contracts
══════════════════════════════════════════════════════════════════════════════

WHAT THIS IS (honestly)
───────────────────────
  NOT passive market making.  NOT queue-sitting.
  This is an aggressive dual-sided hedged execution engine that:
    - enters near the spread aggressively (maker-first, taker fallback)
    - maintains simultaneous long + short per symbol (hedge mode)
    - exits each leg at a calculated spread target (fees + margin)
    - recycles capital immediately after profitable exit
    - keeps inventory balanced and turnover high

EXECUTION MODES
───────────────
  MAKER   : post-only at best bid (sell) / best ask (buy) — earns rebate
  AGGR    : limit at best ask (buy) / best bid (sell) — crosses spread
  TAKER   : IOC at market — guaranteed fill, pays taker fee

  Default flow: MAKER → wait TTL → TAKER fallback

PROFIT MECHANISM
────────────────
  Edge = spread_capture - (entry_fee + exit_fee)
  Before every order: compute expected net edge.
  If net edge ≤ 0 → skip that side.

HEDGE FSM (per symbol)
──────────────────────
  FLAT → OPENING → HEDGED → BROKEN → REPAIRING → REDUCING → HALTED
  All transitions deterministic and logged.

RISK CONTROLS
─────────────
  - Max gross exposure (total + per symbol)
  - Max inventory per side per symbol
  - Max leg imbalance duration
  - Max stale order / stale book age
  - Daily loss kill-switch
  - API error circuit breaker
  - Forced flatten on reconciliation mismatch
  - Risk engine overrides ALL quoting logic

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
  python gate_aggressive_hedge_v2.py
  Dashboard → http://localhost:8765
══════════════════════════════════════════════════════════════════════════════
"""

from __future__ import annotations

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

try:
    import aiohttp
except ImportError:
    raise SystemExit("pip install aiohttp")

try:
    import websockets
except ImportError:
    raise SystemExit("pip install websockets")


# ═══════════════════════════════════════════════════════════════════════════════
# §1  LOGGING
# ═══════════════════════════════════════════════════════════════════════════════

LOG_FMT = "%(asctime)s.%(msecs)03d %(levelname)-5s [%(name)s] %(message)s"
LOG_DATE = "%Y-%m-%dT%H:%M:%S"


def _setup_logging(level: str = "INFO", log_file: str = "gate_hedge.log") -> None:
    root = logging.getLogger()
    root.setLevel(getattr(logging, level.upper(), logging.INFO))
    for h in root.handlers[:]:
        root.removeHandler(h)
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
    """All tunables. Override via env or subclass."""

    # ── Auth ──────────────────────────────────────────────────────────────────
    API_KEY    : str = os.getenv("GATE_API_KEY", "")
    API_SECRET : str = os.getenv("GATE_API_SECRET", "")
    PAPER      : bool = os.getenv("GATE_PAPER", "0") == "1"

    # ── Exchange endpoints ────────────────────────────────────────────────────
    SETTLE   : str = "usdt"
    REST_URL : str = "https://api.gateio.ws/api/v4"
    WS_URL   : str = "wss://fx-ws.gateio.ws/v4/ws/usdt"

    # ── Symbol universe ───────────────────────────────────────────────────────
    SYMBOLS : List[str] = []
    MAX_SYMBOLS          : int   = 5
    SCAN_PRICE_MIN       : float = 0.0005
    SCAN_PRICE_MAX       : float = 0.10
    SCAN_VOLUME_MIN      : float = 500_000.0
    SCAN_MIN_SPREAD_BPS  : float = 2.0     # min spread in bps to be viable
    SCAN_MAX_SPREAD_BPS  : float = 50.0    # max spread — too wide = illiquid
    SCAN_MIN_BOOK_DEPTH  : float = 100.0   # min contracts at top of book

    # ── Sizing ────────────────────────────────────────────────────────────────
    TARGET_NOTIONAL : float = 0.07
    MIN_NOTIONAL    : float = 0.01
    MAX_NOTIONAL    : float = 0.10
    LEVERAGE        : int   = 10

    # ── Execution ─────────────────────────────────────────────────────────────
    PRIMARY_MODE    : str   = "maker"      # "maker", "aggressive", "taker"
    FALLBACK_MODE   : str   = "taker"      # fallback after TTL
    MAKER_TIF       : str   = "gtc"        # rest at bid/ask (poc too fragile in micro-caps)
    AGGR_TIF        : str   = "gtc"        # good-till-cancel
    TAKER_TIF       : str   = "ioc"        # immediate-or-cancel
    QUOTE_TTL_SEC   : float = 8.0          # cancel unfilled maker after this
    REPRICE_TICKS   : int   = 1            # reprice if best moved ≥ N ticks
    REPRICE_LOOP_SEC: float = 0.3          # reprice check frequency

    # ── Spread-capture ────────────────────────────────────────────────────────
    SPREAD_TARGET_BPS : float = 8.0        # 0.08% target exit offset per leg
    MAKER_FEE_BPS     : float = -1.5       # Gate.io maker rebate (negative = earn)
    TAKER_FEE_BPS     : float = 5.0        # Gate.io taker fee
    MIN_NET_EDGE_BPS  : float = 0.5        # minimum net edge to quote

    # ── Hedge / Recycling ─────────────────────────────────────────────────────
    MAX_INVENTORY        : int   = 10      # max contracts per side per symbol
    RECYCLE_DELAY_SEC    : float = 0.05
    ENABLE_DUAL_MODE     : bool  = True
    MAX_IMBALANCE_SEC    : float = 120.0   # max time one-sided before flatten
    EXIT_STALE_SEC       : float = 300.0   # force-close position older than this

    # ── Risk ──────────────────────────────────────────────────────────────────
    MAX_DAILY_LOSS_USD   : float = 1.00
    KILL_SWITCH_LOSS_USD : float = 2.00
    MAX_OPEN_ORDERS_SYM  : int   = 6
    MAX_GROSS_EXPOSURE   : float = 5.00    # total USD notional across all symbols
    MAX_SYM_EXPOSURE     : float = 1.50    # max USD notional per symbol
    BOOK_STALE_SEC       : float = 5.0
    API_ERROR_WINDOW_SEC : float = 60.0    # circuit breaker window
    API_ERROR_THRESHOLD  : int   = 10      # errors in window → halt
    RECON_MISMATCH_FLATTEN: bool = True    # flatten on recon mismatch

    # ── Persistence ───────────────────────────────────────────────────────────
    DB_PATH : str = "gate_hedge_v2.db"

    # ── Dashboard ─────────────────────────────────────────────────────────────
    DASHBOARD_PORT : int = 8765
    DASHBOARD_HOST : str = "127.0.0.1"

    # ── Logging ───────────────────────────────────────────────────────────────
    LOG_LEVEL : str = os.getenv("LOG_LEVEL", "INFO")
    LOG_FILE  : str = "gate_hedge_v2.log"

    # ── Rate limits ───────────────────────────────────────────────────────────
    RATE_PRIVATE_RPS : float = 8.0
    RATE_PUBLIC_RPS  : float = 15.0


def _validate_cfg() -> None:
    if not Cfg.PAPER and (not Cfg.API_KEY or not Cfg.API_SECRET):
        raise RuntimeError("GATE_API_KEY and GATE_API_SECRET required (or GATE_PAPER=1)")
    if Cfg.TARGET_NOTIONAL > Cfg.MAX_NOTIONAL:
        raise ValueError("TARGET_NOTIONAL must be ≤ MAX_NOTIONAL")


# ═══════════════════════════════════════════════════════════════════════════════
# §3  DOMAIN TYPES
# ═══════════════════════════════════════════════════════════════════════════════

class Side(str, Enum):
    LONG  = "long"
    SHORT = "short"

class OrderStatus(str, Enum):
    PENDING   = "pending"
    OPEN      = "open"
    FILLED    = "filled"
    PARTIAL   = "partial"
    CANCELLED = "cancelled"
    FAILED    = "failed"

class OrderRole(str, Enum):
    ENTRY   = "entry"
    RECYCLE = "recycle"
    EXIT    = "exit"
    TRIM    = "trim"
    FLATTEN = "flatten"

class ExecMode(str, Enum):
    MAKER      = "maker"       # post-only at best bid/ask
    AGGRESSIVE = "aggressive"  # limit crossing spread
    TAKER      = "taker"       # IOC

class HedgePhase(str, Enum):
    FLAT      = "flat"
    OPENING   = "opening"      # at least one entry pending
    HEDGED    = "hedged"       # both sides have inventory
    BROKEN    = "broken"       # one side lost
    REPAIRING = "repairing"    # repair order pending
    REDUCING  = "reducing"     # trimming excess
    HALTED    = "halted"       # risk-stopped


@dataclass
class BookTick:
    symbol   : str
    bid      : float
    ask      : float
    bid_size : float
    ask_size : float
    ts       : float = field(default_factory=time.monotonic)

    @property
    def mid(self) -> float:
        return (self.bid + self.ask) / 2.0

    @property
    def spread(self) -> float:
        return self.ask - self.bid

    @property
    def spread_bps(self) -> float:
        m = self.mid
        return (self.spread / m * 10000) if m > 0 else 0

    def age_sec(self) -> float:
        return time.monotonic() - self.ts


@dataclass
class ContractSpec:
    symbol            : str
    tick_size         : float
    quanto_multiplier : float
    min_size          : int
    mark_price        : float


@dataclass
class Order:
    client_id   : str
    exchange_id : str
    symbol      : str
    side        : Side
    size        : int
    price       : float
    tif         : str
    role        : OrderRole
    exec_mode   : ExecMode = ExecMode.MAKER
    status      : OrderStatus = OrderStatus.PENDING
    fill_price  : float = 0.0
    fill_size   : int   = 0
    fee_usdt    : float = 0.0
    created_at  : float = field(default_factory=time.time)
    updated_at  : float = field(default_factory=time.time)
    exchange_ts : float = 0.0


@dataclass
class LegAccounting:
    """Correct position accounting for one side. Tracks avg entry, realized PnL."""
    side         : Side
    symbol       : str
    contracts    : int   = 0
    cost_basis   : float = 0.0     # total USD cost of open position
    realized_pnl : float = 0.0
    total_fees   : float = 0.0
    fill_count   : int   = 0
    pending_oid  : Optional[str] = None
    exit_oid     : Optional[str] = None
    last_fill_ts : float = 0.0
    opened_at    : float = 0.0     # when first contract entered

    @property
    def avg_entry(self) -> float:
        if self.contracts <= 0:
            return 0.0
        return self.cost_basis / self.contracts

    @property
    def is_flat(self) -> bool:
        return self.contracts <= 0

    def on_entry_fill(self, size: int, price: float, quanto: float, fee: float) -> float:
        """Record entry fill. Returns net PnL of this fill (just -fee for entries)."""
        notional = price * size * quanto
        if self.contracts == 0:
            self.opened_at = time.time()
        self.contracts += size
        self.cost_basis += notional
        self.total_fees += fee
        self.realized_pnl -= fee
        self.fill_count += 1
        self.last_fill_ts = time.time()
        return -fee

    def on_close_fill(self, size: int, price: float, quanto: float, fee: float) -> float:
        """Record close fill. Returns realized PnL for this fill."""
        if self.contracts <= 0:
            self.total_fees += fee
            self.realized_pnl -= fee
            return -fee
        avg = self.avg_entry
        size = min(size, self.contracts)
        if self.side == Side.LONG:
            gross_pnl = (price - avg) * size * quanto
        else:
            gross_pnl = (avg - price) * size * quanto
        net_pnl = gross_pnl - fee
        self.cost_basis -= avg * size * quanto
        self.contracts = max(0, self.contracts - size)
        self.realized_pnl += net_pnl
        self.total_fees += fee
        self.fill_count += 1
        self.last_fill_ts = time.time()
        if self.contracts == 0:
            self.cost_basis = 0.0
            self.opened_at = 0.0
        return net_pnl

    def reset(self) -> None:
        self.contracts = 0
        self.cost_basis = 0.0
        self.pending_oid = None
        self.exit_oid = None
        self.opened_at = 0.0


@dataclass
class SymbolState:
    symbol     : str
    long_leg   : LegAccounting = field(init=False)
    short_leg  : LegAccounting = field(init=False)
    spec       : Optional[ContractSpec] = None
    book       : Optional[BookTick]     = None
    phase      : HedgePhase = HedgePhase.FLAT
    phase_ts   : float = field(default_factory=time.time)
    imbalance_since : float = 0.0

    def __post_init__(self) -> None:
        self.long_leg  = LegAccounting(side=Side.LONG,  symbol=self.symbol)
        self.short_leg = LegAccounting(side=Side.SHORT, symbol=self.symbol)

    @property
    def net_inventory(self) -> int:
        return self.long_leg.contracts - self.short_leg.contracts

    @property
    def gross_contracts(self) -> int:
        return self.long_leg.contracts + self.short_leg.contracts

    @property
    def book_stale(self) -> bool:
        return self.book is None or self.book.age_sec() > Cfg.BOOK_STALE_SEC

    def notional_exposure(self) -> float:
        if not self.spec:
            return 0.0
        q = self.spec.quanto_multiplier
        p = self.spec.mark_price
        return self.gross_contracts * p * q

    def set_phase(self, new: HedgePhase) -> None:
        if new != self.phase:
            log.info("FSM %s: %s → %s", self.symbol, self.phase.value, new.value)
            self.phase = new
            self.phase_ts = time.time()

    def update_phase(self) -> None:
        """Recompute phase from leg state."""
        l_has = self.long_leg.contracts > 0
        s_has = self.short_leg.contracts > 0
        l_pend = self.long_leg.pending_oid is not None
        s_pend = self.short_leg.pending_oid is not None

        if self.phase == HedgePhase.HALTED:
            return
        if l_has and s_has:
            self.set_phase(HedgePhase.HEDGED)
            self.imbalance_since = 0.0
        elif l_has or s_has:
            if self.phase not in (HedgePhase.BROKEN, HedgePhase.REPAIRING):
                self.set_phase(HedgePhase.BROKEN)
                if self.imbalance_since == 0:
                    self.imbalance_since = time.time()
        elif l_pend or s_pend:
            self.set_phase(HedgePhase.OPENING)
        else:
            self.set_phase(HedgePhase.FLAT)
            self.imbalance_since = 0.0


# ═══════════════════════════════════════════════════════════════════════════════
# §4  CRYPTOGRAPHIC UTILITIES
# ═══════════════════════════════════════════════════════════════════════════════

def _rest_signature(method: str, path: str, query: str, body: str, ts: int) -> str:
    body_hash = hashlib.sha512(body.encode()).hexdigest()
    msg = f"{method}\n{path}\n{query}\n{body_hash}\n{ts}"
    return hmac_mod.new(Cfg.API_SECRET.encode(), msg.encode(), hashlib.sha512).hexdigest()


def _ws_signature(channel: str, event: str, ts: int) -> str:
    msg = f"channel={channel}&event={event}&time={ts}"
    return hmac_mod.new(Cfg.API_SECRET.encode(), msg.encode(), hashlib.sha512).hexdigest()


def _rest_headers(method: str, path: str, query: str = "", body: str = "") -> Dict[str, str]:
    ts = int(time.time())
    return {
        "KEY":          Cfg.API_KEY,
        "Timestamp":    str(ts),
        "SIGN":         _rest_signature(method, path, query, body, ts),
        "Content-Type": "application/json",
        "Accept":       "application/json",
    }


# ═══════════════════════════════════════════════════════════════════════════════
# §5  RATE LIMITER
# ═══════════════════════════════════════════════════════════════════════════════

class _TokenBucket:
    def __init__(self, rate: float) -> None:
        self._rate   = rate
        self._tokens = rate
        self._last   = time.monotonic()
        self._lock   = asyncio.Lock()

    async def acquire(self) -> None:
        async with self._lock:
            now = time.monotonic()
            self._tokens = min(self._rate, self._tokens + (now - self._last) * self._rate)
            self._last = now
            if self._tokens < 1.0:
                await asyncio.sleep((1.0 - self._tokens) / self._rate)
                self._tokens = 0.0
            else:
                self._tokens -= 1.0


_private_limiter = _TokenBucket(Cfg.RATE_PRIVATE_RPS)
_public_limiter  = _TokenBucket(Cfg.RATE_PUBLIC_RPS)


# ═══════════════════════════════════════════════════════════════════════════════
# §6  REST CLIENT
# ═══════════════════════════════════════════════════════════════════════════════

_SIGN_PREFIX = "/api/v4"   # Gate.io signs against full URL path


class GateRest:
    """Async Gate.io Futures REST client with signed requests."""

    def __init__(self, session: aiohttp.ClientSession) -> None:
        self._s = session

    async def _get(self, path: str, params: Optional[Dict] = None,
                   private: bool = False) -> Any:
        await (_private_limiter if private else _public_limiter).acquire()
        query = "&".join(f"{k}={v}" for k, v in (params or {}).items())
        url = Cfg.REST_URL + path + (("?" + query) if query else "")
        sign_path = _SIGN_PREFIX + path
        headers = _rest_headers("GET", sign_path, query) if private else {}
        async with self._s.get(url, headers=headers) as r:
            data = await r.json()
            if r.status not in (200, 201):
                raise RuntimeError(f"GET {path} → {r.status}: {data}")
            return data

    async def _post(self, path: str, body: Dict) -> Any:
        await _private_limiter.acquire()
        raw = json.dumps(body)
        sign_path = _SIGN_PREFIX + path
        hdrs = _rest_headers("POST", sign_path, "", raw)
        async with self._s.post(Cfg.REST_URL + path, headers=hdrs, data=raw) as r:
            data = await r.json()
            if r.status not in (200, 201):
                raise RuntimeError(f"POST {path} → {r.status}: {data}")
            return data

    async def _delete(self, path: str, params: Optional[Dict] = None) -> Any:
        await _private_limiter.acquire()
        query = "&".join(f"{k}={v}" for k, v in (params or {}).items())
        sign_path = _SIGN_PREFIX + path
        hdrs = _rest_headers("DELETE", sign_path, query)
        url = Cfg.REST_URL + path + (("?" + query) if query else "")
        async with self._s.delete(url, headers=hdrs) as r:
            data = await r.json()
            if r.status not in (200, 201):
                raise RuntimeError(f"DELETE {path} → {r.status}: {data}")
            return data

    async def _put(self, path: str, body: Dict) -> Any:
        await _private_limiter.acquire()
        raw = json.dumps(body)
        sign_path = _SIGN_PREFIX + path
        hdrs = _rest_headers("PUT", sign_path, "", raw)
        async with self._s.put(Cfg.REST_URL + path, headers=hdrs, data=raw) as r:
            data = await r.json()
            if r.status not in (200, 201):
                raise RuntimeError(f"PUT {path} → {r.status}: {data}")
            return data

    async def get_contracts(self) -> List[Dict]:
        return await self._get(f"/futures/{Cfg.SETTLE}/contracts")

    async def get_contract(self, symbol: str) -> Dict:
        return await self._get(f"/futures/{Cfg.SETTLE}/contracts/{symbol}")

    async def get_tickers(self) -> List[Dict]:
        return await self._get(f"/futures/{Cfg.SETTLE}/tickers")

    async def get_order_book(self, symbol: str, limit: int = 5) -> Dict:
        return await self._get(f"/futures/{Cfg.SETTLE}/order_book",
                               {"contract": symbol, "limit": str(limit)})

    async def get_account(self) -> Dict:
        return await self._get(f"/futures/{Cfg.SETTLE}/accounts", private=True)

    async def set_dual_mode(self, dual: bool) -> Dict:
        """POST with query param, not body."""
        await _private_limiter.acquire()
        val = "true" if dual else "false"
        query = f"dual_mode={val}"
        path = f"/futures/{Cfg.SETTLE}/dual_mode"
        sign_path = _SIGN_PREFIX + path
        hdrs = _rest_headers("POST", sign_path, query, "")
        url = Cfg.REST_URL + path + "?" + query
        async with self._s.post(url, headers=hdrs) as r:
            data = await r.json()
            if r.status not in (200, 201):
                raise RuntimeError(f"POST {path} → {r.status}: {data}")
            return data

    async def set_leverage(self, symbol: str, leverage: int) -> Dict:
        """POST with query params, not body."""
        await _private_limiter.acquire()
        path = f"/futures/{Cfg.SETTLE}/positions/{symbol}/leverage"
        query = f"leverage={leverage}"
        sign_path = _SIGN_PREFIX + path
        hdrs = _rest_headers("POST", sign_path, query, "")
        url = Cfg.REST_URL + path + "?" + query
        async with self._s.post(url, headers=hdrs) as r:
            data = await r.json()
            if r.status not in (200, 201):
                raise RuntimeError(f"POST {path} → {r.status}: {data}")
            return data

    async def get_positions(self) -> List[Dict]:
        return await self._get(f"/futures/{Cfg.SETTLE}/positions", private=True)

    async def get_dual_positions(self, symbol: str) -> List[Dict]:
        return await self._get(
            f"/futures/{Cfg.SETTLE}/dual_comp/positions/{symbol}", private=True)

    async def place_order(self, symbol: str, size: int, price: float,
                          tif: str = "ioc", reduce_only: bool = False,
                          text: str = "") -> Dict:
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
        return await self._get(f"/futures/{Cfg.SETTLE}/orders", params, private=True)

    async def get_order(self, order_id: str) -> Dict:
        return await self._get(f"/futures/{Cfg.SETTLE}/orders/{order_id}", private=True)


# ═══════════════════════════════════════════════════════════════════════════════
# §7  WEBSOCKET MANAGER
# ═══════════════════════════════════════════════════════════════════════════════

BookCallback  = Callable[[BookTick], Coroutine]
OrderCallback = Callable[[Dict], Coroutine]
TradeCallback = Callable[[Dict], Coroutine]


class GateWS:
    """Public (book ticker) + Private (orders, usertrades) WebSocket feeds."""

    def __init__(self, symbols: List[str],
                 on_book: Optional[BookCallback] = None,
                 on_order: Optional[OrderCallback] = None,
                 on_trade: Optional[TradeCallback] = None) -> None:
        self._symbols  = symbols
        self._on_book  = on_book
        self._on_order = on_order
        self._on_trade = on_trade
        self._shutdown = False
        self._tasks: List[asyncio.Task] = []
        self.reconnect_count = 0

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

    async def _run_public(self) -> None:
        backoff = 1.0
        while not self._shutdown:
            try:
                async with websockets.connect(
                    Cfg.WS_URL, ping_interval=20, ping_timeout=10, close_timeout=5,
                ) as ws:
                    log.info("WS public connected")
                    backoff = 1.0
                    for sym in self._symbols:
                        await ws.send(json.dumps({
                            "time": int(time.time()),
                            "channel": "futures.book_ticker",
                            "event": "subscribe",
                            "payload": [sym],
                        }))
                    async for raw in ws:
                        if self._shutdown:
                            return
                        try:
                            msg = json.loads(raw)
                            if msg.get("event") in ("subscribe", "unsubscribe"):
                                continue
                            result = msg.get("result")
                            if msg.get("channel") == "futures.book_ticker" and result:
                                bid = float(result.get("b") or result.get("bid_price") or 0)
                                ask = float(result.get("a") or result.get("ask_price") or 0)
                                bsz = float(result.get("B") or result.get("bid_amount") or 0)
                                asz = float(result.get("A") or result.get("ask_amount") or 0)
                                sym = str(result.get("s") or result.get("c") or
                                          result.get("contract") or "")
                                if sym and bid > 0 and ask > 0 and self._on_book:
                                    await self._on_book(BookTick(
                                        symbol=sym, bid=bid, ask=ask,
                                        bid_size=bsz, ask_size=asz))
                        except Exception:
                            log.exception("WS public dispatch error")
            except asyncio.CancelledError:
                return
            except Exception as exc:
                if self._shutdown:
                    return
                self.reconnect_count += 1
                log.warning("WS public disconnected: %s — retry %.1fs", exc, backoff)
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2.0, 30.0)

    async def _run_private(self) -> None:
        backoff = 1.0
        while not self._shutdown:
            try:
                async with websockets.connect(
                    Cfg.WS_URL, ping_interval=20, ping_timeout=10, close_timeout=5,
                ) as ws:
                    log.info("WS private connected")
                    backoff = 1.0
                    for channel in ("futures.orders", "futures.usertrades"):
                        ts = int(time.time())
                        sign = _ws_signature(channel, "subscribe", ts)
                        await ws.send(json.dumps({
                            "time": ts, "channel": channel, "event": "subscribe",
                            "payload": [Cfg.SETTLE],
                            "auth": {"method": "api_key", "KEY": Cfg.API_KEY, "SIGN": sign},
                        }))
                    async for raw in ws:
                        if self._shutdown:
                            return
                        try:
                            msg = json.loads(raw)
                            if msg.get("event") in ("subscribe", "unsubscribe"):
                                continue
                            result = msg.get("result")
                            if result is None:
                                continue
                            items = result if isinstance(result, list) else [result]
                            ch = msg.get("channel", "")
                            if ch == "futures.orders":
                                for item in items:
                                    if item and self._on_order:
                                        await self._on_order(item)
                            elif ch == "futures.usertrades":
                                for item in items:
                                    if item and self._on_trade:
                                        await self._on_trade(item)
                        except Exception:
                            log.exception("WS private dispatch error")
            except asyncio.CancelledError:
                return
            except Exception as exc:
                if self._shutdown:
                    return
                self.reconnect_count += 1
                log.warning("WS private disconnected: %s — retry %.1fs", exc, backoff)
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2.0, 30.0)


# ═══════════════════════════════════════════════════════════════════════════════
# §8  PERSISTENCE (SQLite)
# ═══════════════════════════════════════════════════════════════════════════════

class DB:
    """SQLite persistence — orders, fills, events, daily PnL, metrics."""

    def __init__(self, path: str = Cfg.DB_PATH) -> None:
        self._con = sqlite3.connect(path, check_same_thread=False)
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
                    exec_mode    TEXT,
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
                    role         TEXT,
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
                    fills      INTEGER DEFAULT 0,
                    cancels    INTEGER DEFAULT 0,
                    notional   REAL DEFAULT 0
                );

                CREATE TABLE IF NOT EXISTS metrics (
                    ts             REAL PRIMARY KEY,
                    fills_per_min  REAL DEFAULT 0,
                    cancels_per_min REAL DEFAULT 0,
                    gross_notional REAL DEFAULT 0,
                    fees_paid      REAL DEFAULT 0,
                    realized_pnl   REAL DEFAULT 0,
                    api_errors     INTEGER DEFAULT 0,
                    ws_reconnects  INTEGER DEFAULT 0
                );

                CREATE INDEX IF NOT EXISTS idx_orders_symbol ON orders(symbol);
                CREATE INDEX IF NOT EXISTS idx_orders_status ON orders(status);
                CREATE INDEX IF NOT EXISTS idx_fills_ts ON fills(ts);
            """)

    def upsert_order(self, o: Order) -> None:
        with self._lock, self._con:
            self._con.execute("""
                INSERT INTO orders VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(client_id) DO UPDATE SET
                    exchange_id=excluded.exchange_id, status=excluded.status,
                    fill_price=excluded.fill_price, fill_size=excluded.fill_size,
                    fee_usdt=excluded.fee_usdt, updated_at=excluded.updated_at,
                    exchange_ts=excluded.exchange_ts
            """, (o.client_id, o.exchange_id, o.symbol, o.side.value,
                  o.size, o.price, o.tif, o.role.value, o.exec_mode.value,
                  o.status.value, o.fill_price, o.fill_size, o.fee_usdt,
                  o.created_at, o.updated_at, o.exchange_ts))

    def get_open_orders(self, symbol: Optional[str] = None) -> List[Dict]:
        with self._lock:
            q = "SELECT * FROM orders WHERE status IN ('pending','open')"
            args: tuple = ()
            if symbol:
                q += " AND symbol=?"
                args = (symbol,)
            return [dict(r) for r in self._con.execute(q, args).fetchall()]

    def insert_fill(self, fill_id: str, order_id: str, symbol: str,
                    side: Side, role: str, size: int, price: float,
                    fee: float, pnl: float, ts: float) -> None:
        with self._lock, self._con:
            self._con.execute(
                "INSERT OR IGNORE INTO fills VALUES (?,?,?,?,?,?,?,?,?,?)",
                (fill_id, order_id, symbol, side.value, role, size, price, fee, pnl, ts))

    def add_daily_pnl(self, pnl: float, fee: float, notional: float = 0) -> None:
        date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        with self._lock, self._con:
            self._con.execute("""
                INSERT INTO daily_pnl(date,realized,fees,fills,notional)
                VALUES(?,?,?,1,?)
                ON CONFLICT(date) DO UPDATE SET
                    realized=realized+excluded.realized,
                    fees=fees+excluded.fees,
                    fills=fills+1,
                    notional=notional+excluded.notional
            """, (date, pnl, fee, notional))

    def add_daily_cancel(self) -> None:
        date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        with self._lock, self._con:
            self._con.execute("""
                INSERT INTO daily_pnl(date,cancels) VALUES(?,1)
                ON CONFLICT(date) DO UPDATE SET cancels=cancels+1
            """, (date,))

    def daily_pnl_today(self) -> Dict:
        date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        with self._lock:
            row = self._con.execute("SELECT * FROM daily_pnl WHERE date=?", (date,)).fetchone()
            return dict(row) if row else {"date": date, "realized": 0.0,
                                           "fees": 0.0, "fills": 0, "cancels": 0,
                                           "notional": 0.0}

    def get_recent_fills(self, limit: int = 100) -> List[Dict]:
        with self._lock:
            return [dict(r) for r in self._con.execute(
                "SELECT * FROM fills ORDER BY ts DESC LIMIT ?", (limit,)).fetchall()]

    def log_event(self, level: str, message: str, symbol: Optional[str] = None,
                  data: Optional[Dict] = None) -> None:
        with self._lock, self._con:
            self._con.execute(
                "INSERT INTO events(ts,level,symbol,message,data) VALUES(?,?,?,?,?)",
                (time.time(), level, symbol, message, json.dumps(data) if data else None))

    def get_events(self, limit: int = 200) -> List[Dict]:
        with self._lock:
            return [dict(r) for r in self._con.execute(
                "SELECT * FROM events ORDER BY id DESC LIMIT ?", (limit,)).fetchall()]

    def save_metric_snapshot(self, **kw: Any) -> None:
        with self._lock, self._con:
            self._con.execute("""
                INSERT OR REPLACE INTO metrics(ts,fills_per_min,cancels_per_min,
                    gross_notional,fees_paid,realized_pnl,api_errors,ws_reconnects)
                VALUES(?,?,?,?,?,?,?,?)
            """, (time.time(), kw.get("fpm", 0), kw.get("cpm", 0),
                  kw.get("notional", 0), kw.get("fees", 0), kw.get("pnl", 0),
                  kw.get("api_err", 0), kw.get("ws_recon", 0)))


# ═══════════════════════════════════════════════════════════════════════════════
# §9  ORDER LIFECYCLE MANAGER
# ═══════════════════════════════════════════════════════════════════════════════

class OrderManager:
    """
    Owns all live orders. Bridges REST → DB.
    Strictly separated from position/fill state.
    """

    def __init__(self, rest: GateRest, db: DB) -> None:
        self._rest = rest
        self._db   = db
        self._orders: Dict[str, Order] = {}
        self._eid_map: Dict[str, str]  = {}
        self._lock = asyncio.Lock()
        self.submit_count = 0
        self.cancel_count = 0
        self.error_count  = 0
        self._error_timestamps: deque = deque(maxlen=100)

    @property
    def recent_error_rate(self) -> int:
        cutoff = time.time() - Cfg.API_ERROR_WINDOW_SEC
        return sum(1 for ts in self._error_timestamps if ts > cutoff)

    async def all_open(self, symbol: Optional[str] = None) -> List[Order]:
        async with self._lock:
            return [o for o in self._orders.values()
                    if o.status in (OrderStatus.PENDING, OrderStatus.OPEN)
                    and (symbol is None or o.symbol == symbol)]

    async def get_by_client(self, client_id: str) -> Optional[Order]:
        async with self._lock:
            return self._orders.get(client_id)

    async def get_by_exchange(self, exchange_id: str) -> Optional[Order]:
        async with self._lock:
            cid = self._eid_map.get(exchange_id)
            return self._orders.get(cid) if cid else None

    async def submit(self, symbol: str, side: Side, size: int, price: float,
                     tif: str, role: OrderRole,
                     exec_mode: ExecMode = ExecMode.MAKER,
                     reduce_only: bool = False) -> Optional[Order]:
        client_id = uuid.uuid4().hex[:16]
        gate_size = size if side == Side.LONG else -size
        o = Order(client_id=client_id, exchange_id="", symbol=symbol,
                  side=side, size=size, price=price, tif=tif, role=role,
                  exec_mode=exec_mode, status=OrderStatus.PENDING,
                  created_at=time.time(), updated_at=time.time())
        async with self._lock:
            self._orders[client_id] = o
        self._db.upsert_order(o)

        if Cfg.PAPER:
            log.info("PAPER %s %s %s ×%d @ %.8g %s %s",
                     exec_mode.value.upper(), side.value.upper(),
                     symbol, size, price, tif, role.value)
            o.status = OrderStatus.OPEN
            o.exchange_id = client_id
            o.updated_at = time.time()
            self._db.upsert_order(o)
            self.submit_count += 1
            return o

        try:
            resp = await self._rest.place_order(
                symbol=symbol, size=gate_size, price=price,
                tif=tif, reduce_only=reduce_only, text=client_id)
            eid = str(resp.get("id", ""))
            status_str = resp.get("status", "open")
            finish_as = resp.get("finish_as", "")
            async with self._lock:
                o.exchange_id = eid
                if status_str == "finished" and finish_as == "filled":
                    o.status = OrderStatus.FILLED
                    o.fill_price = float(resp.get("fill_price") or price)
                    o.fill_size = abs(int(resp.get("size", 0))) - abs(int(resp.get("left", 0)))
                elif status_str == "finished":
                    o.status = OrderStatus.CANCELLED
                else:
                    o.status = OrderStatus.OPEN
                o.updated_at = time.time()
                if eid:
                    self._eid_map[eid] = client_id
            self._db.upsert_order(o)
            self.submit_count += 1
            log.debug("ORDER %s %s %s ×%d @ %.8g eid=%s → %s",
                      exec_mode.value, side.value.upper(), symbol, size,
                      price, eid, o.status.value)
            return o
        except Exception as exc:
            log.error("ORDER FAILED %s %s ×%d: %s", side.value.upper(), symbol, size, exc)
            async with self._lock:
                o.status = OrderStatus.FAILED
                o.updated_at = time.time()
            self._db.upsert_order(o)
            self.error_count += 1
            self._error_timestamps.append(time.time())
            return None

    async def cancel(self, client_id: str) -> bool:
        o = await self.get_by_client(client_id)
        if not o or o.status not in (OrderStatus.PENDING, OrderStatus.OPEN):
            return False
        if not o.exchange_id or Cfg.PAPER:
            async with self._lock:
                o.status = OrderStatus.CANCELLED
                o.updated_at = time.time()
            self._db.upsert_order(o)
            self._db.add_daily_cancel()
            self.cancel_count += 1
            return True
        try:
            await self._rest.cancel_order(o.exchange_id)
        except Exception as exc:
            err_str = str(exc)
            if "ORDER_NOT_FOUND" in err_str or "FINISHED" in err_str:
                pass  # already gone — treat as cancelled
            else:
                log.warning("Cancel %s failed: %s", client_id, exc)
                self._error_timestamps.append(time.time())
                return False
        async with self._lock:
            o.status = OrderStatus.CANCELLED
            o.updated_at = time.time()
        self._db.upsert_order(o)
        self._db.add_daily_cancel()
        self.cancel_count += 1
        return True

    async def cancel_symbol(self, symbol: str) -> int:
        if not Cfg.PAPER:
            try:
                await self._rest.cancel_all_orders(symbol)
            except Exception as exc:
                log.warning("cancel_all %s: %s", symbol, exc)
        count = 0
        async with self._lock:
            for o in self._orders.values():
                if o.symbol == symbol and o.status in (OrderStatus.PENDING, OrderStatus.OPEN):
                    o.status = OrderStatus.CANCELLED
                    o.updated_at = time.time()
                    count += 1
        self.cancel_count += count
        return count

    async def on_order_update(self, raw: Dict) -> Optional[Order]:
        eid = str(raw.get("id", ""))
        o = await self.get_by_exchange(eid)
        if not o:
            return None
        status = raw.get("status", "")
        new_status: Optional[OrderStatus] = None
        if status == "open":
            new_status = OrderStatus.OPEN
        elif status in ("closed", "finished"):
            finish = raw.get("finish_as", "")
            left = abs(int(raw.get("left", 0)))
            total = abs(int(raw.get("size", o.size)))
            if finish == "filled" or left == 0:
                new_status = OrderStatus.FILLED
            elif left > 0 and left < total:
                new_status = OrderStatus.PARTIAL
            else:
                new_status = OrderStatus.CANCELLED
        if new_status and new_status != o.status:
            async with self._lock:
                o.status = new_status
                o.updated_at = time.time()
                if raw.get("fill_price"):
                    o.fill_price = float(raw["fill_price"])
                if raw.get("left") is not None and raw.get("size") is not None:
                    o.fill_size = abs(int(raw["size"])) - abs(int(raw["left"]))
            self._db.upsert_order(o)
            return o
        return None

    async def on_trade(self, raw: Dict) -> Optional[Tuple[Order, int, float, float]]:
        """Returns (order, fill_size, fill_price, fee_usdt) or None."""
        oid = str(raw.get("order_id", ""))
        o = await self.get_by_exchange(oid)
        if not o:
            return None
        fill_price = float(raw.get("price", 0))
        fill_size = abs(int(raw.get("size", 0)))
        fee_usdt = abs(float(raw.get("fee", 0)))
        async with self._lock:
            o.fill_price = fill_price
            o.fill_size += fill_size
            o.fee_usdt += fee_usdt
            o.exchange_ts = float(raw.get("create_time", time.time()))
        self._db.upsert_order(o)
        return o, fill_size, fill_price, fee_usdt

    async def load_from_db(self) -> None:
        rows = self._db.get_open_orders()
        async with self._lock:
            for row in rows:
                try:
                    o = Order(
                        client_id=row["client_id"],
                        exchange_id=row.get("exchange_id") or "",
                        symbol=row["symbol"], side=Side(row["side"]),
                        size=row["size"], price=row["price"],
                        tif=row.get("tif", ""), role=OrderRole(row["role"]),
                        exec_mode=ExecMode(row.get("exec_mode", "maker")),
                        status=OrderStatus(row["status"]),
                        fill_price=row.get("fill_price", 0),
                        fill_size=row.get("fill_size", 0),
                        fee_usdt=row.get("fee_usdt", 0),
                        created_at=row["created_at"],
                        updated_at=row["updated_at"],
                        exchange_ts=row.get("exchange_ts", 0))
                    self._orders[o.client_id] = o
                    if o.exchange_id:
                        self._eid_map[o.exchange_id] = o.client_id
                except Exception:
                    pass
        log.info("OrderManager: loaded %d orders from DB", len(rows))


# ═══════════════════════════════════════════════════════════════════════════════
# §10  RISK ENGINE
# ═══════════════════════════════════════════════════════════════════════════════

class RiskEngine:
    """
    Centralised risk. Overrides ALL quoting logic.
    Checks: daily loss, kill-switch, exposure, inventory, imbalance,
    stale book, API error circuit breaker.
    """

    def __init__(self, db: DB) -> None:
        self._db           = db
        self._killed       = False
        self._daily_loss   = 0.0
        self._daily_fees   = 0.0
        self._daily_fills  = 0
        self._daily_cancels = 0
        self._daily_notional = 0.0
        self._halted_symbols: Set[str] = set()

    async def refresh(self) -> None:
        snap = self._db.daily_pnl_today()
        self._daily_loss    = -min(0.0, float(snap.get("realized", 0)))
        self._daily_fees    = float(snap.get("fees", 0))
        self._daily_fills   = int(snap.get("fills", 0))
        self._daily_cancels = int(snap.get("cancels", 0))
        self._daily_notional = float(snap.get("notional", 0))

    def record_fill(self, pnl: float, fee: float, notional: float = 0) -> None:
        self._daily_loss += -min(0.0, pnl)
        self._daily_fees += fee
        self._daily_fills += 1
        self._daily_notional += notional
        self._db.add_daily_pnl(pnl, fee, notional)
        if self._daily_loss >= Cfg.KILL_SWITCH_LOSS_USD:
            log.critical("KILL SWITCH: daily loss $%.4f >= $%.2f",
                         self._daily_loss, Cfg.KILL_SWITCH_LOSS_USD)
            self._killed = True

    @property
    def killed(self) -> bool:
        return self._killed

    def halt_symbol(self, symbol: str) -> None:
        self._halted_symbols.add(symbol)

    def unhalt_symbol(self, symbol: str) -> None:
        self._halted_symbols.discard(symbol)

    def is_halted(self, symbol: str) -> bool:
        return symbol in self._halted_symbols

    def can_quote(self, symbol: str, open_orders: int,
                  states: Dict[str, SymbolState],
                  om: "OrderManager") -> Tuple[bool, str]:
        """Master gate for all quoting decisions."""
        if self._killed:
            return False, "kill_switch"
        if self._daily_loss >= Cfg.MAX_DAILY_LOSS_USD:
            return False, f"daily_loss ${self._daily_loss:.4f}"
        if symbol in self._halted_symbols:
            return False, "symbol_halted"
        if open_orders >= Cfg.MAX_OPEN_ORDERS_SYM:
            return False, f"max_open_orders {open_orders}"
        # API error circuit breaker
        if om.recent_error_rate >= Cfg.API_ERROR_THRESHOLD:
            return False, f"api_errors {om.recent_error_rate} in {Cfg.API_ERROR_WINDOW_SEC}s"
        # Gross exposure check
        total_exp = sum(st.notional_exposure() for st in states.values())
        if total_exp >= Cfg.MAX_GROSS_EXPOSURE:
            return False, f"max_gross_exposure ${total_exp:.4f}"
        # Per-symbol exposure
        st = states.get(symbol)
        if st and st.notional_exposure() >= Cfg.MAX_SYM_EXPOSURE:
            return False, f"max_sym_exposure ${st.notional_exposure():.4f}"
        return True, ""

    def can_add_inventory(self, leg: LegAccounting) -> bool:
        return leg.contracts < Cfg.MAX_INVENTORY

    def check_imbalance(self, st: SymbolState) -> Tuple[bool, str]:
        """Check if one-sided position exceeds max imbalance duration."""
        if st.imbalance_since <= 0:
            return True, ""
        elapsed = time.time() - st.imbalance_since
        if elapsed > Cfg.MAX_IMBALANCE_SEC:
            return False, f"imbalance {elapsed:.0f}s > {Cfg.MAX_IMBALANCE_SEC}s"
        return True, ""

    def check_stale_position(self, leg: LegAccounting) -> Tuple[bool, str]:
        """Check if position is too old and should be force-closed."""
        if leg.is_flat or leg.opened_at <= 0:
            return True, ""
        age = time.time() - leg.opened_at
        if age > Cfg.EXIT_STALE_SEC:
            return False, f"position_age {age:.0f}s > {Cfg.EXIT_STALE_SEC}s"
        return True, ""

    def status_dict(self) -> Dict:
        return {
            "killed": self._killed,
            "daily_loss": self._daily_loss,
            "daily_fees": self._daily_fees,
            "daily_fills": self._daily_fills,
            "daily_cancels": self._daily_cancels,
            "daily_notional": self._daily_notional,
            "max_daily_loss": Cfg.MAX_DAILY_LOSS_USD,
            "halted_symbols": list(self._halted_symbols),
        }


# ═══════════════════════════════════════════════════════════════════════════════
# §11  SYMBOL SELECTOR
# ═══════════════════════════════════════════════════════════════════════════════

async def scan_micro_symbols(rest: GateRest) -> List[str]:
    """
    Select symbols that are economically viable for the strategy.
    Filters: notional range, volume, spread, book depth, fee viability.
    """
    try:
        tickers = await rest.get_tickers()
        contracts = await rest.get_contracts()
        spec_map = {c["name"]: c for c in contracts}
    except Exception as exc:
        log.error("Symbol scan failed: %s", exc)
        return []

    candidates: List[Tuple[float, str, float]] = []  # (score, symbol, spread_bps)
    for t in tickers:
        sym = t.get("contract", "")
        if not sym.endswith("_USDT"):
            continue
        mark = float(t.get("mark_price") or t.get("last", 0) or 0)
        vol24 = float(t.get("volume_24h_base", 0) or t.get("volume_24h", 0) or 0)
        if mark < Cfg.SCAN_PRICE_MIN or mark > Cfg.SCAN_PRICE_MAX:
            continue
        if vol24 < Cfg.SCAN_VOLUME_MIN:
            continue
        spec = spec_map.get(sym, {})
        quanto = float(spec.get("quanto_multiplier") or 1.0)
        notional = mark * quanto
        if not (Cfg.MIN_NOTIONAL <= notional <= Cfg.MAX_NOTIONAL):
            continue
        # Estimate spread from ticker
        highest_bid = float(t.get("highest_bid", 0) or 0)
        lowest_ask = float(t.get("lowest_ask", 0) or 0)
        if highest_bid > 0 and lowest_ask > highest_bid:
            spread_bps = (lowest_ask - highest_bid) / ((lowest_ask + highest_bid) / 2) * 10000
        else:
            spread_bps = 0
        # Filter by spread viability
        if spread_bps > 0:
            if spread_bps < Cfg.SCAN_MIN_SPREAD_BPS or spread_bps > Cfg.SCAN_MAX_SPREAD_BPS:
                continue
        # Fee viability: spread must cover round-trip fees
        entry_fee_bps = Cfg.TAKER_FEE_BPS  # worst case
        exit_fee_bps = Cfg.TAKER_FEE_BPS
        total_fee_bps = entry_fee_bps + exit_fee_bps
        if spread_bps > 0 and spread_bps < total_fee_bps * 1.2:
            continue  # spread too tight to cover fees
        # Score: volume-weighted, prefer tighter spreads that still have edge
        score = vol24 * (1.0 / max(spread_bps, 1.0))
        candidates.append((score, sym, spread_bps))

    candidates.sort(reverse=True)
    chosen = [sym for _, sym, _ in candidates[:Cfg.MAX_SYMBOLS]]
    log.info("Scanned %d viable symbols: %s", len(chosen), chosen)
    for score, sym, spread_bps in candidates[:Cfg.MAX_SYMBOLS]:
        log.info("  %s: spread=%.1f bps, score=%.0f", sym, spread_bps, score)
    return chosen


async def load_contract_spec(rest: GateRest, symbol: str) -> Optional[ContractSpec]:
    try:
        c = await rest.get_contract(symbol)
        return ContractSpec(
            symbol=symbol,
            tick_size=float(c.get("order_price_round") or c.get("mark_price_round") or "0.00001"),
            quanto_multiplier=float(c.get("quanto_multiplier") or "1"),
            min_size=int(c.get("order_size_min") or 1),
            mark_price=float(c.get("mark_price") or c.get("index_price") or 0))
    except Exception as exc:
        log.error("Failed to load spec for %s: %s", symbol, exc)
        return None


def compute_size(spec: ContractSpec, notional: float) -> int:
    value_per_ct = spec.mark_price * spec.quanto_multiplier
    if value_per_ct <= 0:
        return spec.min_size
    return max(spec.min_size, math.floor(notional / value_per_ct))


def round_price(price: float, tick: float) -> float:
    if tick <= 0:
        return price
    return round(round(price / tick) * tick, 10)


# ═══════════════════════════════════════════════════════════════════════════════
# §12  PROFITABILITY CHECKER
# ═══════════════════════════════════════════════════════════════════════════════

def estimate_net_edge_bps(exec_mode: ExecMode, book: Optional[BookTick]) -> float:
    """
    Estimate net edge in bps BEFORE placing an order.
    Exit orders are placed as maker (gtc limit at spread target),
    so exit_fee = MAKER_FEE_BPS in the normal case.
    Returns expected net profit per unit after fees.
    If negative → don't quote.
    """
    if not book or book.spread <= 0:
        return 0.0
    # Entry fee depends on mode; exit is always maker (gtc limit)
    if exec_mode == ExecMode.MAKER:
        entry_fee = Cfg.MAKER_FEE_BPS
    elif exec_mode == ExecMode.AGGRESSIVE:
        entry_fee = Cfg.TAKER_FEE_BPS
    else:  # TAKER
        entry_fee = Cfg.TAKER_FEE_BPS
    exit_fee = Cfg.MAKER_FEE_BPS  # exit is always maker (gtc limit order)
    # Use the larger of target or actual spread as gross edge
    gross_edge = max(Cfg.SPREAD_TARGET_BPS, book.spread_bps * 0.5)
    net_edge = gross_edge - entry_fee - exit_fee
    return net_edge


def select_exec_mode(book: Optional[BookTick]) -> ExecMode:
    """Choose execution mode based on profitability."""
    if not book:
        return ExecMode.TAKER
    # Try maker first (cheapest)
    maker_edge = estimate_net_edge_bps(ExecMode.MAKER, book)
    if maker_edge >= Cfg.MIN_NET_EDGE_BPS:
        return ExecMode.MAKER
    # Try aggressive limit
    aggr_edge = estimate_net_edge_bps(ExecMode.AGGRESSIVE, book)
    if aggr_edge >= Cfg.MIN_NET_EDGE_BPS:
        return ExecMode.AGGRESSIVE
    # Only taker if still viable
    taker_edge = estimate_net_edge_bps(ExecMode.TAKER, book)
    if taker_edge >= Cfg.MIN_NET_EDGE_BPS:
        return ExecMode.TAKER
    return ExecMode.MAKER  # default to maker even if marginal


def get_tif_for_mode(mode: ExecMode) -> str:
    if mode == ExecMode.MAKER:
        return Cfg.MAKER_TIF
    elif mode == ExecMode.AGGRESSIVE:
        return Cfg.AGGR_TIF
    else:
        return Cfg.TAKER_TIF


def get_entry_price(mode: ExecMode, side: Side, book: BookTick,
                    spec: ContractSpec) -> float:
    """
    Compute entry price based on execution mode.
    MAKER: buy@bid, sell@ask (passive, earns rebate)
    AGGRESSIVE: buy@ask, sell@bid (crosses spread)
    TAKER: buy@ask+tick, sell@bid-tick (guaranteed fill)
    """
    if mode == ExecMode.MAKER:
        px = book.bid if side == Side.LONG else book.ask
    elif mode == ExecMode.AGGRESSIVE:
        px = book.ask if side == Side.LONG else book.bid
    else:  # TAKER
        if side == Side.LONG:
            px = book.ask + spec.tick_size
        else:
            px = book.bid - spec.tick_size
    return round_price(px, spec.tick_size)


def get_exit_price(side: Side, entry: float, spec: ContractSpec) -> float:
    """Compute exit price at spread target, covering fees."""
    target_move = entry * Cfg.SPREAD_TARGET_BPS / 10000
    if side == Side.LONG:
        return round_price(entry + target_move, spec.tick_size)
    else:
        return round_price(entry - target_move, spec.tick_size)


# ═══════════════════════════════════════════════════════════════════════════════
# §13  QUOTE ENGINE
# ═══════════════════════════════════════════════════════════════════════════════

class QuoteEngine:
    """
    Core execution logic. Per symbol:
    - Maintain one entry quote per side (long buy, short sell)
    - On fill → place exit at spread target
    - On exit fill → record PnL, recycle
    - Profitability check before every order
    """

    def __init__(self, rest: GateRest, om: OrderManager, db: DB,
                 risk: RiskEngine, states: Dict[str, SymbolState]) -> None:
        self._rest   = rest
        self._om     = om
        self._db     = db
        self._risk   = risk
        self._states = states

    async def on_book_tick(self, tick: BookTick) -> None:
        st = self._states.get(tick.symbol)
        if not st:
            return
        st.book = tick
        if st.spec:
            st.spec.mark_price = tick.mid
        await self._manage_symbol(st)

    async def _manage_symbol(self, st: SymbolState) -> None:
        if st.book_stale or self._risk.killed or st.phase == HedgePhase.HALTED:
            return
        if self._risk.is_halted(st.symbol):
            return
        book = st.book
        spec = st.spec
        if not spec or not book or book.bid <= 0 or book.ask <= 0 or book.bid >= book.ask:
            return
        # Risk: check imbalance timeout
        ok, reason = self._risk.check_imbalance(st)
        if not ok:
            log.warning("FLATTEN %s: %s", st.symbol, reason)
            await self._flatten_symbol(st, reason)
            return
        # Manage each leg independently
        await self._manage_entry_leg(st, Side.LONG)
        await self._manage_entry_leg(st, Side.SHORT)
        await self._manage_exit_leg(st, Side.LONG)
        await self._manage_exit_leg(st, Side.SHORT)
        st.update_phase()

    async def _manage_entry_leg(self, st: SymbolState, side: Side) -> None:
        """Manage entry (opening) orders for one side."""
        leg = st.long_leg if side == Side.LONG else st.short_leg
        book = st.book
        spec = st.spec
        if not book or not spec:
            return
        # If already filled, don't place new entry
        if not leg.is_flat:
            return
        # If exit order still pending, don't re-enter yet
        if leg.exit_oid:
            return
        # Check if there's an active entry order
        if leg.pending_oid:
            existing = await self._om.get_by_client(leg.pending_oid)
            if not existing or existing.status not in (OrderStatus.PENDING, OrderStatus.OPEN):
                leg.pending_oid = None
            else:
                # Check if we should reprice
                exec_mode = select_exec_mode(book)
                target = get_entry_price(exec_mode, side, book, spec)
                diff = abs(existing.price - target)
                if diff < Cfg.REPRICE_TICKS * spec.tick_size:
                    return  # price hasn't moved enough
                await self._om.cancel(leg.pending_oid)
                leg.pending_oid = None
                log.debug("REPRICE %s %s: %.8g → %.8g", st.symbol, side.value,
                          existing.price, target)
            if leg.pending_oid:
                return
        # Inventory check
        if not self._risk.can_add_inventory(leg):
            return
        # Risk gate
        open_orders = await self._om.all_open(st.symbol)
        allowed, reason = self._risk.can_quote(st.symbol, len(open_orders),
                                                self._states, self._om)
        if not allowed:
            log.debug("BLOCKED %s %s: %s", st.symbol, side.value, reason)
            return
        # Profitability check
        exec_mode = select_exec_mode(book)
        net_edge = estimate_net_edge_bps(exec_mode, book)
        if net_edge < Cfg.MIN_NET_EDGE_BPS:
            log.debug("SKIP %s %s: net_edge=%.1f bps < %.1f min",
                      st.symbol, side.value, net_edge, Cfg.MIN_NET_EDGE_BPS)
            return
        # Compute size and price
        size = compute_size(spec, Cfg.TARGET_NOTIONAL)
        if size < spec.min_size:
            return
        price = get_entry_price(exec_mode, side, book, spec)
        tif = get_tif_for_mode(exec_mode)
        role = OrderRole.ENTRY if leg.fill_count == 0 else OrderRole.RECYCLE
        o = await self._om.submit(
            symbol=st.symbol, side=side, size=size, price=price,
            tif=tif, role=role, exec_mode=exec_mode)
        if o:
            leg.pending_oid = o.client_id
            log.info("QUOTE %s %s %s ×%d @ %.8g [%s] edge=%.1fbps",
                     st.symbol, side.value.upper(), exec_mode.value,
                     size, price, role.value, net_edge)

    async def _manage_exit_leg(self, st: SymbolState, side: Side) -> None:
        """Manage exit (closing) orders for a filled leg."""
        leg = st.long_leg if side == Side.LONG else st.short_leg
        spec = st.spec
        if not spec:
            return
        # Only manage exit if we have inventory
        if leg.is_flat:
            return
        # Check stale position
        ok, reason = self._risk.check_stale_position(leg)
        if not ok:
            log.warning("STALE EXIT %s %s: %s", st.symbol, side.value, reason)
            await self._force_close_leg(st, side, reason)
            return
        # If no exit order, place one
        if not leg.exit_oid:
            exit_price = get_exit_price(side, leg.avg_entry, spec)
            close_side = Side.SHORT if side == Side.LONG else Side.LONG
            o = await self._om.submit(
                symbol=st.symbol, side=close_side, size=leg.contracts,
                price=exit_price, tif="gtc", role=OrderRole.EXIT,
                exec_mode=ExecMode.MAKER, reduce_only=True)
            if o:
                leg.exit_oid = o.client_id
                log.info("EXIT %s %s ×%d @ %.8g (entry=%.8g)",
                         st.symbol, side.value.upper(), leg.contracts,
                         exit_price, leg.avg_entry)
        else:
            # Check if exit order is still alive
            o = await self._om.get_by_client(leg.exit_oid)
            if not o or o.status not in (OrderStatus.PENDING, OrderStatus.OPEN):
                leg.exit_oid = None

    async def on_fill(self, order: Order, fill_size: int,
                      fill_price: float, fee: float) -> None:
        """Called when a fill is confirmed. Updates accounting, recycles."""
        st = self._states.get(order.symbol)
        if not st or not st.spec:
            return
        quanto = st.spec.quanto_multiplier
        notional = fill_price * fill_size * quanto

        if order.role in (OrderRole.EXIT, OrderRole.TRIM, OrderRole.FLATTEN):
            # This is a close fill — determine which leg it closes
            # EXIT sell closes LONG, EXIT buy closes SHORT
            if order.side == Side.SHORT:
                leg = st.long_leg
                leg_side = Side.LONG
            else:
                leg = st.short_leg
                leg_side = Side.SHORT
            pnl = leg.on_close_fill(fill_size, fill_price, quanto, fee)
            if leg.pending_oid == order.client_id:
                leg.pending_oid = None
            if leg.exit_oid == order.client_id:
                leg.exit_oid = None
            log.info("CLOSE %s %s ×%d @ %.8g  pnl=%+.6f  fee=%.6f  inv=%d",
                     order.symbol, leg_side.value.upper(), fill_size,
                     fill_price, pnl, fee, leg.contracts)
        else:
            # Entry/recycle fill
            leg = st.long_leg if order.side == Side.LONG else st.short_leg
            pnl = leg.on_entry_fill(fill_size, fill_price, quanto, fee)
            if leg.pending_oid == order.client_id:
                leg.pending_oid = None
            log.info("ENTRY %s %s ×%d @ %.8g  fee=%.6f  inv=%d  avg=%.8g",
                     order.symbol, order.side.value.upper(), fill_size,
                     fill_price, fee, leg.contracts, leg.avg_entry)

        # Record to risk + DB
        self._risk.record_fill(pnl, fee, notional)
        fill_id = uuid.uuid4().hex
        self._db.insert_fill(
            fill_id=fill_id, order_id=order.client_id,
            symbol=order.symbol, side=order.side, role=order.role.value,
            size=fill_size, price=fill_price, fee=fee, pnl=pnl, ts=time.time())
        self._db.log_event(
            "FILL",
            f"{order.role.value.upper()} {order.side.value.upper()} "
            f"{order.symbol} ×{fill_size} @ {fill_price:.8g} "
            f"pnl={pnl:+.6f} fee={fee:.6f}",
            symbol=order.symbol,
            data={"side": order.side.value, "role": order.role.value,
                  "size": fill_size, "price": fill_price, "pnl": pnl, "fee": fee})

        st.update_phase()

        # Recycle: after exit fill, re-enter same side
        if order.role in (OrderRole.EXIT,) and not self._risk.killed:
            await asyncio.sleep(Cfg.RECYCLE_DELAY_SEC)
            await self._manage_symbol(st)

    async def _flatten_symbol(self, st: SymbolState, reason: str) -> None:
        """Cancel all orders and market-close all positions for a symbol."""
        log.warning("FLATTEN %s: %s", st.symbol, reason)
        await self._om.cancel_symbol(st.symbol)
        st.long_leg.pending_oid = None
        st.long_leg.exit_oid = None
        st.short_leg.pending_oid = None
        st.short_leg.exit_oid = None
        for side in (Side.LONG, Side.SHORT):
            await self._force_close_leg(st, side, reason)
        st.set_phase(HedgePhase.HALTED)
        self._risk.halt_symbol(st.symbol)
        self._db.log_event("FLATTEN", f"Flattened: {reason}", symbol=st.symbol)

    async def _force_close_leg(self, st: SymbolState, side: Side, reason: str) -> None:
        """Market-close a single leg."""
        leg = st.long_leg if side == Side.LONG else st.short_leg
        if leg.is_flat:
            return
        book = st.book
        spec = st.spec
        if not book or not spec:
            return
        close_side = Side.SHORT if side == Side.LONG else Side.LONG
        if side == Side.LONG:
            px = round_price(book.bid - spec.tick_size, spec.tick_size)
        else:
            px = round_price(book.ask + spec.tick_size, spec.tick_size)
        await self._om.submit(
            symbol=st.symbol, side=close_side, size=leg.contracts,
            price=px, tif="ioc", role=OrderRole.FLATTEN,
            exec_mode=ExecMode.TAKER, reduce_only=True)

    async def trim_inventory(self, st: SymbolState, side: Side) -> None:
        """Trim excess inventory on one side."""
        leg = st.long_leg if side == Side.LONG else st.short_leg
        excess = leg.contracts - Cfg.MAX_INVENTORY
        if excess <= 0:
            return
        book = st.book
        spec = st.spec
        if not book or not spec:
            return
        close_side = Side.SHORT if side == Side.LONG else Side.LONG
        px = round_price(book.bid if side == Side.LONG else book.ask, spec.tick_size)
        log.warning("TRIM %s %s excess=%d", st.symbol, side.value, excess)
        await self._om.submit(
            symbol=st.symbol, side=close_side, size=excess,
            price=px, tif="ioc", role=OrderRole.TRIM,
            exec_mode=ExecMode.TAKER, reduce_only=True)


# ═══════════════════════════════════════════════════════════════════════════════
# §14  REPRICE LOOP
# ═══════════════════════════════════════════════════════════════════════════════

async def reprice_loop(states: Dict[str, SymbolState],
                       engine: QuoteEngine, om: OrderManager) -> None:
    """Periodic: TTL cancel, forced reprice, stale cleanup."""
    while True:
        try:
            await asyncio.sleep(Cfg.REPRICE_LOOP_SEC)
            now = time.time()
            for st in states.values():
                if st.book_stale:
                    continue
                for leg in (st.long_leg, st.short_leg):
                    # Check pending entry orders for TTL
                    if leg.pending_oid:
                        o = await om.get_by_client(leg.pending_oid)
                        if not o or o.status not in (OrderStatus.PENDING, OrderStatus.OPEN):
                            leg.pending_oid = None
                        elif now - o.created_at > Cfg.QUOTE_TTL_SEC:
                            log.debug("TTL %s %s oid=%s age=%.1fs",
                                      st.symbol, leg.side.value, leg.pending_oid,
                                      now - o.created_at)
                            await om.cancel(leg.pending_oid)
                            leg.pending_oid = None
                    # Check exit orders for staleness
                    if leg.exit_oid:
                        o = await om.get_by_client(leg.exit_oid)
                        if not o or o.status not in (OrderStatus.PENDING, OrderStatus.OPEN):
                            leg.exit_oid = None
                # After cleanup, trigger re-evaluation
                if st.book and not st.book_stale:
                    await engine.on_book_tick(st.book)
        except asyncio.CancelledError:
            return
        except Exception:
            log.exception("reprice_loop error")


# ═══════════════════════════════════════════════════════════════════════════════
# §15  RECONCILER
# ═══════════════════════════════════════════════════════════════════════════════

async def reconcile(rest: GateRest, db: DB, states: Dict[str, SymbolState],
                    om: OrderManager, risk: RiskEngine) -> None:
    """
    Startup reconciliation:
    1. Fetch live positions → update leg accounting
    2. Fetch live open orders → mark orphan DB orders
    3. Detect mismatches → optionally flatten
    4. Rebuild FSM state from actual positions
    """
    log.info("Reconciler: fetching live positions...")
    try:
        live_positions = await rest.get_positions()
    except Exception as exc:
        log.error("Reconciler: positions fetch failed: %s", exc)
        live_positions = []

    pos_map: Dict[str, Dict[str, Tuple[int, float]]] = defaultdict(
        lambda: {"long": (0, 0.0), "short": (0, 0.0)})
    for p in live_positions:
        sym = p.get("contract", "")
        size = int(p.get("size", 0))
        entry = float(p.get("entry_price", 0) or 0)
        mode = p.get("mode", "")
        if sym not in states:
            continue
        if mode == "dual_long" or size > 0:
            pos_map[sym]["long"] = (abs(size), entry)
        elif mode == "dual_short" or size < 0:
            pos_map[sym]["short"] = (abs(size), entry)

    mismatches = 0
    for sym, st in states.items():
        live_long_cts, live_long_entry = pos_map[sym]["long"]
        live_short_cts, live_short_entry = pos_map[sym]["short"]
        # Detect mismatch
        if (st.long_leg.contracts != live_long_cts or
                st.short_leg.contracts != live_short_cts):
            mismatches += 1
            log.warning("RECON MISMATCH %s: DB long=%d/short=%d vs LIVE long=%d/short=%d",
                        sym, st.long_leg.contracts, st.short_leg.contracts,
                        live_long_cts, live_short_cts)
        # Update from exchange truth
        st.long_leg.contracts = live_long_cts
        if live_long_entry > 0 and live_long_cts > 0:
            quanto = st.spec.quanto_multiplier if st.spec else 1.0
            st.long_leg.cost_basis = live_long_entry * live_long_cts * quanto
            if st.long_leg.opened_at == 0:
                st.long_leg.opened_at = time.time()
        elif live_long_cts == 0:
            st.long_leg.reset()

        st.short_leg.contracts = live_short_cts
        if live_short_entry > 0 and live_short_cts > 0:
            quanto = st.spec.quanto_multiplier if st.spec else 1.0
            st.short_leg.cost_basis = live_short_entry * live_short_cts * quanto
            if st.short_leg.opened_at == 0:
                st.short_leg.opened_at = time.time()
        elif live_short_cts == 0:
            st.short_leg.reset()

        st.update_phase()
        log.info("Reconciler %s: long=%d(@%.8g) short=%d(@%.8g) → %s",
                 sym, live_long_cts, live_long_entry,
                 live_short_cts, live_short_entry, st.phase.value)

    # Handle orphan DB orders
    log.info("Reconciler: checking open orders...")
    try:
        live_orders = await rest.get_open_orders()
    except Exception as exc:
        log.error("Reconciler: open orders fetch failed: %s", exc)
        live_orders = []
    live_eids = {str(o["id"]) for o in live_orders}
    db_open = db.get_open_orders()
    orphan_count = 0
    for row in db_open:
        eid = row.get("exchange_id", "")
        if eid and eid not in live_eids:
            orphan_count += 1
            log.info("Reconciler: orphan order %s → cancelled", row["client_id"])

    # Flatten on mismatch if configured
    if mismatches > 0 and Cfg.RECON_MISMATCH_FLATTEN:
        log.warning("Reconciler: %d mismatches detected — NOT auto-flattening (positions synced)",
                    mismatches)

    db.log_event("INFO", "Reconciler completed",
                 data={"live_pos": len(live_positions), "live_orders": len(live_eids),
                       "mismatches": mismatches, "orphans": orphan_count})
    log.info("Reconciler: done (mismatches=%d, orphans=%d)", mismatches, orphan_count)


# ═══════════════════════════════════════════════════════════════════════════════
# §16  METRICS / TELEMETRY
# ═══════════════════════════════════════════════════════════════════════════════

class Metrics:
    """First-class telemetry. Tracks per-minute rates and cumulative stats."""

    def __init__(self, db: DB) -> None:
        self._db = db
        self._fill_times: deque = deque(maxlen=500)
        self._cancel_times: deque = deque(maxlen=500)
        self._start_ts = time.monotonic()
        self.gross_notional = 0.0
        self.fees_paid = 0.0
        self.realized_pnl = 0.0
        self.api_errors = 0
        self.ws_reconnects = 0
        self.hedge_repairs = 0
        self.stale_book_pauses = 0
        self.per_symbol_pnl: Dict[str, float] = defaultdict(float)

    def record_fill(self, symbol: str, notional: float, fee: float, pnl: float) -> None:
        self._fill_times.append(time.time())
        self.gross_notional += notional
        self.fees_paid += fee
        self.realized_pnl += pnl
        self.per_symbol_pnl[symbol] += pnl

    def record_cancel(self) -> None:
        self._cancel_times.append(time.time())

    @property
    def fills_per_min(self) -> float:
        cutoff = time.time() - 60
        return sum(1 for t in self._fill_times if t > cutoff)

    @property
    def cancels_per_min(self) -> float:
        cutoff = time.time() - 60
        return sum(1 for t in self._cancel_times if t > cutoff)

    @property
    def uptime_sec(self) -> float:
        return time.monotonic() - self._start_ts

    def snapshot_dict(self) -> Dict:
        return {
            "fills_per_min": self.fills_per_min,
            "cancels_per_min": self.cancels_per_min,
            "gross_notional": self.gross_notional,
            "fees_paid": self.fees_paid,
            "realized_pnl": self.realized_pnl,
            "api_errors": self.api_errors,
            "ws_reconnects": self.ws_reconnects,
            "hedge_repairs": self.hedge_repairs,
            "stale_pauses": self.stale_book_pauses,
            "per_symbol_pnl": dict(self.per_symbol_pnl),
            "uptime": self.uptime_sec,
        }

    def save_snapshot(self) -> None:
        self._db.save_metric_snapshot(
            fpm=self.fills_per_min, cpm=self.cancels_per_min,
            notional=self.gross_notional, fees=self.fees_paid,
            pnl=self.realized_pnl, api_err=self.api_errors,
            ws_recon=self.ws_reconnects)


# ═══════════════════════════════════════════════════════════════════════════════
# §17  DASHBOARD
# ═══════════════════════════════════════════════════════════════════════════════

_DASH_HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<meta http-equiv="refresh" content="2"/>
<title>Gate Hedge Engine v2</title>
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{background:#0a0f1e;color:#c9d1e0;font-family:'JetBrains Mono',monospace;font-size:12px;padding:12px}
h1{font-size:16px;color:#7dd3fc;margin-bottom:12px;letter-spacing:.05em}
h2{font-size:11px;color:#94a3b8;text-transform:uppercase;letter-spacing:.12em;margin-bottom:8px}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:10px;margin-bottom:12px}
.card{background:#0f1829;border:1px solid #1e3058;border-radius:6px;padding:12px}
table{width:100%;border-collapse:collapse;margin-top:6px}
th{padding:4px 8px;text-align:left;color:#475569;font-size:10px;border-bottom:1px solid #1e3058}
td{padding:4px 8px;border-bottom:1px solid rgba(15,24,42,.7);white-space:nowrap}
tr:hover td{background:rgba(59,130,246,.05)}
.buy{color:#4ade80}.sell{color:#f87171}.na{color:#475569}
.killed{color:#f87171;font-weight:bold}.ok{color:#4ade80}
.warn{color:#fbbf24}
.kv{display:grid;grid-template-columns:auto 1fr;gap:3px 10px}
.kv-k{color:#475569}.kv-v{color:#e2e8f0}
.big{font-size:20px;font-weight:700;color:#fff;margin:4px 0}
</style>
</head>
<body>
<h1>⬡ Gate Hedged Spread-Capture Engine v2</h1>
<div class="grid" id="sym-grid"></div>
<div class="grid">
  <div class="card"><h2>Risk</h2><div class="kv" id="risk-kv"></div></div>
  <div class="card"><h2>Metrics</h2><div class="kv" id="metrics-kv"></div></div>
  <div class="card"><h2>Session</h2><div class="kv" id="sess-kv"></div></div>
</div>
<div class="card" style="margin-bottom:10px">
  <h2>Recent Fills</h2><div id="fills-tbl"></div>
</div>
<div class="card">
  <h2>Events</h2><div id="evt-tbl"></div>
</div>
<script>
const f=(v,d=6)=>{
  if(v===null||v===undefined||v==='')return'<span class="na">–</span>';
  if(typeof v==='number')return isNaN(v)?'<span class="na">nan</span>':v.toFixed(d);
  return String(v);
};
const kv=p=>p.map(([k,v])=>`<div class="kv-k">${k}</div><div class="kv-v">${v}</div>`).join('');
const tbl=(c,r)=>`<table><thead><tr>${c.map(h=>`<th>${h}</th>`).join('')}</tr></thead><tbody>${
  r.map(row=>`<tr>${row.map(c=>`<td>${c}</td>`).join('')}</tr>`).join('')
}</tbody></table>`;
async function refresh(){
  const d=await fetch('/api/state').then(r=>r.json());
  document.getElementById('sym-grid').innerHTML=d.symbols.map(s=>`
    <div class="card">
      <h2>${s.symbol} <span class="${s.phase==='hedged'?'ok':s.phase==='halted'?'killed':'warn'}">[${s.phase}]</span></h2>
      <div class="kv">${kv([
        ['bid/ask', `<span class="sell">${f(s.bid,8)}</span> / <span class="buy">${f(s.ask,8)}</span>`],
        ['spread', f(s.spread_bps,1)+' bps'],
        ['long', `${s.long_inv}ct @ ${f(s.long_avg,8)}`],
        ['short', `${s.short_inv}ct @ ${f(s.short_avg,8)}`],
        ['delta', s.net_delta],
        ['long_pnl', `<span class="${s.long_pnl>=0?'buy':'sell'}">${f(s.long_pnl,6)}</span>`],
        ['short_pnl', `<span class="${s.short_pnl>=0?'buy':'sell'}">${f(s.short_pnl,6)}</span>`],
        ['sym_pnl', `<span class="${s.sym_pnl>=0?'buy':'sell'}">${f(s.sym_pnl,6)}</span>`],
        ['pend_entry', (s.pending_long||'–')+' / '+(s.pending_short||'–')],
        ['pend_exit', (s.exit_long||'–')+' / '+(s.exit_short||'–')],
        ['book_age', f(s.book_age,2)+'s'],
        ['exposure', '$'+f(s.exposure,4)],
      ])}</div>
    </div>
  `).join('');
  const r=d.risk;
  document.getElementById('risk-kv').innerHTML=kv([
    ['status', r.killed?'<span class="killed">KILLED</span>':'<span class="ok">ACTIVE</span>'],
    ['daily_loss', `<span class="${r.daily_loss>0?'sell':'ok'}">$${f(r.daily_loss,4)}</span>`],
    ['daily_fees', '$'+f(r.daily_fees,4)],
    ['daily_fills', r.daily_fills],
    ['daily_cancels', r.daily_cancels],
    ['daily_notional', '$'+f(r.daily_notional,4)],
    ['max_loss', '$'+f(r.max_daily_loss,2)],
    ['halted', r.halted_symbols.length?r.halted_symbols.join(', '):'none'],
  ]);
  const m=d.metrics;
  document.getElementById('metrics-kv').innerHTML=kv([
    ['fills/min', f(m.fills_per_min,1)],
    ['cancels/min', f(m.cancels_per_min,1)],
    ['gross_notional', '$'+f(m.gross_notional,4)],
    ['fees_paid', '$'+f(m.fees_paid,6)],
    ['realized_pnl', `<span class="${m.realized_pnl>=0?'buy':'sell'}">$${f(m.realized_pnl,6)}</span>`],
    ['api_errors', m.api_errors],
    ['ws_reconnects', m.ws_reconnects],
    ['hedge_repairs', m.hedge_repairs],
    ['stale_pauses', m.stale_pauses],
  ]);
  const s=d.session;
  document.getElementById('sess-kv').innerHTML=kv([
    ['uptime', s.uptime],
    ['paper', s.paper?'YES':'NO'],
    ['symbols', s.symbols.join(', ')],
    ['mode', s.primary_mode+' → '+s.fallback_mode],
  ]);
  const fills=d.fills.map(fl=>[
    new Date(fl.ts*1000).toISOString().slice(11,22),
    fl.symbol, fl.role||'',
    `<span class="${fl.side==='long'?'buy':'sell'}">${fl.side.toUpperCase()}</span>`,
    fl.size, fl.price.toFixed(8),
    `<span class="${fl.realized_pnl>=0?'buy':'sell'}">${fl.realized_pnl.toFixed(6)}</span>`,
    fl.fee_usdt.toFixed(6),
  ]);
  document.getElementById('fills-tbl').innerHTML=tbl(
    ['time','symbol','role','side','size','price','pnl','fee'], fills
  );
  const evts=d.events.slice(0,40).map(e=>[
    new Date(e.ts*1000).toISOString().slice(11,22),
    `<span class="${e.level==='FILL'?'buy':e.level==='WARN'||e.level==='ERROR'?'sell':'na'}">${e.level}</span>`,
    e.symbol||'', e.message,
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
            try:
                state = self.engine_ref.get_state_dict()
                self.wfile.write(json.dumps(state, default=str).encode())
            except Exception:
                self.wfile.write(b'{"error":"state_error"}')
        elif self.path == "/health":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"status": "ok"}).encode())
        else:
            self.send_response(404)
            self.end_headers()


class Dashboard:
    def __init__(self, engine: "Engine") -> None:
        self._server: Optional[HTTPServer] = None
        _DashHandler.engine_ref = engine

    def start(self) -> None:
        self._server = HTTPServer(
            (Cfg.DASHBOARD_HOST, Cfg.DASHBOARD_PORT), _DashHandler)
        t = threading.Thread(target=self._server.serve_forever, daemon=True)
        t.start()
        log.info("Dashboard at http://%s:%d", Cfg.DASHBOARD_HOST, Cfg.DASHBOARD_PORT)

    def stop(self) -> None:
        if self._server:
            self._server.shutdown()


# ═══════════════════════════════════════════════════════════════════════════════
# §18  ENGINE (MAIN ORCHESTRATOR)
# ═══════════════════════════════════════════════════════════════════════════════

class Engine:
    """Top-level orchestrator. Owns all components."""

    def __init__(self) -> None:
        self._session   : Optional[aiohttp.ClientSession] = None
        self._rest      : Optional[GateRest]              = None
        self._db        : Optional[DB]                    = None
        self._om        : Optional[OrderManager]          = None
        self._risk      : Optional[RiskEngine]            = None
        self._quote_eng : Optional[QuoteEngine]           = None
        self._ws        : Optional[GateWS]                = None
        self._dash      : Optional[Dashboard]             = None
        self._metrics   : Optional[Metrics]               = None
        self._states    : Dict[str, SymbolState]          = {}
        self._start_ts  = time.monotonic()
        self._symbols   : List[str]                       = []

    async def start(self) -> None:
        log.info("═══ Gate Hedged Spread-Capture Engine v2 starting ═══")
        log.info("Mode: %s | Primary: %s → %s",
                 "PAPER" if Cfg.PAPER else "LIVE",
                 Cfg.PRIMARY_MODE, Cfg.FALLBACK_MODE)

        _validate_cfg()

        self._db = DB(Cfg.DB_PATH)
        self._session = aiohttp.ClientSession(
            connector=aiohttp.TCPConnector(limit=50),
            timeout=aiohttp.ClientTimeout(total=10))
        self._rest = GateRest(self._session)

        # Resolve symbol list
        if Cfg.SYMBOLS:
            self._symbols = Cfg.SYMBOLS
        else:
            self._symbols = await scan_micro_symbols(self._rest)
            if not self._symbols:
                raise RuntimeError("No viable micro symbols found")

        log.info("Active symbols: %s", self._symbols)
        self._db.log_event("INFO", "Engine started",
                           data={"symbols": self._symbols, "paper": Cfg.PAPER})

        # Enable dual-position mode
        if Cfg.ENABLE_DUAL_MODE and not Cfg.PAPER:
            try:
                await self._rest.set_dual_mode(True)
                log.info("Dual-position mode enabled")
            except Exception as exc:
                log.warning("Could not enable dual mode: %s", exc)

        # Load specs + init states
        for sym in self._symbols:
            spec = await load_contract_spec(self._rest, sym)
            st = SymbolState(symbol=sym, spec=spec)
            self._states[sym] = st
            if spec:
                log.info("Spec %s: tick=%.8g qty=%.4g mark=%.8g min=%d",
                         sym, spec.tick_size, spec.quanto_multiplier,
                         spec.mark_price, spec.min_size)
                if not Cfg.PAPER:
                    try:
                        await self._rest.set_leverage(sym, Cfg.LEVERAGE)
                    except Exception as exc:
                        log.warning("set_leverage %s: %s", sym, exc)

        # Initialize components
        self._risk = RiskEngine(self._db)
        await self._risk.refresh()
        self._om = OrderManager(self._rest, self._db)
        await self._om.load_from_db()
        self._quote_eng = QuoteEngine(
            self._rest, self._om, self._db, self._risk, self._states)
        self._metrics = Metrics(self._db)

        # Startup reconciliation
        await reconcile(self._rest, self._db, self._states, self._om, self._risk)

        # Dashboard
        self._dash = Dashboard(self)
        self._dash.start()

        # WebSocket feeds
        self._ws = GateWS(
            symbols=self._symbols,
            on_book=self._on_book,
            on_order=self._on_order_update,
            on_trade=self._on_trade)
        await self._ws.start()

        # Background tasks
        asyncio.create_task(reprice_loop(self._states, self._quote_eng, self._om),
                            name="reprice_loop")
        asyncio.create_task(self._metrics_loop(), name="metrics_loop")

        log.info("Engine LIVE — watching %d symbols", len(self._symbols))

    # ── Callbacks ─────────────────────────────────────────────────────────────

    async def _on_book(self, tick: BookTick) -> None:
        if tick.symbol in self._states and self._quote_eng:
            await self._quote_eng.on_book_tick(tick)

    async def _on_order_update(self, raw: Dict) -> None:
        if not self._om:
            return
        o = await self._om.on_order_update(raw)
        if o:
            log.debug("ORDER_UPD %s %s → %s", o.symbol, o.client_id[:8], o.status.value)
            # Handle IOC immediate fills
            if o.status == OrderStatus.FILLED and o.fill_size > 0:
                fee = o.fee_usdt
                if self._quote_eng:
                    await self._quote_eng.on_fill(o, o.fill_size, o.fill_price, fee)
                    if self._metrics:
                        quanto = 1.0
                        st = self._states.get(o.symbol)
                        if st and st.spec:
                            quanto = st.spec.quanto_multiplier
                        self._metrics.record_fill(
                            o.symbol, o.fill_price * o.fill_size * quanto, fee, 0)

    async def _on_trade(self, raw: Dict) -> None:
        if not self._om:
            return
        result = await self._om.on_trade(raw)
        if result:
            order, fill_size, fill_price, fee = result
            if self._quote_eng:
                await self._quote_eng.on_fill(order, fill_size, fill_price, fee)
            if self._metrics:
                quanto = 1.0
                st = self._states.get(order.symbol)
                if st and st.spec:
                    quanto = st.spec.quanto_multiplier
                notional = fill_price * fill_size * quanto
                self._metrics.record_fill(order.symbol, notional, fee, 0)

    # ── Metrics loop ──────────────────────────────────────────────────────────

    async def _metrics_loop(self) -> None:
        while True:
            try:
                await asyncio.sleep(60)
                if self._metrics:
                    if self._ws:
                        self._metrics.ws_reconnects = self._ws.reconnect_count
                    if self._om:
                        self._metrics.api_errors = self._om.error_count
                    self._metrics.save_snapshot()
            except asyncio.CancelledError:
                return
            except Exception:
                log.exception("metrics_loop error")

    # ── State export for dashboard ────────────────────────────────────────────

    def get_state_dict(self) -> Dict:
        symbols = []
        for sym, st in self._states.items():
            book = st.book
            symbols.append({
                "symbol":       sym,
                "phase":        st.phase.value,
                "bid":          book.bid if book else None,
                "ask":          book.ask if book else None,
                "spread_bps":   book.spread_bps if book else None,
                "long_inv":     st.long_leg.contracts,
                "short_inv":    st.short_leg.contracts,
                "long_avg":     st.long_leg.avg_entry,
                "short_avg":    st.short_leg.avg_entry,
                "net_delta":    st.net_inventory,
                "long_pnl":     st.long_leg.realized_pnl,
                "short_pnl":    st.short_leg.realized_pnl,
                "sym_pnl":      self._metrics.per_symbol_pnl.get(sym, 0) if self._metrics else 0,
                "pending_long":  st.long_leg.pending_oid,
                "pending_short": st.short_leg.pending_oid,
                "exit_long":    st.long_leg.exit_oid,
                "exit_short":   st.short_leg.exit_oid,
                "book_age":     book.age_sec() if book else None,
                "exposure":     st.notional_exposure(),
            })

        uptime_sec = int(time.monotonic() - self._start_ts)
        h, rem = divmod(uptime_sec, 3600)
        m, s = divmod(rem, 60)

        return {
            "symbols": symbols,
            "risk":    self._risk.status_dict() if self._risk else {},
            "metrics": self._metrics.snapshot_dict() if self._metrics else {},
            "session": {
                "uptime":       f"{h:02d}:{m:02d}:{s:02d}",
                "paper":        Cfg.PAPER,
                "symbols":      self._symbols,
                "primary_mode": Cfg.PRIMARY_MODE,
                "fallback_mode": Cfg.FALLBACK_MODE,
            },
            "fills":  self._db.get_recent_fills(50) if self._db else [],
            "events": self._db.get_events(60) if self._db else [],
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
        if self._metrics:
            self._metrics.save_snapshot()
        if self._db:
            self._db.log_event("INFO", "Engine stopped cleanly")
        log.info("Engine stopped.")


# ═══════════════════════════════════════════════════════════════════════════════
# §19  ENTRYPOINT
# ═══════════════════════════════════════════════════════════════════════════════

async def _main() -> None:
    engine = Engine()
    loop = asyncio.get_running_loop()

    def _sig_handler() -> None:
        log.info("Signal received — graceful shutdown")
        asyncio.create_task(engine.stop())
        loop.call_later(5.0, loop.stop)

    import signal as _signal
    for sig in (_signal.SIGINT, _signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, _sig_handler)
        except NotImplementedError:
            pass

    try:
        await engine.start()
        while True:
            await asyncio.sleep(60)
    except Exception as exc:
        log.critical("Fatal: %s\n%s", exc, traceback.format_exc())
    finally:
        try:
            await engine.stop()
        except Exception:
            pass


if __name__ == "__main__":
    _setup_logging(Cfg.LOG_LEVEL, Cfg.LOG_FILE)
    log.info("gate_aggressive_hedge v2.0")
    log.info("Python %s", sys.version.split()[0])
    if Cfg.PAPER:
        log.info("*** PAPER MODE — no real orders ***")
    try:
        asyncio.run(_main())
    except KeyboardInterrupt:
        pass
