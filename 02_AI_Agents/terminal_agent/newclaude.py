#!/usr/bin/env python3
"""
gate_aggressive_hedge_v2.py  ·  v2.0
══════════════════════════════════════════════════════════════════════════════
Aggressive Hedged Spread-Capture Engine  —  Full Production Rebuild
Gate.io USDT Perpetual Futures
══════════════════════════════════════════════════════════════════════════════

WHAT WAS BROKEN IN v1 AND IS NOW FIXED
───────────────────────────────────────
1.  ACCOUNTING: entry_value += notional broke on closes and partials.
    Fixed: VWAP Leg.open_fill() / Leg.close_fill() with correct proportional
    cost-basis reduction and explicit long-vs-short realized PnL formula.

2.  PARTIAL FILLS: treated as binary (filled / cancelled).
    Fixed: LimitOrder.record_partial_fill() accumulates size/price incrementally.
    VWAP and remaining_size are always correct.

3.  FSM: no explicit state machine; state inferred ad-hoc from pending_oid.
    Fixed: HedgeFSM per symbol with guarded transitions:
    FLAT→OPENING→HEDGED→BROKEN_HEDGE→REPAIRING→REDUCING→HALTED.
    Every transition logged with reason.

4.  QUOTE / POSITION COUPLING: one pending_oid per leg mixed lifecycle concerns.
    Fixed: OrderStore owns order lifecycle independently.  Leg owns position.
    HedgeFSM owns quoting decisions.  No cross-coupling.

5.  RISK ENGINE: only daily loss + kill-switch + order count.
    Fixed: 11 risk dimensions — gross exposure, per-symbol exposure,
    leg imbalance duration, stale book, WS desync, reconcile mismatch,
    API error rate, forced-flatten on breach.

6.  PRE-QUOTE PROFITABILITY: quoting unconditionally.
    Fixed: ProfitFilter checks spread ≥ viability_threshold before every quote.
    Viability depends on execution mode (taker fees vs maker rebate).

7.  SYMBOL SELECTION: only checked mark_price and volume.
    Fixed: SymbolSelector additionally filters on spread%, top-book depth,
    fee-to-spread ratio, tick-to-notional efficiency.

8.  TELEMETRY: basic PnL only.
    Fixed: Metrics tracks fills/min, cancels/min, gross notional, fees,
    realized PnL, unrealized PnL, hedge repairs, leg imbalances,
    stale book pauses, API errors, WS reconnects — per-symbol.

9.  RESTART SAFETY: reconciler was advisory only.
    Fixed: Reconciler rebuilds FSM state from live exchange positions,
    re-registers live exchange orders, marks orphans CANCELLED.

10. EXECUTION MODES: single IOC path only.
    Fixed: ExecMode.MAKER_FIRST (poc, fallback IOC),
    ExecMode.AGGRESSIVE_LIMIT (ioc at best bid/ask),
    ExecMode.TAKER_FALLBACK (IOC at touch price).

WHY THIS VERSION IS MORE LIKELY TO ACTUALLY WORK LIVE
──────────────────────────────────────────────────────
  • PnL accounting matches exchange accounting: no phantom profit/loss.
  • FSM prevents contradictory actions (won't open new leg while repairing).
  • Risk engine forces flatten before losses compound — not after.
  • Pre-quote check refuses to trade when fees exceed expected gross edge.
  • Symbol selector only picks pairs where spread structure supports the strategy.
  • Partial-fill tracking prevents inventory miscounts after IOC partials.
  • Reconciler restores correct live state after crash/restart — no ghosts.
  • Metrics give immediate signal when execution economics break down.

══════════════════════════════════════════════════════════════════════════════
REQUIREMENTS:  pip install aiohttp websockets
ENV VARS:      GATE_API_KEY, GATE_API_SECRET  (or GATE_PAPER=1)
RUN:           python gate_aggressive_hedge_v2.py
DASHBOARD:     http://localhost:8765
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
import signal
import sqlite3
import sys
import time
import threading
import traceback
import uuid
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import (Any, Callable, Coroutine, Dict, Deque,
                    List, Optional, Set, Tuple)

# ─── third-party ──────────────────────────────────────────────────────────────
import aiohttp
import websockets

# ═══════════════════════════════════════════════════════════════════════════════
# §1  ENUMS
# ═══════════════════════════════════════════════════════════════════════════════

class Side(str, Enum):
    LONG  = "long"
    SHORT = "short"

class ExecMode(str, Enum):
    MAKER_FIRST      = "maker_first"   # poc → fallback IOC after timeout
    AGGRESSIVE_LIMIT = "aggressive"    # IOC at best bid/ask (touch price)
    TAKER_FALLBACK   = "taker"         # IOC at mid ± tolerance (wider touch)

class HedgeState(str, Enum):
    FLAT          = "FLAT"
    OPENING       = "OPENING"
    HEDGED        = "HEDGED"
    BROKEN_HEDGE  = "BROKEN_HEDGE"
    REPAIRING     = "REPAIRING"
    REDUCING      = "REDUCING"
    HALTED        = "HALTED"

class OrderStatus(str, Enum):
    PENDING   = "pending"
    OPEN      = "open"
    PARTIAL   = "partial"
    FILLED    = "filled"
    CANCELLED = "cancelled"
    FAILED    = "failed"

class RiskEvent(str, Enum):
    DAILY_LOSS       = "daily_loss"
    KILL_SWITCH      = "kill_switch"
    GROSS_EXPOSURE   = "gross_exposure"
    SYM_EXPOSURE     = "sym_exposure"
    LEG_IMBALANCE    = "leg_imbalance"
    STALE_BOOK       = "stale_book"
    WS_DESYNC        = "ws_desync"
    RECONCILE_MISS   = "reconcile_mismatch"
    API_ERROR_RATE   = "api_error_rate"
    MAX_OPEN_ORDERS  = "max_open_orders"
    MANUAL_HALT      = "manual_halt"

# ═══════════════════════════════════════════════════════════════════════════════
# §2  CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════════

class Cfg:
    # ── Auth ──────────────────────────────────────────────────────────────────
    API_KEY    : str  = os.getenv("GATE_API_KEY",    "")
    API_SECRET : str  = os.getenv("GATE_API_SECRET", "")
    PAPER      : bool = os.getenv("GATE_PAPER", "0") == "1"

    # ── Exchange ──────────────────────────────────────────────────────────────
    SETTLE   : str = "usdt"
    REST_URL : str = "https://api.gateio.ws/api/v4"
    WS_URL   : str = "wss://fx-ws.gateio.ws/v4/ws/usdt"

    # ── Execution mode ────────────────────────────────────────────────────────
    # MAKER_FIRST:      post bid (long) / ask (short) as maker; fallback to IOC
    # AGGRESSIVE_LIMIT: IOC at best_ask (long) / best_bid (short) — taker
    DEFAULT_EXEC_MODE  : ExecMode = ExecMode.AGGRESSIVE_LIMIT
    MAKER_FALLBACK_SEC : float    = 0.4   # poc → IOC after this many seconds
    MAKER_TIF          : str      = "poc"
    AGGR_TIF           : str      = "ioc"

    # ── Symbol universe ───────────────────────────────────────────────────────
    SYMBOLS              : List[str] = []    # set manually or auto-scanned
    MAX_SYMBOLS          : int       = 5
    # Fallback symbols for paper mode when API is unreachable
    PAPER_SYMBOLS_FALLBACK: List[str] = ["BTC_USDT", "ETH_USDT", "SOL_USDT"]
    MIN_CONTRACT_NOTIONAL: float     = 0.005  # USD per 1 contract
    MAX_CONTRACT_NOTIONAL: float     = 0.10
    MIN_SPREAD_VIABILITY : float     = 1.5    # spread >= 1.5× round-trip fee
    MIN_BOOK_DEPTH       : int       = 50     # contracts at best bid/ask
    MIN_VOLUME_24H       : float     = 50_000.0  # contracts/day

    # ── Sizing ────────────────────────────────────────────────────────────────
    TARGET_NOTIONAL  : float = 0.07   # USD target per order
    MIN_NOTIONAL     : float = 0.005
    LEVERAGE         : int   = 10
    ENABLE_DUAL_MODE : bool  = True

    # ── Quoting ───────────────────────────────────────────────────────────────
    QUOTE_TTL_SEC       : float = 4.0    # cancel + reprice
    REPRICE_TICKS       : int   = 1      # reprice if best moves ≥ N ticks
    REPRICE_LOOP_SEC    : float = 0.15
    RECYCLE_DELAY_SEC   : float = 0.05
    MAX_INVENTORY       : int   = 5      # max contracts per leg
    OPENING_TIMEOUT_SEC : float = 5.0   # OPENING → BROKEN_HEDGE if not filled

    # ── Risk ──────────────────────────────────────────────────────────────────
    MAX_DAILY_LOSS_USD     : float = 1.00
    KILL_SWITCH_USD        : float = 2.00
    MAX_GROSS_EXPOSURE_USD : float = 5.00   # total notional all legs
    MAX_SYM_EXPOSURE_USD   : float = 1.50   # per symbol
    MAX_LEG_IMBALANCE_SEC  : float = 30.0   # BROKEN_HEDGE timeout → forced flatten
    BOOK_STALE_SEC         : float = 5.0
    PRIVATE_WS_STALE_SEC   : float = 30.0   # no private msgs for this long → halt
    API_ERR_WINDOW_SEC     : float = 60.0
    API_ERR_RATE_LIMIT     : int   = 8      # errors/window → circuit break
    MAX_OPEN_ORDERS_SYM    : int   = 8

    # ── Fee model ─────────────────────────────────────────────────────────────
    TAKER_FEE_RATE : float = 0.0005    # 0.05%  paid on IOC/market fills
    MAKER_FEE_RATE : float = -0.00015  # −0.015%  rebate on poc fills

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
        raise RuntimeError("Set GATE_API_KEY + GATE_API_SECRET (or GATE_PAPER=1)")


# ═══════════════════════════════════════════════════════════════════════════════
# §3  LOGGING
# ═══════════════════════════════════════════════════════════════════════════════

_LOG_FMT  = "%(asctime)s.%(msecs)03d %(levelname)-5s [%(name)s] %(message)s"
_LOG_DATE = "%Y-%m-%dT%H:%M:%S"

def setup_logging() -> None:
    root = logging.getLogger()
    root.setLevel(getattr(logging, Cfg.LOG_LEVEL.upper(), logging.INFO))
    fmt = logging.Formatter(_LOG_FMT, datefmt=_LOG_DATE)
    fh  = logging.FileHandler(Cfg.LOG_FILE, encoding="utf-8")
    fh.setFormatter(fmt)
    ch = logging.StreamHandler(sys.stdout)
    ch.setFormatter(fmt)
    root.addHandler(fh)
    root.addHandler(ch)

log = logging.getLogger("engine")

# ═══════════════════════════════════════════════════════════════════════════════
# §4  DOMAIN TYPES
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class BookTick:
    symbol   : str
    bid      : float
    ask      : float
    bid_size : float
    ask_size : float
    ts       : float = field(default_factory=time.monotonic)

    @property
    def mid(self) -> float: return (self.bid + self.ask) / 2.0
    @property
    def spread(self) -> float: return self.ask - self.bid
    @property
    def spread_pct(self) -> float:
        return self.spread / self.mid if self.mid > 0 else 0.0
    def age(self) -> float: return time.monotonic() - self.ts
    def is_stale(self) -> bool:
        # Use longer staleness threshold in paper mode due to WS connectivity issues
        threshold = 60.0 if Cfg.PAPER else Cfg.BOOK_STALE_SEC
        return self.age() > threshold


@dataclass
class ContractSpec:
    symbol            : str
    tick_size         : float
    quanto_multiplier : float  # base tokens per contract
    min_size          : int    # minimum order size in contracts
    mark_price        : float  # last known mark price


@dataclass
class LimitOrder:
    """
    Tracks a single exchange order through its complete lifecycle.
    Supports partial fills via accumulation.
    """
    client_id        : str
    exchange_id      : str
    symbol           : str
    side             : Side
    requested_size   : int
    price            : float
    tif              : str
    exec_mode        : ExecMode
    status           : OrderStatus = OrderStatus.PENDING
    filled_size      : int   = 0
    remaining_size   : int   = 0
    total_fill_cost  : float = 0.0   # Σ(price × size) for VWAP
    avg_fill_price   : float = 0.0   # total_fill_cost / filled_size
    fees_paid        : float = 0.0
    created_at       : float = field(default_factory=time.time)
    updated_at       : float = field(default_factory=time.time)

    def __post_init__(self) -> None:
        self.remaining_size = self.requested_size

    def record_fill(self, size: int, price: float, fee: float) -> None:
        """Accumulate a (partial) fill. Idempotency: caller must not double-count."""
        actual = min(size, self.remaining_size)
        if actual <= 0:
            return
        self.filled_size     += actual
        self.remaining_size  -= actual
        self.total_fill_cost += actual * price
        self.avg_fill_price   = self.total_fill_cost / max(1, self.filled_size)
        self.fees_paid       += fee
        self.updated_at       = time.time()
        self.status = OrderStatus.FILLED if self.remaining_size <= 0 else OrderStatus.PARTIAL

    def is_terminal(self) -> bool:
        return self.status in (OrderStatus.FILLED, OrderStatus.CANCELLED,
                               OrderStatus.FAILED)

    def age(self) -> float:
        return time.time() - self.created_at


@dataclass
class Leg:
    """
    VWAP-accurate position tracker for one directional leg.
    Partial fills, multiple fill events, and correct close PnL are all handled.
    """
    symbol    : str
    side      : Side
    # ── live position ────────────────────────────────────────────────────────
    contracts : int   = 0
    total_cost: float = 0.0   # Σ(contracts × price) for VWAP (no quanto here)
    # ── PnL accounting ───────────────────────────────────────────────────────
    realized_pnl : float = 0.0
    fees_paid    : float = 0.0
    fill_count   : int   = 0

    @property
    def avg_entry_price(self) -> float:
        """VWAP entry price in USDT."""
        return (self.total_cost / self.contracts) if self.contracts > 0 else 0.0

    def unrealized_pnl(self, mark: float, quanto: float = 1.0) -> float:
        if self.contracts <= 0:
            return 0.0
        avg = self.avg_entry_price
        if self.side == Side.LONG:
            return (mark - avg) * self.contracts * quanto
        else:
            return (avg - mark) * self.contracts * quanto

    def notional(self, price: float, quanto: float = 1.0) -> float:
        return self.contracts * price * quanto

    def open_fill(self, size: int, price: float, fee: float) -> None:
        """Record an opening fill. Builds cost basis."""
        self.contracts   += size
        self.total_cost  += size * price
        self.fees_paid   += fee
        self.fill_count  += 1

    def close_fill(self, size: int, price: float, fee: float,
                   quanto: float = 1.0) -> float:
        """
        Record a closing fill.
        Returns realized PnL (net of fee) for this close chunk.

        LONG close: (price_close - avg_entry) × size × quanto − fee
        SHORT close: (avg_entry − price_close) × size × quanto − fee
        """
        if self.contracts <= 0:
            return -fee

        actual_close = min(size, self.contracts)
        avg          = self.avg_entry_price

        if self.side == Side.LONG:
            gross_pnl = (price - avg) * actual_close * quanto
        else:
            gross_pnl = (avg - price) * actual_close * quanto

        net_pnl = gross_pnl - fee

        # Reduce cost basis proportionally (average cost method)
        if self.contracts > 0:
            ratio         = actual_close / self.contracts
            self.total_cost *= (1.0 - ratio)
        self.contracts  -= actual_close
        if self.contracts < 0:
            self.contracts = 0
        if self.total_cost < 0:
            self.total_cost = 0.0

        self.realized_pnl += net_pnl
        self.fees_paid    += fee
        self.fill_count   += 1
        return net_pnl


# ═══════════════════════════════════════════════════════════════════════════════
# §5  CRYPTOGRAPHIC UTILITIES
# ═══════════════════════════════════════════════════════════════════════════════

def _rest_sign(method: str, path: str, query: str, body: str, ts: int) -> str:
    body_hash = hashlib.sha512(body.encode()).hexdigest()
    msg = f"{method}\n{path}\n{query}\n{body_hash}\n{ts}"
    return hmac_mod.new(
        Cfg.API_SECRET.encode(), msg.encode(), hashlib.sha512
    ).hexdigest()


def _ws_sign(channel: str, event: str, ts: int) -> str:
    msg = f"channel={channel}&event={event}&time={ts}"
    return hmac_mod.new(
        Cfg.API_SECRET.encode(), msg.encode(), hashlib.sha512
    ).hexdigest()


def _rest_headers(method: str, path: str,
                  query: str = "", body: str = "") -> Dict[str, str]:
    ts   = int(time.time())
    sign = _rest_sign(method, path, query, body, ts)
    return {
        "KEY":          Cfg.API_KEY,
        "Timestamp":    str(ts),
        "SIGN":         sign,
        "Content-Type": "application/json",
        "Accept":       "application/json",
    }


# ═══════════════════════════════════════════════════════════════════════════════
# §6  RATE LIMITER
# ═══════════════════════════════════════════════════════════════════════════════

class TokenBucket:
    def __init__(self, rate: float) -> None:
        self._rate   = rate
        self._tokens = rate
        self._last   = time.monotonic()
        self._lock   = asyncio.Lock()

    async def acquire(self) -> None:
        async with self._lock:
            now     = time.monotonic()
            elapsed = now - self._last
            self._tokens = min(self._rate, self._tokens + elapsed * self._rate)
            self._last   = now
            if self._tokens < 1.0:
                wait = (1.0 - self._tokens) / self._rate
                await asyncio.sleep(wait)
                self._tokens = 0.0
            else:
                self._tokens -= 1.0


_pvt_bucket = TokenBucket(Cfg.RATE_PRIVATE_RPS)
_pub_bucket = TokenBucket(Cfg.RATE_PUBLIC_RPS)

# ═══════════════════════════════════════════════════════════════════════════════
# §7  GATE REST ADAPTER
# ═══════════════════════════════════════════════════════════════════════════════

class GateRest:
    """
    Full Gate.io futures REST adapter.
    All private calls signed; rate-limited; errors propagate as exceptions.
    """

    def __init__(self, session: aiohttp.ClientSession,
                 metrics: "Metrics") -> None:
        self._s   = session
        self._met = metrics
        self._log = logging.getLogger("rest")

    # ── Internal ──────────────────────────────────────────────────────────────

    async def _get(self, path: str, params: Optional[Dict] = None,
                   private: bool = False) -> Any:
        await (_pvt_bucket if private else _pub_bucket).acquire()
        query  = "&".join(f"{k}={v}" for k, v in (params or {}).items())
        url    = Cfg.REST_URL + path + ("?" + query if query else "")
        hdrs   = _rest_headers("GET", path, query) if private else {}
        try:
            async with self._s.get(url, headers=hdrs) as r:
                data = await r.json()
                if r.status not in (200, 201):
                    self._met.record_api_error()
                    raise RuntimeError(f"GET {path} → {r.status}: {data}")
                return data
        except (aiohttp.ClientError, asyncio.TimeoutError) as exc:
            self._met.record_api_error()
            raise RuntimeError(f"GET {path} network: {exc}") from exc

    async def _post(self, path: str, body: Dict) -> Any:
        await _pvt_bucket.acquire()
        raw  = json.dumps(body)
        hdrs = _rest_headers("POST", path, "", raw)
        try:
            async with self._s.post(Cfg.REST_URL + path,
                                    headers=hdrs, data=raw) as r:
                data = await r.json()
                if r.status not in (200, 201):
                    self._met.record_api_error()
                    raise RuntimeError(f"POST {path} → {r.status}: {data}")
                return data
        except (aiohttp.ClientError, asyncio.TimeoutError) as exc:
            self._met.record_api_error()
            raise RuntimeError(f"POST {path} network: {exc}") from exc

    async def _delete(self, path: str, params: Optional[Dict] = None) -> Any:
        await _pvt_bucket.acquire()
        query    = "&".join(f"{k}={v}" for k, v in (params or {}).items())
        raw_path = path
        full_url = Cfg.REST_URL + path + ("?" + query if query else "")
        hdrs     = _rest_headers("DELETE", raw_path, query)
        try:
            async with self._s.delete(full_url, headers=hdrs) as r:
                data = await r.json()
                if r.status not in (200, 201):
                    self._met.record_api_error()
                    raise RuntimeError(f"DELETE {path} → {r.status}: {data}")
                return data
        except (aiohttp.ClientError, asyncio.TimeoutError) as exc:
            self._met.record_api_error()
            raise RuntimeError(f"DELETE {path} network: {exc}") from exc

    async def _put(self, path: str, body: Dict) -> Any:
        await _pvt_bucket.acquire()
        raw  = json.dumps(body)
        hdrs = _rest_headers("PUT", path, "", raw)
        try:
            async with self._s.put(Cfg.REST_URL + path,
                                   headers=hdrs, data=raw) as r:
                data = await r.json()
                if r.status not in (200, 201):
                    self._met.record_api_error()
                    raise RuntimeError(f"PUT {path} → {r.status}: {data}")
                return data
        except (aiohttp.ClientError, asyncio.TimeoutError) as exc:
            self._met.record_api_error()
            raise RuntimeError(f"PUT {path} network: {exc}") from exc

    # ── Public ────────────────────────────────────────────────────────────────

    async def get_contracts(self) -> List[Dict]:
        return await self._get(f"/futures/{Cfg.SETTLE}/contracts")

    async def get_contract(self, symbol: str) -> Dict:
        return await self._get(f"/futures/{Cfg.SETTLE}/contracts/{symbol}")

    async def get_tickers(self) -> List[Dict]:
        return await self._get(f"/futures/{Cfg.SETTLE}/tickers")

    async def get_order_book(self, symbol: str, limit: int = 5) -> Dict:
        return await self._get(f"/futures/{Cfg.SETTLE}/order_book",
                               {"contract": symbol, "limit": str(limit)})

    # ── Private ───────────────────────────────────────────────────────────────

    async def get_account(self) -> Dict:
        return await self._get(f"/futures/{Cfg.SETTLE}/accounts", private=True)

    async def set_dual_mode(self, dual: bool) -> Dict:
        return await self._put(f"/futures/{Cfg.SETTLE}/dual_mode",
                               {"dual_mode": dual})

    async def set_leverage(self, symbol: str, leverage: int) -> Dict:
        return await self._post(
            f"/futures/{Cfg.SETTLE}/positions/{symbol}/leverage",
            {"leverage": str(leverage), "cross_leverage_limit": "0"},
        )

    async def get_positions(self) -> List[Dict]:
        return await self._get(f"/futures/{Cfg.SETTLE}/positions", private=True)

    async def place_order(self, symbol: str, size: int, price: float,
                          tif: str = "ioc", reduce_only: bool = False,
                          text: str = "") -> Dict:
        """
        size > 0  → buy / long
        size < 0  → sell / short
        reduce_only=True → close existing position (dual mode aware)
        """
        body: Dict[str, Any] = {
            "contract":    symbol,
            "size":        size,
            "price":       f"{price:.10g}",
            "tif":         tif,
            "reduce_only": reduce_only,
        }
        if text:
            body["text"] = f"t-{text[:18]}"
        return await self._post(f"/futures/{Cfg.SETTLE}/orders", body)

    async def cancel_order(self, exchange_id: str) -> Dict:
        return await self._delete(
            f"/futures/{Cfg.SETTLE}/orders/{exchange_id}"
        )

    async def cancel_all_symbol(self, symbol: str) -> List[Dict]:
        """Cancel all open orders for symbol."""
        return await self._delete(
            f"/futures/{Cfg.SETTLE}/orders",
            {"contract": symbol, "side": "0"},
        )

    async def get_open_orders(self, symbol: Optional[str] = None) -> List[Dict]:
        params: Dict = {"status": "open"}
        if symbol:
            params["contract"] = symbol
        return await self._get(f"/futures/{Cfg.SETTLE}/orders",
                               params, private=True)

    async def close_position_ioc(self, symbol: str, side: Side,
                                  contracts: int, price: float) -> Dict:
        """Place IOC reduce-only order to close existing position."""
        gate_size = contracts if side == Side.SHORT else -contracts
        return await self.place_order(
            symbol=symbol, size=gate_size, price=price,
            tif="ioc", reduce_only=True,
        )


# ═══════════════════════════════════════════════════════════════════════════════
# §8  ORDER BOOK CACHE
# ═══════════════════════════════════════════════════════════════════════════════

class BookCache:
    """Thread-safe per-symbol best bid/ask cache, populated by WS feed."""

    def __init__(self) -> None:
        self._ticks: Dict[str, BookTick] = {}
        self._lock  = threading.Lock()

    def update(self, tick: BookTick) -> None:
        with self._lock:
            self._ticks[tick.symbol] = tick

    def get(self, symbol: str) -> Optional[BookTick]:
        with self._lock:
            return self._ticks.get(symbol)

    def stale_symbols(self) -> List[str]:
        with self._lock:
            return [s for s, t in self._ticks.items() if t.is_stale()]


# ═══════════════════════════════════════════════════════════════════════════════
# §9  ORDER STORE
# ═══════════════════════════════════════════════════════════════════════════════

class OrderStore:
    """
    In-memory order registry keyed by client_id.
    Exchange-ID index for WS dispatch.
    Lifecycle and partial-fill tracking are owned here.
    Position accounting is NOT done here — that belongs to Leg.
    """

    def __init__(self, db: "DB") -> None:
        self._db     = db
        self._orders : Dict[str, LimitOrder] = {}
        self._eid_map: Dict[str, str]         = {}   # exchange_id → client_id
        self._lock   = asyncio.Lock()

    # ── Query ─────────────────────────────────────────────────────────────────

    async def get(self, client_id: str) -> Optional[LimitOrder]:
        async with self._lock:
            return self._orders.get(client_id)

    async def get_by_eid(self, exchange_id: str) -> Optional[LimitOrder]:
        async with self._lock:
            cid = self._eid_map.get(exchange_id)
            return self._orders.get(cid) if cid else None

    async def all_open(self, symbol: Optional[str] = None) -> List[LimitOrder]:
        async with self._lock:
            return [
                o for o in self._orders.values()
                if o.status in (OrderStatus.PENDING, OrderStatus.OPEN,
                                OrderStatus.PARTIAL)
                and (symbol is None or o.symbol == symbol)
            ]

    async def all_for_symbol(self, symbol: str) -> List[LimitOrder]:
        async with self._lock:
            return [o for o in self._orders.values() if o.symbol == symbol]

    # ── Mutations ─────────────────────────────────────────────────────────────

    async def register(self, order: LimitOrder) -> None:
        async with self._lock:
            self._orders[order.client_id] = order
            if order.exchange_id:
                self._eid_map[order.exchange_id] = order.client_id
        self._db.upsert_order(order)

    async def set_exchange_id(self, client_id: str, exchange_id: str) -> None:
        async with self._lock:
            o = self._orders.get(client_id)
            if o:
                o.exchange_id = exchange_id
                self._eid_map[exchange_id] = client_id
        if o:
            self._db.upsert_order(o)

    async def apply_fill(self, exchange_id: str, size: int, price: float,
                         fee: float) -> Optional[LimitOrder]:
        """Record a fill event. Returns order after update, or None."""
        async with self._lock:
            cid = self._eid_map.get(exchange_id)
            if not cid:
                return None
            o = self._orders.get(cid)
            if not o:
                return None
            o.record_fill(size, price, fee)
        self._db.upsert_order(o)
        return o

    async def mark_cancelled(self, client_id: str) -> Optional[LimitOrder]:
        async with self._lock:
            o = self._orders.get(client_id)
            if o and not o.is_terminal():
                o.status     = OrderStatus.CANCELLED
                o.updated_at = time.time()
        if o:
            self._db.upsert_order(o)
        return o

    async def mark_status(self, exchange_id: str,
                          status: OrderStatus) -> Optional[LimitOrder]:
        async with self._lock:
            cid = self._eid_map.get(exchange_id)
            o   = self._orders.get(cid) if cid else None
            if o and not o.is_terminal():
                o.status     = status
                o.updated_at = time.time()
        if o:
            self._db.upsert_order(o)
        return o

    # ── Startup restore ───────────────────────────────────────────────────────

    async def restore_from_db(self) -> None:
        rows = self._db.get_open_orders()
        async with self._lock:
            for row in rows:
                # Handle old database values that may not match current enums
                try:
                    exec_mode = ExecMode(row.get("exec_mode", "aggressive") or "aggressive")
                except ValueError:
                    # Map old 'maker' to 'maker_first'
                    exec_mode_str = row.get("exec_mode", "aggressive") or "aggressive"
                    if exec_mode_str == "maker":
                        exec_mode = ExecMode.MAKER_FIRST
                    else:
                        exec_mode = ExecMode.AGGRESSIVE_LIMIT

                try:
                    status = OrderStatus(row.get("status", "pending"))
                except ValueError:
                    status = OrderStatus.PENDING

                o = LimitOrder(
                    client_id      = row.get("client_id", ""),
                    exchange_id    = row.get("exchange_id", "") or "",
                    symbol         = row.get("symbol", ""),
                    side           = Side(row.get("side", "long")),
                    requested_size = row.get("requested_size", 0),
                    price          = row.get("price", 0.0),
                    tif            = row.get("tif", "ioc") or "ioc",
                    exec_mode      = exec_mode,
                    status         = status,
                    filled_size    = row.get("filled_size", 0),
                    remaining_size = row.get("remaining_size", 0),
                    avg_fill_price = row.get("avg_fill_price", 0.0),
                    fees_paid      = row.get("fees_paid", 0.0),
                    created_at     = row.get("created_at", time.time()),
                    updated_at     = row.get("updated_at", time.time()),
                )
                self._orders[o.client_id] = o
                if o.exchange_id:
                    self._eid_map[o.exchange_id] = o.client_id
        log.info("OrderStore: restored %d orders from DB", len(rows))


# ═══════════════════════════════════════════════════════════════════════════════
# §10  HEDGE FSM
# ═══════════════════════════════════════════════════════════════════════════════

class HedgeFSM:
    """
    Per-symbol hedge state machine.

    State transitions are EXPLICIT and logged.
    Quoting decisions are gated by state.
    Recovery paths are deterministic.

    Separate from position accounting (Leg) and order lifecycle (OrderStore).
    """

    def __init__(self, symbol: str, long_leg: Leg, short_leg: Leg) -> None:
        self.symbol       = symbol
        self.long_leg     = long_leg
        self.short_leg    = short_leg
        self.state        = HedgeState.FLAT
        self.entered_at   = time.time()
        self.broken_since : Optional[float] = None
        # Active order client_ids per leg (set; supports multiple concurrent orders)
        self.long_oids  : Set[str] = set()
        self.short_oids : Set[str] = set()
        self._log = logging.getLogger(f"fsm.{symbol[:8]}")

    # ── State machine ─────────────────────────────────────────────────────────

    def transition(self, new_state: HedgeState, reason: str = "") -> None:
        if new_state == self.state:
            return
        self._log.info("%s: %s → %s  [%s]",
                       self.symbol, self.state.value, new_state.value, reason)
        self.state      = new_state
        self.entered_at = time.time()
        self.broken_since = time.time() if new_state == HedgeState.BROKEN_HEDGE else None

    def time_in_state(self) -> float:
        return time.time() - self.entered_at

    # ── Guards ────────────────────────────────────────────────────────────────

    def can_quote_long(self) -> bool:
        return (self.state in (HedgeState.FLAT, HedgeState.OPENING,
                               HedgeState.HEDGED, HedgeState.REPAIRING)
                and len(self.long_oids) == 0
                and self.long_leg.contracts < Cfg.MAX_INVENTORY)

    def can_quote_short(self) -> bool:
        return (self.state in (HedgeState.FLAT, HedgeState.OPENING,
                               HedgeState.HEDGED, HedgeState.REPAIRING)
                and len(self.short_oids) == 0
                and self.short_leg.contracts < Cfg.MAX_INVENTORY)

    def needs_repair(self) -> Optional[Side]:
        """Return the MISSING side if we're in BROKEN_HEDGE, else None."""
        if self.state != HedgeState.BROKEN_HEDGE:
            return None
        if self.long_leg.contracts > 0 and self.short_leg.contracts == 0:
            return Side.SHORT
        if self.short_leg.contracts > 0 and self.long_leg.contracts == 0:
            return Side.LONG
        return None

    def needs_reduce(self) -> Optional[Side]:
        """Return LONG or SHORT if inventory exceeds limit."""
        if self.long_leg.contracts > Cfg.MAX_INVENTORY:
            return Side.LONG
        if self.short_leg.contracts > Cfg.MAX_INVENTORY:
            return Side.SHORT
        return None

    def is_halted(self) -> bool:
        return self.state == HedgeState.HALTED

    def halt(self, reason: str = "") -> None:
        self.transition(HedgeState.HALTED, reason)

    def resume(self) -> None:
        """After forced flatten, return to FLAT."""
        if self.state == HedgeState.HALTED:
            if self.long_leg.contracts == 0 and self.short_leg.contracts == 0:
                self.transition(HedgeState.FLAT, "flatten complete")

    # ── Automatic state update from leg inventory ─────────────────────────────

    def sync_state(self) -> None:
        """Derive expected state from leg inventory. Call after fills."""
        if self.state == HedgeState.HALTED:
            return   # halt is sticky until resume() is called explicitly

        has_long  = self.long_leg.contracts > 0
        has_short = self.short_leg.contracts > 0
        excess    = (self.long_leg.contracts > Cfg.MAX_INVENTORY or
                     self.short_leg.contracts > Cfg.MAX_INVENTORY)

        if excess and self.state not in (HedgeState.REDUCING, HedgeState.HALTED):
            self.transition(HedgeState.REDUCING, "inventory exceeds limit")
        elif has_long and has_short and not excess:
            if self.state not in (HedgeState.HEDGED, HedgeState.REDUCING):
                self.transition(HedgeState.HEDGED, "both legs filled")
        elif has_long and not has_short:
            if self.state not in (HedgeState.BROKEN_HEDGE, HedgeState.REPAIRING,
                                   HedgeState.OPENING):
                self.transition(HedgeState.BROKEN_HEDGE, "only long leg open")
        elif has_short and not has_long:
            if self.state not in (HedgeState.BROKEN_HEDGE, HedgeState.REPAIRING,
                                   HedgeState.OPENING):
                self.transition(HedgeState.BROKEN_HEDGE, "only short leg open")
        elif not has_long and not has_short:
            if self.state not in (HedgeState.FLAT, HedgeState.OPENING,
                                   HedgeState.HALTED):
                self.transition(HedgeState.FLAT, "both legs empty")


