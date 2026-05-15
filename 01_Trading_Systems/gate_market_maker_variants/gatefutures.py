from __future__ import annotations

"""
Gate.io Micro Futures Trader — one-file advanced rewrite
========================================================

What this is
------------
A single-file, research-heavy, live-capable futures bot framework for Gate.io
with:
- dry/live modes
- startup state persistence
- startup exchange reconciliation hooks
- contract metadata validation
- idempotent order tags
- safer close plumbing (reduce-only / close-position support where possible)
- cooldowns
- structured JSONL logging
- CSV trade journal
- Telegram alerts
- walk-forward backtesting
- parameter sweeps
- Monte Carlo robustness simulation
- stress testing for DCA ladders
- unit tests

What this is not
----------------
- Not a promise of profitability
- Not institutional infrastructure
- Not legal / tax / compliance advice
- Not a substitute for verifying exact exchange semantics in your environment

Install
-------
    pip install gate-api requests

Run dry
-------
    python gate_micro_advanced.py --dry

Run live
--------
    python gate_micro_advanced.py --live

Backtest
--------
    python gate_micro_advanced.py --backtest BTC_USDT

Sweep
-----
    python gate_micro_advanced.py --sweep BTC_USDT

Monte Carlo from backtest
-------------------------
    python gate_micro_advanced.py --mc BTC_USDT

Tests
-----
    python gate_micro_advanced.py --test
"""

import argparse
import csv
import hashlib
import json
import logging
import math
import os
import random
import statistics
import sys
import threading
import time
import traceback
import unittest
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum, auto
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence, Tuple

try:
    import requests
except ImportError:  # pragma: no cover
    requests = None  # type: ignore[assignment]

try:
    import gate_api
    from gate_api import ApiClient, Configuration, FuturesApi
    GATE_AVAILABLE = True
except ImportError:  # pragma: no cover
    gate_api = None  # type: ignore[assignment]
    ApiClient = Configuration = FuturesApi = object  # type: ignore[misc,assignment]
    GATE_AVAILABLE = False


# =============================================================================
# GLOBAL CONFIG
# =============================================================================

APP_NAME = "gate-micro-advanced"
VERSION = "2.0-single-file"
GATE_API_KEY = os.getenv("GATE_API_KEY", "")
GATE_API_SECRET = os.getenv("GATE_API_SECRET", "")


TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "")
TELEGRAM_CHAT = os.environ.get("TELEGRAM_CHAT", "")

SETTLE = os.environ.get("GATE_SETTLE", "usdt")
DEFAULT_SYMBOL = os.environ.get("GATE_SYMBOL", "BTC_USDT")

# Account and risk
ACCOUNT_BALANCE = float(os.environ.get("ACCOUNT_BALANCE", "10.0"))
LEVERAGE = int(os.environ.get("LEVERAGE", "5"))
MAX_DAILY_LOSS_PCT = float(os.environ.get("MAX_DAILY_LOSS_PCT", "0.10"))
MAX_ACCOUNT_RISK_PCT = float(os.environ.get("MAX_ACCOUNT_RISK_PCT", "0.20"))
MAX_OPEN_POSITIONS = int(os.environ.get("MAX_OPEN_POSITIONS", "5"))
MAX_PER_REGIME = int(os.environ.get("MAX_PER_REGIME", "3"))
COOLDOWN_SECONDS = int(os.environ.get("COOLDOWN_SECONDS", "1800"))

# Universe scanning
MIN_NOTIONAL = float(os.environ.get("MIN_NOTIONAL", "0.01"))
MAX_NOTIONAL = float(os.environ.get("MAX_NOTIONAL", "0.25"))
MIN_VOLUME_USDT = float(os.environ.get("MIN_VOLUME_USDT", "250000"))
SCAN_WORKERS = int(os.environ.get("SCAN_WORKERS", "10"))
LOOKBACK_HOURS = int(os.environ.get("LOOKBACK_HOURS", "1"))
POLL_INTERVAL = int(os.environ.get("POLL_INTERVAL", "30"))
REGIME_TTL = int(os.environ.get("REGIME_TTL", "180"))

# Strategy thresholds
PUMP_THRESHOLD = float(os.environ.get("PUMP_THRESHOLD", "0.08"))
DUMP_THRESHOLD = float(os.environ.get("DUMP_THRESHOLD", "-0.08"))
ADX_TREND_MIN = float(os.environ.get("ADX_TREND_MIN", "23.0"))
ATR_VOLATILE_MULT = float(os.environ.get("ATR_VOLATILE_MULT", "1.8"))
RSI_OVERBOUGHT = float(os.environ.get("RSI_OVERBOUGHT", "70.0"))
RSI_OVERSOLD = float(os.environ.get("RSI_OVERSOLD", "30.0"))
BB_SQUEEZE_RATIO = float(os.environ.get("BB_SQUEEZE_RATIO", "0.015"))
VWAP_BARS = int(os.environ.get("VWAP_BARS", "48"))

# Exits and sizing
STOP_LOSS_PCT = float(os.environ.get("STOP_LOSS_PCT", "0.045"))
TRAIL_PCT = float(os.environ.get("TRAIL_PCT", "0.015"))
TRAIL_ACTIVATE = float(os.environ.get("TRAIL_ACTIVATE", "0.018"))
TAKE_PROFIT_PCT = float(os.environ.get("TAKE_PROFIT_PCT", "0.010"))
PARTIALS = [(0.025, 0.35), (0.050, 0.35), (0.080, 1.00)]

# DCA (hard capped)
ENABLE_DCA = os.environ.get("ENABLE_DCA", "1") == "1"
DCA_STEP_PCT = float(os.environ.get("DCA_STEP_PCT", "0.10"))
MAX_DCA_ADDS = int(os.environ.get("MAX_DCA_ADDS", "2"))
DCA_SCALE = float(os.environ.get("DCA_SCALE", "1.10"))
BASE_ORDER_NOTIONAL_USD = float(os.environ.get("BASE_ORDER_NOTIONAL_USD", "0.10"))

# Backtesting
BACKTEST_INTERVAL = os.environ.get("BACKTEST_INTERVAL", "5m")
BACKTEST_LIMIT = int(os.environ.get("BACKTEST_LIMIT", "1200"))
WALK_TRAIN = int(os.environ.get("WALK_TRAIN", "250"))
WALK_TEST = int(os.environ.get("WALK_TEST", "100"))
MC_RUNS = int(os.environ.get("MC_RUNS", "500"))

# Execution assumptions
TAKER_FEE_RATE = float(os.environ.get("TAKER_FEE_RATE", "0.0005"))
MAKER_FEE_RATE = float(os.environ.get("MAKER_FEE_RATE", "0.0002"))
SLIPPAGE_PCT = float(os.environ.get("SLIPPAGE_PCT", "0.0007"))
MAINT_MARGIN_RATE = float(os.environ.get("MAINT_MARGIN_RATE", "0.01"))

# Retry and heartbeat
API_MAX_RETRIES = int(os.environ.get("API_MAX_RETRIES", "4"))
API_RETRY_DELAY = float(os.environ.get("API_RETRY_DELAY", "1.0"))
COUNTDOWN_KILL_SWITCH_SECONDS = int(os.environ.get("COUNTDOWN_KILL_SWITCH_SECONDS", "15"))

# Files
STATE_FILE = Path(os.environ.get("STATE_FILE", "bot_state.json"))
JSONL_LOG = Path(os.environ.get("JSONL_LOG", "events.jsonl"))
TRADE_LOG_CSV = Path(os.environ.get("TRADE_LOG_CSV", "trades.csv"))

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
_jsonl_lock = threading.Lock()
_csv_lock = threading.Lock()


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def ts() -> str:
    return now_utc().isoformat()


def event_log(kind: str, **payload: Any) -> None:
    record = {
        "ts": ts(),
        "kind": kind,
        "app": APP_NAME,
        "version": VERSION,
        **payload,
    }
    line = json.dumps(record, separators=(",", ":"), sort_keys=False)
    with _jsonl_lock:
        with open(JSONL_LOG, "a", encoding="utf-8") as handle:
            handle.write(line + "\n")


def tg(message: str) -> None:
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT or requests is None:
        return
    try:
        requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
            json={"chat_id": TELEGRAM_CHAT, "text": message, "parse_mode": "HTML"},
            timeout=5,
        )
    except Exception:
        pass


def write_trade_csv(row: Dict[str, Any]) -> None:
    with _csv_lock:
        new_file = not TRADE_LOG_CSV.exists()
        with open(TRADE_LOG_CSV, "a", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(row.keys()))
            if new_file:
                writer.writeheader()
            writer.writerow(row)


# =============================================================================
# DATA STRUCTURES
# =============================================================================

class Regime(Enum):
    TREND_UP = auto()
    TREND_DOWN = auto()
    RANGING = auto()
    VOLATILE = auto()


@dataclass
class RegimeSnapshot:
    regime: Regime
    adx: float
    rsi: float
    atr_ratio: float
    bb_width: float
    ema_fast: float = 0.0
    ema_slow: float = 0.0
    computed_at: str = field(default_factory=ts)

    def is_stale(self) -> bool:
        dt = datetime.fromisoformat(self.computed_at)
        return (now_utc() - dt).total_seconds() > REGIME_TTL

    def label(self) -> str:
        return self.regime.name


@dataclass
class ContractMeta:
    symbol: str
    last_price: float
    quanto_multiplier: float
    volume_24h_quote: float
    min_order_size: int
    leverage_min: int
    leverage_max: int
    maintenance_rate: float = MAINT_MARGIN_RATE

    @property
    def approx_contract_notional(self) -> float:
        return self.last_price * self.quanto_multiplier


@dataclass
class FillRecord:
    ts: str
    side: str
    size: int
    price: float
    label: str
    fee: float
    reduce_only: bool = False


