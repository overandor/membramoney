
#!/usr/bin/env python3
"""
hyperliquid_llm_trader_100.py

Production-style single-file Hyperliquid LLM trader baseline.

What this version fixes vs the earlier drafts
---------------------------------------------
- no fake raw signing stub for live orders
- uses official hyperliquid-python-sdk Exchange/Info for signed trading
- SQLite persistence for orders/fills/service state
- JSONL structured logs
- metadata-driven asset resolution
- strict startup guards for live mode
- reconciliation against exchange open orders and fills
- cancel / cancel-by-cloid / modify support
- dead-man switch scheduling
- LLM planner via Groq or OpenRouter
- hard risk controls
- dry-run by default

Install
-------
pip install hyperliquid-python-sdk eth-account openai requests

Environment
-----------
# Hyperliquid
HL_SECRET_KEY=0x...
HL_ACCOUNT_ADDRESS=0x...
HL_BASE_URL=https://api.hyperliquid.xyz
HL_SYMBOL=BTC
HL_DRY_RUN=true
HL_ENABLE_LIVE=false
HL_REQUIRE_LIVE_CONFIRMATION=YES_I_UNDERSTAND

# Risk / execution
HL_MAX_ORDER_USD=25
HL_MAX_POSITION_USD=100
HL_MAX_OPEN_ORDERS=10
HL_MAX_DAILY_REALIZED_LOSS=25
HL_MAX_NOTIONAL_PER_MIN=250
HL_ORDER_TTL_MS=8000
HL_LOOP_INTERVAL_SEC=3
HL_STALE_ORDER_CANCEL_SEC=20
HL_CANCEL_ALL_ARM_SEC=15
HL_MIN_CONFIDENCE=0.60
HL_MAX_CONFIDENCE=1.00
HL_MAX_SPREAD_BPS=15

# LLM
LLM_PROVIDER=groq              # groq | openrouter | both | none
GROQ_API_KEY=
GROQ_MODEL=llama-3.3-70b-versatile
OPENROUTER_API_KEY=
OPENROUTER_MODEL=openrouter/auto

# Files
HL_DB_FILE=hl_trader.db
HL_LOG_FILE=hl_events.jsonl

Notes
-----
- "modify" is implemented as cancel-and-replace for safety/compatibility.
- "cancel_by_cloid" is resolved via persisted local cloid->oid mapping or exchange open orders.
- This is a serious baseline, not a promise of profitability.
"""

from __future__ import annotations

import datetime as dt
import json
import math
import os
import sqlite3
import time
import traceback
import uuid
from dataclasses import dataclass
from decimal import Decimal, ROUND_DOWN, getcontext
from typing import Any, Dict, List, Optional, Tuple

import requests
from openai import OpenAI

from eth_account import Account
from eth_account.signers.local import LocalAccount
from hyperliquid.exchange import Exchange
from hyperliquid.info import Info

getcontext().prec = 50


# ============================================================================
# Helpers
# ============================================================================

def now_ms() -> int:
    return int(time.time() * 1000)


def now_s() -> int:
    return int(time.time())


def utc_now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def today_utc() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d")


def safe_json_dumps(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":"), sort_keys=True, default=str)


def decimal_to_str(d: Decimal) -> str:
    s = format(d, "f")
    if "." in s:
        s = s.rstrip("0").rstrip(".")
    return s if s else "0"


def to_decimal(x: Any, default: str = "0") -> Decimal:
    try:
        return Decimal(str(x))
    except Exception:
        return Decimal(default)


def quantize_down(value: Decimal, decimals: int) -> Decimal:
    if decimals <= 0:
        return value.quantize(Decimal("1"), rounding=ROUND_DOWN)
    quantum = Decimal("1." + ("0" * decimals))
    return value.quantize(quantum, rounding=ROUND_DOWN)


def bps(a: Decimal, b: Decimal) -> Decimal:
    if a <= 0 or b <= 0:
        return Decimal("0")
    return abs(a - b) / ((a + b) / Decimal("2")) * Decimal("10000")


def new_cloid() -> str:
    return "0x" + uuid.uuid4().hex


# ============================================================================
# Config
# ============================================================================