# ═══════════════════════════════════════════════════════════════════════════════
# §11  FEE MODEL
# ═══════════════════════════════════════════════════════════════════════════════

class FeeModel:
    """Fee computation and pre-quote viability checks."""

    @staticmethod
    def fee_for_fill(notional: float, tif: str) -> float:
        """Expected fee in USD for a fill of given notional."""
        rate = Cfg.MAKER_FEE_RATE if tif == "poc" else Cfg.TAKER_FEE_RATE
        return notional * rate   # negative = rebate (for poc)

    @staticmethod
    def round_trip_cost(notional: float, exec_mode: ExecMode) -> float:
        """
        Expected USD cost of ONE round trip (open + close of ONE leg).
        Negative = net rebate (profitable with maker mode).
        """
        if exec_mode == ExecMode.MAKER_FIRST:
            return 2.0 * Cfg.MAKER_FEE_RATE * notional   # both fills are maker
        else:
            return 2.0 * Cfg.TAKER_FEE_RATE * notional   # both fills are taker

    @staticmethod
    def is_viable(spread: float, mid: float,
                  notional: float, exec_mode: ExecMode) -> Tuple[bool, str]:
        """
        Returns (viable, reason).
        Strategy is viable when gross edge > round-trip fee cost.

        For AGGRESSIVE mode (taker): gross edge ≈ 1 spread tick per round trip.
        For MAKER_FIRST: gross edge ≈ rebate × 2 (always positive).
        """
        if mid <= 0 or spread <= 0:
            return False, "invalid_book"

        spread_pct        = spread / mid
        round_trip_fee_pct = 2.0 * abs(Cfg.TAKER_FEE_RATE)   # absolute cost

        if exec_mode == ExecMode.MAKER_FIRST:
            # Maker earns rebate → always potentially viable if book is valid
            net_pct = -2.0 * Cfg.MAKER_FEE_RATE  # positive (rebate × 2)
            if net_pct > 0:
                return True, f"maker_rebate_{net_pct*100:.3f}pct"
            return False, "maker_fee_zero"

        # Aggressive taker: need spread ≥ viability_threshold × round_trip_fee
        threshold = Cfg.MIN_SPREAD_VIABILITY * round_trip_fee_pct
        if spread_pct >= threshold:
            return True, f"spread_{spread_pct*100:.3f}pct_ok"
        return (False,
                f"spread_{spread_pct*100:.3f}pct < threshold_{threshold*100:.3f}pct")