@dataclass
class PositionRecord:
    symbol: str
    side: str
    regime: str
    entry_price: float
    avg_entry: float
    size: int
    remaining: int
    contract_multiplier: float
    leverage: int
    opened_at: str = field(default_factory=ts)
    closed: bool = False
    ladder_idx: int = 0
    dca_adds_used: int = 0
    next_dca_trigger: Optional[float] = None
    realised_pnl: float = 0.0
    unrealised_pnl: float = 0.0
    peak_pnl_pct: float = 0.0
    last_price: float = 0.0
    entry_tag: str = ""
    fills: List[FillRecord] = field(default_factory=list)
    notes: Dict[str, Any] = field(default_factory=dict)

    def is_open(self) -> bool:
        return (not self.closed) and self.remaining > 0


@dataclass
class OrderIntent:
    symbol: str
    size: int
    side: str
    label: str
    reduce_only: bool = False
    close_position: bool = False


@dataclass
class BacktestTrade:
    symbol: str
    side: str
    regime: str
    entry_idx: int
    exit_idx: int
    entry_price: float
    exit_price: float
    pnl_pct: float
    pnl_usd: float
    fees_usd: float
    reason: str
    dca_adds: int


@dataclass
class BacktestSummary:
    symbol: str
    trades: List[BacktestTrade]
    final_equity: float
    return_pct: float
    max_drawdown_pct: float
    win_rate_pct: float
    avg_trade_pct: float
    profit_factor: float
    sharpe_like: float
    liquidation_events: int
    params: Dict[str, Any]


# =============================================================================
# STATE STORE
# =============================================================================

class StateStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.lock = threading.Lock()

    def load(self) -> Dict[str, Any]:
        if not self.path.exists():
            return {
                "positions": {},
                "cooldowns": {},
                "seen_order_tags": [],
                "daily_realised": {},
                "last_reconcile_at": None,
                "metadata": {},
            }
        try:
            with open(self.path, "r", encoding="utf-8") as handle:
                data = json.load(handle)
            if not isinstance(data, dict):
                raise ValueError("state root must be dict")
            return data
        except Exception as exc:
            log.warning("State load failed: %s", exc)
            return {
                "positions": {},
                "cooldowns": {},
                "seen_order_tags": [],
                "daily_realised": {},
                "last_reconcile_at": None,
                "metadata": {"load_error": str(exc)},
            }

    def save(self, state: Dict[str, Any]) -> None:
        temp = self.path.with_suffix(".tmp")
        with self.lock:
            with open(temp, "w", encoding="utf-8") as handle:
                json.dump(state, handle, indent=2, sort_keys=True)
            temp.replace(self.path)


# =============================================================================
# RETRY
# =============================================================================

def with_retry(
    fn: Callable[..., Any],
    *args: Any,
    retries: int = API_MAX_RETRIES,
    base_delay: float = API_RETRY_DELAY,
    **kwargs: Any,
) -> Any:
    delay = base_delay
    last_exc: Optional[Exception] = None
    for attempt in range(1, retries + 1):
        try:
            return fn(*args, **kwargs)
        except Exception as exc:
            last_exc = exc
            event_log("api_retry", fn=getattr(fn, "__name__", "call"), attempt=attempt, error=str(exc))
            if attempt >= retries:
                break
            time.sleep(delay)
            delay *= 2
    if last_exc:
        log.warning("Retry exhausted on %s: %s", getattr(fn, "__name__", "call"), last_exc)
    return None


# =============================================================================
# HELPERS
# =============================================================================

def safe_float(x: Any, default: float = 0.0) -> float:
    try:
        return float(x)
    except Exception:
        return default


def safe_int(x: Any, default: int = 0) -> int:
    try:
        return int(float(x))
    except Exception:
        return default


def clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


def make_order_tag(parts: Sequence[str]) -> str:
    seed = "|".join(parts)
    digest = hashlib.sha256(seed.encode("utf-8")).hexdigest()[:20]
    return f"mt-{digest}"[:28]


def dateroll_key(dt: Optional[datetime] = None) -> str:
    d = (dt or now_utc()).date()
    return d.isoformat()


# =============================================================================
# GATE CLIENT
# =============================================================================

class GateClient:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._client = self._build() if GATE_AVAILABLE else None

    def _build(self) -> Optional[FuturesApi]:
        if not GATE_AVAILABLE:
            return None
        cfg = Configuration(key=GATE_API_KEY, secret=GATE_API_SECRET)
        return FuturesApi(ApiClient(cfg))

    def reconnect(self) -> None:
        if not GATE_AVAILABLE:
            return
        with self._lock:
            self._client = self._build()
        event_log("reconnect")

    def alive(self) -> bool:
        return self._client is not None

    def list_contracts(self) -> List[Any]:
        if not self._client:
            return []
        def _call() -> List[Any]:
            return list(self._client.list_futures_tickers(SETTLE))
        return with_retry(_call) or []

    def fetch_contract_meta(self, symbol: str) -> Optional[ContractMeta]:
        contracts = self.list_contracts()
        for c in contracts:
            name = getattr(c, "contract", "")
            if name != symbol:
                continue
            return ContractMeta(
                symbol=name,
                last_price=safe_float(getattr(c, "last", 0.0)),
                quanto_multiplier=safe_float(getattr(c, "quanto_multiplier", 1.0), 1.0),
                volume_24h_quote=safe_float(getattr(c, "volume_24h_quote", 0.0)),
                min_order_size=max(1, safe_int(getattr(c, "order_size_min", 1), 1)),
                leverage_min=max(1, safe_int(getattr(c, "leverage_min", 1), 1)),
                leverage_max=max(1, safe_int(getattr(c, "leverage_max", 100), 100)),
                maintenance_rate=MAINT_MARGIN_RATE,
            )
        return None

    def fetch_candles(self, symbol: str, interval: str = "5m", limit: int = 100) -> List[Any]:
        if not self._client:
            return []
        def _call() -> List[Any]:
            return list(self._client.list_futures_candlesticks(SETTLE, symbol, interval=interval, limit=limit))
        return with_retry(_call) or []

    def get_price(self, symbol: str) -> Optional[float]:
        if not self._client:
            return None
        def _call() -> Optional[float]:
            data = self._client.list_futures_tickers(SETTLE, contract=symbol)
            if not data:
                return None
            return safe_float(getattr(data[0], "last", 0.0))
        px = with_retry(_call)
        if px is None:
            self.reconnect()
        return px

    def set_leverage(self, symbol: str, leverage: int) -> bool:
        if DRY_RUN or not self._client:
            return True
        def _call() -> Any:
            return self._client.update_position_leverage(
                SETTLE, symbol, str(leverage)
            )
        result = with_retry(_call)
        return result is not None

    def countdown_kill_switch(self, timeout_seconds: int, symbol: str = "") -> bool:
        if DRY_RUN or not self._client:
            event_log("kill_switch_dry", timeout_seconds=timeout_seconds, symbol=symbol)
            return True
        try:
            task = gate_api.CountdownCancelAllFuturesTask(
                timeout=timeout_seconds,
                contract=symbol or None,
            )
        except Exception:
            event_log("kill_switch_unsupported", timeout_seconds=timeout_seconds, symbol=symbol)
            return False

        def _call() -> Any:
            return self._client.countdown_cancel_all_futures(SETTLE, task)

        result = with_retry(_call)
        return result is not None

    def list_my_trades(self, symbol: str = "", limit: int = 50) -> List[Any]:
        if not self._client:
            return []
        def _call() -> List[Any]:
            return list(self._client.get_my_trades(SETTLE, contract=symbol or None, limit=limit))
        return with_retry(_call) or []

    def list_open_orders(self, symbol: str = "") -> List[Any]:
        if not self._client:
            return []
        def _call() -> List[Any]:
            return list(self._client.list_futures_orders(SETTLE, status="open", contract=symbol or None))
        return with_retry(_call) or []

    def list_positions(self) -> List[Any]:
        if not self._client:
            return []
        def _call() -> List[Any]:
            return list(self._client.list_positions(SETTLE))
        return with_retry(_call) or []

    def place_order(self, intent: OrderIntent) -> Optional[Any]:
        if intent.size == 0 and not intent.close_position:
            return None

        if DRY_RUN:
            event_log(
                "dry_order",
                symbol=intent.symbol,
                size=intent.size,
                side=intent.side,
                label=intent.label,
                reduce_only=intent.reduce_only,
                close_position=intent.close_position,
            )
            return {
                "dry_run": True,
                "symbol": intent.symbol,
                "size": intent.size,
                "label": intent.label,
                "reduce_only": intent.reduce_only,
                "close_position": intent.close_position,
                "fill_price": None,
                "status": "finished",
            }

        if not self._client or gate_api is None:
            return None

        try:
            order = gate_api.FuturesOrder(
                contract=intent.symbol,
                size=intent.size,
                price="0",
                tif="ioc",
                text=intent.label[:28],
                reduce_only=bool(intent.reduce_only),
                close=bool(intent.close_position),
            )
        except TypeError:
            # SDK compatibility fallback if some fields are absent
            order = gate_api.FuturesOrder(
                contract=intent.symbol,
                size=intent.size,
                price="0",
                tif="ioc",
                text=intent.label[:28],
            )
            try:
                setattr(order, "reduce_only", bool(intent.reduce_only))
            except Exception:
                pass
            try:
                setattr(order, "close", bool(intent.close_position))
            except Exception:
                pass

        def _call() -> Any:
            return self._client.create_futures_order(SETTLE, order)

        result = with_retry(_call)
        if result is None:
            event_log("order_failed", symbol=intent.symbol, label=intent.label, size=intent.size)
            return None

        event_log(
            "order_placed",
            symbol=intent.symbol,
            label=intent.label,
            size=intent.size,
            reduce_only=intent.reduce_only,
            close_position=intent.close_position,
            order_id=str(getattr(result, "id", "")),
            status=str(getattr(result, "status", "")),
            fill_price=safe_float(getattr(result, "fill_price", 0.0)),
        )
        return result


# =============================================================================
# INDICATORS
# =============================================================================

def _closes(candles: Sequence[Any]) -> List[float]:
    return [safe_float(getattr(c, "c", 0.0)) for c in candles]


def _highs(candles: Sequence[Any]) -> List[float]:
    return [safe_float(getattr(c, "h", 0.0)) for c in candles]