@dataclass
class Config:
    secret_key: str
    account_address: str
    base_url: str
    symbol: str

    dry_run: bool
    enable_live: bool
    live_confirmation: str

    max_order_usd: Decimal
    max_position_usd: Decimal
    max_open_orders: int
    max_daily_realized_loss: Decimal
    max_notional_per_min: Decimal
    order_ttl_ms: int
    loop_interval_sec: float
    stale_order_cancel_sec: int
    cancel_all_arm_sec: int

    min_confidence: float
    max_confidence: float
    max_spread_bps: Decimal

    llm_provider: str
    groq_api_key: str
    groq_model: str
    openrouter_api_key: str
    openrouter_model: str

    db_file: str
    log_file: str
    request_timeout: int

    @staticmethod
    def from_env() -> "Config":
        def dec(name: str, default: str) -> Decimal:
            return Decimal(os.getenv(name, default).strip())

        def boolean(name: str, default: str) -> bool:
            return os.getenv(name, default).strip().lower() in {"1", "true", "yes", "y", "on"}

        return Config(
            secret_key=os.getenv("HL_SECRET_KEY", "").strip(),
            account_address=os.getenv("HL_ACCOUNT_ADDRESS", "").strip().lower(),
            base_url=os.getenv("HL_BASE_URL", "https://api.hyperliquid.xyz").strip().rstrip("/"),
            symbol=os.getenv("HL_SYMBOL", "BTC").strip().upper(),

            dry_run=boolean("HL_DRY_RUN", "true"),
            enable_live=boolean("HL_ENABLE_LIVE", "false"),
            live_confirmation=os.getenv("HL_REQUIRE_LIVE_CONFIRMATION", "").strip(),

            max_order_usd=dec("HL_MAX_ORDER_USD", "25"),
            max_position_usd=dec("HL_MAX_POSITION_USD", "100"),
            max_open_orders=int(os.getenv("HL_MAX_OPEN_ORDERS", "10")),
            max_daily_realized_loss=dec("HL_MAX_DAILY_REALIZED_LOSS", "25"),
            max_notional_per_min=dec("HL_MAX_NOTIONAL_PER_MIN", "250"),
            order_ttl_ms=int(os.getenv("HL_ORDER_TTL_MS", "8000")),
            loop_interval_sec=float(os.getenv("HL_LOOP_INTERVAL_SEC", "3")),
            stale_order_cancel_sec=int(os.getenv("HL_STALE_ORDER_CANCEL_SEC", "20")),
            cancel_all_arm_sec=int(os.getenv("HL_CANCEL_ALL_ARM_SEC", "15")),

            min_confidence=float(os.getenv("HL_MIN_CONFIDENCE", "0.60")),
            max_confidence=float(os.getenv("HL_MAX_CONFIDENCE", "1.00")),
            max_spread_bps=dec("HL_MAX_SPREAD_BPS", "15"),

            llm_provider=os.getenv("LLM_PROVIDER", "groq").strip().lower(),
            groq_api_key=os.getenv("GROQ_API_KEY", "").strip(),
            groq_model=os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile").strip(),
            openrouter_api_key=os.getenv("OPENROUTER_API_KEY", "").strip(),
            openrouter_model=os.getenv("OPENROUTER_MODEL", "openrouter/auto").strip(),

            db_file=os.getenv("HL_DB_FILE", "hl_trader.db").strip(),
            log_file=os.getenv("HL_LOG_FILE", "hl_events.jsonl").strip(),
            request_timeout=int(os.getenv("HL_HTTP_TIMEOUT_SEC", "15")),
        )

    def validate(self) -> None:
        if not self.account_address.startswith("0x") or len(self.account_address) != 42:
            raise RuntimeError("HL_ACCOUNT_ADDRESS must be a valid 42-char 0x address")

        if not self.dry_run:
            if not self.enable_live:
                raise RuntimeError("HL_DRY_RUN=false but HL_ENABLE_LIVE is not true")
            if self.live_confirmation != "YES_I_UNDERSTAND":
                raise RuntimeError("Live trading requires HL_REQUIRE_LIVE_CONFIRMATION=YES_I_UNDERSTAND")
            if not self.secret_key:
                raise RuntimeError("HL_SECRET_KEY is required in live mode")

        if self.cancel_all_arm_sec < 5:
            raise RuntimeError("HL_CANCEL_ALL_ARM_SEC must be >= 5")


# ============================================================================
# Logger
# ============================================================================

class JsonlLogger:
    def __init__(self, path: str):
        self.path = path

    def write(self, level: str, event: str, **details: Any) -> None:
        rec = {
            "ts": utc_now_iso(),
            "ts_ms": now_ms(),
            "level": level,
            "event": event,
            **details,
        }
        line = json.dumps(rec, ensure_ascii=False, default=str)
        print(line, flush=True)
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(line + "\n")

    def info(self, event: str, **details: Any) -> None:
        self.write("INFO", event, **details)

    def warning(self, event: str, **details: Any) -> None:
        self.write("WARNING", event, **details)

    def error(self, event: str, **details: Any) -> None:
        self.write("ERROR", event, **details)


# ============================================================================
# DB
# ============================================================================

