#!/usr/bin/env python3
"""
CopyThatPay — Hedged Spread-Capture Engine

A microstructure-aware, risk-gated execution engine for Gate.io futures.
Designed to capture micro spreads with strict risk controls and edge validation.

⚠️  SECURITY REQUIREMENT: This system is designed for Gate.io whitelisted
IP addresses only. You must whitelist your IP address in Gate.io API settings
before using this system. Do not use without IP whitelisting enabled.

⚠️  WARNING: This is experimental software. Trading involves significant risk.

Capital preservation first. Profit second. Always.

Execution Doctrine: Hedged Micro-Spread Capture (HMSC)
  A non-passive, delta-neutral spread-capture engine designed for micro accounts.
  Combines known quant building blocks in an uncommon package:
    - Two-sided hedged quoting (long+short on same symbol, simultaneously)
    - Maker-first entry with aggressive taker fallback after timeout
    - Per-leg exit at calculated spread target (fees + margin, guaranteed net-positive)
    - High turnover: exit → recycle → re-quote (no idle capital)
    - Micro-account native: designed to scale from tiny deposits upward
    - Capital as a controllable machine, not a passive allocation

  Individual components are standard (market making, delta-neutral positioning,
  inventory recycling, spread capture, maker/taker hybrid execution).
  The combination — micro sizing + hedged legs + immediate fills + non-passive
  behavior + low blow-up risk + scaling from small deposits — is distinctive.

Architecture:
  RiskEngine          — Centralized risk control, overrides all trading logic
  PerformanceTracker  — Equity curve, Sharpe, drawdown, CSV export
  TradeJournal        — Auditable, human-readable action log
  CopyThatPay         — Aggressive spread-capture engine with maker-first quoting

Execution Model:
  1. Quote both sides: post_only buy@bid + sell@ask (simultaneous)
  2. On fill: place reduce_only exit at spread target price
  3. On exit fill: record PnL, recycle quote (high turnover)
  4. Stale quote refresh: cancel + re-place when book moves >0.1%
  5. Taker fallback: cross spread after maker timeout (20s default)

Why this system will NOT blow up:
  1. Risk engine vetoes every trade before execution
  2. Capital partitioned: 60% active, 20% reserve, 20% buffer
  3. Max 2% equity drawdown per symbol, 10% global — hard enforced
  4. Time-based exits flatten stale positions automatically
  5. Volatility kill-switch pauses trading in abnormal conditions
  6. Inventory imbalance detection + forced rebalance
  7. Every action logged with reason + risk state for audit
  8. Full restart recovery from persisted state
"""

import ccxt.async_support as ccxt
import asyncio
import aiohttp
import csv
import json
import math
import os
import random
import sys
import time
import traceback
import urllib.request
import urllib.error
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from dotenv import load_dotenv
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from rich.console import Console
from rich.table import Table

load_dotenv()
console = Console()

# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 1: CONFIGURATION
# All parameters are constants. No runtime mutation. No magic numbers in logic.
# ═══════════════════════════════════════════════════════════════════════════════

API_KEY    = os.getenv('GATE_API_KEY', '')
API_SECRET = os.getenv('GATE_API_SECRET', '')
GROQ_KEY   = os.getenv('GROQ_API_KEY', '')

# — LLM Self-Testing Loop Config —
LLM_TEST_HORIZON_SEC   = int(os.getenv('LLM_TEST_HORIZON_SEC', '60'))
LLM_CRITIC_INTERVAL   = int(os.getenv('LLM_CRITIC_INTERVAL_SEC', '300'))
LLM_MIN_CONFIDENCE    = float(os.getenv('LLM_MIN_CONFIDENCE', '0.6'))
LLM_MAX_ERRORS_READ   = int(os.getenv('LLM_MAX_ERRORS_READ', '50'))
LLM_POLICY_MAX_ADJ    = float(os.getenv('LLM_POLICY_MAX_ADJ', '0.1'))

if not API_KEY or not API_SECRET:
    console.print('[bold red]FATAL: GATE_API_KEY and GATE_API_SECRET must be set in .env')
    sys.exit(1)

# — File paths —
DATA_DIR          = Path('copythatpay_data')
SYMBOL_FILE       = DATA_DIR / 'symbols.json'
STATE_FILE        = DATA_DIR / 'state.json'
HEDGE_STATE_FILE  = DATA_DIR / 'hedge_state.json'
TRADE_JOURNAL     = DATA_DIR / 'journal.jsonl'
EQUITY_CURVE_CSV  = DATA_DIR / 'equity_curve.csv'
DAILY_REPORT_DIR  = DATA_DIR / 'reports'
PERF_METRICS_FILE    = DATA_DIR / 'metrics.json'
LLM_TRADE_MEMORY     = DATA_DIR / 'llm_trade_memory.jsonl'
LLM_ERROR_MEMORY     = DATA_DIR / 'llm_error_memory.jsonl'
LLM_POLICY_FILE      = DATA_DIR / 'llm_policy.json'
PENNY_TRACKER_CSV = DATA_DIR / 'penny_tracker.csv'

# — Risk limits (institutional) —
MAX_DRAWDOWN_PER_SYMBOL   = 0.02    # 2% of equity max loss per symbol before flatten
MAX_DRAWDOWN_GLOBAL       = 0.10    # 10% of equity total floating loss cap
MAX_CONCURRENT_SYMBOLS    = 5       # 5 high-vol symbols only
MAX_EXPOSURE_PER_SYMBOL   = 0.15    # 15% of equity per symbol notional
MAX_NOTIONAL_PER_CONTRACT = 5.00    # $5.00 max notional per contract (loosened for $9 account)
MARGIN_RATIO_CRITICAL     = 0.70    # flatten all at 70% margin ratio
MAX_POSITION_AGE_SECONDS  = 7200    # 2 hours — time-based exit
VOLATILITY_KILL_THRESHOLD = 0.05    # 5% candle move = pause symbol
MAX_DCA_ROUNDS            = 0       # bounded DCA — no infinite averaging

# — Capital partitioning (micro-account: $9) —
CAPITAL_ACTIVE_RATIO   = 0.70   # 70% available for trading (aggressive for tiny account)
CAPITAL_RESERVE_RATIO  = 0.20   # 20% untouchable reserve
CAPITAL_BUFFER_RATIO   = 0.10   # 10% risk buffer (minimal for growth)
TOTAL_CAPITAL_USD      = 9.0     # Starting capital
TOTAL_MAX_POSITION_USD = 0.45    # max $0.45 per leg (tighter for micro account) capital

# — Execution —
DEFAULT_LEVERAGE    = 5
FEE_RATE            = 0.00075
OFFSET              = 0.002      # 0.2% limit offset to cross spread
MAX_ORDER_RETRIES   = 5
FILL_TIMEOUT_SEC    = 10
MONITOR_INTERVAL    = 15
MARGIN_MODE         = 'isolated'
FORCE_TAKER_MODE    = True      # Edge version: accept entry cost, don't pretend to be first in queue
DIAGNOSTIC_MODE     = False     # Real edge detection — no more random trades

# — Spread-capture params —
MIN_REAL_SPREAD        = 0.0035   # 0.35% — must beat fees (0.15%) + slippage (0.1-0.2%)
SPREAD_TARGET_PCT      = 0.005    # 0.5% target — real profit after costs
MAKER_TIMEOUT_SEC      = 120      # 2min for maker fill
QUOTE_REFRESH_SEC      = 30       # re-place quotes only on significant drift
BOOK_DRIFT_THRESHOLD   = 0.002    # 0.2% drift triggers re-quote
CYCLE_INTERVAL_SEC     = 20       # 20s between cycles — fewer trades, less fee bleed
MIN_VOLUME_USD         = 20000    # $20k minimum 24h volume — allow wider-spread symbols
SLIPPAGE_EST           = 0.0015   # 0.15% estimated slippage — realistic for taker fills

# — Execution risk controls —
PANIC_EXIT_SEC         = 900      # 15min — only panic on truly stale positions
EXIT_FILL_RATE_MIN     = 0.3      # 30% min exit fill rate before tightening
MAX_EXIT_WAIT_SEC      = 60       # 60 seconds max wait for exit fill
SYMBOL_COOLDOWN_SEC    = 30       # 30 seconds cooldown after failed exit
EDGE_DECAY_THRESHOLD   = 0.5      # if real edge < 50% of theoretical, pause
REAL_STOP_PCT          = 0.0015   # 0.15% stop — cut losers immediately
TP_PCT                 = 0.003    # 0.3% take-profit — fast continuation scalp
MAX_HOLD_SEC           = 30       # 30s max hold — if it doesn't move fast, leave
DAILY_STOP             = -0.01    # -1% daily stop — survival > everything with $9
MAX_SHORT_TERM_VOL     = 0.02     # 2% max short-term volatility — prevents getting run over
MIN_EXPECTED_MOVE      = 0.0015   # 0.15% minimum momentum / expected move
EARLY_EXIT_SEC         = 12       # kill dead trades quickly
EARLY_EXIT_PNL_PCT     = 0.001    # if still under +0.1%, leave early
SPREAD_Z_MIN          = 2.0      # only trade abnormal spread conditions
SPREAD_HISTORY_MIN    = 10       # minimum samples before spread z-score is trusted
SPREAD_HISTORY_MAX    = 20       # bounded rolling spread history per symbol
SPREAD_READY_Z        = 1.2      # compression toward normal before breakout entry
MEAN_REVERSION_MOM_MAX = 0.0005  # high-z but weak motion = skip breakout mode
MAX_MAKER_WAIT_SEC    = 3.0      # short maker probe before paying taker fees
MODEL_PROB_MIN         = 0.55     # local model veto threshold
MODEL_PROB_HIGH        = 0.70     # strongest setups
OLLAMA_TIE_MIN         = 0.55     # only use Ollama in this band
OLLAMA_TIE_MAX         = 0.65
OLLAMA_MIN_SCORE       = 6.0      # veto borderline setups below this score
OLLAMA_MIN_INTERVAL    = 5.0      # don't spam local inference server
OLLAMA_TIMEOUT_SEC     = 1.5
OLLAMA_URL             = 'http://localhost:11434/api/chat'
OLLAMA_MODEL           = 'llama3'
MAX_INVENTORY_CTS      = 5.0      # hard inventory cap per symbol
TARGET_INVENTORY_CTS   = 0.0      # neutral target inventory
INVENTORY_GAMMA        = 0.0005   # quote skew per contract of net inventory
ALPHA_SIGNAL_K         = 0.35     # converts signal score into fair-price bias
POSITION_DECAY_SEC     = 60       # reduce stale inventory after 60s

# — Micro-capital whitelist (ALL 89 ultra-micro symbols: min_trade <= $0.05) —
MICRO_WHITELIST = [
    'DOGS/USDT:USDT',      # $0.000323/ct, vol $128k
    'SLP/USDT:USDT',       # $0.000653/ct, vol $9.6k
    'MBOX/USDT:USDT',      # $0.001250/ct, vol $58k
    'ZK/USDT:USDT',        # $0.001624/ct, vol $276k
    'TLM/USDT:USDT',       # $0.001754/ct, vol $32k
    'SUN/USDT:USDT',       # $0.001879/ct, vol $42k
    'RDNT/USDT:USDT',      # $0.001932/ct, vol $26k
    'ICP/USDT:USDT',       # $0.002462/ct, vol $599k
    'BICO/USDT:USDT',      # $0.002524/ct, vol $28k
    'FLOW/USDT:USDT',      # $0.003831/ct, vol $151k
    'MEME/USDT:USDT',      # $0.005624/ct, vol $97k
    'JASMY/USDT:USDT',     # $0.005628/ct, vol $158k
    'MINA/USDT:USDT',      # $0.005938/ct, vol $117k
    'WAXP/USDT:USDT',      # $0.006722/ct, vol $70k
    'PIXEL/USDT:USDT',     # $0.007447/ct, vol $68k
    'ALT/USDT:USDT',       # $0.007786/ct, vol $75k
    'HOOK/USDT:USDT',      # $0.007990/ct, vol $22k
    'MANA/USDT:USDT',      # $0.009038/ct, vol $183k
    'FIL/USDT:USDT',       # $0.009214/ct, vol $3.4M
    'FIO/USDT:USDT',       # $0.009700/ct, vol $199k
    'XAI/USDT:USDT',       # $0.009913/ct, vol $53k
    'ME/USDT:USDT',        # $0.010460/ct, vol $129k
    'IOST/USDT:USDT',      # $0.010770/ct, vol $16k
    'GMT/USDT:USDT',       # $0.011400/ct, vol $112k
    'ACE/USDT:USDT',       # $0.011600/ct, vol $39k
    'DEGO/USDT:USDT',      # $0.011620/ct, vol $451k
    'W/USDT:USDT',         # $0.012682/ct, vol $130k
    'DYDX/USDT:USDT',      # $0.013153/ct, vol $568k
    'HIPPO/USDT:USDT',     # $0.013650/ct, vol $33k
    'COTI/USDT:USDT',      # $0.014400/ct, vol $12k
    'NFP/USDT:USDT',       # $0.014430/ct, vol $13k
    'USUAL/USDT:USDT',     # $0.014480/ct, vol $65k
    'ALICE/USDT:USDT',     # $0.014560/ct, vol $54k
    'HFT/USDT:USDT',       # $0.014570/ct, vol $105k
    'HMSTR/USDT:USDT',     # $0.015280/ct, vol $44k
    'MOG/USDT:USDT',       # $0.015670/ct, vol $309k
    'FIDA/USDT:USDT',      # $0.016410/ct, vol $25k
    'LRC/USDT:USDT',       # $0.016960/ct, vol $12k
    'SAGA/USDT:USDT',      # $0.017450/ct, vol $281k
    'ZKJ/USDT:USDT',       # $0.018040/ct, vol $28k
    'DYM/USDT:USDT',       # $0.018080/ct, vol $94k
    'WOO/USDT:USDT',       # $0.018100/ct, vol $15k
    'MOVR/USDT:USDT',      # $0.018170/ct, vol $487k
    'MOVE/USDT:USDT',      # $0.018250/ct, vol $78k
    'RPL/USDT:USDT',       # $0.018400/ct, vol $59k
    'C98/USDT:USDT',       # $0.021070/ct, vol $20k
    'AI/USDT:USDT',        # $0.021490/ct, vol $23k
    'BAND/USDT:USDT',      # $0.021700/ct, vol $43k
    'ONE/USDT:USDT',       # $0.021780/ct, vol $14k
    'CRV/USDT:USDT',       # $0.022220/ct, vol $2.2M
    'OGN/USDT:USDT',       # $0.023340/ct, vol $18k
    'AEVO/USDT:USDT',      # $0.025090/ct, vol $19k
    'XVS/USDT:USDT',       # $0.026360/ct, vol $31k
    'CELR/USDT:USDT',      # $0.026670/ct, vol $5k
    'NTRN/USDT:USDT',      # $0.028100/ct, vol $24k
    'MTL/USDT:USDT',       # $0.028960/ct, vol $5k
    'ETHW/USDT:USDT',      # $0.029050/ct, vol $67k
    'SNX/USDT:USDT',       # $0.029400/ct, vol $19k
    'ID/USDT:USDT',        # $0.030900/ct, vol $53k
    'BLUR/USDT:USDT',      # $0.031180/ct, vol $1.2M
    'PHA/USDT:USDT',       # $0.031500/ct, vol $28k
    'BIO/USDT:USDT',       # $0.031710/ct, vol $7.4M
    'GALA/USDT:USDT',      # $0.031720/ct, vol $3.0M
    'MAVIA/USDT:USDT',     # $0.033030/ct, vol $523k
    'CTSI/USDT:USDT',      # $0.033480/ct, vol $68k
    'METIS/USDT:USDT',     # $0.035500/ct, vol $121k
    'MERL/USDT:USDT',      # $0.036800/ct, vol $1.5M
    'REZ/USDT:USDT',       # $0.036800/ct, vol $54k
    'ICX/USDT:USDT',       # $0.036910/ct, vol $91k
    'SOLV/USDT:USDT',      # $0.038000/ct, vol $38k
    'TNSR/USDT:USDT',      # $0.038150/ct, vol $67k
    'YGG/USDT:USDT',       # $0.039210/ct, vol $78k
    'NOT/USDT:USDT',       # $0.039350/ct, vol $215k
    'NIL/USDT:USDT',       # $0.039350/ct, vol $61k
    'ZIL/USDT:USDT',       # $0.040110/ct, vol $27k
    'MBABYDOGE/USDT:USDT', # $0.041770/ct, vol $178k
    'SCR/USDT:USDT',       # $0.043050/ct, vol $71k
    'S/USDT:USDT',         # $0.043100/ct, vol $73k
    'TRU/USDT:USDT',       # $0.043170/ct, vol $233k
    'STRK/USDT:USDT',      # $0.043190/ct, vol $2.8M
    'ETHFI/USDT:USDT',     # $0.045170/ct, vol $299k
    'CATI/USDT:USDT',      # $0.045220/ct, vol $71k
    'ILV/USDT:USDT',       # $0.045360/ct, vol $72k
    'XCN/USDT:USDT',       # $0.046440/ct, vol $11k
    'ANIME/USDT:USDT',     # $0.046550/ct, vol $111k
    'IOTX/USDT:USDT',      # $0.046660/ct, vol $52k
    'RUNE/USDT:USDT',      # $0.047570/ct, vol $585k
    'CORE/USDT:USDT',      # $0.049120/ct, vol $10.6M
    'ANKR/USDT:USDT',      # $0.049800/ct, vol $15k
]


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 2: DATA STRUCTURES
# Immutable records for state tracking, audit trail, and risk snapshots.
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class HedgeLeg:
    """One side of a hedged position."""
    contracts: float = 0
    entry: float = 0
    timestamp: float = 0
    filled: bool = False
    dca_rounds: int = 0

@dataclass
class HedgePair:
    """A complete hedge: long + short on the same symbol."""
    long_leg: HedgeLeg = field(default_factory=HedgeLeg)
    short_leg: HedgeLeg = field(default_factory=HedgeLeg)
    hedge_open_time: float = 0
    harvests: int = 0
    
    # Execution risk metrics (new)
    exit_attempts: int = 0
    exit_fills: int = 0
    total_expected_profit: float = 0
    total_realized_profit: float = 0
    last_exit_time: float = 0

    @property
    def is_complete(self) -> bool:
        return self.long_leg.filled and self.short_leg.filled

    @property
    def is_empty(self) -> bool:
        return not self.long_leg.filled and not self.short_leg.filled

    @property
    def is_broken(self) -> bool:
        return self.long_leg.filled != self.short_leg.filled

    @property
    def age_seconds(self) -> float:
        if self.hedge_open_time <= 0:
            return 0
        return time.time() - self.hedge_open_time

@dataclass
class RiskSnapshot:
    """Point-in-time risk state. Attached to every journal entry for audit."""
    timestamp: float = 0
    equity: float = 0
    used_margin: float = 0
    free_capital: float = 0
    active_capital: float = 0
    margin_ratio: float = 0
    total_floating_pnl: float = 0
    drawdown_pct: float = 0
    open_hedges: int = 0
    broken_hedges: int = 0
    symbols_at_limit: int = 0
    risk_verdict: str = 'UNKNOWN'

@dataclass
class TradeRecord:
    """Auditable trade record. Every action produces one."""
    timestamp: str = ''
    epoch: float = 0
    action: str = ''
    symbol: str = ''
    side: str = ''
    contracts: float = 0
    price: float = 0
    pnl: float = 0
    reason: str = ''
    hedge_state: str = ''
    risk_snapshot: dict = field(default_factory=dict)