def _lows(candles: Sequence[Any]) -> List[float]:
    return [safe_float(getattr(c, "l", 0.0)) for c in candles]


def _opens(candles: Sequence[Any]) -> List[float]:
    return [safe_float(getattr(c, "o", 0.0)) for c in candles]


def _volumes(candles: Sequence[Any]) -> List[float]:
    return [safe_float(getattr(c, "v", 0.0)) for c in candles]


def ema(values: Sequence[float], period: int) -> List[float]:
    if len(values) < period:
        return []
    alpha = 2.0 / (period + 1.0)
    out = [sum(values[:period]) / period]
    for value in values[period:]:
        out.append(value * alpha + out[-1] * (1.0 - alpha))
    return out


def rsi(closes: Sequence[float], period: int = 14) -> Optional[float]:
    if len(closes) < period + 1:
        return None
    deltas = [closes[i] - closes[i - 1] for i in range(1, len(closes))]
    gains = [x if x > 0 else 0.0 for x in deltas]
    losses = [-x if x < 0 else 0.0 for x in deltas]
    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period
    for idx in range(period, len(deltas)):
        avg_gain = (avg_gain * (period - 1) + gains[idx]) / period
        avg_loss = (avg_loss * (period - 1) + losses[idx]) / period
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100.0 - (100.0 / (1.0 + rs))


def true_range(highs: Sequence[float], lows: Sequence[float], closes: Sequence[float]) -> List[float]:
    if len(closes) < 2:
        return []
    out: List[float] = []
    for idx in range(1, len(closes)):
        out.append(
            max(
                highs[idx] - lows[idx],
                abs(highs[idx] - closes[idx - 1]),
                abs(lows[idx] - closes[idx - 1]),
            )
        )
    return out


def atr_series(candles: Sequence[Any], period: int = 14) -> List[float]:
    highs = _highs(candles)
    lows = _lows(candles)
    closes = _closes(candles)
    tr = true_range(highs, lows, closes)
    if len(tr) < period:
        return []
    out: List[float] = []
    for idx in range(period - 1, len(tr)):
        out.append(sum(tr[idx - period + 1:idx + 1]) / period)
    return out


def bollinger(closes: Sequence[float], period: int = 20, num_std: float = 2.0) -> Optional[Tuple[float, float, float, float]]:
    if len(closes) < period:
        return None
    window = list(closes[-period:])
    mid = sum(window) / period
    std = statistics.stdev(window) if len(window) > 1 else 0.0
    upper = mid + num_std * std
    lower = mid - num_std * std
    width = (upper - lower) / mid if mid else 0.0
    return upper, mid, lower, width


def adx(candles: Sequence[Any], period: int = 14) -> Optional[float]:
    if len(candles) < period * 2:
        return None
    highs = _highs(candles)
    lows = _lows(candles)
    closes = _closes(candles)

    tr = true_range(highs, lows, closes)
    plus_dm: List[float] = []
    minus_dm: List[float] = []

    for idx in range(1, len(closes)):
        up_move = highs[idx] - highs[idx - 1]
        down_move = lows[idx - 1] - lows[idx]
        plus_dm.append(up_move if up_move > down_move and up_move > 0 else 0.0)
        minus_dm.append(down_move if down_move > up_move and down_move > 0 else 0.0)

    def smooth(values: Sequence[float], p: int) -> List[float]:
        if len(values) < p:
            return []
        out = [sum(values[:p])]
        for val in values[p:]:
            out.append(out[-1] - out[-1] / p + val)
        return out

    tr_s = smooth(tr, period)
    plus_s = smooth(plus_dm, period)
    minus_s = smooth(minus_dm, period)
    if not tr_s:
        return None

    dx_vals: List[float] = []
    for trv, pv, mv in zip(tr_s, plus_s, minus_s):
        if trv == 0:
            continue
        pdi = 100.0 * pv / trv
        mdi = 100.0 * mv / trv
        dx = 100.0 * abs(pdi - mdi) / (pdi + mdi) if (pdi + mdi) else 0.0
        dx_vals.append(dx)

    if not dx_vals:
        return None
    window = dx_vals[-period:]
    return sum(window) / len(window)


def vwap(candles: Sequence[Any], bars: int = VWAP_BARS) -> Optional[float]:
    window = list(candles[-bars:] if len(candles) >= bars else candles)
    if not window:
        return None
    pv = 0.0
    vv = 0.0
    for c in window:
        typical = (safe_float(getattr(c, "h", 0.0)) + safe_float(getattr(c, "l", 0.0)) + safe_float(getattr(c, "c", 0.0))) / 3.0
        vol = safe_float(getattr(c, "v", 0.0))
        pv += typical * vol
        vv += vol
    return pv / vv if vv else None


# =============================================================================
# REGIME + STRATEGY
# =============================================================================

def classify_regime_from_candles(candles: Sequence[Any]) -> RegimeSnapshot:
    if len(candles) < 30:
        return RegimeSnapshot(Regime.VOLATILE, 0.0, 50.0, 99.0, 0.0)

    closes = _closes(candles)
    ema_fast = ema(closes, 9)
    ema_slow = ema(closes, 21)
    current_rsi = rsi(closes) or 50.0

    atr_vals = atr_series(candles, 14)
    current_atr = atr_vals[-1] if atr_vals else 0.0
    mean_atr = sum(atr_vals[-20:]) / max(1, min(20, len(atr_vals))) if atr_vals else 1.0
    atr_ratio = current_atr / mean_atr if mean_atr else 1.0

    bb = bollinger(closes)
    bb_width = bb[3] if bb else 0.0
    current_adx = adx(candles) or 0.0

    if atr_ratio >= ATR_VOLATILE_MULT:
        reg = Regime.VOLATILE
    elif current_adx >= ADX_TREND_MIN:
        fast_now = ema_fast[-1] if ema_fast else 0.0
        slow_now = ema_slow[-1] if ema_slow else 0.0
        reg = Regime.TREND_UP if fast_now > slow_now else Regime.TREND_DOWN
    else:
        reg = Regime.RANGING

    return RegimeSnapshot(
        regime=reg,
        adx=round(current_adx, 3),
        rsi=round(current_rsi, 3),
        atr_ratio=round(atr_ratio, 3),
        bb_width=round(bb_width, 5),
        ema_fast=ema_fast[-1] if ema_fast else 0.0,
        ema_slow=ema_slow[-1] if ema_slow else 0.0,
    )


def classify_regime(client: GateClient, symbol: str) -> RegimeSnapshot:
    candles = client.fetch_candles(symbol, interval="5m", limit=100)
    return classify_regime_from_candles(candles)


def measure_move(client: GateClient, symbol: str) -> Optional[float]:
    candles = client.fetch_candles(symbol, interval="1m", limit=LOOKBACK_HOURS * 60)
    if len(candles) < 5:
        return None
    opens = _opens(candles)
    closes = _closes(candles)
    if not opens or not closes or opens[0] == 0:
        return None
    return (closes[-1] - opens[0]) / opens[0]


def regime_allows_entry(
    snap: RegimeSnapshot,
    move_pct: float,
    current_price: float,
    vwap_price: Optional[float],
) -> Tuple[bool, str, str]:
    if snap.regime == Regime.VOLATILE:
        return False, "volatile-skip", ""

    def vwap_ok(side: str) -> Tuple[bool, str]:
        if vwap_price is None:
            return True, ""
        if side == "short" and current_price <= vwap_price:
            return False, "vwap-block-short"
        if side == "long" and current_price >= vwap_price:
            return False, "vwap-block-long"
        return True, ""

    if snap.regime == Regime.TREND_UP:
        if snap.rsi >= RSI_OVERBOUGHT and move_pct >= PUMP_THRESHOLD:
            ok, reason = vwap_ok("short")
            return ok, (reason or "trend-up-fade-short"), ("short" if ok else "")
        return False, "trend-up-no-edge", ""

    if snap.regime == Regime.TREND_DOWN:
        if move_pct >= PUMP_THRESHOLD:
            ok, reason = vwap_ok("short")
            return ok, (reason or "trend-down-cont-short"), ("short" if ok else "")
        return False, "trend-down-no-edge", ""

    if snap.rsi >= RSI_OVERBOUGHT and move_pct >= PUMP_THRESHOLD:
        ok, reason = vwap_ok("short")
        return ok, (reason or "range-short"), ("short" if ok else "")
    if snap.rsi <= RSI_OVERSOLD and move_pct <= DUMP_THRESHOLD:
        ok, reason = vwap_ok("long")
        return ok, (reason or "range-long"), ("long" if ok else "")
    return False, "range-no-edge", ""


def calc_order_size(meta: ContractMeta, snap: RegimeSnapshot, balance_usd: float) -> int:
    # Basic quote-notional sizing translated to contracts via multiplier/price
    # Risk-aware and capped hard.
    if meta.quanto_multiplier <= 0 or meta.last_price <= 0:
        return 0

    volatility_scalar = 1.0
    if snap.atr_ratio > 1.5:
        volatility_scalar = 0.8
    elif snap.atr_ratio < 0.8:
        volatility_scalar = 1.2

    max_risk_usd = balance_usd * MAX_ACCOUNT_RISK_PCT
    desired_notional = min(BASE_ORDER_NOTIONAL_USD * volatility_scalar, max_risk_usd)
    contract_notional = meta.approx_contract_notional
    raw_contracts = max(1, int(round(desired_notional / max(contract_notional, 1e-9))))
    size = max(meta.min_order_size, raw_contracts)
    return max(0, size)


def estimate_margin_required(price: float, qty: int, multiplier: float, leverage: int) -> float:
    notion = price * qty * multiplier
    return notion / max(1, leverage)


def estimated_fee(price: float, qty: int, multiplier: float, rate: float = TAKER_FEE_RATE) -> float:
    notion = price * abs(qty) * multiplier
    return notion * rate


# =============================================================================
# CACHE + COOLDOWNS
# =============================================================================

