#!/usr/bin/env python3
"""
HEDGE BEAST — Unified Multi-Symbol Hedging System
==================================================
Combines the best of: godforbit.py, ena333.py, ena4.py, ena.py, melania.py,
ENA_Hedging_Project, gate_mm_beast, and Hedging_Project into one production system.

Features merged:
  [godforbit]   Async multi-symbol, HedgePair tracking, health monitor, emergency close,
                trade journal, state persistence, position recovery, LLM volatility scoring
  [ena/melania] DCA accumulation on opposite side, target-price limit closes, cancel stale
                reduce-only orders, exponential backoff, per-symbol config
  [ENA_Project] Per-symbol settings (leverage, size, threshold), multi-coin list, risk scoring
  [gate_beast]  Clean .env config, structured logging
  [Hedging_Proj] Token scanning, direct API patterns

Usage:
  1. Copy .env.example -> .env and fill in your Gate.io API keys
  2. (Optional) Edit SYMBOL_CONFIGS below or let auto-discovery find symbols
  3. python hedge_beast.py
"""

import ccxt.async_support as ccxt
import asyncio
import aiohttp
import json
import os
import sys
import time
import traceback
from dataclasses import dataclass, field, asdict
from dotenv import load_dotenv
from rich.console import Console
from rich.table import Table
from typing import List, Dict, Optional

load_dotenv()

# ══════════════════════════════════════════════════════════════
# API Keys — from .env ONLY
# ══════════════════════════════════════════════════════════════
API_KEY    = os.getenv('GATE_API_KEY', '')
API_SECRET = os.getenv('GATE_API_SECRET', '')
GROQ_KEY   = os.getenv('GROQ_API_KEY', '')

if not API_KEY or not API_SECRET:
    print('FATAL: Set GATE_API_KEY and GATE_API_SECRET in .env')
    sys.exit(1)

# ══════════════════════════════════════════════════════════════
# Files
# ══════════════════════════════════════════════════════════════
SYMBOL_FILE      = 'symbols.json'
STATE_FILE       = 'state.json'
HEDGE_STATE_FILE = 'hedge_state.json'
TRADE_LOG        = 'trades.jsonl'

# ══════════════════════════════════════════════════════════════
# Global Risk Rules (from godforbit — conservative baseline)
# ══════════════════════════════════════════════════════════════
MAX_NOTIONAL       = 0.10    # only symbols where 1 contract < $0.10
DEFAULT_LEVERAGE   = 3       # conservative default
MAX_EQUITY_PER_POS = 0.02    # max 2% equity per position margin
MAX_TOTAL_EXPOSURE = 0.30    # max 30% equity used total
MARGIN_RATIO_DANGER = 0.80   # emergency close above 80%
BALANCE_RESERVE    = 0.20    # keep 20% untouched
FEE_RATE           = 0.00075 # Gate.io taker fee
MARGIN_MODE        = 'cross' # 'cross' or 'isolated'

# ══════════════════════════════════════════════════════════════
# Behavior
# ══════════════════════════════════════════════════════════════
OFFSET             = 0.002   # 0.2% limit offset to cross spread
LOOP_DELAY         = 1.0     # seconds between symbol checks
MONITOR_INTERVAL   = 15      # seconds between dashboard prints
MAX_LIMIT_RETRIES  = 5       # max retries for order placement
FILL_TIMEOUT       = 10      # seconds to wait for fill

# ══════════════════════════════════════════════════════════════
# Per-Symbol Config (from ena/melania bots — proven settings)
# Keys are Gate.io swap symbols. Missing symbols use defaults.
# ══════════════════════════════════════════════════════════════
@dataclass
class SymbolConfig:
    leverage: int = DEFAULT_LEVERAGE
    trade_size: float = 1          # contracts per leg
    dca_size: float = 1            # contracts to DCA on opposite side
    profit_per_contract: float = 0.01   # $ net profit target per contract
    fee_per_contract: float = 0.002     # $ estimated fee per contract
    gross_threshold: float = 0.03       # $ gross threshold to exit (legacy compat)

SYMBOL_CONFIGS: Dict[str, SymbolConfig] = {
    'PEPE/USDT:USDT':    SymbolConfig(leverage=20, trade_size=1.69, dca_size=0.69,
                                       profit_per_contract=0.01, fee_per_contract=0.002),
    'ENA/USDT:USDT':     SymbolConfig(leverage=3,  trade_size=1,    dca_size=0.69,
                                       profit_per_contract=0.0369, fee_per_contract=0.002),
    'GOAT/USDT:USDT':    SymbolConfig(leverage=3,  trade_size=1,    dca_size=1,
                                       profit_per_contract=0.01, fee_per_contract=0.002),
    'MELANIA/USDT:USDT': SymbolConfig(leverage=10, trade_size=1,    dca_size=1,
                                       profit_per_contract=0.0369, fee_per_contract=0.002),
}

DEFAULT_SYM_CFG = SymbolConfig()

def get_sym_cfg(symbol: str) -> SymbolConfig:
    return SYMBOL_CONFIGS.get(symbol, DEFAULT_SYM_CFG)

console = Console()