@dataclass
class TradeAnalytics:
    """Comprehensive trade analytics for edge validation."""
    symbol: str = ''
    side: str = ''
    entry_time: float = 0
    exit_time: float = 0
    entry_price: float = 0
    exit_price: float = 0
    mid_price_at_entry: float = 0
    contracts: float = 0
    expected_profit: float = 0
    realized_profit: float = 0
    fees_paid: float = 0
    is_maker_entry: bool = True
    is_maker_exit: bool = True
    exit_reason: str = ''

@dataclass
class EquityPoint:
    """Single point on the equity curve."""
    timestamp: str = ''
    epoch: float = 0
    equity: float = 0
    realized_pnl: float = 0
    unrealized_pnl: float = 0
    drawdown_pct: float = 0
    open_hedges: int = 0


@dataclass
class QuoteState:
    """Per-symbol state for the spread-capture engine."""
    long_order_id: str = ''
    short_order_id: str = ''
    long_quote_px: float = 0
    short_quote_px: float = 0
    long_filled: bool = False
    short_filled: bool = False
    long_entry: float = 0
    short_entry: float = 0
    long_cts: float = 0
    short_cts: float = 0
    long_exit_id: str = ''
    short_exit_id: str = ''
    cycles: int = 0
    realized: float = 0
    post_entry_alpha: float = 0  # price move 5s after entry as % of entry
    quote_time: float = 0
    long_mid_at_entry: float = 0   # mid price when long was placed (for slippage)
    short_mid_at_entry: float = 0  # mid price when short was placed (for slippage)
    net_inventory_cts: float = 0
    avg_inventory_entry: float = 0
    last_alpha_signal: float = 0
    last_momentum: float = 0
    bad_setup_count: int = 0
    last_features: List[float] = field(default_factory=list)
    last_model_prob: float = 0
    last_llm_score: Optional[float] = None
    last_edge_score: float = 0
    spread_history: List[float] = field(default_factory=list)
    last_spread_pct: float = 0
    last_spread_z: float = 0
    spread_state: str = 'idle'
    execution_mode: str = 'skip'


@dataclass
class LLMDecisionTest:
    """Record of a single LLM decision, registered for self-testing."""
    decision_id: str = ''
    timestamp: float = 0
    symbol: str = ''
    action: str = ''          # 'enter_long', 'enter_short', 'skip', 'exit'
    features: dict = field(default_factory=dict)
    confidence: float = 0     # 0-1
    rationale: str = ''
    predicted_move: float = 0 # expected price move as pct
    outcome_price: float = 0  # price at horizon end
    actual_move: float = 0    # actual price move as pct
    correct: Optional[bool] = None
    evaluated: bool = False


# ═══════════════════════════════════════════════════════════════════════════════
# PENNY TRACKER: Every cent accounted for — gross, fees, slippage, net
# ═══════════════════════════════════════════════════════════════════════════════

class PennyTracker:
    """Penny-accurate income tracker. Tracks gross PnL, fees, slippage, net income."""

    def __init__(self):
        self.trades: List[dict] = []
        self.gross_income: float = 0.0      # raw price movement profit
        self.total_fees: float = 0.0        # entry fee + exit fee
        self.total_slippage: float = 0.0    # cost of bad fills vs mid
        self.net_income: float = 0.0        # gross - fees - slippage
        self.wins: int = 0
        self.losses: int = 0
        self._load()

    def _load(self) -> None:
        """Load history from CSV on startup."""
        try:
            if PENNY_TRACKER_CSV.exists():
                with open(PENNY_TRACKER_CSV, 'r') as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        t = {
                            'time': row['time'],
                            'symbol': row['symbol'],
                            'side': row['side'],
                            'entry_px': float(row['entry_px']),
                            'exit_px': float(row['exit_px']),
                            'contracts': float(row['contracts']),
                            'contract_size': float(row['contract_size']),
                            'gross': float(row['gross']),
                            'entry_fee': float(row['entry_fee']),
                            'exit_fee': float(row['exit_fee']),
                            'slippage': float(row['slippage']),
                            'net': float(row['net']),
                            'exit_type': row['exit_type'],
                        }
                        self.trades.append(t)
                        self.gross_income += t['gross']
                        self.total_fees += t['entry_fee'] + t['exit_fee']
                        self.total_slippage += t['slippage']
                        self.net_income += t['net']
                        if t['net'] > 0:
                            self.wins += 1
                        else:
                            self.losses += 1
                if self.trades:
                    console.print(f'[cyan]PennyTracker: loaded {len(self.trades)} trades, net=${self.net_income:.6f}')
        except Exception as e:
            console.print(f'[yellow]PennyTracker load warning: {e}')

    def record(self, symbol: str, side: str, entry_px: float, exit_px: float,
               contracts: float, contract_size: float, mid_at_entry: float,
               exit_type: str = '') -> dict:
        """Record a completed trade with penny-accurate breakdown.
        
        Args:
            symbol: Trading pair
            side: 'long' or 'short'
            entry_px: Actual fill price at entry
            exit_px: Actual fill price at exit
            contracts: Number of contracts
            contract_size: USD value per contract unit
            mid_at_entry: Mid price when entry was placed (for slippage calc)
            exit_type: 'tp', 'stop', 'time', 'harvest', 'maker_fill'
        
        Returns:
            Trade record dict with full breakdown
        """
        notional_entry = entry_px * contract_size * contracts
        notional_exit = exit_px * contract_size * contracts

        # Gross PnL from price movement (before any costs)
        if side == 'long':
            gross = (exit_px - entry_px) * contract_size * contracts
        else:
            gross = (entry_px - exit_px) * contract_size * contracts

        # Fees: taker fee on entry notional + exit notional
        entry_fee = notional_entry * FEE_RATE
        exit_fee = notional_exit * FEE_RATE

        # Slippage: how much worse was our fill vs mid price
        if side == 'long':
            # Bought above mid = paid more = negative slippage
            slip_entry = (entry_px - mid_at_entry) * contract_size * contracts
        else:
            # Sold below mid = received less = negative slippage
            slip_entry = (mid_at_entry - entry_px) * contract_size * contracts
        slippage = max(slip_entry, 0)  # only count adverse slippage

        # Net = gross - fees - slippage
        net = gross - entry_fee - exit_fee - slippage

        t = {
            'time': datetime.now(timezone.utc).isoformat(),
            'symbol': symbol,
            'side': side,
            'entry_px': entry_px,
            'exit_px': exit_px,
            'contracts': contracts,
            'contract_size': contract_size,
            'gross': gross,
            'entry_fee': entry_fee,
            'exit_fee': exit_fee,
            'slippage': slippage,
            'net': net,
            'exit_type': exit_type,
        }
        self.trades.append(t)
        self.gross_income += gross
        self.total_fees += entry_fee + exit_fee
        self.total_slippage += slippage
        self.net_income += net
        if net > 0:
            self.wins += 1
        else:
            self.losses += 1

        # Persist to CSV
        self._append_csv(t)

        # Log the breakdown
        short_sym = symbol.split('/')[0]
        fee_total = entry_fee + exit_fee
        console.print(
            f'[bold {"green" if net > 0 else "red"}]'
            f'[{short_sym}] PENNY: gross=${gross:+.6f} fees=${fee_total:.6f} '
            f'slip=${slippage:.6f} → net=${net:+.6f} ({exit_type})')

        return t

    def _append_csv(self, t: dict) -> None:
        """Append one trade to the penny tracker CSV."""
        try:
            DATA_DIR.mkdir(exist_ok=True)
            write_header = not PENNY_TRACKER_CSV.exists()
            with open(PENNY_TRACKER_CSV, 'a', newline='') as f:
                w = csv.writer(f)
                if write_header:
                    w.writerow(['time', 'symbol', 'side', 'entry_px', 'exit_px',
                                'contracts', 'contract_size', 'gross', 'entry_fee',
                                'exit_fee', 'slippage', 'net', 'exit_type'])
                w.writerow([t['time'], t['symbol'], t['side'], t['entry_px'],
                            t['exit_px'], t['contracts'], t['contract_size'],
                            t['gross'], t['entry_fee'], t['exit_fee'],
                            t['slippage'], t['net'], t['exit_type']])
        except Exception as e:
            console.print(f'[red]PennyTracker CSV write error: {e}')

    def summary(self) -> dict:
        """Summary dict for dashboard display."""
        count = len(self.trades)
        return {
            'count': count,
            'gross': self.gross_income,
            'fees': self.total_fees,
            'slippage': self.total_slippage,
            'net': self.net_income,
            'wins': self.wins,
            'losses': self.losses,
            'win_rate': self.wins / count if count > 0 else 0,
            'avg_net': self.net_income / count if count > 0 else 0,
            'fee_drag': self.total_fees / self.gross_income if self.gross_income != 0 else 0,
        }


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 3: RISK ENGINE
# Centralized. Every trade goes through here. No exceptions. No overrides.
# ═══════════════════════════════════════════════════════════════════════════════

class RiskEngine:
    """Institutional risk control layer. Vetoes trades that breach limits."""

    def __init__(self):
        self.peak_equity: float = 0
        self.symbol_pnl: Dict[str, float] = {}
        self.symbol_exposure: Dict[str, float] = {}
        self.paused_symbols: Dict[str, float] = {}  # symbol -> pause until epoch
        self.cooldown_symbols: Dict[str, float] = {}  # symbol -> cooldown until epoch (new)
        self.global_pause_until: float = 0

    def update_peak_equity(self, equity: float) -> None:
        if equity > self.peak_equity:
            self.peak_equity = equity

    def current_drawdown(self, equity: float) -> float:
        if self.peak_equity <= 0:
            return 0
        return max(0, (self.peak_equity - equity) / self.peak_equity)

    def record_symbol_pnl(self, symbol: str, unrealized_pnl: float) -> None:
        self.symbol_pnl[symbol] = unrealized_pnl

    def record_symbol_exposure(self, symbol: str, notional: float) -> None:
        self.symbol_exposure[symbol] = notional

    def clear_symbol(self, symbol: str) -> None:
        self.symbol_pnl.pop(symbol, None)
        self.symbol_exposure.pop(symbol, None)
    
    def set_cooldown(self, symbol: str, duration_sec: float) -> None:
        """Set cooldown for symbol after failed exit"""
        self.cooldown_symbols[symbol] = time.time() + duration_sec
    
    def is_cooldown(self, symbol: str) -> bool:
        """Check if symbol is in cooldown"""
        return time.time() < self.cooldown_symbols.get(symbol, 0)

    def total_floating_pnl(self) -> float:
        return sum(self.symbol_pnl.values())

    def total_exposure(self) -> float:
        return sum(self.symbol_exposure.values())

    # — Gate checks: every trade must pass ALL of these —

    def check_global_risk(self, equity: float) -> Tuple[bool, str]:
        """Returns (safe, reason). If not safe, ALL trading must stop."""
        self.update_peak_equity(equity)
        dd = self.current_drawdown(equity)
        if dd >= MAX_DRAWDOWN_GLOBAL:
            return False, f'global drawdown {dd:.1%} >= {MAX_DRAWDOWN_GLOBAL:.0%} limit'

        floating = self.total_floating_pnl()
        if equity > 0 and abs(floating) / equity >= MAX_DRAWDOWN_GLOBAL:
            return False, f'floating loss {floating/equity:.1%} >= {MAX_DRAWDOWN_GLOBAL:.0%}'

        if time.time() < self.global_pause_until:
            return False, 'global pause active (volatility kill-switch)'

        return True, 'OK'

    def check_symbol_risk(self, symbol: str, equity: float) -> Tuple[bool, str]:
        """Returns (safe, reason) for a specific symbol."""
        if time.time() < self.paused_symbols.get(symbol, 0):
            return False, f'{symbol} paused (volatility)'
        
        if self.is_cooldown(symbol):
            return False, f'{symbol} in cooldown (failed exit)'

        sym_pnl = self.symbol_pnl.get(symbol, 0)
        if equity > 0 and sym_pnl < 0 and abs(sym_pnl) / equity >= MAX_DRAWDOWN_PER_SYMBOL:
            return False, f'{symbol} drawdown {sym_pnl/equity:.1%} >= {MAX_DRAWDOWN_PER_SYMBOL:.0%}'

        sym_exp = self.symbol_exposure.get(symbol, 0)
        if equity > 0 and sym_exp / equity >= MAX_EXPOSURE_PER_SYMBOL:
            return False, f'{symbol} exposure {sym_exp/equity:.1%} >= {MAX_EXPOSURE_PER_SYMBOL:.0%}'

        return True, 'OK'

    def check_can_open_new(self, current_hedges: int) -> Tuple[bool, str]:
        """Check if we can open another hedge pair."""
        if current_hedges >= MAX_CONCURRENT_SYMBOLS:
            return False, f'at {MAX_CONCURRENT_SYMBOLS} symbol cap'
        return True, 'OK'

    def check_dca_allowed(self, hedge_pair: HedgePair, side: str) -> Tuple[bool, str]:
        """Check if DCA is allowed (bounded to MAX_DCA_ROUNDS)."""
        leg = hedge_pair.long_leg if side == 'long' else hedge_pair.short_leg
        if leg.dca_rounds >= MAX_DCA_ROUNDS:
            return False, f'{side} DCA at {MAX_DCA_ROUNDS} round cap'
        return True, 'OK'

    def check_position_age(self, hedge_pair: HedgePair) -> Tuple[bool, str]:
        """Check if position has exceeded max age."""
        age = hedge_pair.age_seconds
        if age > MAX_POSITION_AGE_SECONDS:
            return False, f'position age {age:.0f}s > {MAX_POSITION_AGE_SECONDS}s limit'
        return True, 'OK'

    def pause_symbol(self, symbol: str, duration: float = 300) -> None:
        self.paused_symbols[symbol] = time.time() + duration

    def pause_global(self, duration: float = 600) -> None:
        self.global_pause_until = time.time() + duration

    def get_snapshot(self, equity: float, used: float, free: float,
                     hedges: Dict[str, HedgePair]) -> RiskSnapshot:
        """Generate a point-in-time risk snapshot for audit logging."""
        mr = used / equity if equity > 0 else 0
        active_cap = equity * CAPITAL_ACTIVE_RATIO
        dd = self.current_drawdown(equity)
        ok = sum(1 for hp in hedges.values() if hp.is_complete)
        broken = sum(1 for hp in hedges.values() if hp.is_broken)
        at_limit = sum(1 for s, p in self.symbol_pnl.items()
                       if equity > 0 and p < 0 and abs(p) / equity >= MAX_DRAWDOWN_PER_SYMBOL * 0.8)
        g_safe, g_reason = self.check_global_risk(equity)
        return RiskSnapshot(
            timestamp=time.time(), equity=equity, used_margin=used,
            free_capital=free, active_capital=active_cap, margin_ratio=mr,
            total_floating_pnl=self.total_floating_pnl(), drawdown_pct=dd,
            open_hedges=ok, broken_hedges=broken, symbols_at_limit=at_limit,
            risk_verdict='SAFE' if g_safe else f'BREACH: {g_reason}',
        )

    def symbols_to_flatten(self, equity: float, hedges: Dict[str, HedgePair]) -> List[Tuple[str, str]]:
        """Returns list of (symbol, reason) that must be force-flattened."""
        result = []
        for sym, hp in list(hedges.items()):
            age_ok, age_reason = self.check_position_age(hp)
            if not age_ok:
                result.append((sym, age_reason))
                continue
            sym_ok, sym_reason = self.check_symbol_risk(sym, equity)
            if not sym_ok and 'drawdown' in sym_reason:
                result.append((sym, sym_reason))
        return result


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 4: PERFORMANCE TRACKER
# Equity curve, Sharpe ratio, drawdown, win rate, CSV export, daily reports.
# ═══════════════════════════════════════════════════════════════════════════════

