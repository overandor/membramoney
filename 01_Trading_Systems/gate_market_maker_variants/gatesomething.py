from __future__ import annotations

"""
gate_multi_pair_mm_spread_capture.py

Gate.io futures multi-pair market maker + spread-capture foundation.
Public market data uses WebSocket incremental books.
Trading/account operations use REST for simpler reconciliation.

What this version adds
----------------------
- Places maker quotes at best bid and best ask
- Can optionally step inside by one tick when allowed
- Tracks fills by comparing hydrated positions
- After a long fill, works exit at best ask or takes bid if net profit after fees is positive
- After a short fill, works cover at best bid or takes ask if net profit after fees is positive
- Keeps tiny notional and inventory/risk caps
- Separate entry and exit order roles

Important
---------
- "First in line" cannot be guaranteed. This bot only follows top-of-book aggressively.
- Keep this in dry mode until you validate every payload on your own Gate.io account.

Install:
    pip install requests websockets

Examples:
    python gate_multi_pair_mm_spread_capture.py --dry
    python gate_multi_pair_mm_spread_capture.py --live
    python gate_multi_pair_mm_spread_capture.py --balance
    python gate_multi_pair_mm_spread_capture.py --positions
    python gate_multi_pair_mm_spread_capture.py --cancel-all
    python gate_multi_pair_mm_spread_capture.py --flatten-all
"""

import argparse
import asyncio
import contextlib
import hashlib
import hmac
import json
import logging
import os
import random
import signal
import ssl
import sys
import time
import traceback
from collections import deque
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from decimal import Decimal, ROUND_DOWN, ROUND_HALF_UP, getcontext
from pathlib import Path
from typing import Any, Deque, Dict, Iterable, List, Optional, Tuple

import requests
import websockets

getcontext().prec = 28

APP_NAME = "gate-multi-pair-mm-spread-capture"
VERSION = "6.1"

# =============================================================================
# CONFIG
# =============================================================================

GATE_API_KEY = os.getenv("GATE_API_KEY", "")
GATE_API_SECRET = os.getenv("GATE_API_SECRET", "")
SETTLE = os.getenv("GATE_SETTLE", "usdt").lower()

USE_TESTNET = os.getenv("USE_TESTNET", "0") == "1"

REST_BASE_URL = os.getenv("GATE_BASE_URL", "https://api.gateio.ws/api/v4").rstrip("/")
if USE_TESTNET and "GATE_BASE_URL" not in os.environ:
    REST_BASE_URL = "https://fx-api-testnet.gateio.ws/api/v4"

WS_URL = os.getenv("GATE_WS_URL", "").strip()
if not WS_URL:
    if USE_TESTNET:
        if SETTLE == "usdt":
            WS_URL = "wss://ws-testnet.gate.com/v4/ws/futures/usdt"
        else:
            WS_URL = f"wss://fx-ws-testnet.gateio.ws/v4/ws/{SETTLE}"
    else:
        WS_URL = f"wss://fx-ws.gateio.ws/v4/ws/{SETTLE}"

# universe
MAX_CONTRACT_NOMINAL_USD = Decimal(os.getenv("MAX_CONTRACT_NOMINAL_USD", "0.15"))
MIN_VOLUME_USDT = Decimal(os.getenv("MIN_VOLUME_USDT", "250000"))
MAX_SYMBOLS = int(os.getenv("MAX_SYMBOLS", "24"))
UNIVERSE_REFRESH_SECONDS = int(os.getenv("UNIVERSE_REFRESH_SECONDS", "60"))
INCLUDE_SYMBOLS = [s.strip().upper() for s in os.getenv("INCLUDE_SYMBOLS", "").split(",") if s.strip()]
EXCLUDE_SYMBOLS = {s.strip().upper() for s in os.getenv("EXCLUDE_SYMBOLS", "").split(",") if s.strip()}

# quote timing
QUOTE_INTERVAL_SECONDS = float(os.getenv("QUOTE_INTERVAL_SECONDS", "0.60"))
ENTRY_ORDER_TTL_SECONDS = float(os.getenv("ENTRY_ORDER_TTL_SECONDS", "2.20"))
EXIT_ORDER_TTL_SECONDS = float(os.getenv("EXIT_ORDER_TTL_SECONDS", "1.20"))
REPRICE_MIN_BPS = Decimal(os.getenv("REPRICE_MIN_BPS", "0.00"))
TOP_LEVELS = int(os.getenv("TOP_LEVELS", "20"))
WS_BOOK_PUSH = os.getenv("WS_BOOK_PUSH", "100ms")
MAX_POSITION_HOLD_SECONDS = float(os.getenv("MAX_POSITION_HOLD_SECONDS", "20"))

# risk
LEVERAGE = int(os.getenv("LEVERAGE", "3"))
BASE_ORDER_NOTIONAL_USD = Decimal(os.getenv("BASE_ORDER_NOTIONAL_USD", "0.05"))
MAX_PORTFOLIO_GROSS_USD = Decimal(os.getenv("MAX_PORTFOLIO_GROSS_USD", "2.00"))
MAX_PORTFOLIO_NET_USD = Decimal(os.getenv("MAX_PORTFOLIO_NET_USD", "1.00"))
MAX_SYMBOL_GROSS_USD = Decimal(os.getenv("MAX_SYMBOL_GROSS_USD", "0.30"))
MAX_SYMBOL_NET_USD = Decimal(os.getenv("MAX_SYMBOL_NET_USD", "0.20"))
SKEW_FACTOR = Decimal(os.getenv("SKEW_FACTOR", "1.0"))

# spread / fill-to-exit logic
MIN_SPREAD_BPS = Decimal(os.getenv("MIN_SPREAD_BPS", "0.0"))
JOIN_TOP_ONLY = os.getenv("JOIN_TOP_ONLY", "1") == "1"
ALLOW_STEP_INSIDE = os.getenv("ALLOW_STEP_INSIDE", "0") == "1"
ENTRY_MAKER_FEE_RATE = Decimal(os.getenv("ENTRY_MAKER_FEE_RATE", "0.0002"))
EXIT_MAKER_FEE_RATE = Decimal(os.getenv("EXIT_MAKER_FEE_RATE", "0.0002"))
EXIT_TAKER_FEE_RATE = Decimal(os.getenv("EXIT_TAKER_FEE_RATE", "0.0005"))
MIN_NET_PROFIT_USDT = Decimal(os.getenv("MIN_NET_PROFIT_USDT", "0.0002"))
ALLOW_TAKER_EXIT = os.getenv("ALLOW_TAKER_EXIT", "1") == "1"
ALLOW_TIMEOUT_EXIT = os.getenv("ALLOW_TIMEOUT_EXIT", "1") == "1"

# safety
PING_SECONDS = float(os.getenv("PING_SECONDS", "10"))
PUBLIC_RECONNECT_SECONDS = float(os.getenv("PUBLIC_RECONNECT_SECONDS", "2.0"))
API_TIMEOUT = float(os.getenv("API_TIMEOUT", "10.0"))
API_RETRIES = int(os.getenv("API_RETRIES", "3"))
API_RETRY_SLEEP = float(os.getenv("API_RETRY_SLEEP", "0.5"))
MAX_CONSECUTIVE_MAIN_ERRORS = int(os.getenv("MAX_CONSECUTIVE_MAIN_ERRORS", "25"))
COUNTDOWN_CANCEL_TIMEOUT = int(os.getenv("COUNTDOWN_CANCEL_TIMEOUT", "5"))