class StateDB:
    def __init__(self, path: str):
        self.conn = sqlite3.connect(path)
        self.conn.row_factory = sqlite3.Row
        self._init()

    def _init(self) -> None:
        cur = self.conn.cursor()

        cur.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            oid TEXT PRIMARY KEY,
            cloid TEXT UNIQUE,
            symbol TEXT NOT NULL,
            asset INTEGER NOT NULL,
            side TEXT NOT NULL,
            limit_px TEXT NOT NULL,
            size TEXT NOT NULL,
            tif TEXT NOT NULL,
            reduce_only INTEGER NOT NULL,
            status TEXT NOT NULL,
            submit_ts INTEGER NOT NULL,
            last_update_ts INTEGER NOT NULL,
            raw_response_json TEXT,
            error_text TEXT
        )
        """)

        cur.execute("""
        CREATE TABLE IF NOT EXISTS fills (
            fill_id TEXT PRIMARY KEY,
            oid TEXT,
            symbol TEXT NOT NULL,
            side TEXT,
            px TEXT NOT NULL,
            sz TEXT NOT NULL,
            fee TEXT,
            closed_pnl TEXT,
            fill_ts INTEGER NOT NULL,
            raw_json TEXT
        )
        """)

        cur.execute("""
        CREATE TABLE IF NOT EXISTS positions (
            symbol TEXT PRIMARY KEY,
            asset INTEGER NOT NULL,
            position_sz TEXT NOT NULL,
            entry_px TEXT,
            unrealized_pnl TEXT,
            margin_used TEXT,
            leverage TEXT,
            last_update_ts INTEGER NOT NULL,
            raw_json TEXT
        )
        """)

        cur.execute("""
        CREATE TABLE IF NOT EXISTS service_state (
            k TEXT PRIMARY KEY,
            v TEXT NOT NULL
        )
        """)

        self.conn.commit()

    def set_kv(self, k: str, v: str) -> None:
        self.conn.execute("""
        INSERT INTO service_state (k, v) VALUES (?, ?)
        ON CONFLICT(k) DO UPDATE SET v = excluded.v
        """, (k, v))
        self.conn.commit()

    def get_kv(self, k: str, default: Optional[str] = None) -> Optional[str]:
        row = self.conn.execute("SELECT v FROM service_state WHERE k = ?", (k,)).fetchone()
        return row["v"] if row else default

    def upsert_order(
        self,
        oid: str,
        cloid: str,
        symbol: str,
        asset: int,
        side: str,
        limit_px: str,
        size: str,
        tif: str,
        reduce_only: int,
        status: str,
        raw_response_json: Optional[str],
        error_text: Optional[str],
    ) -> None:
        ts = now_ms()
        self.conn.execute("""
        INSERT INTO orders (
            oid, cloid, symbol, asset, side, limit_px, size, tif, reduce_only,
            status, submit_ts, last_update_ts, raw_response_json, error_text
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(oid) DO UPDATE SET
            cloid=excluded.cloid,
            symbol=excluded.symbol,
            asset=excluded.asset,
            side=excluded.side,
            limit_px=excluded.limit_px,
            size=excluded.size,
            tif=excluded.tif,
            reduce_only=excluded.reduce_only,
            status=excluded.status,
            last_update_ts=excluded.last_update_ts,
            raw_response_json=COALESCE(excluded.raw_response_json, orders.raw_response_json),
            error_text=excluded.error_text
        """, (
            oid, cloid, symbol, asset, side, limit_px, size, tif, reduce_only,
            status, ts, ts, raw_response_json, error_text
        ))
        self.conn.commit()

    def update_order_status(self, oid: str, status: str, raw_response_json: Optional[str] = None, error_text: Optional[str] = None) -> None:
        self.conn.execute("""
        UPDATE orders
        SET status = ?, raw_response_json = COALESCE(?, raw_response_json), error_text = ?, last_update_ts = ?
        WHERE oid = ?
        """, (status, raw_response_json, error_text, now_ms(), oid))
        self.conn.commit()

    def get_order_by_cloid(self, cloid: str) -> Optional[sqlite3.Row]:
        return self.conn.execute("SELECT * FROM orders WHERE cloid = ?", (cloid,)).fetchone()

    def get_open_local_orders(self) -> List[sqlite3.Row]:
        return self.conn.execute("""
        SELECT * FROM orders
        WHERE status IN ('resting','pending_submit','partially_filled','unknown')
        """).fetchall()

    def get_resting_local_orders_older_than(self, cutoff_ms: int) -> List[sqlite3.Row]:
        return self.conn.execute("""
        SELECT * FROM orders
        WHERE status IN ('resting','partially_filled','unknown')
          AND submit_ts < ?
        """, (cutoff_ms,)).fetchall()

    def insert_fill(
        self,
        fill_id: str,
        oid: Optional[str],
        symbol: str,
        side: Optional[str],
        px: str,
        sz: str,
        fee: Optional[str],
        closed_pnl: Optional[str],
        fill_ts: int,
        raw_json: str,
    ) -> bool:
        cur = self.conn.execute("""
        INSERT OR IGNORE INTO fills (fill_id, oid, symbol, side, px, sz, fee, closed_pnl, fill_ts, raw_json)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (fill_id, oid, symbol, side, px, sz, fee, closed_pnl, fill_ts, raw_json))
        self.conn.commit()
        return cur.rowcount > 0

    def upsert_position(
        self,
        symbol: str,
        asset: int,
        position_sz: str,
        entry_px: Optional[str],
        unrealized_pnl: Optional[str],
        margin_used: Optional[str],
        leverage: Optional[str],
        raw_json: str,
    ) -> None:
        self.conn.execute("""
        INSERT INTO positions (symbol, asset, position_sz, entry_px, unrealized_pnl, margin_used, leverage, last_update_ts, raw_json)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(symbol) DO UPDATE SET
            asset=excluded.asset,
            position_sz=excluded.position_sz,
            entry_px=excluded.entry_px,
            unrealized_pnl=excluded.unrealized_pnl,
            margin_used=excluded.margin_used,
            leverage=excluded.leverage,
            last_update_ts=excluded.last_update_ts,
            raw_json=excluded.raw_json
        """, (symbol, asset, position_sz, entry_px, unrealized_pnl, margin_used, leverage, now_ms(), raw_json))
        self.conn.commit()

    def daily_realized_pnl(self, date_str: Optional[str] = None) -> Decimal:
        target = date_str or today_utc()
        start = int(dt.datetime.strptime(target, "%Y-%m-%d").replace(tzinfo=dt.timezone.utc).timestamp() * 1000)
        end = start + 24 * 60 * 60 * 1000
        row = self.conn.execute("""
        SELECT COALESCE(SUM(CAST(COALESCE(closed_pnl, '0') AS REAL)), 0.0) AS pnl
        FROM fills WHERE fill_ts >= ? AND fill_ts < ?
        """, (start, end)).fetchone()
        return Decimal(str(row["pnl"] or 0.0))

    def total_fees(self) -> Decimal:
        row = self.conn.execute("""
        SELECT COALESCE(SUM(CAST(COALESCE(fee, '0') AS REAL)), 0.0) AS fees
        FROM fills
        """).fetchone()
        return Decimal(str(row["fees"] or 0.0))

    def current_position_size(self, symbol: str) -> Decimal:
        row = self.conn.execute("SELECT position_sz FROM positions WHERE symbol = ?", (symbol,)).fetchone()
        if not row:
            return Decimal("0")
        return Decimal(str(row["position_sz"]))

    def close(self) -> None:
        self.conn.close()


