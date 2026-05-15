#!/usr/bin/env python3
"""
Marinade Native Stake Tracker
-----------------------------

What this does:
- Fetches all native stake wallets from Marinade Snapshot API
- Saves repeated snapshots to SQLite
- Tracks SOL/USD price
- Computes wallet growth rates and ROI over multiple windows
- Exposes CLI commands for collection and ranking

Usage examples:
    python marinade_tracker.py init-db
    python marinade_tracker.py collect-once
    python marinade_tracker.py daemon --interval 3600
    python marinade_tracker.py leaderboard --window 1d --limit 25
    python marinade_tracker.py wallet <PUBKEY>
    python marinade_tracker.py stats

Environment variables:
    MARINADE_NS_ALL_URL
    SOL_PRICE_URL
    DB_PATH

Defaults:
    MARINADE_NS_ALL_URL=https://snapshots-api.marinade.finance/v1/stakers/ns/all
    SOL_PRICE_URL=https://api.coingecko.com/api/v3/simple/price?ids=solana&vs_currencies=usd
    DB_PATH=marinade_tracker.db
"""

from __future__ import annotations

import argparse
import dataclasses
import datetime as dt
import json
import logging
import math
import os
import sqlite3
import sys
import threading
import time
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Tuple

import requests


# ============================================================
# Config
# ============================================================

MARINADE_NS_ALL_URL = os.getenv(
    "MARINADE_NS_ALL_URL",
    "https://snapshots-api.marinade.finance/v1/stakers/ns/all",
)
SOL_PRICE_URL = os.getenv(
    "SOL_PRICE_URL",
    "https://api.coingecko.com/api/v3/simple/price?ids=solana&vs_currencies=usd",
)
DB_PATH = os.getenv("DB_PATH", "marinade_tracker.db")

HTTP_TIMEOUT = 30
DEFAULT_INTERVAL_SECONDS = 3600
MAX_PRICE_AGE_SECONDS = 6 * 3600

WINDOWS = {
    "1h": 3600,
    "6h": 6 * 3600,
    "12h": 12 * 3600,
    "1d": 86400,
    "7d": 7 * 86400,
    "30d": 30 * 86400,
    "90d": 90 * 86400,
    "365d": 365 * 86400,
}

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)
log = logging.getLogger("marinade-tracker")


# ============================================================
# Models
# ============================================================

@dataclass
class WalletSnapshot:
    snapshot_run_at: str
    wallet: str
    amount_sol: float
    source_created_at: Optional[str] = None

@dataclass
class PriceSnapshot:
    snapshot_run_at: str
    sol_usd: float
    source: str = "coingecko"

@dataclass
class WalletMetrics:
    wallet: str
    current_amount_sol: float
    current_value_usd: Optional[float]
    delta_sol: float
    delta_usd: Optional[float]
    seconds_between: float
    sol_per_second: float
    usd_per_second: Optional[float]
    cents_per_second: Optional[float]
    roi_pct: Optional[float]
    from_snapshot: str
    to_snapshot: str


# ============================================================
# Helpers
# ============================================================

def utc_now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)

def utc_now_iso() -> str:
    return utc_now().isoformat()

def parse_iso(value: str) -> dt.datetime:
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"
    return dt.datetime.fromisoformat(value)

def safe_float(x: Any, default: float = 0.0) -> float:
    try:
        if x is None:
            return default
        return float(x)
    except Exception:
        return default

def safe_div(a: float, b: float) -> float:
    if b == 0:
        return 0.0
    return a / b

def fmt_money(x: Optional[float]) -> str:
    if x is None:
        return "n/a"
    return f"${x:,.6f}"

def fmt_pct(x: Optional[float]) -> str:
    if x is None:
        return "n/a"
    return f"{x:.6f}%"

def nearest_record_before_or_at(
    records: List[Tuple[str, float]],
    target_time: dt.datetime,
) -> Optional[Tuple[str, float]]:
    """
    records: sorted ascending by snapshot_run_at
    returns latest record <= target_time
    """
    best = None
    for ts_str, amt in records:
        ts = parse_iso(ts_str)
        if ts <= target_time:
            best = (ts_str, amt)
        else:
            break
    return best


# ============================================================
# Database
# ============================================================