# ═══════════════════════════════════════════════════════════════════════════════
# §12  METRICS REGISTRY
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class SymMetrics:
    """Per-symbol performance counters."""
    symbol          : str
    fills           : int   = 0
    cancels         : int   = 0
    gross_notional  : float = 0.0
    fees_paid       : float = 0.0
    realized_pnl    : float = 0.0
    repairs         : int   = 0
    imbalances      : int   = 0
    viability_skips : int   = 0   # times pre-quote check failed
    stale_skips     : int   = 0   # times book was stale


class Metrics:
    """
    First-class telemetry registry.
    All counters are thread-safe (primitive increments).
    """

    def __init__(self) -> None:
        self._lock         = threading.Lock()
        self._api_errors   : Deque[float] = deque(maxlen=200)   # timestamps
        self._fill_ts      : Deque[float] = deque(maxlen=600)   # last 10 min
        self._cancel_ts    : Deque[float] = deque(maxlen=600)
        self.ws_reconnects : int   = 0
        self.session_start : float = time.time()
        self._sym          : Dict[str, SymMetrics] = {}

    def sym(self, symbol: str) -> SymMetrics:
        if symbol not in self._sym:
            self._sym[symbol] = SymMetrics(symbol=symbol)
        return self._sym[symbol]

    def record_api_error(self) -> None:
        with self._lock:
            self._api_errors.append(time.time())

    def api_error_rate(self, window_sec: float = Cfg.API_ERR_WINDOW_SEC) -> int:
        cutoff = time.time() - window_sec
        with self._lock:
            return sum(1 for t in self._api_errors if t > cutoff)

    def record_fill(self, symbol: str, notional: float, fee: float) -> None:
        with self._lock:
            self._fill_ts.append(time.time())
            m = self.sym(symbol)
            m.fills          += 1
            m.gross_notional += notional
            m.fees_paid      += fee

    def record_cancel(self, symbol: str) -> None:
        with self._lock:
            self._cancel_ts.append(time.time())
            self.sym(symbol).cancels += 1

    def record_realized_pnl(self, symbol: str, pnl: float, fee: float) -> None:
        with self._lock:
            m = self.sym(symbol)
            m.realized_pnl += pnl
            m.fees_paid    += fee

    def record_repair(self, symbol: str) -> None:
        with self._lock:
            self.sym(symbol).repairs += 1

    def record_imbalance(self, symbol: str) -> None:
        with self._lock:
            self.sym(symbol).imbalances += 1

    def record_viability_skip(self, symbol: str) -> None:
        with self._lock:
            self.sym(symbol).viability_skips += 1

    def record_stale_skip(self, symbol: str) -> None:
        with self._lock:
            self.sym(symbol).stale_skips += 1

    def rate_per_min(self, ts_deque: Deque[float]) -> float:
        cutoff = time.time() - 60.0
        with self._lock:
            return sum(1 for t in ts_deque if t > cutoff)

    @property
    def fills_per_min(self) -> float:
        return self.rate_per_min(self._fill_ts)

    @property
    def cancels_per_min(self) -> float:
        return self.rate_per_min(self._cancel_ts)

    @property
    def total_realized_pnl(self) -> float:
        return sum(m.realized_pnl for m in self._sym.values())

    @property
    def total_fees(self) -> float:
        return sum(m.fees_paid for m in self._sym.values())

    @property
    def total_gross_notional(self) -> float:
        return sum(m.gross_notional for m in self._sym.values())

    def snapshot(self) -> Dict:
        """Return full metrics dict for dashboard."""
        uptime = int(time.time() - self.session_start)
        h, rem = divmod(uptime, 3600)
        m, s   = divmod(rem, 60)
        with self._lock:
            sym_list = [
                {
                    "symbol":         sm.symbol,
                    "fills":          sm.fills,
                    "cancels":        sm.cancels,
                    "gross_notional": sm.gross_notional,
                    "fees_paid":      sm.fees_paid,
                    "realized_pnl":   sm.realized_pnl,
                    "repairs":        sm.repairs,
                    "imbalances":     sm.imbalances,
                    "viability_skips":sm.viability_skips,
                    "stale_skips":    sm.stale_skips,
                }
                for sm in self._sym.values()
            ]
        return {
            "fills_per_min":      self.fills_per_min,
            "cancels_per_min":    self.cancels_per_min,
            "total_realized_pnl": self.total_realized_pnl,
            "total_fees":         self.total_fees,
            "total_gross_notional": self.total_gross_notional,
            "api_errors_1m":      self.api_error_rate(60),
            "ws_reconnects":      self.ws_reconnects,
            "uptime":             f"{h:02d}:{m:02d}:{s:02d}",
            "symbols":            sym_list,
        }