# files
STATE_FILE = Path(os.getenv("STATE_FILE", "gate_mm_state.json"))
JSONL_LOG = Path(os.getenv("JSONL_LOG", "gate_mm_events.jsonl"))

# runtime
DRY_RUN = True

# =============================================================================
# LOGGING
# =============================================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(APP_NAME)

# =============================================================================
# HELPERS
# =============================================================================


def now_ts() -> float:
    return time.time()


def now_ms() -> int:
    return int(time.time() * 1000)


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def ensure_parent(path: Path) -> None:
    if path.parent and not path.parent.exists():
        path.parent.mkdir(parents=True, exist_ok=True)


def event_log(kind: str, **payload: Any) -> None:
    ensure_parent(JSONL_LOG)
    rec = {
        "ts": now_iso(),
        "kind": kind,
        "app": APP_NAME,
        "version": VERSION,
        **payload,
    }
    try:
        with open(JSONL_LOG, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, separators=(",", ":"), ensure_ascii=False) + "\n")
    except Exception:
        log.exception("event_log failed")


def safe_int(x: Any, default: int = 0) -> int:
    try:
        return int(float(x))
    except Exception:
        return default


def safe_float(x: Any, default: float = 0.0) -> float:
    try:
        return float(x)
    except Exception:
        return default


def D(x: Any, default: str = "0") -> Decimal:
    try:
        if isinstance(x, Decimal):
            return x
        return Decimal(str(x))
    except Exception:
        return Decimal(default)


def clamp_dec(x: Decimal, lo: Decimal, hi: Decimal) -> Decimal:
    return max(lo, min(hi, x))


def jitter(seconds: float, frac: float = 0.15) -> float:
    return seconds * (1.0 + random.uniform(-frac, frac))


def sha512_hex(s: str) -> str:
    return hashlib.sha512(s.encode("utf-8")).hexdigest()


def bps_diff(a: Decimal, b: Decimal) -> Decimal:
    if a <= 0 or b <= 0:
        return Decimal("0")
    mid = (a + b) / Decimal("2")
    if mid <= 0:
        return Decimal("0")
    return (abs(a - b) / mid) * Decimal("10000")


def spread_bps(bid: Decimal, ask: Decimal) -> Decimal:
    if bid <= 0 or ask <= 0 or ask < bid:
        return Decimal("0")
    mid = (bid + ask) / Decimal("2")
    if mid <= 0:
        return Decimal("0")
    return ((ask - bid) / mid) * Decimal("10000")


def make_text_tag(*parts: str) -> str:
    seed = "|".join(parts)
    digest = hashlib.sha256(seed.encode("utf-8")).hexdigest()[:20]
    return f"t-{digest}"[:28]


def decimal_to_wire(x: Decimal) -> str:
    s = format(x, "f")
    if "." in s:
        s = s.rstrip("0").rstrip(".")
    return s or "0"


def floor_to_step(value: Decimal, step: Decimal) -> Decimal:
    if step <= 0:
        return value
    steps = (value / step).to_integral_value(rounding=ROUND_DOWN)
    return (steps * step).normalize()


def round_to_tick(price: Decimal, tick: Decimal) -> Decimal:
    if tick <= 0:
        return price
    steps = (price / tick).to_integral_value(rounding=ROUND_HALF_UP)
    return (steps * tick).normalize()


def order_create_time(order: Dict[str, Any]) -> float:
    ms = safe_float(order.get("create_time_ms", 0.0))
    if ms > 1e12:
        return ms / 1000.0
    s = safe_float(order.get("create_time", 0.0))
    if s > 0:
        return s
    return now_ts()


# =============================================================================
# DATA MODELS
# =============================================================================


@dataclass
class ContractMeta:
    symbol: str
    last_price: Decimal
    quanto_multiplier: Decimal
    order_size_min: Decimal
    order_size_max: Decimal
    order_price_round: Decimal
    leverage_min: int
    leverage_max: int
    volume_24h_quote: Decimal

    @property
    def nominal(self) -> Decimal:
        return self.last_price * self.quanto_multiplier


@dataclass
class HedgeInventory:
    long_contracts: Decimal = Decimal("0")
    short_contracts: Decimal = Decimal("0")
    long_entry_price: Decimal = Decimal("0")
    short_entry_price: Decimal = Decimal("0")

    def gross_contracts(self) -> Decimal:
        return self.long_contracts + self.short_contracts

    def net_contracts(self) -> Decimal:
        return self.long_contracts - self.short_contracts


@dataclass
class QuoteIntent:
    symbol: str
    side: str
    price: Decimal
    size: Decimal
    tif: str = "poc"
    reduce_only: bool = False
    role: str = "entry"

    def key(self) -> Tuple[str, str, str]:
        return (self.symbol, self.side, self.role)


@dataclass
class LiveOrder:
    order_id: str
    symbol: str
    side: str
    price: Decimal
    size: Decimal
    text: str
    created_ts: float
    status: str = "open"
    role: str = "entry"

    def age(self) -> float:
        return max(0.0, now_ts() - self.created_ts)


@dataclass
class ManagedLeg:
    symbol: str
    entry_side: str
    qty: Decimal
    entry_price: Decimal
    opened_ts: float

    def age(self) -> float:
        return max(0.0, now_ts() - self.opened_ts)


@dataclass
class PersistedState:
    cycle: int = 0
    last_universe_refresh: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)


# =============================================================================
# STATE STORE
# =============================================================================


class StateStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        self._lock = asyncio.Lock()

    def load(self) -> PersistedState:
        if not self.path.exists():
            return PersistedState()
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            return PersistedState(
                cycle=safe_int(data.get("cycle", 0)),
                last_universe_refresh=safe_float(data.get("last_universe_refresh", 0.0)),
                metadata=dict(data.get("metadata", {})),
            )
        except Exception as exc:
            event_log("state_load_error", error=str(exc))
            return PersistedState(metadata={"load_error": str(exc)})

    async def save(self, state: PersistedState) -> None:
        ensure_parent(self.path)
        tmp = self.path.with_suffix(".tmp")
        raw = json.dumps(asdict(state), indent=2, sort_keys=True, ensure_ascii=False)
        async with self._lock:
            tmp.write_text(raw, encoding="utf-8")
            tmp.replace(self.path)


# =============================================================================
# REST CLIENT
# =============================================================================