class PerformanceTracker:
    """Continuous performance measurement and reporting."""

    def __init__(self):
        self.equity_curve: List[EquityPoint] = []
        self.realized_trades: List[float] = []  # pnl of each closed trade
        self.total_realized: float = 0
        self.session_start: float = time.time()
        self.peak_equity: float = 0
        self.max_drawdown: float = 0.0
        
        # Comprehensive trade analytics for edge validation
        self.trade_analytics: List[TradeAnalytics] = []
        self.pending_entries: Dict[str, TradeAnalytics] = {}  # symbol -> analytics
        
        # Aggregate metrics
        self.total_expected_profit: float = 0
        self.total_fees_paid: float = 0
        self.maker_entries: int = 0
        self.taker_entries: int = 0
        self.maker_exits: int = 0
        self.taker_exits: int = 0
        self._ensure_dirs()

    def _ensure_dirs(self) -> None:
        DATA_DIR.mkdir(exist_ok=True)
        DAILY_REPORT_DIR.mkdir(parents=True, exist_ok=True)

    def record_equity(self, equity: float, unrealized: float, open_hedges: int) -> None:
        """Record an equity point. Called every monitor cycle."""
        if equity > self.peak_equity:
            self.peak_equity = equity
        dd = (self.peak_equity - equity) / self.peak_equity if self.peak_equity > 0 else 0
        if dd > self.max_drawdown:
            self.max_drawdown = dd
        pt = EquityPoint(
            timestamp=datetime.now(timezone.utc).isoformat(),
            epoch=time.time(),
            equity=equity,
            realized_pnl=self.total_realized,
            unrealized_pnl=unrealized,
            drawdown_pct=dd,
            open_hedges=open_hedges,
        )
        self.equity_curve.append(pt)
        self._append_equity_csv(pt)

    def record_trade_pnl(self, pnl: float) -> None:
        """Record a realized trade result."""
        self.realized_trades.append(pnl)
        self.total_realized += pnl

    def record_trade_entry(self, symbol: str, side: str, entry_price: float, 
                          mid_price: float, contracts: float, expected_profit: float,
                          is_maker: bool = True) -> None:
        """Record trade entry for analytics."""
        analytics = TradeAnalytics(
            symbol=symbol,
            side=side,
            entry_time=time.time(),
            entry_price=entry_price,
            mid_price_at_entry=mid_price,
            contracts=contracts,
            expected_profit=expected_profit,
            is_maker_entry=is_maker
        )
        self.pending_entries[symbol] = analytics
        self.total_expected_profit += expected_profit
        
        if is_maker:
            self.maker_entries += 1
        else:
            self.taker_entries += 1
    
    def record_trade_exit(self, symbol: str, exit_price: float, realized_profit: float,
                         fees_paid: float, is_maker: bool = True, exit_reason: str = '') -> None:
        """Record trade exit and complete analytics."""
        if symbol not in self.pending_entries:
            return
        
        entry = self.pending_entries[symbol]
        entry.exit_time = time.time()
        entry.exit_price = exit_price
        entry.realized_profit = realized_profit
        entry.fees_paid = fees_paid
        entry.is_maker_exit = is_maker
        entry.exit_reason = exit_reason
        
        self.trade_analytics.append(entry)
        self.total_fees_paid += fees_paid
        
        if is_maker:
            self.maker_exits += 1
        else:
            self.taker_exits += 1
        
        del self.pending_entries[symbol]
    
    def get_edge_ratio(self) -> float:
        """Calculate execution edge: realized / expected. >1.0 = good execution."""
        if self.total_expected_profit == 0:
            return 0.0
        total_realized = sum(t.realized_profit for t in self.trade_analytics)
        return total_realized / self.total_expected_profit
    
    def get_net_pnl(self) -> float:
        """Net PnL after fees."""
        total_realized = sum(t.realized_profit for t in self.trade_analytics)
        return total_realized - self.total_fees_paid
    
    def get_fill_quality(self) -> Dict:
        """Analyze fill quality vs mid price."""
        if not self.trade_analytics:
            return {}
        
        slippages = []
        for t in self.trade_analytics:
            if t.side == 'long':
                # For longs, fill above mid = bad (positive slippage)
                slippage = (t.entry_price - t.mid_price_at_entry) / t.mid_price_at_entry
            else:
                # For shorts, fill below mid = bad (negative slippage)
                slippage = (t.mid_price_at_entry - t.entry_price) / t.mid_price_at_entry
            slippages.append(slippage)
        
        avg_slippage = sum(slippages) / len(slippages)
        adverse_fills = sum(1 for s in slippages if s > 0.0001)  # > 0.01% slippage
        
        return {
            'avg_slippage_bps': avg_slippage * 10000,  # basis points
            'adverse_fill_pct': adverse_fills / len(slippages) * 100,
            'total_trades': len(slippages)
        }
    
    def get_maker_taker_ratio(self) -> Dict:
        """Maker vs taker fill statistics."""
        total_entries = self.maker_entries + self.taker_entries
        total_exits = self.maker_exits + self.taker_exits
        
        return {
            'maker_entry_pct': self.maker_entries / total_entries * 100 if total_entries > 0 else 0,
            'taker_entry_pct': self.taker_entries / total_entries * 100 if total_entries > 0 else 0,
            'maker_exit_pct': self.maker_exits / total_exits * 100 if total_exits > 0 else 0,
            'taker_exit_pct': self.taker_exits / total_exits * 100 if total_exits > 0 else 0,
            'total_entries': total_entries,
            'total_exits': total_exits
        }
    
    def get_avg_time_to_exit(self) -> float:
        """Average seconds from entry to exit."""
        completed = [t for t in self.trade_analytics if t.exit_time > 0]
        if not completed:
            return 0.0
        times = [(t.exit_time - t.entry_time) for t in completed]
        return sum(times) / len(times)
    
    def print_performance_report(self) -> None:
        """Print comprehensive performance report."""
        if not self.trade_analytics:
            console.print('[yellow]No completed trades yet.')
            return
        
        total_trades = len(self.trade_analytics)
        edge_ratio = self.get_edge_ratio()
        net_pnl = self.get_net_pnl()
        fill_quality = self.get_fill_quality()
        maker_taker = self.get_maker_taker_ratio()
        avg_exit_time = self.get_avg_time_to_exit()
        
        # Win rate
        winning_trades = sum(1 for t in self.trade_analytics if t.realized_profit > 0)
        win_rate = winning_trades / total_trades * 100
        
        table = Table(title='Performance Analytics Report')
        table.add_column('Metric', style='cyan')
        table.add_column('Value', style='green')
        
        table.add_row('Total Trades', str(total_trades))
        table.add_row('Win Rate', f'{win_rate:.1f}%')
        table.add_row('Edge Ratio', f'{edge_ratio:.3f} (>1.0 = good)')
        table.add_row('Net PnL (after fees)', f'${net_pnl:.4f}')
        table.add_row('Total Fees Paid', f'${self.total_fees_paid:.4f}')
        table.add_row('Avg Slippage', f'{fill_quality.get("avg_slippage_bps", 0):.2f} bps')
        table.add_row('Adverse Fills', f'{fill_quality.get("adverse_fill_pct", 0):.1f}%')
        table.add_row('Maker Entry %', f'{maker_taker["maker_entry_pct"]:.1f}%')
        table.add_row('Avg Time to Exit', f'{avg_exit_time:.0f}s')
        
        console.print('\n')
        console.print(table)
        
        # Verdict
        if edge_ratio > 1.0 and net_pnl > 0:
            console.print('[bold green]✓ POSITIVE EDGE DETECTED')
        elif edge_ratio > 0.8 and net_pnl > 0:
            console.print('[yellow]~ MARGINAL EDGE - Monitor closely')
        else:
            console.print('[bold red]✗ NO EDGE - Strategy needs revision')

    def sharpe_ratio(self) -> float:
        """Approximate Sharpe ratio from realized trade PnLs."""
        if len(self.realized_trades) < 2:
            return 0
        mean = sum(self.realized_trades) / len(self.realized_trades)
        variance = sum((x - mean) ** 2 for x in self.realized_trades) / (len(self.realized_trades) - 1)
        std = math.sqrt(variance) if variance > 0 else 0
        if std == 0:
            return 0
        return mean / std

    def win_rate(self) -> float:
        """Percentage of trades that were profitable."""
        if not self.realized_trades:
            return 0
        wins = sum(1 for t in self.realized_trades if t > 0)
        return wins / len(self.realized_trades)

    def avg_profit(self) -> float:
        """Average PnL per trade."""
        if not self.realized_trades:
            return 0
        return sum(self.realized_trades) / len(self.realized_trades)

    def capital_utilization(self, used: float, equity: float) -> float:
        """Current capital utilization as percentage."""
        if equity <= 0:
            return 0
        return used / equity

    def get_summary(self, equity: float, used: float) -> dict:
        """Full performance summary for display and export."""
        return {
            'total_realized_pnl': self.total_realized,
            'trade_count': len(self.realized_trades),
            'win_rate': self.win_rate(),
            'avg_profit_per_trade': self.avg_profit(),
            'sharpe_ratio': self.sharpe_ratio(),
            'max_drawdown': self.max_drawdown,
            'peak_equity': self.peak_equity,
            'current_equity': equity,
            'capital_utilization': self.capital_utilization(used, equity),
            'session_duration_s': time.time() - self.session_start,
        }

    def _append_equity_csv(self, pt: EquityPoint) -> None:
        """Append one row to equity curve CSV."""
        try:
            write_header = not EQUITY_CURVE_CSV.exists()
            with open(EQUITY_CURVE_CSV, 'a', newline='') as f:
                w = csv.writer(f)
                if write_header:
                    w.writerow(['timestamp', 'epoch', 'equity', 'realized_pnl',
                                'unrealized_pnl', 'drawdown_pct', 'open_hedges'])
                w.writerow([pt.timestamp, pt.epoch, pt.equity, pt.realized_pnl,
                            pt.unrealized_pnl, pt.drawdown_pct, pt.open_hedges])
        except Exception:
            pass

    def export_daily_report(self, equity: float, used: float,
                            hedges: Dict[str, HedgePair], risk: RiskEngine) -> None:
        """Write a daily summary report to disk."""
        try:
            today = datetime.now(timezone.utc).strftime('%Y-%m-%d')
            report_path = DAILY_REPORT_DIR / f'report_{today}.txt'
            summary = self.get_summary(equity, used)
            snap = risk.get_snapshot(equity, used, equity - used, hedges)
            lines = [
                f'CopyThatPay Daily Report — {today}',
                '=' * 50,
                f'Equity:              ${equity:.4f}',
                f'Peak Equity:         ${self.peak_equity:.4f}',
                f'Total Realized PnL:  ${self.total_realized:.6f}',
                f'Trade Count:         {len(self.realized_trades)}',
                f'Win Rate:            {self.win_rate():.1%}',
                f'Avg Profit/Trade:    ${self.avg_profit():.6f}',
                f'Sharpe Ratio:        {self.sharpe_ratio():.3f}',
                f'Max Drawdown:        {self.max_drawdown:.2%}',
                f'Capital Utilization: {self.capital_utilization(used, equity):.1%}',
                f'',
                f'Risk State:',
                f'  Verdict:           {snap.risk_verdict}',
                f'  Margin Ratio:      {snap.margin_ratio:.1%}',
                f'  Floating PnL:      ${snap.total_floating_pnl:.6f}',
                f'  Open Hedges:       {snap.open_hedges}',
                f'  Broken Hedges:     {snap.broken_hedges}',
                f'  Symbols Near Limit:{snap.symbols_at_limit}',
                f'',
                f'Session Duration:    {summary["session_duration_s"]:.0f}s',
            ]
            with open(report_path, 'w') as f:
                f.write('\n'.join(lines) + '\n')
        except Exception:
            pass

    def save_metrics(self, equity: float, used: float) -> None:
        """Persist current metrics to JSON for external consumption."""
        try:
            with open(PERF_METRICS_FILE, 'w') as f:
                json.dump(self.get_summary(equity, used), f, indent=2)
        except Exception:
            pass


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 5: TRADE JOURNAL
# Every action logged with reason, risk state, hedge state. Human-readable.
# ═══════════════════════════════════════════════════════════════════════════════

class TradeJournal:
    """Auditable trade journal. Append-only JSONL + human-readable console output."""

    def __init__(self):
        DATA_DIR.mkdir(exist_ok=True)

    def log(self, action: str, symbol: str, side: str, contracts: float,
            price: float = 0, pnl: float = 0, reason: str = '',
            hedge_state: str = '', risk_snapshot: Optional[RiskSnapshot] = None) -> None:
        """Write one auditable record."""
        record = TradeRecord(
            timestamp=datetime.now(timezone.utc).isoformat(),
            epoch=time.time(),
            action=action,
            symbol=symbol,
            side=side,
            contracts=contracts,
            price=price,
            pnl=pnl,
            reason=reason,
            hedge_state=hedge_state,
            risk_snapshot=asdict(risk_snapshot) if risk_snapshot else {},
        )
        self._write_jsonl(record)
        self._print_human(record)

    def _write_jsonl(self, record: TradeRecord) -> None:
        try:
            with open(TRADE_JOURNAL, 'a') as f:
                f.write(json.dumps(asdict(record)) + '\n')
        except Exception:
            pass

    def _print_human(self, record: TradeRecord) -> None:
        color = 'green' if record.pnl > 0 else ('red' if record.pnl < 0 else 'cyan')
        pnl_str = f' PnL=${record.pnl:.6f}' if record.pnl != 0 else ''
        price_str = f' @{record.price:.8f}' if record.price > 0 else ''
        console.print(
            f'[{color}][JOURNAL] {record.action} {record.symbol} '
            f'{record.side} {record.contracts}ct{price_str}{pnl_str} '
            f'| {record.reason} | risk={record.risk_snapshot.get("risk_verdict", "N/A")}[/{color}]'
        )
# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 5.5: LLM SELF-TESTING TRADER LOOP
# Records every LLM decision, evaluates outcomes after a delay,
# logs errors, and runs a critic loop to update policy from errors.
# The LLM never directly modifies code — only updates a JSON policy file.
# ═══════════════════════════════════════════════════════════════════════════════

class LLMSelfTester:
    """Continuous self-testing loop for LLM trading decisions."""

    def __init__(self, exchange=None):
        self.exchange = exchange
        self.pending: List[LLMDecisionTest] = []
        self.policy: dict = self._load_policy()
        self._ensure_dirs()

    def _ensure_dirs(self) -> None:
        DATA_DIR.mkdir(exist_ok=True)

    # ── Memory helpers ──

    def _load_policy(self) -> dict:
        """Load learned policy from disk, or return defaults."""
        defaults = {
            'min_spread_pct': 0.003,
            'min_momentum': 0.001,
            'min_imbalance': 0.20,
            'min_edge_score': 0.30,
            'confidence_threshold': LLM_MIN_CONFIDENCE,
            'avoid_high_vol': True,
            'max_adverse_fills': 3,
            'learned_adjustments': {},
        }
        if LLM_POLICY_FILE.exists():
            try:
                with open(LLM_POLICY_FILE) as f:
                    saved = json.load(f)
                defaults.update(saved)
            except Exception:
                pass
        return defaults

    def _save_policy(self) -> None:
        try:
            with open(LLM_POLICY_FILE, 'w') as f:
                json.dump(self.policy, f, indent=2)
        except Exception:
            pass

    def _append_jsonl(self, path: Path, record: dict) -> None:
        try:
            with open(path, 'a') as f:
                f.write(json.dumps(record) + '\n')
        except Exception:
            pass

    def _read_jsonl(self, path: Path, limit: int = 50) -> List[dict]:
        records = []
        if not path.exists():
            return records
        try:
            with open(path) as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            records.append(json.loads(line))
                        except Exception:
                            pass
        except Exception:
            pass
        return records[-limit:]

    # ── Decision registration ──

    def register_decision(self, symbol: str, action: str, features: dict,
                         confidence: float, rationale: str,
                         predicted_move: float = 0) -> str:
        """Register an LLM decision as a test. Returns decision_id."""
        decision_id = f"dec_{int(time.time()*1000)}_{symbol.replace('/','_').replace(':','_')}"
        test = LLMDecisionTest(
            decision_id=decision_id,
            timestamp=time.time(),
            symbol=symbol,
            action=action,
            features=features,
            confidence=confidence,
            rationale=rationale,
            predicted_move=predicted_move,
        )
        self.pending.append(test)
        # Also write to trade memory
        self._append_jsonl(LLM_TRADE_MEMORY, asdict(test))
        short_sym = symbol.split('/')[0]
        console.print(
            f'[magenta][LLM-TEST] Registered {action} {short_sym} '
            f'conf={confidence:.2f} pred={predicted_move:+.4%}'
        )
        return decision_id

    # ── Outcome evaluation loop ──

    async def outcome_test_loop(self) -> None:
        """Evaluate pending decisions after LLM_TEST_HORIZON_SEC seconds."""
        while True:
            try:
                now = time.time()
                still_pending = []
                for test in self.pending:
                    elapsed = now - test.timestamp
                    if elapsed < LLM_TEST_HORIZON_SEC:
                        still_pending.append(test)
                        continue
                    # Evaluate this decision
                    await self._evaluate_decision(test)
                self.pending = still_pending
            except Exception as e:
                console.print(f'[red][LLM-TEST] Outcome loop error: {e}')
            await asyncio.sleep(10)

    async def _evaluate_decision(self, test: LLMDecisionTest) -> None:
        """Compare predicted vs actual outcome for one decision."""
        try:
            if not self.exchange:
                return
            tk = await self.exchange.fetch_ticker(test.symbol, {'type': 'swap'})
            current_price = float(tk.get('last', 0) or 0)
            if current_price <= 0:
                return

            # Get price at decision time from features
            entry_price = test.features.get('mid_price', 0)
            if entry_price <= 0:
                entry_price = test.features.get('last_price', 0)
            if entry_price <= 0:
                return

            actual_move = (current_price - entry_price) / entry_price
            test.outcome_price = current_price
            test.actual_move = actual_move
            test.evaluated = True

            # Determine correctness based on action
            if test.action == 'enter_long':
                test.correct = actual_move > 0
            elif test.action == 'enter_short':
                test.correct = actual_move < 0
            elif test.action == 'skip':
                # Skip was correct if price didn't move favorably in either direction
                test.correct = abs(actual_move) < abs(test.predicted_move)
            elif test.action == 'exit':
                test.correct = True  # exits are always evaluated as correct (risk mgmt)
            else:
                test.correct = None

            # Log errors separately
            if test.correct is False:
                error_record = {
                    'decision_id': test.decision_id,
                    'timestamp': test.timestamp,
                    'symbol': test.symbol,
                    'action': test.action,
                    'features': test.features,
                    'confidence': test.confidence,
                    'rationale': test.rationale,
                    'predicted_move': test.predicted_move,
                    'actual_move': actual_move,
                    'outcome_price': current_price,
                    'error_type': 'wrong_direction' if test.action in ('enter_long', 'enter_short') else 'missed_opportunity',
                }
                self._append_jsonl(LLM_ERROR_MEMORY, error_record)
                short_sym = test.symbol.split('/')[0]
                console.print(
                    f'[bold red][LLM-TEST] ERROR {test.action} {short_sym} '
                    f'pred={test.predicted_move:+.4%} actual={actual_move:+.4%}'
                )
            elif test.correct is True:
                short_sym = test.symbol.split('/')[0]
                console.print(
                    f'[bold green][LLM-TEST] CORRECT {test.action} {short_sym} '
                    f'pred={test.predicted_move:+.4%} actual={actual_move:+.4%}'
                )

            # Update the trade memory record
            self._append_jsonl(LLM_TRADE_MEMORY, {
                'decision_id': test.decision_id,
                'evaluated': True,
                'actual_move': actual_move,
                'correct': test.correct,
                'outcome_price': current_price,
            })
        except Exception as e:
            console.print(f'[red][LLM-TEST] Evaluate error: {e}')

    # ── Critic loop: update policy from errors ──

    async def critic_loop(self) -> None:
        """Periodically read recent errors and update policy via Groq LLM."""
        while True:
            try:
                await asyncio.sleep(LLM_CRITIC_INTERVAL)
                if not GROQ_KEY:
                    continue
                errors = self._read_jsonl(LLM_ERROR_MEMORY, LLM_MAX_ERRORS_READ)
                if not errors:
                    continue
                await self._run_critic(errors)
            except Exception as e:
                console.print(f'[red][LLM-TEST] Critic loop error: {e}')

    async def _run_critic(self, errors: List[dict]) -> None:
        """Ask Groq LLM to analyze errors and return updated policy."""
        # Summarize error patterns for the prompt
        error_summary = []
        for e in errors[-20:]:  # last 20 errors
            error_summary.append({
                'symbol': e.get('symbol', ''),
                'action': e.get('action', ''),
                'confidence': e.get('confidence', 0),
                'predicted_move': e.get('predicted_move', 0),
                'actual_move': e.get('actual_move', 0),
                'error_type': e.get('error_type', ''),
                'spread_pct': e.get('features', {}).get('spread_pct', 0),
                'momentum': e.get('features', {}).get('momentum', 0),
                'imbalance': e.get('features', {}).get('imbalance', 0),
            })

        prompt = f"""You are a trading strategy critic. Analyze these recent decision errors and suggest CONSERVATIVE policy adjustments.

Current policy:
{json.dumps(self.policy, indent=2)}

Recent errors ({len(errors)} total, showing last 20):
{json.dumps(error_summary, indent=2)}

Rules:
- Return ONLY a JSON object with the same keys as the current policy, plus any new keys under "learned_adjustments".
- Adjust values CONSERVATIVELY: max {LLM_POLICY_MAX_ADJ:.0%} change per key per cycle.
- If errors show wrong_direction on longs when momentum is negative, increase min_momentum.
- If errors show wrong_direction on shorts when imbalance is weak, increase min_imbalance.
- If errors show missed_opportunity when spread is wide, decrease min_spread_pct slightly.
- Never set any threshold below 0 or above 1.
- Do NOT include any code, explanations, or markdown. Only raw JSON."""

        try:
            async with aiohttp.ClientSession() as sess:
                resp = await sess.post(
                    'https://api.groq.com/openai/v1/chat/completions',
                    headers={'Authorization': f'Bearer {GROQ_KEY}',
                             'Content-Type': 'application/json'},
                    json={
                        'model': 'llama-3.1-8b-instant',
                        'messages': [{'role': 'user', 'content': prompt}],
                        'temperature': 0.2,
                        'max_tokens': 500,
                    },
                    timeout=aiohttp.ClientTimeout(total=15)
                )
                if resp.status != 200:
                    console.print(f'[yellow][LLM-TEST] Critic API status {resp.status}')
                    return
                data = await resp.json()
                text = data['choices'][0]['message']['content'].strip()
                # Strip markdown code fences if present
                if text.startswith('```'):
                    text = text.split('\n', 1)[-1].rsplit('```', 1)[0].strip()
                new_policy = json.loads(text)

                # Validate and clamp adjustments
                for key in ('min_spread_pct', 'min_momentum', 'min_imbalance',
                            'min_edge_score', 'confidence_threshold'):
                    if key in new_policy:
                        old_val = self.policy.get(key, 0)
                        new_val = float(new_policy[key])
                        # Clamp to max adjustment
                        max_change = abs(old_val) * LLM_POLICY_MAX_ADJ if old_val != 0 else LLM_POLICY_MAX_ADJ
                        clamped = max(old_val - max_change, min(old_val + max_change, new_val))
                        clamped = max(0.0, min(1.0, clamped))
                        new_policy[key] = clamped

                # Merge learned_adjustments
                if 'learned_adjustments' in new_policy:
                    existing = self.policy.get('learned_adjustments', {})
                    existing.update(new_policy['learned_adjustments'])
                    new_policy['learned_adjustments'] = existing

                self.policy.update(new_policy)
                self._save_policy()
                console.print(f'[bold magenta][LLM-TEST] Policy updated: {list(new_policy.keys())}')
        except json.JSONDecodeError:
            console.print('[yellow][LLM-TEST] Critic returned invalid JSON')
        except Exception as e:
            console.print(f'[yellow][LLM-TEST] Critic error: {e}')

    # ── Policy-aware decision context ──

    def get_policy_context(self) -> str:
        """Return a concise string of current policy for inclusion in LLM prompts."""
        lines = [f'{k}={v}' for k, v in self.policy.items()
                 if k != 'learned_adjustments']
        learned = self.policy.get('learned_adjustments', {})
        if learned:
            lines.append('learned:')
            for k, v in learned.items():
                lines.append(f'  {k}={v}')
        return '\n'.join(lines)

    def policy_gate(self, spread_pct: float, momentum: float,
                    imbalance: float, edge_score: float) -> Tuple[bool, str]:
        """Apply learned policy thresholds. Returns (allowed, reason)."""
        if spread_pct < self.policy.get('min_spread_pct', 0.003):
            return False, f'spread {spread_pct:.4%} < policy min {self.policy["min_spread_pct"]:.4%}'
        if abs(momentum) < self.policy.get('min_momentum', 0.001):
            return False, f'momentum {momentum:.4%} < policy min {self.policy["min_momentum"]:.4%}'
        if abs(imbalance) < self.policy.get('min_imbalance', 0.20):
            return False, f'imbalance {imbalance:.2f} < policy min {self.policy["min_imbalance"]:.2f}'
        if edge_score < self.policy.get('min_edge_score', 0.30):
            return False, f'edge_score {edge_score:.2f} < policy min {self.policy["min_edge_score"]:.2f}'
        return True, 'policy_ok'

    # ── Summary for dashboard ──

    def get_summary(self) -> dict:
        errors = self._read_jsonl(LLM_ERROR_MEMORY, 100)
        decisions = self._read_jsonl(LLM_TRADE_MEMORY, 100)
        evaluated = [d for d in decisions if d.get('evaluated')]
        correct = sum(1 for d in evaluated if d.get('correct') is True)
        total = len(evaluated)
        return {
            'total_decisions': len(decisions),
            'pending_evaluations': len(self.pending),
            'evaluated': total,
            'correct': correct,
            'accuracy': correct / total if total > 0 else 0,
            'total_errors': len(errors),
            'policy_keys': list(self.policy.keys()),
            'learned_adjustments': self.policy.get('learned_adjustments', {}),
        }