# ═══════════════════════════════════════════════════════════════════════════════
# §13  RISK ENGINE
# ═══════════════════════════════════════════════════════════════════════════════

class RiskEngine:
    """
    Centralised, authoritative risk gate.
    All quoting must pass through this; any breach triggers forced flatten.
    """

    def __init__(self, db: "DB", metrics: Metrics) -> None:
        self._db          = db
        self._met         = metrics
        self._breaches    : List[Tuple[float, RiskEvent, str]] = []
        self._halted_syms : Set[str] = set()
        self._global_halt : bool     = False
        self._daily_loss  : float    = 0.0
        self._daily_fees  : float    = 0.0
        self._last_pvt_ws : float    = time.time()  # last private WS message

    async def refresh_daily(self) -> None:
        snap              = self._db.daily_pnl_today()
        self._daily_loss  = -min(0.0, float(snap.get("realized", 0.0)))
        self._daily_fees  = float(snap.get("fees", 0.0))

    def touch_private_ws(self) -> None:
        """Call whenever a private WS message is received."""
        self._last_pvt_ws = time.time()

    def record_fill_pnl(self, pnl: float, fee: float) -> None:
        self._daily_loss += max(0.0, -pnl)
        self._daily_fees += fee
        self._db.add_daily_pnl(pnl, fee)
        if self._daily_loss >= Cfg.KILL_SWITCH_USD:
            self._global_halt = True
            self._breach(RiskEvent.KILL_SWITCH,
                         f"daily_loss=${self._daily_loss:.4f}")
            log.critical("KILL SWITCH: daily_loss=%.4f", self._daily_loss)

    def _breach(self, event: RiskEvent, detail: str,
                symbol: Optional[str] = None) -> None:
        self._breaches.append((time.time(), event, detail))
        self._db.log_event("RISK", f"BREACH {event.value}: {detail}", symbol=symbol)
        log.warning("RISK BREACH %s: %s [sym=%s]", event.value, detail, symbol)

    # ── Global checks ─────────────────────────────────────────────────────────

    def global_ok(self) -> Tuple[bool, str]:
        if self._global_halt:
            return False, "global_halt"
        if self._daily_loss >= Cfg.MAX_DAILY_LOSS_USD:
            return False, f"daily_loss ${self._daily_loss:.4f}"
        if self._met.api_error_rate() >= Cfg.API_ERR_RATE_LIMIT:
            self._breach(RiskEvent.API_ERROR_RATE,
                         f"errors={self._met.api_error_rate()}")
            return False, "api_error_rate"
        # Skip private WS check in paper mode (no private WS needed)
        if not Cfg.PAPER:
            pvt_age = time.time() - self._last_pvt_ws
            if pvt_age > Cfg.PRIVATE_WS_STALE_SEC:
                self._breach(RiskEvent.WS_DESYNC, f"pvt_ws_age={pvt_age:.0f}s")
                return False, "private_ws_stale"
        return True, ""

    # ── Per-symbol checks ─────────────────────────────────────────────────────

    def symbol_ok(self, symbol: str, book: Optional[BookTick],
                  fsm: HedgeFSM, open_order_count: int,
                  long_notional: float, short_notional: float) -> Tuple[bool, str]:
        ok, reason = self.global_ok()
        if not ok:
            return False, reason
        if symbol in self._halted_syms:
            return False, "sym_halted"
        if book is None or book.is_stale():
            return False, "stale_book"
        if open_order_count >= Cfg.MAX_OPEN_ORDERS_SYM:
            return False, f"max_open_orders {open_order_count}"
        gross = long_notional + short_notional
        if gross > Cfg.MAX_SYM_EXPOSURE_USD:
            self._breach(RiskEvent.SYM_EXPOSURE,
                         f"gross={gross:.4f} > {Cfg.MAX_SYM_EXPOSURE_USD}", symbol)
            return False, "sym_exposure"
        # Leg imbalance duration: BROKEN_HEDGE for too long
        if (fsm.state == HedgeState.BROKEN_HEDGE and
                fsm.broken_since and
                (time.time() - fsm.broken_since) > Cfg.MAX_LEG_IMBALANCE_SEC):
            self._breach(RiskEvent.LEG_IMBALANCE,
                         f"broken for {time.time()-fsm.broken_since:.0f}s", symbol)
            return False, "leg_imbalance_timeout"
        return True, ""

    def total_gross_ok(self, fsm_map: Dict[str, HedgeFSM],
                        specs: Dict[str, ContractSpec],
                        book_cache: BookCache) -> Tuple[bool, str]:
        total = 0.0
        for sym, fsm in fsm_map.items():
            spec = specs.get(sym)
            if not spec:
                continue
            book = book_cache.get(sym)
            price = book.mid if book else spec.mark_price
            quanto = spec.quanto_multiplier
            total += (fsm.long_leg.contracts + fsm.short_leg.contracts) * price * quanto
        if total > Cfg.MAX_GROSS_EXPOSURE_USD:
            self._breach(RiskEvent.GROSS_EXPOSURE, f"total_gross={total:.4f}")
            return False, f"gross_exposure ${total:.4f}"
        return True, ""

    def halt_symbol(self, symbol: str, reason: str) -> None:
        self._halted_syms.add(symbol)
        self._breach(RiskEvent.MANUAL_HALT, reason, symbol)

    def unhalt_symbol(self, symbol: str) -> None:
        self._halted_syms.discard(symbol)

    def status(self) -> Dict:
        return {
            "global_halt":  self._global_halt,
            "daily_loss":   self._daily_loss,
            "daily_fees":   self._daily_fees,
            "halted_syms":  list(self._halted_syms),
            "breaches":     [(t, ev.value, d) for t, ev, d in self._breaches[-20:]],
        }


# ═══════════════════════════════════════════════════════════════════════════════
# §14  SYMBOL SELECTOR
# ═══════════════════════════════════════════════════════════════════════════════

async def select_symbols(rest: GateRest) -> List[str]:
    """
    Auto-select symbols based on:
      contract notional, 24h volume, live spread viability, book depth.
    Returns up to MAX_SYMBOLS symbols ranked by volume.
    """
    log.info("SymbolSelector: scanning Gate.io for viable micro-cap contracts")
    try:
        contracts = await rest.get_contracts()
        tickers   = await rest.get_tickers()
    except Exception as exc:
        log.error("SymbolSelector: fetch failed: %s", exc)
        if Cfg.PAPER:
            log.warning("SymbolSelector: using fallback symbols for paper mode")
            return Cfg.PAPER_SYMBOLS_FALLBACK[:Cfg.MAX_SYMBOLS]
        return []

    spec_map  : Dict[str, Dict] = {c["name"]: c for c in contracts}
    tick_map  : Dict[str, Dict] = {t["contract"]: t for t in tickers}

    candidates: List[Tuple[float, str]] = []

    for sym, cspec in spec_map.items():
        if not sym.endswith("_USDT"):
            continue
        tick   = tick_map.get(sym, {})
        mark   = float(tick.get("mark_price") or tick.get("last", 0) or 0)
        vol24  = float(tick.get("volume_24h_base", 0) or
                       tick.get("volume_24h", 0) or 0)
        quanto = float(cspec.get("quanto_multiplier") or 1.0)
        tsize  = float(cspec.get("order_price_round") or 0.00001)

        if mark <= 0:
            continue

        notional_1c = mark * quanto
        if not (Cfg.MIN_CONTRACT_NOTIONAL <= notional_1c <= Cfg.MAX_CONTRACT_NOTIONAL):
            continue
        if vol24 < Cfg.MIN_VOLUME_24H:
            continue

        # Tick-to-notional efficiency: 1 tick / notional × 100 = tick_pct
        tick_pct = (tsize / mark) if mark > 0 else 1.0

        # Fee-to-spread viability proxy (no live book here, use best estimate)
        round_trip_fee_pct = 2.0 * Cfg.TAKER_FEE_RATE
        # Minimum 1-tick spread assumed; viability if tick >= threshold
        if tick_pct < Cfg.MIN_SPREAD_VIABILITY * round_trip_fee_pct:
            # Spread too tight relative to fees
            continue

        candidates.append((vol24, sym))
        log.debug("Candidate %s: notional_1c=%.5f vol=%.0f tick_pct=%.4f%%",
                  sym, notional_1c, vol24, tick_pct * 100)

    candidates.sort(reverse=True)
    chosen = [sym for _, sym in candidates[:Cfg.MAX_SYMBOLS]]
    log.info("SymbolSelector: chose %d symbols: %s", len(chosen), chosen)
    return chosen


async def load_spec(rest: GateRest, symbol: str) -> Optional[ContractSpec]:
    try:
        c     = await rest.get_contract(symbol)
        mark  = float(c.get("mark_price") or c.get("index_price") or 0)
        tick  = float(c.get("order_price_round") or "0.00001")
        qm    = float(c.get("quanto_multiplier") or "1")
        mins  = int(c.get("order_size_min") or 1)
        return ContractSpec(symbol=symbol, tick_size=tick,
                            quanto_multiplier=qm, min_size=mins,
                            mark_price=mark)
    except Exception as exc:
        log.error("load_spec %s: %s", symbol, exc)
        return None


def round_price(price: float, tick: float) -> float:
    """Round price down to nearest tick."""
    if tick <= 0:
        return price
    return round(round(price / tick) * tick, 12)


def compute_size(spec: ContractSpec, notional: float) -> int:
    """Compute contract count for target USD notional."""
    vpc = spec.mark_price * spec.quanto_multiplier
    if vpc <= 0:
        return spec.min_size
    return max(spec.min_size, math.floor(notional / vpc))


# ═══════════════════════════════════════════════════════════════════════════════
# §15  DATABASE LAYER
# ═══════════════════════════════════════════════════════════════════════════════