class Database:
    def __init__(self, path: str = DB_PATH):
        self.path = path

    def connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        return conn

    def init_db(self) -> None:
        with self.connect() as conn:
            conn.executescript(
                """
                PRAGMA journal_mode=WAL;

                CREATE TABLE IF NOT EXISTS snapshot_runs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    snapshot_run_at TEXT NOT NULL UNIQUE,
                    wallet_count INTEGER DEFAULT 0,
                    notes TEXT
                );

                CREATE TABLE IF NOT EXISTS wallet_snapshots (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    snapshot_run_at TEXT NOT NULL,
                    wallet TEXT NOT NULL,
                    amount_sol REAL NOT NULL,
                    source_created_at TEXT,
                    UNIQUE(snapshot_run_at, wallet)
                );

                CREATE INDEX IF NOT EXISTS idx_wallet_snapshots_wallet
                ON wallet_snapshots(wallet);

                CREATE INDEX IF NOT EXISTS idx_wallet_snapshots_run
                ON wallet_snapshots(snapshot_run_at);

                CREATE TABLE IF NOT EXISTS price_snapshots (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    snapshot_run_at TEXT NOT NULL UNIQUE,
                    sol_usd REAL NOT NULL,
                    source TEXT NOT NULL
                );
                """
            )
        log.info("database initialized: %s", self.path)

    def insert_snapshot_run(self, snapshot_run_at: str, wallet_count: int, notes: str = "") -> None:
        with self.connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO snapshot_runs (snapshot_run_at, wallet_count, notes)
                VALUES (?, ?, ?)
                """,
                (snapshot_run_at, wallet_count, notes),
            )

    def insert_wallet_snapshots(self, snapshots: Iterable[WalletSnapshot]) -> int:
        rows = [
            (s.snapshot_run_at, s.wallet, s.amount_sol, s.source_created_at)
            for s in snapshots
        ]
        with self.connect() as conn:
            conn.executemany(
                """
                INSERT OR REPLACE INTO wallet_snapshots
                (snapshot_run_at, wallet, amount_sol, source_created_at)
                VALUES (?, ?, ?, ?)
                """,
                rows,
            )
        return len(rows)

    def insert_price_snapshot(self, ps: PriceSnapshot) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO price_snapshots
                (snapshot_run_at, sol_usd, source)
                VALUES (?, ?, ?)
                """,
                (ps.snapshot_run_at, ps.sol_usd, ps.source),
            )

    def latest_snapshot_run(self) -> Optional[str]:
        with self.connect() as conn:
            row = conn.execute(
                """
                SELECT snapshot_run_at
                FROM snapshot_runs
                ORDER BY snapshot_run_at DESC
                LIMIT 1
                """
            ).fetchone()
            return row["snapshot_run_at"] if row else None

    def latest_price(self) -> Optional[PriceSnapshot]:
        with self.connect() as conn:
            row = conn.execute(
                """
                SELECT snapshot_run_at, sol_usd, source
                FROM price_snapshots
                ORDER BY snapshot_run_at DESC
                LIMIT 1
                """
            ).fetchone()
            if not row:
                return None
            return PriceSnapshot(
                snapshot_run_at=row["snapshot_run_at"],
                sol_usd=row["sol_usd"],
                source=row["source"],
            )

    def all_wallets_in_latest_run(self) -> List[str]:
        latest = self.latest_snapshot_run()
        if not latest:
            return []
        with self.connect() as conn:
            rows = conn.execute(
                """
                SELECT wallet
                FROM wallet_snapshots
                WHERE snapshot_run_at = ?
                ORDER BY wallet ASC
                """,
                (latest,),
            ).fetchall()
            return [r["wallet"] for r in rows]

    def wallet_history(self, wallet: str) -> List[Tuple[str, float]]:
        with self.connect() as conn:
            rows = conn.execute(
                """
                SELECT snapshot_run_at, amount_sol
                FROM wallet_snapshots
                WHERE wallet = ?
                ORDER BY snapshot_run_at ASC
                """,
                (wallet,),
            ).fetchall()
            return [(r["snapshot_run_at"], r["amount_sol"]) for r in rows]

    def latest_wallet_amounts(self) -> List[Tuple[str, str, float]]:
        latest = self.latest_snapshot_run()
        if not latest:
            return []
        with self.connect() as conn:
            rows = conn.execute(
                """
                SELECT wallet, snapshot_run_at, amount_sol
                FROM wallet_snapshots
                WHERE snapshot_run_at = ?
                ORDER BY amount_sol DESC
                """,
                (latest,),
            ).fetchall()
            return [(r["wallet"], r["snapshot_run_at"], r["amount_sol"]) for r in rows]

    def count_wallets(self) -> int:
        latest = self.latest_snapshot_run()
        if not latest:
            return 0
        with self.connect() as conn:
            row = conn.execute(
                """
                SELECT COUNT(*) AS c
                FROM wallet_snapshots
                WHERE snapshot_run_at = ?
                """,
                (latest,),
            ).fetchone()
            return int(row["c"])

    def run_count(self) -> int:
        with self.connect() as conn:
            row = conn.execute("SELECT COUNT(*) AS c FROM snapshot_runs").fetchone()
            return int(row["c"])

    def prune_old_runs(self, keep_last_n_runs: int) -> None:
        with self.connect() as conn:
            rows = conn.execute(
                """
                SELECT snapshot_run_at
                FROM snapshot_runs
                ORDER BY snapshot_run_at DESC
                LIMIT -1 OFFSET ?
                """,
                (keep_last_n_runs,),
            ).fetchall()
            old_runs = [r["snapshot_run_at"] for r in rows]
            if not old_runs:
                return
            conn.executemany(
                "DELETE FROM wallet_snapshots WHERE snapshot_run_at = ?",
                [(r,) for r in old_runs],
            )
            conn.executemany(
                "DELETE FROM price_snapshots WHERE snapshot_run_at = ?",
                [(r,) for r in old_runs],
            )
            conn.executemany(
                "DELETE FROM snapshot_runs WHERE snapshot_run_at = ?",
                [(r,) for r in old_runs],
            )
        log.info("pruned old runs, kept last %d", keep_last_n_runs)