# ============================================================================
# Public reads + official SDK trading
# ============================================================================

class HL:
    def __init__(self, cfg: Config):
        self.cfg = cfg
        self.wallet: Optional[LocalAccount] = Account.from_key(cfg.secret_key) if cfg.secret_key else None
        self.info = Info(cfg.base_url, skip_ws=True)
        self.exchange: Optional[Exchange] = None
        if self.wallet:
            self.exchange = Exchange(
                wallet=self.wallet,
                base_url=cfg.base_url,
                account_address=cfg.account_address,
            )

    def all_mids(self) -> Dict[str, str]:
        return self.info.all_mids()

    def open_orders(self) -> List[Dict[str, Any]]:
        try:
            return self.info.open_orders(self.cfg.account_address)
        except Exception:
            return self.info.frontend_open_orders(self.cfg.account_address)

    def user_fills(self) -> List[Dict[str, Any]]:
        return self.info.user_fills(self.cfg.account_address)

    def user_state(self) -> Dict[str, Any]:
        return self.info.user_state(self.cfg.account_address)

    def meta(self) -> Dict[str, Any]:
        # Fallback to raw call if needed by SDK version
        try:
            return self.info.meta()
        except Exception:
            r = requests.post(
                f"{self.cfg.base_url}/info",
                json={"type": "meta"},
                timeout=15,
            )
            r.raise_for_status()
            return r.json()

    def update_leverage(self, leverage: int, coin: str) -> Any:
        if self.exchange is None:
            raise RuntimeError("Exchange not initialized")
        return self.exchange.update_leverage(leverage, coin, is_cross=True)

    def schedule_cancel(self, target_ms: int) -> Any:
        if self.exchange is None:
            raise RuntimeError("Exchange not initialized")
        return self.exchange.schedule_cancel(target_ms)

    def place_limit(self, coin: str, is_buy: bool, sz: float, px: float, reduce_only: bool, cloid: str) -> Any:
        if self.exchange is None:
            raise RuntimeError("Exchange not initialized")
        return self.exchange.order(
            coin,
            is_buy,
            sz,
            px,
            {"limit": {"tif": "Alo"}},
            reduce_only=reduce_only,
            cloid=cloid,
        )

    def cancel_oid(self, coin: str, oid: int) -> Any:
        if self.exchange is None:
            raise RuntimeError("Exchange not initialized")
        return self.exchange.cancel(coin, oid)


# ============================================================================
# Metadata
# ============================================================================

@dataclass
class SymbolMeta:
    symbol: str
    asset: int
    size_decimals: int
    price_decimals: int
    max_leverage: Optional[int]
    raw: Dict[str, Any]


class MetadataResolver:
    def __init__(self, hl: HL):
        self.hl = hl
        self._symbols: Dict[str, SymbolMeta] = {}

    def refresh(self) -> None:
        meta = self.hl.meta()
        universe = meta.get("universe") or []
        out: Dict[str, SymbolMeta] = {}

        for idx, item in enumerate(universe):
            name = str(item.get("name", "")).upper()
            if not name:
                continue
            size_decimals = int(item.get("szDecimals", 0))
            price_decimals = int(item.get("pxDecimals", item.get("priceDecimals", 2)))
            max_leverage = item.get("maxLeverage")
            try:
                max_leverage = int(max_leverage) if max_leverage is not None else None
            except Exception:
                max_leverage = None

            out[name] = SymbolMeta(
                symbol=name,
                asset=idx,
                size_decimals=size_decimals,
                price_decimals=price_decimals,
                max_leverage=max_leverage,
                raw=item,
            )

        self._symbols = out

    def symbol_meta(self, symbol: str) -> SymbolMeta:
        s = symbol.upper()
        if s not in self._symbols:
            raise KeyError(f"Symbol not found in live metadata: {s}")
        return self._symbols[s]


# ============================================================================
# LLM
# ============================================================================

SYSTEM_PROMPT = """
You are a Hyperliquid perp trading planner.
Return strict JSON only.

Allowed decisions:
- do_nothing
- place_limit_buy
- place_limit_sell
- cancel_order
- modify_order
- schedule_cancel_all

Rules:
- prefer passive orders (Alo) when possible
- never exceed max_order_usd
- if data quality is weak, choose do_nothing
- do not invent balances
- use one symbol from the provided state
"""

def groq_client(api_key: str) -> OpenAI:
    return OpenAI(api_key=api_key, base_url="https://api.groq.com/openai/v1")


def openrouter_chat(api_key: str, messages: List[Dict[str, str]], model: str) -> Dict[str, Any]:
    r = requests.post(
        "https://openrouter.ai/api/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json={"model": model, "messages": messages},
        timeout=20,
    )
    r.raise_for_status()
    return r.json()


def build_llm_messages(state: Dict[str, Any]) -> List[Dict[str, str]]:
    user = f"""
Return JSON with this shape:
{{
  "decision": "do_nothing|place_limit_buy|place_limit_sell|cancel_order|modify_order|schedule_cancel_all",
  "symbol": "{state['symbol']}",
  "confidence": 0.0,
  "rationale": "text",
  "action_payload": {{
    "price": 0,
    "size_usd": 0,
    "reduce_only": false,
    "oid": null,
    "cloid": null,
    "time": null
  }}
}}

State:
{json.dumps(state, ensure_ascii=False)}
"""
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user},
    ]


