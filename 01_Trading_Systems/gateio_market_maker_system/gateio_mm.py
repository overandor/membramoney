#!/usr/bin/env python3
"""
Gate.io Spot Market-Maker  v3  –  Production Edition
=====================================================

Install
-------
pip install "aiohttp>=3.9" "websockets>=12" "pydantic[dotenv]>=1,<2"

Configure
---------
cp .env.example .env
# edit .env with your API credentials and symbol list

Run
---
python gateio_mm.py              # live
DRY_RUN=1 python gateio_mm.py   # paper-trade (no orders placed)

Test
----
pip install pytest pytest-asyncio
pytest test_gateio_mm.py -v

Health / Metrics
----------------
curl http://localhost:8080/health
curl http://localhost:8080/metrics

Session persistence
-------------------
Ledger state is saved to session_state.json every 30 s
and loaded on restart so P&L history survives process restarts.

Important
---------
Market-making carries real financial risk.
No parameter set guarantees profit.
Always start in DRY_RUN=1, verify fills and logic,
then size up gradually from minimum notional.
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac as _hmac
import json
import logging
import math
import os
import signal
import sys
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from decimal import Decimal, ROUND_DOWN
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple

import aiohttp
from aiohttp import web
import websockets
try:
    from pydantic_settings import BaseSettings
    from pydantic import Field
    from pydantic import field_validator as _field_validator
    _SYMBOLS_VALIDATOR = _field_validator("symbols", mode="before")
except Exception:  # pragma: no cover
    from pydantic import BaseSettings, Field, validator as _validator
    _SYMBOLS_VALIDATOR = _validator("symbols", pre=True)


# ======================================================================
# SETTINGS
# ======================================================================

class Settings(BaseSettings):
    # -- credentials ---------------------------------------------------
    gateio_api_key:    str       = Field("", env="GATEIO_API_KEY")
    gateio_api_secret: str       = Field("", env="GATEIO_API_SECRET")
    symbols:           List[str] = Field(default_factory=list, env="SYMBOLS")

    # -- endpoints -----------------------------------------------------
    base_url: str = Field("https://api.gateio.ws/api/v4", env="BASE_URL")
    ws_url:   str = Field("wss://api.gateio.ws/ws/v4/",   env="WS_URL")

    # -- mode ----------------------------------------------------------
    dry_run: bool = Field(False, env="DRY_RUN")

    # -- timing --------------------------------------------------------
    engine_hz:         float = 4.0    # main loop frequency (Hz)
    quote_refresh_sec: float = 0.8    # requote if time since last > this
    status_sec:        float = 5.0    # P&L log interval
    hedge_cooldown:    float = 3.0    # min seconds between hedge orders
    dca_refresh_sec:   float = 12.0   # DCA check interval
    persist_sec:       float = 30.0   # session save interval

    # -- Avellaneda-Stoikov --------------------------------------------
    gamma:               float = 0.15   # risk aversion  (higher = tighter spread)
    kappa:               float = 3.0    # order arrival rate estimate
    horizon_sec:         float = 30.0   # inventory risk horizon
    min_half_spread_bps: float = 4.0    # floor on half-spread
    max_half_spread_bps: float = 60.0   # ceiling on half-spread

    # -- quoting -------------------------------------------------------
    quote_levels:       int   = 2       # bid/ask layers each side
    level_spacing_bps:  float = 3.0     # price step between layers
    level_size_decay:   float = 0.6     # size multiplier per level (0.6^i)
    order_notional_usd: float = 25.0    # base layer notional in USD
    spread_lock_bps:    float = 0.5     # suppress requote if drift < this

    # -- inventory cap -------------------------------------------------
    max_inventory_notional_usd: float = 250.0

    # -- hedge ---------------------------------------------------------
    hedge_trigger_frac: float = 0.75    # trigger IOC hedge at this fraction of max_inv
    hedge_ioc_frac:     float = 0.35    # fraction of excess inventory to hedge

    # -- DCA -----------------------------------------------------------
    dca_enabled:          bool  = True
    dca_levels:           int   = 3
    dca_step_bps:         float = 20.0   # base step between DCA layers
    dca_clip_usd:         float = 10.0   # notional per DCA order
    dca_max_sigma_bps:    float = 40.0   # skip DCA if vol exceeds this
    dca_vol_scale_factor: float = 1.5    # step width scales as sigma/baseline * this
    dca_vol_baseline_bps: float = 10.0   # vol reference for scaling

    # -- volatility ----------------------------------------------------
    ewma_fast_span: int   = 20     # fast EWMA window (ticks)
    ewma_slow_span: int   = 120    # slow EWMA window (ticks)
    max_sigma_bps:  float = 80.0   # pause quoting above this vol

    # -- toxicity (order-book imbalance skew) --------------------------
    tox_depth_levels:   int   = 10    # levels to sum for imbalance
    tox_skew_scale_bps: float = 8.0   # max reservation-price shift

    # -- circuit breaker -----------------------------------------------
    cb_bps:        float = 150.0   # trigger if price moves > this in window
    cb_window_sec: float = 3.0     # lookback window for flash-crash detection
    cb_pause_sec:  float = 30.0    # pause duration after trigger

    # -- risk ----------------------------------------------------------
    stop_if_drawdown_usd:   float = 150.0   # aggregate kill-switch
    max_open_per_symbol:    int   = 10      # hard cap on open orders
    max_consecutive_errors: int   = 8       # backoff after N REST errors

    # -- fees ----------------------------------------------------------
    maker_fee_bps: float = 1.5    # Gate VIP0 maker
    taker_fee_bps: float = 5.0    # Gate VIP0 taker

    # -- rate limiting -------------------------------------------------
    rate_limit_burst: int   = 8     # token bucket capacity
    rate_limit_rps:   float = 8.0   # sustained requests per second

    # -- order params --------------------------------------------------
    stp_act: str = "cn"   # self-trade prevention: cn=cancel_new  co=cancel_old  cb=cancel_both

    # -- misc ----------------------------------------------------------
    metrics_port: int  = 8080
    session_file: str  = "session_state.json"
    log_json:     bool = Field(False, env="LOG_JSON")

    class Config:
        env_file          = ".env"
        env_file_encoding = "utf-8"

    @_SYMBOLS_VALIDATOR
    def _split(cls, v: Any) -> List[str]:
        if isinstance(v, str):
            return [x.strip().upper() for x in v.split(",") if x.strip()]
        return v

    def validate_params(self) -> None:
        """Boot-time sanity checks that catch common misconfigurations early."""
        assert self.min_half_spread_bps < self.max_half_spread_bps, \
            "min_half_spread_bps must be < max_half_spread_bps"
        assert 0.0 < self.hedge_trigger_frac <= 1.0, \
            "hedge_trigger_frac must be in (0, 1]"
        assert self.order_notional_usd > 0.0, \
            "order_notional_usd must be positive"
        assert self.quote_levels >= 1, \
            "quote_levels must be >= 1"
        assert self.stp_act in ("cn", "co", "cb"), \
            f"stp_act must be cn/co/cb, got {self.stp_act!r}"
        # Boot ergonomics: if creds are missing, force DRY_RUN so the
        # process can still start for smoke-testing.
        if (not self.gateio_api_key.strip()) or (not self.gateio_api_secret.strip()):
            if not self.dry_run:
                log.warning("Missing Gate.io credentials; forcing DRY_RUN=1")
            self.dry_run = True

        if self.dry_run:
            log.warning("DRY-RUN MODE: no orders will be placed")
        else:
            assert self.gateio_api_key.strip(), "Missing GATEIO_API_KEY"
            assert self.gateio_api_secret.strip(), "Missing GATEIO_API_SECRET"
            assert self.symbols, "Missing SYMBOLS (comma-separated, e.g. BTC_USDT,ETH_USDT)"


cfg = Settings()

# In DRY_RUN we allow running without a .env. Provide a safe default symbol
# before the engine is constructed so internal state is consistent.
if cfg.dry_run and not cfg.symbols:
    cfg.symbols = ["BTC_USDT"]
    # logger is initialized below; use print here to avoid reordering globals.
    print(f"[gate-mm] DRY_RUN: defaulting SYMBOLS to {cfg.symbols}")


# ======================================================================
# LOGGING
# ======================================================================

class _JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        return json.dumps({
            "ts":  self.formatTime(record, "%Y-%m-%dT%H:%M:%S"),
            "lvl": record.levelname,
            "msg": record.getMessage(),
        })


_handler = logging.StreamHandler(sys.stdout)
_handler.setFormatter(
    _JsonFormatter() if cfg.log_json
    else logging.Formatter("%(asctime)s %(levelname)-8s  %(message)s")
)
logging.basicConfig(level=logging.INFO, handlers=[_handler])
log = logging.getLogger("gate-mm")


# ======================================================================
# HELPERS
# ======================================================================

def now_ts() -> int:
    return int(time.time())


def bps_f(b: float) -> float:
    return b / 10_000.0


def clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


def sha512_hex(s: str) -> str:
    return hashlib.sha512(s.encode()).hexdigest()


def round_dn(v: float, dp: int) -> str:
    quantizer = Decimal("1." + "0" * dp) if dp > 0 else Decimal("1")
    return format(
        Decimal(str(v)).quantize(quantizer, rounding=ROUND_DOWN), "f"
    )


def safe_float(x: Any, default: float = 0.0) -> float:
    try:
        return float(x)
    except (TypeError, ValueError):
        return default


def pair_parts(sym: str) -> Tuple[str, str]:
    base, quote = sym.split("_", 1)
    return base.upper(), quote.upper()


def _dp(raw: Any) -> int:
    """
    Parse Gate.io precision field to a decimal-place count.

    Gate returns two formats:
      integer string  "8"      -> 8 decimal places
      decimal string  "0.0100" -> 4 decimal places (trailing zeros stripped)
    """
    s = str(raw).strip()
    if "." in s:
        decimal_part = s.split(".", 1)[1].rstrip("0") or "0"
        return len(decimal_part)
    try:
        return int(s)
    except ValueError:
        return 8


# ======================================================================
# TOKEN-BUCKET RATE LIMITER
# ======================================================================

class RateLimiter:
    def __init__(self, capacity: int, rps: float) -> None:
        self._capacity = float(capacity)
        self._rps      = rps
        self._tokens   = float(capacity)
        self._last     = time.monotonic()
        self._lock     = asyncio.Lock()

    async def acquire(self) -> None:
        async with self._lock:
            now = time.monotonic()
            self._tokens = min(
                self._capacity,
                self._tokens + (now - self._last) * self._rps,
            )
            self._last = now
            if self._tokens < 1.0:
                await asyncio.sleep((1.0 - self._tokens) / self._rps)
                self._tokens = 0.0
            else:
                self._tokens -= 1.0


# ======================================================================
# INSTRUMENT SPEC
# ======================================================================

@dataclass
class InstrumentSpec:
    symbol:     str
    price_dp:   int   = 8
    amount_dp:  int   = 8
    min_amount: float = 0.0
    min_total:  float = 1.0
    tick_size:  float = 1e-8
    lot_size:   float = 1e-8

    def min_notional(self) -> float:
        return max(self.min_total, 1.0)


# ======================================================================
# ORDER LIFECYCLE
# ======================================================================

class OrderStatus(str, Enum):
    PENDING   = "pending"    # placed locally, exchange not yet confirmed
    OPEN      = "open"       # confirmed open on exchange
    FILLED    = "filled"
    CANCELLED = "cancelled"
    REJECTED  = "rejected"


@dataclass
class OrderRecord:
    oid:    str
    sym:    str
    side:   str
    price:  float
    size:   float
    label:  str
    status: OrderStatus = OrderStatus.PENDING
    ts:     float       = field(default_factory=time.time)


class PlaceResult(str, Enum):
    PLACED   = "placed"
    REJECTED = "rejected"   # post-only crossed  / min-notional fail
    DRY      = "dry"        # dry-run mode active
    ERROR    = "error"      # unexpected REST error


# ======================================================================
# ABSTRACT EXCHANGE
# Swap Gate.io for any venue by subclassing these six method groups.
# ======================================================================

class AbstractExchange(ABC):

    @abstractmethod
    async def get_order_book(self, sym: str,
                              limit: int = 100) -> Dict[str, Any]:
        """Return {"bids": [[px,sz],...], "asks": [[px,sz],...], "id": int}"""

    @abstractmethod
    async def get_instrument_spec(self, sym: str) -> InstrumentSpec:
        """Return exchange precision / lot / tick for sym."""

    @abstractmethod
    async def get_balances(self) -> Dict[str, float]:
        """Return {currency: available_amount}."""

    @abstractmethod
    async def create_limit(
        self, sym: str, side: str, amount: float, price: float,
        tif: str = "poc", text: str = "", stp_act: str = "cn",
        spec: Optional[InstrumentSpec] = None,
    ) -> Dict[str, Any]:
        """Place a limit order. Return exchange dict containing 'id'."""

    @abstractmethod
    async def cancel_order(self, sym: str, oid: str) -> None:
        """Cancel a single order."""

    @abstractmethod
    async def cancel_all(self, sym: str) -> None:
        """Cancel all open orders for sym (best-effort)."""

    @abstractmethod
    async def list_open_orders(self, sym: str) -> List[Dict[str, Any]]:
        """Return open orders: [{id, side, price, amount, text}, ...]"""

    @abstractmethod
    async def start_book_stream(
        self,
        symbols: List[str],
        on_snapshot: Callable[[str, Dict], None],
        on_update:   Callable[[str, Dict], None],
    ) -> None:
        """Start public order-book WS. Calls on_snapshot once then on_update."""

    @abstractmethod
    async def start_fill_stream(
        self,
        symbols: List[str],
        on_fill: Callable[..., Any],
    ) -> None:
        """Start authenticated fill WS. on_fill(sym,side,amt,px,fee,fee_ccy)."""

    @abstractmethod
    async def close(self) -> None:
        """Release underlying HTTP session and stop WS loops."""


# ======================================================================
# GATE.IO IMPLEMENTATION
# ======================================================================

class GateExchange(AbstractExchange):

    _REST_PREFIX = "/api/v4"

    def __init__(self, key: str, secret: str,
                 base_url: str, ws_url: str,
                 rl: RateLimiter) -> None:
        self._key     = key
        self._secret  = secret
        self._base    = base_url.rstrip("/")
        self._ws_url  = ws_url
        self._rl      = rl
        self._sess: Optional[aiohttp.ClientSession] = None
        self._ws_stop = False

    # -- session -------------------------------------------------------

    def _ensure_session(self) -> None:
        if not self._sess or self._sess.closed:
            self._sess = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=20)
            )

    # -- signing -------------------------------------------------------

    def _sign(self, method: str, path: str,
              qs: str, body: str) -> Dict[str, str]:
        ts  = str(now_ts())
        msg = (f"{method.upper()}\n"
               f"{self._REST_PREFIX}{path}\n"
               f"{qs}\n"
               f"{sha512_hex(body)}\n"
               f"{ts}")
        sig = _hmac.new(
            self._secret.encode(), msg.encode(), hashlib.sha512
        ).hexdigest()
        return {
            "KEY":          self._key,
            "Timestamp":    ts,
            "SIGN":         sig,
            "Content-Type": "application/json",
            "Accept":       "application/json",
        }

    # -- raw request ---------------------------------------------------

    async def _req(
        self, method: str, path: str,
        params: Optional[Dict[str, Any]] = None,
        body:   Optional[Dict[str, Any]] = None,
    ) -> Any:
        self._ensure_session()
        await self._rl.acquire()
        qs  = "&".join(
            f"{k}={v}" for k, v in (params or {}).items()
            if v is not None
        )
        bs   = json.dumps(body, separators=(",", ":")) if body else ""
        hdrs = self._sign(method, path, qs, bs)
        url  = f"{self._base}{path}"
        assert self._sess is not None
        async with self._sess.request(
            method.upper(), url,
            params=params, data=bs or None, headers=hdrs,
        ) as r:
            txt = await r.text()
            if r.status >= 400:
                raise RuntimeError(
                    f"REST {method} {path} {r.status}: {txt[:400]}"
                )
            return json.loads(txt) if txt else {}

    # -- AbstractExchange: market data ---------------------------------

    async def get_order_book(self, sym: str,
                              limit: int = 100) -> Dict[str, Any]:
        return await self._req("GET", "/spot/order_book", {
            "currency_pair": sym, "limit": limit, "with_id": "true",
        })

    async def get_instrument_spec(self, sym: str) -> InstrumentSpec:
        pair = await self._req("GET", f"/spot/currency_pairs/{sym}")
        spec = InstrumentSpec(sym)
        spec.price_dp   = _dp(pair.get("precision",        8))
        spec.amount_dp  = _dp(pair.get("amount_precision", 8))
        spec.min_amount = safe_float(pair.get("min_base_amount",  "0"))
        spec.min_total  = safe_float(pair.get("min_quote_amount", "1"))
        return spec

    # -- AbstractExchange: account ------------------------------------

    async def get_balances(self) -> Dict[str, float]:
        accounts = await self._req("GET", "/spot/accounts")
        return {
            a["currency"]: safe_float(a.get("available", 0))
            for a in accounts
        }

    # -- AbstractExchange: orders -------------------------------------

    async def create_limit(
        self, sym: str, side: str, amount: float, price: float,
        tif: str = "poc", text: str = "", stp_act: str = "cn",
        spec: Optional[InstrumentSpec] = None,
    ) -> Dict[str, Any]:
        pdp  = spec.price_dp  if spec else 8
        adp  = spec.amount_dp if spec else 8
        body: Dict[str, Any] = {
            "currency_pair": sym,
            "type":          "limit",
            "account":       "spot",
            "side":          side,
            "amount":        round_dn(amount, adp),
            "price":         round_dn(price,  pdp),
            "time_in_force": tif,
            "action_mode":   "FULL",
        }
        if text:    body["text"]    = text[:28]
        if stp_act: body["stp_act"] = stp_act
        return await self._req("POST", "/spot/orders", body=body)

    async def cancel_order(self, sym: str, oid: str) -> None:
        await self._req("DELETE", f"/spot/orders/{oid}",
                        {"currency_pair": sym})

    async def cancel_all(self, sym: str) -> None:
        try:
            await self._req("DELETE", "/spot/orders",
                            {"currency_pair": sym, "account": "spot"})
        except Exception as exc:
            log.warning("cancel_all %s: %s", sym, exc)

    async def list_open_orders(self, sym: str) -> List[Dict[str, Any]]:
        return await self._req("GET", "/spot/orders", {
            "currency_pair": sym, "status": "open", "limit": 100,
        })

    # -- AbstractExchange: streaming ----------------------------------

    async def start_book_stream(
        self,
        symbols: List[str],
        on_snapshot: Callable[[str, Dict], None],
        on_update:   Callable[[str, Dict], None],
    ) -> None:
        asyncio.create_task(
            self._book_loop(symbols, on_snapshot, on_update)
        )

    async def _book_loop(
        self,
        symbols: List[str],
        on_snapshot: Callable[[str, Dict], None],
        on_update:   Callable[[str, Dict], None],
    ) -> None:
        backoff = 1.0
        while not self._ws_stop:
            try:
                ws = await websockets.connect(
                    self._ws_url,
                    ping_interval=20, ping_timeout=20, close_timeout=5,
                )
                backoff = 1.0
                for sym in symbols:
                    await ws.send(json.dumps({
                        "time":    now_ts(),
                        "channel": "spot.order_book_update",
                        "event":   "subscribe",
                        "payload": [sym, "100ms"],
                    }))
                async for raw in ws:
                    msg = json.loads(raw)
                    if (msg.get("channel") != "spot.order_book_update"
                            or msg.get("event") != "update"):
                        continue
                    res = msg["result"]
                    sym = res.get("s", "")
                    if sym in symbols:
                        on_update(sym, res)
            except Exception as exc:
                if not self._ws_stop:
                    log.warning("BookWS error: %s – retry in %.0fs",
                                exc, backoff)
                    await asyncio.sleep(backoff)
                    backoff = min(backoff * 2, 30.0)

    async def start_fill_stream(
        self,
        symbols: List[str],
        on_fill: Callable[..., Any],
    ) -> None:
        asyncio.create_task(self._fill_loop(symbols, on_fill))

    async def _fill_loop(
        self,
        symbols: List[str],
        on_fill: Callable[..., Any],
    ) -> None:
        channel = "spot.usertrades"
        backoff = 1.0
        while not self._ws_stop:
            try:
                ws = await websockets.connect(
                    self._ws_url,
                    ping_interval=20, ping_timeout=20, close_timeout=5,
                )
                backoff = 1.0
                ts  = now_ts()
                sig = _hmac.new(
                    self._secret.encode(),
                    f"api\n{channel}\n\n{ts}".encode(),
                    hashlib.sha512,
                ).hexdigest()
                await ws.send(json.dumps({
                    "time":    ts,
                    "channel": channel,
                    "event":   "subscribe",
                    "payload": symbols,
                    "auth":    {
                        "method": "api_key",
                        "KEY":    self._key,
                        "SIGN":   sig,
                    },
                }))
                async for raw in ws:
                    msg = json.loads(raw)
                    if (msg.get("channel") != channel
                            or msg.get("event") != "update"):
                        continue
                    for t in msg.get("result", []):
                        sym  = t.get("currency_pair", "")
                        side = t.get("side", "")
                        amt  = safe_float(t.get("amount"))
                        px   = safe_float(t.get("price"))
                        fee  = safe_float(t.get("fee"))
                        fcy  = t.get("fee_currency", "")
                        if sym and side and amt > 0 and px > 0:
                            await on_fill(sym, side, amt, px, fee, fcy)
            except Exception as exc:
                if not self._ws_stop:
                    log.warning("FillWS error: %s – retry in %.0fs",
                                exc, backoff)
                    await asyncio.sleep(backoff)
                    backoff = min(backoff * 2, 30.0)

    async def close(self) -> None:
        self._ws_stop = True
        if self._sess and not self._sess.closed:
            await self._sess.close()


# ======================================================================
# LOCAL ORDER BOOK
# ======================================================================

@dataclass
class LocalBook:
    symbol:  str
    bids:    Dict[float, float] = field(default_factory=dict)
    asks:    Dict[float, float] = field(default_factory=dict)
    last_id: int  = 0
    ready:   bool = False

    def apply_snapshot(self, snap: Dict[str, Any]) -> None:
        self.bids.clear()
        self.asks.clear()
        for p, a in snap.get("bids", []):
            self.bids[float(p)] = float(a)
        for p, a in snap.get("asks", []):
            self.asks[float(p)] = float(a)
        self.last_id = int(snap.get("id", 0))
        self.ready   = True

    def apply_update(self, upd: Dict[str, Any]) -> bool:
        """
        Apply a delta update.
        Returns False if a sequence gap is detected (caller should resync).
        """
        U = int(upd["U"])
        u = int(upd["u"])
        if not self.ready:
            return False
        if u <= self.last_id:
            return True                   # stale, already applied
        if U > self.last_id + 1:
            return False                  # gap: resync needed
        for p, a in upd.get("b", []):
            pf = float(p); af = float(a)
            if af == 0.0:
                self.bids.pop(pf, None)
            else:
                self.bids[pf] = af
        for p, a in upd.get("a", []):
            pf = float(p); af = float(a)
            if af == 0.0:
                self.asks.pop(pf, None)
            else:
                self.asks[pf] = af
        self.last_id = u
        return True

    def top(self) -> Optional[Tuple[float, float]]:
        if not self.bids or not self.asks:
            return None
        return max(self.bids), min(self.asks)

    def mid(self) -> Optional[float]:
        t = self.top()
        return (t[0] + t[1]) / 2.0 if t else None

    def spread_bps(self) -> Optional[float]:
        t = self.top()
        if t is None:
            return None
        bb, ba = t
        return (ba - bb) / ((ba + bb) / 2.0) * 10_000

    def imbalance(self, n: int = 10) -> float:
        """
        [-1, +1]:  +1 = bid-heavy (buying pressure),  -1 = ask-heavy.
        """
        bv = sum(a for _, a in sorted(self.bids.items(), reverse=True)[:n])
        av = sum(a for _, a in sorted(self.asks.items())[:n])
        total = bv + av
        return (bv - av) / total if total > 0 else 0.0


# ======================================================================
# BOOK MANAGER  (snapshot + streaming, gap-safe)
# ======================================================================

class BookManager:
    def __init__(self, exchange: AbstractExchange,
                 symbols: List[str]) -> None:
        self._exchange = exchange
        self._symbols  = symbols
        self._books    = {s: LocalBook(s) for s in symbols}

    async def start(self) -> None:
        for sym in self._symbols:
            snap = await self._exchange.get_order_book(sym)
            self._books[sym].apply_snapshot(snap)
            log.info("book snapshot %s  id=%s",
                     sym, self._books[sym].last_id)
        await self._exchange.start_book_stream(
            self._symbols,
            on_snapshot=self._on_snapshot,
            on_update=self._on_update,
        )

    def _on_snapshot(self, sym: str, snap: Dict) -> None:
        self._books[sym].apply_snapshot(snap)

    def _on_update(self, sym: str, upd: Dict) -> None:
        if not self._books[sym].apply_update(upd):
            asyncio.create_task(self._resync(sym))

    async def _resync(self, sym: str) -> None:
        snap = await self._exchange.get_order_book(sym)
        self._books[sym].apply_snapshot(snap)
        log.warning("book resynced %s", sym)

    def book(self, sym: str) -> LocalBook:
        return self._books[sym]


# ======================================================================
# FILL LEDGER  (average-cost P&L, long/short support)
# ======================================================================

@dataclass
class FillLedger:
    symbol:    str
    base_ccy:  str
    quote_ccy: str

    position_base:   float = 0.0
    avg_cost_quote:  float = 0.0
    realized_pnl:    float = 0.0
    fees_paid:       float = 0.0
    total_buys_usd:  float = 0.0
    total_sells_usd: float = 0.0
    fill_count:      int   = 0

    def on_fill(self, side: str, amount: float, price: float,
                fee: float = 0.0, fee_ccy: str = "") -> None:
        side     = side.lower()
        notional = amount * price
        fee_quote = fee * price if fee_ccy == self.base_ccy else fee
        self.fees_paid  += fee_quote
        self.fill_count += 1

        if side == "buy":
            self.total_buys_usd += notional
            new_pos = self.position_base + amount
            if new_pos:
                self.avg_cost_quote = (
                    self.position_base * self.avg_cost_quote + notional
                ) / new_pos
            self.position_base = new_pos

        else:
            self.total_sells_usd += notional
            pos = self.position_base

            if pos >= amount:
                # normal long-side close
                self.realized_pnl  += (price - self.avg_cost_quote) * amount
                self.position_base -= amount
                if self.position_base < 1e-12:
                    self.avg_cost_quote = 0.0

            elif pos > 0:
                # partial close then flip to short
                self.realized_pnl  += (price - self.avg_cost_quote) * pos
                self.position_base  = -(amount - pos)
                self.avg_cost_quote = price

            else:
                # adding to existing short
                short_total = abs(pos) + amount
                self.avg_cost_quote = (
                    abs(pos) * self.avg_cost_quote + notional
                ) / short_total
                self.position_base -= amount

    def unrealized_pnl(self, mark: float) -> float:
        if self.position_base > 0:
            return (mark - self.avg_cost_quote) * self.position_base
        if self.position_base < 0:
            return (self.avg_cost_quote - mark) * abs(self.position_base)
        return 0.0

    def total_pnl(self, mark: float) -> float:
        return self.realized_pnl + self.unrealized_pnl(mark) - self.fees_paid

    def notional(self, price: float) -> float:
        return abs(self.position_base) * price

    def to_dict(self) -> Dict[str, Any]:
        keys = (
            "position_base", "avg_cost_quote", "realized_pnl",
            "fees_paid", "total_buys_usd", "total_sells_usd", "fill_count",
        )
        return {k: getattr(self, k) for k in keys}

    def load_dict(self, d: Dict[str, Any]) -> None:
        for k in self.to_dict():
            if k in d:
                setattr(self, k, d[k])


# ======================================================================
# EWMA VOLATILITY  (fast / slow dual-band + regime ratio)
# ======================================================================

class EWMAVol:
    def __init__(self, fast_span: int, slow_span: int) -> None:
        self._alpha_fast = 2.0 / (fast_span + 1)
        self._alpha_slow = 2.0 / (slow_span + 1)
        self._var_fast   = 0.0
        self._var_slow   = 0.0
        self._last_price: Optional[float] = None
        self._n = 0

    def update(self, price: float) -> None:
        if self._last_price and self._last_price > 0:
            r2 = math.log(price / self._last_price) ** 2
            self._var_fast = (self._alpha_fast * r2
                              + (1 - self._alpha_fast) * self._var_fast)
            self._var_slow = (self._alpha_slow * r2
                              + (1 - self._alpha_slow) * self._var_slow)
        self._last_price = price
        self._n         += 1

    @property
    def fast_bps(self) -> float:
        return math.sqrt(self._var_fast) * 10_000 if self._n > 2 else 0.0

    @property
    def slow_bps(self) -> float:
        return math.sqrt(self._var_slow) * 10_000 if self._n > 2 else 0.0

    @property
    def regime(self) -> float:
        """fast_var / slow_var.  >1 = current vol above long-run average."""
        return (self._var_fast / self._var_slow
                if self._var_slow > 1e-12 else 1.0)


# ======================================================================
# RISK MANAGER
# ======================================================================

class RiskManager:
    def __init__(self) -> None:
        self._killed  = False
        self._resume: Dict[str, float] = {}

    def kill(self, reason: str) -> None:
        log.critical("RISK KILL: %s", reason)
        self._killed = True

    def pause(self, sym: str, secs: float, reason: str) -> None:
        log.warning("PAUSE %s  %.0fs  (%s)", sym, secs, reason)
        self._resume[sym] = time.time() + secs

    def check(
        self, sym: str,
        ledgers: Dict[str, FillLedger],
        mid: float,
        sigma_bps: float,
        consec_err: int,
    ) -> Tuple[bool, str]:
        if self._killed:
            return False, "global kill"

        if sym in self._resume:
            if time.time() < self._resume[sym]:
                return False, "paused"
            del self._resume[sym]

        agg_pnl = sum(
            l.total_pnl(mid if l.symbol == sym else 0.0)
            for l in ledgers.values()
        )
        if agg_pnl < -cfg.stop_if_drawdown_usd:
            self.kill(f"drawdown {agg_pnl:.2f} USD")
            return False, "drawdown"

        ld = ledgers.get(sym)
        if ld and ld.notional(mid) > cfg.max_inventory_notional_usd * 1.5:
            self.pause(sym, 30, "inventory oversize")
            return False, "inventory cap"

        if sigma_bps > cfg.max_sigma_bps:
            return False, f"vol {sigma_bps:.1f} bps"

        if consec_err >= cfg.max_consecutive_errors:
            self.pause(sym, 60, f"{consec_err} consecutive errors")
            return False, "error backoff"

        return True, "ok"

    @property
    def killed(self) -> bool:
        return self._killed


# ======================================================================
# CIRCUIT BREAKER  (flash-crash detection)
# ======================================================================

class CircuitBreaker:
    _MAX_HIST = 500

    def __init__(self) -> None:
        self._hist:  Dict[str, List[Tuple[float, float]]] = {}
        self._pause: Dict[str, float] = {}

    def record(self, sym: str, px: float) -> None:
        buf = self._hist.setdefault(sym, [])
        buf.append((time.time(), px))
        if len(buf) > self._MAX_HIST:
            self._hist[sym] = buf[-self._MAX_HIST:]

    def ok(self, sym: str, px: float) -> bool:
        now = time.time()
        if sym in self._pause and now < self._pause[sym]:
            return False
        hist   = self._hist.get(sym, [])
        cutoff = now - cfg.cb_window_sec
        ref_px = next((p for ts, p in hist if ts >= cutoff), None)
        if ref_px is None:
            return True
        move_bps = abs(px - ref_px) / ref_px * 10_000
        if move_bps >= cfg.cb_bps:
            log.warning("CB %s  %.1f bps move", sym, move_bps)
            self._pause[sym] = now + cfg.cb_pause_sec
            return False
        return True


# ======================================================================
# PER-SYMBOL STATE
# ======================================================================

@dataclass
class SymbolState:
    symbol:    str
    base_ccy:  str
    quote_ccy: str
    spec:      InstrumentSpec = field(
        default_factory=lambda: InstrumentSpec("?"))
    ledger:    FillLedger = field(init=False)
    vol:       EWMAVol    = field(init=False)

    orders: Dict[str, OrderRecord] = field(default_factory=dict)

    last_quote_ts: float = 0.0
    last_hedge_ts: float = 0.0
    last_dca_ts:   float = 0.0
    last_mid:      float = 0.0
    consec_err:    int   = 0

    def __post_init__(self) -> None:
        self.ledger = FillLedger(self.symbol, self.base_ccy, self.quote_ccy)
        self.vol    = EWMAVol(cfg.ewma_fast_span, cfg.ewma_slow_span)
        self.spec   = InstrumentSpec(self.symbol)

    @property
    def open_orders(self) -> Dict[str, str]:
        return {
            oid: r.side for oid, r in self.orders.items()
            if r.status in (OrderStatus.PENDING, OrderStatus.OPEN)
        }

    @property
    def order_labels(self) -> Dict[str, str]:
        return {oid: r.label for oid, r in self.orders.items()}


# ======================================================================
# A-S MULTI-LEVEL QUOTING
# ======================================================================

@dataclass
class QuoteSet:
    bids: List[Tuple[float, float]]    # (price, size)
    asks: List[Tuple[float, float]]


def compute_quotes(
    mid:       float,
    sigma_bps: float,
    inventory: float,
    max_inv:   float,
    imbalance: float,
    regime:    float,
) -> QuoteSet:
    """
    Avellaneda-Stoikov reservation price + optimal spread.

    Extensions:
      - Multi-level layering with configurable size decay
      - Toxicity: imbalance shifts the reservation price so both quotes
        move together (spread width preserved).  Bid-heavy book raises
        r_adj, protecting against adverse selection on the ask side.
      - Regime multiplier: widens spread in choppy conditions.
    """
    sigma = bps_f(sigma_bps) * mid
    q     = clamp(inventory / max_inv, -1.0, 1.0) if max_inv else 0.0

    # A-S reservation price (inventory-adjusted mid)
    r = mid - cfg.gamma * (sigma ** 2) * q * cfg.horizon_sec

    # A-S optimal half-spread
    raw_half = (
        cfg.gamma * sigma ** 2 * cfg.horizon_sec / 2.0
        + (1.0 / cfg.gamma) * math.log(1.0 + cfg.gamma / cfg.kappa)
    ) / 2.0
    half_bps = clamp(
        raw_half / mid * 10_000 * max(1.0, regime),
        cfg.min_half_spread_bps,
        cfg.max_half_spread_bps,
    )
    half = bps_f(half_bps) * mid

    # Toxicity shift: positive imbalance -> bid heavy -> shift reservation
    # price up.  Both bid and ask rise together; spread width unchanged.
    tox_shift = imbalance * bps_f(cfg.tox_skew_scale_bps) * mid
    r_adj     = r + tox_shift

    bids_out: List[Tuple[float, float]] = []
    asks_out: List[Tuple[float, float]] = []
    for i in range(cfg.quote_levels):
        extra = bps_f(cfg.level_spacing_bps * i) * mid
        decay = cfg.level_size_decay ** i
        size  = cfg.order_notional_usd * decay / mid
        bids_out.append((r_adj - half - extra, size))
        asks_out.append((r_adj + half + extra, size))

    return QuoteSet(bids=bids_out, asks=asks_out)


# ======================================================================
# SESSION PERSISTENCE
# ======================================================================

def save_session(states: Dict[str, SymbolState]) -> None:
    try:
        with open(cfg.session_file, "w") as fh:
            json.dump(
                {sym: st.ledger.to_dict() for sym, st in states.items()},
                fh, indent=2,
            )
    except Exception as exc:
        log.warning("session save failed: %s", exc)


def load_session(states: Dict[str, SymbolState]) -> None:
    if not os.path.exists(cfg.session_file):
        return
    try:
        with open(cfg.session_file) as fh:
            data = json.load(fh)
        for sym, d in data.items():
            if sym in states:
                states[sym].ledger.load_dict(d)
                log.info(
                    "session restored %s  fills=%d  realPnL=%.4f",
                    sym,
                    states[sym].ledger.fill_count,
                    states[sym].ledger.realized_pnl,
                )
    except Exception as exc:
        log.warning("session load failed: %s", exc)


# ======================================================================
# HTTP METRICS  (/health   /metrics)
# ======================================================================

class MetricsServer:
    def __init__(self, engine: "Engine") -> None:
        self._engine = engine

    async def start(self) -> None:
        app = web.Application()
        app.router.add_get("/metrics", self._metrics)
        app.router.add_get("/health",  self._health)
        runner = web.AppRunner(app)
        await runner.setup()
        await web.TCPSite(runner, "0.0.0.0", cfg.metrics_port).start()
        log.info("metrics at http://0.0.0.0:%d/metrics", cfg.metrics_port)

    async def _metrics(
        self, _: web.Request
    ) -> web.Response:
        lines: List[str] = []
        for sym, st in self._engine.states.items():
            mid = self._engine.books.book(sym).mid() or 0.0
            ld  = st.ledger
            for name, val in [
                ("mid_price",          mid),
                ("position_base",      ld.position_base),
                ("realized_pnl_usd",   ld.realized_pnl),
                ("unrealized_pnl_usd", ld.unrealized_pnl(mid)),
                ("fees_paid_usd",      ld.fees_paid),
                ("total_pnl_usd",      ld.total_pnl(mid)),
                ("vol_fast_bps",       st.vol.fast_bps),
                ("vol_slow_bps",       st.vol.slow_bps),
                ("vol_regime",         st.vol.regime),
                ("open_orders",        len(st.open_orders)),
                ("fill_count",         ld.fill_count),
            ]:
                lines.append(
                    f'gateio_mm_{name}{{symbol="{sym}"}} {val:.8f}'
                )
        return web.Response(
            text="\n".join(lines), content_type="text/plain"
        )

    async def _health(
        self, _: web.Request
    ) -> web.Response:
        ok = not self._engine.risk.killed and self._engine._running
        return web.json_response(
            {
                "ok":          ok,
                "dry_run":     cfg.dry_run,
                "symbols":     cfg.symbols,
                "uptime_sec":  int(time.time() - self._engine._start_ts),
                "risk_killed": self._engine.risk.killed,
            },
            status=200 if ok else 503,
        )


# ======================================================================
# ENGINE   (depends on AbstractExchange, not Gate.io directly)
# ======================================================================

class Engine:
    def __init__(self, exchange: AbstractExchange) -> None:
        self._exchange = exchange
        self.books     = BookManager(exchange, cfg.symbols)
        self.states    = {
            s: SymbolState(s, *pair_parts(s)) for s in cfg.symbols
        }
        self.risk      = RiskManager()
        self.cb        = CircuitBreaker()
        self._metrics  = MetricsServer(self)
        self._running  = True
        self._start_ts = time.time()

    # -- startup -------------------------------------------------------

    async def start(self) -> None:
        log.info("starting  symbols=%s  dry_run=%s",
                 cfg.symbols, cfg.dry_run)
        cfg.validate_params()
        await self._load_specs()
        if not cfg.dry_run:
            await self._check_balances()
        load_session(self.states)
        await self.books.start()
        if not cfg.dry_run:
            await self._exchange.start_fill_stream(cfg.symbols, self._on_fill)
            await asyncio.sleep(1.5)
            await self._reconcile_open_orders()
        asyncio.create_task(self._engine_loop())
        asyncio.create_task(self._status_loop())
        asyncio.create_task(self._persist_loop())
        await self._metrics.start()

    async def _load_specs(self) -> None:
        for sym in cfg.symbols:
            try:
                spec = await self._exchange.get_instrument_spec(sym)
                self.states[sym].spec = spec
                log.info(
                    "spec %s  price_dp=%d  amt_dp=%d  min_total=%.4f",
                    sym, spec.price_dp, spec.amount_dp, spec.min_total,
                )
            except Exception as exc:
                log.warning("spec %s: %s (using defaults)", sym, exc)

    async def _check_balances(self) -> None:
        try:
            bal = await self._exchange.get_balances()
            for sym in cfg.symbols:
                base, quote = pair_parts(sym)
                b_base  = bal.get(base,  0.0)
                b_quote = bal.get(quote, 0.0)
                log.info("balance %s  %s=%.6f  %s=%.6f",
                         sym, base, b_base, quote, b_quote)
                if b_quote < cfg.order_notional_usd:
                    log.warning(
                        "low quote balance %s: %.2f < order_notional %.2f",
                        sym, b_quote, cfg.order_notional_usd,
                    )
        except Exception as exc:
            log.warning("balance check failed: %s", exc)

    async def _reconcile_open_orders(self) -> None:
        for sym in cfg.symbols:
            try:
                open_orders = await self._exchange.list_open_orders(sym)
                st = self.states[sym]
                for o in open_orders:
                    oid   = o.get("id", "")
                    side  = o.get("side", "")
                    price = safe_float(o.get("price"))
                    size  = safe_float(o.get("amount"))
                    label = o.get("text", "unknown")
                    if oid and oid not in st.orders:
                        st.orders[oid] = OrderRecord(
                            oid=oid, sym=sym, side=side,
                            price=price, size=size,
                            label=label, status=OrderStatus.OPEN,
                        )
                if open_orders:
                    log.info("reconciled %s  %d open orders",
                             sym, len(open_orders))
            except Exception as exc:
                log.warning("reconcile %s: %s", sym, exc)

    # -- shutdown ------------------------------------------------------

    async def shutdown(self) -> None:
        log.info("shutting down")
        self._running = False
        for sym in cfg.symbols:
            await self._exchange.cancel_all(sym)
        save_session(self.states)
        await self._exchange.close()
        log.info("clean shutdown complete")

    # -- fill callback -------------------------------------------------

    async def _on_fill(self, sym: str, side: str, amt: float,
                       px: float, fee: float, fee_ccy: str) -> None:
        if sym not in self.states:
            return
        st = self.states[sym]
        st.ledger.on_fill(side, amt, px, fee, fee_ccy)
        mid = self.books.book(sym).mid() or px
        log.info(
            "FILL %-12s %4s  amt=%.6f  px=%.6f  fee=%.6f %s"
            "  pos=%+.6f  tPnL=%+.4f",
            sym, side.upper(), amt, px, fee, fee_ccy,
            st.ledger.position_base, st.ledger.total_pnl(mid),
        )

    # -- engine loop ---------------------------------------------------

    async def _engine_loop(self) -> None:
        interval = 1.0 / cfg.engine_hz
        while self._running and not self.risk.killed:
            t0 = time.time()
            await asyncio.gather(
                *[self._tick(s) for s in cfg.symbols],
                return_exceptions=True,
            )
            await asyncio.sleep(max(0.0, interval - (time.time() - t0)))

    async def _tick(self, sym: str) -> None:
        st   = self.states[sym]
        book = self.books.book(sym)
        if not book.ready:
            return
        mid = book.mid()
        if not mid:
            return

        st.vol.update(mid)
        self.cb.record(sym, mid)
        if not self.cb.ok(sym, mid):
            return

        sigma_bps = st.vol.fast_bps
        ok, _reason = self.risk.check(
            sym,
            {s: self.states[s].ledger for s in self.states},
            mid, sigma_bps, st.consec_err,
        )
        if not ok:
            return

        now       = time.time()
        drift_bps = (
            abs(mid - st.last_mid) / mid * 10_000
            if st.last_mid else 999.0
        )

        if (drift_bps >= cfg.spread_lock_bps
                or now - st.last_quote_ts >= cfg.quote_refresh_sec):
            await self._requote(sym, mid, sigma_bps)
            st.last_quote_ts = now
            st.last_mid      = mid

        if cfg.dca_enabled and now - st.last_dca_ts >= cfg.dca_refresh_sec:
            await self._dca(sym, mid, sigma_bps)
            st.last_dca_ts = now

        if now - st.last_hedge_ts >= cfg.hedge_cooldown:
            await self._hedge(sym, mid)

    # -- quoting -------------------------------------------------------

    async def _requote(self, sym: str, mid: float,
                       sigma_bps: float) -> None:
        st      = self.states[sym]
        book    = self.books.book(sym)
        spec    = st.spec
        max_inv = cfg.max_inventory_notional_usd / mid if mid else 1.0

        qs = compute_quotes(
            mid=mid,
            sigma_bps=sigma_bps,
            inventory=st.ledger.position_base,
            max_inv=max_inv,
            imbalance=book.imbalance(cfg.tox_depth_levels),
            regime=st.vol.regime,
        )

        # cancel only our MM-labelled quotes
        mm_oids = [
            oid for oid, rec in st.orders.items()
            if rec.label.startswith("mm-")
            and rec.status in (OrderStatus.PENDING, OrderStatus.OPEN)
        ]
        for oid in mm_oids:
            try:
                await self._exchange.cancel_order(sym, oid)
            except Exception:
                pass
            if oid in st.orders:
                st.orders[oid].status = OrderStatus.CANCELLED

        if len(st.open_orders) >= cfg.max_open_per_symbol:
            return
        top = book.top()
        if not top:
            return
        bb, ba = top

        for i, (bid_px, bid_sz) in enumerate(qs.bids):
            bid_px = min(bid_px, bb - spec.tick_size * (i + 1))
            if bid_px <= 0:
                continue
            if bid_px * bid_sz < spec.min_notional():
                continue
            if bid_sz < spec.min_amount:
                continue
            await self._place(sym, "buy", bid_sz, bid_px, "poc",
                              f"mm-bid-{i}")

        for i, (ask_px, ask_sz) in enumerate(qs.asks):
            ask_px = max(ask_px, ba + spec.tick_size * (i + 1))
            if ask_px * ask_sz < spec.min_notional():
                continue
            if ask_sz < spec.min_amount:
                continue
            await self._place(sym, "sell", ask_sz, ask_px, "poc",
                              f"mm-ask-{i}")

    # -- DCA -----------------------------------------------------------

    async def _dca(self, sym: str, mid: float,
                   sigma_bps: float) -> None:
        if sigma_bps > cfg.dca_max_sigma_bps:
            return   # don't ladder into elevated volatility

        st      = self.states[sym]
        max_inv = cfg.max_inventory_notional_usd / mid if mid else 1.0
        skew    = st.ledger.position_base / max_inv if max_inv else 0.0
        if abs(skew) < 0.25:
            return   # inventory close enough to flat

        # widen step proportionally to current vol vs baseline
        vol_scale = max(
            1.0, sigma_bps / cfg.dca_vol_baseline_bps
        ) * cfg.dca_vol_scale_factor
        step_bps = cfg.dca_step_bps * vol_scale

        side = "buy" if skew < 0.0 else "sell"
        for i in range(1, cfg.dca_levels + 1):
            off = bps_f(step_bps * i) * mid
            px  = (mid - off) if side == "buy" else (mid + off)
            sz  = cfg.dca_clip_usd / px
            if sz * px < max(st.spec.min_total, 1.0):
                continue
            await self._place(sym, side, sz, px, "gtc", f"dca-{i}")

    # -- hedge ---------------------------------------------------------

    async def _hedge(self, sym: str, mid: float) -> None:
        st      = self.states[sym]
        max_inv = cfg.max_inventory_notional_usd / mid if mid else 1.0
        pos     = st.ledger.position_base
        frac    = abs(pos) / max_inv if max_inv else 0.0
        if frac < cfg.hedge_trigger_frac:
            return

        qty = (abs(pos) - cfg.hedge_trigger_frac * max_inv) * cfg.hedge_ioc_frac
        if qty * mid < max(st.spec.min_total, 1.0):
            return

        side = "sell" if pos > 0 else "buy"
        log.info("hedge %s %s %.6f  skew=%.1f%%",
                 sym, side, qty, frac * 100)
        result = await self._place(sym, side, qty, mid, "ioc", "hedge")
        if result == PlaceResult.PLACED:
            st.last_hedge_ts = time.time()

    # -- place helper --------------------------------------------------

    async def _place(
        self, sym: str, side: str, size: float, price: float,
        tif: str, label: str,
    ) -> PlaceResult:
        st = self.states[sym]

        if cfg.dry_run:
            log.debug("DRY %s %s %s  sz=%.6f  px=%.6f",
                      sym, side, label, size, price)
            return PlaceResult.DRY

        try:
            resp = await self._exchange.create_limit(
                sym, side, size, price,
                tif=tif, text=label,
                stp_act=cfg.stp_act,
                spec=st.spec,
            )
            oid = resp.get("id", "")
            if oid:
                st.orders[oid] = OrderRecord(
                    oid=oid, sym=sym, side=side,
                    price=price, size=size,
                    label=label, status=OrderStatus.PENDING,
                )
            st.consec_err = 0
            return PlaceResult.PLACED

        except Exception as exc:
            err = str(exc)
            if "POC" in err or "post only" in err.lower():
                return PlaceResult.REJECTED   # normal, not an error
            log.warning("place %s %s @ %.6f: %s", sym, side, price, exc)
            st.consec_err += 1
            return PlaceResult.ERROR

    # -- status loop ---------------------------------------------------

    async def _status_loop(self) -> None:
        while self._running:
            await asyncio.sleep(cfg.status_sec)
            self._log_status()

    def _log_status(self) -> None:
        W    = 92
        rows = ["=" * W]
        agg_pnl = agg_fees = 0.0
        for sym in cfg.symbols:
            st  = self.states[sym]
            mid = self.books.book(sym).mid() or 0.0
            ld  = st.ledger
            r   = ld.realized_pnl
            u   = ld.unrealized_pnl(mid)
            t   = ld.total_pnl(mid)
            agg_pnl  += t
            agg_fees += ld.fees_paid
            cb_tag    = "" if self.cb.ok(sym, mid) else " [CB]"
            rows.append(
                f"  {sym:<14} mid={mid:>14.6f}"
                f"  pos={ld.position_base:>+12.6f}"
                f"  rPnL={r:>+9.4f}  uPnL={u:>+9.4f}  tPnL={t:>+9.4f}"
                f"  s={st.vol.fast_bps:>5.1f}bps"
                f"  rg={st.vol.regime:>4.2f}"
                f"  ord={len(st.open_orders):>2}{cb_tag}"
            )
        dry_tag  = "  [DRY]"  if cfg.dry_run       else ""
        kill_tag = "  [KILL]" if self.risk.killed   else ""
        rows.append(
            f"  {'TOTAL':<14}"
            f"  pnl={agg_pnl:>+9.4f} USDT"
            f"  fees={agg_fees:>8.4f} USDT"
            f"  up={int(time.time()-self._start_ts)}s"
            + dry_tag + kill_tag
        )
        rows.append("=" * W)
        log.info("\n" + "\n".join(rows))

    async def _persist_loop(self) -> None:
        while self._running:
            await asyncio.sleep(cfg.persist_sec)
            save_session(self.states)


# ======================================================================
# ENTRY POINT
# ======================================================================

async def main() -> None:
    rl       = RateLimiter(cfg.rate_limit_burst, cfg.rate_limit_rps)
    exchange = GateExchange(
        cfg.gateio_api_key, cfg.gateio_api_secret,
        cfg.base_url, cfg.ws_url, rl,
    )
    engine = Engine(exchange)
    loop   = asyncio.get_running_loop()

    def _handle_signal(sig: int, _: Any) -> None:
        log.info("signal %d received, shutting down", sig)
        asyncio.create_task(engine.shutdown())
        loop.call_later(8, loop.stop)

    signal.signal(signal.SIGINT,  _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)

    await engine.start()

    while engine._running and not engine.risk.killed:
        await asyncio.sleep(1.0)

    if engine.risk.killed:
        await engine.shutdown()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