# ============================================================
# API client
# ============================================================

class MarinadeClient:
    def __init__(self, ns_all_url: str = MARINADE_NS_ALL_URL, timeout: int = HTTP_TIMEOUT):
        self.ns_all_url = ns_all_url
        self.timeout = timeout
        self.session = requests.Session()

    def fetch_ns_all(self) -> Any:
        log.info("fetching Marinade native stake snapshot: %s", self.ns_all_url)
        resp = self.session.get(self.ns_all_url, timeout=self.timeout)
        resp.raise_for_status()
        return resp.json()

    def parse_ns_all_records(self, payload: Any) -> List[WalletSnapshot]:
        """
        Adjust THIS if Marinade changes the shape.

        Supported shapes:
        1) [ {"pubkey": "...", "amount": "...", "createdAt": "..."} ]
        2) { "data": [ ... ] }
        3) { "items": [ ... ] }
        """
        if isinstance(payload, list):
            items = payload
        elif isinstance(payload, dict):
            if isinstance(payload.get("data"), list):
                items = payload["data"]
            elif isinstance(payload.get("items"), list):
                items = payload["items"]
            else:
                raise ValueError("Unsupported JSON shape: expected list or dict[data/items]")
        else:
            raise ValueError("Unsupported payload type")

        snapshot_run_at = utc_now_iso()
        out: List[WalletSnapshot] = []

        for item in items:
            wallet = item.get("pubkey") or item.get("wallet") or item.get("address")
            amount = item.get("amount") or item.get("balance") or item.get("amountSol")
            created_at = item.get("createdAt")

            if not wallet:
                continue

            out.append(
                WalletSnapshot(
                    snapshot_run_at=snapshot_run_at,
                    wallet=str(wallet),
                    amount_sol=safe_float(amount),
                    source_created_at=created_at,
                )
            )
        return out


class PriceClient:
    def __init__(self, url: str = SOL_PRICE_URL, timeout: int = 20):
        self.url = url
        self.timeout = timeout
        self.session = requests.Session()

    def fetch_sol_usd(self) -> float:
        resp = self.session.get(self.url, timeout=self.timeout)
        resp.raise_for_status()
        payload = resp.json()
        if "solana" in payload and "usd" in payload["solana"]:
            return float(payload["solana"]["usd"])
        raise ValueError("Could not parse SOL/USD price payload")


# ============================================================
# Collector
# ============================================================

class SnapshotCollector:
    def __init__(self, db: Database, marinade: MarinadeClient, price_client: PriceClient):
        self.db = db
        self.marinade = marinade
        self.price_client = price_client

    def collect_once(self) -> str:
        payload = self.marinade.fetch_ns_all()
        snapshots = self.marinade.parse_ns_all_records(payload)
        if not snapshots:
            raise RuntimeError("No wallet snapshots parsed from Marinade response")

        snapshot_run_at = snapshots[0].snapshot_run_at
        count = self.db.insert_wallet_snapshots(snapshots)
        self.db.insert_snapshot_run(snapshot_run_at, count, notes="ns/all")

        try:
            price = self.price_client.fetch_sol_usd()
            self.db.insert_price_snapshot(
                PriceSnapshot(snapshot_run_at=snapshot_run_at, sol_usd=price)
            )
            log.info("stored SOL/USD price %.6f for run %s", price, snapshot_run_at)
        except Exception as e:
            log.warning("price fetch failed: %s", e)

        log.info("collected %d wallet snapshots at %s", count, snapshot_run_at)
        return snapshot_run_at

    def daemon(self, interval_seconds: int, keep_last_n_runs: Optional[int] = None) -> None:
        log.info("starting daemon, interval=%ss", interval_seconds)
        while True:
            started = time.time()
            try:
                self.collect_once()
                if keep_last_n_runs:
                    self.db.prune_old_runs(keep_last_n_runs)
            except Exception as e:
                log.exception("collection failed: %s", e)

            elapsed = time.time() - started
            sleep_for = max(1, interval_seconds - int(elapsed))
            log.info("sleeping %ss", sleep_for)
            time.sleep(sleep_for)


# ============================================================
# Metrics engine
# ============================================================