def ask_llm(cfg: Config, state: Dict[str, Any]) -> Dict[str, Any]:
    if cfg.llm_provider == "none":
        return {"decision": "do_nothing", "symbol": state["symbol"], "confidence": 0.0, "rationale": "llm disabled", "action_payload": {}}

    messages = build_llm_messages(state)

    if cfg.llm_provider == "groq":
        client = groq_client(cfg.groq_api_key)
        resp = client.chat.completions.create(
            model=cfg.groq_model,
            temperature=0.2,
            response_format={"type": "json_object"},
            messages=messages,
        )
        return json.loads(resp.choices[0].message.content)

    if cfg.llm_provider == "openrouter":
        resp = openrouter_chat(cfg.openrouter_api_key, messages, cfg.openrouter_model)
        return json.loads(resp["choices"][0]["message"]["content"])

    # both
    try:
        client = groq_client(cfg.groq_api_key)
        resp = client.chat.completions.create(
            model=cfg.groq_model,
            temperature=0.2,
            response_format={"type": "json_object"},
            messages=messages,
        )
        return json.loads(resp.choices[0].message.content)
    except Exception:
        resp = openrouter_chat(cfg.openrouter_api_key, messages, cfg.openrouter_model)
        return json.loads(resp["choices"][0]["message"]["content"])


# ============================================================================
# Risk
# ============================================================================

class RiskHalt(Exception):
    pass


class RiskEngine:
    def __init__(self, cfg: Config, db: StateDB, logger: JsonlLogger):
        self.cfg = cfg
        self.db = db
        self.logger = logger

    def check(self, intended_order_usd: Decimal, current_mid: Decimal, current_position_sz: Decimal) -> None:
        daily_realized = self.db.daily_realized_pnl()
        if daily_realized <= -self.cfg.max_daily_realized_loss:
            self.logger.error("risk_block", reason="max_daily_realized_loss", daily_realized=decimal_to_str(daily_realized))
            raise RiskHalt("max daily realized loss breached")

        local_open = self.db.get_open_local_orders()
        if len(local_open) >= self.cfg.max_open_orders:
            self.logger.error("risk_block", reason="max_open_orders", open_orders=len(local_open))
            raise RiskHalt("max open orders breached")

        minute_bucket = now_s() // 60
        k = f"notional_minute_{minute_bucket}"
        used = to_decimal(self.db.get_kv(k, "0"))
        if used + intended_order_usd > self.cfg.max_notional_per_min:
            self.logger.error("risk_block", reason="max_notional_per_min", used=decimal_to_str(used), intended=decimal_to_str(intended_order_usd))
            raise RiskHalt("max notional per minute breached")

        current_abs_usd = abs(current_position_sz) * current_mid
        if current_abs_usd + intended_order_usd > self.cfg.max_position_usd:
            self.logger.error("risk_block", reason="max_position_usd", current_abs_usd=decimal_to_str(current_abs_usd), intended=decimal_to_str(intended_order_usd))
            raise RiskHalt("max position usd breached")

    def mark_notional(self, usd: Decimal) -> None:
        minute_bucket = now_s() // 60
        k = f"notional_minute_{minute_bucket}"
        used = to_decimal(self.db.get_kv(k, "0"))
        self.db.set_kv(k, decimal_to_str(used + usd))


# ============================================================================
# Engine
# ============================================================================