class GateRestClient:
    def __init__(self, key: str, secret: str, base_url: str, settle: str) -> None:
        self.key = key
        self.secret = secret
        self.base_url = base_url.rstrip("/")
        self.settle = settle.lower()
        self.session = requests.Session()

    def _public_headers(self) -> Dict[str, str]:
        return {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "X-Gate-Size-Decimal": "1",
        }

    def _signed_headers(self, method: str, path: str, query_string: str, payload: str) -> Dict[str, str]:
        ts = str(int(time.time()))
        sign_str = f"{method.upper()}\n{path}\n{query_string}\n{sha512_hex(payload)}\n{ts}"
        sign = hmac.new(
            self.secret.encode("utf-8"),
            sign_str.encode("utf-8"),
            digestmod=hashlib.sha512,
        ).hexdigest()
        return {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "KEY": self.key,
            "Timestamp": ts,
            "SIGN": sign,
            "X-Gate-Size-Decimal": "1",
        }

    def _request(
        self,
        method: str,
        path: str,
        *,
        params: Optional[Dict[str, Any]] = None,
        payload_obj: Optional[Dict[str, Any]] = None,
        private: bool = False,
    ) -> Any:
        params = params or {}
        payload_obj = payload_obj or {}

        query_string = "&".join(
            f"{k}={requests.utils.quote(str(v), safe='')}"
            for k, v in sorted(params.items())
            if v is not None
        )
        payload = json.dumps(payload_obj, separators=(",", ":"), ensure_ascii=False) if payload_obj else ""
        url = f"{self.base_url}{path}"
        if query_string:
            url = f"{url}?{query_string}"

        headers = self._signed_headers(method, path, query_string, payload) if private else self._public_headers()

        last_exc: Optional[Exception] = None
        for attempt in range(1, API_RETRIES + 1):
            try:
                r = self.session.request(
                    method=method.upper(),
                    url=url,
                    headers=headers,
                    data=payload if payload else None,
                    timeout=API_TIMEOUT,
                )
                if r.status_code >= 400:
                    raise RuntimeError(f"HTTP {r.status_code}: {r.text[:1000]}")
                if not r.text.strip():
                    return None
                return r.json()
            except Exception as exc:
                last_exc = exc
                event_log("api_retry", method=method, path=path, attempt=attempt, error=str(exc))
                if attempt < API_RETRIES:
                    time.sleep(API_RETRY_SLEEP * attempt)

        raise RuntimeError(f"API request failed {method} {path}: {last_exc}")

    # public
    def list_contracts(self) -> List[Dict[str, Any]]:
        return self._request("GET", f"/futures/{self.settle}/contracts") or []

    def order_book_snapshot(self, symbol: str, limit: int = 20, with_id: bool = True) -> Dict[str, Any]:
        return self._request(
            "GET",
            f"/futures/{self.settle}/order_book",
            params={"contract": symbol, "limit": limit, "with_id": "true" if with_id else "false"},
        ) or {}

    # private
    def account(self) -> Dict[str, Any]:
        try:
            return self._request("GET", f"/futures/{self.settle}/accounts", private=True) or {}
        except Exception:
            return self._request("GET", f"/futures/{self.settle}/account", private=True) or {}

    def positions(self) -> List[Dict[str, Any]]:
        return self._request("GET", f"/futures/{self.settle}/positions", private=True) or []

    def open_orders(self, symbol: str = "") -> List[Dict[str, Any]]:
        params: Dict[str, Any] = {"status": "open"}
        if symbol:
            params["contract"] = symbol
        return self._request(
            "GET",
            f"/futures/{self.settle}/orders",
            params=params,
            private=True,
        ) or []

    def create_order(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return self._request(
            "POST",
            f"/futures/{self.settle}/orders",
            payload_obj=payload,
            private=True,
        ) or {}

    def cancel_order(self, order_id: str) -> Dict[str, Any]:
        return self._request(
            "DELETE",
            f"/futures/{self.settle}/orders/{order_id}",
            private=True,
        ) or {}

    def set_dual_mode(self, enabled: bool) -> Any:
        return self._request(
            "POST",
            f"/futures/{self.settle}/dual_mode",
            payload_obj={"dual_mode": enabled},
            private=True,
        )

    def set_leverage(self, symbol: str, leverage: int) -> Any:
        payload = {"leverage": str(leverage), "cross_leverage_limit": str(leverage)}
        return self._request(
            "POST",
            f"/futures/{self.settle}/positions/{symbol}/leverage",
            payload_obj=payload,
            private=True,
        )

    def countdown_cancel_all(self, timeout_seconds: int) -> Any:
        return self._request(
            "POST",
            f"/futures/{self.settle}/countdown_cancel_all",
            payload_obj={"timeout": int(timeout_seconds)},
            private=True,
        )


# =============================================================================
# LOCAL ORDER BOOK
# =============================================================================


class LocalBook:
    def __init__(self, symbol: str) -> None:
        self.symbol = symbol
        self.id: int = 0
        self.timestamp_ms: int = 0
        self.bids: Dict[Decimal, Decimal] = {}
        self.asks: Dict[Decimal, Decimal] = {}
        self.buffer: Deque[Dict[str, Any]] = deque(maxlen=5000)
        self.ready = False

    def best_bid(self) -> Decimal:
        return max(self.bids.keys()) if self.bids else Decimal("0")

    def best_ask(self) -> Decimal:
        return min(self.asks.keys()) if self.asks else Decimal("0")

    def top_bid_size(self) -> Decimal:
        p = self.best_bid()
        return self.bids.get(p, Decimal("0")) if p > 0 else Decimal("0")

    def top_ask_size(self) -> Decimal:
        p = self.best_ask()
        return self.asks.get(p, Decimal("0")) if p > 0 else Decimal("0")

    def apply_snapshot(self, snapshot: Dict[str, Any]) -> None:
        self.id = safe_int(snapshot.get("id", 0))
        self.timestamp_ms = safe_int(snapshot.get("current", now_ms()))
        self.bids.clear()
        self.asks.clear()

        for row in snapshot.get("bids", []) or []:
            p = D(row.get("p", "0") if isinstance(row, dict) else row[0] if len(row) > 0 else "0")
            s = D(row.get("s", "0") if isinstance(row, dict) else row[1] if len(row) > 1 else "0")
            if p > 0 and s > 0:
                self.bids[p] = s

        for row in snapshot.get("asks", []) or []:
            p = D(row.get("p", "0") if isinstance(row, dict) else row[0] if len(row) > 0 else "0")
            s = D(row.get("s", "0") if isinstance(row, dict) else row[1] if len(row) > 1 else "0")
            if p > 0 and s > 0:
                self.asks[p] = s

    def buffer_update(self, msg: Dict[str, Any]) -> None:
        self.buffer.append(msg)

    def _apply_levels(self, side_levels: List[Any], target: Dict[Decimal, Decimal]) -> None:
        for lvl in side_levels or []:
            p = D(lvl.get("p", "0") if isinstance(lvl, dict) else lvl[0] if len(lvl) > 0 else "0")
            s = D(lvl.get("s", "0") if isinstance(lvl, dict) else lvl[1] if len(lvl) > 1 else "0")
            if p <= 0:
                continue
            if s <= 0:
                target.pop(p, None)
            else:
                target[p] = s

    def apply_update(self, msg: Dict[str, Any]) -> bool:
        result = msg.get("result", {}) or {}
        U = safe_int(result.get("U", 0))
        u = safe_int(result.get("u", 0))

        if self.id and U > self.id + 1:
            return False

        self._apply_levels(result.get("b", []) or result.get("bids", []), self.bids)
        self._apply_levels(result.get("a", []) or result.get("asks", []), self.asks)

        self.id = u if u > 0 else self.id
        self.timestamp_ms = safe_int(result.get("t", now_ms()))
        return True

    def sync_from_snapshot_and_buffer(self, snapshot: Dict[str, Any]) -> bool:
        self.apply_snapshot(snapshot)
        base_id = self.id
        buffered = list(self.buffer)

        start_idx = None
        for i, msg in enumerate(buffered):
            result = msg.get("result", {}) or {}
            U = safe_int(result.get("U", 0))
            u = safe_int(result.get("u", 0))
            if U <= base_id + 1 <= u:
                start_idx = i
                break

        if start_idx is None:
            return False

        for msg in buffered[start_idx:]:
            result = msg.get("result", {}) or {}
            U = safe_int(result.get("U", 0))
            u = safe_int(result.get("u", 0))
            if u < self.id + 1:
                continue
            if U > self.id + 1:
                return False
            if not self.apply_update(msg):
                return False

        bid = self.best_bid()
        ask = self.best_ask()
        self.ready = bid > 0 and ask > 0 and ask >= bid
        return self.ready


# =============================================================================
# PUBLIC MARKET DATA
# =============================================================================


class PublicMarketData:
    def __init__(self, ws_url: str, rest: GateRestClient) -> None:
        self.ws_url = ws_url
        self.rest = rest
        self.ws = None
        self.stop_event = asyncio.Event()
        self.connected = asyncio.Event()
        self.symbols: List[str] = []
        self.books: Dict[str, LocalBook] = {}

    def set_symbols(self, symbols: Iterable[str]) -> None:
        new_symbols = list(symbols)
        changed = set(new_symbols) != set(self.symbols)
        self.symbols = new_symbols

        for s in self.symbols:
            if s not in self.books:
                self.books[s] = LocalBook(s)

        for s in list(self.books.keys()):
            if s not in self.symbols:
                self.books.pop(s, None)

        if changed:
            event_log("public_symbols_set", count=len(self.symbols), symbols=self.symbols)

    async def connect_loop(self) -> None:
        while not self.stop_event.is_set():
            if not self.symbols:
                await asyncio.sleep(1.0)
                continue

            try:
                ssl_ctx = ssl.create_default_context()
                async with websockets.connect(
                    self.ws_url,
                    ssl=ssl_ctx,
                    ping_interval=None,
                    extra_headers={"X-Gate-Size-Decimal": "1"},
                    max_size=20 * 1024 * 1024,
                ) as ws:
                    self.ws = ws
                    self.connected.set()
                    event_log("public_ws_connected", url=self.ws_url, symbols=self.symbols)

                    await self.subscribe_books()
                    await self.bootstrap_snapshots()

                    ping_task = asyncio.create_task(self._ping_loop())
                    listen_task = asyncio.create_task(self._listen())

                    done, pending = await asyncio.wait(
                        [ping_task, listen_task],
                        return_when=asyncio.FIRST_COMPLETED,
                    )
                    for task in pending:
                        task.cancel()
                        with contextlib.suppress(Exception):
                            await task

            except asyncio.CancelledError:
                raise
            except Exception as exc:
                event_log("public_ws_error", error=str(exc), traceback=traceback.format_exc())
                await asyncio.sleep(jitter(PUBLIC_RECONNECT_SECONDS))
            finally:
                self.connected.clear()
                self.ws = None
                for book in self.books.values():
                    book.ready = False

    async def _ping_loop(self) -> None:
        while not self.stop_event.is_set():
            await asyncio.sleep(PING_SECONDS)
            if self.ws:
                await self.ws.ping()

    async def subscribe_books(self) -> None:
        if not self.ws:
            raise RuntimeError("public ws not connected")
        for symbol in self.symbols:
            msg = {
                "time": int(time.time()),
                "channel": "futures.order_book_update",
                "event": "subscribe",
                "payload": [symbol, WS_BOOK_PUSH, str(TOP_LEVELS)],
            }
            await self.ws.send(json.dumps(msg, separators=(",", ":"), ensure_ascii=False))
            event_log("public_subscribe_book", symbol=symbol, push=WS_BOOK_PUSH, levels=TOP_LEVELS)

    async def bootstrap_snapshots(self) -> None:
        loop = asyncio.get_running_loop()
        for symbol in self.symbols:
            book = self.books[symbol]
            snap = await loop.run_in_executor(None, self.rest.order_book_snapshot, symbol, TOP_LEVELS, True)
            if book.sync_from_snapshot_and_buffer(snap):
                event_log("book_bootstrap_ok", symbol=symbol, book_id=book.id)
            else:
                event_log("book_bootstrap_pending", symbol=symbol, snapshot_id=safe_int(snap.get("id", 0)))

    async def _listen(self) -> None:
        assert self.ws is not None
        async for raw in self.ws:
            try:
                msg = json.loads(raw)
                await self._handle_message(msg)
            except Exception as exc:
                event_log("public_ws_parse_error", error=str(exc), raw_preview=str(raw)[:800])

    async def _handle_message(self, msg: Dict[str, Any]) -> None:
        channel = str(msg.get("channel", ""))
        event = str(msg.get("event", ""))
        result = msg.get("result", {}) or {}

        if channel == "futures.order_book_update" and event == "update":
            symbol = str(result.get("s", result.get("contract", "")))
            book = self.books.get(symbol)
            if not book:
                return

            if not book.ready:
                book.buffer_update(msg)
                loop = asyncio.get_running_loop()
                snap = await loop.run_in_executor(None, self.rest.order_book_snapshot, symbol, TOP_LEVELS, True)
                if book.sync_from_snapshot_and_buffer(snap):
                    event_log("book_resync_ok", symbol=symbol, book_id=book.id)
                else:
                    event_log("book_resync_retry", symbol=symbol)
                return

            ok = book.apply_update(msg)
            if not ok:
                book.ready = False
                event_log("book_gap_detected", symbol=symbol, last_id=book.id)
                loop = asyncio.get_running_loop()
                snap = await loop.run_in_executor(None, self.rest.order_book_snapshot, symbol, TOP_LEVELS, True)
                if book.sync_from_snapshot_and_buffer(snap):
                    event_log("book_gap_resync_ok", symbol=symbol, book_id=book.id)
                else:
                    event_log("book_gap_resync_failed", symbol=symbol)

    def top(self, symbol: str) -> Tuple[Decimal, Decimal, Decimal, Decimal]:
        book = self.books.get(symbol)
        if not book or not book.ready:
            return Decimal("0"), Decimal("0"), Decimal("0"), Decimal("0")
        return (
            book.best_bid(),
            book.best_ask(),
            book.top_bid_size(),
            book.top_ask_size(),
        )

    async def stop(self) -> None:
        self.stop_event.set()
        if self.ws:
            with contextlib.suppress(Exception):
                await self.ws.close()


# =============================================================================
# INVENTORY
# =============================================================================


class InventoryModel:
    def __init__(self) -> None:
        self.by_symbol: Dict[str, HedgeInventory] = {}

    def set_positions_from_rest(self, rows: List[Dict[str, Any]], symbols: Optional[set[str]] = None) -> None:
        if symbols is not None:
            self.by_symbol = {sym: self.by_symbol.get(sym, HedgeInventory()) for sym in symbols}

        for p in rows:
            symbol = str(p.get("contract", ""))
            if symbols is not None and symbol not in symbols:
                continue

            qty = D(p.get("size", "0"))
            side_raw = str(p.get("side", "")).lower()
            entry = D(p.get("entry_price", "0"))

            inv = HedgeInventory()

            if side_raw in ("long", "buy"):
                inv.long_contracts = abs(qty)
                inv.long_entry_price = entry
            elif side_raw in ("short", "sell"):
                inv.short_contracts = abs(qty)
                inv.short_entry_price = entry
            else:
                if qty > 0:
                    inv.long_contracts = qty
                    inv.long_entry_price = entry
                elif qty < 0:
                    inv.short_contracts = abs(qty)
                    inv.short_entry_price = entry

            self.by_symbol[symbol] = inv

    def portfolio_exposure(self, metas: Dict[str, ContractMeta]) -> Tuple[Decimal, Decimal]:
        net_usd = Decimal("0")
        gross_usd = Decimal("0")
        for sym, inv in self.by_symbol.items():
            meta = metas.get(sym)
            if not meta:
                continue
            long_usd = inv.long_contracts * meta.nominal
            short_usd = inv.short_contracts * meta.nominal
            net_usd += long_usd - short_usd
            gross_usd += long_usd + short_usd
        return net_usd, gross_usd


# =============================================================================
# QUOTE / SPREAD CAPTURE ENGINE
# =============================================================================


class HedgeQuoteEngine:
    def __init__(self, metas: Dict[str, ContractMeta], inventory: InventoryModel) -> None:
        self.metas = metas
        self.inventory = inventory

    def contracts_for_notional(self, meta: ContractMeta, notional_usd: Decimal) -> Decimal:
        if meta.nominal <= 0 or notional_usd <= 0:
            return Decimal("0")

        raw_contracts = notional_usd / meta.nominal
        stepped = floor_to_step(raw_contracts, meta.order_size_min)
        if stepped <= 0:
            return Decimal("0")

        qty = max(meta.order_size_min, stepped)
        if meta.order_size_max > 0:
            qty = min(qty, meta.order_size_max)
        return qty

    def quote_sizes_for_symbol(
        self,
        meta: ContractMeta,
        inv: HedgeInventory,
        portfolio_net_usd: Decimal,
        portfolio_gross_usd: Decimal,
    ) -> Tuple[Decimal, Decimal]:
        symbol_long_usd = inv.long_contracts * meta.nominal
        symbol_short_usd = inv.short_contracts * meta.nominal
        symbol_net_usd = symbol_long_usd - symbol_short_usd
        symbol_gross_usd = symbol_long_usd + symbol_short_usd

        if portfolio_gross_usd >= MAX_PORTFOLIO_GROSS_USD and symbol_gross_usd >= MAX_SYMBOL_GROSS_USD:
            return Decimal("0"), Decimal("0")

        buy_notional = BASE_ORDER_NOTIONAL_USD
        sell_notional = BASE_ORDER_NOTIONAL_USD
        base = max(BASE_ORDER_NOTIONAL_USD, Decimal("0.00000001"))

        symbol_skew = clamp_dec(symbol_net_usd / base, Decimal("-3"), Decimal("3"))
        portfolio_skew = clamp_dec(portfolio_net_usd / base, Decimal("-3"), Decimal("3"))

        buy_notional *= clamp_dec(
            Decimal("1") - max(Decimal("0"), symbol_skew) * Decimal("0.50") * SKEW_FACTOR,
            Decimal("0"),
            Decimal("3"),
        )
        sell_notional *= clamp_dec(
            Decimal("1") + max(Decimal("0"), symbol_skew) * Decimal("0.50") * SKEW_FACTOR,
            Decimal("0"),
            Decimal("3"),
        )

        buy_notional *= clamp_dec(
            Decimal("1") - max(Decimal("0"), portfolio_skew) * Decimal("0.25") * SKEW_FACTOR,
            Decimal("0"),
            Decimal("3"),
        )
        sell_notional *= clamp_dec(
            Decimal("1") + max(Decimal("0"), portfolio_skew) * Decimal("0.25") * SKEW_FACTOR,
            Decimal("0"),
            Decimal("3"),
        )

        if symbol_net_usd >= MAX_SYMBOL_NET_USD:
            buy_notional = Decimal("0")
        if symbol_net_usd <= -MAX_SYMBOL_NET_USD:
            sell_notional = Decimal("0")

        if portfolio_net_usd >= MAX_PORTFOLIO_NET_USD:
            buy_notional = Decimal("0")
        if portfolio_net_usd <= -MAX_PORTFOLIO_NET_USD:
            sell_notional = Decimal("0")

        if symbol_gross_usd >= MAX_SYMBOL_GROSS_USD:
            if symbol_net_usd >= 0:
                buy_notional = Decimal("0")
            if symbol_net_usd <= 0:
                sell_notional = Decimal("0")

        return (
            self.contracts_for_notional(meta, buy_notional),
            self.contracts_for_notional(meta, sell_notional),
        )

    def select_entry_prices(self, bid: Decimal, ask: Decimal, meta: ContractMeta) -> Tuple[Decimal, Decimal]:
        bid_px = round_to_tick(bid, meta.order_price_round)
        ask_px = round_to_tick(ask, meta.order_price_round)

        if not JOIN_TOP_ONLY and ALLOW_STEP_INSIDE:
            inside_bid = round_to_tick(bid + meta.order_price_round, meta.order_price_round)
            inside_ask = round_to_tick(ask - meta.order_price_round, meta.order_price_round)
            if inside_bid < ask:
                bid_px = inside_bid
            if inside_ask > bid:
                ask_px = inside_ask

        return bid_px, ask_px

    def build_entry_intents(self, books: PublicMarketData) -> List[QuoteIntent]:
        portfolio_net_usd, portfolio_gross_usd = self.inventory.portfolio_exposure(self.metas)
        intents: List[QuoteIntent] = []

        for sym, meta in self.metas.items():
            bid, ask, _, _ = books.top(sym)
            if bid <= 0 or ask <= 0 or ask < bid:
                continue

            if spread_bps(bid, ask) < MIN_SPREAD_BPS:
                continue

            inv = self.inventory.by_symbol.get(sym, HedgeInventory())
            buy_qty, sell_qty = self.quote_sizes_for_symbol(meta, inv, portfolio_net_usd, portfolio_gross_usd)
            bid_px, ask_px = self.select_entry_prices(bid, ask, meta)

            # This is the part you asked for:
            # place buy at best bid and sell at best ask, both sides live when allowed.
            if buy_qty > 0:
                intents.append(QuoteIntent(symbol=sym, side="buy", price=bid_px, size=buy_qty, role="entry"))
            if sell_qty > 0:
                intents.append(QuoteIntent(symbol=sym, side="sell", price=ask_px, size=sell_qty, role="entry"))

        return intents

    def pnl_close_long(self, meta: ContractMeta, entry_price: Decimal, exit_price: Decimal, qty: Decimal, exit_is_taker: bool) -> Decimal:
        gross = (exit_price - entry_price) * qty * meta.quanto_multiplier
        fees = (entry_price * qty * meta.quanto_multiplier * ENTRY_MAKER_FEE_RATE)
        fees += (exit_price * qty * meta.quanto_multiplier * (EXIT_TAKER_FEE_RATE if exit_is_taker else EXIT_MAKER_FEE_RATE))
        return gross - fees

    def pnl_close_short(self, meta: ContractMeta, entry_price: Decimal, exit_price: Decimal, qty: Decimal, exit_is_taker: bool) -> Decimal:
        gross = (entry_price - exit_price) * qty * meta.quanto_multiplier
        fees = (entry_price * qty * meta.quanto_multiplier * ENTRY_MAKER_FEE_RATE)
        fees += (exit_price * qty * meta.quanto_multiplier * (EXIT_TAKER_FEE_RATE if exit_is_taker else EXIT_MAKER_FEE_RATE))
        return gross - fees

    def build_exit_intent(self, leg: ManagedLeg, books: PublicMarketData) -> Optional[QuoteIntent]:
        meta = self.metas.get(leg.symbol)
        if not meta:
            return None

        bid, ask, _, _ = books.top(leg.symbol)
        if bid <= 0 or ask <= 0 or ask < bid:
            return None

        # If entry was buy at best bid, prefer sell at best ask.
        if leg.entry_side == "buy":
            maker_exit_pnl = self.pnl_close_long(meta, leg.entry_price, ask, leg.qty, exit_is_taker=False)
            taker_exit_pnl = self.pnl_close_long(meta, leg.entry_price, bid, leg.qty, exit_is_taker=True)

            if maker_exit_pnl >= MIN_NET_PROFIT_USDT:
                return QuoteIntent(
                    symbol=leg.symbol,
                    side="sell",
                    price=round_to_tick(ask, meta.order_price_round),
                    size=leg.qty,
                    tif="poc",
                    reduce_only=True,
                    role="exit",
                )
            if ALLOW_TAKER_EXIT and taker_exit_pnl >= MIN_NET_PROFIT_USDT:
                return QuoteIntent(
                    symbol=leg.symbol,
                    side="sell",
                    price=round_to_tick(bid, meta.order_price_round),
                    size=leg.qty,
                    tif="ioc",
                    reduce_only=True,
                    role="exit",
                )
            if ALLOW_TIMEOUT_EXIT and leg.age() >= MAX_POSITION_HOLD_SECONDS:
                return QuoteIntent(
                    symbol=leg.symbol,
                    side="sell",
                    price=round_to_tick(bid, meta.order_price_round),
                    size=leg.qty,
                    tif="ioc",
                    reduce_only=True,
                    role="exit",
                )
            return None

        # If entry was sell at best ask, prefer buy back at best bid.
        maker_exit_pnl = self.pnl_close_short(meta, leg.entry_price, bid, leg.qty, exit_is_taker=False)
        taker_exit_pnl = self.pnl_close_short(meta, leg.entry_price, ask, leg.qty, exit_is_taker=True)

        if maker_exit_pnl >= MIN_NET_PROFIT_USDT:
            return QuoteIntent(
                symbol=leg.symbol,
                side="buy",
                price=round_to_tick(bid, meta.order_price_round),
                size=leg.qty,
                tif="poc",
                reduce_only=True,
                role="exit",
            )
        if ALLOW_TAKER_EXIT and taker_exit_pnl >= MIN_NET_PROFIT_USDT:
            return QuoteIntent(
                symbol=leg.symbol,
                side="buy",
                price=round_to_tick(ask, meta.order_price_round),
                size=leg.qty,
                tif="ioc",
                reduce_only=True,
                role="exit",
            )
        if ALLOW_TIMEOUT_EXIT and leg.age() >= MAX_POSITION_HOLD_SECONDS:
            return QuoteIntent(
                symbol=leg.symbol,
                side="buy",
                price=round_to_tick(ask, meta.order_price_round),
                size=leg.qty,
                tif="ioc",
                reduce_only=True,
                role="exit",
            )
        return None


# =============================================================================
# ORDER MANAGER
# =============================================================================


class OrderManager:
    def __init__(self, rest: GateRestClient, contracts: Dict[str, ContractMeta]) -> None:
        self.rest = rest
        self.contracts = contracts
        self.open_by_slot: Dict[Tuple[str, str, str], LiveOrder] = {}
        self._op_lock = asyncio.Lock()

    async def sync_from_exchange(self, symbols: List[str]) -> None:
        loop = asyncio.get_running_loop()
        self.open_by_slot.clear()

        if DRY_RUN:
            return

        rows = await loop.run_in_executor(None, self.rest.open_orders)
        for row in rows:
            symbol = str(row.get("contract", ""))
            if symbols and symbol not in symbols:
                continue

            size_signed = D(row.get("size", "0"))
            side = "buy" if size_signed > 0 else "sell"
            oid = str(row.get("id", ""))
            text = str(row.get("text", ""))
            role = "exit" if "exit" in text else "entry"
            lo = LiveOrder(
                order_id=oid,
                symbol=symbol,
                side=side,
                price=D(row.get("price", "0")),
                size=abs(size_signed),
                text=text,
                created_ts=order_create_time(row),
                status=str(row.get("status", "open")),
                role=role,
            )
            self.open_by_slot[(symbol, side, role)] = lo

        event_log("order_sync_ok", count=len(self.open_by_slot))

    async def cancel(self, order: LiveOrder, reason: str) -> None:
        if DRY_RUN:
            event_log("dry_cancel", order_id=order.order_id, symbol=order.symbol, side=order.side, role=order.role, reason=reason)
            self.open_by_slot.pop((order.symbol, order.side, order.role), None)
            return

        loop = asyncio.get_running_loop()
        try:
            resp = await loop.run_in_executor(None, self.rest.cancel_order, order.order_id)
            event_log(
                "cancel_sent",
                order_id=order.order_id,
                symbol=order.symbol,
                side=order.side,
                role=order.role,
                reason=reason,
                resp=resp,
            )
            self.open_by_slot.pop((order.symbol, order.side, order.role), None)
        except Exception as exc:
            event_log(
                "cancel_error",
                order_id=order.order_id,
                symbol=order.symbol,
                side=order.side,
                role=order.role,
                reason=reason,
                error=str(exc),
            )

    async def cancel_if_needed(self, order: LiveOrder, desired: QuoteIntent) -> bool:
        ttl = EXIT_ORDER_TTL_SECONDS if order.role == "exit" else ENTRY_ORDER_TTL_SECONDS

        if order.age() >= ttl:
            await self.cancel(order, reason="ttl")
            return True

        if REPRICE_MIN_BPS > 0 and bps_diff(order.price, desired.price) >= REPRICE_MIN_BPS:
            await self.cancel(order, reason="reprice_bps")
            return True

        if order.price != desired.price:
            await self.cancel(order, reason="touch_follow")
            return True

        return False

    async def place(self, intent: QuoteIntent) -> None:
        if intent.size <= 0 or intent.price <= 0:
            return

        meta = self.contracts[intent.symbol]
        price = round_to_tick(intent.price, meta.order_price_round)
        size = floor_to_step(intent.size, meta.order_size_min)
        if size < meta.order_size_min:
            return

        signed_size = size if intent.side == "buy" else -size
        text = make_text_tag(intent.symbol, intent.side, intent.role, str(now_ms()), decimal_to_wire(price), decimal_to_wire(size))
        req = {
            "contract": intent.symbol,
            "size": decimal_to_wire(signed_size),
            "price": decimal_to_wire(price),
            "tif": intent.tif,
            "text": text,
            "reduce_only": bool(intent.reduce_only),
        }

        if DRY_RUN:
            event_log("dry_place", req=req)
            self.open_by_slot[(intent.symbol, intent.side, intent.role)] = LiveOrder(
                order_id=f"dry-{text}",
                symbol=intent.symbol,
                side=intent.side,
                price=price,
                size=size,
                text=text,
                created_ts=now_ts(),
                status="open",
                role=intent.role,
            )
            return

        loop = asyncio.get_running_loop()
        try:
            resp = await loop.run_in_executor(None, self.rest.create_order, req)
            oid = str(resp.get("id", ""))
            event_log("place_sent", req=req, resp=resp)
            if oid:
                self.open_by_slot[(intent.symbol, intent.side, intent.role)] = LiveOrder(
                    order_id=oid,
                    symbol=intent.symbol,
                    side=intent.side,
                    price=price,
                    size=size,
                    text=text,
                    created_ts=now_ts(),
                    status=str(resp.get("status", "open")),
                    role=intent.role,
                )
        except Exception as exc:
            event_log("place_error", req=req, error=str(exc))

    async def reconcile(self, intents: List[QuoteIntent]) -> None:
        async with self._op_lock:
            desired_by_slot: Dict[Tuple[str, str, str], QuoteIntent] = {i.key(): i for i in intents}

            for slot, live in list(self.open_by_slot.items()):
                desired = desired_by_slot.get(slot)
                if not desired:
                    await self.cancel(live, reason="no_longer_desired")
                    continue
                canceled = await self.cancel_if_needed(live, desired)
                if canceled:
                    continue

            for slot, desired in desired_by_slot.items():
                if slot in self.open_by_slot:
                    continue
                await self.place(desired)

    async def cancel_all(self) -> None:
        for _, order in list(self.open_by_slot.items()):
            await self.cancel(order, reason="cancel_all")
        self.open_by_slot.clear()

    async def flatten_all(self, rest: GateRestClient) -> None:
        loop = asyncio.get_running_loop()
        rows = await loop.run_in_executor(None, rest.positions)

        for p in rows:
            symbol = str(p.get("contract", ""))
            qty = D(p.get("size", "0"))
            mode_raw = str(p.get("mode", "single")).lower()

            payload: Optional[Dict[str, Any]] = None

            if mode_raw in ("dual_long", "long"):
                payload = {
                    "contract": symbol,
                    "size": "0",
                    "price": "0",
                    "tif": "ioc",
                    "auto_size": "close_long",
                    "reduce_only": True,
                    "text": make_text_tag(symbol, "flatten", "close_long"),
                }
            elif mode_raw in ("dual_short", "short"):
                payload = {
                    "contract": symbol,
                    "size": "0",
                    "price": "0",
                    "tif": "ioc",
                    "auto_size": "close_short",
                    "reduce_only": True,
                    "text": make_text_tag(symbol, "flatten", "close_short"),
                }
            elif qty > 0:
                payload = {
                    "contract": symbol,
                    "size": decimal_to_wire(-abs(qty)),
                    "price": "0",
                    "tif": "ioc",
                    "reduce_only": True,
                    "text": make_text_tag(symbol, "flatten", "sell"),
                }
            elif qty < 0:
                payload = {
                    "contract": symbol,
                    "size": decimal_to_wire(abs(qty)),
                    "price": "0",
                    "tif": "ioc",
                    "reduce_only": True,
                    "text": make_text_tag(symbol, "flatten", "buy"),
                }

            if not payload:
                continue

            if DRY_RUN:
                event_log("dry_flatten", payload=payload)
            else:
                try:
                    resp = await loop.run_in_executor(None, rest.create_order, payload)
                    event_log("flatten_sent", payload=payload, resp=resp)
                except Exception as exc:
                    event_log("flatten_error", payload=payload, error=str(exc))


# =============================================================================
# MAIN BOT
# =============================================================================


class GateMultiPairMM:
    def __init__(self, rest: GateRestClient, store: StateStore, state: PersistedState) -> None:
        self.rest = rest
        self.store = store
        self.state = state

        self.contracts: Dict[str, ContractMeta] = {}
        self.inventory = InventoryModel()
        self.public = PublicMarketData(WS_URL, rest)
        self.quote_engine = HedgeQuoteEngine(self.contracts, self.inventory)
        self.orders = OrderManager(rest, self.contracts)

        self.stop_event = asyncio.Event()
        self.tasks: List[asyncio.Task] = []
        self.main_errors = 0
        self.position_seen_at: Dict[Tuple[str, str], float] = {}

    async def refresh_universe(self, force: bool = False) -> None:
        now = now_ts()
        if not force and now - self.state.last_universe_refresh < UNIVERSE_REFRESH_SECONDS:
            return

        loop = asyncio.get_running_loop()
        rows = await loop.run_in_executor(None, self.rest.list_contracts)

        metas: List[ContractMeta] = []
        for c in rows:
            try:
                symbol = str(c.get("name", "")).upper()
                if not symbol:
                    continue

                if INCLUDE_SYMBOLS and symbol not in INCLUDE_SYMBOLS:
                    continue
                if symbol in EXCLUDE_SYMBOLS:
                    continue
                if c.get("in_delisting") or str(c.get("status", "trading")) != "trading":
                    continue

                meta = ContractMeta(
                    symbol=symbol,
                    last_price=D(c.get("last_price", "0")),
                    quanto_multiplier=D(c.get("quanto_multiplier", "0")),
                    order_size_min=max(D(c.get("order_size_min", "1")), Decimal("0.00000001")),
                    order_size_max=D(c.get("order_size_max", "0")),
                    order_price_round=max(D(c.get("order_price_round", "0.0001")), Decimal("0.00000001")),
                    leverage_min=max(1, safe_int(c.get("leverage_min", 1))),
                    leverage_max=max(1, safe_int(c.get("leverage_max", 100))),
                    volume_24h_quote=D(c.get("volume_24h_quote", "0")),
                )

                if meta.last_price <= 0 or meta.quanto_multiplier <= 0:
                    continue
                if meta.nominal <= 0 or meta.nominal > MAX_CONTRACT_NOMINAL_USD:
                    continue
                if meta.volume_24h_quote < MIN_VOLUME_USDT:
                    continue

                metas.append(meta)
            except Exception:
                continue

        metas.sort(key=lambda m: m.volume_24h_quote, reverse=True)
        selected = metas[:MAX_SYMBOLS]

        self.contracts = {m.symbol: m for m in selected}
        self.quote_engine.metas = self.contracts
        self.orders.contracts = self.contracts
        self.public.set_symbols(self.contracts.keys())

        self.state.last_universe_refresh = now
        self.state.metadata["universe_count"] = len(self.contracts)
        self.state.metadata["symbols"] = list(self.contracts.keys())
        await self.store.save(self.state)

        event_log(
            "universe_refresh",
            count=len(self.contracts),
            symbols=list(self.contracts.keys()),
            max_nominal=decimal_to_wire(MAX_CONTRACT_NOMINAL_USD),
            min_volume=decimal_to_wire(MIN_VOLUME_USDT),
        )

    async def ensure_exchange_settings(self) -> None:
        if DRY_RUN:
            return

        loop = asyncio.get_running_loop()

        try:
            await loop.run_in_executor(None, self.rest.set_dual_mode, True)
            event_log("dual_mode_set", enabled=True)
        except Exception as exc:
            event_log("dual_mode_error", error=str(exc))

        for meta in self.contracts.values():
            lev = int(max(meta.leverage_min, min(meta.leverage_max, LEVERAGE)))
            try:
                await loop.run_in_executor(None, self.rest.set_leverage, meta.symbol, lev)
                event_log("leverage_set", symbol=meta.symbol, leverage=lev)
            except Exception as exc:
                event_log("leverage_error", symbol=meta.symbol, leverage=lev, error=str(exc))

    async def hydrate_positions(self) -> List[Dict[str, Any]]:
        loop = asyncio.get_running_loop()
        rows = await loop.run_in_executor(None, self.rest.positions)
        self.inventory.set_positions_from_rest(rows, symbols=set(self.contracts.keys()))
        event_log("positions_hydrated", count=len(rows))
        return rows

    async def hydrate_open_orders(self) -> None:
        await self.orders.sync_from_exchange(list(self.contracts.keys()))

    def all_books_ready(self) -> bool:
        if not self.contracts:
            return False
        return all(self.public.books.get(sym) and self.public.books[sym].ready for sym in self.contracts)

    async def show_balance(self) -> Dict[str, Any]:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self.rest.account)

    async def show_positions(self) -> List[Dict[str, Any]]:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self.rest.positions)

    async def cancel_all(self) -> None:
        await self.orders.cancel_all()

    async def flatten_all(self) -> None:
        await self.orders.flatten_all(self.rest)

    def detect_managed_legs(self, position_rows: List[Dict[str, Any]]) -> List[ManagedLeg]:
        legs: List[ManagedLeg] = []
        live_keys: set[Tuple[str, str]] = set()

        for p in position_rows:
            symbol = str(p.get("contract", ""))
            if symbol not in self.contracts:
                continue
            qty = D(p.get("size", "0"))
            if qty == 0:
                continue
            side_raw = str(p.get("side", "")).lower()
            entry_side = "buy" if side_raw in ("long", "buy") or qty > 0 else "sell"
            key = (symbol, entry_side)
            live_keys.add(key)
            if key not in self.position_seen_at:
                self.position_seen_at[key] = now_ts()
            legs.append(
                ManagedLeg(
                    symbol=symbol,
                    entry_side=entry_side,
                    qty=abs(qty),
                    entry_price=D(p.get("entry_price", "0")),
                    opened_ts=self.position_seen_at[key],
                )
            )

        for key in list(self.position_seen_at.keys()):
            if key not in live_keys:
                self.position_seen_at.pop(key, None)

        return legs

    async def build_and_reconcile_all_intents(self) -> None:
        entry_intents = self.quote_engine.build_entry_intents(self.public)
        position_rows = await self.hydrate_positions()
        exit_intents: List[QuoteIntent] = []

        for leg in self.detect_managed_legs(position_rows):
            exit_intent = self.quote_engine.build_exit_intent(leg, self.public)
            if exit_intent:
                exit_intents.append(exit_intent)
                event_log(
                    "exit_intent",
                    symbol=leg.symbol,
                    entry_side=leg.entry_side,
                    entry_price=decimal_to_wire(leg.entry_price),
                    exit_side=exit_intent.side,
                    exit_price=decimal_to_wire(exit_intent.price),
                    size=decimal_to_wire(exit_intent.size),
                    tif=exit_intent.tif,
                )

        await self.orders.reconcile(entry_intents + exit_intents)

    async def quote_loop(self) -> None:
        while not self.stop_event.is_set():
            cycle_start = now_ts()
            self.state.cycle += 1

            try:
                await self.refresh_universe()

                if not self.all_books_ready():
                    ready = sum(1 for b in self.public.books.values() if b.ready)
                    event_log("quote_wait_books", ready=ready, total=len(self.contracts))
                    await asyncio.sleep(0.5)
                    continue

                if not DRY_RUN:
                    try:
                        loop = asyncio.get_running_loop()
                        await loop.run_in_executor(None, self.rest.countdown_cancel_all, COUNTDOWN_CANCEL_TIMEOUT)
                    except Exception as exc:
                        event_log("countdown_cancel_error", error=str(exc))

                await self.build_and_reconcile_all_intents()
                await self.store.save(self.state)

                net_usd, gross_usd = self.inventory.portfolio_exposure(self.contracts)
                live_intents = len(self.orders.open_by_slot)
                log.info(
                    "cycle=%d symbols=%d live_orders=%d net=%+s gross=%s",
                    self.state.cycle,
                    len(self.contracts),
                    live_intents,
                    decimal_to_wire(net_usd),
                    decimal_to_wire(gross_usd),
                )
                event_log(
                    "quote_cycle",
                    cycle=self.state.cycle,
                    symbols=len(self.contracts),
                    live_orders=live_intents,
                    portfolio_net_usd=decimal_to_wire(net_usd),
                    portfolio_gross_usd=decimal_to_wire(gross_usd),
                )

                self.main_errors = 0

            except asyncio.CancelledError:
                raise
            except Exception as exc:
                self.main_errors += 1
                event_log(
                    "quote_loop_error",
                    error=str(exc),
                    traceback=traceback.format_exc(),
                    consecutive_errors=self.main_errors,
                )
                log.error("quote loop error: %s", exc)
                if self.main_errors >= MAX_CONSECUTIVE_MAIN_ERRORS:
                    event_log("panic_stop", consecutive_errors=self.main_errors)
                    self.stop_event.set()
                    break

            elapsed = now_ts() - cycle_start
            await asyncio.sleep(max(0.05, QUOTE_INTERVAL_SECONDS - elapsed))

    async def maintenance_loop(self) -> None:
        while not self.stop_event.is_set():
            try:
                await self.refresh_universe()
                await asyncio.sleep(UNIVERSE_REFRESH_SECONDS)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                event_log("maintenance_error", error=str(exc))
                await asyncio.sleep(2.0)

    async def run(self) -> None:
        await self.refresh_universe(force=True)
        await self.ensure_exchange_settings()
        await self.hydrate_positions()
        await self.hydrate_open_orders()

        event_log(
            "startup",
            mode="DRY" if DRY_RUN else "LIVE",
            settle=SETTLE,
            rest_base_url=REST_BASE_URL,
            ws_url=WS_URL,
            universe=list(self.contracts.keys()),
        )
        log.info(
            "Starting %s %s mode=%s settle=%s ws=%s symbols=%d",
            APP_NAME,
            VERSION,
            "DRY" if DRY_RUN else "LIVE",
            SETTLE,
            WS_URL,
            len(self.contracts),
        )

        self.tasks = [
            asyncio.create_task(self.public.connect_loop(), name="public_ws"),
            asyncio.create_task(self.quote_loop(), name="quote_loop"),
            asyncio.create_task(self.maintenance_loop(), name="maintenance_loop"),
        ]

        await self.stop_event.wait()

        event_log("shutdown_begin")
        for task in self.tasks:
            task.cancel()
        for task in self.tasks:
            with contextlib.suppress(Exception):
                await task

        with contextlib.suppress(Exception):
            await self.orders.cancel_all()
        with contextlib.suppress(Exception):
            await self.public.stop()

        event_log("shutdown_complete")

    def request_stop(self) -> None:
        self.stop_event.set()