class MetricsEngine:
    def __init__(self, db: Database):
        self.db = db

    def _current_sol_price(self) -> Optional[float]:
        ps = self.db.latest_price()
        if not ps:
            return None
        age = (utc_now() - parse_iso(ps.snapshot_run_at)).total_seconds()
        if age > MAX_PRICE_AGE_SECONDS:
            return ps.sol_usd
        return ps.sol_usd

    def wallet_metrics_for_window(self, wallet: str, window_seconds: int) -> Optional[WalletMetrics]:
        history = self.db.wallet_history(wallet)
        if len(history) < 2:
            return None

        latest_ts_str, latest_amt = history[-1]
        latest_ts = parse_iso(latest_ts_str)
        target_time = latest_ts - dt.timedelta(seconds=window_seconds)
        prev = nearest_record_before_or_at(history, target_time)

        if prev is None:
            return None

        prev_ts_str, prev_amt = prev
        prev_ts = parse_iso(prev_ts_str)
        seconds_between = (latest_ts - prev_ts).total_seconds()
        if seconds_between <= 0:
            return None

        delta_sol = latest_amt - prev_amt
        sol_per_second = delta_sol / seconds_between
        roi_pct = safe_div(delta_sol, prev_amt) * 100.0 if prev_amt > 0 else None

        sol_usd = self._current_sol_price()
        current_value_usd = latest_amt * sol_usd if sol_usd is not None else None
        delta_usd = delta_sol * sol_usd if sol_usd is not None else None
        usd_per_second = delta_usd / seconds_between if delta_usd is not None else None
        cents_per_second = usd_per_second * 100.0 if usd_per_second is not None else None

        return WalletMetrics(
            wallet=wallet,
            current_amount_sol=latest_amt,
            current_value_usd=current_value_usd,
            delta_sol=delta_sol,
            delta_usd=delta_usd,
            seconds_between=seconds_between,
            sol_per_second=sol_per_second,
            usd_per_second=usd_per_second,
            cents_per_second=cents_per_second,
            roi_pct=roi_pct,
            from_snapshot=prev_ts_str,
            to_snapshot=latest_ts_str,
        )

    def leaderboard(self, window_seconds: int, limit: int = 25, sort_by: str = "cents_per_second") -> List[WalletMetrics]:
        wallets = self.db.all_wallets_in_latest_run()
        out: List[WalletMetrics] = []

        for wallet in wallets:
            m = self.wallet_metrics_for_window(wallet, window_seconds)
            if m is not None:
                out.append(m)

        if sort_by == "roi_pct":
            out.sort(key=lambda x: (x.roi_pct if x.roi_pct is not None else -math.inf), reverse=True)
        elif sort_by == "sol_per_second":
            out.sort(key=lambda x: x.sol_per_second, reverse=True)
        else:
            out.sort(key=lambda x: (x.cents_per_second if x.cents_per_second is not None else -math.inf), reverse=True)

        return out[:limit]

    def multi_window_report(self, wallet: str) -> Dict[str, Optional[WalletMetrics]]:
        report: Dict[str, Optional[WalletMetrics]] = {}
        for label, secs in WINDOWS.items():
            report[label] = self.wallet_metrics_for_window(wallet, secs)
        return report


# ============================================================
# Printing
# ============================================================

def print_leaderboard(rows: List[WalletMetrics], title: str) -> None:
    print()
    print("=" * 120)
    print(title)
    print("=" * 120)
    print(
        f"{'#':>3}  {'wallet':<46} {'current_SOL':>12} {'USD_value':>12} {'ROI_%':>8} {'cents/sec':>10} {'period':>8}"
    )
    print("-" * 120)
    for i, m in enumerate(rows, 1):
        print(
            f"{i:>3}  {m.wallet:<46} {m.current_amount_sol:>12.6f} {fmt_money(m.current_value_usd):>12} {fmt_pct(m.roi_pct):>8} {fmt_money(m.cents_per_second):>10} {m.seconds_between/86400:>8.1f}d"
        )
    print("-" * 120)


# ============================================================
# Web Interface
# ============================================================

from flask import Flask, render_template_string, jsonify, request
import webbrowser

app = Flask(__name__)

MARINADE_UI_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Marinade Staking Tracker - Top Performers</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <style>
        .gradient-bg {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 50%, #f093fb 100%);
        }
        .glass-effect {
            background: rgba(255, 255, 255, 0.1);
            backdrop-filter: blur(10px);
            border: 1px solid rgba(255, 255, 255, 0.2);
        }
        @keyframes pulse {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.7; }
        }
        .live-indicator {
            background: #10b981;
            animation: pulse 2s infinite;
        }
    </style>