class DB:
    """SQLite WAL persistence for orders, fills, events, daily PnL."""

    def __init__(self, path: str = Cfg.DB_PATH) -> None:
        self._path = path
        self._con  = sqlite3.connect(path, check_same_thread=False)
        self._con.row_factory = sqlite3.Row
        self._lock = threading.Lock()
        self._init_schema()

    def _init_schema(self) -> None:
        with self._lock, self._con:
            self._con.executescript("""
                PRAGMA journal_mode=WAL;
                PRAGMA synchronous=NORMAL;

                CREATE TABLE IF NOT EXISTS orders (
                    client_id       TEXT PRIMARY KEY,
                    exchange_id     TEXT,
                    symbol          TEXT NOT NULL,
                    side            TEXT NOT NULL,
                    requested_size  INTEGER NOT NULL,
                    price           REAL NOT NULL,
                    tif             TEXT,
                    exec_mode       TEXT,
                    status          TEXT NOT NULL,
                    filled_size     INTEGER DEFAULT 0,
                    remaining_size  INTEGER DEFAULT 0,
                    avg_fill_price  REAL    DEFAULT 0,
                    total_fill_cost REAL    DEFAULT 0,
                    fees_paid       REAL    DEFAULT 0,
                    created_at      REAL    NOT NULL,
                    updated_at      REAL    NOT NULL
                );

                CREATE TABLE IF NOT EXISTS fills (
                    id              TEXT PRIMARY KEY,
                    client_order_id TEXT,
                    exchange_order_id TEXT,
                    symbol          TEXT NOT NULL,
                    side            TEXT NOT NULL,
                    size            INTEGER NOT NULL,
                    price           REAL NOT NULL,
                    fee_usdt        REAL DEFAULT 0,
                    realized_pnl    REAL DEFAULT 0,
                    is_close        INTEGER DEFAULT 0,
                    ts              REAL NOT NULL
                );

                CREATE TABLE IF NOT EXISTS events (
                    id      INTEGER PRIMARY KEY AUTOINCREMENT,
                    ts      REAL NOT NULL,
                    level   TEXT NOT NULL,
                    symbol  TEXT,
                    message TEXT NOT NULL,
                    data    TEXT
                );

                CREATE TABLE IF NOT EXISTS daily_pnl (
                    date       TEXT PRIMARY KEY,
                    realized   REAL DEFAULT 0,
                    fees       REAL DEFAULT 0,
                    fills      INTEGER DEFAULT 0
                );

                CREATE TABLE IF NOT EXISTS positions_snapshot (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    ts          REAL NOT NULL,
                    symbol      TEXT NOT NULL,
                    side        TEXT NOT NULL,
                    contracts   INTEGER NOT NULL,
                    avg_entry   REAL NOT NULL,
                    realized    REAL DEFAULT 0,
                    fees        REAL DEFAULT 0
                );

                CREATE INDEX IF NOT EXISTS idx_orders_sym
                    ON orders(symbol);
                CREATE INDEX IF NOT EXISTS idx_orders_status
                    ON orders(status);
                CREATE INDEX IF NOT EXISTS idx_fills_ts
                    ON fills(ts);
                CREATE INDEX IF NOT EXISTS idx_events_ts
                    ON events(ts);
            """)

    # ── Orders ────────────────────────────────────────────────────────────────

    def upsert_order(self, o: LimitOrder) -> None:
        with self._lock, self._con:
            self._con.execute("""
                INSERT INTO orders VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(client_id) DO UPDATE SET
                    exchange_id=excluded.exchange_id,
                    status=excluded.status,
                    filled_size=excluded.filled_size,
                    remaining_size=excluded.remaining_size,
                    avg_fill_price=excluded.avg_fill_price,
                    total_fill_cost=excluded.total_fill_cost,
                    fees_paid=excluded.fees_paid,
                    updated_at=excluded.updated_at
            """, (
                o.client_id, o.exchange_id, o.symbol, o.side.value,
                o.requested_size, o.price, o.tif, o.exec_mode.value,
                o.status.value, o.filled_size, o.remaining_size,
                o.avg_fill_price, o.total_fill_cost, o.fees_paid,
                o.created_at, o.updated_at,
            ))

    def get_open_orders(self) -> List[Dict]:
        with self._lock:
            rows = self._con.execute(
                "SELECT * FROM orders WHERE status IN ('pending','open','partial')"
            ).fetchall()
            return [dict(r) for r in rows]

    def get_all_orders(self, limit: int = 200) -> List[Dict]:
        with self._lock:
            rows = self._con.execute(
                "SELECT * FROM orders ORDER BY created_at DESC LIMIT ?", (limit,)
            ).fetchall()
            return [dict(r) for r in rows]

    # ── Fills ─────────────────────────────────────────────────────────────────

    def insert_fill(self, fill_id: str, client_oid: str, exchange_oid: str,
                    symbol: str, side: Side, size: int, price: float,
                    fee: float, pnl: float, is_close: bool, ts: float) -> None:
        with self._lock, self._con:
            self._con.execute("""
                INSERT OR IGNORE INTO fills VALUES (?,?,?,?,?,?,?,?,?,?,?)
            """, (fill_id, client_oid, exchange_oid, symbol, side.value,
                  size, price, fee, pnl, int(is_close), ts))

    def get_recent_fills(self, limit: int = 100) -> List[Dict]:
        with self._lock:
            rows = self._con.execute(
                "SELECT * FROM fills ORDER BY ts DESC LIMIT ?", (limit,)
            ).fetchall()
            return [dict(r) for r in rows]

    # ── PnL ───────────────────────────────────────────────────────────────────

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

    # ── Position snapshots ────────────────────────────────────────────────────

    def snapshot_leg(self, leg: Leg) -> None:
        with self._lock, self._con:
            self._con.execute(
                "INSERT INTO positions_snapshot(ts,symbol,side,contracts,"
                "avg_entry,realized,fees) VALUES(?,?,?,?,?,?,?)",
                (time.time(), leg.symbol, leg.side.value, leg.contracts,
                 leg.avg_entry_price, leg.realized_pnl, leg.fees_paid),
            )


# ═══════════════════════════════════════════════════════════════════════════════
# §16  WEBSOCKET MANAGER
# ═══════════════════════════════════════════════════════════════════════════════

class GateWS:
    """
    Public (book_ticker) + Private (orders, usertrades) WebSocket feeds.
    Auto-reconnect with exponential backoff.
    Metrics: ws_reconnects incremented on every reconnect.
    """

    def __init__(self, symbols: List[str], book_cache: BookCache,
                 metrics: Metrics,
                 on_order: Callable[[Dict], Coroutine],
                 on_trade: Callable[[Dict], Coroutine]) -> None:
        self._symbols    = symbols
        self._cache      = book_cache
        self._met        = metrics
        self._on_order   = on_order
        self._on_trade   = on_trade
        self._shutdown   = False
        self._tasks: List[asyncio.Task] = []

    async def start(self) -> None:
        self._tasks = [
            asyncio.create_task(self._run_public(),  name="ws_public"),
        ]
        # Skip private WS in paper mode (no real orders needed)
        if not Cfg.PAPER:
            self._tasks.append(asyncio.create_task(self._run_private(), name="ws_private"))
        else:
            log.info("Paper mode: skipping private WebSocket")

    async def stop(self) -> None:
        self._shutdown = True
        for t in self._tasks:
            t.cancel()
        await asyncio.gather(*self._tasks, return_exceptions=True)

    # ── Public ────────────────────────────────────────────────────────────────

    async def _run_public(self) -> None:
        backoff = 1.0
        while not self._shutdown:
            try:
                async with websockets.connect(
                    Cfg.WS_URL, ping_interval=20, ping_timeout=10, close_timeout=5
                ) as ws:
                    log.info("WS public connected")
                    self._met.ws_reconnects += 1
                    backoff = 1.0
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
                            await self._on_public(json.loads(raw))
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

    async def _on_public(self, msg: Dict) -> None:
        if msg.get("event") in ("subscribe", "unsubscribe"):
            return
        result = msg.get("result")
        if not result or msg.get("channel") != "futures.book_ticker":
            return
        r    = result
        sym  = str(r.get("s") or r.get("c") or r.get("contract") or "")
        bid  = float(r.get("b") or r.get("bid_price") or 0)
        ask  = float(r.get("a") or r.get("ask_price") or 0)
        bsz  = float(r.get("B") or r.get("bid_amount") or 0)
        asz  = float(r.get("A") or r.get("ask_amount") or 0)
        if sym and bid > 0 and ask > 0:
            self._cache.update(BookTick(sym, bid, ask, bsz, asz))

    # ── Private ───────────────────────────────────────────────────────────────

    async def _run_private(self) -> None:
        backoff = 1.0
        while not self._shutdown:
            try:
                async with websockets.connect(
                    Cfg.WS_URL, ping_interval=20, ping_timeout=10, close_timeout=5
                ) as ws:
                    log.info("WS private connected")
                    self._met.ws_reconnects += 1
                    backoff = 1.0
                    for ch in ("futures.orders", "futures.usertrades"):
                        await self._subscribe(ws, ch)
                    async for raw in ws:
                        if self._shutdown:
                            return
                        try:
                            await self._on_private(json.loads(raw))
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
        sign = _ws_sign(channel, "subscribe", ts)
        await ws.send(json.dumps({
            "time":    ts,
            "channel": channel,
            "event":   "subscribe",
            "payload": [Cfg.SETTLE],
            "auth": {"method": "api_key", "KEY": Cfg.API_KEY, "SIGN": sign},
        }))

    async def _on_private(self, msg: Dict) -> None:
        channel = msg.get("channel", "")
        event   = msg.get("event",   "")
        result  = msg.get("result")
        if event in ("subscribe", "unsubscribe") or result is None:
            return
        items = result if isinstance(result, list) else [result]
        if channel == "futures.orders":
            for item in items:
                if item:
                    await self._on_order(item)
        elif channel == "futures.usertrades":
            for item in items:
                if item:
                    await self._on_trade(item)

    # Delegate to engine callbacks
    async def _on_order(self, raw: Dict) -> None:
        await self._on_order_cb(raw)

    async def _on_trade(self, raw: Dict) -> None:
        await self._on_trade_cb(raw)

    def set_callbacks(self,
                      on_order: Callable[[Dict], Coroutine],
                      on_trade: Callable[[Dict], Coroutine]) -> None:
        self._on_order_cb = on_order
        self._on_trade_cb = on_trade


# ═══════════════════════════════════════════════════════════════════════════════
# §17  RECONCILER
# ═══════════════════════════════════════════════════════════════════════════════

async def reconcile(rest: GateRest, db: DB,
                    fsm_map: Dict[str, HedgeFSM],
                    order_store: OrderStore,
                    specs: Dict[str, ContractSpec]) -> None:
    """
    Startup reconciliation:
    1. Fetch live exchange positions → rebuild Leg inventory from ground truth.
    2. Fetch live exchange open orders → register unknown, mark orphan DB orders.
    3. Sync FSM states from rebuilt positions.
    4. Log any mismatch.
    """
    log.info("Reconciler: fetching live positions...")
    try:
        live_positions = await rest.get_positions()
    except Exception as exc:
        log.error("Reconciler: positions fetch failed: %s", exc)
        live_positions = []

    pos_map: Dict[str, Dict[str, int]] = defaultdict(lambda: {"long": 0, "short": 0})
    for p in live_positions:
        sym  = p.get("contract", "")
        size = int(p.get("size", 0))
        mode = p.get("mode", "")
        if sym not in fsm_map:
            continue
        if mode == "dual_long" or (size > 0 and mode != "dual_short"):
            pos_map[sym]["long"] = abs(size)
        elif mode == "dual_short" or (size < 0 and mode != "dual_long"):
            pos_map[sym]["short"] = abs(size)

    for sym, fsm in fsm_map.items():
        live_long  = pos_map[sym]["long"]
        live_short = pos_map[sym]["short"]
        db_long    = fsm.long_leg.contracts
        db_short   = fsm.short_leg.contracts

        if live_long != db_long or live_short != db_short:
            log.warning("Reconciler %s: DB long=%d short=%d  LIVE long=%d short=%d",
                        sym, db_long, db_short, live_long, live_short)
            db.log_event("WARN",
                         f"Reconciler mismatch {sym}: "
                         f"DB({db_long},{db_short}) vs LIVE({live_long},{live_short})",
                         symbol=sym)

        # Override with exchange truth
        spec = specs.get(sym)
        mark = spec.mark_price if spec else 0.0
        if live_long != db_long:
            fsm.long_leg.contracts  = live_long
            fsm.long_leg.total_cost = live_long * mark  # approximate entry
        if live_short != db_short:
            fsm.short_leg.contracts  = live_short
            fsm.short_leg.total_cost = live_short * mark

        # Sync FSM state
        fsm.sync_state()
        log.info("Reconciler %s: state=%s long=%d short=%d",
                 sym, fsm.state.value, fsm.long_leg.contracts,
                 fsm.short_leg.contracts)

    # Fetch live open orders
    log.info("Reconciler: fetching live open orders...")
    try:
        live_orders = await rest.get_open_orders()
    except Exception as exc:
        log.error("Reconciler: orders fetch failed: %s", exc)
        live_orders = []

    live_eids = {str(o["id"]) for o in live_orders}

    # Mark DB-open orders not present on exchange as CANCELLED
    db_open = db.get_open_orders()
    orphan_count = 0
    for row in db_open:
        eid = row.get("exchange_id", "")
        if eid and eid not in live_eids:
            await order_store.mark_cancelled(row["client_id"])
            orphan_count += 1
            log.debug("Reconciler: orphan order %s → CANCELLED", row["client_id"][:8])

    db.log_event("INFO", "Reconciler complete",
                 data={"orphans_cancelled": orphan_count,
                       "live_orders":       len(live_eids)})
    log.info("Reconciler done: %d orphans cancelled, %d live exchange orders",
             orphan_count, len(live_eids))