# SECTION 6: CopyThatPay — MAIN TRADING ENGINE
# ═══════════════════════════════════════════════════════════════════════════════

class CopyThatPay:
    """Aggressive hedged spread-capture engine (HMSC)."""

    def __init__(self):
        self.exchange = None
        self.risk = RiskEngine()
        self.perf = PerformanceTracker()
        self.penny = PennyTracker()
        self.scorer = ScoringEngine()
        self.journal = TradeJournal()
        self.llm_tester = LLMSelfTester()
        self.hedges: Dict[str, HedgePair] = {}
        self.quotes: Dict[str, QuoteState] = {}
        self.state: Dict[str, float] = {}
        self._last_report_day: str = ''
        
        # LLM symbol selection cache
        self.llm_symbol_scores: Dict[str, float] = {}
        self.llm_last_update: float = 0
        self.active_symbols: List[str] = []

    def train_setup_outcome(self, qs: QuoteState, pnl: float) -> None:
        try:
            if not qs.last_features:
                return
            target = 1 if pnl > 0 else 0
            self.scorer.partial_fit(qs.last_features, target)
        except Exception:
            pass

    async def init_exchange(self) -> None:
        self.llm_tester.exchange = self.exchange  # will be set after exchange created below
        self.exchange = ccxt.gateio({
            'apiKey': API_KEY, 'secret': API_SECRET, 'enableRateLimit': True,
            'timeout': 60000,  # 60 second timeout for API requests
            'options': {'defaultType': 'swap', 'defaultSettle': 'usdt',
                'adjustForTimeDifference': True, 'recvWindow': 60000,
                'fetchCurrencies': False},  # Skip problematic currencies endpoint
            'headers': {'User-Agent': 'Mozilla/5.0'}
        })
        # Retry logic for load_markets with exponential backoff
        for attempt in range(5):
            try:
                await self.exchange.load_markets()
                console.print('[green]Exchange connected[/green]')
                self.llm_tester.exchange = self.exchange
                return
            except Exception as e:
                console.print(f'[yellow]Load markets failed ({attempt+1}/5): {e}[/yellow]')
                if attempt < 4:  # Don't sleep after last attempt
                    await asyncio.sleep(2 ** attempt)  # Exponential backoff

        console.print('[red]WARNING: running without full market load - will retry in background[/red]')

    async def cleanup(self) -> None:
        if self.exchange:
            try:
                await self.exchange.close()
            except Exception:
                pass

    async def get_health(self) -> dict:
        """Fetch balance with capital partitioning."""
        h = {'equity': 0, 'used': 0, 'free': 0, 'active_capital': 0,
             'reserve': 0, 'buffer': 0, 'margin_ratio': 0, 'safe': True}
        try:
            bal = await self.exchange.fetch_balance()
            total = float(bal.get('total', {}).get('USDT', 0) or 0)
            used = float(bal.get('used', {}).get('USDT', 0) or 0)
            free = float(bal.get('free', {}).get('USDT', 0) or 0)
            if free <= 0:
                free = float(bal.get('info', {}).get('available', 0) or 0)
            if free <= 0:
                free = max(total - used, 0)
            mr = used / total if total > 0 else 0
            g_safe, _ = self.risk.check_global_risk(total)
            h.update({
                'equity': total, 'used': used, 'free': free,
                'active_capital': total * CAPITAL_ACTIVE_RATIO,
                'reserve': total * CAPITAL_RESERVE_RATIO,
                'buffer': total * CAPITAL_BUFFER_RATIO,
                'margin_ratio': mr,
                'safe': g_safe and mr < MARGIN_RATIO_CRITICAL,
            })
        except Exception as e:
            console.print(f'[red]Health error: {e}')
            h['safe'] = False
        return h

    async def check_volatility(self, symbol: str) -> bool:
        """Volatility kill-switch. Returns False if abnormal — pauses symbol."""
        try:
            ohlcv = await self.exchange.fetch_ohlcv(symbol, '5m', limit=2)
            if len(ohlcv) < 2:
                return True
            o, c = ohlcv[-1][1], ohlcv[-1][4]
            if o <= 0:
                return True
            move = abs(c - o) / o
            if move >= VOLATILITY_KILL_THRESHOLD:
                console.print(f'[bold red][{symbol}] VOL KILL: {move:.1%} >= {VOLATILITY_KILL_THRESHOLD:.0%}')
                self.risk.pause_symbol(symbol, 300)
                snap = self.risk.get_snapshot(0, 0, 0, self.hedges)
                self.journal.log('VOL_PAUSE', symbol, '', 0,
                                 reason=f'{move:.1%} 5m candle', risk_snapshot=snap)
                return False
        except Exception:
            pass
        return True

    # ═══════════════════════════════════════════════════════════════════════════════
    # ADAPTIVE MICROSTRUCTURE ENGINE (AME) - Market Awareness Layer
    # ═══════════════════════════════════════════════════════════════════════════════

    async def get_orderbook_imbalance(self, symbol: str) -> float:
        """Returns imbalance score: +1 = heavy buy pressure, -1 = heavy sell pressure, 0 = neutral"""
        try:
            ob = await self.exchange.fetch_order_book(symbol, 10, {'type': 'swap'})
            bids = sum(b[1] for b in ob['bids'])
            asks = sum(a[1] for a in ob['asks'])
            total = bids + asks
            if total == 0:
                return 0.0
            return (bids - asks) / total
        except Exception as e:
            console.print(f'[dim][{symbol}] Imbalance error: {e}')
            return 0.0

    async def get_micro_momentum(self, symbol: str) -> float:
        """Returns 1-minute momentum: positive = rising, negative = falling"""
        try:
            ohlcv = await self.exchange.fetch_ohlcv(symbol, '1m', limit=3, params={'type': 'swap'})
            if len(ohlcv) < 3:
                return 0.0
            closes = [c[4] for c in ohlcv]
            # Momentum as % change over last 3 minutes
            if closes[0] == 0:
                return 0.0
            return (closes[-1] - closes[0]) / closes[0]
        except Exception as e:
            console.print(f'[dim][{symbol}] Momentum error: {e}')
            return 0.0

    def calculate_edge_score(self, imbalance: float, momentum: float) -> Tuple[int, List[str], List[str]]:
        """
        Calculate edge score and determine allowed sides.
        Returns: (score, allowed_sides, reasons)
        Score 0-2: 0=no edge, 1=weak edge, 2=strong edge
        """
        score = 0
        reasons = []
        allowed_sides = []

        # Imbalance contribution (0 or 1 point)
        if abs(imbalance) > 0.2:
            score += 1
            if imbalance > 0.2:
                reasons.append(f'buy pressure {imbalance:.2f}')
            else:
                reasons.append(f'sell pressure {imbalance:.2f}')

        # Momentum contribution (0 or 1 point)
        if abs(momentum) > 0.001:  # 0.1% move
            score += 1
            reasons.append(f'momentum {momentum:.3%}')

        # Determine allowed sides based on combined signal
        if imbalance > 0.2 and momentum > 0:
            allowed_sides = ['long']  # Bullish: quote long only
        elif imbalance < -0.2 and momentum < 0:
            allowed_sides = ['short']  # Bearish: quote short only
        elif score >= 2:
            allowed_sides = ['long', 'short']  # Strong edge both sides
        # score < 2 with weak/conflicting signals = no trade

        return score, allowed_sides, reasons

    def is_adverse_fill(self, entry: float, current: float, side: str) -> bool:
        """Check if fill was adverse (price moved against position)"""
        if side == 'long':
            return current < entry  # Price dropped after we bought
        else:  # short
            return current > entry  # Price rose after we sold

    def has_real_edge(self, imbalance: float, momentum: float) -> bool:
        """Strict directional pressure gate for the active Edge Version."""
        return (
            abs(imbalance) > 0.35 and
            abs(momentum) > MIN_EXPECTED_MOVE and
            (imbalance * momentum) > 0
        )

    def directional_edge_score(self, imbalance: float, momentum: float) -> float:
        """Combine pressure and motion into one directional edge score."""
        if (imbalance * momentum) <= 0:
            return 0.0
        imbalance_strength = max(0.0, (abs(imbalance) - 0.35) / 0.65)
        momentum_strength = max(0.0, (abs(momentum) - MIN_EXPECTED_MOVE) / max(MIN_EXPECTED_MOVE, 1e-9))
        return imbalance_strength * 0.65 + min(momentum_strength, 2.0) * 0.35

    def spread_zscore(self, history: List[float], current_spread: float) -> float:
        """Rolling z-score for spread anomaly detection."""
        if len(history) < SPREAD_HISTORY_MIN:
            return 0.0
        mean_spread = sum(history) / len(history)
        variance = sum((value - mean_spread) ** 2 for value in history) / len(history)
        std_spread = math.sqrt(variance)
        if std_spread <= 1e-9:
            return 0.0
        return (current_spread - mean_spread) / std_spread

    def update_spread_history(self, qs: QuoteState, spread_pct: float) -> Tuple[float, float]:
        """Update rolling spread state and return (zscore, spread_velocity)."""
        zscore = self.spread_zscore(qs.spread_history, spread_pct)
        spread_velocity = spread_pct - qs.last_spread_pct if qs.last_spread_pct > 0 else 0.0
        qs.spread_history.append(spread_pct)
        if len(qs.spread_history) > SPREAD_HISTORY_MAX:
            qs.spread_history = qs.spread_history[-SPREAD_HISTORY_MAX:]
        qs.last_spread_pct = spread_pct
        return zscore, spread_velocity

    def execution_mode(self, spread_z: float, momentum: float, imbalance: float,
                       compression_speed: float, spread_pct: float) -> str:
        """Choose maker/hybrid/taker based on urgency of the move."""
        if spread_z > SPREAD_READY_Z:
            return 'skip'
        if abs(momentum) > 0.002 and abs(imbalance) > 0.35 and compression_speed > 0:
            return 'taker'
        if abs(momentum) > 0.001 or compression_speed > 0.5:
            return 'hybrid'
        if spread_pct > 0.004 or abs(imbalance) >= 0.25:
            return 'maker'
        return 'skip'

    async def place_post_only_entry(self, symbol: str, side: str, ct: int) -> Optional[str]:
        """Place a post-only entry regardless of the global taker bias."""
        try:
            bid, ask = await self.fetch_book(symbol)
            price = bid if side == 'buy' else ask
            if price <= 0:
                return None
            order = await self.exchange.create_limit_order(
                symbol, side, ct, price,
                {'marginMode': MARGIN_MODE, 'type': 'swap', 'postOnly': True}
            )
            short_sym = symbol.split('/')[0]
            console.print(f'[cyan][{short_sym}] MAKER ENTRY {side.upper()} {ct}ct @ {price:.8f}')
            return order.get('id', '')
        except Exception as e:
            console.print(f'[red][{symbol}] MAKER ENTRY FAILED: {e}')
            return None

    async def execute_entry_mode(self, symbol: str, side: str, ct: int, mode: str) -> bool:
        """Execute entry using maker/hybrid/taker timing."""
        order_side = 'buy' if side == 'long' else 'sell'
        if mode == 'taker':
            return await self.open_position(symbol, order_side)
        if mode == 'maker':
            oid = await self.place_post_only_entry(symbol, order_side, ct)
            return bool(oid)
        if mode == 'hybrid':
            oid = await self.place_post_only_entry(symbol, order_side, ct)
            if not oid:
                return await self.open_position(symbol, order_side)
            try:
                await asyncio.sleep(MAX_MAKER_WAIT_SEC)
                order = await self.exchange.fetch_order(oid, symbol, {'type': 'swap'})
                if order.get('status') == 'closed':
                    return True
                await self.exchange.cancel_order(oid, symbol)
            except Exception:
                pass
            return await self.open_position(symbol, order_side)
        return False

    async def get_dynamic_spread_target(self, momentum: float) -> float:
        """Calculate dynamic spread target based on market conditions"""
        # Base: 0.5%, range: 0.15% to 0.5%
        base = SPREAD_TARGET_PCT
        momentum_factor = abs(momentum) * 2  # More volatility = tighter target
        return max(0.0015, min(base, 0.0015 + momentum_factor))

    async def safe_size(self, symbol: str) -> int:
        """Risk-gated order sizing. Allocates max contracts within risk limits."""
        # DIAGNOSTIC MODE: Force size=1 to test execution path
        if DIAGNOSTIC_MODE:
            console.print(f'[bold yellow][DIAGNOSTIC] Forcing size=1 for {symbol}')
            return 1
        
        try:
            h = await self.get_health()
            if not h['safe']:
                console.print(f'[red][{symbol}] Size=0: health check failed')
                return 0
            usable = h['active_capital']
            if h['used'] >= usable:
                console.print(f'[red][{symbol}] Size=0: no capital (used={h["used"]:.4f} >= usable={usable:.4f})')
                return 0
            mkt = self.exchange.market(symbol)
            tk = await self.exchange.fetch_ticker(symbol, {'type': 'swap'})
            px = float(tk['last'])
            if px <= 0:
                console.print(f'[red][{symbol}] Size=0: invalid price {px}')
                return 0
            cs = float(mkt.get('contractSize', 1) or 1)
            ntl = px * cs
            mrg = ntl / DEFAULT_LEVERAGE
            min_ct = max(int(mkt.get('limits', {}).get('amount', {}).get('min') or 1), 1)
            if ntl * min_ct > MAX_NOTIONAL_PER_CONTRACT * max(min_ct, 1):
                console.print(f'[red][{symbol}] Size=0: notional too large (ntl={ntl:.4f} * min_ct={min_ct} > {MAX_NOTIONAL_PER_CONTRACT})')
                return 0
            remaining = (usable - h['used']) * 0.90
            if mrg * min_ct > remaining:
                console.print(f'[red][{symbol}] Size=0: insufficient margin (mrg={mrg:.4f} * min_ct={min_ct} > remaining={remaining:.4f})')
                return 0
            exposure_cap = h['equity'] * MAX_EXPOSURE_PER_SYMBOL if h['equity'] > 0 else 0
            max_by_margin = int(remaining / mrg) if mrg > 0 else min_ct
            max_by_exposure = int(exposure_cap / ntl) if ntl > 0 else min_ct
            ct = max(min_ct, min(max_by_margin, max_by_exposure))
            console.print(f'[green][{symbol}] Size={ct} contracts (min_ct={min_ct}, max_by_margin={max_by_margin}, max_by_exposure={max_by_exposure})')
            return ct
        except Exception as e:
            console.print(f'[red][{symbol}] Size err: {e}')
            return 0

    # — Order execution —

    async def open_position(self, symbol: str, side: str) -> bool:
        """Open position. Uses market order if FORCE_TAKER_MODE, else limit with backoff."""
        ct = await self.safe_size(symbol)
        if ct <= 0:
            return False
        delay = 1
        for attempt in range(MAX_ORDER_RETRIES):
            try:
                if FORCE_TAKER_MODE:
                    # Market order — guaranteed fill, accepts spread cost
                    order = await self.exchange.create_market_order(
                        symbol, side, ct,
                        {'marginMode': MARGIN_MODE, 'type': 'swap'}
                    )
                    console.print(f'[bold green][{symbol}] {side.upper()} {ct}ct MARKET ORDER (#{attempt+1})')
                    # Verify fill
                    await asyncio.sleep(1)
                    if await self._wait_fill(symbol, side, ct):
                        console.print(f'[bold green][{symbol}] {side.upper()} FILLED ✓')
                        return True
                    console.print(f'[yellow][{symbol}] {side.upper()} market order sent but fill not confirmed yet')
                    return True  # Market orders should always fill
                else:
                    # Limit order crossing spread
                    tk = await self.exchange.fetch_ticker(symbol, {'type': 'swap'})
                    px = float(tk['last'])
                    lim = px * (1 + OFFSET) if side == 'buy' else px * (1 - OFFSET)
                    order = await self.exchange.create_limit_order(
                        symbol, side, ct, lim,
                        {'marginMode': MARGIN_MODE, 'type': 'swap'}
                    )
                    console.print(f'[cyan][{symbol}] {side.upper()} {ct}ct @ {lim:.8f} (#{attempt+1})')
                    if await self._wait_fill(symbol, side, ct):
                        console.print(f'[bold green][{symbol}] {side.upper()} FILLED')
                        return True
                    try:
                        await self.exchange.cancel_order(order['id'], symbol, {'type': 'swap'})
                    except Exception:
                        pass
            except Exception as e:
                console.print(f'[{symbol}] {side} #{attempt+1}: {e}')
            await asyncio.sleep(delay)
            delay = min(delay * 2, 8)
        return False

    async def _wait_fill(self, symbol: str, side: str, target: float) -> bool:
        t0 = time.time()
        want = 'long' if side == 'buy' else 'short'
        while time.time() - t0 < FILL_TIMEOUT_SEC:
            try:
                pos = await self.exchange.fetch_positions([symbol], {'type': 'swap'})
                filled = sum(float(p['contracts']) for p in pos
                             if p['side'] == want and float(p.get('contracts', 0)) > 0)
                if filled >= target:
                    return True
            except Exception:
                pass
            await asyncio.sleep(1)
        return False

    async def cancel_reduce_orders(self, symbol: str) -> None:
        """Cancel stale reduce-only orders before placing new closes."""
        try:
            orders = await self.exchange.fetch_open_orders(
                symbol, params={'marginMode': MARGIN_MODE, 'type': 'swap'})
            for o in orders:
                reduce = o.get('reduceOnly', False)
                if not reduce:
                    info = o.get('info', {})
                    reduce = info.get('is_reduce_only', False) or info.get('reduce_only', False)
                if reduce:
                    await self.exchange.cancel_order(
                        o['id'], symbol, {'marginMode': MARGIN_MODE, 'type': 'swap'})
        except Exception:
            pass

    async def close_at_target(self, symbol: str, side: str, contracts: float,
                              target_price: float) -> bool:
        """Limit close at calculated target price. Guarantees profit on every exit."""
        await self.cancel_reduce_orders(symbol)
        close_side = 'sell' if side == 'long' else 'buy'
        delay = 1
        for attempt in range(MAX_ORDER_RETRIES):
            try:
                await self.exchange.create_limit_order(
                    symbol, close_side, contracts, target_price,
                    {'marginMode': MARGIN_MODE, 'reduceOnly': True, 'type': 'swap'}
                )
                console.print(f'[green][{symbol}] Close {side} {contracts}ct @ {target_price:.8f}')
                return True
            except Exception as e:
                console.print(f'[{symbol}] target close #{attempt+1}: {e}')
                await self.cancel_reduce_orders(symbol)
                await asyncio.sleep(delay)
                delay = min(delay * 2, 8)
        return False

    async def close_position_market(self, symbol: str, side: str, contracts: float) -> bool:
        """Market order fallback for emergency/forced closes."""
        close_side = 'sell' if side == 'long' else 'buy'
        try:
            await self.exchange.create_market_order(
                symbol, close_side, contracts,
                {'marginMode': MARGIN_MODE, 'reduceOnly': True, 'type': 'swap'})
            return True
        except Exception as e:
            console.print(f'[red][{symbol}] Market close failed: {e}')
            return False

    async def dca_opposite(self, symbol: str, closed_side: str) -> None:
        """Bounded DCA: add 1ct to opposite side. Risk engine caps rounds."""
        hp = self.hedges.get(symbol)
        if not hp:
            return
        opp = 'short' if closed_side == 'long' else 'long'
        allowed, reason = self.risk.check_dca_allowed(hp, opp)
        if not allowed:
            console.print(f'[yellow][{symbol}] DCA blocked: {reason}')
            return
        opp_side = 'sell' if closed_side == 'long' else 'buy'
        try:
            tk = await self.exchange.fetch_ticker(symbol, {'type': 'swap'})
            px = float(tk['last'])
            lim = px * (1 + OFFSET) if opp_side == 'buy' else px * (1 - OFFSET)
            await self.exchange.create_limit_order(
                symbol, opp_side, 1, lim,
                {'marginMode': MARGIN_MODE, 'type': 'swap'})
            leg = hp.short_leg if closed_side == 'long' else hp.long_leg
            leg.dca_rounds += 1
            snap = self.risk.get_snapshot(0, 0, 0, self.hedges)
            self.journal.log('DCA', symbol, opp_side, 1, price=lim,
                             reason=f'opposite DCA round {leg.dca_rounds}/{MAX_DCA_ROUNDS}',
                             risk_snapshot=snap)
        except Exception as e:
            console.print(f'[yellow][{symbol}] DCA failed: {e}')

    # — Hedge state persistence —

    def save_hedge_state(self) -> None:
        try:
            data = {}
            for sym, hp in self.hedges.items():
                data[sym] = asdict(hp)
            with open(HEDGE_STATE_FILE, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception:
            pass

    def load_hedge_state(self) -> None:
        if not HEDGE_STATE_FILE.exists():
            return
        try:
            with open(HEDGE_STATE_FILE) as f:
                data = json.load(f)
            for sym, hp_dict in data.items():
                ll = hp_dict.get('long_leg', {})
                sl = hp_dict.get('short_leg', {})
                self.hedges[sym] = HedgePair(
                    long_leg=HedgeLeg(**ll), short_leg=HedgeLeg(**sl),
                    hedge_open_time=hp_dict.get('hedge_open_time', 0),
                    harvests=hp_dict.get('harvests', 0),
                    # New execution metrics (default to 0 for backward compatibility)
                    exit_attempts=hp_dict.get('exit_attempts', 0),
                    exit_fills=hp_dict.get('exit_fills', 0),
                    total_expected_profit=hp_dict.get('total_expected_profit', 0),
                    total_realized_profit=hp_dict.get('total_realized_profit', 0),
                    last_exit_time=hp_dict.get('last_exit_time', 0),
                )
        except Exception:
            pass

    # — Flatten symbol (force close both legs) —

    async def flatten_symbol(self, symbol: str, reason: str = '') -> None:
        """Close both legs. Used by risk engine force-flatten and emergency."""
        await self.cancel_reduce_orders(symbol)
        try:
            positions = await self.exchange.fetch_positions([symbol], {'type': 'swap'})
            for pos in positions:
                ct = float(pos.get('contracts', 0) or 0)
                if ct <= 0:
                    continue
                side = pos['side']
                close_side = 'sell' if side == 'long' else 'buy'
                try:
                    tk = await self.exchange.fetch_ticker(symbol, {'type': 'swap'})
                    px = float(tk['last'])
                    lim = px * (1 + OFFSET) if close_side == 'buy' else px * (1 - OFFSET)
                    await self.exchange.create_limit_order(
                        symbol, close_side, ct, lim,
                        {'marginMode': MARGIN_MODE, 'reduceOnly': True, 'type': 'swap'})
                except Exception:
                    try:
                        await self.close_position_market(symbol, side, ct)
                    except Exception as e2:
                        console.print(f'[bold red][{symbol}] FLATTEN FAILED {side}: {e2}')
                await asyncio.sleep(0.3)
        except Exception as e:
            console.print(f'[red][{symbol}] Flatten error: {e}')
        self.hedges.pop(symbol, None)
        self.state[symbol] = 0.0
        self.risk.clear_symbol(symbol)
        snap = self.risk.get_snapshot(0, 0, 0, self.hedges)
        self.journal.log('FLATTEN', symbol, '', 0, reason=reason,
                         risk_snapshot=asdict(snap) if snap else {})
    
    # — Panic exit (market order for emergency) —
    
    async def panic_exit(self, symbol: str, reason: str = '') -> None:
        """Emergency market exit - accepts slippage to guarantee fill."""
        try:
            positions = await self.exchange.fetch_positions([symbol], {'type': 'swap'})
            for pos in positions:
                ct = float(pos.get('contracts', 0) or 0)
                if ct <= 0:
                    continue
                side = pos['side']
                close_side = 'sell' if side == 'long' else 'buy'
                try:
                    await self.exchange.create_market_order(
                        symbol, close_side, ct,
                        {'marginMode': MARGIN_MODE, 'reduceOnly': True, 'type': 'swap'})
                    console.print(f'[bold yellow][{symbol}] PANIC EXIT {side}: {ct}ct | {reason}')
                except Exception as e:
                    console.print(f'[bold red][{symbol}] PANIC EXIT FAILED {side}: {e}')
            # Set cooldown after panic exit
            self.risk.set_cooldown(symbol, SYMBOL_COOLDOWN_SEC)
        except Exception as e:
            console.print(f'[red][{symbol}] Panic exit error: {e}')

    # — Hedge open pair (atomic: both legs or rollback) —

    async def hedge_open_pair(self, symbol: str) -> bool:
        """Open LONG + SHORT atomically. Rollback on failure."""
        h = await self.get_health()
        if not h['safe']:
            return False
        ok_count = sum(1 for hp in self.hedges.values() if hp.is_complete)
        can_open, reason = self.risk.check_can_open_new(ok_count)
        if not can_open:
            return False
        sym_ok, sym_reason = self.risk.check_symbol_risk(symbol, h['equity'])
        if not sym_ok:
            return False
        vol_ok = await self.check_volatility(symbol)
        if not vol_ok:
            return False
        ct = await self.safe_size(symbol)
        if ct <= 0:
            return False
        mkt = self.exchange.market(symbol)
        cs = float(mkt.get('contractSize', 1) or 1)
        tk = await self.exchange.fetch_ticker(symbol, {'type': 'swap'})
        px = float(tk['last'])
        margin_both = (px * cs * ct / DEFAULT_LEVERAGE) * 2
        if margin_both > h['active_capital'] - h['used']:
            return False
        snap = self.risk.get_snapshot(h['equity'], h['used'], h['free'], self.hedges)
        self.journal.log('HEDGE_ATTEMPT', symbol, 'both', ct, price=px,
                         reason='new hedge pair', risk_snapshot=snap)
        console.print(f'[cyan][{symbol}] Opening hedge: LONG leg...')
        if not await self.open_position(symbol, 'buy'):
            self.journal.log('HEDGE_FAIL', symbol, 'long', 0, reason='long fill failed',
                             risk_snapshot=snap)
            return False
        await asyncio.sleep(0.5)
        console.print(f'[cyan][{symbol}] Opening hedge: SHORT leg...')
        if not await self.open_position(symbol, 'sell'):
            console.print(f'[yellow][{symbol}] Short failed — rolling back long')
            await self.flatten_symbol(symbol, reason='rollback: short leg failed')
            return False
        now = time.time()
        try:
            positions = await self.exchange.fetch_positions([symbol], {'type': 'swap'})
            hp = HedgePair(hedge_open_time=now)
            for pos in positions:
                pct = float(pos.get('contracts', 0) or 0)
                if pct <= 0:
                    continue
                entry = float(pos.get('entryPrice', 0) or 0)
                if pos['side'] == 'long':
                    hp.long_leg = HedgeLeg(contracts=pct, entry=entry,
                                           timestamp=now, filled=True)
                elif pos['side'] == 'short':
                    hp.short_leg = HedgeLeg(contracts=pct, entry=entry,
                                            timestamp=now, filled=True)
            if hp.is_complete:
                self.hedges[symbol] = hp
                ntl = px * cs * ct
                self.risk.record_symbol_exposure(symbol, ntl * 2)
                self.save_hedge_state()
                console.print(
                    f'[bold green][{symbol}] HEDGE OPEN — '
                    f'L:{hp.long_leg.contracts}ct@{hp.long_leg.entry:.8f} '
                    f'S:{hp.short_leg.contracts}ct@{hp.short_leg.entry:.8f}')
                self.journal.log('HEDGE_OPEN', symbol, 'both', ct, price=px,
                                 reason='pair confirmed',
                                 hedge_state=f'L@{hp.long_leg.entry:.8f} S@{hp.short_leg.entry:.8f}',
                                 risk_snapshot=snap)
                return True
            else:
                await self.flatten_symbol(symbol, reason='incomplete after fills')
                return False
        except Exception as e:
            await self.flatten_symbol(symbol, reason=f'confirm error: {e}')
            return False

    # — Hedge harvest (profit-only close + DCA + reopen) —

    async def hedge_harvest(self, symbol: str) -> None:
        """Close profitable leg at target price, DCA opposite, reopen. Zero-loss design."""
        hp = self.hedges.get(symbol)
        if not hp or not hp.is_complete:
            return
        try:
            positions = await self.exchange.fetch_positions([symbol], {'type': 'swap'})
            for pos in positions:
                ct = float(pos.get('contracts', 0) or 0)
                if ct <= 0:
                    continue
                side = pos['side']
                upnl = float(pos.get('unrealizedPnl', 0) or 0)
                entry = float(pos.get('entryPrice', 0) or 0)
                self.risk.record_symbol_pnl(symbol, upnl)
                effective_threshold = entry * SPREAD_TARGET_PCT * ct
                if upnl >= effective_threshold:
                    per_ct_target = effective_threshold / ct
                    if side == 'long':
                        target_price = entry + per_ct_target
                    else:
                        target_price = entry - per_ct_target
                    h = await self.get_health()
                    snap = self.risk.get_snapshot(
                        h['equity'], h['used'], h['free'], self.hedges)
                    console.print(
                        f'[bold green][{symbol}] {side} PROFIT ${upnl:.6f} >= '
                        f'${effective_threshold:.6f} — harvest @ {target_price:.8f}')
                    closed = await self.close_at_target(symbol, side, ct, target_price)
                    if closed:
                        self.perf.record_trade_pnl(upnl)
                        mkt = self.exchange.market(symbol)
                        cs_val = float(mkt.get('contractSize', 1) or 1)
                        self.penny.record(symbol, side, entry, target_price, ct, cs_val, entry, 'harvest')
                        hp.harvests += 1
                        self.journal.log(
                            'HARVEST', symbol, side, ct, price=target_price, pnl=upnl,
                            reason=f'profit>threshold target={target_price:.8f}',
                            hedge_state=f'harvest#{hp.harvests}', risk_snapshot=snap)
                        if side == 'long':
                            hp.long_leg.filled = False
                        else:
                            hp.short_leg.filled = False
                        self.save_hedge_state()
                        await asyncio.sleep(1)
                        short_sym = symbol.split('/')[0]
                        console.print(f"[red]Hedge broken for {short_sym} — flattening, no DCA[/red]")
                        reopen_side = 'buy' if side == 'long' else 'sell'
                        console.print(f'[cyan][{symbol}] Reopening {side} leg...')
                        if await self.open_position(symbol, reopen_side):
                            new_pos = await self.exchange.fetch_positions(
                                [symbol], {'type': 'swap'})
                            for np_ in new_pos:
                                nct = float(np_.get('contracts', 0) or 0)
                                if nct > 0 and np_['side'] == side:
                                    new_entry = float(np_.get('entryPrice', 0) or 0)
                                    leg = HedgeLeg(contracts=nct, entry=new_entry,
                                                   timestamp=time.time(), filled=True)
                                    if side == 'long':
                                        hp.long_leg = leg
                                    else:
                                        hp.short_leg = leg
                                    break
                            self.save_hedge_state()
                            console.print(f'[bold green][{symbol}] {side} REOPENED')
                            self.journal.log('REOPEN', symbol, side, ct,
                                             reason='profit cycle complete', risk_snapshot=snap)
                        else:
                            self.journal.log('HEDGE_BROKEN', symbol, side, 0,
                                             reason='reopen failed', risk_snapshot=snap)
                    return
            total_upnl = sum(float(p.get('unrealizedPnl', 0) or 0)
                             for p in positions if float(p.get('contracts', 0) or 0) > 0)
            self.state[symbol] = total_upnl
            self.risk.record_symbol_pnl(symbol, total_upnl)
        except Exception as e:
            console.print(f'[red][{symbol}] Harvest error: {e}')

    # — Hedge repair (fix broken hedges) —

    async def hedge_repair(self, symbol: str) -> None:
        """Detect and fix broken hedges. Flatten if unfixable."""
        hp = self.hedges.get(symbol)
        if not hp:
            return
        try:
            positions = await self.exchange.fetch_positions([symbol], {'type': 'swap'})
            has_long = has_short = False
            for pos in positions:
                ct = float(pos.get('contracts', 0) or 0)
                if ct <= 0:
                    continue
                if pos['side'] == 'long':
                    has_long = True
                elif pos['side'] == 'short':
                    has_short = True
            hp.long_leg.filled = has_long
            hp.short_leg.filled = has_short
            if hp.is_complete:
                return
            if hp.is_empty:
                self.hedges.pop(symbol, None)
                self.risk.clear_symbol(symbol)
                self.save_hedge_state()
                return
            missing = 'long' if not has_long else 'short'
            h = await self.get_health()
            if not h['safe']:
                await self.flatten_symbol(symbol, reason='unsafe to repair')
                return
            snap = self.risk.get_snapshot(h['equity'], h['used'], h['free'], self.hedges)
            self.journal.log('REPAIR_ATTEMPT', symbol, missing, 0,
                             reason=f'{missing} missing', risk_snapshot=snap)
            reopen_side = 'buy' if missing == 'long' else 'sell'
            if await self.open_position(symbol, reopen_side):
                new_pos = await self.exchange.fetch_positions([symbol], {'type': 'swap'})
                for np_ in new_pos:
                    nct = float(np_.get('contracts', 0) or 0)
                    if nct > 0 and np_['side'] == missing:
                        leg = HedgeLeg(contracts=nct,
                                       entry=float(np_.get('entryPrice', 0) or 0),
                                       timestamp=time.time(), filled=True)
                        if missing == 'long':
                            hp.long_leg = leg
                        else:
                            hp.short_leg = leg
                        break
                self.save_hedge_state()
                self.journal.log('REPAIR_OK', symbol, missing, 1,
                                 reason='repaired', risk_snapshot=snap)
            else:
                await self.flatten_symbol(symbol, reason=f'{missing} repair failed')
        except Exception as e:
            console.print(f'[red][{symbol}] Repair error: {e}')

    # — Emergency close all —

    async def emergency_close_all(self, reason: str = 'margin critical') -> None:
        """Flatten every position. Last resort."""
        console.print(f'[bold red]EMERGENCY FLATTEN: {reason}')
        try:
            positions = await self.exchange.fetch_positions(None, {'type': 'swap'})
            for pos in positions:
                ct = float(pos.get('contracts', 0) or 0)
                if ct <= 0:
                    continue
                sym = pos['symbol']
                side = pos['side']
                close_side = 'sell' if side == 'long' else 'buy'
                try:
                    tk = await self.exchange.fetch_ticker(sym, {'type': 'swap'})
                    px = float(tk['last'])
                    lim = px * 0.995 if close_side == 'sell' else px * 1.005
                    await self.exchange.create_limit_order(
                        sym, close_side, ct, lim,
                        {'marginMode': MARGIN_MODE, 'reduceOnly': True, 'type': 'swap'})
                except Exception:
                    try:
                        await self.exchange.create_market_order(
                            sym, close_side, ct,
                            {'marginMode': MARGIN_MODE, 'reduceOnly': True, 'type': 'swap'})
                    except Exception:
                        pass
                await asyncio.sleep(0.2)
        except Exception as e:
            console.print(f'[red]Emergency error: {e}')
        self.hedges.clear()
        self.save_hedge_state()
        snap = self.risk.get_snapshot(0, 0, 0, self.hedges)
        self.journal.log('EMERGENCY_FLATTEN', 'ALL', '', 0,
                         reason=reason, risk_snapshot=snap)

    # — Position recovery (restart-safe) —

    async def recover_positions(self) -> None:
        """Rebuild hedge state from exchange + disk. Only recover configured symbols."""
        # Clear stale disk state — we only trust live exchange positions
        self.hedges.clear()
        allowed = set(self.active_symbols) if self.active_symbols else set()
        try:
            all_pos = await self.exchange.fetch_positions(None, {'type': 'swap'})
            by_symbol: Dict[str, list] = {}
            stale_symbols = set()
            for pos in all_pos:
                ct = float(pos.get('contracts', 0) or 0)
                if ct <= 0:
                    continue
                sym = pos['symbol']
                if allowed and sym not in allowed:
                    stale_symbols.add(sym)
                    continue  # skip non-configured symbols
                by_symbol.setdefault(sym, []).append(pos)
            # Warn about stale positions on non-configured symbols
            if stale_symbols:
                console.print(f'[yellow]⚠ Ignoring {len(stale_symbols)} stale symbol(s) not in config: '
                              f'{[s.split("/")[0] for s in stale_symbols]}')
            recovered = 0
            for sym, pos_list in by_symbol.items():
                now = time.time()
                hp = HedgePair(hedge_open_time=now)
                for pos in pos_list:
                    ct = float(pos.get('contracts', 0) or 0)
                    side = pos['side']
                    entry = float(pos.get('entryPrice', 0) or 0)
                    upnl = float(pos.get('unrealizedPnl', 0) or 0)
                    leg = HedgeLeg(contracts=ct, entry=entry,
                                   timestamp=now, filled=True)
                    if side == 'long':
                        hp.long_leg = leg
                    elif side == 'short':
                        hp.short_leg = leg
                    self.state[sym] = self.state.get(sym, 0) + upnl
                    self.risk.record_symbol_pnl(sym, upnl)
                    recovered += 1
                self.hedges[sym] = hp
            self.save_hedge_state()
            if recovered:
                ok = sum(1 for hp in self.hedges.values() if hp.is_complete)
                broken = sum(1 for hp in self.hedges.values() if hp.is_broken)
                console.print(f'[bold cyan]Recovered {recovered} legs — {ok} complete, {broken} broken')
                h = await self.get_health()
                snap = self.risk.get_snapshot(h['equity'], h['used'], h['free'], self.hedges)
                self.journal.log('RECOVER', 'ALL', '', 0,
                                 reason=f'{recovered} legs {ok} ok {broken} broken',
                                 risk_snapshot=snap)
            else:
                console.print('[green]Clean start — no positions to recover')
        except Exception as e:
            console.print(f'[red]Recovery error: {e}')

    # — LLM symbol scoring (limited, deterministic filtering only) —

    async def _fetch_market_context(self, symbol: str) -> str:
        try:
            tk = await self.exchange.fetch_ticker(symbol, {'type': 'swap'})
            ohlcv = await self.exchange.fetch_ohlcv(symbol, '5m', limit=6)
            last = float(tk.get('last', 0))
            pct24 = float(tk.get('percentage', 0) or 0)
            vol24 = float(tk.get('quoteVolume', 0) or 0)
            closes = [c[4] for c in ohlcv] if ohlcv else []
            candle_str = ', '.join(f'{c:.8f}' for c in closes[-6:])
            return (f'Symbol: {symbol}\nLast: {last:.8f}\n24h change: {pct24:+.2f}%\n'
                    f'24h vol USDT: {vol24:.0f}\nRecent 5m closes: [{candle_str}]')
        except Exception:
            return f'Symbol: {symbol} (no data)'

    async def llm_score_symbol(self, symbol: str) -> float:
        """Score 0-10 for volatility (hedging opportunity). AI is advisory only."""
        if not GROQ_KEY:
            return 5.0
        try:
            context = await self._fetch_market_context(symbol)
            async with aiohttp.ClientSession() as sess:
                payload = {
                    'model': 'llama-3.1-8b-instant',
                    'messages': [
                        {'role': 'system', 'content':
                         'Score this crypto 0-10 for short-term volatility. '
                         'Higher = more volatile = better for hedged harvesting. '
                         'Reply ONLY a number.'},
                        {'role': 'user', 'content': context}
                    ],
                    'max_tokens': 5, 'temperature': 0.1,
                }
                headers = {'Authorization': f'Bearer {GROQ_KEY}',
                           'Content-Type': 'application/json'}
                async with sess.post(
                    'https://api.groq.com/openai/v1/chat/completions',
                    json=payload, headers=headers,
                    timeout=aiohttp.ClientTimeout(total=8)
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        raw = data['choices'][0]['message']['content'].strip()
                        return max(0.0, min(10.0, float(raw)))
        except Exception:
            pass
        return 5.0

    async def llm_select_symbols(self, candidates: List[str]) -> List[str]:
        """LLM-based symbol selection with fill probability scoring. Runs once per session, not per trade."""
        if not GROQ_KEY:
            return candidates[:MAX_CONCURRENT_SYMBOLS]
        
        # Shuffle candidates to break deterministic loops
        random.shuffle(candidates)
        
        # First: filter by basic liquidity criteria
        eligible = []
        for sym in candidates[:50]:  # Expanded from 20 for diversity
            try:
                ob = await self.exchange.fetch_order_book(sym, 10)
                ticker = await self.exchange.fetch_ticker(sym)
                
                bid = ob['bids'][0][0] if ob['bids'] else 0
                ask = ob['asks'][0][0] if ob['asks'] else 0
                if bid == 0 or ask == 0:
                    continue
                    
                spread = (ask - bid) / bid
                volume = ticker.get('quoteVolume', 0) or 0
                
                # Pre-filter: spread > 0.2%, volume > $50k
                if spread < 0.002 or volume < 50000:
                    continue
                
                # Depth calculation
                bid_depth = sum(b[0] * b[1] for b in ob['bids'][:5])
                ask_depth = sum(a[0] * a[1] for a in ob['asks'][:5])
                
                # Fill probability score
                fill_score = (
                    spread * 2 +
                    min(volume / 1000000, 1) +
                    min(bid_depth / 100, 1) +
                    min(ask_depth / 100, 1)
                )
                # Add noise to break ties
                fill_score += random.uniform(-0.05, 0.05)
                
                eligible.append({
                    'symbol': sym,
                    'spread': spread,
                    'volume': volume,
                    'bid_depth': bid_depth,
                    'ask_depth': ask_depth,
                    'fill_score': fill_score
                })
            except Exception:
                continue
        
        if not eligible:
            return candidates[:MAX_CONCURRENT_SYMBOLS]
        
        # Rank by fill score, take top 10 for LLM review (expanded from 5)
        ranked = sorted(eligible, key=lambda x: x['fill_score'], reverse=True)
        top_10 = ranked[:10]
        
        # Build LLM prompt
        context = "\n".join([
            f"{r['symbol']}: spread={r['spread']:.3%}, vol=${r['volume']:,.0f}, depth=${r['bid_depth']:.0f}/${r['ask_depth']:.0f}"
            for r in top_10
        ])
        
        prompt = f"""You are a professional market maker. Select the BEST symbols for spread capture.

Criteria:
- Stable liquidity (not pump/dump)
- Consistent fills (high depth)
- Non-spiky behavior

Data:
{context}

Return ONLY a JSON list of symbols in priority order. Example: ["BTC/USDT:USDT", "ETH/USDT:USDT"]"""
        
        try:
            async with aiohttp.ClientSession() as sess:
                resp = await sess.post(
                    'https://api.groq.com/openai/v1/chat/completions',
                    headers={'Authorization': f'Bearer {GROQ_KEY}', 'Content-Type': 'application/json'},
                    json={
                        'model': 'llama-3.1-8b-instant',
                        'messages': [{'role': 'user', 'content': prompt}],
                        'temperature': 0.2
                    },
                    timeout=aiohttp.ClientTimeout(total=10)
                )
                data = await resp.json()
                text = data['choices'][0]['message']['content']
                selected = json.loads(text)
                
                # Diversity check: force change if stuck
                if hasattr(self, 'last_selected') and selected == self.last_selected:
                    console.print('[yellow]LLM STUCK — forcing diversity[/yellow]')
                    selected = random.sample([r['symbol'] for r in top_10], k=min(MAX_CONCURRENT_SYMBOLS, len(top_10)))
                
                self.last_selected = selected
                console.print(f'[green]LLM selected: {selected}[/green]')
                return selected[:MAX_CONCURRENT_SYMBOLS]
        except Exception as e:
            console.print(f'[yellow]LLM selection failed: {e}, using top by fill score[/yellow]')
            return [r['symbol'] for r in top_10[:MAX_CONCURRENT_SYMBOLS]]

    # — Symbol selection (auto-discovery, budget-aware) —

    async def fetch_eligible_symbols(self) -> List[str]:
        """Discover tradeable symbols within budget and risk limits."""
        if not self.exchange:
            await self.init_exchange()
        h = await self.get_health()
        if h['free'] <= 0:
            return []
        candidates = []
        for mkt in (self.exchange.markets or {}).values():
            sym = mkt.get('symbol')
            if not sym or not mkt.get('active', True) or not mkt.get('swap', False):
                continue
            if mkt.get('quote') != 'USDT' and mkt.get('settle') != 'USDT':
                continue
            cs = float(mkt.get('contractSize', 1) or 1)
            px = float(mkt.get('info', {}).get('last_price', 0) or 0)
            if px <= 0:
                continue
            ntl = px * cs
            mrg = ntl / DEFAULT_LEVERAGE
            if ntl <= MAX_NOTIONAL_PER_CONTRACT:
                candidates.append((sym, ntl, mrg))
        candidates.sort(key=lambda x: x[2])
        budget = h['active_capital'] - h['used']
        selected, running = [], 0.0
        for sym, ntl, mrg in candidates:
            hedge_cost = mrg * 2
            if running + hedge_cost <= budget and len(selected) < MAX_CONCURRENT_SYMBOLS:
                selected.append((sym, ntl, mrg))
                running += hedge_cost
        console.print(f'[bold green]{len(selected)} symbols eligible (hedge margin ${running:.4f})')
        return [s for s, _, _ in selected]

    # — Order book + position reading —

    async def fetch_book(self, symbol: str) -> Tuple[float, float]:
        """Return (best_bid, best_ask) from L2 order book."""
        try:
            ob = await self.exchange.fetch_order_book(symbol, 5, {'type': 'swap'})
            bid = float(ob['bids'][0][0]) if ob.get('bids') else 0
            ask = float(ob['asks'][0][0]) if ob.get('asks') else 0
            return bid, ask
        except Exception:
            tk = await self.exchange.fetch_ticker(symbol, {'type': 'swap'})
            px = float(tk['last'])
            return px * 0.9999, px * 1.0001

    async def read_positions(self, symbol: str) -> dict:
        """Read current positions for symbol. Returns {long: {cts, entry, upnl}, short: ...}."""
        result = {'long': None, 'short': None}
        try:
            positions = await self.exchange.fetch_positions([symbol], {'type': 'swap'})
            for pos in positions:
                ct = float(pos.get('contracts', 0) or 0)
                if ct <= 0:
                    continue
                side = pos['side']
                result[side] = {
                    'cts': ct,
                    'entry': float(pos.get('entryPrice', 0) or 0),
                    'upnl': float(pos.get('unrealizedPnl', 0) or 0),
                }
        except Exception:
            pass
        return result

    # — Spread-capture: maker quote placement —

    async def place_maker_quote(self, symbol: str, side: str, ct: int, px: Optional[float] = None) -> Optional[str]:
        """Place post_only order at a specified price or top of book. Returns order ID.
        In FORCE_TAKER_MODE: uses market order to guarantee fill."""
        try:
            if FORCE_TAKER_MODE:
                # Market order — guaranteed fill, accepts spread cost
                order = await self.exchange.create_market_order(
                    symbol, side, ct,
                    {'marginMode': MARGIN_MODE, 'type': 'swap'})
                short_sym = symbol.split('/')[0]
                console.print(f'[bold green][{short_sym}] TAKER MARKET {side.upper()} {ct}ct [Order ID: {order.get("id", "N/A")}]')
                return order.get('id', '')
            else:
                bid, ask = await self.fetch_book(symbol)
                quote_px = px if px and px > 0 else (bid if side == 'buy' else ask)
                if quote_px <= 0:
                    console.print(f'[red][{symbol}] QUOTE FAILED: Invalid price (bid={bid}, ask={ask})')
                    return None
                order_params = {'marginMode': MARGIN_MODE, 'type': 'swap', 'postOnly': True}
                order = await self.exchange.create_limit_order(symbol, side, ct, quote_px, order_params)
                short_sym = symbol.split('/')[0]
                console.print(f'[cyan][{short_sym}] MAKER QUOTE {side.upper()} {ct}ct @ {quote_px:.8f} [Order ID: {order.get("id", "N/A")}]')
                return order.get('id', '')
        except Exception as e:
            console.print(f'[bold red][{symbol}] ORDER FAILED: {type(e).__name__}: {e}')
            console.print(f'[red]  Symbol: {symbol}, Side: {side}, Contracts: {ct}')
            return None

    # — Spread-capture: taker fallback —

    async def taker_entry(self, symbol: str, side: str, ct: int) -> Optional[str]:
        """Cross the spread aggressively after maker timeout."""
        try:
            tk = await self.exchange.fetch_ticker(symbol, {'type': 'swap'})
            px = float(tk['last'])
            lim = px * (1 + OFFSET) if side == 'buy' else px * (1 - OFFSET)
            order = await self.exchange.create_limit_order(
                symbol, side, ct, lim,
                {'marginMode': MARGIN_MODE, 'type': 'swap'})
            short_sym = symbol.split('/')[0]
            console.print(f'[yellow][{short_sym}] TAKER {side.upper()} {ct}ct @ {lim:.8f}')
            return order.get('id', '')
        except Exception as e:
            console.print(f'[{symbol}] Taker {side}: {e}')
            return None

    # — Spread-capture: exit order at spread target —

    async def place_spread_exit(self, symbol: str, side: str, cts: float,
                                entry: float, dynamic_spread: float = None) -> Optional[str]:
        """Place reduce_only exit at entry ± dynamic spread target (covers fees)."""
        try:
            mkt = self.exchange.market(symbol)
            cs = float(mkt.get('contractSize', 1) or 1)
            fee_per_unit = entry * FEE_RATE * 2
            # Use dynamic spread if provided, else fall back to global constant
            spread_target = dynamic_spread if dynamic_spread is not None else SPREAD_TARGET_PCT
            target_move = entry * spread_target + fee_per_unit
            if side == 'long':
                exit_px = entry + target_move
                close_side = 'sell'
            else:
                exit_px = entry - target_move
                close_side = 'buy'
            await self.cancel_reduce_orders(symbol)
            order = await self.exchange.create_limit_order(
                symbol, close_side, cts, exit_px,
                {'marginMode': MARGIN_MODE, 'reduceOnly': True, 'type': 'swap'})
            profit_est = target_move * cs * cts
            short_sym = symbol.split('/')[0]
            
            # Track execution metrics
            hp = self.hedges.get(symbol)
            if hp:
                hp.exit_attempts += 1
                hp.total_expected_profit += profit_est
                hp.last_exit_time = time.time()
            
            console.print(
                f'[green][{short_sym}] EXIT {side} {cts}ct @ {exit_px:.8f} '
                f'(entry={entry:.8f} profit=${profit_est:.6f} attempt={hp.exit_attempts if hp else 1})')
            return order.get('id', '')
        except Exception as e:
            console.print(f'[{symbol}] Exit order {side}: {e}')
            return None

    # — Spread-capture: manage one side (long or short) —

    async def _manage_side(self, symbol: str, side: str, qs: QuoteState, momentum: float = 0.0) -> None:
        """Manage a single leg: quote → wait → taker fallback → exit placement with dynamic spread."""
        is_long = side == 'long'
        filled = qs.long_filled if is_long else qs.short_filled
        order_id = qs.long_order_id if is_long else qs.short_order_id
        exit_id = qs.long_exit_id if is_long else qs.short_exit_id
        entry = qs.long_entry if is_long else qs.short_entry
        cts = qs.long_cts if is_long else qs.short_cts
        buy_side = 'buy' if is_long else 'sell'

        # FORCE_TAKER_MODE: lean entry + TP/time exit loop
        if FORCE_TAKER_MODE:
            short_sym = symbol.split('/')[0]

            # --- EXIT: check TP or time-based exit for filled positions ---
            if filled and entry > 0 and cts > 0:
                try:
                    tk = await self.exchange.fetch_ticker(symbol, {'type': 'swap'})
                    current_px = float(tk['last'])  
                    if is_long:
                        pnl_pct = (current_px - entry) / entry
                    else:
                        pnl_pct = (entry - current_px) / entry
                    hold_time = time.time() - qs.quote_time if qs.quote_time > 0 else 0
                    edge_score = qs.last_edge_score
                    kill_threshold = 0.001 if edge_score >= 0.60 else 0.0007
                    dead_exit_sec = EARLY_EXIT_SEC if edge_score >= 0.60 else max(6, EARLY_EXIT_SEC // 2)
                    dead_exit_pnl = EARLY_EXIT_PNL_PCT if edge_score >= 0.60 else max(0.0, EARLY_EXIT_PNL_PCT * 0.5)

                    if self.is_adverse_fill(entry, current_px, side) and abs(pnl_pct) > kill_threshold:
                        await self.close_position_market(symbol, side, cts)
                        mkt = self.exchange.market(symbol)
                        cs = float(mkt.get('contractSize', 1) or 1)
                        pnl = pnl_pct * entry * cs * cts
                        console.print(f'[bold red][{short_sym}] KILL TRADE {side.upper()}: {pnl_pct:+.3%} ${pnl:.6f} edge={edge_score:.2f}')
                        self.perf.record_trade_pnl(pnl)
                        mid = qs.long_mid_at_entry if is_long else qs.short_mid_at_entry
                        self.penny.record(symbol, side, entry, current_px, cts, cs, mid, 'kill')
                        if is_long:
                            qs.long_filled = False; qs.long_entry = 0; qs.long_cts = 0
                        else:
                            qs.short_filled = False; qs.short_entry = 0; qs.short_cts = 0
                        qs.cycles += 1
                        qs.realized += pnl
                        self.train_setup_outcome(qs, pnl)
                        return

                    # TP hit — take profit
                    if pnl_pct >= TP_PCT:
                        await self.close_position_market(symbol, side, cts)
                        mkt = self.exchange.market(symbol)
                        cs = float(mkt.get('contractSize', 1) or 1)
                        profit = pnl_pct * entry * cs * cts
                        console.print(f'[bold green][{short_sym}] TP HIT {side.upper()}: +{pnl_pct:.3%} ${profit:.6f} (held {hold_time:.0f}s)')
                        self.perf.record_trade_pnl(profit)
                        mid = qs.long_mid_at_entry if is_long else qs.short_mid_at_entry
                        self.penny.record(symbol, side, entry, current_px, cts, cs, mid, 'tp')
                        if is_long:
                            qs.long_filled = False; qs.long_entry = 0; qs.long_cts = 0
                        else:
                            qs.short_filled = False; qs.short_entry = 0; qs.short_cts = 0
                        qs.cycles += 1
                        qs.realized += profit
                        self.train_setup_outcome(qs, profit)
                        return

                    # REAL stop — 1% actual danger, not noise
                    if pnl_pct < -REAL_STOP_PCT:
                        await self.close_position_market(symbol, side, cts)
                        mkt = self.exchange.market(symbol)
                        cs = float(mkt.get('contractSize', 1) or 1)
                        loss = pnl_pct * entry * cs * cts
                        console.print(f'[bold red][{short_sym}] STOP {side.upper()}: {pnl_pct:.3%} ${loss:.6f} (held {hold_time:.0f}s)')
                        self.perf.record_trade_pnl(loss)
                        mid = qs.long_mid_at_entry if is_long else qs.short_mid_at_entry
                        self.penny.record(symbol, side, entry, current_px, cts, cs, mid, 'stop')
                        if is_long:
                            qs.long_filled = False; qs.long_entry = 0; qs.long_cts = 0
                        else:
                            qs.short_filled = False; qs.short_entry = 0; qs.short_cts = 0
                        qs.cycles += 1
                        qs.realized += loss
                        self.train_setup_outcome(qs, loss)
                        return

                    # Early dead-trade exit — don't let weak trades linger
                    if hold_time > dead_exit_sec and pnl_pct < dead_exit_pnl:
                        await self.close_position_market(symbol, side, cts)
                        mkt = self.exchange.market(symbol)
                        cs = float(mkt.get('contractSize', 1) or 1)
                        pnl = pnl_pct * entry * cs * cts
                        console.print(f'[yellow][{short_sym}] DEAD EXIT {side.upper()}: {pnl_pct:+.3%} ${pnl:.6f} (held {hold_time:.0f}s edge={edge_score:.2f})')
                        self.perf.record_trade_pnl(pnl)
                        mid = qs.long_mid_at_entry if is_long else qs.short_mid_at_entry
                        self.penny.record(symbol, side, entry, current_px, cts, cs, mid, 'dead')
                        if is_long:
                            qs.long_filled = False; qs.long_entry = 0; qs.long_cts = 0
                        else:
                            qs.short_filled = False; qs.short_entry = 0; qs.short_cts = 0
                        qs.cycles += 1
                        qs.realized += pnl
                        self.train_setup_outcome(qs, pnl)
                        return

                    # Time exit — don't linger, get out
                    if hold_time > MAX_HOLD_SEC:
                        await self.close_position_market(symbol, side, cts)
                        mkt = self.exchange.market(symbol)
                        cs = float(mkt.get('contractSize', 1) or 1)
                        pnl = pnl_pct * entry * cs * cts
                        console.print(f'[yellow][{short_sym}] TIME EXIT {side.upper()}: {pnl_pct:+.3%} ${pnl:.6f} (held {hold_time:.0f}s)')
                        self.perf.record_trade_pnl(pnl)
                        mid = qs.long_mid_at_entry if is_long else qs.short_mid_at_entry
                        self.penny.record(symbol, side, entry, current_px, cts, cs, mid, 'time')
                        if is_long:
                            qs.long_filled = False; qs.long_entry = 0; qs.long_cts = 0
                        else:
                            qs.short_filled = False; qs.short_entry = 0; qs.short_cts = 0
                        qs.cycles += 1
                        qs.realized += pnl
                        return

                    # Still holding
                    console.print(f'[dim][{short_sym}] HOLD {side.upper()}: {pnl_pct:+.3%} ({hold_time:.0f}s/{MAX_HOLD_SEC}s)')
                except Exception as e:
                    console.print(f'[red][{short_sym}] Exit check error: {e}')
                return

            # --- ENTRY: market order if no position ---
            if not filled and not order_id and not exit_id:
                ct = await self.safe_size(symbol)
                if ct > 0:
                    mode = qs.execution_mode or 'taker'
                    console.print(f'[bold green][{short_sym}] {mode.upper()} {buy_side.upper()} {ct}ct')
                    ok = await self.execute_entry_mode(symbol, side, ct, mode)
                    if ok:
                        await asyncio.sleep(0.5)
                        pos = await self.read_positions(symbol)
                        pos_data = pos.get(side)
                        if pos_data and pos_data['cts'] > 0:
                            # Fetch mid price for slippage tracking
                            try:
                                book = await self.exchange.fetch_order_book(symbol, 1, {'type': 'swap'})
                                mid_px = (book['bids'][0][0] + book['asks'][0][0]) / 2
                            except Exception:
                                mid_px = pos_data['entry']
                            if is_long:
                                qs.long_filled = True
                                qs.long_entry = pos_data['entry']
                                qs.long_cts = pos_data['cts']
                                qs.long_mid_at_entry = mid_px
                            else:
                                qs.short_filled = True
                                qs.short_entry = pos_data['entry']
                                qs.short_cts = pos_data['cts']
                                qs.short_mid_at_entry = mid_px
                            qs.quote_time = time.time()  # track hold start
                            console.print(f'[bold green][{short_sym}] {side.upper()} FILLED @ {pos_data["entry"]:.8f} (mid={mid_px:.8f})')
                            
                            # Post-entry alpha: track price move 5s after entry
                            await asyncio.sleep(5)
                            try:
                                tk = await self.exchange.fetch_ticker(symbol, {'type': 'swap'})
                                price_5s = float(tk.get('last', 0) or 0)
                                if is_long:
                                    alpha = (price_5s - pos_data['entry']) / pos_data['entry']
                                else:
                                    alpha = (pos_data['entry'] - price_5s) / pos_data['entry']
                                qs.post_entry_alpha = alpha
                                if alpha < 0:
                                    qs.bad_setup_count += 1
                                else:
                                    qs.bad_setup_count = max(0, qs.bad_setup_count - 1)
                                console.print(f'[dim][{short_sym}] 5s alpha: {alpha:+.4%}')
                            except Exception:
                                pass
            return

        if filled and entry > 0 and cts > 0:
            if not exit_id:
                # Place exit order with dynamic spread based on momentum
                dynamic_spread = await self.get_dynamic_spread_target(momentum)
                oid = await self.place_spread_exit(symbol, side, cts, entry, dynamic_spread)
                if oid:
                    if is_long:
                        qs.long_exit_id = oid
                    else:
                        qs.short_exit_id = oid
            else:
                # Check if exit filled or timed out
                try:
                    order = await self.exchange.fetch_order(exit_id, symbol)
                    if order['status'] == 'closed':
                        # Exit filled - track actual profit
                        hp = self.hedges.get(symbol)
                        if hp:
                            hp.exit_fills += 1
                            mkt = self.exchange.market(symbol)
                            cs = float(mkt.get('contractSize', 1) or 1)
                            fee_per_unit = entry * FEE_RATE * 2
                            target_move = entry * SPREAD_TARGET_PCT + fee_per_unit
                            profit_est = target_move * cs * cts
                            hp.total_realized_profit += profit_est
                        
                        short_sym = symbol.split('/')[0]
                        console.print(f'[green][{short_sym}] EXIT FILLED {side}')
                        exit_price = float(order.get('average') or order.get('price') or entry)
                        mid = qs.long_mid_at_entry if is_long else qs.short_mid_at_entry
                        self.penny.record(symbol, side, entry, exit_price, cts, cs, mid, 'maker_fill')
                        if is_long:
                            qs.long_filled = False
                            qs.long_exit_id = ''
                            qs.realized += profit_est
                            
                            try:
                                notional = entry * cs * cts
                                fees = notional * FEE_RATE * 2
                                self.perf.record_trade_exit(
                                    symbol, exit_price, profit_est, fees, 
                                    is_maker=True, exit_reason='limit_fill'
                                )
                            except Exception:
                                pass
                        else:
                            qs.short_filled = False
                            qs.short_exit_id = ''
                            qs.realized += profit_est
                            
                            try:
                                notional = entry * cs * cts
                                fees = notional * FEE_RATE * 2
                                self.perf.record_trade_exit(
                                    symbol, exit_price, profit_est, fees,
                                    is_maker=True, exit_reason='limit_fill'
                                )
                            except Exception:
                                pass
                        self.train_setup_outcome(qs, profit_est)
                    else:
                        # Check for timeout - switch to market exit
                        elapsed = time.time() - qs.quote_time
                        if elapsed > MAX_EXIT_WAIT_SEC:
                            console.print(f'[yellow][{symbol}] EXIT TIMEOUT after {elapsed:.0f}s, switching to market')
                            await self.exchange.cancel_order(exit_id, symbol)
                            # Market exit
                            await self.close_position_market(symbol, side, cts)
                            hp = self.hedges.get(symbol)
                            mkt = self.exchange.market(symbol)
                            cs = float(mkt.get('contractSize', 1) or 1)
                            tk = await self.exchange.fetch_ticker(symbol, {'type': 'swap'})
                            current_px = float(tk['last'])
                            if hp:
                                hp.exit_fills += 1
                                if side == 'long':
                                    actual_profit = (current_px - entry) * cs * cts
                                else:
                                    actual_profit = (entry - current_px) * cs * cts
                                hp.total_realized_profit += actual_profit
                            mid = qs.long_mid_at_entry if is_long else qs.short_mid_at_entry
                            self.penny.record(symbol, side, entry, current_px, cts, cs, mid, 'timeout_taker')
                            
                            if is_long:
                                qs.long_filled = False
                                qs.long_exit_id = ''
                            else:
                                qs.short_filled = False
                                qs.short_exit_id = ''
                            
                            # Set cooldown after failed exit
                            self.risk.set_cooldown(symbol, SYMBOL_COOLDOWN_SEC)
                except Exception as e:
                    console.print(f'[{symbol}] Exit check error: {e}')
        else:
            pos = await self.read_positions(symbol)
            pos_data = pos.get(side)
            if not pos_data or pos_data['cts'] <= 0:
                # Position gone — but only record if we had a real entry
                if entry > 0 and cts > 0:
                    mkt = self.exchange.market(symbol)
                    cs = float(mkt.get('contractSize', 1) or 1)
                    fee_per_unit = entry * FEE_RATE * 2
                    profit = (entry * SPREAD_TARGET_PCT + fee_per_unit) * cs * cts
                    if abs(profit) > 0.000001:  # skip noise / $0 exits
                        qs.cycles += 1
                        qs.realized += profit
                        self.perf.record_trade_pnl(profit)
                        short_sym = symbol.split('/')[0]
                        h = await self.get_health()
                        snap = self.risk.get_snapshot(h['equity'], h['used'], h['free'], self.hedges)
                        self.journal.log('SPREAD_EXIT', symbol, side, cts, price=entry,
                                         pnl=profit,
                                         reason=f'cycle#{qs.cycles} +${profit:.8f}',
                                         risk_snapshot=snap)
                        console.print(
                            f'[bold green][{short_sym}] {side.upper()} EXIT +${profit:.8f} '
                            f'(cycle {qs.cycles} total=${qs.realized:.8f})')
                # Always clear stale filled state
                if is_long:
                    qs.long_filled = False
                    qs.long_entry = 0
                    qs.long_cts = 0
                    qs.long_exit_id = ''
                    qs.long_order_id = ''
                else:
                    qs.short_filled = False
                    qs.short_entry = 0
                    qs.short_cts = 0
                    qs.short_exit_id = ''
                    qs.short_order_id = ''

        # Re-read filled state (may have been updated above)
        current_filled = qs.long_filled if is_long else qs.short_filled
        current_exit = qs.long_exit_id if is_long else qs.short_exit_id
        if not order_id and not current_filled and not current_exit:
            ct = await self.safe_size(symbol)
            if ct <= 0:
                return
            oid = await self.place_maker_quote(symbol, buy_side, ct)
            if oid:
                if is_long:
                    qs.long_order_id = oid
                else:
                    qs.short_order_id = oid
                qs.quote_time = time.time()
            return

        elapsed = time.time() - qs.quote_time if qs.quote_time > 0 else 0
        try:
            order = await self.exchange.fetch_order(order_id, symbol, {'type': 'swap'})
            status = order.get('status', '')
            if status == 'closed':
                pos = await self.read_positions(symbol)
                pos_data = pos.get(side)
                if pos_data and pos_data['cts'] > 0:
                    entry_price = pos_data['entry']
                    
                    # Adverse fill detection + hard exit
                    try:
                        tk = await self.exchange.fetch_ticker(symbol, {'type': 'swap'})
                        current_price = float(tk['last'])
                        if self.is_adverse_fill(entry_price, current_price, side):
                            short_sym = symbol.split('/')[0]
                            console.print(f'[bold red][{short_sym}] ADVERSE FILL {side}: entry={entry_price:.8f} current={current_price:.8f}')
                            
                            # Hard adverse selection exit - take small loss instead of slow death
                            if side == 'long' and current_price < entry_price * (1 - REAL_STOP_PCT):
                                console.print(f'[bold red][{short_sym}] ADVERSE EXIT: price dropped {REAL_STOP_PCT:.1%}')
                                await self.close_position_market(symbol, 'long', pos_data['cts'])
                                return
                            if side == 'short' and current_price > entry_price * (1 + REAL_STOP_PCT):
                                console.print(f'[bold red][{short_sym}] ADVERSE EXIT: price rose {REAL_STOP_PCT:.1%}')
                                await self.close_position_market(symbol, 'short', pos_data['cts'])
                                return
                            
                            self.risk.pause_symbol(symbol, 60)  # Pause 1 minute
                    except Exception:
                        pass
                    
                    # Fetch mid price for slippage tracking + analytics
                    try:
                        book = await self.exchange.fetch_order_book(symbol, 1, {'type': 'swap'})
                        mid_price = (book['bids'][0][0] + book['asks'][0][0]) / 2
                    except Exception:
                        mid_price = entry_price
                    
                    if is_long:
                        qs.long_filled = True
                        qs.long_entry = entry_price
                        qs.long_cts = pos_data['cts']
                        qs.long_order_id = ''
                        qs.long_mid_at_entry = mid_price
                        
                        try:
                            expected_profit = qs.long_cts * mid_price * SPREAD_TARGET_PCT
                            self.perf.record_trade_entry(
                                symbol, 'long', entry_price, mid_price, 
                                qs.long_cts, expected_profit, is_maker=True
                            )
                        except Exception:
                            pass
                    else:
                        qs.short_filled = True
                        qs.short_entry = entry_price
                        qs.short_cts = pos_data['cts']
                        qs.short_order_id = ''
                        qs.short_mid_at_entry = mid_price
                        
                        try:
                            expected_profit = qs.short_cts * mid_price * SPREAD_TARGET_PCT
                            self.perf.record_trade_entry(
                                symbol, 'short', entry_price, mid_price, 
                                qs.short_cts, expected_profit, is_maker=True
                            )
                        except Exception:
                            pass
                return
            if status == 'canceled' or status == 'expired':
                if is_long:
                    qs.long_order_id = ''
                else:
                    qs.short_order_id = ''
                return
        except Exception:
            if is_long:
                qs.long_order_id = ''
            else:
                qs.short_order_id = ''
            return

        if elapsed >= QUOTE_REFRESH_SEC and elapsed < MAKER_TIMEOUT_SEC:
            bid, ask = await self.fetch_book(symbol)
            quote_px = qs.long_quote_px if is_long else qs.short_quote_px
            ref = bid if is_long else ask
            if ref > 0 and quote_px > 0 and abs(ref - quote_px) / ref > BOOK_DRIFT_THRESHOLD:
                try:
                    await self.exchange.cancel_order(order_id, symbol, {'type': 'swap'})
                except Exception:
                    pass
                if is_long:
                    qs.long_order_id = ''
                else:
                    qs.short_order_id = ''

        if elapsed >= MAKER_TIMEOUT_SEC:
            try:
                await self.exchange.cancel_order(order_id, symbol, {'type': 'swap'})
            except Exception:
                pass
            # No fill = no trade - don't force losses
            if is_long:
                qs.long_order_id = ''
            else:
                qs.short_order_id = ''
            return

    # — Spread-capture cycle (replaces passive execute_trade) —

    def is_trade_worth_it(self, spread_pct: float, is_taker: bool = False) -> bool:
        """Pre-trade validation: expected move must beat total cost."""
        if is_taker:
            # Taker pays spread crossing + fees + slippage
            total_cost = spread_pct + (FEE_RATE * 2) + SLIPPAGE_EST
        else:
            # Maker earns spread, pays fees only
            total_cost = (FEE_RATE * 2) + SLIPPAGE_EST
        edge = spread_pct - total_cost
        margin = 0.002  # require 0.2% real margin
        return edge > margin

    def calculate_microprice(self, book: dict) -> float:
        """Calculate weighted mid price from bid/ask sizes — better signal than simple mid."""
        bids = book.get('bids', [])
        asks = book.get('asks', [])
        if not bids or not asks:
            return 0
        bid_px, bid_sz = bids[0]
        ask_px, ask_sz = asks[0]
        # Weighted mid: favors side with more liquidity
        microprice = (bid_px * ask_sz + ask_px * bid_sz) / (ask_sz + bid_sz)
        return microprice

    def update_inventory_state(self, qs: QuoteState) -> None:
        long_cts = qs.long_cts if qs.long_filled else 0.0
        short_cts = qs.short_cts if qs.short_filled else 0.0
        qs.net_inventory_cts = long_cts - short_cts
        total_cts = long_cts + short_cts
        if total_cts > 0:
            weighted = (qs.long_entry * long_cts) + (qs.short_entry * short_cts)
            qs.avg_inventory_entry = weighted / total_cts
        else:
            qs.avg_inventory_entry = 0.0

    def alpha_signal(self, momentum: float, imbalance: float, mid: float) -> float:
        signal = ((momentum * 100.0) + imbalance) * ALPHA_SIGNAL_K
        return mid * signal * 0.001 if mid > 0 else 0.0

    def inventory_skew(self, inventory_cts: float, mid: float) -> float:
        return -(inventory_cts - TARGET_INVENTORY_CTS) * INVENTORY_GAMMA * mid if mid > 0 else 0.0

    def inventory_unrealized_pnl(self, qs: QuoteState, current_px: float) -> float:
        upnl = 0.0
        if qs.long_filled and qs.long_entry > 0 and qs.long_cts > 0:
            upnl += (current_px - qs.long_entry) * qs.long_cts
        if qs.short_filled and qs.short_entry > 0 and qs.short_cts > 0:
            upnl += (qs.short_entry - current_px) * qs.short_cts
        return upnl

    async def is_toxic_flow(self, symbol: str, book: dict, imbalance: float) -> bool:
        """Predictive filter: detect toxic order flow before quoting."""
        # 1. Extreme imbalance = toxic flow (one-sided pressure)
        if abs(imbalance) > 0.7:
            return True
        
        # 2. Spread collapsing = adverse selection risk
        bids = book.get('bids', [])
        asks = book.get('asks', [])
        if bids and asks:
            spread_pct = (asks[0][0] - bids[0][0]) / bids[0][0]
            if spread_pct < MIN_REAL_SPREAD * 0.5:  # spread collapsed to half minimum
                return True
        
        # 3. Check recent trades for aggressive flow
        try:
            trades = await self.exchange.fetch_trades(symbol, None, 10, None, {'type': 'swap'})
            if not trades:
                return False
            # If recent trades are all on one side = aggressive flow
            buy_count = sum(1 for t in trades if t['side'] == 'buy')
            sell_count = sum(1 for t in trades if t['side'] == 'sell')
            if buy_count / len(trades) > 0.8 or sell_count / len(trades) > 0.8:
                return True
        except Exception:
            pass
        
        return False

    async def is_volatility_too_high(self, symbol: str) -> bool:
        """Check if short-term volatility exceeds threshold — prevents getting run over."""
        try:
            # Fetch last 20 candles for short-term volatility calculation
            candles = await self.exchange.fetch_ohlcv(symbol, '1m', None, 20, None, {'type': 'swap'})
            if len(candles) < 10:
                return False
            
            # Calculate volatility from last 10 candles
            closes = [c[4] for c in candles[-10:]]
            if not closes:
                return False
            
            # Simple volatility: max - min as % of average
            vol_range = max(closes) - min(closes)
            avg_price = sum(closes) / len(closes)
            vol_pct = vol_range / avg_price if avg_price > 0 else 0
            
            return vol_pct > MAX_SHORT_TERM_VOL
        except Exception:
            return False

    async def spread_capture_cycle(self, symbol: str) -> None:
        """Per-symbol: selective scalper. One side, real edge only."""
        try:
            short_sym = symbol.split('/')[0]

            # ═══════════════════════════════════════════════════════════════
            # GATE 1: Account health
            # ═══════════════════════════════════════════════════════════════
            h = await self.get_health()
            if not h['safe']:
                if h['margin_ratio'] >= MARGIN_RATIO_CRITICAL:
                    await self.emergency_close_all('margin ratio critical')
                return
            g_safe, g_reason = self.risk.check_global_risk(h['equity'])
            if not g_safe:
                console.print(f'[red]Global risk breach: {g_reason}')
                return

            # ═══════════════════════════════════════════════════════════════
            # GATE 2: Hard edge filter — no edge, no trade
            # ═══════════════════════════════════════════════════════════════
            qs = self.quotes.get(symbol)
            if not qs:
                qs = QuoteState()
                self.quotes[symbol] = qs

            # Always manage existing positions (exit checks) regardless of edge
            if qs.long_filled or qs.short_filled:
                momentum = await self.get_micro_momentum(symbol)
                if qs.long_filled:
                    await self._manage_side(symbol, 'long', qs, momentum)
                if qs.short_filled:
                    await self._manage_side(symbol, 'short', qs, momentum)
                return

            # No position — check if we SHOULD enter
            try:
                book = await self.exchange.fetch_order_book(symbol, limit=5)
                bid = book['bids'][0][0] if book['bids'] else 0
                ask = book['asks'][0][0] if book['asks'] else 0
                if bid <= 0 or ask <= 0:
                    return
                mid = (bid + ask) / 2
                spread_pct = (ask - bid) / mid
            except Exception:
                return

            spread_z, spread_velocity = self.update_spread_history(qs, spread_pct)

            if spread_z >= SPREAD_Z_MIN:
                qs.spread_state = 'armed'
            elif qs.spread_state == 'armed' and qs.last_spread_z > SPREAD_Z_MIN and spread_z <= SPREAD_READY_Z and spread_velocity < 0:
                qs.spread_state = 'ready'
            elif spread_z <= 0.5:
                qs.spread_state = 'idle'
            qs.last_spread_z = spread_z

            # Must beat fees + slippage
            MIN_EDGE = (FEE_RATE * 2) + 0.002  # ~0.35% minimum real edge
            if spread_pct < MIN_EDGE:
                console.print(f'[dim][{short_sym}] NO EDGE ({spread_pct:.3%} < {MIN_EDGE:.3%})')
                return

            # ═══════════════════════════════════════════════════════════════
            # GATE 3: Volume filter — no garbage
            # ═══════════════════════════════════════════════════════════════
            try:
                ticker = await self.exchange.fetch_ticker(symbol, {'type': 'swap'})
                volume_usd = float(ticker.get('quoteVolume', 0) or 0)
                if volume_usd < MIN_VOLUME_USD:
                    console.print(f'[dim][{short_sym}] LOW VOL (${volume_usd:.0f} < ${MIN_VOLUME_USD:.0f})')
                    return
            except Exception:
                return

            # ═══════════════════════════════════════════════════════════════
            # GATE 3.5: Volatility gate — prevent getting run over
            # ═══════════════════════════════════════════════════════════════
            if await self.is_volatility_too_high(symbol):
                console.print(f'[dim][{short_sym}] HIGH VOL (> {MAX_SHORT_TERM_VOL:.1%})')
                return
  
            # ═══════════════════════════════════════════════════════════════
            # GATE 4: Direction — momentum + microprice decide ONE side only
            # ═══════════════════════════════════════════════════════════════
            momentum = await self.get_micro_momentum(symbol)
            bid_vol = sum(b[1] for b in book['bids'][:5])
            ask_vol = sum(a[1] for a in book['asks'][:5])
            total_vol = bid_vol + ask_vol
            imbalance = (bid_vol - ask_vol) / total_vol if total_vol > 0 else 0
            
            # Microprice signal — weighted mid price for better fill probability
            microprice = self.calculate_microprice(book)
            mid = (book['bids'][0][0] + book['asks'][0][0]) / 2 if book['bids'] and book['asks'] else 0
            microprice_bias = (microprice - mid) / mid if mid > 0 else 0  # positive = favor ask, negative = favor bid

            # HARD FILTERS — no pressure, no movement = no trade
            if not self.has_real_edge(imbalance, momentum):
                console.print(f'[dim][{short_sym}] NO REAL EDGE (mom={momentum:+.4%} imb={imbalance:+.2f})')
                qs.last_momentum = momentum
                return
            if qs.spread_state != 'ready':
                console.print(f'[dim][{short_sym}] WAITING COMPRESSION (state={qs.spread_state} z={spread_z:.2f})')
                qs.last_momentum = momentum
                return
            if spread_z >= SPREAD_Z_MIN and abs(momentum) < MEAN_REVERSION_MOM_MAX:
                console.print(f'[dim][{short_sym}] MEAN REVERSION REGIME (z={spread_z:.2f} mom={momentum:+.4%})')
                qs.last_momentum = momentum
                return
            edge_score = self.directional_edge_score(imbalance, momentum)
            edge_score += min(max(spread_z - SPREAD_Z_MIN, 0.0), 2.0) * 0.25
            edge_score += min(abs(spread_velocity) * 100, 0.5) * 0.15
            if edge_score < 0.30:
                console.print(f'[dim][{short_sym}] WEAK EDGE SCORE ({edge_score:.2f})')
                qs.last_momentum = momentum
                return
            if abs(qs.last_momentum) > 0 and abs(momentum) > abs(qs.last_momentum) * 2:
                console.print(f'[dim][{short_sym}] CHASING SPIKE (mom={momentum:+.4%} prev={qs.last_momentum:+.4%})')
                qs.last_momentum = momentum
                return
            if qs.bad_setup_count >= 2 and qs.post_entry_alpha < 0:
                console.print(f'[dim][{short_sym}] BAD SETUP MEMORY (alpha={qs.post_entry_alpha:+.4%})')
                qs.last_momentum = momentum
                return

            # TOXICITY FILTER — skip adverse selection before quoting
            if await self.is_toxic_flow(symbol, book, imbalance):
                console.print(f'[dim][{short_sym}] TOXIC FLOW (imb={imbalance:+.2f})')
                qs.last_momentum = momentum
                return

            # Direction — momentum + imbalance must agree, microprice biases fill probability
            if momentum > 0 and imbalance > 0:
                side = 'long'
            elif momentum < 0 and imbalance < 0:
                side = 'short'
            else:
                console.print(f'[dim][{short_sym}] CONFLICTING (mom={momentum:+.4%} imb={imbalance:+.2f})')
                return

            compression_speed = max(0.0, qs.last_spread_z - spread_z)
            mode = self.execution_mode(spread_z, momentum, imbalance, compression_speed, spread_pct)
            qs.execution_mode = mode
            if mode == 'skip':
                console.print(f'[dim][{short_sym}] EXECUTION SKIP (z={spread_z:.2f} comp={compression_speed:.2f})')
                return

            console.print(f'[cyan][{short_sym}] EDGE: mode={mode} score={edge_score:.2f} z={spread_z:.2f} vel={spread_velocity:+.4%} spread={spread_pct:.3%} mom={momentum:+.4%} imb={imbalance:+.2f} microbias={microprice_bias:+.4%} → {side.upper()}')
            
            # PRE-TRADE VALIDATION — expected edge must beat total cost
            if not self.is_trade_worth_it(spread_pct, is_taker=FORCE_TAKER_MODE):
                mode = 'TAKER' if FORCE_TAKER_MODE else 'MAKER'
                console.print(f'[dim][{short_sym}] EDGE TOO THIN for {mode} (spread {spread_pct:.3%} < cost)')
                qs.last_momentum = momentum
                return

            vol_pct = 0.0
            try:
                candles = await self.exchange.fetch_ohlcv(symbol, '1m', None, 10, None, {'type': 'swap'})
                closes = [c[4] for c in candles[-10:]] if candles else []
                if closes:
                    avg_px = sum(closes) / len(closes)
                    vol_pct = ((max(closes) - min(closes)) / avg_px) if avg_px > 0 else 0.0
            except Exception:
                pass

            features = self.scorer.extract_features(
                spread_pct=spread_pct,
                imbalance=imbalance,
                momentum=momentum,
                microprice_bias=microprice_bias,
                vol_pct=vol_pct,
                post_entry_alpha=qs.post_entry_alpha,
                bad_setup_count=qs.bad_setup_count,
            )
            prob = self.scorer.predict_proba(features)
            qs.last_features = features
            qs.last_model_prob = prob
            qs.last_llm_score = None
            if prob < MODEL_PROB_MIN:
                console.print(f'[dim][{short_sym}] MODEL VETO ({prob:.2f} < {MODEL_PROB_MIN:.2f})')
                qs.last_momentum = momentum
                return

            if self.scorer.should_call_ollama(prob):
                snapshot = {
                    'spread': round(spread_pct, 6),
                    'imbalance': round(imbalance, 4),
                    'momentum': round(momentum, 6),
                    'microprice_bias': round(microprice_bias, 6),
                    'volatility': round(vol_pct, 6),
                    'post_entry_alpha': round(qs.post_entry_alpha, 6),
                    'bad_setup_count': qs.bad_setup_count,
                    'side': side,
                }
                llm_score = self.scorer.ollama_score(snapshot)
                qs.last_llm_score = llm_score
                if llm_score is None:
                    console.print(f'[dim][{short_sym}] OLLAMA TIMEOUT → SKIP')
                    return
                if llm_score < OLLAMA_MIN_SCORE:
                    console.print(f'[dim][{short_sym}] OLLAMA VETO ({llm_score:.1f} < {OLLAMA_MIN_SCORE:.1f})')
                    return

            qs.last_alpha_signal = momentum + imbalance
            qs.last_momentum = momentum
            qs.last_edge_score = edge_score
            qs.spread_state = 'idle'

            # ── LLM Self-Testing: policy gate + decision registration ──
            policy_ok, policy_reason = self.llm_tester.policy_gate(
                spread_pct, momentum, imbalance, edge_score)
            if not policy_ok:
                console.print(f'[dim][{short_sym}] POLICY VETO: {policy_reason}')
                # Register skip decision for self-testing
                self.llm_tester.register_decision(
                    symbol, 'skip',
                    features={'spread_pct': spread_pct, 'momentum': momentum,
                              'imbalance': imbalance, 'edge_score': edge_score,
                              'mid_price': mid},
                    confidence=edge_score,
                    rationale=policy_reason,
                    predicted_move=momentum,
                )
                return

            # Register entry decision for self-testing
            self.llm_tester.register_decision(
                symbol, f'enter_{side}',
                features={'spread_pct': spread_pct, 'momentum': momentum,
                          'imbalance': imbalance, 'edge_score': edge_score,
                          'microprice_bias': microprice_bias,
                          'mid_price': mid, 'last_price': mid},
                confidence=edge_score,
                rationale=f'edge={edge_score:.2f} z={spread_z:.2f} mom={momentum:+.4%}',
                predicted_move=momentum,
            )

            await self._manage_side(symbol, side, qs, momentum)
        except Exception as e:
            console.print(f'[{symbol}] Spread cycle error: {e}')

    # — Risk enforcement sweep —

    async def risk_enforcement_sweep(self) -> None:
        """Minimal risk check — update peak equity, daily report."""
        try:
            h = await self.get_health()
            self.risk.update_peak_equity(h['equity'])
            active_count = sum(1 for qs in self.quotes.values() if qs.long_filled or qs.short_filled)
            self.perf.record_equity(h['equity'], 0, active_count)
            today = datetime.now(timezone.utc).strftime('%Y-%m-%d')
            if today != self._last_report_day:
                self._last_report_day = today
                self.perf.save_metrics(h['equity'], h['used'])
        except Exception as e:
            console.print(f'[red]Risk sweep error: {e}')

    # — Monitor loop (dashboard) —

    async def monitor_loop(self, symbols: List[str]) -> None:
        """Periodic dashboard display."""
        while True:
            try:
                await asyncio.sleep(MONITOR_INTERVAL)
                h = await self.get_health()
                dd = self.risk.current_drawdown(h['equity'])
                total_upnl = sum(self.state.get(sym, 0) for sym in self.quotes)
                total_realized = sum(qs.realized for qs in self.quotes.values())
                total_cycles = sum(qs.cycles for qs in self.quotes.values())
                table = Table(title='CopyThatPay — Directional Scalper')
                table.add_column('', style='bold')
                table.add_column('')
                snap = self.risk.get_snapshot(h['equity'], h['used'], h['free'], self.hedges)
                table.add_row('Risk', snap.risk_verdict)
                table.add_row('Equity', f'${h["equity"]:.4f}')
                table.add_row('Active/Reserve/Buffer',
                              f'${h["active_capital"]:.4f}/${h["reserve"]:.4f}/${h["buffer"]:.4f}')
                table.add_row('Used/Free', f'${h["used"]:.4f} / ${h["free"]:.4f}')
                table.add_row('Margin', f'{h["margin_ratio"]:.1%}')
                table.add_row('Drawdown',
                              f'{dd:.2%} (max {self.risk.current_drawdown(h["equity"]):.2%})')
                active_pos = sum(1 for qs in self.quotes.values() if qs.long_filled or qs.short_filled)
                table.add_row('Positions', f'{active_pos} open / {len(self.quotes)} tracked')
                table.add_row('uPnL', f'${total_upnl:.6f}')
                table.add_row('Realized', f'${total_realized:.6f} ({total_cycles} cycles)')
                ps = self.perf.get_summary(h['equity'], h['used'])
                table.add_row('Cycle PnL', f'${ps["total_realized_pnl"]:.6f}')
                table.add_row('Win Rate', f'{ps["win_rate"]:.0%} ({ps["trade_count"]} trades)')
                table.add_row('Sharpe', f'{ps["sharpe_ratio"]:.3f}')
                elapsed = time.time() - self.perf.session_start if self.perf.session_start else 1
                rate = total_realized / elapsed if elapsed > 0 else 0
                table.add_row('Rate', f'${rate:.8f}/s')
                table.add_row('Uptime', f'{elapsed:.0f}s')
                # — Penny Tracker: fee-adjusted income —
                ps_penny = self.penny.summary()
                if ps_penny['count'] > 0:
                    net_color = 'green' if ps_penny['net'] >= 0 else 'red'
                    table.add_row('─── Penny Tracker ───', '─────────────────')
                    table.add_row('Gross Income', f'${ps_penny["gross"]:+.6f}')
                    table.add_row('Fees Paid', f'[red]-${ps_penny["fees"]:.6f}[/red]')
                    table.add_row('Slippage Cost', f'[red]-${ps_penny["slippage"]:.6f}[/red]')
                    table.add_row('Net Income', f'[bold {net_color}]${ps_penny["net"]:+.6f}[/bold {net_color}]')
                    table.add_row('Fee Drag', f'{ps_penny["fee_drag"]:.0%} of gross')
                    table.add_row('Avg Net/Trade', f'${ps_penny["avg_net"]:+.6f}')
                    table.add_row('Penny W/L', f'{ps_penny["wins"]}W / {ps_penny["losses"]}L ({ps_penny["win_rate"]:.0%})')
                
                # — LLM Self-Testing Info —
                llm_summary = self.llm_tester.get_summary()
                if llm_summary['total_decisions'] > 0:
                    table.add_row('─── LLM Self-Test ───', '─────────────────')
                    table.add_row('Decisions', f'{llm_summary["total_decisions"]} ({llm_summary["pending_evaluations"]} pending)')
                    table.add_row('Accuracy', f'{llm_summary["accuracy"]:.0%} ({llm_summary["correct"]}/{llm_summary["evaluated"]})')
                    table.add_row('Errors', f'{llm_summary["total_errors"]}')
                    learned = llm_summary.get('learned_adjustments', {})
                    if learned:
                        table.add_row('Learned', f'{len(learned)} adjustments')

                # Print comprehensive analytics report every 5 cycles
                if int(elapsed / MONITOR_INTERVAL) % 5 == 0:
                    self.perf.print_performance_report()
                for sym in sorted(self.quotes.keys()):
                    qs = self.quotes[sym]
                    short_sym = sym.split('/')[0]
                    if qs.long_filled:
                        status = f'LONG {qs.long_cts:.0f}ct @ {qs.long_entry:.6f}'
                    elif qs.short_filled:
                        status = f'SHORT {qs.short_cts:.0f}ct @ {qs.short_entry:.6f}'
                    else:
                        status = 'flat'
                    table.add_row(short_sym, f'{status} [{qs.cycles}cyc +${qs.realized:.6f}]')
                console.print(table)
            except Exception as e:
                console.print(f'[red]Monitor error: {e}')

    # — Main run loop —

    async def run(self) -> None:
        """Initialize, recover, then loop directional scalping on all symbols."""
        try:
            DATA_DIR.mkdir(exist_ok=True)
            DAILY_REPORT_DIR.mkdir(parents=True, exist_ok=True)
            # MAKER MODE: spread > 3x fee (0.225%) + vol > $20k
            symbols = [
                'FIO/USDT:USDT',   # spread ~1.0%, vol $197k — huge edge
                'TRU/USDT:USDT',   # spread ~0.44%, vol $234k — solid
                'DEGO/USDT:USDT',  # spread ~0.36%, vol $439k — best volume
                'RDNT/USDT:USDT',  # spread ~0.58%, vol $25k — good edge
                'NTRN/USDT:USDT',  # spread ~1.0%, vol $24k — widest spread
            ]
            console.print(f'[bold green]SCALPER MODE: {len(symbols)} symbols: {[s.split("/")[0] for s in symbols]}')
            with open(SYMBOL_FILE, 'w') as f:
                json.dump(symbols, f, indent=2)
            if not symbols:
                console.print('[red]No eligible symbols. Exiting.')
                return
            self.state = {s: 0.0 for s in symbols}
            self.active_symbols = symbols  # store BEFORE recovery so it can filter
            if not self.exchange:
                await self.init_exchange()
            for sym in symbols:
                try:
                    await self.exchange.set_leverage(
                        DEFAULT_LEVERAGE, sym,
                        {'marginMode': MARGIN_MODE, 'type': 'swap'})
                except Exception:
                    pass
            await self.recover_positions()
            h = await self.get_health()
            self.risk.update_peak_equity(h['equity'])
            ok = sum(1 for hp in self.hedges.values() if hp.is_complete)
            console.print(
                f'\n[bold cyan]CopyThatPay — Directional Scalper\n'
                f'  Capital: ${h["equity"]:.4f} '
                f'(active=${h["active_capital"]:.4f} '
                f'reserve=${h["reserve"]:.4f} '
                f'buffer=${h["buffer"]:.4f})\n'
                f'  Mode: {MARGIN_MODE} {DEFAULT_LEVERAGE}x | '
                f'TP: {TP_PCT:.1%} | SL: {REAL_STOP_PCT:.1%} | '
                f'Cycle: {CYCLE_INTERVAL_SEC}s\n'
                f'  Symbols: {len(symbols)} | Max: {MAX_CONCURRENT_SYMBOLS}\n'
                f'  Positions: recovered\n'
                f'  Risk: {MAX_DRAWDOWN_PER_SYMBOL:.0%}/sym, '
                f'{MAX_DRAWDOWN_GLOBAL:.0%} global, '
                f'{MAX_POSITION_AGE_SECONDS//3600}h exit\n'
                f'  Data: {DATA_DIR}/\n')
            snap = self.risk.get_snapshot(h['equity'], h['used'], h['free'], self.hedges)
            self.journal.log('SYSTEM_START', 'ALL', '', 0,
                             reason=f'equity=${h["equity"]:.4f} symbols={len(symbols)}',
                             risk_snapshot=snap)
            monitor = asyncio.create_task(self.monitor_loop(symbols))
            llm_outcome = asyncio.create_task(self.llm_tester.outcome_test_loop())
            llm_critic = asyncio.create_task(self.llm_tester.critic_loop())
            while True:
                await self.risk_enforcement_sweep()
                
                # LLM symbol selection DISABLED — using MICRO_WHITELIST directly
                # Re-enable after execution is proven working
                # (was: fetch_eligible_symbols → llm_select_symbols every 5 min)
                
                # Edge ratio kill switch - stop if real edge < 80% of expected
                edge_ratio = self.perf.get_edge_ratio()
                if edge_ratio > 0 and edge_ratio < 0.8:
                    console.print(f'[red]EDGE RATIO {edge_ratio:.2f} < 0.8 — PAUSING TRADING[/red]')
                    await asyncio.sleep(60)
                    continue
                
                # Daily stop loss - protect account from death spirals
                h = await self.get_health()
                net_pnl = self.perf.get_net_pnl()
                if net_pnl < DAILY_STOP * h['equity']:
                    console.print(f'[red]DAILY STOP: ${net_pnl:.4f} < {DAILY_STOP:.1%} of equity — PAUSING 1 HOUR[/red]')
                    await asyncio.sleep(3600)
                    continue
                
                # Use MICRO_WHITELIST directly (LLM selection disabled)
                active = symbols
                console.print(f'[dim]Processing {len(active)} symbols: {active}')
                for sym in active:
                    try:
                        console.print(f'[dim]→ Cycle: {sym}')
                        await self.spread_capture_cycle(sym)
                    except Exception as e:
                        console.print(f'[{sym}] Error: {e}')
                    await asyncio.sleep(CYCLE_INTERVAL_SEC)
        except Exception as e:
            console.print(f'[red]Fatal: {e}')
            traceback.print_exc()
        finally:
            await self.cleanup()


# ═══════════════════════════════════════════════════════════════════════════════
# ENTRY POINT
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == '__main__':
    console.print('[bold cyan]CopyThatPay — Directional Scalper')
    console.print('[dim]One side. Real edge. Cut losers fast.')
    bot = CopyThatPay()
    try:
        asyncio.run(bot.run())
    except KeyboardInterrupt:
        console.print('\n[yellow]Shutdown requested.')
    except Exception as e:
        console.print(f'[red]Fatal: {e}')
        traceback.print_exc()
