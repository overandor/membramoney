import ccxt.async_support as ccxt
import asyncio
import aiohttp
import json
import os
import sys
import time
from dataclasses import dataclass, field, asdict
from dotenv import load_dotenv
from pathlib import Path
from rich.console import Console
from typing import List, Dict, Optional, Tuple

load_dotenv()  # reads .env file in current directory

# ── API Keys (env vars ONLY — no hardcoded secrets) ──────
API_KEY = os.getenv('GATE_API_KEY', '')
API_SECRET = os.getenv('GATE_API_SECRET', '')
GROQ_KEY = os.getenv('GROQ_API_KEY', '')

# ── LLM Self-Testing Loop Config ──
LLM_TEST_HORIZON_SEC   = int(os.getenv('LLM_TEST_HORIZON_SEC', '60'))
LLM_CRITIC_INTERVAL   = int(os.getenv('LLM_CRITIC_INTERVAL_SEC', '300'))
LLM_MIN_CONFIDENCE    = float(os.getenv('LLM_MIN_CONFIDENCE', '0.6'))
LLM_MAX_ERRORS_READ   = int(os.getenv('LLM_MAX_ERRORS_READ', '50'))
LLM_POLICY_MAX_ADJ    = float(os.getenv('LLM_POLICY_MAX_ADJ', '0.1'))

if not API_KEY or not API_SECRET:
    print('FATAL: Set GATE_API_KEY and GATE_API_SECRET environment variables.')
    print('See .env.example for the required format.')
    sys.exit(1)

# ── Files ─────────────────────────────────────────────────
SYMBOL_FILE = 'symbols.json'
STATE_FILE = 'state.json'
TRADE_LOG = 'trades.jsonl'

# ── Risk rules ────────────────────────────────────────────
MAX_NOTIONAL = 0.01 
LEVERAGE = 3                 # only trade symbols where 1 contract < $0.10          # isolated 2x — very conservative
MAX_EQUITY_PER_POS = 0.02    # max 2% of equity per position margin
MAX_TOTAL_EXPOSURE = 0.30    # max 30% of equity used across all positions
MARGIN_RATIO_DANGER = 0.80   # emergency close everything above 80%
BALANCE_RESERVE = 0.20       # always keep 20% of balance untouched
FEE_RATE = 0.00075           # Gate.io taker fee ~0.075%

# ── Behavior ──────────────────────────────────────────────
# NO routine stop-loss. Positions are held until profitable.
# Only emergency protection (margin danger) can close at a loss.
OFFSET = 0.002               # 0.2% limit order offset to cross spread
LOOP_DELAY = 2.0             # seconds between position checks
MONITOR_INTERVAL = 20        # seconds between dashboard prints

console = Console()


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

    @property
    def is_complete(self) -> bool:
        return self.long_leg.filled and self.short_leg.filled

    @property
    def is_empty(self) -> bool:
        return not self.long_leg.filled and not self.short_leg.filled

    @property
    def is_broken(self) -> bool:
        return self.long_leg.filled != self.short_leg.filled


HEDGE_STATE_FILE = 'hedge_state.json'
LLM_TRADE_MEMORY  = Path('llm_trade_memory.jsonl')
LLM_ERROR_MEMORY  = Path('llm_error_memory.jsonl')
LLM_POLICY_FILE   = Path('llm_policy.json')


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


class LLMSelfTester:
    """Continuous self-testing loop for LLM trading decisions."""

    def __init__(self, exchange=None):
        self.exchange = exchange
        self.pending: List[LLMDecisionTest] = []
        self.policy: dict = self._load_policy()

    # ── Memory helpers ──

    def _load_policy(self) -> dict:
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
        self._append_jsonl(LLM_TRADE_MEMORY, asdict(test))
        short_sym = symbol.split('/')[0]
        console.print(
            f'[magenta][LLM-TEST] Registered {action} {short_sym} '
            f'conf={confidence:.2f} pred={predicted_move:+.4%}'
        )
        return decision_id

    # ── Outcome evaluation loop ──

    async def outcome_test_loop(self) -> None:
        while True:
            try:
                now = time.time()
                still_pending = []
                for test in self.pending:
                    elapsed = now - test.timestamp
                    if elapsed < LLM_TEST_HORIZON_SEC:
                        still_pending.append(test)
                        continue
                    await self._evaluate_decision(test)
                self.pending = still_pending
            except Exception as e:
                console.print(f'[red][LLM-TEST] Outcome loop error: {e}')
            await asyncio.sleep(10)

    async def _evaluate_decision(self, test: LLMDecisionTest) -> None:
        try:
            if not self.exchange:
                return
            tk = await self.exchange.fetch_ticker(test.symbol, {'type': 'swap'})
            current_price = float(tk.get('last', 0) or 0)
            if current_price <= 0:
                return
            entry_price = test.features.get('mid_price', 0)
            if entry_price <= 0:
                entry_price = test.features.get('last_price', 0)
            if entry_price <= 0:
                return
            actual_move = (current_price - entry_price) / entry_price
            test.outcome_price = current_price
            test.actual_move = actual_move
            test.evaluated = True
            if test.action == 'enter_long':
                test.correct = actual_move > 0
            elif test.action == 'enter_short':
                test.correct = actual_move < 0
            elif test.action == 'skip':
                test.correct = abs(actual_move) < abs(test.predicted_move)
            elif test.action == 'exit':
                test.correct = True
            else:
                test.correct = None
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
            self._append_jsonl(LLM_TRADE_MEMORY, {
                'decision_id': test.decision_id,
                'evaluated': True,
                'actual_move': actual_move,
                'correct': test.correct,
                'outcome_price': current_price,
            })
        except Exception as e:
            console.print(f'[red][LLM-TEST] Evaluate error: {e}')

    # ── Critic loop ──

    async def critic_loop(self) -> None:
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
        error_summary = []
        for e in errors[-20:]:
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
                if text.startswith('```'):
                    text = text.split('\n', 1)[-1].rsplit('```', 1)[0].strip()
                new_policy = json.loads(text)
                for key in ('min_spread_pct', 'min_momentum', 'min_imbalance',
                            'min_edge_score', 'confidence_threshold'):
                    if key in new_policy:
                        old_val = self.policy.get(key, 0)
                        new_val = float(new_policy[key])
                        max_change = abs(old_val) * LLM_POLICY_MAX_ADJ if old_val != 0 else LLM_POLICY_MAX_ADJ
                        clamped = max(old_val - max_change, min(old_val + max_change, new_val))
                        clamped = max(0.0, min(1.0, clamped))
                        new_policy[key] = clamped
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
        if spread_pct < self.policy.get('min_spread_pct', 0.003):
            return False, f'spread {spread_pct:.4%} < policy min'
        if abs(momentum) < self.policy.get('min_momentum', 0.001):
            return False, f'momentum {momentum:.4%} < policy min'
        if abs(imbalance) < self.policy.get('min_imbalance', 0.20):
            return False, f'imbalance {imbalance:.2f} < policy min'
        if edge_score < self.policy.get('min_edge_score', 0.30):
            return False, f'edge_score {edge_score:.2f} < policy min'
        return True, 'policy_ok'

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