</head>
<body class="gradient-bg min-h-screen text-white">
    <div class="container mx-auto px-4 py-8">
        <!-- Header -->
        <header class="text-center mb-10">
            <h1 class="text-5xl font-bold mb-4">
                <i class="fas fa-chart-line mr-3"></i>Marinade Staking Tracker
            </h1>
            <p class="text-xl opacity-90">Top Performing Wallets Analysis</p>
            <div class="flex items-center justify-center mt-4">
                <div class="live-indicator w-3 h-3 rounded-full mr-2"></div>
                <span class="text-lg">LIVE TRACKING</span>
            </div>
        </header>

        <!-- Control Panel -->
        <div class="glass-effect rounded-xl p-6 mb-10">
            <h2 class="text-2xl font-bold mb-6">
                <i class="fas fa-gamepad mr-2"></i>Analysis Control
            </h2>
            
            <div class="grid md:grid-cols-4 gap-6 mb-6">
                <div class="text-center">
                    <button onclick="collectData()" id="collect-btn"
                            class="w-full bg-green-600 hover:bg-green-700 px-6 py-3 rounded-lg font-bold transition">
                        <i class="fas fa-download mr-2"></i>Collect Data
                    </button>
                </div>
                <div class="text-center">
                    <button onclick="showLeaderboard()" 
                            class="w-full bg-blue-600 hover:bg-blue-700 px-6 py-3 rounded-lg font-bold transition">
                        <i class="fas fa-trophy mr-2"></i>Show Leaderboard
                    </button>
                </div>
                <div class="text-center">
                    <button onclick="analyzeWallet()" 
                            class="w-full bg-purple-600 hover:bg-purple-700 px-6 py-3 rounded-lg font-bold transition">
                        <i class="fas fa-search mr-2"></i>Analyze Wallet
                    </button>
                </div>
                <div class="text-center">
                    <button onclick="deployService()" 
                            class="w-full bg-orange-600 hover:bg-orange-700 px-6 py-3 rounded-lg font-bold transition">
                        <i class="fas fa-rocket mr-2"></i>Deploy Service
                    </button>
                </div>
            </div>
            
            <div class="grid md:grid-cols-3 gap-4">
                <div>
                    <label class="block text-sm mb-2">Time Window</label>
                    <select id="window-select" class="w-full bg-white/20 rounded px-3 py-2">
                        <option value="1d">1 Day</option>
                        <option value="7d">7 Days</option>
                        <option value="30d">30 Days</option>
                        <option value="90d" selected>90 Days</option>
                        <option value="365d">365 Days</option>
                    </select>
                </div>
                <div>
                    <label class="block text-sm mb-2">Limit</label>
                    <select id="limit-select" class="w-full bg-white/20 rounded px-3 py-2">
                        <option value="10">Top 10</option>
                        <option value="25" selected>Top 25</option>
                        <option value="50">Top 50</option>
                        <option value="100">Top 100</option>
                    </select>
                </div>
                <div>
                    <label class="block text-sm mb-2">Sort By</label>
                    <select id="sort-select" class="w-full bg-white/20 rounded px-3 py-2">
                        <option value="cents_per_second" selected>Cents/Second</option>
                        <option value="roi_pct">ROI %</option>
                        <option value="sol_per_second">SOL/Second</option>
                    </select>
                </div>
            </div>
        </div>

        <!-- Stats Overview -->
        <div class="grid md:grid-cols-4 gap-6 mb-10">
            <div class="glass-effect rounded-xl p-6 text-center">
                <div class="text-4xl font-bold text-yellow-300" id="total-wallets">0</div>
                <div class="text-sm opacity-70 mt-2">Total Wallets</div>
            </div>
            <div class="glass-effect rounded-xl p-6 text-center">
                <div class="text-4xl font-bold text-green-400" id="snapshot-runs">0</div>
                <div class="text-sm opacity-70 mt-2">Snapshot Runs</div>
            </div>
            <div class="glass-effect rounded-xl p-6 text-center">
                <div class="text-4xl font-bold text-blue-400" id="sol-price">$0</div>
                <div class="text-sm opacity-70 mt-2">SOL Price</div>
            </div>
            <div class="glass-effect rounded-xl p-6 text-center">
                <div class="text-4xl font-bold text-purple-400" id="last-update">Never</div>
                <div class="text-sm opacity-70 mt-2">Last Update</div>
            </div>
        </div>

        <!-- Leaderboard -->
        <div class="glass-effect rounded-xl p-6 mb-10">
            <h2 class="text-2xl font-bold mb-6">
                <i class="fas fa-trophy mr-2"></i>Top Performers
            </h2>
            
            <div class="overflow-x-auto">
                <table class="w-full text-sm">
                    <thead>
                        <tr class="border-b border-white/20">
                            <th class="text-left p-3">#</th>
                            <th class="text-left p-3">Wallet Address</th>
                            <th class="text-right p-3">Current SOL</th>
                            <th class="text-right p-3">USD Value</th>
                            <th class="text-right p-3">ROI %</th>
                            <th class="text-right p-3">Cents/Sec</th>
                            <th class="text-right p-3">Period</th>
                            <th class="text-center p-3">Actions</th>
                        </tr>
                    </thead>
                    <tbody id="leaderboard-body">
                        <tr>
                            <td colspan="8" class="text-center p-8 opacity-60">
                                <i class="fas fa-chart-line text-4xl mb-4"></i>
                                <p>Click "Show Leaderboard" to load top performers</p>
                            </td>
                        </tr>
                    </tbody>
                </table>
            </div>
        </div>

        <!-- Wallet Analysis -->
        <div class="glass-effect rounded-xl p-6" id="wallet-analysis" style="display: none;">
            <h2 class="text-2xl font-bold mb-6">
                <i class="fas fa-search mr-2"></i>Wallet Analysis
            </h2>
            
            <div class="mb-4">
                <input type="text" id="wallet-input" placeholder="Enter wallet address..." 
                       class="w-full bg-white/20 rounded px-4 py-3 text-white placeholder-white/60">
            </div>
            
            <div id="wallet-results" class="space-y-4"></div>
        </div>
    </div>

    <script>
        // API functions
        async function apiCall(endpoint, method = 'GET', data = null) {
            try {
                const options = {
                    method: method,
                    headers: {
                        'Content-Type': 'application/json',
                    }
                };
                
                if (data && method !== 'GET') {
                    options.body = JSON.stringify(data);
                }
                
                const response = await fetch(`/api${endpoint}`, options);
                return await response.json();
            } catch (error) {
                console.error('API call failed:', error);
                return { error: error.message };
            }
        }

        // Control functions
        async function collectData() {
            const btn = document.getElementById('collect-btn');
            btn.disabled = true;
            btn.innerHTML = '<i class="fas fa-spinner fa-spin mr-2"></i>Collecting...';
            
            const response = await apiCall('/collect', 'POST');
            
            btn.disabled = false;
            btn.innerHTML = '<i class="fas fa-download mr-2"></i>Collect Data';
            
            if (response.success) {
                showNotification('Data collected successfully!', 'success');
                loadStats();
            } else {
                showNotification(response.error || 'Failed to collect data', 'error');
            }
        }

        async function showLeaderboard() {
            const window = document.getElementById('window-select').value;
            const limit = document.getElementById('limit-select').value;
            const sortBy = document.getElementById('sort-select').value;
            
            const response = await apiCall(`/leaderboard?window=${window}&limit=${limit}&sort=${sortBy}`);
            
            if (response.success) {
                displayLeaderboard(response.data);
            } else {
                showNotification(response.error || 'Failed to load leaderboard', 'error');
            }
        }

        function displayLeaderboard(data) {
            const tbody = document.getElementById('leaderboard-body');
            
            if (!data || data.length === 0) {
                tbody.innerHTML = `
                    <tr>
                        <td colspan="8" class="text-center p-8 opacity-60">
                            <i class="fas fa-chart-line text-4xl mb-4"></i>
                            <p>No data available</p>
                        </td>
                    </tr>
                `;
                return;
            }
            
            tbody.innerHTML = data.map((wallet, index) => `
                <tr class="border-b border-white/10 hover:bg-white/5">
                    <td class="p-3 font-bold">${index + 1}</td>
                    <td class="p-3">
                        <div class="font-mono text-xs">${wallet.wallet}</div>
                        <div class="text-xs opacity-60 mt-1">
                            <a href="https://explorer.solana.com/address/${wallet.wallet}" 
                               target="_blank" class="text-blue-400 hover:underline">
                                View on Explorer →
                            </a>
                        </div>
                    </td>
                    <td class="p-3 text-right font-mono">${wallet.current_amount_sol.toFixed(6)}</td>
                    <td class="p-3 text-right">$${wallet.current_value_usd?.toFixed(2) || 'n/a'}</td>
                    <td class="p-3 text-right font-mono ${wallet.roi_pct > 0 ? 'text-green-400' : 'text-red-400'}">
                        ${wallet.roi_pct?.toFixed(6) || 'n/a'}%
                    </td>
                    <td class="p-3 text-right font-mono">$${wallet.cents_per_second?.toFixed(6) || 'n/a'}</td>
                    <td class="p-3 text-right">${(wallet.seconds_between / 86400).toFixed(1)}d</td>
                    <td class="p-3 text-center">
                        <button onclick="analyzeSpecificWallet('${wallet.wallet}')" 
                                class="bg-blue-600 hover:bg-blue-700 px-3 py-1 rounded text-sm transition">
                            Analyze
                        </button>
                    </td>
                </tr>
            `).join('');
        }

        function analyzeWallet() {
            const analysisDiv = document.getElementById('wallet-analysis');
            analysisDiv.style.display = analysisDiv.style.display === 'none' ? 'block' : 'none';
        }

        async function analyzeSpecificWallet(wallet) {
            const response = await apiCall(`/wallet/${wallet}`);
            
            if (response.success) {
                displayWalletAnalysis(response.data);
                document.getElementById('wallet-analysis').style.display = 'block';
            } else {
                showNotification(response.error || 'Failed to analyze wallet', 'error');
            }
        }

        function displayWalletAnalysis(data) {
            const resultsDiv = document.getElementById('wallet-results');
            
            let html = '<div class="space-y-4">';
            
            for (const [window, metrics] of Object.entries(data)) {
                if (!metrics) continue;
                
                html += `
                    <div class="p-4 bg-white/10 rounded-lg">
                        <h3 class="font-bold mb-2">${window} Performance</h3>
                        <div class="grid grid-cols-2 gap-4 text-sm">
                            <div>
                                <div class="opacity-70">Current SOL</div>
                                <div class="font-mono">${metrics.current_amount_sol.toFixed(6)}</div>
                            </div>
                            <div>
                                <div class="opacity-70">USD Value</div>
                                <div class="font-mono">$${metrics.current_value_usd?.toFixed(2) || 'n/a'}</div>
                            </div>
                            <div>
                                <div class="opacity-70">ROI %</div>
                                <div class="font-mono ${metrics.roi_pct > 0 ? 'text-green-400' : 'text-red-400'}">
                                    ${metrics.roi_pct?.toFixed(6) || 'n/a'}%
                                </div>
                            </div>
                            <div>
                                <div class="opacity-70">Cents/Second</div>
                                <div class="font-mono">$${metrics.cents_per_second?.toFixed(6) || 'n/a'}</div>
                            </div>
                        </div>
                    </div>
                `;
            }
            
            html += '</div>';
            resultsDiv.innerHTML = html;
        }

        async function deployService() {
            showNotification('Deploying Marinade service...', 'info');
            
            const response = await apiCall('/deploy', 'POST');
            
            if (response.success) {
                showNotification('Service deployed successfully!', 'success');
            } else {
                showNotification(response.error || 'Failed to deploy', 'error');
            }
        }

        async function loadStats() {
            const response = await apiCall('/stats');
            
            if (response.success) {
                document.getElementById('total-wallets').textContent = response.data.total_wallets.toLocaleString();
                document.getElementById('snapshot-runs').textContent = response.data.run_count;
                document.getElementById('sol-price').textContent = `$${response.data.sol_price?.toFixed(2) || 'n/a'}`;
                document.getElementById('last-update').textContent = response.data.last_update || 'Never';
            }
        }

        function showNotification(message, type = 'info') {
            const colors = {
                success: 'bg-green-500',
                error: 'bg-red-500',
                warning: 'bg-yellow-500',
                info: 'bg-blue-500'
            };
            
            const notification = document.createElement('div');
            notification.className = `fixed top-4 right-4 ${colors[type]} text-white px-6 py-3 rounded-lg shadow-lg z-50`;
            notification.textContent = message;
            
            document.body.appendChild(notification);
            
            setTimeout(() => {
                notification.remove();
            }, 4000);
        }

        // Initialize
        async function init() {
            await loadStats();
        }

        // Start dashboard
        init();
    </script>