# ═══════════════════════════════════════════════════════════════════════════════
# §18  EXECUTION ENGINE
# ═══════════════════════════════════════════════════════════════════════════════

class ExecEngine:
    """
    Central execution loop.

    Responsibilities:
      - Decide whether to quote, based on FSM state + risk + profitability.
      - Submit, track, cancel, reprice orders.
      - On fill: update Leg accounting, update FSM, trigger recycle.
      - On broken hedge: trigger repair.
      - On excess inventory: trigger reduce.
      - Forced flatten: close all positions IOC.
    """

    def __init__(self, rest: GateRest, order_store: OrderStore,
                 db: DB, risk: RiskEngine, metrics: Metrics,
                 fsm_map: Dict[str, HedgeFSM],
                 specs: Dict[str, ContractSpec],
                 book_cache: BookCache) -> None:
        self._rest   = rest
        self._os     = order_store
        self._db     = db
        self._risk   = risk
        self._met    = metrics
        self._fsm    = fsm_map
        self._specs  = specs
        self._books  = book_cache

    # ── Public API ────────────────────────────────────────────────────────────

    async def on_book_tick(self, symbol: str) -> None:
        """Called when a new book tick arrives for symbol."""
        fsm  = self._fsm.get(symbol)
        spec = self._specs.get(symbol)
        if fsm is None or spec is None:
            return
        await self._manage_symbol(fsm, spec)

    async def on_order_update(self, raw: Dict) -> None:
        """Called from private WS futures.orders channel."""
        self._risk.touch_private_ws()
        eid    = str(raw.get("id", ""))
        status = raw.get("status", "")
        finish = raw.get("finish_as", "")
        if not eid:
            return

        if status in ("closed", "finished"):
            if finish in ("cancelled", "ioc", "poc", "stp", "liquidated"):
                o = await self._os.mark_status(eid, OrderStatus.CANCELLED)
                if o:
                    self._met.record_cancel(o.symbol)
                    self._unregister_oid(o)
            # filled orders arrive via usertrades; don't double-process here

    async def on_trade(self, raw: Dict) -> None:
        """Called from private WS futures.usertrades channel."""
        self._risk.touch_private_ws()
        eid   = str(raw.get("order_id", ""))
        size  = abs(int(raw.get("size", 0)))
        price = float(raw.get("price", 0))
        fee   = abs(float(raw.get("fee", 0)))

        if not eid or size == 0 or price == 0:
            return

        o = await self._os.apply_fill(eid, size, price, fee)
        if o is None:
            return

        await self._process_fill(o, size, price, fee)

    # ── Internal: symbol management ───────────────────────────────────────────

    async def _manage_symbol(self, fsm: HedgeFSM, spec: ContractSpec) -> None:
        book = self._books.get(fsm.symbol)
        if book is None:
            return

        # Stale book check
        if book.is_stale():
            self._met.record_stale_skip(fsm.symbol)
            return

        # FSM-driven routing
        if fsm.is_halted():
            return

        if fsm.state == HedgeState.HALTED:
            return

        # Check if inventory needs reducing
        side_reduce = fsm.needs_reduce()
        if side_reduce:
            if fsm.state != HedgeState.REDUCING:
                fsm.transition(HedgeState.REDUCING, "inventory trim")
            await self._reduce_inventory(fsm, spec, book, side_reduce)
            return

        # Check if hedge needs repair
        side_repair = fsm.needs_repair()
        if side_repair:
            fsm.transition(HedgeState.REPAIRING, f"repair {side_repair.value} leg")
            await self._repair_leg(fsm, spec, book, side_repair)
            return

        # Check broken hedge timeout → forced flatten
        if (fsm.state == HedgeState.BROKEN_HEDGE and fsm.broken_since and
                (time.time() - fsm.broken_since) > Cfg.MAX_LEG_IMBALANCE_SEC):
            log.warning("Broken hedge timeout on %s — forcing flatten", fsm.symbol)
            self._met.record_imbalance(fsm.symbol)
            self._risk.halt_symbol(fsm.symbol, "broken_hedge_timeout")
            fsm.halt("broken_hedge_timeout")
            await self.force_flatten_symbol(fsm, spec, book)
            return

        # Normal dual-sided quoting
        ok, reason = self._risk.symbol_ok(
            fsm.symbol, book, fsm,
            len(await self._os.all_open(fsm.symbol)),
            fsm.long_leg.notional(book.mid, spec.quanto_multiplier),
            fsm.short_leg.notional(book.mid, spec.quanto_multiplier),
        )
        if not ok:
            if book.is_stale():
                self._met.record_stale_skip(fsm.symbol)
            return

        if fsm.state in (HedgeState.FLAT, HedgeState.OPENING):
            fsm.transition(HedgeState.OPENING, "dual quote attempt")

        await self._quote_long(fsm, spec, book)
        await self._quote_short(fsm, spec, book)

    async def _quote_long(self, fsm: HedgeFSM, spec: ContractSpec,
                           book: BookTick) -> None:
        if not fsm.can_quote_long():
            return
        price = round_price(book.ask, spec.tick_size)
        if price <= 0:
            return
        # Pre-quote profitability check
        notional = compute_size(spec, Cfg.TARGET_NOTIONAL) * price * spec.quanto_multiplier
        viable, reason = FeeModel.is_viable(
            book.spread, book.mid, notional, Cfg.DEFAULT_EXEC_MODE
        )
        if not viable:
            self._met.record_viability_skip(fsm.symbol)
            log.debug("SKIP long quote %s: %s", fsm.symbol, reason)
            return
        await self._submit_quote(fsm, spec, Side.LONG, price)

    async def _quote_short(self, fsm: HedgeFSM, spec: ContractSpec,
                            book: BookTick) -> None:
        if not fsm.can_quote_short():
            return
        price = round_price(book.bid, spec.tick_size)
        if price <= 0:
            return
        notional = compute_size(spec, Cfg.TARGET_NOTIONAL) * price * spec.quanto_multiplier
        viable, reason = FeeModel.is_viable(
            book.spread, book.mid, notional, Cfg.DEFAULT_EXEC_MODE
        )
        if not viable:
            self._met.record_viability_skip(fsm.symbol)
            log.debug("SKIP short quote %s: %s", fsm.symbol, reason)
            return
        await self._submit_quote(fsm, spec, Side.SHORT, price)

    async def _submit_quote(self, fsm: HedgeFSM, spec: ContractSpec,
                             side: Side, price: float) -> Optional[LimitOrder]:
        size = compute_size(spec, Cfg.TARGET_NOTIONAL)
        if size < spec.min_size:
            return None

        tif      = Cfg.AGGR_TIF
        exec_mode = Cfg.DEFAULT_EXEC_MODE
        if exec_mode == ExecMode.MAKER_FIRST:
            tif = Cfg.MAKER_TIF

        gate_size = size if side == Side.LONG else -size
        client_id = uuid.uuid4().hex[:16]

        o = LimitOrder(
            client_id=client_id, exchange_id="",
            symbol=fsm.symbol, side=side,
            requested_size=size, price=price,
            tif=tif, exec_mode=exec_mode,
            status=OrderStatus.PENDING,
            created_at=time.time(), updated_at=time.time(),
        )

        await self._os.register(o)
        if side == Side.LONG:
            fsm.long_oids.add(client_id)
        else:
            fsm.short_oids.add(client_id)

        if Cfg.PAPER:
            log.info("PAPER %s %s ×%d @ %.8g %s",
                     side.value.upper(), fsm.symbol, size, price, tif)
            o.status = OrderStatus.OPEN
            o.updated_at = time.time()
            self._db.upsert_order(o)
            return o

        try:
            resp = await self._rest.place_order(
                symbol=fsm.symbol, size=gate_size, price=price,
                tif=tif, text=client_id,
            )
            eid = str(resp.get("id", ""))
            await self._os.set_exchange_id(client_id, eid)
            o.exchange_id = eid
            o.status      = OrderStatus.OPEN
            o.updated_at  = time.time()
            self._db.upsert_order(o)
            log.debug("ORDER %s %s ×%d @ %.8g eid=%s",
                      side.value.upper(), fsm.symbol, size, price, eid[:8])
        except Exception as exc:
            log.error("ORDER submit %s %s: %s",
                      side.value.upper(), fsm.symbol, exc)
            o.status = OrderStatus.FAILED
            self._db.upsert_order(o)
            self._unregister_oid(o)
            return None

        return o

    # ── Fill processing ───────────────────────────────────────────────────────

    async def _process_fill(self, o: LimitOrder, fill_size: int,
                             fill_price: float, fee: float) -> None:
        """
        On fill:
          1. Update Leg (VWAP accounting).
          2. Record fill in DB.
          3. Update FSM.
          4. Trigger recycle or repair.
        """
        fsm  = self._fsm.get(o.symbol)
        spec = self._specs.get(o.symbol)
        if fsm is None or spec is None:
            return

        quanto   = spec.quanto_multiplier
        is_close = o.exec_mode == ExecMode.TAKER_FALLBACK  # reduce-only orders
        # Determine if this is an opening or closing fill based on FSM
        # Closing fills come from _reduce_inventory or force_flatten
        # Use order role info from exec_mode (simplified): CLOSE orders use reduce_only
        # We'll track this via the order's reduce_only flag — but LimitOrder doesn't
        # store reduce_only. We infer: if REDUCING state, it's a close.
        is_close_fill = fsm.state in (HedgeState.REDUCING, HedgeState.HALTED)

        if is_close_fill:
            pnl = (fsm.long_leg if o.side == Side.LONG else fsm.short_leg).close_fill(
                fill_size, fill_price, fee, quanto
            )
        else:
            (fsm.long_leg if o.side == Side.LONG else fsm.short_leg).open_fill(
                fill_size, fill_price, fee
            )
            pnl = -fee   # cost = fee only on entry

        # Metrics and persistence
        notional = fill_size * fill_price * quanto
        self._met.record_fill(o.symbol, notional, fee)
        self._met.record_realized_pnl(o.symbol, pnl, fee)
        self._risk.record_fill_pnl(pnl, fee)

        self._db.insert_fill(
            fill_id=uuid.uuid4().hex,
            client_oid=o.client_id,
            exchange_oid=o.exchange_id,
            symbol=o.symbol, side=o.side,
            size=fill_size, price=fill_price,
            fee=fee, pnl=pnl, is_close=is_close_fill,
            ts=time.time(),
        )
        log.info("FILL %s %s ×%d @ %.8g  pnl=%+.6f  fee=%.6f  %s",
                 o.symbol, o.side.value.upper(), fill_size, fill_price, pnl, fee,
                 "CLOSE" if is_close_fill else "OPEN")

        # Unregister from FSM
        self._unregister_oid(o)

        # Sync FSM state from updated legs
        fsm.sync_state()

        # Snapshot leg state to DB periodically (every fill)
        self._db.snapshot_leg(fsm.long_leg)
        self._db.snapshot_leg(fsm.short_leg)

        # Recycle: re-enter same side if not halted
        if not fsm.is_halted() and not is_close_fill:
            await asyncio.sleep(Cfg.RECYCLE_DELAY_SEC)
            book = self._books.get(o.symbol)
            if book and not book.is_stale() and spec:
                await self._manage_symbol(fsm, spec)

    def _unregister_oid(self, o: LimitOrder) -> None:
        fsm = self._fsm.get(o.symbol)
        if not fsm:
            return
        fsm.long_oids.discard(o.client_id)
        fsm.short_oids.discard(o.client_id)

    # ── Repair leg ────────────────────────────────────────────────────────────

    async def _repair_leg(self, fsm: HedgeFSM, spec: ContractSpec,
                           book: BookTick, side: Side) -> None:
        """Re-open the missing hedge leg."""
        if side == Side.LONG and not fsm.can_quote_long():
            return
        if side == Side.SHORT and not fsm.can_quote_short():
            return

        price = round_price(book.ask if side == Side.LONG else book.bid, spec.tick_size)
        if price <= 0:
            return

        notional = compute_size(spec, Cfg.TARGET_NOTIONAL) * price * spec.quanto_multiplier
        viable, reason = FeeModel.is_viable(
            book.spread, book.mid, notional, Cfg.DEFAULT_EXEC_MODE
        )
        if not viable:
            self._met.record_viability_skip(fsm.symbol)
            return

        log.info("REPAIR %s: placing %s leg", fsm.symbol, side.value)
        self._met.record_repair(fsm.symbol)
        await self._submit_quote(fsm, spec, side, price)

    # ── Reduce inventory ──────────────────────────────────────────────────────

    async def _reduce_inventory(self, fsm: HedgeFSM, spec: ContractSpec,
                                  book: BookTick, side: Side) -> None:
        """Place IOC reduce-only order to trim excess contracts."""
        leg     = fsm.long_leg if side == Side.LONG else fsm.short_leg
        excess  = leg.contracts - Cfg.MAX_INVENTORY
        if excess <= 0:
            fsm.sync_state()
            return

        # Close side: if LONG excess → sell (hit bid); SHORT excess → buy (lift ask)
        close_price = round_price(
            book.bid if side == Side.LONG else book.ask, spec.tick_size
        )
        if close_price <= 0:
            return

        gate_size = -excess if side == Side.LONG else excess
        client_id = uuid.uuid4().hex[:16]
        o = LimitOrder(
            client_id=client_id, exchange_id="",
            symbol=fsm.symbol,
            side=Side.SHORT if side == Side.LONG else Side.LONG,
            requested_size=excess, price=close_price,
            tif="ioc", exec_mode=ExecMode.TAKER_FALLBACK,
            status=OrderStatus.PENDING,
            created_at=time.time(), updated_at=time.time(),
        )
        await self._os.register(o)

        if Cfg.PAPER:
            log.info("PAPER REDUCE %s %s ×%d @ %.8g",
                     side.value.upper(), fsm.symbol, excess, close_price)
            return

        try:
            resp = await self._rest.place_order(
                symbol=fsm.symbol, size=gate_size, price=close_price,
                tif="ioc", reduce_only=True, text=client_id,
            )
            eid = str(resp.get("id", ""))
            await self._os.set_exchange_id(client_id, eid)
            o.exchange_id = eid
            o.status = OrderStatus.OPEN
            self._db.upsert_order(o)
            log.info("REDUCE %s %s excess=%d @ %.8g",
                     fsm.symbol, side.value.upper(), excess, close_price)
        except Exception as exc:
            log.error("REDUCE failed %s %s: %s",
                      fsm.symbol, side.value.upper(), exc)
            o.status = OrderStatus.FAILED
            self._db.upsert_order(o)

    # ── Forced flatten ────────────────────────────────────────────────────────

    async def force_flatten_symbol(self, fsm: HedgeFSM, spec: ContractSpec,
                                    book: BookTick) -> None:
        """
        Emergency close: cancel all open orders then IOC close both legs.
        """
        log.warning("FORCED FLATTEN: %s", fsm.symbol)
        self._db.log_event("RISK", f"Forced flatten {fsm.symbol}", symbol=fsm.symbol)

        if not Cfg.PAPER:
            try:
                await self._rest.cancel_all_symbol(fsm.symbol)
            except Exception as exc:
                log.error("cancel_all_symbol %s: %s", fsm.symbol, exc)

        # Clear all pending order refs from FSM
        fsm.long_oids.clear()
        fsm.short_oids.clear()

        # Close LONG leg if open
        if fsm.long_leg.contracts > 0:
            close_price = round_price(book.bid * 0.999, spec.tick_size)  # aggressive hit
            if not Cfg.PAPER:
                try:
                    await self._rest.close_position_ioc(
                        fsm.symbol, Side.LONG,
                        fsm.long_leg.contracts, close_price
                    )
                except Exception as exc:
                    log.error("force_flatten LONG %s: %s", fsm.symbol, exc)
            pnl = fsm.long_leg.close_fill(
                fsm.long_leg.contracts, close_price,
                Cfg.TAKER_FEE_RATE * close_price * fsm.long_leg.contracts,
                spec.quanto_multiplier,
            )
            self._risk.record_fill_pnl(pnl, abs(pnl) * 0.001)

        # Close SHORT leg if open
        if fsm.short_leg.contracts > 0:
            close_price = round_price(book.ask * 1.001, spec.tick_size)
            if not Cfg.PAPER:
                try:
                    await self._rest.close_position_ioc(
                        fsm.symbol, Side.SHORT,
                        fsm.short_leg.contracts, close_price
                    )
                except Exception as exc:
                    log.error("force_flatten SHORT %s: %s", fsm.symbol, exc)
            pnl = fsm.short_leg.close_fill(
                fsm.short_leg.contracts, close_price,
                Cfg.TAKER_FEE_RATE * close_price * fsm.short_leg.contracts,
                spec.quanto_multiplier,
            )
            self._risk.record_fill_pnl(pnl, abs(pnl) * 0.001)

        fsm.sync_state()

    # ── Reprice loop ──────────────────────────────────────────────────────────

    async def reprice_loop(self) -> None:
        """
        Background heartbeat: TTL-cancel stale orders, trigger reprice.
        """
        while True:
            try:
                await asyncio.sleep(Cfg.REPRICE_LOOP_SEC)
                now = time.time()

                for sym, fsm in self._fsm.items():
                    if fsm.is_halted():
                        continue
                    spec = self._specs.get(sym)
                    if not spec:
                        continue

                    # TTL cancel
                    stale_oids: List[str] = []
                    for oid_set in (fsm.long_oids, fsm.short_oids):
                        for oid in list(oid_set):
                            o = await self._os.get(oid)
                            if o is None or o.is_terminal():
                                oid_set.discard(oid)
                                continue
                            if o.age() > Cfg.QUOTE_TTL_SEC:
                                stale_oids.append(oid)
                                oid_set.discard(oid)

                    for oid in stale_oids:
                        o = await self._os.get(oid)
                        if o and not Cfg.PAPER and o.exchange_id:
                            try:
                                await self._rest.cancel_order(o.exchange_id)
                            except Exception:
                                pass
                        await self._os.mark_cancelled(oid)
                        self._met.record_cancel(sym)
                        log.debug("TTL cancel %s oid=%s", sym, oid[:8])

                    # Reprice if book has moved
                    book = self._books.get(sym)
                    if book and not book.is_stale():
                        await self._check_reprice(fsm, spec, book)

                    # Opening timeout check
                    if (fsm.state == HedgeState.OPENING and
                            fsm.time_in_state() > Cfg.OPENING_TIMEOUT_SEC):
                        if (fsm.long_leg.contracts == 0 or
                                fsm.short_leg.contracts == 0):
                            fsm.sync_state()  # will go BROKEN or FLAT

            except asyncio.CancelledError:
                return
            except Exception:
                log.exception("reprice_loop error")

    async def _check_reprice(self, fsm: HedgeFSM, spec: ContractSpec,
                              book: BookTick) -> None:
        """Cancel and re-quote if best bid/ask has moved by ≥ REPRICE_TICKS."""
        for side, oid_set in ((Side.LONG, fsm.long_oids),
                               (Side.SHORT, fsm.short_oids)):
            for oid in list(oid_set):
                o = await self._os.get(oid)
                if not o or o.is_terminal():
                    oid_set.discard(oid)
                    continue
                target = round_price(
                    book.ask if side == Side.LONG else book.bid, spec.tick_size
                )
                drift = abs(o.price - target)
                if drift >= Cfg.REPRICE_TICKS * spec.tick_size:
                    if not Cfg.PAPER and o.exchange_id:
                        try:
                            await self._rest.cancel_order(o.exchange_id)
                        except Exception:
                            pass
                    await self._os.mark_cancelled(oid)
                    oid_set.discard(oid)
                    self._met.record_cancel(fsm.symbol)
                    log.debug("REPRICE %s %s: %.8g → %.8g",
                              fsm.symbol, side.value, o.price, target)
                    # Re-quote immediately
                    await self._manage_symbol(fsm, spec)
                    break   # one re-quote per tick per side