# ══════════════════════════════════════════════════════════════
# Dataclasses — hedge state tracking (from godforbit)
# ══════════════════════════════════════════════════════════════
@dataclass
class HedgeLeg:
    contracts: float = 0
    entry: float = 0
    timestamp: float = 0
    filled: bool = False

@dataclass
class HedgePair:
    long_leg: HedgeLeg = field(default_factory=HedgeLeg)
    short_leg: HedgeLeg = field(default_factory=HedgeLeg)
    hedge_open_time: float = 0
    long_dca_total: float = 0   # accumulated DCA on long side
    short_dca_total: float = 0  # accumulated DCA on short side
    harvests: int = 0           # total harvest cycles completed

    @property
    def is_complete(self) -> bool:
        return self.long_leg.filled and self.short_leg.filled

    @property
    def is_empty(self) -> bool:
        return not self.long_leg.filled and not self.short_leg.filled

    @property
    def is_broken(self) -> bool:
        return self.long_leg.filled != self.short_leg.filled


# ══════════════════════════════════════════════════════════════
# THE BEAST
# ══════════════════════════════════════════════════════════════
class HedgeBeast:
    def __init__(self):
        self.exchange = None
        self.state: Dict[str, float] = {}        # symbol -> unrealized PnL
        self.hedges: Dict[str, HedgePair] = {}   # symbol -> HedgePair
        self.total_harvested: float = 0.0         # lifetime realized profit
        self.session_start: float = 0.0

    # ── exchange ──────────────────────────────────────────

    async def init_exchange(self) -> None:
        self.exchange = ccxt.gateio({
            'apiKey': API_KEY,
            'secret': API_SECRET,
            'enableRateLimit': True,
            'options': {
                'defaultType': 'swap',
                'defaultSettle': 'usdt',
                'adjustForTimeDifference': True,
                'recvWindow': 60000,
            }
        })
        await self.exchange.load_markets()

    async def cleanup(self) -> None:
        if self.exchange:
            try:
                await self.exchange.close()
            except Exception:
                pass

    # ── trade journal (from godforbit) ────────────────────

    def log_trade(self, action: str, symbol: str, side: str, contracts: float,
                  price: float = 0, pnl: float = 0, note: str = ''):
        record = {
            'ts': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
            'epoch': time.time(),
            'action': action,
            'symbol': symbol,
            'side': side,
            'contracts': contracts,
            'price': price,
            'pnl': pnl,
            'note': note,
        }
        try:
            with open(TRADE_LOG, 'a') as f:
                f.write(json.dumps(record) + '\n')
        except Exception:
            pass

    # ── health monitor (from godforbit) ───────────────────

    async def get_health(self) -> dict:
        h = {'equity': 0, 'used': 0, 'free': 0, 'margin_ratio': 0, 'safe': True}
        try:
            bal = await self.exchange.fetch_balance()
            total = float(bal.get('total', {}).get('USDT', 0) or 0)
            used  = float(bal.get('used', {}).get('USDT', 0) or 0)
            free  = float(bal.get('free', {}).get('USDT', 0) or 0)
            if free <= 0:
                free = float(bal.get('info', {}).get('available', 0) or 0)
            if free <= 0:
                free = max(total - used, 0)
            mr = used / total if total > 0 else 0
            h.update({
                'equity': total, 'used': used, 'free': free,
                'margin_ratio': mr,
                'safe': mr < MARGIN_RATIO_DANGER and (used / total if total > 0 else 0) < MAX_TOTAL_EXPOSURE,
            })
        except Exception as e:
            console.print(f"[red]Health error: {e}")
            h['safe'] = False
        return h

    # ── emergency close (from godforbit — limit+market fallback) ──

    async def emergency_close_all(self) -> None:
        console.print("[bold red]EMERGENCY FLATTEN — margin ratio critical")
        try:
            positions = await self.exchange.fetch_positions(None, {'type': 'swap'})
            for pos in positions:
                ct = float(pos.get('contracts', 0) or 0)
                if ct <= 0:
                    continue
                sym = pos['symbol']
                side = pos['side']
                close_side = 'sell' if side == 'long' else 'buy'
                closed = False
                try:
                    tk = await self.exchange.fetch_ticker(sym, {'type': 'swap'})
                    px = float(tk['last'])
                    lim = px * 0.995 if close_side == 'sell' else px * 1.005
                    await self.exchange.create_limit_order(
                        sym, close_side, ct, lim,
                        {'marginMode': MARGIN_MODE, 'reduceOnly': True, 'type': 'swap'}
                    )
                    console.print(f"[red]  Limit close {sym} {side} {ct}ct")
                    closed = True
                except Exception:
                    pass
                if not closed:
                    try:
                        await self.exchange.create_market_order(
                            sym, close_side, ct,
                            {'marginMode': MARGIN_MODE, 'reduceOnly': True, 'type': 'swap'}
                        )
                        console.print(f"[red]  Market close {sym} {side} {ct}ct")
                    except Exception as e2:
                        console.print(f"[bold red]  FAILED {sym}: {e2}")
                await asyncio.sleep(0.2)
        except Exception as e:
            console.print(f"[red]Emergency error: {e}")
        self.hedges.clear()
        self.save_hedge_state()
        self.log_trade('EMERGENCY_FLATTEN', 'ALL', '', 0, note='margin critical')

    # ── cancel stale orders (from ena bots) ───────────────

    async def cancel_reduce_orders(self, symbol: str) -> None:
        try:
            open_orders = await self.exchange.fetch_open_orders(
                symbol, params={'marginMode': MARGIN_MODE, 'type': 'swap'}
            )
            for order in open_orders:
                reduce = order.get('reduceOnly', False)
                if not reduce:
                    info = order.get('info', {})
                    reduce = info.get('is_reduce_only', False) or info.get('reduce_only', False)
                if reduce:
                    await self.exchange.cancel_order(
                        order['id'], symbol,
                        {'marginMode': MARGIN_MODE, 'type': 'swap'}
                    )
                    console.print(f"[dim][{symbol}] Cancelled stale reduce order {order['id']}[/dim]")
        except Exception:
            pass

    # ── order sizing (from godforbit — budget-aware) ──────

    async def safe_size(self, symbol: str) -> int:
        cfg = get_sym_cfg(symbol)
        try:
            h = await self.get_health()
            if not h['safe']:
                return 0
            usable = h['equity'] * (1 - BALANCE_RESERVE)
            if h['used'] >= usable:
                return 0
            mkt = self.exchange.market(symbol)
            tk = await self.exchange.fetch_ticker(symbol, {'type': 'swap'})
            px = float(tk['last'])
            if px <= 0:
                return 0
            cs = float(mkt.get('contractSize', 1) or 1)
            ntl = px * cs
            lev = cfg.leverage
            mrg = ntl / lev
            min_ct = max(int(mkt.get('limits', {}).get('amount', {}).get('min') or 1), int(cfg.trade_size))
            if mrg * min_ct > h['free'] * 0.90:
                return 0
            if mrg * min_ct > h['equity'] * MAX_EQUITY_PER_POS:
                return 0
            if ntl * min_ct > MAX_NOTIONAL * max(min_ct, 1):
                return 0
            return min_ct
        except Exception as e:
            console.print(f"[{symbol}] Size err: {e}")
            return 0

    # ── open position (async, with retries + backoff from ena bots) ──

    async def open_position(self, symbol: str, side: str) -> bool:
        cfg = get_sym_cfg(symbol)
        ct = await self.safe_size(symbol)
        if ct <= 0:
            return False

        delay = 1
        for attempt in range(MAX_LIMIT_RETRIES):
            try:
                tk = await self.exchange.fetch_ticker(symbol, {'type': 'swap'})
                px = float(tk['last'])
                if side == 'buy':
                    lim = px * (1 + OFFSET)
                else:
                    lim = px * (1 - OFFSET)
                order = await self.exchange.create_limit_order(
                    symbol, side, ct, lim,
                    {'marginMode': MARGIN_MODE, 'type': 'swap'}
                )
                console.print(f"[cyan][{symbol}] {side.upper()} {ct}ct @ {lim:.8f} (attempt {attempt+1})")
                if await self._wait_fill(symbol, side, ct):
                    console.print(f"[bold green][{symbol}] {side.upper()} FILLED")
                    return True
                # Not filled — cancel and retry with adjusted price
                try:
                    await self.exchange.cancel_order(order['id'], symbol, {'type': 'swap'})
                except Exception:
                    pass
                # Exponential backoff + deeper offset (from ena bots)
                await asyncio.sleep(delay)
                delay = min(delay * 2, 8)
            except Exception as e:
                console.print(f"[{symbol}] {side} #{attempt+1}: {e}")
                await asyncio.sleep(delay)
                delay = min(delay * 2, 8)
        return False

    async def _wait_fill(self, symbol: str, side: str, target: float, timeout: int = FILL_TIMEOUT) -> bool:
        t0 = time.time()
        want = 'long' if side == 'buy' else 'short'
        while time.time() - t0 < timeout:
            try:
                pos = await self.exchange.fetch_positions([symbol], {'type': 'swap'})
                filled = sum(float(p['contracts']) for p in pos if p['side'] == want and float(p.get('contracts', 0)) > 0)
                if filled >= target:
                    return True
            except Exception:
                pass
            await asyncio.sleep(1)
        return False

    # ── close at target price (from ena bots — limit + cancel stale) ──

    async def close_at_target(self, symbol: str, side: str, contracts: float,
                              target_price: float) -> bool:
        """Close position with limit order at calculated target price.
        Cancels stale reduce orders first (from ena bots)."""
        await self.cancel_reduce_orders(symbol)
        close_side = 'sell' if side == 'long' else 'buy'
        delay = 1
        for attempt in range(MAX_LIMIT_RETRIES):
            try:
                await self.exchange.create_limit_order(
                    symbol, close_side, contracts, target_price,
                    {'marginMode': MARGIN_MODE, 'reduceOnly': True, 'type': 'swap'}
                )
                console.print(
                    f"[green][{symbol}] Close {side} {contracts}ct @ {target_price:.8f} "
                    f"(attempt {attempt+1})"
                )
                return True
            except Exception as e:
                console.print(f"[{symbol}] close #{attempt+1}: {e}")
                await self.cancel_reduce_orders(symbol)
                await asyncio.sleep(delay)
                delay = min(delay * 2, 8)
        return False

    async def close_position_market(self, symbol: str, side: str, contracts: float) -> bool:
        """Market order fallback for closing."""
        close_side = 'sell' if side == 'long' else 'buy'
        try:
            await self.exchange.create_market_order(
                symbol, close_side, contracts,
                {'marginMode': MARGIN_MODE, 'reduceOnly': True, 'type': 'swap'}
            )
            return True
        except Exception as e:
            console.print(f"[red][{symbol}] Market close failed: {e}")
            return False

    # ── DCA on opposite side (from ena bots) ──────────────

    async def dca_opposite(self, symbol: str, closed_side: str) -> None:
        """When one leg closes profitably, DCA the opposite side (from ena bots)."""
        cfg = get_sym_cfg(symbol)
        dca = cfg.dca_size
        if dca <= 0:
            return
        opp_side = 'sell' if closed_side == 'long' else 'buy'
        opp_label = 'SHORT' if closed_side == 'long' else 'LONG'
        console.print(f"[cyan][{symbol}] DCA +{dca}ct on {opp_label}")
        try:
            tk = await self.exchange.fetch_ticker(symbol, {'type': 'swap'})
            px = float(tk['last'])
            lim = px * (1 + OFFSET) if opp_side == 'buy' else px * (1 - OFFSET)
            await self.exchange.create_limit_order(
                symbol, opp_side, dca, lim,
                {'marginMode': MARGIN_MODE, 'type': 'swap'}
            )
            # Track DCA totals
            hp = self.hedges.get(symbol)
            if hp:
                if closed_side == 'long':
                    hp.short_dca_total += dca
                else:
                    hp.long_dca_total += dca
            self.log_trade('DCA', symbol, opp_side, dca, price=lim,
                           note=f'opposite DCA after {closed_side} harvest')
        except Exception as e:
            console.print(f"[yellow][{symbol}] DCA failed: {e}")

    # ── hedge state persistence (from godforbit) ──────────

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
        if not os.path.exists(HEDGE_STATE_FILE):
            return
        try:
            with open(HEDGE_STATE_FILE) as f:
                data = json.load(f)
            for sym, hp_dict in data.items():
                ll = hp_dict.get('long_leg', {})
                sl = hp_dict.get('short_leg', {})
                self.hedges[sym] = HedgePair(
                    long_leg=HedgeLeg(**ll),
                    short_leg=HedgeLeg(**sl),
                    hedge_open_time=hp_dict.get('hedge_open_time', 0),
                    long_dca_total=hp_dict.get('long_dca_total', 0),
                    short_dca_total=hp_dict.get('short_dca_total', 0),
                    harvests=hp_dict.get('harvests', 0),
                )
        except Exception:
            pass

    # ── position recovery (from godforbit — upgraded for hedges) ──

    async def recover_positions(self) -> None:
        self.load_hedge_state()
        if self.hedges:
            console.print(f"[cyan]Loaded {len(self.hedges)} persisted hedge pairs from disk")
        try:
            all_pos = await self.exchange.fetch_positions(None, {'type': 'swap'})
            by_symbol: Dict[str, list] = {}
            for pos in all_pos:
                ct = float(pos.get('contracts', 0) or 0)
                if ct <= 0:
                    continue
                by_symbol.setdefault(pos['symbol'], []).append(pos)

            recovered = 0
            for sym, pos_list in by_symbol.items():
                now = time.time()
                hp = self.hedges.get(sym, HedgePair(hedge_open_time=now))
                for pos in pos_list:
                    ct = float(pos.get('contracts', 0) or 0)
                    side = pos['side']
                    entry = float(pos.get('entryPrice', 0) or 0)
                    upnl = float(pos.get('unrealizedPnl', 0) or 0)
                    leg = HedgeLeg(contracts=ct, entry=entry,
                                   timestamp=hp.hedge_open_time or now, filled=True)
                    if side == 'long':
                        hp.long_leg = leg
                    elif side == 'short':
                        hp.short_leg = leg
                    self.state[sym] = self.state.get(sym, 0) + upnl
                    recovered += 1
                self.hedges[sym] = hp
                status = "OK" if hp.is_complete else ("BROKEN" if hp.is_broken else "EMPTY")
                l_info = f"L:{hp.long_leg.contracts}ct@{hp.long_leg.entry:.6f}" if hp.long_leg.filled else "L:none"
                s_info = f"S:{hp.short_leg.contracts}ct@{hp.short_leg.entry:.6f}" if hp.short_leg.filled else "S:none"
                console.print(f"[cyan]  {sym} [{status}] {l_info} {s_info}")
            self.save_hedge_state()
            if recovered:
                ok = sum(1 for hp in self.hedges.values() if hp.is_complete)
                broken = sum(1 for hp in self.hedges.values() if hp.is_broken)
                console.print(f"[bold cyan]Recovered {recovered} legs — {ok} complete, {broken} broken")
                self.log_trade('RECOVER', 'ALL', '', 0, note=f'{recovered} legs, {ok} ok, {broken} broken')
        except Exception as e:
            console.print(f"[red]Recovery error: {e}")

    # ── LLM volatility scorer (from godforbit — symbol prioritizer) ──

    async def _fetch_market_context(self, symbol: str) -> str:
        try:
            tk = await self.exchange.fetch_ticker(symbol, {'type': 'swap'})
            ohlcv = await self.exchange.fetch_ohlcv(symbol, '5m', limit=6)
            last = float(tk.get('last', 0))
            pct24 = float(tk.get('percentage', 0) or 0)
            vol24 = float(tk.get('quoteVolume', 0) or 0)
            closes = [c[4] for c in ohlcv] if ohlcv else []
            candle_str = ', '.join(f'{c:.8f}' for c in closes[-6:])
            return (
                f"Symbol: {symbol}\nLast: {last:.8f}\n24h change: {pct24:+.2f}%\n"
                f"24h vol USDT: {vol24:.0f}\nRecent 5m closes: [{candle_str}]"
            )
        except Exception:
            return f"Symbol: {symbol} (no data)"

    async def llm_score_symbol(self, symbol: str) -> float:
        if not GROQ_KEY:
            return 5.0
        try:
            context = await self._fetch_market_context(symbol)
            async with aiohttp.ClientSession() as sess:
                payload = {
                    "model": "llama-3.1-8b-instant",
                    "messages": [
                        {"role": "system", "content": (
                            "Score this crypto symbol 0-10 for short-term volatility. "
                            "Higher = more volatile = better for hedged profit harvesting. "
                            "Reply with ONLY a number."
                        )},
                        {"role": "user", "content": context}
                    ],
                    "max_tokens": 5, "temperature": 0.1,
                }
                headers = {"Authorization": f"Bearer {GROQ_KEY}", "Content-Type": "application/json"}
                async with sess.post(
                    "https://api.groq.com/openai/v1/chat/completions",
                    json=payload, headers=headers, timeout=aiohttp.ClientTimeout(total=8)
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        return max(0.0, min(10.0, float(data['choices'][0]['message']['content'].strip())))
        except Exception:
            pass
        return 5.0

    # ── symbol selection (from godforbit — auto-discovery + manual) ──

    async def fetch_eligible_symbols(self) -> List[str]:
        if not self.exchange:
            await self.init_exchange()
        h = await self.get_health()
        free = h['free']
        if free <= 0:
            return []

        # Manual symbols from config always included if they exist
        manual = list(SYMBOL_CONFIGS.keys())

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
            cfg = get_sym_cfg(sym)
            mrg = ntl / cfg.leverage
            if ntl <= MAX_NOTIONAL or sym in manual:
                candidates.append((sym, ntl, mrg))

        candidates.sort(key=lambda x: x[2])
        budget = free * (1 - BALANCE_RESERVE)
        selected, running = [], 0.0
        for sym, ntl, mrg in candidates:
            hedge_cost = mrg * 2
            if running + hedge_cost <= budget:
                selected.append((sym, ntl, mrg))
                running += hedge_cost

        console.print(f"[bold green]{len(selected)} symbols eligible (hedge margin ${running:.4f})")
        for sym, ntl, mrg in selected[:20]:
            console.print(f"  [green]{sym:<30}[/green] ntl=${ntl:.6f} hedge=${mrg*2:.6f}")
        if len(selected) > 20:
            console.print(f"  ... and {len(selected)-20} more")
        return [s for s, _, _ in selected]

    # ══════════════════════════════════════════════════════════
    # HEDGE EXECUTION LAYER
    # ══════════════════════════════════════════════════════════

    async def flatten_symbol(self, symbol: str, reason: str = '') -> None:
        """Close both legs — return to flat (from godforbit with market fallback)."""
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
                        {'marginMode': MARGIN_MODE, 'reduceOnly': True, 'type': 'swap'}
                    )
                    console.print(f"[red][{symbol}] Flatten {side} {ct}ct ({reason})")
                except Exception:
                    try:
                        await self.exchange.create_market_order(
                            symbol, close_side, ct,
                            {'marginMode': MARGIN_MODE, 'reduceOnly': True, 'type': 'swap'}
                        )
                        console.print(f"[red][{symbol}] Market flatten {side} {ct}ct ({reason})")
                    except Exception as e2:
                        console.print(f"[bold red][{symbol}] FLATTEN FAILED {side}: {e2}")
                await asyncio.sleep(0.3)
        except Exception as e:
            console.print(f"[red][{symbol}] Flatten error: {e}")
        self.hedges.pop(symbol, None)
        self.state[symbol] = 0.0
        self.log_trade('EMERGENCY_FLATTEN', symbol, '', 0, note=reason)
        self.save_hedge_state()

    async def hedge_open_pair(self, symbol: str) -> bool:
        """Atomic: open LONG + SHORT. Rollback on failure (from godforbit)."""
        h = await self.get_health()
        if not h['safe']:
            return False

        ct = await self.safe_size(symbol)
        if ct <= 0:
            return False

        cfg = get_sym_cfg(symbol)
        mkt = self.exchange.market(symbol)
        cs = float(mkt.get('contractSize', 1) or 1)
        tk = await self.exchange.fetch_ticker(symbol, {'type': 'swap'})
        px = float(tk['last'])
        margin_both = (px * cs * ct / cfg.leverage) * 2
        if margin_both > h['free'] * 0.90:
            console.print(f"[yellow][{symbol}] Can't afford hedge (need ${margin_both:.6f})")
            return False

        # LONG leg
        console.print(f"[cyan][{symbol}] Opening hedge: LONG leg...")
        if not await self.open_position(symbol, 'buy'):
            self.log_trade('HEDGE_BROKEN', symbol, 'long', 0, note='long failed')
            return False
        await asyncio.sleep(0.5)

        # SHORT leg
        console.print(f"[cyan][{symbol}] Opening hedge: SHORT leg...")
        if not await self.open_position(symbol, 'sell'):
            console.print(f"[yellow][{symbol}] Short failed — rolling back long")
            await self.flatten_symbol(symbol, reason='hedge rollback: short failed')
            return False

        # Confirm both on exchange
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
                    hp.long_leg = HedgeLeg(contracts=pct, entry=entry, timestamp=now, filled=True)
                elif pos['side'] == 'short':
                    hp.short_leg = HedgeLeg(contracts=pct, entry=entry, timestamp=now, filled=True)

            if hp.is_complete:
                self.hedges[symbol] = hp
                self.save_hedge_state()
                console.print(
                    f"[bold green][{symbol}] HEDGE OPEN — "
                    f"L:{hp.long_leg.contracts}ct@{hp.long_leg.entry:.8f} "
                    f"S:{hp.short_leg.contracts}ct@{hp.short_leg.entry:.8f}"
                )
                self.log_trade('HEDGE_OPEN', symbol, 'both', ct, price=px,
                               note=f'L@{hp.long_leg.entry:.8f} S@{hp.short_leg.entry:.8f}')
                return True
            else:
                await self.flatten_symbol(symbol, reason='incomplete after fills')
                return False
        except Exception as e:
            await self.flatten_symbol(symbol, reason=f'confirm error: {e}')
            return False

    async def hedge_harvest(self, symbol: str) -> None:
        """Close profitable leg at target price, DCA opposite, reopen (combined logic)."""
        hp = self.hedges.get(symbol)
        if not hp or not hp.is_complete:
            return

        cfg = get_sym_cfg(symbol)
        try:
            positions = await self.exchange.fetch_positions([symbol], {'type': 'swap'})
            mkt = self.exchange.market(symbol)
            cs = float(mkt.get('contractSize', 1) or 1)

            for pos in positions:
                ct = float(pos.get('contracts', 0) or 0)
                if ct <= 0:
                    continue
                side = pos['side']
                upnl = float(pos.get('unrealizedPnl', 0) or 0)
                entry = float(pos.get('entryPrice', 0) or 0)

                # Profit threshold: per-contract scaling (from ena bots)
                effective_threshold = (cfg.profit_per_contract + cfg.fee_per_contract) * ct
                min_profit = max(effective_threshold, cfg.gross_threshold)

                if upnl > min_profit:
                    # Calculate TARGET EXIT PRICE (from ena bots — not just PnL check)
                    per_ct_target = min_profit / ct
                    if side == 'long':
                        target_price = entry + per_ct_target
                    else:
                        target_price = entry - per_ct_target

                    console.print(
                        f"[bold green][{symbol}] {side} PROFIT ${upnl:.6f} > ${min_profit:.6f} "
                        f"— harvesting @ {target_price:.8f}"
                    )

                    # Close at target price (from ena bots)
                    closed = await self.close_at_target(symbol, side, ct, target_price)
                    if not closed:
                        # Fallback: try with spread-crossing price
                        tk = await self.exchange.fetch_ticker(symbol, {'type': 'swap'})
                        px = float(tk['last'])
                        close_side = 'sell' if side == 'long' else 'buy'
                        fallback_price = px * (1 - OFFSET) if close_side == 'sell' else px * (1 + OFFSET)
                        closed = await self.close_at_target(symbol, side, ct, fallback_price)

                    if closed:
                        self.total_harvested += upnl
                        hp.harvests += 1
                        self.log_trade('LEG_CLOSE_PROFIT', symbol, side, ct, entry,
                                       pnl=upnl, note=f'harvest#{hp.harvests} target={target_price:.8f}')

                        if side == 'long':
                            hp.long_leg.filled = False
                        else:
                            hp.short_leg.filled = False
                        self.save_hedge_state()
                        await asyncio.sleep(1)

                        # DCA on opposite side (from ena bots)
                        await self.dca_opposite(symbol, side)
                        await asyncio.sleep(0.5)

                        # Reopen same side
                        reopen_side = 'buy' if side == 'long' else 'sell'
                        console.print(f"[cyan][{symbol}] Reopening {side} leg...")
                        if await self.open_position(symbol, reopen_side):
                            new_pos = await self.exchange.fetch_positions([symbol], {'type': 'swap'})
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
                            console.print(f"[bold green][{symbol}] {side} REOPENED — cycle complete")
                            self.log_trade('LEG_REOPEN', symbol, side, ct, note='profit cycle')
                        else:
                            self.log_trade('HEDGE_BROKEN', symbol, side, 0, note='reopen failed')
                    # Only one leg per cycle
                    return

            # Update combined uPnL
            total_upnl = sum(
                float(p.get('unrealizedPnl', 0) or 0)
                for p in positions if float(p.get('contracts', 0) or 0) > 0
            )
            self.state[symbol] = total_upnl

        except Exception as e:
            console.print(f"[red][{symbol}] Harvest error: {e}")

    async def hedge_repair(self, symbol: str) -> None:
        """Detect and fix broken hedges (from godforbit)."""
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
                self.save_hedge_state()
                return

            missing = 'long' if not has_long else 'short'
            console.print(f"[yellow][{symbol}] Broken — {missing} missing, repairing...")
            self.log_trade('HEDGE_REPAIR', symbol, missing, 0, note='attempting')

            h = await self.get_health()
            if not h['safe']:
                await self.flatten_symbol(symbol, reason='unsafe to repair')
                return

            reopen_side = 'buy' if missing == 'long' else 'sell'
            if await self.open_position(symbol, reopen_side):
                new_pos = await self.exchange.fetch_positions([symbol], {'type': 'swap'})
                for np_ in new_pos:
                    nct = float(np_.get('contracts', 0) or 0)
                    if nct > 0 and np_['side'] == missing:
                        leg = HedgeLeg(contracts=nct, entry=float(np_.get('entryPrice', 0) or 0),
                                       timestamp=time.time(), filled=True)
                        if missing == 'long':
                            hp.long_leg = leg
                        else:
                            hp.short_leg = leg
                        break
                self.save_hedge_state()
                console.print(f"[bold green][{symbol}] REPAIRED — {missing} reopened")
                self.log_trade('HEDGE_REPAIR', symbol, missing, 1, note='success')
            else:
                await self.flatten_symbol(symbol, reason=f'{missing} repair failed')
        except Exception as e:
            console.print(f"[red][{symbol}] Repair error: {e}")

    async def _register_hedge_from_exchange(self, symbol: str) -> None:
        """Register exchange positions as a HedgePair."""
        now = time.time()
        try:
            positions = await self.exchange.fetch_positions([symbol], {'type': 'swap'})
            new_hp = HedgePair(hedge_open_time=now)
            for pos in positions:
                ct = float(pos.get('contracts', 0) or 0)
                if ct <= 0:
                    continue
                entry = float(pos.get('entryPrice', 0) or 0)
                leg = HedgeLeg(contracts=ct, entry=entry, timestamp=now, filled=True)
                if pos['side'] == 'long':
                    new_hp.long_leg = leg
                elif pos['side'] == 'short':
                    new_hp.short_leg = leg
            if new_hp.is_complete:
                self.hedges[symbol] = new_hp
                self.save_hedge_state()
                console.print(f"[bold green][{symbol}] Hedge registered from exchange")
                self.log_trade('HEDGE_OPEN', symbol, 'both', 0, note='registered')
            else:
                await self.flatten_symbol(symbol, reason='registration incomplete')
        except Exception as e:
            console.print(f"[red][{symbol}] Register error: {e}")

    # ══════════════════════════════════════════════════════════
    # MAIN TRADE LOGIC — HEDGED MARKET-NEUTRAL ENGINE
    # ══════════════════════════════════════════════════════════

    async def execute_trade(self, symbol: str) -> None:
        """Per-symbol: maintain hedge pair, harvest profits, DCA, repair breaks."""
        try:
            h = await self.get_health()
            if not h['safe']:
                console.print(f"[red][{symbol}] Skip — unsafe (MR {h['margin_ratio']:.1%})")
                if h['margin_ratio'] >= MARGIN_RATIO_DANGER:
                    await self.emergency_close_all()
                return

            hp = self.hedges.get(symbol)

            if hp:
                if hp.is_broken:
                    await self.hedge_repair(symbol)
                elif hp.is_complete:
                    await self.hedge_harvest(symbol)
                elif hp.is_empty:
                    self.hedges.pop(symbol, None)
                    self.save_hedge_state()
            else:
                # Check for orphaned positions
                positions = await self.exchange.fetch_positions([symbol], {'type': 'swap'})
                active = [p for p in positions if float(p.get('contracts', 0) or 0) > 0]
                if active:
                    has_long = any(p['side'] == 'long' for p in active if float(p.get('contracts', 0) or 0) > 0)
                    has_short = any(p['side'] == 'short' for p in active if float(p.get('contracts', 0) or 0) > 0)
                    if has_long and has_short:
                        await self._register_hedge_from_exchange(symbol)
                    elif has_long:
                        console.print(f"[cyan][{symbol}] Orphan long — adding short leg")
                        if await self.open_position(symbol, 'sell'):
                            await self._register_hedge_from_exchange(symbol)
                        else:
                            await self.flatten_symbol(symbol, reason='orphan completion failed')
                    elif has_short:
                        console.print(f"[cyan][{symbol}] Orphan short — adding long leg")
                        if await self.open_position(symbol, 'buy'):
                            await self._register_hedge_from_exchange(symbol)
                        else:
                            await self.flatten_symbol(symbol, reason='orphan completion failed')
                    return

                # Fresh entry
                if not await self.hedge_open_pair(symbol):
                    self.log_trade('SKIP', symbol, '', 0, note='pair open failed')

        except Exception as e:
            console.print(f"[{symbol}] Error: {e}")

    # ── monitor (from godforbit — enhanced with harvest stats) ──

    async def monitor_loop(self, symbols: List[str]) -> None:
        while True:
            try:
                total_pnl = sum(self.state.values())
                elapsed = max(time.time() - self.session_start, 1)
                h = await self.get_health()
                ok = sum(1 for hp in self.hedges.values() if hp.is_complete)
                broken = sum(1 for hp in self.hedges.values() if hp.is_broken)
                total_harvests = sum(hp.harvests for hp in self.hedges.values())
                status = "[green]SAFE" if h['safe'] else "[red]DANGER"

                table = Table(title="HEDGE BEAST", show_header=False, border_style="cyan")
                table.add_row("Status", f"[bold]{status}[/bold]")
                table.add_row("Equity", f"${h['equity']:.4f}")
                table.add_row("Used / Free", f"${h['used']:.4f} / ${h['free']:.4f}")
                table.add_row("Margin Ratio", f"{h['margin_ratio']:.1%}")
                table.add_row("Hedges", f"{ok} ok / {broken} broken / {len(symbols)} symbols")
                table.add_row("uPnL", f"${total_pnl:.6f}")
                table.add_row("Harvested", f"${self.total_harvested:.6f} ({total_harvests} cycles)")
                table.add_row("Rate", f"${total_pnl/elapsed:.8f}/s")
                table.add_row("Uptime", f"{elapsed:.0f}s")
                console.print(table)

                if h['margin_ratio'] >= MARGIN_RATIO_DANGER:
                    await self.emergency_close_all()
            except Exception as e:
                console.print(f"[red]Monitor: {e}")
            await asyncio.sleep(MONITOR_INTERVAL)

    # ── main ──────────────────────────────────────────────

    async def run(self) -> None:
        self.session_start = time.time()
        try:
            # Load or discover symbols
            symbols = []
            if os.path.exists(SYMBOL_FILE):
                try:
                    with open(SYMBOL_FILE) as f:
                        symbols = [s for s in json.load(f) if isinstance(s, str) and s]
                except Exception:
                    pass

            if not symbols:
                symbols = await self.fetch_eligible_symbols()
                if symbols:
                    with open(SYMBOL_FILE, 'w') as f:
                        json.dump(symbols, f, indent=2)

            if not symbols:
                console.print("[red]No eligible symbols. Exiting.")
                return

            self.state = {s: 0.0 for s in symbols}

            if not self.exchange:
                await self.init_exchange()

            # Set leverage per symbol
            for sym in symbols:
                cfg = get_sym_cfg(sym)
                try:
                    mkt = self.exchange.market(sym)
                    max_lev = int(mkt.get('info', {}).get('leverage_max', cfg.leverage) or cfg.leverage)
                    use_lev = min(cfg.leverage, max_lev)
                    await self.exchange.set_leverage(
                        use_lev, sym, {'marginMode': MARGIN_MODE, 'type': 'swap'}
                    )
                except Exception:
                    try:
                        await self.exchange.set_leverage(
                            DEFAULT_LEVERAGE, sym, {'marginMode': MARGIN_MODE, 'type': 'swap'}
                        )
                    except Exception:
                        pass

            await self.recover_positions()

            h = await self.get_health()
            ok = sum(1 for hp in self.hedges.values() if hp.is_complete)
            broken = sum(1 for hp in self.hedges.values() if hp.is_broken)
            console.print(
                f"\n[bold cyan]HEDGE BEAST READY\n"
                f"  Mode: {MARGIN_MODE} margin, per-symbol leverage\n"
                f"  Symbols: {len(symbols)} | Free: ${h['free']:.4f}\n"
                f"  Hedges: {ok} complete, {broken} broken\n"
                f"  Features: DCA + target-price closes + auto-repair + LLM scoring\n"
            )

            monitor = asyncio.create_task(self.monitor_loop(symbols))
            while True:
                for sym in symbols:
                    try:
                        await self.execute_trade(sym)
                    except Exception as e:
                        console.print(f"[{sym}] Error: {e}")
                    await asyncio.sleep(LOOP_DELAY)
                await asyncio.sleep(3)

        except Exception as e:
            console.print(f"[red]Fatal: {e}")
            traceback.print_exc()
        finally:
            await self.cleanup()


# ══════════════════════════════════════════════════════════════
# ENTRY POINT
# ══════════════════════════════════════════════════════════════
if __name__ == '__main__':
    console.print("[bold cyan]HEDGE BEAST — Unified Multi-Symbol Hedging System[/bold cyan]")
    console.print("[dim]Combining godforbit + ena + melania + ENA_Project + gate_beast[/dim]\n")
    bot = HedgeBeast()
    asyncio.run(bot.run())