</body>
</html>
"""

@app.route('/')
def marinade_dashboard():
    """Serve Marinade staking tracker dashboard"""
    return render_template_string(MARINADE_UI_TEMPLATE)

@app.route('/api/collect', methods=['POST'])
def collect_data():
    """Collect Marinade snapshot data"""
    try:
        db = Database()
        marinade = MarinadeClient()
        price_client = PriceClient()
        collector = SnapshotCollector(db, marinade, price_client)
        
        snapshot_run_at = collector.collect_once()
        
        return jsonify({
            "success": True,
            "message": f"Data collected at {snapshot_run_at}",
            "snapshot_run_at": snapshot_run_at
        })
        
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/leaderboard')
def get_leaderboard():
    """Get leaderboard data"""
    try:
        window = request.args.get('window', '90d')
        limit = int(request.args.get('limit', 25))
        sort_by = request.args.get('sort', 'cents_per_second')
        
        window_seconds = WINDOWS.get(window, WINDOWS['90d'])
        
        db = Database()
        metrics = MetricsEngine(db)
        leaderboard = metrics.leaderboard(window_seconds, limit, sort_by)
        
        # Convert to JSON-serializable format
        data = []
        for m in leaderboard:
            data.append({
                "wallet": m.wallet,
                "current_amount_sol": m.current_amount_sol,
                "current_value_usd": m.current_value_usd,
                "delta_sol": m.delta_sol,
                "delta_usd": m.delta_usd,
                "seconds_between": m.seconds_between,
                "sol_per_second": m.sol_per_second,
                "usd_per_second": m.usd_per_second,
                "cents_per_second": m.cents_per_second,
                "roi_pct": m.roi_pct,
                "from_snapshot": m.from_snapshot,
                "to_snapshot": m.to_snapshot
            })
        
        return jsonify({
            "success": True,
            "data": data,
            "window": window,
            "limit": limit,
            "sort_by": sort_by
        })
        
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/wallet/<wallet>')
def analyze_wallet(wallet):
    """Analyze specific wallet"""
    try:
        db = Database()
        metrics = MetricsEngine(db)
        report = metrics.multi_window_report(wallet)
        
        # Convert to JSON-serializable format
        data = {}
        for window, m in report.items():
            if m:
                data[window] = {
                    "wallet": m.wallet,
                    "current_amount_sol": m.current_amount_sol,
                    "current_value_usd": m.current_value_usd,
                    "delta_sol": m.delta_sol,
                    "delta_usd": m.delta_usd,
                    "seconds_between": m.seconds_between,
                    "sol_per_second": m.sol_per_second,
                    "usd_per_second": m.usd_per_second,
                    "cents_per_second": m.cents_per_second,
                    "roi_pct": m.roi_pct,
                    "from_snapshot": m.from_snapshot,
                    "to_snapshot": m.to_snapshot
                }
            else:
                data[window] = None
        
        return jsonify({
            "success": True,
            "wallet": wallet,
            "data": data
        })
        
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/stats')
def get_stats():
    """Get system statistics"""
    try:
        db = Database()
        price = db.latest_price()
        
        stats = {
            "total_wallets": db.count_wallets(),
            "run_count": db.run_count(),
            "sol_price": price.sol_usd if price else None,
            "last_update": price.snapshot_run_at if price else None
        }
        
        return jsonify({
            "success": True,
            "data": stats
        })
        
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/deploy', methods=['POST'])
def deploy_service():
    """Deploy Marinade service"""
    try:
        import subprocess
        import os
        
        # Create deployment script
        deploy_script = """#!/bin/bash