class ProfitOnlyBot:
    def __init__(self):
        self.exchange = None
        self.llm_tester = LLMSelfTester()
        self.state = {}           # symbol -> current unrealized PnL
        self.positions = {}       # symbol -> {side, entry, contracts, opened_at, sentiment}
        self.hedges: Dict[str, HedgePair] = {}  # symbol -> HedgePair

    # ── exchange ─────────────────────────────────────────────

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
        self.llm_tester.exchange = self.exchange

    async def cleanup(self) -> None:
        if self.exchange:
            try:
                await self.exchange.close()
            except Exception:
                pass

    # ── trade journal ────────────────────────────────────────

    def log_trade(self, action: str, symbol: str, side: str, contracts: float,
                  price: float = 0, pnl: float = 0, sentiment: str = '', note: str = ''):
        """Append structured trade record to trades.jsonl."""
        record = {
            'ts': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
            'epoch': time.time(),
            'action': action,      # OPEN, CLOSE, EMERGENCY, CONFIRM, SKIP
            'symbol': symbol,
            'side': side,
            'contracts': contracts,
            'price': price,
            'pnl': pnl,
            'sentiment': sentiment,
            'note': note,
        }
        try:
            with open(TRADE_LOG, 'a') as f:
                f.write(json.dumps(record) + '\n')
        except Exception:
            pass

    async def confirm_position(self, symbol: str, side: str, sentiment: str) -> bool:
        """After fill, verify position exists on exchange and record details."""
        try:
            positions = await self.exchange.fetch_positions([symbol], {'type': 'swap'})
            want = 'long' if side == 'buy' else 'short'
            for pos in positions:
                if pos['side'] == want and float(pos.get('contracts', 0) or 0) > 0:
                    ct = float(pos['contracts'])
                    entry = float(pos['entryPrice'])
                    margin = float(pos.get('initialMargin', 0) or 0)
                    console.print(
                        f"[bold cyan][{symbol}] CONFIRMED {want} {ct}ct @ {entry:.8f} "
                        f"(margin ${margin:.6f})"
                    )
                    self.positions[symbol] = {
                        'side': want,
                        'entry': entry,
                        'contracts': ct,
                        'opened_at': time.time(),
                        'sentiment': sentiment,
                    }
                    self.log_trade('CONFIRM', symbol, want, ct, entry, sentiment=sentiment,
                                   note=f'margin=${margin:.6f}')
                    return True
            console.print(f"[yellow][{symbol}] Fill claimed but no position found on exchange")
            return False
        except Exception as e:
            console.print(f"[red][{symbol}] Confirm error: {e}")
            return False

    async def recover_positions(self) -> None:
        """On startup, scan exchange positions and rebuild hedge pairs.
        1. Load persisted hedge state from disk
        2. Reconcile with actual exchange positions
        3. Register complete pairs, flag broken ones for repair
        """
        # Load any persisted hedge state
        self.load_hedge_state()
        if self.hedges:
            console.print(f"[cyan]Loaded {len(self.hedges)} persisted hedge pairs from disk")

        try:
            all_pos = await self.exchange.fetch_positions(None, {'type': 'swap'})
            # Group positions by symbol
            by_symbol: Dict[str, list] = {}
            for pos in all_pos:
                ct = float(pos.get('contracts', 0) or 0)
                if ct <= 0:
                    continue
                sym = pos['symbol']
                by_symbol.setdefault(sym, []).append(pos)

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

                    # Also populate legacy tracking
                    self.positions[sym] = {
                        'side': side, 'entry': entry, 'contracts': ct,
                        'opened_at': now, 'sentiment': 'recovered',
                    }
                    self.state[sym] = self.state.get(sym, 0) + upnl
                    recovered += 1

                self.hedges[sym] = hp
                status = "COMPLETE" if hp.is_complete else ("BROKEN" if hp.is_broken else "EMPTY")
                l_info = f"L:{hp.long_leg.contracts}ct@{hp.long_leg.entry:.8f}" if hp.long_leg.filled else "L:none"
                s_info = f"S:{hp.short_leg.contracts}ct@{hp.short_leg.entry:.8f}" if hp.short_leg.filled else "S:none"
                console.print(f"[cyan]  {sym} [{status}] {l_info} {s_info}")

            self.save_hedge_state()

            if recovered:
                complete = sum(1 for hp in self.hedges.values() if hp.is_complete)
                broken = sum(1 for hp in self.hedges.values() if hp.is_broken)
                console.print(
                    f"[bold cyan]Recovered {recovered} legs across {len(self.hedges)} symbols "
                    f"({complete} complete, {broken} broken)"
                )
                self.log_trade('RECOVER', 'ALL', '', 0,
                               note=f'{recovered} legs, {complete} complete hedges, {broken} broken')
        except Exception as e:
            console.print(f"[red]Recovery error: {e}")

    # ── balance & health ─────────────────────────────────────

    async def get_health(self) -> dict:
        """Account snapshot: equity, used, free, margin_ratio, safe flag."""
        h = {'equity': 0, 'used': 0, 'free': 0, 'margin_ratio': 0, 'safe': True}
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
            h.update({
                'equity': total, 'used': used, 'free': free,
                'margin_ratio': mr,
                'safe': mr < MARGIN_RATIO_DANGER and (used / total if total > 0 else 0) < MAX_TOTAL_EXPOSURE,
            })
        except Exception as e:
            console.print(f"[red]Health error: {e}")
            h['safe'] = False
        return h

    async def emergency_close_all(self) -> None:
        """Flatten everything — last resort before liquidation.
        Try aggressive limit first, then market order fallback."""
        console.print("[bold red]⚠ EMERGENCY FLATTEN — margin ratio critical")
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
                # Attempt 1: aggressive limit (0.5% through the book)
                try:
                    tk = await self.exchange.fetch_ticker(sym, {'type': 'swap'})
                    px = float(tk['last'])
                    lim = px * 0.995 if close_side == 'sell' else px * 1.005
                    await self.exchange.create_limit_order(
                        sym, close_side, ct, lim,
                        {'marginMode': 'isolated', 'reduceOnly': True, 'type': 'swap'}
                    )
                    console.print(f"[red]  Limit close {sym} {side} {ct}ct")
                    closed = True
                except Exception as e1:
                    console.print(f"[red]  Limit failed {sym}: {e1}")
                # Attempt 2: market order fallback
                if not closed:
                    try:
                        await self.exchange.create_market_order(
                            sym, close_side, ct,
                            {'marginMode': 'isolated', 'reduceOnly': True, 'type': 'swap'}
                        )
                        console.print(f"[red]  Market close {sym} {side} {ct}ct")
                    except Exception as e2:
                        console.print(f"[bold red]  FAILED TO CLOSE {sym}: {e2}")
                await asyncio.sleep(0.2)
        except Exception as e:
            console.print(f"[red]Emergency error: {e}")

        # Clear all hedge tracking — we're flat now
        self.hedges.clear()
        self.save_hedge_state()
        self.log_trade('EMERGENCY_FLATTEN', 'ALL', '', 0, note='margin ratio critical')

    # ── LLM sentiment (data-driven) ─────────────────────────

    async def _fetch_market_context(self, symbol: str) -> str:
        """Gather real price data for the LLM prompt."""
        try:
            tk = await self.exchange.fetch_ticker(symbol, {'type': 'swap'})
            ohlcv = await self.exchange.fetch_ohlcv(symbol, '5m', limit=6)  # last 30 min

            last = float(tk.get('last', 0))
            high24 = float(tk.get('high', 0) or 0)
            low24 = float(tk.get('low', 0) or 0)
            pct24 = float(tk.get('percentage', 0) or 0)
            vol24 = float(tk.get('quoteVolume', 0) or 0)

            # Recent 5m candle closes
            closes = [c[4] for c in ohlcv] if ohlcv else []
            candle_str = ', '.join(f'{c:.8f}' for c in closes[-6:])

            return (
                f"Symbol: {symbol}\n"
                f"Last price: {last:.8f}\n"
                f"24h high: {high24:.8f}, low: {low24:.8f}, change: {pct24:+.2f}%\n"
                f"24h volume (USDT): {vol24:.0f}\n"
                f"Recent 5m closes: [{candle_str}]"
            )
        except Exception:
            return f"Symbol: {symbol} (no data available)"

    async def llm_sentiment(self, symbol: str) -> str:
        """Legacy method — kept for compatibility. Returns 'neutral' always.
        Hedge mode does not use directional sentiment."""
        return 'neutral'

    async def llm_score_symbol(self, symbol: str) -> float:
        """Ask LLM to score symbol quality for hedging (0-10).
        Higher = more volatile/active = better for profit harvesting.
        LLM does NOT pick direction — hedge is always both sides."""
        if not GROQ_KEY:
            return 5.0  # default: treat all symbols equally
        try:
            context = await self._fetch_market_context(symbol)
            async with aiohttp.ClientSession() as sess:
                payload = {
                    "model": "llama-3.1-8b-instant",
                    "messages": [
                        {"role": "system", "content": (
                            "You are a crypto market analyst evaluating symbols for hedged trading. "
                            "Based on the data below, score this symbol from 0 to 10 for "
                            "short-term volatility and trading activity. "
                            "Higher score = more volatile = better for market-neutral profit harvesting. "
                            "Reply with ONLY a single number (0-10), nothing else."
                        )},
                        {"role": "user", "content": context}
                    ],
                    "max_tokens": 5,
                    "temperature": 0.1,
                }
                headers = {"Authorization": f"Bearer {GROQ_KEY}", "Content-Type": "application/json"}
                async with sess.post(
                    "https://api.groq.com/openai/v1/chat/completions",
                    json=payload, headers=headers, timeout=aiohttp.ClientTimeout(total=8)
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        raw = data['choices'][0]['message']['content'].strip()
                        score = float(raw)
                        return max(0.0, min(10.0, score))
        except Exception:
            pass
        return 5.0

    # ── symbol selection ─────────────────────────────────────

    async def fetch_eligible_symbols(self) -> List[str]:
        """Micro-priced USDT swap symbols where 1ct notional < MAX_NOTIONAL, budget-capped."""
        if not self.exchange:
            await self.init_exchange()

        h = await self.get_health()
        free = h['free']
        console.print(f"[cyan]Free balance: ${free:.4f}")
        if free <= 0:
            console.print("[red]No free margin.")
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
            if ntl <= MAX_NOTIONAL:
                margin_1 = ntl / LEVERAGE
                candidates.append((sym, ntl, margin_1))

        candidates.sort(key=lambda x: x[2])

        # Budget: hedge needs margin for BOTH legs, use (1-BALANCE_RESERVE)*free
        budget = free * (1 - BALANCE_RESERVE)
        selected, running = [], 0.0
        for sym, ntl, mrg in candidates:
            hedge_cost = mrg * 2  # long + short legs
            if running + hedge_cost <= budget:
                selected.append((sym, ntl, mrg))
                running += hedge_cost

        console.print(f"[bold green]{len(selected)} symbols (1ct < ${MAX_NOTIONAL}, hedge margin ${running:.4f})")
        for sym, ntl, mrg in selected:
            console.print(f"  [green]{sym:<30}[/green] ntl=${ntl:.6f} hedge_mrg=${mrg*2:.6f}")

        return [s for s, _, _ in selected]

    # ── order sizing ─────────────────────────────────────────

    async def safe_size(self, symbol: str) -> int:
        """Return 1 contract if affordable under all limits, else 0."""
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
            mrg = ntl / LEVERAGE
            min_ct = int(mkt.get('limits', {}).get('amount', {}).get('min') or 1)

            if mrg * min_ct > h['free'] * 0.90:
                return 0
            if mrg * min_ct > h['equity'] * MAX_EQUITY_PER_POS:
                return 0
            if ntl * min_ct > MAX_NOTIONAL:
                return 0

            console.print(f"[dim][{symbol}] {min_ct}ct ntl=${ntl*min_ct:.6f} mrg=${mrg*min_ct:.6f}[/dim]")
            return min_ct
        except Exception as e:
            console.print(f"[{symbol}] Size err: {e}")
            return 0

    # ── order execution ──────────────────────────────────────

    async def open_position(self, symbol: str, side: str) -> bool:
        """Place a limit order crossing the spread. Exponential backoff on retries."""
        ct = await self.safe_size(symbol)
        if ct <= 0:
            return False
        delay = 1
        for attempt in range(5):
            try:
                tk = await self.exchange.fetch_ticker(symbol, {'type': 'swap'})
                px = float(tk['last'])
                lim = px * (1 + OFFSET) if side == 'buy' else px * (1 - OFFSET)
                order = await self.exchange.create_limit_order(
                    symbol, side, ct, lim,
                    {'marginMode': 'isolated', 'type': 'swap'}
                )
                console.print(f"[cyan][{symbol}] {side.upper()} {ct}ct @ {lim:.8f} (attempt {attempt+1})")
                if await self._wait_fill(symbol, side, ct):
                    console.print(f"[bold green][{symbol}] {side.upper()} FILLED")
                    return True
                try:
                    await self.exchange.cancel_order(order['id'], symbol, {'type': 'swap'})
                except Exception:
                    pass
            except Exception as e:
                console.print(f"[{symbol}] {side} #{attempt+1}: {e}")
            await asyncio.sleep(delay)
            delay = min(delay * 2, 8)
        return False

    async def _wait_fill(self, symbol: str, side: str, target: float, timeout: int = 10) -> bool:
        t0 = time.time()
        want = 'long' if side == 'buy' else 'short'
        while time.time() - t0 < timeout:
            try:
                pos = await self.exchange.fetch_positions([symbol], {'type': 'swap'})
                filled = sum(float(p['contracts']) for p in pos if p['side'] == want)
                if filled >= target:
                    return True
            except Exception:
                pass
            await asyncio.sleep(1)
        return False

    async def close_position(self, symbol: str, side: str, contracts: float) -> bool:
        """Close at profit only — limit order crossing spread. Exp backoff."""
        await self.cancel_reduce_orders(symbol)
        close_side = 'sell' if side == 'long' else 'buy'
        delay = 1
        for attempt in range(5):
            try:
                tk = await self.exchange.fetch_ticker(symbol, {'type': 'swap'})
                px = float(tk['last'])
                lim = px * (1 + OFFSET) if close_side == 'buy' else px * (1 - OFFSET)
                await self.exchange.create_limit_order(
                    symbol, close_side, contracts, lim,
                    {'marginMode': 'isolated', 'reduceOnly': True, 'type': 'swap'}
                )
                return True
            except Exception as e:
                console.print(f"[{symbol}] close #{attempt+1}: {e}")
                await self.cancel_reduce_orders(symbol)
                await asyncio.sleep(delay)
                delay = min(delay * 2, 8)
        return False

    # ── ena-style helpers: cancel stale, target-price close, DCA ──

    async def cancel_reduce_orders(self, symbol: str) -> None:
        """Cancel any pending reduce-only orders on a symbol (from ena bots).
        Prevents stale close orders from blocking new ones."""
        try:
            open_orders = await self.exchange.fetch_open_orders(
                symbol, params={'marginMode': 'isolated', 'type': 'swap'}
            )
            for order in open_orders:
                reduce = order.get('reduceOnly', False)
                if not reduce:
                    info = order.get('info', {})
                    reduce = info.get('is_reduce_only', False) or info.get('reduce_only', False)
                if reduce:
                    await self.exchange.cancel_order(
                        order['id'], symbol, {'marginMode': 'isolated', 'type': 'swap'}
                    )
                    console.print(f"[dim][{symbol}] Cancelled stale reduce order {order['id']}[/dim]")
        except Exception:
            pass

    async def close_at_target(self, symbol: str, side: str, contracts: float,
                              target_price: float) -> bool:
        """Close position with a limit order at a CALCULATED target price (from ena bots).
        This ensures we only exit at a price that guarantees net profit after fees."""
        await self.cancel_reduce_orders(symbol)
        close_side = 'sell' if side == 'long' else 'buy'
        delay = 1
        for attempt in range(5):
            try:
                await self.exchange.create_limit_order(
                    symbol, close_side, contracts, target_price,
                    {'marginMode': 'isolated', 'reduceOnly': True, 'type': 'swap'}
                )
                console.print(
                    f"[green][{symbol}] Close {side} {contracts}ct @ target {target_price:.8f} "
                    f"(attempt {attempt+1})"
                )
                return True
            except Exception as e:
                console.print(f"[{symbol}] target close #{attempt+1}: {e}")
                await self.cancel_reduce_orders(symbol)
                await asyncio.sleep(delay)
                delay = min(delay * 2, 8)
        return False

    async def dca_opposite(self, symbol: str, closed_side: str) -> None:
        """When one leg closes profitably, DCA the opposite side (from ena bots).
        This accumulates size on the losing leg, averaging down its entry,
        so it becomes profitable sooner — creating a no-loss cycle."""
        DCA_SIZE = 1  # contracts to add on opposite side
        opp_side = 'sell' if closed_side == 'long' else 'buy'
        opp_label = 'SHORT' if closed_side == 'long' else 'LONG'
        console.print(f"[cyan][{symbol}] DCA +{DCA_SIZE}ct on {opp_label} (average down)")
        try:
            tk = await self.exchange.fetch_ticker(symbol, {'type': 'swap'})
            px = float(tk['last'])
            lim = px * (1 + OFFSET) if opp_side == 'buy' else px * (1 - OFFSET)
            await self.exchange.create_limit_order(
                symbol, opp_side, DCA_SIZE, lim,
                {'marginMode': 'isolated', 'type': 'swap'}
            )
            self.log_trade('DCA', symbol, opp_side, DCA_SIZE, price=lim,
                           note=f'opposite DCA after {closed_side} harvest')
        except Exception as e:
            console.print(f"[yellow][{symbol}] DCA failed: {e}")

    # ── hedge state persistence ──────────────────────────────

    def save_hedge_state(self) -> None:
        """Persist hedge pair tracking to disk for restart recovery."""
        try:
            data = {}
            for sym, hp in self.hedges.items():
                data[sym] = asdict(hp)
            with open(HEDGE_STATE_FILE, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception:
            pass

    def load_hedge_state(self) -> None:
        """Load persisted hedge state from disk."""
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
                )
        except Exception:
            pass

    # ── hedge execution layer ──────────────────────────────

    async def flatten_symbol(self, symbol: str, reason: str = '') -> None:
        """Close both legs of a symbol — return to flat."""
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
                        {'marginMode': 'isolated', 'reduceOnly': True, 'type': 'swap'}
                    )
                    console.print(f"[red][{symbol}] Flatten {side} {ct}ct ({reason})")
                except Exception as e:
                    # Fallback to market
                    try:
                        await self.exchange.create_market_order(
                            symbol, close_side, ct,
                            {'marginMode': 'isolated', 'reduceOnly': True, 'type': 'swap'}
                        )
                        console.print(f"[red][{symbol}] Market flatten {side} {ct}ct ({reason})")
                    except Exception as e2:
                        console.print(f"[bold red][{symbol}] FLATTEN FAILED {side}: {e2}")
                await asyncio.sleep(0.3)
        except Exception as e:
            console.print(f"[red][{symbol}] Flatten error: {e}")

        self.hedges.pop(symbol, None)
        self.positions.pop(symbol, None)
        self.state[symbol] = 0.0
        self.log_trade('EMERGENCY_FLATTEN', symbol, '', 0, note=reason)
        self.save_hedge_state()

    async def hedge_open_pair(self, symbol: str) -> bool:
        """Open both long and short legs atomically. If one fails, close the other."""
        h = await self.get_health()
        if not h['safe']:
            return False

        # Need margin for TWO positions
        ct = await self.safe_size(symbol)
        if ct <= 0:
            return False

        # Check we can afford two legs
        mkt = self.exchange.market(symbol)
        cs = float(mkt.get('contractSize', 1) or 1)
        tk = await self.exchange.fetch_ticker(symbol, {'type': 'swap'})
        px = float(tk['last'])
        margin_both = (px * cs * ct / LEVERAGE) * 2
        if margin_both > h['free'] * 0.90:
            console.print(f"[yellow][{symbol}] Can't afford hedge pair (need ${margin_both:.6f})")
            return False

        # Open LONG
        console.print(f"[cyan][{symbol}] Opening hedge: LONG leg...")
        long_ok = await self.open_position(symbol, 'buy')
        if not long_ok:
            console.print(f"[yellow][{symbol}] Long leg failed — no hedge opened")
            self.log_trade('HEDGE_BROKEN', symbol, 'long', 0, note='long leg failed to open')
            return False

        await asyncio.sleep(0.5)

        # Open SHORT
        console.print(f"[cyan][{symbol}] Opening hedge: SHORT leg...")
        short_ok = await self.open_position(symbol, 'sell')
        if not short_ok:
            # Rollback: close the long we just opened
            console.print(f"[yellow][{symbol}] Short leg failed — rolling back long")
            await self.flatten_symbol(symbol, reason='hedge rollback: short failed')
            self.log_trade('HEDGE_BROKEN', symbol, 'short', 0, note='short leg failed, rolled back long')
            return False

        # Both filled — build HedgePair from exchange state
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
                self.log_trade('HEDGE_OPEN', symbol, 'both', ct,
                               price=px, note=f'L@{hp.long_leg.entry:.8f} S@{hp.short_leg.entry:.8f}')
                return True
            else:
                console.print(f"[yellow][{symbol}] Hedge incomplete after both fills — flattening")
                await self.flatten_symbol(symbol, reason='hedge incomplete after fills')
                return False
        except Exception as e:
            console.print(f"[red][{symbol}] Hedge confirm error: {e}")
            await self.flatten_symbol(symbol, reason=f'confirm error: {e}')
            return False

    async def hedge_harvest(self, symbol: str) -> None:
        """Ena-style profit harvesting: per-contract threshold, target-price close,
        DCA opposite side, reopen same side. ONLY closes in profit — zero loss."""
        hp = self.hedges.get(symbol)
        if not hp or not hp.is_complete:
            return

        # Per-contract profit/fee thresholds (from ena bots)
        BASE_PROFIT_PER_CT = 0.01    # $0.01 net profit target per contract
        FEE_COST_PER_CT    = 0.002   # $0.002 fee estimate per contract

        try:
            positions = await self.exchange.fetch_positions([symbol], {'type': 'swap'})

            for pos in positions:
                ct = float(pos.get('contracts', 0) or 0)
                if ct <= 0:
                    continue
                side = pos['side']  # 'long' or 'short'
                upnl = float(pos.get('unrealizedPnl', 0) or 0)
                entry = float(pos.get('entryPrice', 0) or 0)

                # Effective threshold scales with contracts (from ena check_profit_and_close)
                effective_threshold = (BASE_PROFIT_PER_CT + FEE_COST_PER_CT) * ct

                if upnl >= effective_threshold:
                    # ── Calculate TARGET EXIT PRICE (from ena bots — guarantees profit) ──
                    per_ct_target = effective_threshold / ct
                    if side == 'long':
                        target_price = entry + per_ct_target
                    else:
                        target_price = entry - per_ct_target

                    console.print(
                        f"[bold green][{symbol}] {side} PROFIT ${upnl:.6f} >= ${effective_threshold:.6f} "
                        f"— harvesting @ {target_price:.8f}"
                    )

                    # Close at calculated target price (not market — ensures profit)
                    closed = await self.close_at_target(symbol, side, ct, target_price)
                    if not closed:
                        # Fallback: spread-crossing close (still profit-only since uPnL > threshold)
                        closed = await self.close_position(symbol, side, ct)

                    if closed:
                        self.log_trade('LEG_CLOSE_PROFIT', symbol, side, ct, entry,
                                       pnl=upnl, note=f'target={target_price:.8f} thresh=${effective_threshold:.6f}')
                        if side == 'long':
                            hp.long_leg.filled = False
                        else:
                            hp.short_leg.filled = False
                        self.save_hedge_state()

                        await asyncio.sleep(1)

                        # ── DCA opposite side (from ena bots — average down the losing leg) ──
                        await self.dca_opposite(symbol, side)
                        await asyncio.sleep(0.5)

                        # ── REOPEN same side (fresh entry at current price) ──
                        reopen_side = 'buy' if side == 'long' else 'sell'
                        console.print(f"[cyan][{symbol}] Reopening {side} leg...")
                        reopened = await self.open_position(symbol, reopen_side)
                        if reopened:
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
                            console.print(f"[bold green][{symbol}] {side} REOPENED — profit cycle complete")
                            self.log_trade('LEG_REOPEN', symbol, side, ct, note='profit cycle + DCA')
                        else:
                            console.print(f"[yellow][{symbol}] Failed to reopen {side} — hedge now broken")
                            self.log_trade('HEDGE_BROKEN', symbol, side, 0, note='reopen failed after harvest')
                    # Only harvest one leg per cycle to avoid race conditions
                    return

            # Update combined PnL in state
            total_upnl = sum(
                float(p.get('unrealizedPnl', 0) or 0)
                for p in positions if float(p.get('contracts', 0) or 0) > 0
            )
            self.state[symbol] = total_upnl

        except Exception as e:
            console.print(f"[red][{symbol}] Harvest error: {e}")

    async def hedge_repair(self, symbol: str) -> None:
        """Detect and fix broken hedges — one leg missing or partial fill."""
        hp = self.hedges.get(symbol)
        if not hp:
            return

        try:
            positions = await self.exchange.fetch_positions([symbol], {'type': 'swap'})
            has_long = False
            has_short = False
            for pos in positions:
                ct = float(pos.get('contracts', 0) or 0)
                if ct <= 0:
                    continue
                if pos['side'] == 'long':
                    has_long = True
                elif pos['side'] == 'short':
                    has_short = True

            # Sync hedge state with reality
            hp.long_leg.filled = has_long
            hp.short_leg.filled = has_short

            if hp.is_complete:
                return  # All good

            if hp.is_empty:
                # Both legs gone — clean up
                console.print(f"[yellow][{symbol}] Both legs gone — removing hedge")
                self.hedges.pop(symbol, None)
                self.save_hedge_state()
                return

            # One leg missing — try to repair
            missing = 'long' if not has_long else 'short'
            console.print(f"[yellow][{symbol}] Broken hedge — {missing} leg missing, attempting repair")
            self.log_trade('HEDGE_REPAIR', symbol, missing, 0, note='attempting reopen')

            h = await self.get_health()
            if not h['safe']:
                console.print(f"[red][{symbol}] Unsafe to repair — flattening")
                await self.flatten_symbol(symbol, reason='unsafe to repair broken hedge')
                return

            reopen_side = 'buy' if missing == 'long' else 'sell'
            repaired = await self.open_position(symbol, reopen_side)
            if repaired:
                new_pos = await self.exchange.fetch_positions([symbol], {'type': 'swap'})
                for np in new_pos:
                    nct = float(np.get('contracts', 0) or 0)
                    if nct > 0 and np['side'] == missing:
                        leg = HedgeLeg(contracts=nct, entry=float(np.get('entryPrice', 0) or 0),
                                       timestamp=time.time(), filled=True)
                        if missing == 'long':
                            hp.long_leg = leg
                        else:
                            hp.short_leg = leg
                        break
                self.save_hedge_state()
                console.print(f"[bold green][{symbol}] Hedge REPAIRED — {missing} leg reopened")
                self.log_trade('HEDGE_REPAIR', symbol, missing, 1, note='repair success')
            else:
                console.print(f"[red][{symbol}] Repair failed — flattening to safety")
                await self.flatten_symbol(symbol, reason=f'repair failed for {missing} leg')

        except Exception as e:
            console.print(f"[red][{symbol}] Repair error: {e}")

    async def _register_hedge_from_exchange(self, symbol: str) -> None:
        """Read current positions on symbol and register as a HedgePair."""
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
                console.print(
                    f"[bold green][{symbol}] Hedge registered — "
                    f"L:{new_hp.long_leg.contracts}ct S:{new_hp.short_leg.contracts}ct"
                )
                self.log_trade('HEDGE_OPEN', symbol, 'both', 0, note='registered from exchange')
            else:
                console.print(f"[yellow][{symbol}] Registration incomplete — flattening")
                await self.flatten_symbol(symbol, reason='registration incomplete')
        except Exception as e:
            console.print(f"[red][{symbol}] Register error: {e}")

    # ── trade logic: HEDGED MARKET-NEUTRAL PROFIT ENGINE ───

    async def execute_trade(self, symbol: str) -> None:
        """Hedged execution: maintain long+short pair, harvest profitable legs."""
        try:
            # Health gate — preserves all existing safety logic
            h = await self.get_health()
            if not h['safe']:
                console.print(f"[red][{symbol}] Skip — unsafe (margin {h['margin_ratio']:.1%})")
                if h['margin_ratio'] >= MARGIN_RATIO_DANGER:
                    await self.emergency_close_all()
                return

            hp = self.hedges.get(symbol)

            if hp:
                # ── EXISTING HEDGE — repair if broken, harvest if complete ──
                if hp.is_broken:
                    await self.hedge_repair(symbol)
                elif hp.is_complete:
                    await self.hedge_harvest(symbol)
                elif hp.is_empty:
                    # Both legs gone — clean up stale entry
                    self.hedges.pop(symbol, None)
                    self.save_hedge_state()
            else:
                # ── NO HEDGE — open a new pair ──
                # LLM Self-Testing: policy gate before opening new hedge
                try:
                    tk = await self.exchange.fetch_ticker(symbol, {'type': 'swap'})
                    last_px = float(tk.get('last', 0) or 0)
                    book = await self.exchange.fetch_order_book(symbol, 5)
                    bid = book['bids'][0][0] if book.get('bids') else 0
                    ask = book['asks'][0][0] if book.get('asks') else 0
                    mid = (bid + ask) / 2 if bid > 0 and ask > 0 else last_px
                    spread_pct = (ask - bid) / mid if mid > 0 else 0
                    bid_vol = sum(b[1] for b in book.get('bids', [])[:5])
                    ask_vol = sum(a[1] for a in book.get('asks', [])[:5])
                    total_vol = bid_vol + ask_vol
                    imbalance = (bid_vol - ask_vol) / total_vol if total_vol > 0 else 0
                    # Simple momentum from ticker
                    momentum = 0.0
                    try:
                        change_24h = float(tk.get('change', 0) or 0)
                        momentum = change_24h
                    except Exception:
                        pass
                    edge_score = abs(imbalance) * 0.5 + abs(momentum) * 0.5
                    policy_ok, policy_reason = self.llm_tester.policy_gate(
                        spread_pct, momentum, imbalance, edge_score)
                    if not policy_ok:
                        console.print(f'[dim][{symbol}] POLICY VETO: {policy_reason}')
                        self.llm_tester.register_decision(
                            symbol, 'skip',
                            features={'spread_pct': spread_pct, 'momentum': momentum,
                                      'imbalance': imbalance, 'edge_score': edge_score,
                                      'mid_price': mid, 'last_price': last_px},
                            confidence=edge_score,
                            rationale=policy_reason,
                            predicted_move=momentum,
                        )
                        return
                    # Register hedge-open decision for self-testing
                    self.llm_tester.register_decision(
                        symbol, 'enter_long',
                        features={'spread_pct': spread_pct, 'momentum': momentum,
                                  'imbalance': imbalance, 'edge_score': edge_score,
                                  'mid_price': mid, 'last_price': last_px},
                        confidence=edge_score,
                        rationale=f'hedge_open edge={edge_score:.2f}',
                        predicted_move=momentum,
                    )
                except Exception as e:
                    console.print(f'[yellow][{symbol}] LLM policy check error: {e}')

                # Check for orphaned one-sided positions from before upgrade
                positions = await self.exchange.fetch_positions([symbol], {'type': 'swap'})
                active = [p for p in positions if float(p.get('contracts', 0) or 0) > 0]
                if active:
                    # Orphaned position from old one-sided logic — fold into hedge
                    console.print(f"[yellow][{symbol}] Found orphaned position — converting to hedge")
                    has_long = any(p['side'] == 'long' for p in active if float(p.get('contracts', 0) or 0) > 0)
                    has_short = any(p['side'] == 'short' for p in active if float(p.get('contracts', 0) or 0) > 0)

                    if has_long and has_short:
                        # Already a pair — just register it
                        now = time.time()
                        new_hp = HedgePair(hedge_open_time=now)
                        for pos in active:
                            ct = float(pos.get('contracts', 0) or 0)
                            if ct <= 0:
                                continue
                            entry = float(pos.get('entryPrice', 0) or 0)
                            leg = HedgeLeg(contracts=ct, entry=entry, timestamp=now, filled=True)
                            if pos['side'] == 'long':
                                new_hp.long_leg = leg
                            else:
                                new_hp.short_leg = leg
                        self.hedges[symbol] = new_hp
                        self.save_hedge_state()
                        console.print(f"[cyan][{symbol}] Registered existing pair as hedge")
                        self.log_trade('HEDGE_OPEN', symbol, 'both', 0, note='registered orphan pair')
                    elif has_long and not has_short:
                        # Need to add short leg
                        console.print(f"[cyan][{symbol}] Adding short leg to orphaned long...")
                        short_ok = await self.open_position(symbol, 'sell')
                        if short_ok:
                            await self._register_hedge_from_exchange(symbol)
                        else:
                            console.print(f"[yellow][{symbol}] Could not complete hedge — flattening orphan")
                            await self.flatten_symbol(symbol, reason='could not complete orphan hedge')
                    elif has_short and not has_long:
                        # Need to add long leg
                        console.print(f"[cyan][{symbol}] Adding long leg to orphaned short...")
                        long_ok = await self.open_position(symbol, 'buy')
                        if long_ok:
                            await self._register_hedge_from_exchange(symbol)
                        else:
                            console.print(f"[yellow][{symbol}] Could not complete hedge — flattening orphan")
                            await self.flatten_symbol(symbol, reason='could not complete orphan hedge')
                    return

                # Fresh entry — open both legs
                opened = await self.hedge_open_pair(symbol)
                if not opened:
                    self.log_trade('SKIP', symbol, '', 0, note='hedge pair open failed or unaffordable')

        except Exception as e:
            console.print(f"[{symbol}] Error: {e}")

    # ── monitor ──────────────────────────────────────────────

    async def monitor_loop(self, symbols: List[str]) -> None:
        t0 = time.time()
        while True:
            try:
                total_pnl = sum(self.state.values())
                elapsed = max(time.time() - t0, 1)
                h = await self.get_health()
                status = "[green]SAFE" if h['safe'] else "[red]DANGER"
                complete_hedges = sum(1 for hp in self.hedges.values() if hp.is_complete)
                broken_hedges = sum(1 for hp in self.hedges.values() if hp.is_broken)
                console.print(
                    f"[bold]{status}[/bold] | "
                    f"Eq: ${h['equity']:.4f} | "
                    f"Used: ${h['used']:.4f} | "
                    f"Free: ${h['free']:.4f} | "
                    f"MR: {h['margin_ratio']:.1%} | "
                    f"uPnL: ${total_pnl:.6f} | "
                    f"Rate: ${total_pnl/elapsed:.6f}/s | "
                    f"Hedges: {complete_hedges}ok/{broken_hedges}broken | "
                    f"Sym: {len(symbols)}"
                )
                if h['margin_ratio'] >= MARGIN_RATIO_DANGER:
                    await self.emergency_close_all()
                # LLM Self-Testing info
                llm_s = self.llm_tester.get_summary()
                if llm_s['total_decisions'] > 0:
                    console.print(
                        f"  [magenta]LLM-TEST: {llm_s['total_decisions']} decisions, "
                        f"{llm_s['accuracy']:.0%} accuracy ({llm_s['correct']}/{llm_s['evaluated']}), "
                        f"{llm_s['total_errors']} errors, "
                        f"{llm_s['pending_evaluations']} pending"
                    )
            except Exception as e:
                console.print(f"[red]Monitor: {e}")
            await asyncio.sleep(MONITOR_INTERVAL)

    # ── main ─────────────────────────────────────────────────

    async def run(self) -> None:
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

            # Set leverage per symbol — isolated, 2x (or symbol max if lower)
            for sym in symbols:
                try:
                    mkt = self.exchange.market(sym)
                    max_lev = int(mkt.get('info', {}).get('leverage_max', LEVERAGE) or LEVERAGE)
                    use_lev = min(LEVERAGE, max_lev)
                    await self.exchange.set_leverage(use_lev, sym, {'marginMode': 'isolated', 'type': 'swap'})
                except Exception:
                    try:
                        await self.exchange.set_leverage(2, sym, {'marginMode': 'isolated', 'type': 'swap'})
                    except Exception:
                        pass

            # Recover any existing positions from a previous run
            await self.recover_positions()

            h = await self.get_health()
            complete_h = sum(1 for hp in self.hedges.values() if hp.is_complete)
            broken_h = sum(1 for hp in self.hedges.values() if hp.is_broken)
            console.print(
                f"[bold cyan]Ready — HEDGED MODE, isolated {LEVERAGE}x, "
                f"${MAX_NOTIONAL} max notional, "
                f"${h['free']:.4f} free, "
                f"{len(symbols)} symbols, "
                f"{complete_h} complete hedges, {broken_h} broken, "
                f"market-neutral profit harvesting"
            )

            monitor = asyncio.create_task(self.monitor_loop(symbols))
            llm_outcome = asyncio.create_task(self.llm_tester.outcome_test_loop())
            llm_critic = asyncio.create_task(self.llm_tester.critic_loop())
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
        finally:
            await self.cleanup()


if __name__ == '__main__':
    bot = ProfitOnlyBot()
    asyncio.run(bot.run())