# =============================================================================
# CLI
# =============================================================================


async def amain() -> None:
    global DRY_RUN

    parser = argparse.ArgumentParser(description="Gate.io multi-pair futures market maker + spread capture")
    parser.add_argument("--dry", action="store_true", help="Dry mode")
    parser.add_argument("--live", action="store_true", help="Live mode")
    parser.add_argument("--balance", action="store_true", help="Show account balance")
    parser.add_argument("--positions", action="store_true", help="Show positions")
    parser.add_argument("--cancel-all", action="store_true", help="Cancel all open orders")
    parser.add_argument("--flatten-all", action="store_true", help="Flatten all positions")
    args = parser.parse_args()

    DRY_RUN = not args.live

    if not DRY_RUN and (not GATE_API_KEY or not GATE_API_SECRET):
        sys.stderr.write("Missing GATE_API_KEY / GATE_API_SECRET\n")
        sys.exit(1)

    rest = GateRestClient(
        key=GATE_API_KEY,
        secret=GATE_API_SECRET,
        base_url=REST_BASE_URL,
        settle=SETTLE,
    )
    store = StateStore(STATE_FILE)
    state = store.load()
    bot = GateMultiPairMM(rest, store, state)

    if args.balance:
        print(json.dumps(await bot.show_balance(), indent=2, ensure_ascii=False))
        return

    if args.positions:
        print(json.dumps(await bot.show_positions(), indent=2, ensure_ascii=False))
        return

    if args.cancel_all:
        await bot.refresh_universe(force=True)
        await bot.hydrate_open_orders()
        await bot.cancel_all()
        return

    if args.flatten_all:
        await bot.flatten_all()
        return

    loop = asyncio.get_running_loop()
    stop_once = False

    def _stop_handler() -> None:
        nonlocal stop_once
        if stop_once:
            return
        stop_once = True
        bot.request_stop()

    for sig_name in ("SIGINT", "SIGTERM"):
        sig = getattr(signal, sig_name, None)
        if sig is not None:
            with contextlib.suppress(NotImplementedError):
                loop.add_signal_handler(sig, _stop_handler)

    try:
        await bot.run()
    except KeyboardInterrupt:
        bot.request_stop()


def main() -> None:
    try:
        asyncio.run(amain())
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