# Marinade Staking Tracker Deployment
echo "Deploying Marinade Staking Tracker..."

# Deploy to Vercel
vercel --prod

# Deploy to Netlify
netlify deploy --prod --dir=.

echo "Deployment complete!"
"""
        
        with open("deploy_marinade.sh", "w") as f:
            f.write(deploy_script)
        
        os.chmod("deploy_marinade.sh", 0o755)
        
        # Execute deployment
        result = subprocess.run(["./deploy_marinade.sh"], capture_output=True, text=True)
        
        if result.returncode == 0:
            return jsonify({
                "success": True,
                "message": "Marinade service deployed successfully!"
            })
        else:
            return jsonify({
                "success": False,
                "error": result.stderr
            })
            
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# ============================================================
# CLI Commands
# ============================================================

def cli_collect_once() -> None:
    """Collect one snapshot"""
    db = Database()
    marinade = MarinadeClient()
    price_client = PriceClient()
    collector = SnapshotCollector(db, marinade, price_client)
    collector.collect_once()

def cli_daemon(interval_seconds: int, keep_last_n_runs: Optional[int]) -> None:
    """Run collection daemon"""
    db = Database()
    marinade = MarinadeClient()
    price_client = PriceClient()
    collector = SnapshotCollector(db, marinade, price_client)
    collector.daemon(interval_seconds, keep_last_n_runs)

def cli_leaderboard(window: str, limit: int, sort_by: str) -> None:
    """Show leaderboard"""
    db = Database()
    metrics = MetricsEngine(db)
    window_seconds = WINDOWS.get(window, WINDOWS["90d"])
    rows = metrics.leaderboard(window_seconds, limit, sort_by)
    title = f"Marinade Leaderboard - {window} (Top {limit}, sorted by {sort_by})"
    print_leaderboard(rows, title)

def cli_wallet(wallet: str) -> None:
    """Show wallet analysis"""
    db = Database()
    metrics = MetricsEngine(db)
    report = metrics.multi_window_report(wallet)
    
    print(f"\nWallet Analysis: {wallet}")
    print("=" * 80)
    for label, m in report.items():
        if m:
            print(f"\n{label}:")
            print(f"  Current SOL: {m.current_amount_sol:.6f}")
            print(f"  USD Value: {fmt_money(m.current_value_usd)}")
            print(f"  ROI: {fmt_pct(m.roi_pct)}")
            print(f"  Cents/sec: {fmt_money(m.cents_per_second)}")
            print(f"  Period: {m.seconds_between/86400:.1f} days")

def cli_stats() -> None:
    """Show system statistics"""
    db = Database()
    price = db.latest_price()
    
    print(f"\nMarinade Tracker Statistics")
    print("=" * 40)
    print(f"Total Wallets: {db.count_wallets()}")
    print(f"Snapshot Runs: {db.run_count()}")
    print(f"SOL Price: {fmt_money(price.sol_usd if price else None)}")
    print(f"Last Update: {price.snapshot_run_at if price else 'Never'}")

def cli_init_db() -> None:
    """Initialize database"""
    db = Database()
    db.init_db()

def main() -> None:
    parser = argparse.ArgumentParser(description="Marinade Native Stake Tracker")
    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    
    # Init DB
    subparsers.add_parser("init-db", help="Initialize database")
    
    # Collect once
    subparsers.add_parser("collect-once", help="Collect one snapshot")
    
    # Daemon
    daemon_parser = subparsers.add_parser("daemon", help="Run collection daemon")
    daemon_parser.add_argument("--interval", type=int, default=DEFAULT_INTERVAL_SECONDS,
                             help="Collection interval in seconds")
    daemon_parser.add_argument("--keep-last", type=int, help="Keep last N runs")
    
    # Leaderboard
    leaderboard_parser = subparsers.add_parser("leaderboard", help="Show leaderboard")
    leaderboard_parser.add_argument("--window", default="90d", choices=list(WINDOWS.keys()),
                                  help="Time window")
    leaderboard_parser.add_argument("--limit", type=int, default=25,
                                  help="Number of wallets to show")
    leaderboard_parser.add_argument("--sort", default="cents_per_second",
                                  choices=["cents_per_second", "roi_pct", "sol_per_second"],
                                  help="Sort by metric")
    
    # Wallet analysis
    wallet_parser = subparsers.add_parser("wallet", help="Analyze wallet")
    wallet_parser.add_argument("address", help="Wallet address")
    
    # Stats
    subparsers.add_parser("stats", help="Show statistics")
    
    # Web interface
    web_parser = subparsers.add_parser("web", help="Start web interface")
    web_parser.add_argument("--port", type=int, default=8094, help="Port for web interface")
    
    args = parser.parse_args()
    
    if args.command == "init-db":
        cli_init_db()
    elif args.command == "collect-once":
        cli_collect_once()
    elif args.command == "daemon":
        cli_daemon(args.interval, args.keep_last)
    elif args.command == "leaderboard":
        cli_leaderboard(args.window, args.limit, args.sort)
    elif args.command == "wallet":
        cli_wallet(args.address)
    elif args.command == "stats":
        cli_stats()
    elif args.command == "web":
        print(f"🌐 Starting Marinade Web Interface: http://localhost:{args.port}")
        webbrowser.open(f'http://localhost:{args.port}')
        app.run(host='0.0.0.0', port=args.port, debug=False)
    else:
        parser.print_help()

if __name__ == "__main__":
    main()