class CooldownRegistry:
    def __init__(self, initial: Optional[Dict[str, str]] = None) -> None:
        self._bans: Dict[str, str] = dict(initial or {})
        self._lock = threading.Lock()

    def ban(self, symbol: str, seconds: int = COOLDOWN_SECONDS) -> None:
        expiry = (now_utc() + timedelta(seconds=seconds)).isoformat()
        with self._lock:
            self._bans[symbol] = expiry
        event_log("cooldown_ban", symbol=symbol, until=expiry)

    def is_banned(self, symbol: str) -> bool:
        with self._lock:
            expiry = self._bans.get(symbol)
        if not expiry:
            return False
        if now_utc() >= datetime.fromisoformat(expiry):
            with self._lock:
                self._bans.pop(symbol, None)
            return False
        return True

    def export(self) -> Dict[str, str]:
        with self._lock:
            return dict(self._bans)

    def active_count(self) -> int:
        now = now_utc()
        with self._lock:
            return sum(1 for exp in self._bans.values() if datetime.fromisoformat(exp) > now)


class RegimeCache:
    def __init__(self) -> None:
        self._cache: Dict[str, RegimeSnapshot] = {}
        self._lock = threading.Lock()

    def get(self, client: GateClient, symbol: str) -> RegimeSnapshot:
        with self._lock:
            snap = self._cache.get(symbol)
        if snap is None or snap.is_stale():
            snap = classify_regime(client, symbol)
            with self._lock:
                self._cache[symbol] = snap
        return snap

    def summary(self) -> Dict[str, int]:
        out = {r.name: 0 for r in Regime}
        with self._lock:
            for snap in self._cache.values():
                out[snap.regime.name] += 1
        return out


# =============================================================================
# UNIVERSE
# =============================================================================

def scan_micro_contracts(client: GateClient) -> List[ContractMeta]:
    metas: List[ContractMeta] = []
    for c in client.list_contracts():
        try:
            meta = ContractMeta(
                symbol=str(getattr(c, "contract", "")),
                last_price=safe_float(getattr(c, "last", 0.0)),
                quanto_multiplier=safe_float(getattr(c, "quanto_multiplier", 1.0), 1.0),
                volume_24h_quote=safe_float(getattr(c, "volume_24h_quote", 0.0)),
                min_order_size=max(1, safe_int(getattr(c, "order_size_min", 1), 1)),
                leverage_min=max(1, safe_int(getattr(c, "leverage_min", 1), 1)),
                leverage_max=max(1, safe_int(getattr(c, "leverage_max", 100), 100)),
                maintenance_rate=MAINT_MARGIN_RATE,
            )
            if meta.last_price <= 0 or meta.quanto_multiplier <= 0:
                continue
            notional = meta.approx_contract_notional
            if MIN_NOTIONAL <= notional <= MAX_NOTIONAL and meta.volume_24h_quote >= MIN_VOLUME_USDT:
                metas.append(meta)
        except Exception:
            continue
    metas.sort(key=lambda x: x.volume_24h_quote, reverse=True)
    event_log("universe_scan", count=len(metas))
    return metas


# =============================================================================
# PORTFOLIO + LIVE POSITION MANAGER
# =============================================================================