class TradingEngine:
    def __init__(self, cfg: Config):
        self.cfg = cfg
        self.log = JsonlLogger(cfg.log_file)
        self.db = StateDB(cfg.db_file)
        self.hl = HL(cfg)
        self.meta = MetadataResolver(self.hl)
        self.risk = RiskEngine(cfg, self.db, self.log)
        self.symbol_meta: Optional[SymbolMeta] = None
        self.halted = False
        self.api_failures = 0

    def validate_startup(self) -> None:
        self.cfg.validate()
        self.meta.refresh()
        self.symbol_meta = self.meta.symbol_meta(self.cfg.symbol)
        mids = self.hl.all_mids()
        if self.cfg.symbol not in mids:
            raise RuntimeError(f"Symbol {self.cfg.symbol} not found in allMids")

        if not self.cfg.dry_run:
            self.hl.update_leverage(min(3, self.symbol_meta.max_leverage or 3), self.cfg.symbol)

        self.log.info(
            "startup_ok",
            symbol=self.cfg.symbol,
            asset=self.symbol_meta.asset,
            dry_run=self.cfg.dry_run,
            enable_live=self.cfg.enable_live,
            account_address=self.cfg.account_address,
            signer_address=self.hl.wallet.address.lower() if self.hl.wallet else "",
        )

    # ---------- state builders ----------

    def get_mid(self, symbol: str) -> Decimal:
        mids = self.hl.all_mids()
        val = mids.get(symbol)
        if val is None:
            raise RuntimeError(f"No mid for {symbol}")
        return Decimal(str(val))

    def build_state(self) -> Dict[str, Any]:
        symbol = self.cfg.symbol
        mid = self.get_mid(symbol)
        open_orders = self.hl.open_orders()
        fills = self.hl.user_fills()
        pos = self.db.current_position_size(symbol)

        return {
            "timestamp_ms": now_ms(),
            "symbol": symbol,
            "mid": float(mid),
            "position_size": float(pos),
            "open_orders": open_orders[:50],
            "recent_fills": fills[-50:] if isinstance(fills, list) else fills,
            "risk_limits": {
                "max_order_usd": float(self.cfg.max_order_usd),
                "max_position_usd": float(self.cfg.max_position_usd),
                "max_spread_bps": float(self.cfg.max_spread_bps),
                "min_confidence": self.cfg.min_confidence,
                "max_confidence": self.cfg.max_confidence,
                "dry_run": self.cfg.dry_run,
            },
        }

    # ---------- fills / positions ----------

    def ingest_fills(self) -> int:
        fills = self.hl.user_fills()
        inserted = 0

        for fill in fills[:500]:
            fill_id = str(fill.get("tid") or fill.get("tradeId") or fill.get("hash") or fill.get("fillId") or fill.get("id") or uuid.uuid4().hex)
            oid = fill.get("oid")
            symbol = str(fill.get("coin", self.cfg.symbol)).upper()
            side = fill.get("side")
            px = str(fill.get("px", "0"))
            sz = str(fill.get("sz", "0"))
            fee = str(fill.get("fee", "0"))
            closed_pnl = str(fill.get("closedPnl", "0"))
            fill_ts = int(fill.get("time") or fill.get("ts") or fill.get("timestamp") or now_ms())

            if self.db.insert_fill(
                fill_id=fill_id,
                oid=str(oid) if oid is not None else None,
                symbol=symbol,
                side=str(side) if side is not None else None,
                px=px,
                sz=sz,
                fee=fee,
                closed_pnl=closed_pnl,
                fill_ts=fill_ts,
                raw_json=safe_json_dumps(fill),
            ):
                inserted += 1
        if inserted:
            self.log.info("fills_ingested", inserted=inserted)
        return inserted

    def ingest_positions(self) -> None:
        sm = self.symbol_meta
        if sm is None:
            raise RuntimeError("symbol_meta missing")

        user_state = self.hl.user_state()
        positions = user_state.get("assetPositions") or []
        found = False

        for ap in positions:
            pos = ap.get("position") if isinstance(ap, dict) else None
            if not isinstance(pos, dict):
                continue
            coin = str(pos.get("coin", "")).upper()
            if coin != self.cfg.symbol:
                continue
            found = True
            self.db.upsert_position(
                symbol=self.cfg.symbol,
                asset=sm.asset,
                position_sz=str(pos.get("szi", "0")),
                entry_px=str(pos.get("entryPx")) if pos.get("entryPx") is not None else None,
                unrealized_pnl=str(pos.get("unrealizedPnl")) if pos.get("unrealizedPnl") is not None else None,
                margin_used=str(pos.get("marginUsed")) if pos.get("marginUsed") is not None else None,
                leverage=str((pos.get("leverage") or {}).get("value")) if isinstance(pos.get("leverage"), dict) else None,
                raw_json=safe_json_dumps(pos),
            )
        if not found:
            self.db.upsert_position(
                symbol=self.cfg.symbol,
                asset=sm.asset,
                position_sz="0",
                entry_px=None,
                unrealized_pnl=None,
                margin_used=None,
                leverage=None,
                raw_json="{}",
            )

    # ---------- reconciliation ----------

    def reconcile_orders(self) -> None:
        exchange_open = self.hl.open_orders()
        local_open = self.db.get_open_local_orders()

        exchange_oids = {str(x.get("oid")) for x in exchange_open if isinstance(x, dict) and x.get("oid") is not None}
        local_oids = {str(r["oid"]) for r in local_open if not str(r["oid"]).startswith("pending-")}

        for oid in sorted(local_oids - exchange_oids):
            self.db.update_order_status(oid, "unknown")
            self.log.warning("reconcile_order_missing_on_exchange", oid=oid)

        for oid in sorted(exchange_oids & local_oids):
            self.db.update_order_status(oid, "resting")

    def cancel_stale_orders(self) -> None:
        cutoff_ms = now_ms() - self.cfg.stale_order_cancel_sec * 1000
        stale = self.db.get_resting_local_orders_older_than(cutoff_ms)

        for row in stale:
            oid = str(row["oid"])
            try:
                self.cancel_by_oid(oid)
                self.log.info("stale_order_canceled", oid=oid)
            except Exception as e:
                self.log.error("stale_order_cancel_error", oid=oid, error=str(e))

    def arm_deadman(self) -> None:
        last_arm = int(self.db.get_kv("last_deadman_arm_ms", "0") or "0")
        if now_ms() - last_arm < max(1000, (self.cfg.cancel_all_arm_sec * 1000) // 2):
            return

        if self.cfg.dry_run:
            self.db.set_kv("last_deadman_arm_ms", str(now_ms()))
            self.log.info("deadman_armed_dry_run", timeout_sec=self.cfg.cancel_all_arm_sec)
            return

        target_ms = now_ms() + self.cfg.cancel_all_arm_sec * 1000
        resp = self.hl.schedule_cancel(target_ms)
        self.db.set_kv("last_deadman_arm_ms", str(now_ms()))
        self.log.info("deadman_armed", timeout_sec=self.cfg.cancel_all_arm_sec, response=resp)

    def full_reconcile(self) -> None:
        self.ingest_fills()
        self.ingest_positions()
        self.reconcile_orders()
        self.cancel_stale_orders()

    # ---------- execution ----------

    def parse_order_response(self, resp: Any) -> Tuple[Optional[str], str, Optional[str]]:
        if not isinstance(resp, dict):
            return None, "unknown", f"unexpected_response_type:{type(resp).__name__}"

        data = resp.get("response", {}).get("data", {})
        statuses = data.get("statuses", []) if isinstance(data, dict) else []
        if not statuses:
            return None, "unknown", "missing_statuses"

        st0 = statuses[0]
        if not isinstance(st0, dict):
            return None, "unknown", "invalid_status_object"

        if "resting" in st0 and isinstance(st0["resting"], dict):
            return str(st0["resting"].get("oid")), "resting", None
        if "filled" in st0 and isinstance(st0["filled"], dict):
            oid = st0["filled"].get("oid")
            return (str(oid) if oid is not None else None), "filled", None
        if "error" in st0:
            return None, "rejected", str(st0["error"])
        return None, "unknown", safe_json_dumps(st0)

    def place_limit(self, side: str, price: Decimal, size: Decimal, reduce_only: bool = False) -> Optional[str]:
        sm = self.symbol_meta
        if sm is None:
            raise RuntimeError("symbol_meta missing")

        side = side.lower()
        is_buy = side == "buy"
        cloid = new_cloid()
        price_f = float(quantize_down(price, sm.price_decimals))
        size_f = float(quantize_down(size, sm.size_decimals))
        order_usd = Decimal(str(price_f)) * Decimal(str(size_f))

        mid = self.get_mid(self.cfg.symbol)
        pos = self.db.current_position_size(self.cfg.symbol)
        self.risk.check(order_usd, mid, pos)

        if self.cfg.dry_run:
            oid = f"dry-{uuid.uuid4().hex[:10]}"
            self.db.upsert_order(
                oid=oid,
                cloid=cloid,
                symbol=self.cfg.symbol,
                asset=sm.asset,
                side=side,
                limit_px=str(price_f),
                size=str(size_f),
                tif="Alo",
                reduce_only=1 if reduce_only else 0,
                status="resting",
                raw_response_json=safe_json_dumps({"dry_run": True}),
                error_text=None,
            )
            self.risk.mark_notional(order_usd)
            self.log.info("order_submit_dry_run", oid=oid, cloid=cloid, side=side, px=price_f, sz=size_f, reduce_only=reduce_only)
            return oid

        resp = self.hl.place_limit(
            coin=self.cfg.symbol,
            is_buy=is_buy,
            sz=size_f,
            px=price_f,
            reduce_only=reduce_only,
            cloid=cloid,
        )

        oid, status, error_text = self.parse_order_response(resp)
        oid = oid or f"pending-{uuid.uuid4().hex[:10]}"

        self.db.upsert_order(
            oid=oid,
            cloid=cloid,
            symbol=self.cfg.symbol,
            asset=sm.asset,
            side=side,
            limit_px=str(price_f),
            size=str(size_f),
            tif="Alo",
            reduce_only=1 if reduce_only else 0,
            status=status,
            raw_response_json=safe_json_dumps(resp),
            error_text=error_text,
        )
        self.risk.mark_notional(order_usd)
        self.log.info("order_submit_result", oid=oid, cloid=cloid, side=side, px=price_f, sz=size_f, status=status, error_text=error_text)
        return oid

    def cancel_by_oid(self, oid: str) -> Dict[str, Any]:
        if self.cfg.dry_run:
            self.db.update_order_status(oid, "canceled", safe_json_dumps({"dry_run": True}), None)
            return {"dry_run": True, "oid": oid}

        resp = self.hl.cancel_oid(self.cfg.symbol, int(oid))
        self.db.update_order_status(oid, "canceled", safe_json_dumps(resp), None)
        return resp

    def cancel_by_cloid(self, cloid: str) -> Dict[str, Any]:
        row = self.db.get_order_by_cloid(cloid)
        if row:
            return self.cancel_by_oid(str(row["oid"]))

        for o in self.hl.open_orders():
            if str(o.get("cloid", "")) == cloid and o.get("oid") is not None:
                return self.cancel_by_oid(str(o["oid"]))

        raise RuntimeError(f"No active order found for cloid={cloid}")

    def modify_order(self, oid_or_cloid: str, side: str, price: Decimal, size: Decimal, reduce_only: bool = False) -> Optional[str]:
        # Safe compatibility path: cancel then replace.
        if str(oid_or_cloid).startswith("0x"):
            self.cancel_by_cloid(str(oid_or_cloid))
        else:
            self.cancel_by_oid(str(oid_or_cloid))
        return self.place_limit(side=side, price=price, size=size, reduce_only=reduce_only)

    # ---------- risk gate for LLM plan ----------

    def risk_gate(self, plan: Dict[str, Any]) -> Tuple[bool, str]:
        decision = str(plan.get("decision", "do_nothing"))
        if decision == "do_nothing":
            return False, "no trade"

        confidence = float(plan.get("confidence", 0) or 0)
        if confidence < self.cfg.min_confidence or confidence > self.cfg.max_confidence:
            return False, "confidence outside allowed range"

        if str(plan.get("symbol", "")).upper() != self.cfg.symbol:
            return False, "symbol mismatch"

        state = self.build_state()
        mid = to_decimal(state["mid"], "0")
        if mid <= 0:
            return False, "missing mid"

        payload = plan.get("action_payload", {}) or {}
        if decision in {"place_limit_buy", "place_limit_sell"}:
            size_usd = to_decimal(payload.get("size_usd", 0), "0")
            if size_usd <= 0:
                return False, "size_usd missing"
            if size_usd > self.cfg.max_order_usd:
                return False, "size_usd too large"

            px = to_decimal(payload.get("price", state["mid"]), "0")
            spread = bps(px, mid)
            if spread > self.cfg.max_spread_bps:
                return False, f"planner price too far from mid ({decimal_to_str(spread)} bps)"

        return True, "passed"

    # ---------- strategy / planner ----------

    def fallback_decision(self) -> Optional[Dict[str, Any]]:
        sm = self.symbol_meta
        if sm is None:
            raise RuntimeError("symbol_meta missing")

        mid = self.get_mid(self.cfg.symbol)
        pos_sz = self.db.current_position_size(self.cfg.symbol)

        if pos_sz * mid >= self.cfg.max_position_usd * Decimal("0.75"):
            return None

        size_usd = self.cfg.max_order_usd
        raw_sz = size_usd / mid
        sz = quantize_down(raw_sz, sm.size_decimals)
        px = quantize_down(mid * Decimal("0.999"), sm.price_decimals)

        if sz <= 0 or px <= 0:
            return None

        return {
            "decision": "place_limit_buy",
            "symbol": self.cfg.symbol,
            "confidence": 0.61,
            "rationale": "fallback passive bid below mid",
            "action_payload": {
                "price": float(px),
                "size_usd": float(size_usd),
                "reduce_only": False,
            },
        }

    def execute_plan(self, plan: Dict[str, Any]) -> None:
        decision = str(plan.get("decision", "do_nothing"))
        payload = plan.get("action_payload", {}) or {}
        sm = self.symbol_meta
        if sm is None:
            raise RuntimeError("symbol_meta missing")

        if decision == "do_nothing":
            self.log.info("plan_no_action", plan=plan)
            return

        if decision in {"place_limit_buy", "place_limit_sell"}:
            mid = self.get_mid(self.cfg.symbol)
            side = "buy" if decision == "place_limit_buy" else "sell"
            px = to_decimal(payload.get("price", mid), str(mid))
            size_usd = to_decimal(payload.get("size_usd", self.cfg.max_order_usd), str(self.cfg.max_order_usd))
            sz = quantize_down(size_usd / px, sm.size_decimals)
            self.place_limit(side=side, price=px, size=sz, reduce_only=bool(payload.get("reduce_only", False)))
            return

        if decision == "cancel_order":
            if payload.get("oid") is not None:
                self.cancel_by_oid(str(payload["oid"]))
                return
            if payload.get("cloid") is not None:
                self.cancel_by_cloid(str(payload["cloid"]))
                return
            raise RuntimeError("cancel_order requested but neither oid nor cloid provided")

        if decision == "modify_order":
            ref = payload.get("oid") or payload.get("cloid")
            if ref is None:
                raise RuntimeError("modify_order requires oid or cloid")
            px = to_decimal(payload.get("price"), "0")
            size_usd = to_decimal(payload.get("size_usd", self.cfg.max_order_usd), str(self.cfg.max_order_usd))
            if px <= 0:
                px = self.get_mid(self.cfg.symbol)
            sz = quantize_down(size_usd / px, sm.size_decimals)
            side = str(payload.get("side", "buy")).lower()
            self.modify_order(str(ref), side, px, sz, reduce_only=bool(payload.get("reduce_only", False)))
            return

        if decision == "schedule_cancel_all":
            self.arm_deadman()
            return

        raise RuntimeError(f"Unsupported decision: {decision}")

    # ---------- loop ----------

    def health_snapshot(self) -> Dict[str, Any]:
        return {
            "ts": utc_now_iso(),
            "symbol": self.cfg.symbol,
            "dry_run": self.cfg.dry_run,
            "halted": self.halted,
            "api_failures": self.api_failures,
            "daily_realized_pnl": decimal_to_str(self.db.daily_realized_pnl()),
            "total_fees": decimal_to_str(self.db.total_fees()),
            "current_position_sz": decimal_to_str(self.db.current_position_size(self.cfg.symbol)),
            "open_local_orders": len(self.db.get_open_local_orders()),
        }

    def run_once(self) -> None:
        self.arm_deadman()
        self.full_reconcile()

        state = self.build_state()
        try:
            plan = ask_llm(self.cfg, state)
        except Exception as e:
            self.log.warning("llm_error_fallback", error=str(e))
            plan = self.fallback_decision() or {"decision": "do_nothing", "symbol": self.cfg.symbol, "confidence": 0.0, "rationale": "fallback none", "action_payload": {}}

        self.log.info("planner_output", plan=plan)
        approved, reason = self.risk_gate(plan)
        if not approved:
            self.log.info("plan_rejected", reason=reason, health=self.health_snapshot())
            return

        self.execute_plan(plan)
        self.log.info("loop_ok", health=self.health_snapshot())

    def run_forever(self) -> None:
        self.validate_startup()
        print(f"Running Hyperliquid LLM trader for {self.cfg.symbol} | dry_run={self.cfg.dry_run}")

        while True:
            try:
                if self.halted:
                    self.log.warning("engine_halted_sleeping", health=self.health_snapshot())
                    time.sleep(self.cfg.loop_interval_sec)
                    continue

                self.run_once()
                self.api_failures = 0
                time.sleep(self.cfg.loop_interval_sec)

            except RiskHalt as e:
                self.log.error("risk_halt", error=str(e), health=self.health_snapshot())
                self.halted = True
                time.sleep(self.cfg.loop_interval_sec)

            except (requests.RequestException, RuntimeError) as e:
                self.api_failures += 1
                self.log.error("runtime_error", error=str(e), failures=self.api_failures, traceback=traceback.format_exc())
                if self.api_failures >= 5:
                    self.halted = True
                    self.log.error("api_failure_halt", failures=self.api_failures)
                time.sleep(min(5, self.cfg.loop_interval_sec + 1))

            except KeyboardInterrupt:
                self.log.info("shutdown_keyboard_interrupt")
                break

            except Exception as e:
                self.log.error("loop_error", error=str(e), traceback=traceback.format_exc())
                time.sleep(min(5, self.cfg.loop_interval_sec + 1))


# ============================================================================
# Main
# ============================================================================

def main() -> None:
    cfg = Config.from_env()
    engine = TradingEngine(cfg)
    engine.run_forever()


if __name__ == "__main__":
    main()