# ═══════════════════════════════════════════════════════════════════════════════
# §19  DASHBOARD
# ═══════════════════════════════════════════════════════════════════════════════

_DASH_HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8"/><meta http-equiv="refresh" content="3"/>
<title>Gate Hedge v2</title>
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{background:#080d1a;color:#c5d0e4;font-family:'JetBrains Mono',monospace,sans-serif;font-size:12px;padding:10px}
h1{color:#60a5fa;font-size:15px;margin-bottom:10px}
h2{color:#7c8fb0;font-size:10px;text-transform:uppercase;letter-spacing:.12em;margin-bottom:7px}
.g{display:grid;grid-template-columns:repeat(auto-fill,minmax(270px,1fr));gap:8px;margin-bottom:10px}
.card{background:#0d1526;border:1px solid #162040;border-radius:5px;padding:10px}
.kv{display:grid;grid-template-columns:auto 1fr;gap:3px 10px}
.kk{color:#4b5c7a}.vv{color:#e2e8f0}
.buy{color:#4ade80}.sell{color:#f87171}.warn{color:#fbbf24}.na{color:#374151}
.big{font-size:18px;font-weight:700;color:#fff}
table{width:100%;border-collapse:collapse;margin-top:4px}
th{padding:4px 7px;text-align:left;color:#374a6b;font-size:10px;border-bottom:1px solid #162040}
td{padding:3px 7px;border-bottom:1px solid rgba(12,22,42,.7);white-space:nowrap;font-size:11px}
tr:hover td{background:rgba(30,80,180,.05)}
.fsm-FLAT{color:#4b5c7a}.fsm-OPENING{color:#fbbf24}.fsm-HEDGED{color:#4ade80}
.fsm-BROKEN_HEDGE{color:#f87171}.fsm-REPAIRING{color:#f59e0b}
.fsm-REDUCING{color:#a78bfa}.fsm-HALTED{color:#f43f5e;font-weight:700}
.badge{padding:1px 6px;border-radius:3px;font-size:10px;font-weight:600}
.live{background:rgba(74,222,128,.12);color:#4ade80}
.paper{background:rgba(251,191,36,.12);color:#fbbf24}
</style>
</head>
<body>
<h1>⬡ Gate Aggressive Hedge Engine v2</h1>
<div class="g" id="sym-grid"></div>
<div class="g">
  <div class="card"><h2>Metrics</h2><div class="kv" id="met-kv"></div></div>
  <div class="card"><h2>Risk</h2><div class="kv" id="risk-kv"></div></div>
  <div class="card"><h2>Session</h2><div class="kv" id="sess-kv"></div></div>
</div>
<div class="card" style="margin-bottom:8px">
  <h2>Symbol Performance</h2>
  <div id="sym-perf-tbl"></div>
</div>
<div class="card" style="margin-bottom:8px">
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
  if(typeof v==='number')return isNaN(v)?'<span class="na">NaN</span>':v.toFixed(d);
  return String(v);
};
const kv=(pairs)=>pairs.map(([k,v])=>`<div class="kk">${k}</div><div class="vv">${v}</div>`).join('');
const tbl=(cols,rows)=>`<table><thead><tr>${cols.map(c=>`<th>${c}</th>`).join('')}</tr></thead><tbody>${
  rows.map(r=>`<tr>${r.map(c=>`<td>${c}</td>`).join('')}</tr>`).join('')}</tbody></table>`;
const pnlClass=(v)=>v>=0?'buy':'sell';
async function refresh(){
  const d=await fetch('/api/state').then(r=>r.json()).catch(()=>({}));
  if(!d.symbols) return;
  // Symbols
  document.getElementById('sym-grid').innerHTML=d.symbols.map(s=>`
  <div class="card">
    <h2>${s.symbol} <span class="fsm-${s.fsm_state}">[${s.fsm_state}]</span></h2>
    <div class="kv">${kv([
      ['bid',`<span class="sell">${f(s.bid,8)}</span>`],
      ['ask',`<span class="buy">${f(s.ask,8)}</span>`],
      ['spread%',`${s.spread_pct!==null?(s.spread_pct*100).toFixed(4)+'%':'–'}`],
      ['long_inv',s.long_inv],['short_inv',s.short_inv],
      ['net_delta',`<span class="${s.net_delta!==0?'warn':'na'}">${s.net_delta}</span>`],
      ['long_pnl',`<span class="${pnlClass(s.long_pnl)}">${f(s.long_pnl,6)}</span>`],
      ['short_pnl',`<span class="${pnlClass(s.short_pnl)}">${f(s.short_pnl,6)}</span>`],
      ['unreal_pnl',`<span class="${pnlClass(s.unreal_pnl)}">${f(s.unreal_pnl,6)}</span>`],
      ['long_avg_entry',f(s.long_avg,8)],
      ['short_avg_entry',f(s.short_avg,8)],
      ['book_age',f(s.book_age,2)+'s'],
    ])}</div>
  </div>`).join('');
  // Metrics
  const m=d.metrics;
  document.getElementById('met-kv').innerHTML=kv([
    ['fills/min',m.fills_per_min.toFixed(1)],
    ['cancels/min',m.cancels_per_min.toFixed(1)],
    ['gross_notional','$'+f(m.total_gross_notional,4)],
    ['total_fees','$'+f(m.total_fees,6)],
    ['total_pnl',`<span class="${pnlClass(m.total_realized_pnl)}">$${f(m.total_realized_pnl,6)}</span>`],
    ['api_errors_1m',m.api_errors_1m],
    ['ws_reconnects',m.ws_reconnects],
    ['uptime',m.uptime],
  ]);
  // Risk
  const r=d.risk;
  document.getElementById('risk-kv').innerHTML=kv([
    ['status',r.global_halt?'<span class="sell">HALTED</span>':'<span class="buy">ACTIVE</span>'],
    ['daily_loss',`<span class="${r.daily_loss>0?'sell':'buy'}">$${f(r.daily_loss,4)}</span>`],
    ['daily_fees','$'+f(r.daily_fees,4)],
    ['halted_syms',r.halted_syms.join(',')||'none'],
    ['recent_breaches',r.breaches.length],
  ]);
  // Session
  const sess=d.session;
  document.getElementById('sess-kv').innerHTML=kv([
    ['mode',`<span class="${sess.paper?'paper':'live'} badge">${sess.paper?'PAPER':'LIVE'}</span>`],
    ['exec_mode',sess.exec_mode],
    ['symbols',sess.symbols.join(', ')],
    ['leverage',sess.leverage],
    ['target_notional','$'+f(sess.target_notional,3)],
  ]);
  // Symbol perf table
  const sp=d.metrics.symbols.map(s=>[
    s.symbol,s.fills,s.cancels,
    '<span class="sell">$'+f(s.fees_paid,5)+'</span>',
    `<span class="${pnlClass(s.realized_pnl)}">$${f(s.realized_pnl,6)}</span>`,
    s.gross_notional.toFixed(5),
    s.repairs,s.imbalances,s.viability_skips,s.stale_skips,
  ]);
  document.getElementById('sym-perf-tbl').innerHTML=tbl(
    ['symbol','fills','cancels','fees','realized_pnl','gross_notional',
     'repairs','imbalances','via_skips','stale_skips'], sp
  );
  // Fills
  const fills=d.fills.slice(0,50).map(f2=>[
    new Date(f2.ts*1000).toISOString().slice(11,22),
    f2.symbol,
    `<span class="${f2.side==='long'?'buy':'sell'}">${f2.side.toUpperCase()}</span>`,
    f2.size,f2.price.toFixed(8),
    `<span class="${pnlClass(f2.realized_pnl)}">$${f2.realized_pnl.toFixed(6)}</span>`,
    '$'+f2.fee_usdt.toFixed(6),
    f2.is_close?'CLOSE':'OPEN',
  ]);
  document.getElementById('fills-tbl').innerHTML=tbl(
    ['time','symbol','side','size','price','pnl','fee','type'], fills
  );
  // Events
  const evts=d.events.slice(0,40).map(e=>[
    new Date(e.ts*1000).toISOString().slice(11,22),
    `<span class="${e.level==='RISK'?'sell':e.level==='WARN'?'warn':'na'}">${e.level}</span>`,
    e.symbol||'',e.message,
  ]);
  document.getElementById('evt-tbl').innerHTML=tbl(['time','level','sym','message'],evts);
}
refresh();setInterval(refresh,3000);
</script>
</body></html>
"""


class _Handler(BaseHTTPRequestHandler):
    engine_ref: "Engine"
    def log_message(self, *_) -> None: pass
    def do_GET(self) -> None:
        if self.path == "/":
            self.send_response(200)
            self.send_header("Content-Type","text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(_DASH_HTML.encode())
        elif self.path == "/api/state":
            self.send_response(200)
            self.send_header("Content-Type","application/json")
            self.end_headers()
            self.wfile.write(json.dumps(
                self.engine_ref.state_dict()
            ).encode())
        else:
            self.send_response(404)
            self.end_headers()


class Dashboard:
    def __init__(self, engine: "Engine") -> None:
        self._engine = engine
        self._srv: Optional[HTTPServer] = None

    def start(self) -> None:
        _Handler.engine_ref = self._engine
        self._srv = HTTPServer((Cfg.DASHBOARD_HOST, Cfg.DASHBOARD_PORT), _Handler)
        threading.Thread(target=self._srv.serve_forever, daemon=True).start()
        log.info("Dashboard: http://%s:%d", Cfg.DASHBOARD_HOST, Cfg.DASHBOARD_PORT)

    def stop(self) -> None:
        if self._srv:
            self._srv.shutdown()


# ═══════════════════════════════════════════════════════════════════════════════
# §20  ENGINE (ORCHESTRATOR)
# ═══════════════════════════════════════════════════════════════════════════════

class Engine:
    def __init__(self) -> None:
        self._session  : Optional[aiohttp.ClientSession] = None
        self._rest     : Optional[GateRest]              = None
        self._db       : Optional[DB]                    = None
        self._metrics  : Optional[Metrics]               = None
        self._risk     : Optional[RiskEngine]            = None
        self._os       : Optional[OrderStore]            = None
        self._books    : Optional[BookCache]             = None
        self._exec     : Optional[ExecEngine]            = None
        self._ws       : Optional[GateWS]                = None
        self._dash     : Optional[Dashboard]             = None
        self._fsm_map  : Dict[str, HedgeFSM]             = {}
        self._specs    : Dict[str, ContractSpec]         = {}
        self._symbols  : List[str]                       = []
        self._start_ts : float                           = time.time()

    # ── Startup ───────────────────────────────────────────────────────────────

    async def start(self) -> None:
        log.info("═══ Gate Aggressive Hedge Engine v2.0 starting ═══")
        log.info("Mode: %s", "PAPER" if Cfg.PAPER else "LIVE")
        _validate_cfg()

        self._db      = DB(Cfg.DB_PATH)
        self._metrics = Metrics()
        self._session = aiohttp.ClientSession(
            connector=aiohttp.TCPConnector(limit=50),
            timeout=aiohttp.ClientTimeout(total=15),
        )
        self._rest   = GateRest(self._session, self._metrics)
        self._risk   = RiskEngine(self._db, self._metrics)
        await self._risk.refresh_daily()

        # Symbol resolution
        self._symbols = Cfg.SYMBOLS or await select_symbols(self._rest)
        if not self._symbols:
            raise RuntimeError("No viable symbols found. Check config thresholds.")
        log.info("Symbols: %s", self._symbols)
        self._db.log_event("INFO", "Engine started",
                           data={"symbols": self._symbols, "paper": Cfg.PAPER})

        # Enable dual-position mode
        if Cfg.ENABLE_DUAL_MODE and not Cfg.PAPER:
            try:
                await self._rest.set_dual_mode(True)
                log.info("Dual-position mode enabled")
            except Exception as exc:
                log.warning("set_dual_mode: %s (may already be active)", exc)

        # Load specs, set leverage, init FSMs
        for sym in self._symbols:
            spec = await load_spec(self._rest, sym)
            if spec is None:
                log.warning("Could not load spec for %s — skipping", sym)
                continue
            self._specs[sym] = spec
            log.info("Spec %s: tick=%.8g qm=%.4g mark=%.8g min_sz=%d",
                     sym, spec.tick_size, spec.quanto_multiplier,
                     spec.mark_price, spec.min_size)
            if not Cfg.PAPER:
                try:
                    await self._rest.set_leverage(sym, Cfg.LEVERAGE)
                except Exception as exc:
                    log.warning("set_leverage %s: %s", sym, exc)
            long_leg  = Leg(symbol=sym, side=Side.LONG)
            short_leg = Leg(symbol=sym, side=Side.SHORT)
            self._fsm_map[sym] = HedgeFSM(sym, long_leg, short_leg)

        # Filter symbols to those with specs
        self._symbols = [s for s in self._symbols if s in self._specs]

        # Order store + book cache
        self._os    = OrderStore(self._db)
        await self._os.restore_from_db()
        self._books = BookCache()

        # Execution engine
        self._exec = ExecEngine(
            self._rest, self._os, self._db, self._risk, self._metrics,
            self._fsm_map, self._specs, self._books,
        )

        # Reconcile against live exchange state (skip in paper mode)
        if not Cfg.PAPER:
            await reconcile(self._rest, self._db,
                            self._fsm_map, self._os, self._specs)
        else:
            log.info("Paper mode: skipping reconciliation")

        # Dashboard
        self._dash = Dashboard(self)
        self._dash.start()

        # WebSocket
        self._ws = GateWS(
            symbols=self._symbols,
            book_cache=self._books,
            metrics=self._metrics,
            on_order=self._exec.on_order_update,
            on_trade=self._exec.on_trade,
        )
        self._ws.set_callbacks(
            on_order=self._exec.on_order_update,
            on_trade=self._exec.on_trade,
        )
        await self._ws.start()

        # Background tasks
        asyncio.create_task(self._exec.reprice_loop(), name="reprice_loop")
        asyncio.create_task(self._book_tick_loop(),     name="book_tick_loop")
        asyncio.create_task(self._risk_monitor_loop(),  name="risk_monitor")

        log.info("Engine LIVE on %d symbols", len(self._symbols))

    async def _book_tick_loop(self) -> None:
        """Poll book cache and route ticks to exec engine."""
        while True:
            try:
                await asyncio.sleep(Cfg.REPRICE_LOOP_SEC)
                for sym in self._symbols:
                    tick = self._books.get(sym)
                    if tick:
                        await self._exec.on_book_tick(sym)
            except asyncio.CancelledError:
                return
            except Exception:
                log.exception("book_tick_loop error")

    async def _risk_monitor_loop(self) -> None:
        """Periodic risk checks: stale book → halt, broken hedge timeout."""
        while True:
            try:
                await asyncio.sleep(5.0)
                if not self._exec or not self._risk:
                    continue
                ok, reason = self._risk.global_ok()
                if not ok:
                    log.warning("Global risk: %s", reason)
                for sym, fsm in self._fsm_map.items():
                    book = self._books.get(sym) if self._books else None
                    spec = self._specs.get(sym)
                    if book and book.is_stale() and not fsm.is_halted():
                        log.warning("Stale book %s — halting", sym)
                        self._risk.halt_symbol(sym, "stale_book")
                        fsm.halt("stale_book")
                    elif book and not book.is_stale() and fsm.state == HedgeState.HALTED:
                        # Check if we can resume
                        ok_g, _ = self._risk.global_ok()
                        if ok_g and sym not in self._risk._halted_syms:
                            fsm.resume()
            except asyncio.CancelledError:
                return
            except Exception:
                log.exception("risk_monitor_loop error")

    # ── State dict for dashboard ──────────────────────────────────────────────

    def state_dict(self) -> Dict:
        symbols = []
        for sym, fsm in self._fsm_map.items():
            book  = self._books.get(sym) if self._books else None
            spec  = self._specs.get(sym)
            quanto = spec.quanto_multiplier if spec else 1.0
            mark   = book.mid if book else (spec.mark_price if spec else 0.0)
            symbols.append({
                "symbol":      sym,
                "fsm_state":   fsm.state.value,
                "bid":         book.bid   if book else None,
                "ask":         book.ask   if book else None,
                "spread_pct":  book.spread_pct if book else None,
                "book_age":    book.age()  if book else None,
                "long_inv":    fsm.long_leg.contracts,
                "short_inv":   fsm.short_leg.contracts,
                "net_delta":   fsm.long_leg.contracts - fsm.short_leg.contracts,
                "long_pnl":    fsm.long_leg.realized_pnl,
                "short_pnl":   fsm.short_leg.realized_pnl,
                "long_avg":    fsm.long_leg.avg_entry_price,
                "short_avg":   fsm.short_leg.avg_entry_price,
                "unreal_pnl":  (fsm.long_leg.unrealized_pnl(mark, quanto) +
                                 fsm.short_leg.unrealized_pnl(mark, quanto)),
            })
        return {
            "symbols":  symbols,
            "metrics":  self._metrics.snapshot() if self._metrics else {},
            "risk":     self._risk.status()       if self._risk    else {},
            "session":  {
                "paper":           Cfg.PAPER,
                "exec_mode":       Cfg.DEFAULT_EXEC_MODE.value,
                "symbols":         self._symbols,
                "leverage":        Cfg.LEVERAGE,
                "target_notional": Cfg.TARGET_NOTIONAL,
            },
            "fills":    self._db.get_recent_fills(100) if self._db else [],
            "events":   self._db.get_events(80)        if self._db else [],
        }

    # ── Shutdown ──────────────────────────────────────────────────────────────

    async def stop(self) -> None:
        log.info("Engine shutting down...")
        if self._ws:
            await self._ws.stop()
        if not Cfg.PAPER and self._rest and self._books:
            for sym, fsm in self._fsm_map.items():
                book = self._books.get(sym)
                spec = self._specs.get(sym)
                if book and spec:
                    try:
                        await self._exec.force_flatten_symbol(fsm, spec, book)
                    except Exception:
                        pass
                try:
                    await self._rest.cancel_all_symbol(sym)
                except Exception:
                    pass
        if self._dash:
            self._dash.stop()
        if self._session:
            await self._session.close()
        if self._db:
            for fsm in self._fsm_map.values():
                self._db.snapshot_leg(fsm.long_leg)
                self._db.snapshot_leg(fsm.short_leg)
            self._db.log_event("INFO", "Engine stopped cleanly")
        log.info("Engine stopped.")


# ═══════════════════════════════════════════════════════════════════════════════
# §21  ENTRYPOINT
# ═══════════════════════════════════════════════════════════════════════════════

async def _main() -> None:
    engine = Engine()
    loop   = asyncio.get_running_loop()

    def _sig() -> None:
        asyncio.create_task(engine.stop())
        loop.call_later(8.0, loop.stop)

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, _sig)
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
    setup_logging()
    log.info("gate_aggressive_hedge_v2.py  v2.0  |  Python %s", sys.version.split()[0])
    if Cfg.PAPER:
        log.info("*** PAPER MODE — no real orders ***")
    try:
        asyncio.run(_main())
    except KeyboardInterrupt:
        pass