class PositionManager:
    def __init__(
        self,
        client: GateClient,
        cooldown: CooldownRegistry,
        store: StateStore,
        starting_state: Dict[str, Any],
    ) -> None:
        self.client = client
        self.cooldown = cooldown
        self.store = store
        self.lock = threading.Lock()

        self.positions: Dict[str, PositionRecord] = {}
        self.seen_order_tags: set[str] = set(starting_state.get("seen_order_tags", []))
        self.daily_realised: Dict[str, float] = dict(starting_state.get("daily_realised", {}))
        self.last_reconcile_at: Optional[str] = starting_state.get("last_reconcile_at")

        for sym, raw in starting_state.get("positions", {}).items():
            try:
                fills = [FillRecord(**f) for f in raw.get("fills", [])]
                raw = dict(raw)
                raw["fills"] = fills
                self.positions[sym] = PositionRecord(**raw)
            except Exception as exc:
                log.warning("Failed to load position %s: %s", sym, exc)

    def persist(self) -> None:
        state = {
            "positions": {k: asdict(v) for k, v in self.positions.items()},
            "cooldowns": self.cooldown.export(),
            "seen_order_tags": sorted(self.seen_order_tags),
            "daily_realised": self.daily_realised,
            "last_reconcile_at": self.last_reconcile_at,
            "metadata": {
                "saved_at": ts(),
                "app": APP_NAME,
                "version": VERSION,
            },
        }
        self.store.save(state)

    def daily_pnl(self) -> float:
        return float(self.daily_realised.get(dateroll_key(), 0.0))

    def add_realised_today(self, amount: float) -> None:
        key = dateroll_key()
        self.daily_realised[key] = float(self.daily_realised.get(key, 0.0) + amount)

    def active(self) -> List[PositionRecord]:
        return [p for p in self.positions.values() if p.is_open()]

    def daily_guard_tripped(self) -> bool:
        limit = -ACCOUNT_BALANCE * MAX_DAILY_LOSS_PCT
        pnl = self.daily_pnl()
        if pnl <= limit:
            event_log("daily_guard", pnl=pnl, limit=limit)
            return True
        return False

    def can_open_more(self, regime: Regime) -> bool:
        active = self.active()
        if len(active) >= MAX_OPEN_POSITIONS:
            return False
        regime_count = sum(1 for p in active if p.regime == regime.name)
        return regime_count < MAX_PER_REGIME

    def reconcile(self) -> None:
        """
        Conservative reconciliation:
        - refresh last_reconcile_at
        - keep local positions as source of bot-owned state
        - optionally inspect exchange positions/open orders for diagnostics
        """
        try:
            open_orders = self.client.list_open_orders()
            exch_positions = self.client.list_positions()
            event_log(
                "reconcile",
                open_orders=len(open_orders),
                exchange_positions=len(exch_positions),
                local_positions=len(self.active()),
            )
            self.last_reconcile_at = ts()
        except Exception as exc:
            event_log("reconcile_error", error=str(exc))

        self.persist()

    def _fee(self, price: float, qty: int, multiplier: float) -> float:
        return estimated_fee(price, qty, multiplier, TAKER_FEE_RATE)

    def _margin_buffer_ok(self, price: float, qty: int, multiplier: float) -> bool:
        need = estimate_margin_required(price, qty, multiplier, LEVERAGE) + self._fee(price, qty, multiplier)
        max_allow = ACCOUNT_BALANCE * MAX_ACCOUNT_RISK_PCT
        return need <= max_allow

    def _record_fill(self, pos: PositionRecord, side: str, qty: int, price: float, label: str, reduce_only: bool) -> None:
        fee = self._fee(price, qty, pos.contract_multiplier)
        pos.fills.append(
            FillRecord(
                ts=ts(),
                side=side,
                size=qty,
                price=price,
                label=label,
                fee=fee,
                reduce_only=reduce_only,
            )
        )

    def _journal_open(self, pos: PositionRecord) -> None:
        row = {
            "timestamp": ts(),
            "event": "OPEN",
            "symbol": pos.symbol,
            "side": pos.side,
            "entry_price": pos.entry_price,
            "avg_entry": pos.avg_entry,
            "size": pos.size,
            "remaining": pos.remaining,
            "regime": pos.regime,
            "realised": "",
            "tag": pos.entry_tag,
        }
        write_trade_csv(row)

    def _journal_close(self, pos: PositionRecord, reason: str) -> None:
        row = {
            "timestamp": ts(),
            "event": f"CLOSE:{reason}",
            "symbol": pos.symbol,
            "side": pos.side,
            "entry_price": pos.entry_price,
            "avg_entry": pos.avg_entry,
            "size": pos.size,
            "remaining": pos.remaining,
            "regime": pos.regime,
            "realised": f"{pos.realised_pnl:.8f}",
            "tag": pos.entry_tag,
        }
        write_trade_csv(row)

    def open_position(self, meta: ContractMeta, snap: RegimeSnapshot, side: str, entry_reason: str) -> bool:
        symbol = meta.symbol

        if self.cooldown.is_banned(symbol):
            return False
        if self.daily_guard_tripped():
            return False
        if not self.can_open_more(snap.regime):
            return False
        if symbol in self.positions and self.positions[symbol].is_open():
            return False

        size = calc_order_size(meta, snap, ACCOUNT_BALANCE)
        if size < meta.min_order_size:
            return False

        if LEVERAGE < meta.leverage_min or LEVERAGE > meta.leverage_max:
            event_log("bad_leverage", symbol=symbol, leverage=LEVERAGE, min=meta.leverage_min, max=meta.leverage_max)
            return False

        if not self._margin_buffer_ok(meta.last_price, size, meta.quanto_multiplier):
            event_log("margin_block", symbol=symbol, size=size)
            return False

        if not self.client.set_leverage(symbol, LEVERAGE):
            return False

        signed_size = -size if side == "short" else size
        tag = make_order_tag([symbol, side, "entry", str(int(time.time() // 10)), entry_reason])

        if tag in self.seen_order_tags:
            return False

        result = self.client.place_order(
            OrderIntent(
                symbol=symbol,
                size=signed_size,
                side=side,
                label=tag,
                reduce_only=False,
                close_position=False,
            )
        )
        if result is None:
            return False

        fill_price = safe_float(getattr(result, "fill_price", 0.0), meta.last_price) or meta.last_price
        pos = PositionRecord(
            symbol=symbol,
            side=side,
            regime=snap.regime.name,
            entry_price=fill_price,
            avg_entry=fill_price,
            size=size,
            remaining=size,
            contract_multiplier=meta.quanto_multiplier,
            leverage=LEVERAGE,
            entry_tag=tag,
            next_dca_trigger=(fill_price * (1 + DCA_STEP_PCT) if side == "short" else fill_price * (1 - DCA_STEP_PCT)) if ENABLE_DCA else None,
            notes={"entry_reason": entry_reason},
        )
        self._record_fill(pos, side, size, fill_price, tag, False)

        with self.lock:
            self.positions[symbol] = pos
            self.seen_order_tags.add(tag)

        self._journal_open(pos)
        self.persist()

        event_log("position_open", symbol=symbol, side=side, size=size, fill_price=fill_price, regime=snap.regime.name)
        tg(f"📂 <b>OPEN {side.upper()}</b> {symbol}\nPrice: {fill_price:.8f}\nSize: {size}\nRegime: {snap.regime.name}")
        return True

    def _compute_pnl_pct(self, pos: PositionRecord, price: float) -> float:
        if pos.avg_entry <= 0:
            return 0.0
        if pos.side == "short":
            return (pos.avg_entry - price) / pos.avg_entry
        return (price - pos.avg_entry) / pos.avg_entry

    def _compute_pnl_usd(self, pos: PositionRecord, price: float, qty: Optional[int] = None) -> float:
        q = qty if qty is not None else pos.remaining
        if pos.side == "short":
            return (pos.avg_entry - price) * q * pos.contract_multiplier
        return (price - pos.avg_entry) * q * pos.contract_multiplier

    def _close_qty(self, pos: PositionRecord, qty: int, price: float, reason: str) -> bool:
        if qty <= 0 or pos.remaining <= 0:
            return False
        qty = min(qty, pos.remaining)
        intent_size = qty if pos.side == "short" else -qty
        tag = make_order_tag([pos.symbol, reason, "close", str(pos.remaining), str(int(time.time() // 10))])
        if tag in self.seen_order_tags:
            return False

        result = self.client.place_order(
            OrderIntent(
                symbol=pos.symbol,
                size=intent_size,
                side=("buy" if pos.side == "short" else "sell"),
                label=tag,
                reduce_only=True,
                close_position=False,
            )
        )
        if result is None:
            return False

        fill_price = safe_float(getattr(result, "fill_price", 0.0), price) or price
        pnl_amt = self._compute_pnl_usd(pos, fill_price, qty)
        fee_amt = self._fee(fill_price, qty, pos.contract_multiplier)

        pos.remaining -= qty
        pos.last_price = fill_price
        pos.realised_pnl += pnl_amt - fee_amt
        self.add_realised_today(pnl_amt - fee_amt)
        self._record_fill(pos, "close", qty, fill_price, tag, True)
        self.seen_order_tags.add(tag)

        if pos.remaining <= 0:
            pos.closed = True
            self._journal_close(pos, reason)
            tg(f"✅ <b>CLOSED</b> {pos.symbol}\nReason: {reason}\nPnL ≈ ${pos.realised_pnl:.6f}")
            event_log("position_closed", symbol=pos.symbol, reason=reason, pnl=pos.realised_pnl)

        self.persist()
        return True

    def _full_close(self, pos: PositionRecord, price: float, reason: str) -> bool:
        return self._close_qty(pos, pos.remaining, price, reason)

    def _dca_add(self, pos: PositionRecord, price: float) -> bool:
        if not ENABLE_DCA:
            return False
        if pos.dca_adds_used >= MAX_DCA_ADDS:
            return False

        add_qty = max(1, int(round(pos.size * (DCA_SCALE ** pos.dca_adds_used))))
        if not self._margin_buffer_ok(price, add_qty, pos.contract_multiplier):
            return False

        signed = -add_qty if pos.side == "short" else add_qty
        tag = make_order_tag([pos.symbol, "dca", str(pos.dca_adds_used), str(int(time.time() // 10))])
        if tag in self.seen_order_tags:
            return False

        result = self.client.place_order(
            OrderIntent(
                symbol=pos.symbol,
                size=signed,
                side=pos.side,
                label=tag,
                reduce_only=False,
                close_position=False,
            )
        )
        if result is None:
            return False

        fill_price = safe_float(getattr(result, "fill_price", 0.0), price) or price
        old_total = pos.avg_entry * pos.remaining
        new_total = old_total + fill_price * add_qty
        pos.remaining += add_qty
        pos.size += add_qty
        pos.avg_entry = new_total / pos.remaining if pos.remaining else pos.avg_entry
        pos.dca_adds_used += 1
        pos.next_dca_trigger = (
            pos.entry_price * (1 + DCA_STEP_PCT * (pos.dca_adds_used + 1))
            if pos.side == "short" else
            pos.entry_price * (1 - DCA_STEP_PCT * (pos.dca_adds_used + 1))
        )
        self._record_fill(pos, pos.side, add_qty, fill_price, tag, False)
        self.seen_order_tags.add(tag)
        event_log("dca_add", symbol=pos.symbol, adds_used=pos.dca_adds_used, new_avg=pos.avg_entry, fill_price=fill_price)
        self.persist()
        return True

    def tick(self) -> None:
        for pos in list(self.active()):
            price = self.client.get_price(pos.symbol)
            if price is None or price <= 0:
                continue

            pos.last_price = price
            pos.unrealised_pnl = self._compute_pnl_usd(pos, price)
            pnl_pct = self._compute_pnl_pct(pos, price)
            pos.peak_pnl_pct = max(pos.peak_pnl_pct, pnl_pct)
            drawdown = pos.peak_pnl_pct - pnl_pct

            # DCA only when adverse move reaches trigger
            if ENABLE_DCA and pos.next_dca_trigger is not None:
                if (pos.side == "short" and price >= pos.next_dca_trigger) or (pos.side == "long" and price <= pos.next_dca_trigger):
                    self._dca_add(pos, price)

            # Hard stop
            if pnl_pct <= -STOP_LOSS_PCT:
                self._full_close(pos, price, "hard-stop")
                self.cooldown.ban(pos.symbol)
                continue

            # Take profit
            if pnl_pct >= TAKE_PROFIT_PCT and pos.ladder_idx >= len(PARTIALS):
                self._full_close(pos, price, "take-profit")
                continue

            # Trailing stop
            if pos.peak_pnl_pct >= TRAIL_ACTIVATE and drawdown >= TRAIL_PCT:
                self._full_close(pos, price, "trail-stop")
                continue

            # Partial ladder
            while pos.ladder_idx < len(PARTIALS):
                target, frac = PARTIALS[pos.ladder_idx]
                if pnl_pct < target:
                    break
                close_qty = max(1, int(round(pos.remaining * frac)))
                if self._close_qty(pos, close_qty, price, f"partial-{pos.ladder_idx + 1}"):
                    pos.ladder_idx += 1
                else:
                    break

        self.persist()

    def purge_closed(self) -> None:
        keep_after = now_utc() - timedelta(hours=12)
        stale = []
        for symbol, pos in self.positions.items():
            opened = datetime.fromisoformat(pos.opened_at)
            if pos.closed and opened < keep_after:
                stale.append(symbol)
        for s in stale:
            self.positions.pop(s, None)
        if stale:
            self.persist()


# =============================================================================
# SCANNER
# =============================================================================

def scan_one(
    client: GateClient,
    meta: ContractMeta,
    manager: PositionManager,
    regime_cache: RegimeCache,
    cooldown: CooldownRegistry,
) -> Optional[Tuple[ContractMeta, RegimeSnapshot, str, str]]:
    if cooldown.is_banned(meta.symbol):
        return None
    if meta.symbol in manager.positions and manager.positions[meta.symbol].is_open():
        return None

    move = measure_move(client, meta.symbol)
    if move is None:
        return None
    if abs(move) < min(abs(PUMP_THRESHOLD), abs(DUMP_THRESHOLD)):
        return None

    snap = regime_cache.get(client, meta.symbol)
    candles = client.fetch_candles(meta.symbol, interval="5m", limit=VWAP_BARS + 10)
    vwap_px = vwap(candles, VWAP_BARS) if candles else None
    ok, reason, side = regime_allows_entry(snap, move, meta.last_price, vwap_px)
    event_log(
        "scan_symbol",
        symbol=meta.symbol,
        move=move,
        regime=snap.label(),
        rsi=snap.rsi,
        adx=snap.adx,
        ok=ok,
        side=side,
        reason=reason,
    )
    if ok:
        return meta, snap, side, reason
    return None


def concurrent_scan(
    client: GateClient,
    metas: List[ContractMeta],
    manager: PositionManager,
    regime_cache: RegimeCache,
    cooldown: CooldownRegistry,
) -> List[Tuple[ContractMeta, RegimeSnapshot, str, str]]:
    out: List[Tuple[ContractMeta, RegimeSnapshot, str, str]] = []
    with ThreadPoolExecutor(max_workers=SCAN_WORKERS) as pool:
        futs = [pool.submit(scan_one, client, meta, manager, regime_cache, cooldown) for meta in metas]
        for fut in as_completed(futs):
            try:
                result = fut.result()
                if result is not None:
                    out.append(result)
            except Exception as exc:
                event_log("scan_worker_error", error=str(exc))
    return out


# =============================================================================
# BACKTEST ENGINE
# =============================================================================

class BacktestEngine:
    def __init__(self, symbol: str, candles: Sequence[Any], meta: Optional[ContractMeta] = None) -> None:
        self.symbol = symbol
        self.candles = list(candles)
        self.meta = meta or ContractMeta(
            symbol=symbol,
            last_price=safe_float(getattr(candles[-1], "c", 1.0)) if candles else 1.0,
            quanto_multiplier=1.0,
            volume_24h_quote=1_000_000.0,
            min_order_size=1,
            leverage_min=1,
            leverage_max=100,
            maintenance_rate=MAINT_MARGIN_RATE,
        )

    def _slipped(self, price: float, opening: bool, side: str) -> float:
        if side == "short" and opening:
            return price * (1.0 - SLIPPAGE_PCT)
        if side == "long" and opening:
            return price * (1.0 + SLIPPAGE_PCT)
        if side == "short" and not opening:
            return price * (1.0 + SLIPPAGE_PCT)
        return price * (1.0 - SLIPPAGE_PCT)

    def _fee(self, price: float, qty: int) -> float:
        return estimated_fee(price, qty, self.meta.quanto_multiplier, TAKER_FEE_RATE)

    def run(self) -> BacktestSummary:
        if len(self.candles) < 120:
            return BacktestSummary(
                symbol=self.symbol,
                trades=[],
                final_equity=ACCOUNT_BALANCE,
                return_pct=0.0,
                max_drawdown_pct=0.0,
                win_rate_pct=0.0,
                avg_trade_pct=0.0,
                profit_factor=0.0,
                sharpe_like=0.0,
                liquidation_events=0,
                params=self._params(),
            )

        equity = ACCOUNT_BALANCE
        peak_equity = equity
        drawdowns: List[float] = []
        trades: List[BacktestTrade] = []
        liquidation_events = 0

        in_trade = False
        side = ""
        regime_name = ""
        entry_idx = 0
        entry_price = 0.0
        avg_entry = 0.0
        qty = 0
        remaining = 0
        dca_adds = 0
        next_dca_trigger: Optional[float] = None
        peak_pnl_pct = 0.0
        ladder_idx = 0
        fees_paid = 0.0

        closes = _closes(self.candles)

        idx = 60
        while idx < len(self.candles):
            candle = self.candles[idx]
            price = safe_float(getattr(candle, "c", 0.0))
            high = safe_float(getattr(candle, "h", price))
            low = safe_float(getattr(candle, "l", price))

            if not in_trade:
                window = self.candles[:idx]
                snap = classify_regime_from_candles(window)
                lookback = 12
                move = 0.0
                if idx >= lookback:
                    base = closes[idx - lookback]
                    move = (closes[idx] - base) / base if base else 0.0
                vwap_px = vwap(window, min(VWAP_BARS, len(window)))
                ok, _reason, trade_side = regime_allows_entry(snap, move, price, vwap_px)
                if ok:
                    size = calc_order_size(self.meta, snap, equity)
                    if size > 0:
                        side = trade_side
                        regime_name = snap.regime.name
                        entry_idx = idx
                        fill = self._slipped(price, opening=True, side=side)
                        entry_price = fill
                        avg_entry = fill
                        qty = size
                        remaining = size
                        dca_adds = 0
                        next_dca_trigger = fill * (1 + DCA_STEP_PCT) if side == "short" else fill * (1 - DCA_STEP_PCT)
                        peak_pnl_pct = 0.0
                        ladder_idx = 0
                        in_trade = True
                        fees_paid = self._fee(fill, size)
                        equity -= fees_paid
                idx += 1
                peak_equity = max(peak_equity, equity)
                drawdowns.append((equity / peak_equity) - 1.0 if peak_equity else 0.0)
                continue

            # PnL
            pnl_pct = ((avg_entry - price) / avg_entry) if side == "short" else ((price - avg_entry) / avg_entry)
            peak_pnl_pct = max(peak_pnl_pct, pnl_pct)
            drawdown_from_peak = peak_pnl_pct - pnl_pct

            # Estimated liquidation test: use adverse extreme
            adverse_mark = high if side == "short" else low
            adverse_pnl_usd = ((avg_entry - adverse_mark) if side == "short" else (adverse_mark - avg_entry)) * remaining * self.meta.quanto_multiplier
            estimated_margin = estimate_margin_required(avg_entry, remaining, self.meta.quanto_multiplier, LEVERAGE)
            maint = abs(adverse_mark * remaining * self.meta.quanto_multiplier) * self.meta.maintenance_rate
            if equity + adverse_pnl_usd <= maint or (estimated_margin > 0 and (equity + adverse_pnl_usd) < -estimated_margin):
                exit_px = self._slipped(adverse_mark, opening=False, side=side)
                pnl_usd = ((avg_entry - exit_px) if side == "short" else (exit_px - avg_entry)) * remaining * self.meta.quanto_multiplier
                exit_fee = self._fee(exit_px, remaining)
                total_fees = fees_paid + exit_fee
                equity += pnl_usd - exit_fee
                trades.append(
                    BacktestTrade(
                        symbol=self.symbol,
                        side=side,
                        regime=regime_name,
                        entry_idx=entry_idx,
                        exit_idx=idx,
                        entry_price=entry_price,
                        exit_price=exit_px,
                        pnl_pct=((pnl_usd - total_fees) / max(1e-9, (entry_price * qty * self.meta.quanto_multiplier / LEVERAGE))) * 100.0,
                        pnl_usd=pnl_usd - total_fees,
                        fees_usd=total_fees,
                        reason="liquidation-est",
                        dca_adds=dca_adds,
                    )
                )
                in_trade = False
                liquidation_events += 1
                idx += 1
                peak_equity = max(peak_equity, equity)
                drawdowns.append((equity / peak_equity) - 1.0 if peak_equity else 0.0)
                continue

            # DCA
            if ENABLE_DCA and next_dca_trigger is not None and dca_adds < MAX_DCA_ADDS:
                dca_hit = (side == "short" and high >= next_dca_trigger) or (side == "long" and low <= next_dca_trigger)
                if dca_hit:
                    add_qty = max(1, int(round(qty * (DCA_SCALE ** dca_adds))))
                    fill = self._slipped(next_dca_trigger, opening=True, side=side)
                    total_before = avg_entry * remaining
                    total_after = total_before + fill * add_qty
                    remaining += add_qty
                    qty += add_qty
                    avg_entry = total_after / remaining
                    fees_paid += self._fee(fill, add_qty)
                    equity -= self._fee(fill, add_qty)
                    dca_adds += 1
                    next_dca_trigger = entry_price * (1 + DCA_STEP_PCT * (dca_adds + 1)) if side == "short" else entry_price * (1 - DCA_STEP_PCT * (dca_adds + 1))

            # Exit logic
            reason = ""
            exit_px = price

            if pnl_pct <= -STOP_LOSS_PCT:
                reason = "hard-stop"
                exit_px = self._slipped(price, opening=False, side=side)
            elif peak_pnl_pct >= TRAIL_ACTIVATE and drawdown_from_peak >= TRAIL_PCT:
                reason = "trail-stop"
                exit_px = self._slipped(price, opening=False, side=side)
            else:
                while ladder_idx < len(PARTIALS):
                    target, frac = PARTIALS[ladder_idx]
                    if pnl_pct < target:
                        break
                    close_qty = max(1, int(round(remaining * frac)))
                    partial_px = self._slipped(price, opening=False, side=side)
                    partial_pnl = ((avg_entry - partial_px) if side == "short" else (partial_px - avg_entry)) * close_qty * self.meta.quanto_multiplier
                    partial_fee = self._fee(partial_px, close_qty)
                    equity += partial_pnl - partial_fee
                    fees_paid += partial_fee
                    remaining -= close_qty
                    ladder_idx += 1
                    if remaining <= 0:
                        reason = "scaled-out"
                        exit_px = partial_px
                        break
                if not reason and pnl_pct >= TAKE_PROFIT_PCT and ladder_idx >= len(PARTIALS):
                    reason = "take-profit"
                    exit_px = self._slipped(price, opening=False, side=side)

            if reason:
                if remaining > 0:
                    pnl_usd = ((avg_entry - exit_px) if side == "short" else (exit_px - avg_entry)) * remaining * self.meta.quanto_multiplier
                    exit_fee = self._fee(exit_px, remaining)
                    total_fees = fees_paid + exit_fee
                    equity += pnl_usd - exit_fee
                else:
                    pnl_usd = 0.0
                    total_fees = fees_paid
                trades.append(
                    BacktestTrade(
                        symbol=self.symbol,
                        side=side,
                        regime=regime_name,
                        entry_idx=entry_idx,
                        exit_idx=idx,
                        entry_price=entry_price,
                        exit_price=exit_px,
                        pnl_pct=((equity - ACCOUNT_BALANCE) / ACCOUNT_BALANCE) * 100.0 if ACCOUNT_BALANCE else 0.0,
                        pnl_usd=(pnl_usd - total_fees),
                        fees_usd=total_fees,
                        reason=reason,
                        dca_adds=dca_adds,
                    )
                )
                in_trade = False

            idx += 1
            peak_equity = max(peak_equity, equity)
            drawdowns.append((equity / peak_equity) - 1.0 if peak_equity else 0.0)

        trade_returns = [t.pnl_usd for t in trades]
        winners = [x for x in trade_returns if x > 0]
        losers = [x for x in trade_returns if x < 0]
        win_rate = (len(winners) / len(trades) * 100.0) if trades else 0.0
        avg_trade_pct = (sum(trade_returns) / len(trades) / max(ACCOUNT_BALANCE, 1e-9) * 100.0) if trades else 0.0
        profit_factor = (sum(winners) / abs(sum(losers))) if losers else (float("inf") if winners else 0.0)

        if len(trade_returns) >= 2 and statistics.pstdev(trade_returns) > 0:
            sharpe_like = statistics.mean(trade_returns) / statistics.pstdev(trade_returns) * math.sqrt(len(trade_returns))
        else:
            sharpe_like = 0.0

        return BacktestSummary(
            symbol=self.symbol,
            trades=trades,
            final_equity=equity,
            return_pct=((equity / ACCOUNT_BALANCE) - 1.0) * 100.0 if ACCOUNT_BALANCE else 0.0,
            max_drawdown_pct=(min(drawdowns) * 100.0) if drawdowns else 0.0,
            win_rate_pct=win_rate,
            avg_trade_pct=avg_trade_pct,
            profit_factor=profit_factor,
            sharpe_like=sharpe_like,
            liquidation_events=liquidation_events,
            params=self._params(),
        )

    def walk_forward(self) -> Dict[str, Any]:
        candles = self.candles
        results = []
        i = 0
        while i + WALK_TRAIN + WALK_TEST <= len(candles):
            train = candles[i:i + WALK_TRAIN]
            test = candles[i + WALK_TRAIN:i + WALK_TRAIN + WALK_TEST]
            train_engine = BacktestEngine(self.symbol, train, self.meta)
            train_res = train_engine.run()
            test_engine = BacktestEngine(self.symbol, test, self.meta)
            test_res = test_engine.run()
            results.append({
                "start": i,
                "train_return_pct": train_res.return_pct,
                "test_return_pct": test_res.return_pct,
                "train_pf": train_res.profit_factor,
                "test_pf": test_res.profit_factor,
                "train_trades": len(train_res.trades),
                "test_trades": len(test_res.trades),
            })
            i += WALK_TEST
        return {
            "symbol": self.symbol,
            "windows": results,
            "avg_test_return_pct": (sum(x["test_return_pct"] for x in results) / len(results)) if results else 0.0,
            "avg_test_pf": (sum(x["test_pf"] for x in results) / len(results)) if results else 0.0,
        }

    def monte_carlo(self, summary: BacktestSummary, runs: int = MC_RUNS) -> Dict[str, Any]:
        pnl = [t.pnl_usd for t in summary.trades]
        if not pnl:
            return {"runs": runs, "median_final": ACCOUNT_BALANCE, "p05": ACCOUNT_BALANCE, "p95": ACCOUNT_BALANCE}
        finals = []
        for _ in range(runs):
            sampled = [random.choice(pnl) for _ in pnl]
            eq = ACCOUNT_BALANCE + sum(sampled)
            finals.append(eq)
        finals.sort()
        def pct(arr: List[float], p: float) -> float:
            if not arr:
                return 0.0
            idx = int(round((len(arr) - 1) * p))
            return arr[idx]
        return {
            "runs": runs,
            "median_final": pct(finals, 0.50),
            "p05": pct(finals, 0.05),
            "p95": pct(finals, 0.95),
            "min_final": min(finals),
            "max_final": max(finals),
        }

    def sweep(self) -> List[Dict[str, Any]]:
        global STOP_LOSS_PCT, TRAIL_PCT, TAKE_PROFIT_PCT, MAX_DCA_ADDS, DCA_SCALE, BASE_ORDER_NOTIONAL_USD
        orig = (STOP_LOSS_PCT, TRAIL_PCT, TAKE_PROFIT_PCT, MAX_DCA_ADDS, DCA_SCALE, BASE_ORDER_NOTIONAL_USD)

        rows: List[Dict[str, Any]] = []
        for stop in [0.03, 0.045, 0.06]:
            for trail in [0.01, 0.015, 0.02]:
                for tp in [0.008, 0.010, 0.014]:
                    for max_adds in [0, 1, 2]:
                        for dca_scale in [1.0, 1.1, 1.2]:
                            for base_notional in [0.05, 0.10, 0.15]:
                                STOP_LOSS_PCT = stop
                                TRAIL_PCT = trail
                                TAKE_PROFIT_PCT = tp
                                MAX_DCA_ADDS = max_adds
                                DCA_SCALE = dca_scale
                                BASE_ORDER_NOTIONAL_USD = base_notional
                                res = self.run()
                                rows.append({
                                    "stop": stop,
                                    "trail": trail,
                                    "tp": tp,
                                    "max_adds": max_adds,
                                    "dca_scale": dca_scale,
                                    "base_notional": base_notional,
                                    "return_pct": res.return_pct,
                                    "max_dd_pct": res.max_drawdown_pct,
                                    "win_rate_pct": res.win_rate_pct,
                                    "profit_factor": res.profit_factor,
                                    "liquidations": res.liquidation_events,
                                    "trades": len(res.trades),
                                })

        STOP_LOSS_PCT, TRAIL_PCT, TAKE_PROFIT_PCT, MAX_DCA_ADDS, DCA_SCALE, BASE_ORDER_NOTIONAL_USD = orig
        rows.sort(key=lambda x: (x["liquidations"], -x["profit_factor"], -x["return_pct"], x["max_dd_pct"]))
        return rows

    def _params(self) -> Dict[str, Any]:
        return {
            "leverage": LEVERAGE,
            "stop_loss_pct": STOP_LOSS_PCT,
            "trail_pct": TRAIL_PCT,
            "trail_activate": TRAIL_ACTIVATE,
            "take_profit_pct": TAKE_PROFIT_PCT,
            "base_order_notional_usd": BASE_ORDER_NOTIONAL_USD,
            "enable_dca": ENABLE_DCA,
            "dca_step_pct": DCA_STEP_PCT,
            "max_dca_adds": MAX_DCA_ADDS,
            "dca_scale": DCA_SCALE,
            "taker_fee_rate": TAKER_FEE_RATE,
            "slippage_pct": SLIPPAGE_PCT,
        }


# =============================================================================
# REPORTING
# =============================================================================

def print_status(manager: PositionManager, regime_cache: RegimeCache, cooldown: CooldownRegistry, cycle: int, universe_count: int) -> None:
    log.info(
        "cycle=%d universe=%d open=%d cooldowns=%d day_pnl=%+.6f regimes=%s",
        cycle,
        universe_count,
        len(manager.active()),
        cooldown.active_count(),
        manager.daily_pnl(),
        regime_cache.summary(),
    )
    for pos in manager.active():
        log.info(
            "pos %s %s entry=%.8f avg=%.8f rem=%d upnl=%+.6f peak=%.2f%% dca=%d regime=%s",
            pos.symbol, pos.side, pos.entry_price, pos.avg_entry, pos.remaining,
            pos.unrealised_pnl, pos.peak_pnl_pct * 100.0, pos.dca_adds_used, pos.regime
        )


def print_backtest(summary: BacktestSummary) -> None:
    print("=" * 80)
    print(f"Backtest: {summary.symbol}")
    print(f"Trades: {len(summary.trades)}")
    print(f"Final equity: ${summary.final_equity:.6f}")
    print(f"Return: {summary.return_pct:+.2f}%")
    print(f"Max DD: {summary.max_drawdown_pct:.2f}%")
    print(f"Win rate: {summary.win_rate_pct:.2f}%")
    print(f"Avg trade: {summary.avg_trade_pct:+.4f}%")
    print(f"Profit factor: {summary.profit_factor:.4f}")
    print(f"Sharpe-like: {summary.sharpe_like:.4f}")
    print(f"Liquidations: {summary.liquidation_events}")
    print("Params:", json.dumps(summary.params, indent=2))
    print("-" * 80)
    for t in summary.trades[-10:]:
        print(
            f"{t.side:5s} {t.regime:10s} entry={t.entry_price:.8f} exit={t.exit_price:.8f} "
            f"pnl=${t.pnl_usd:+.6f} reason={t.reason} dca={t.dca_adds}"
        )
    print("=" * 80)


def print_walk_forward(report: Dict[str, Any]) -> None:
    print("=" * 80)
    print(f"Walk-forward: {report['symbol']}")
    print(f"Windows: {len(report['windows'])}")
    print(f"Avg test return: {report['avg_test_return_pct']:+.3f}%")
    print(f"Avg test PF: {report['avg_test_pf']:.3f}")
    print("-" * 80)
    for row in report["windows"][:20]:
        print(
            f"start={row['start']:4d} train={row['train_return_pct']:+7.2f}% "
            f"test={row['test_return_pct']:+7.2f}% train_pf={row['train_pf']:.2f} "
            f"test_pf={row['test_pf']:.2f} train_n={row['train_trades']} test_n={row['test_trades']}"
        )
    print("=" * 80)


def print_mc(report: Dict[str, Any]) -> None:
    print("=" * 80)
    print("Monte Carlo")
    for k, v in report.items():
        if isinstance(v, float):
            print(f"{k}: {v:.6f}")
        else:
            print(f"{k}: {v}")
    print("=" * 80)


def print_sweep(rows: List[Dict[str, Any]], top_n: int = 20) -> None:
    print("=" * 120)
    print("Top parameter sets")
    print("=" * 120)
    for row in rows[:top_n]:
        print(
            f"stop={row['stop']:.3f} trail={row['trail']:.3f} tp={row['tp']:.3f} "
            f"adds={row['max_adds']} scale={row['dca_scale']:.2f} base={row['base_notional']:.2f} "
            f"ret={row['return_pct']:+7.2f}% dd={row['max_dd_pct']:7.2f}% "
            f"pf={row['profit_factor']:.3f} liq={row['liquidations']} trades={row['trades']}"
        )
    print("=" * 120)


# =============================================================================
# MAIN LOOP
# =============================================================================

def main_loop(dry: bool = True) -> None:
    global DRY_RUN
    DRY_RUN = dry

    log.info(
        "Starting %s v%s mode=%s balance=$%.2f leverage=%dx",
        APP_NAME, VERSION, "DRY" if DRY_RUN else "LIVE", ACCOUNT_BALANCE, LEVERAGE
    )
    event_log("startup", mode=("DRY" if DRY_RUN else "LIVE"), balance=ACCOUNT_BALANCE, leverage=LEVERAGE)
    tg(f"🚀 <b>{APP_NAME}</b> started\nMode: {'DRY' if DRY_RUN else 'LIVE'}")

    if not GATE_AVAILABLE:
        log.error("gate-api not installed")
        sys.exit(1)
    if not DRY_RUN and (not GATE_API_KEY or not GATE_API_SECRET):
        log.error("Missing GATE_API_KEY / GATE_API_SECRET")
        sys.exit(1)

    client = GateClient()
    store = StateStore(STATE_FILE)
    initial = store.load()
    cooldown = CooldownRegistry(initial=initial.get("cooldowns", {}))
    manager = PositionManager(client, cooldown, store, initial)
    regime_cache = RegimeCache()

    manager.reconcile()

    if not DRY_RUN:
        client.countdown_kill_switch(COUNTDOWN_KILL_SWITCH_SECONDS, "")

    cycle = 0
    while True:
        cycle += 1
        try:
            if not DRY_RUN:
                client.countdown_kill_switch(COUNTDOWN_KILL_SWITCH_SECONDS, "")

            metas = scan_micro_contracts(client)

            if manager.daily_guard_tripped():
                manager.tick()
                manager.purge_closed()
                print_status(manager, regime_cache, cooldown, cycle, len(metas))
                time.sleep(POLL_INTERVAL)
                continue

            candidates = concurrent_scan(client, metas, manager, regime_cache, cooldown)
            for meta, snap, side, reason in candidates:
                manager.open_position(meta, snap, side, reason)

            manager.tick()
            manager.purge_closed()
            print_status(manager, regime_cache, cooldown, cycle, len(metas))
        except KeyboardInterrupt:
            log.info("Interrupted")
            tg(f"🔴 <b>{APP_NAME}</b> stopped")
            event_log("shutdown")
            break
        except Exception as exc:
            log.error("Main loop error: %s", exc)
            event_log("main_loop_error", error=str(exc), traceback=traceback.format_exc())
        finally:
            manager.persist()

        time.sleep(POLL_INTERVAL)


# =============================================================================
# COMMANDS
# =============================================================================

def run_backtest_command(symbol: str) -> None:
    client = GateClient()
    candles = client.fetch_candles(symbol, interval=BACKTEST_INTERVAL, limit=BACKTEST_LIMIT)
    if len(candles) < 100:
        print("Not enough candles.")
        return
    meta = client.fetch_contract_meta(symbol)
    engine = BacktestEngine(symbol, candles, meta)
    summary = engine.run()
    print_backtest(summary)


def run_walk_forward_command(symbol: str) -> None:
    client = GateClient()
    candles = client.fetch_candles(symbol, interval=BACKTEST_INTERVAL, limit=BACKTEST_LIMIT)
    if len(candles) < WALK_TRAIN + WALK_TEST + 20:
        print("Not enough candles for walk-forward.")
        return
    meta = client.fetch_contract_meta(symbol)
    engine = BacktestEngine(symbol, candles, meta)
    report = engine.walk_forward()
    print_walk_forward(report)


def run_mc_command(symbol: str) -> None:
    client = GateClient()
    candles = client.fetch_candles(symbol, interval=BACKTEST_INTERVAL, limit=BACKTEST_LIMIT)
    if len(candles) < 100:
        print("Not enough candles.")
        return
    meta = client.fetch_contract_meta(symbol)
    engine = BacktestEngine(symbol, candles, meta)
    summary = engine.run()
    mc = engine.monte_carlo(summary)
    print_backtest(summary)
    print_mc(mc)


def run_sweep_command(symbol: str) -> None:
    client = GateClient()
    candles = client.fetch_candles(symbol, interval=BACKTEST_INTERVAL, limit=BACKTEST_LIMIT)
    if len(candles) < 100:
        print("Not enough candles.")
        return
    meta = client.fetch_contract_meta(symbol)
    engine = BacktestEngine(symbol, candles, meta)
    rows = engine.sweep()
    print_sweep(rows, 20)


# =============================================================================
# TESTS
# =============================================================================

class _MockCandle:
    def __init__(self, o: float, h: float, l: float, c: float, v: float) -> None:
        self.o = str(o)
        self.h = str(h)
        self.l = str(l)
        self.c = str(c)
        self.v = str(v)


class _MockClient:
    def __init__(self, candles_by_symbol: Dict[str, List[_MockCandle]], prices: Optional[Dict[str, float]] = None) -> None:
        self.candles_by_symbol = candles_by_symbol
        self.prices = prices or {}

    def fetch_candles(self, symbol: str, interval: str = "5m", limit: int = 100) -> List[_MockCandle]:
        return self.candles_by_symbol.get(symbol, [])[-limit:]

    def get_price(self, symbol: str) -> Optional[float]:
        return self.prices.get(symbol)

    def set_leverage(self, symbol: str, leverage: int) -> bool:
        return True

    def place_order(self, intent: OrderIntent) -> Dict[str, Any]:
        return {"fill_price": self.prices.get(intent.symbol, 100.0), "status": "finished", "id": "x"}

    def list_open_orders(self, symbol: str = "") -> List[Any]:
        return []

    def list_positions(self) -> List[Any]:
        return []


def _make_candles(prices: Iterable[float], spread: float = 0.003) -> List[_MockCandle]:
    out: List[_MockCandle] = []
    for p in prices:
        out.append(_MockCandle(p, p * (1 + spread), p * (1 - spread), p, 1000.0))
    return out


class TestIndicators(unittest.TestCase):
    def test_ema(self) -> None:
        vals = ema([float(i) for i in range(1, 21)], 5)
        self.assertTrue(vals)
        self.assertAlmostEqual(vals[0], 3.0, places=4)

    def test_rsi(self) -> None:
        val = rsi([100.0 + i for i in range(30)])
        self.assertIsNotNone(val)
        self.assertGreater(val or 0, 90)

    def test_bollinger(self) -> None:
        result = bollinger([float(i) for i in range(1, 21)], 20)
        self.assertIsNotNone(result)
        assert result is not None
        upper, mid, lower, width = result
        self.assertGreater(upper, mid)
        self.assertGreater(mid, lower)
        self.assertGreater(width, 0.0)

    def test_adx(self) -> None:
        candles = _make_candles([100 + math.sin(i * 0.3) * 3 for i in range(80)])
        result = adx(candles)
        if result is not None:
            self.assertGreaterEqual(result, 0.0)
            self.assertLessEqual(result, 100.0)

    def test_vwap(self) -> None:
        candles = _make_candles([10.0, 11.0, 12.0, 11.0, 10.0], 0.0)
        result = vwap(candles, 5)
        self.assertIsNotNone(result)
        self.assertAlmostEqual(result or 0.0, 10.8, places=1)


class TestRegime(unittest.TestCase):
    def _snap(self, regime: Regime, rsi_val: float = 50.0, atr_ratio: float = 1.0) -> RegimeSnapshot:
        return RegimeSnapshot(regime=regime, adx=20.0, rsi=rsi_val, atr_ratio=atr_ratio, bb_width=0.01)

    def test_short_allowed(self) -> None:
        ok, _, side = regime_allows_entry(self._snap(Regime.TREND_UP, 75.0), 0.12, 100.0, None)
        self.assertTrue(ok)
        self.assertEqual(side, "short")

    def test_long_allowed(self) -> None:
        ok, _, side = regime_allows_entry(self._snap(Regime.RANGING, 25.0), -0.12, 95.0, None)
        self.assertTrue(ok)
        self.assertEqual(side, "long")

    def test_vwap_block(self) -> None:
        ok, reason, _ = regime_allows_entry(self._snap(Regime.TREND_UP, 75.0), 0.12, 95.0, 100.0)
        self.assertFalse(ok)
        self.assertIn("vwap", reason)


class TestCooldown(unittest.TestCase):
    def test_ban(self) -> None:
        cd = CooldownRegistry()
        cd.ban("BTC_USDT", 1)
        self.assertTrue(cd.is_banned("BTC_USDT"))
        time.sleep(1.1)
        self.assertFalse(cd.is_banned("BTC_USDT"))


class TestPositionManager(unittest.TestCase):
    def test_margin_ok(self) -> None:
        state = StateStore(Path("test_state.json"))
        manager = PositionManager(_MockClient({}), CooldownRegistry(), state, state.load())  # type: ignore[arg-type]
        self.assertTrue(manager._margin_buffer_ok(100.0, 1, 0.001))

    def test_open_close_flow(self) -> None:
        candles = {"BTC_USDT": _make_candles([100.0] * 80)}
        client = _MockClient(candles, {"BTC_USDT": 100.0})
        state = StateStore(Path("test_state.json"))
        initial = state.load()
        manager = PositionManager(client, CooldownRegistry(), state, initial)  # type: ignore[arg-type]
        meta = ContractMeta("BTC_USDT", 100.0, 0.001, 1_000_000.0, 1, 1, 100)
        snap = RegimeSnapshot(Regime.RANGING, 20.0, 75.0, 1.0, 0.01)
        opened = manager.open_position(meta, snap, "short", "unit")
        self.assertTrue(opened)
        pos = manager.positions["BTC_USDT"]
        self.assertTrue(pos.is_open())
        ok = manager._full_close(pos, 99.0, "test")
        self.assertTrue(ok)
        self.assertTrue(pos.closed)
        try:
            Path("test_state.json").unlink(missing_ok=True)
        except Exception:
            pass


class TestBacktest(unittest.TestCase):
    def test_backtest_runs(self) -> None:
        prices = [100 + math.sin(i / 10.0) * 5 + (i * 0.02) for i in range(400)]
        candles = _make_candles(prices)
        meta = ContractMeta("BTC_USDT", prices[-1], 0.001, 1_000_000.0, 1, 1, 100)
        engine = BacktestEngine("BTC_USDT", candles, meta)
        summary = engine.run()
        self.assertIsInstance(summary, BacktestSummary)

    def test_mc(self) -> None:
        prices = [100 + math.sin(i / 7.0) * 3 for i in range(400)]
        candles = _make_candles(prices)
        meta = ContractMeta("BTC_USDT", prices[-1], 0.001, 1_000_000.0, 1, 1, 100)
        engine = BacktestEngine("BTC_USDT", candles, meta)
        summary = engine.run()
        report = engine.monte_carlo(summary, 50)
        self.assertIn("median_final", report)


def run_tests() -> None:
    suite = unittest.TestSuite()
    loader = unittest.TestLoader()
    for case in [TestIndicators, TestRegime, TestCooldown, TestPositionManager, TestBacktest]:
        suite.addTests(loader.loadTestsFromTestCase(case))
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)


# =============================================================================
# ENTRY
# =============================================================================

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Gate.io Micro Futures Trader — advanced single-file edition")
    parser.add_argument("--test", action="store_true", help="Run tests and exit")
    parser.add_argument("--dry", action="store_true", default=True, help="Dry-run mode")
    parser.add_argument("--live", action="store_true", help="Live trading mode")
    parser.add_argument("--backtest", metavar="SYMBOL", default="", help="Run backtest")
    parser.add_argument("--walk", metavar="SYMBOL", default="", help="Run walk-forward report")
    parser.add_argument("--mc", metavar="SYMBOL", default="", help="Run backtest + Monte Carlo")
    parser.add_argument("--sweep", metavar="SYMBOL", default="", help="Run parameter sweep")
    args = parser.parse_args()

    if args.test:
        run_tests()
    elif args.backtest:
        run_backtest_command(args.backtest)
    elif args.walk:
        run_walk_forward_command(args.walk)
    elif args.mc:
        run_mc_command(args.mc)
    elif args.sweep:
        run_sweep_command(args.sweep)
    else:
        main_loop(dry=not args.live)