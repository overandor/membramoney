#!/usr/bin/env python3
from __future__ import annotations

"""
gate_micro_profit_only_dca.py

Profit-only micro futures bot with DCA averaging.

Behavior:
- micro-priced USDT swaps only
- paper mode by default
- minimum-size initial entries
- adds minimum-size DCA legs only when position is in loss by configured thresholds
- normal logic closes only when estimated NET profit after fees is positive
- no routine stop-loss exits

Warning:
- No strategy can truthfully guarantee zero realized losses in all real-world conditions.
- DCA can reduce average entry, but it can also increase time-in-trade and capital usage.
"""

import asyncio
import contextlib
import json
import os
import signal
import time
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional

import ccxt.async_support as ccxt
from rich.console import Console
from rich.table import Table

console = Console()

STATE_FILE = Path(os.getenv("STATE_FILE", "profit_only_dca_state.json"))
SYMBOL_FILE = Path(os.getenv("SYMBOL_FILE", "profit_only_dca_symbols.json"))


@dataclass
class BotConfig:
    gate_api_key: str = os.getenv("GATE_API_KEY", "")
    gate_api_secret: str = os.getenv("GATE_API_SECRET", "")
    paper_mode: bool = os.getenv("PAPER_MODE", "true").lower() == "true"

    margin_mode: str = os.getenv("MARGIN_MODE", "isolated")
    leverage: int = int(os.getenv("LEVERAGE", "2"))

    micro_max_price: float = float(os.getenv("MICRO_MAX_PRICE", "0.10"))
    micro_min_price: float = float(os.getenv("MICRO_MIN_PRICE", "0.000001"))
    max_symbols: int = int(os.getenv("MAX_SYMBOLS", "2"))

    min_free_usdt: float = float(os.getenv("MIN_FREE_USDT", "25"))
    reserve_pct: float = float(os.getenv("RESERVE_PCT", "0.50"))
    per_trade_margin_pct: float = float(os.getenv("PER_TRADE_MARGIN_PCT", "0.01"))
    max_total_margin_pct: float = float(os.getenv("MAX_TOTAL_MARGIN_PCT", "0.08"))
    min_liq_buffer_pct: float = float(os.getenv("MIN_LIQ_BUFFER_PCT", "0.35"))

    entry_cooldown_sec: int = int(os.getenv("ENTRY_COOLDOWN_SEC", "180"))
    dca_cooldown_sec: int = int(os.getenv("DCA_COOLDOWN_SEC", "180"))
    loop_delay_sec: float = float(os.getenv("LOOP_DELAY_SEC", "3"))
    scan_interval_sec: int = int(os.getenv("SCAN_INTERVAL_SEC", "180"))
    report_interval_sec: int = int(os.getenv("REPORT_INTERVAL_SEC", "20"))

    signal_timeframe: str = os.getenv("SIGNAL_TIMEFRAME", "1m")
    signal_lookback: int = int(os.getenv("SIGNAL_LOOKBACK", "30"))
    fast_ma: int = int(os.getenv("FAST_MA", "5"))
    slow_ma: int = int(os.getenv("SLOW_MA", "20"))
    momentum_threshold_bps: float = float(os.getenv("MOMENTUM_THRESHOLD_BPS", "8"))

    fee_rate_per_side: float = float(os.getenv("FEE_RATE_PER_SIDE", "0.0005"))
    min_profit_buffer_usdt: float = float(os.getenv("MIN_PROFIT_BUFFER_USDT", "0.0005"))
    limit_offset_bps: float = float(os.getenv("LIMIT_OFFSET_BPS", "2"))

    max_dca_legs: int = int(os.getenv("MAX_DCA_LEGS", "3"))
    dca_trigger_pct: float = float(os.getenv("DCA_TRIGGER_PCT", "0.006"))
    dca_step_multiplier: float = float(os.getenv("DCA_STEP_MULTIPLIER", "1.0"))

    emergency_flatten: bool = os.getenv("EMERGENCY_FLATTEN", "false").lower() == "true"


@dataclass
class PositionState:
    symbol: str
    side: str
    contracts: float
    entry_price: float
    opened_ts: float
    dca_count: int = 0
    last_dca_ts: float = 0.0
    paper: bool = True


class ProfitOnlyDCABot:
    def __init__(self, cfg: BotConfig):
        self.cfg = cfg
        self.exchange = None
        self.running = True
        self.selected_symbols: List[str] = []
        self.last_entry_ts: Dict[str, float] = {}
        self.paper_positions: Dict[str, PositionState] = {}
        self.realized_pnl: Dict[str, float] = {}
        self.last_scan_ts = 0.0
        self.last_report_ts = 0.0

    async def initialize(self) -> None:
        if self.exchange is not None:
            return
        self.exchange = ccxt.gateio({
            "apiKey": self.cfg.gate_api_key,
            "secret": self.cfg.gate_api_secret,
            "enableRateLimit": True,
            "options": {
                "defaultType": "swap",
                "defaultSettle": "usdt",
                "adjustForTimeDifference": True,
                "recvWindow": 60000,
            },
        })
        await self.exchange.load_markets()
        self._load_state()
        self._install_signal_handlers()

    async def cleanup(self) -> None:
        if self.exchange is not None:
            with contextlib.suppress(Exception):
                await self.exchange.close()
        self._save_state()

    def _install_signal_handlers(self) -> None:
        def _stop(*_: Any) -> None:
            self.running = False
        with contextlib.suppress(NotImplementedError):
            signal.signal(signal.SIGINT, _stop)
            signal.signal(signal.SIGTERM, _stop)

    def _save_state(self) -> None:
        payload = {
            "selected_symbols": self.selected_symbols,
            "last_entry_ts": self.last_entry_ts,
            "paper_positions": {k: asdict(v) for k, v in self.paper_positions.items()},
            "realized_pnl": self.realized_pnl,
        }
        STATE_FILE.write_text(json.dumps(payload, indent=2))

    def _load_state(self) -> None:
        if not STATE_FILE.exists():
            return
        try:
            payload = json.loads(STATE_FILE.read_text())
            self.selected_symbols = list(payload.get("selected_symbols", []))
            self.last_entry_ts = dict(payload.get("last_entry_ts", {}))
            self.realized_pnl = dict(payload.get("realized_pnl", {}))
            self.paper_positions = {
                sym: PositionState(**data)
                for sym, data in payload.get("paper_positions", {}).items()
            }
        except Exception as exc:
            console.print(f"[yellow]State load failed: {exc}[/yellow]")

    async def get_balance_snapshot(self) -> dict:
        if self.cfg.paper_mode:
            equity = float(os.getenv("PAPER_USDT_BALANCE", "1000"))
            used = 0.0
            return {"equity": equity, "used": used, "free": equity, "safe": equity >= self.cfg.min_free_usdt, "margin_ratio": 0.0}

        try:
            bal = await self.exchange.fetch_balance()
            total = float(bal.get("total", {}).get("USDT", 0) or 0)
            used = float(bal.get("used", {}).get("USDT", 0) or 0)
            free = float(bal.get("free", {}).get("USDT", 0) or 0)
            if free <= 0:
                free = max(total - used, 0)
            return {"equity": total, "used": used, "free": free, "safe": free >= self.cfg.min_free_usdt, "margin_ratio": (used / total if total > 0 else 0.0)}
        except Exception as exc:
            console.print(f"[red]Balance snapshot failed: {exc}[/red]")
            return {"equity": 0.0, "used": 0.0, "free": 0.0, "safe": False, "margin_ratio": 1.0}

    async def fetch_eligible_symbols(self) -> List[str]:
        snap = await self.get_balance_snapshot()
        if not snap["safe"]:
            return []

        eligible: List[tuple[str, float]] = []
        for market in self.exchange.markets.values():
            symbol = market.get("symbol")
            if not symbol or not market.get("active", True) or not market.get("swap", False):
                continue
            quote = market.get("quote")
            settle = market.get("settle")
            if quote != "USDT" and settle != "USDT":
                continue
            try:
                ticker = await self.exchange.fetch_ticker(symbol, {"type": "swap"})
                last = float(ticker.get("last") or 0)
                if not (self.cfg.micro_min_price <= last <= self.cfg.micro_max_price):
                    continue
                qv = float(ticker.get("quoteVolume") or 0)
                eligible.append((symbol, qv))
            except Exception:
                continue

        eligible.sort(key=lambda x: x[1], reverse=True)
        chosen = [s for s, _ in eligible[: self.cfg.max_symbols]]
        SYMBOL_FILE.write_text(json.dumps(chosen, indent=2))
        return chosen

    async def refresh_universe_if_needed(self) -> None:
        now = time.time()
        if self.selected_symbols and now - self.last_scan_ts < self.cfg.scan_interval_sec:
            return
        self.selected_symbols = await self.fetch_eligible_symbols()
        self.last_scan_ts = now
        if self.selected_symbols:
            console.print(f"[cyan]Selected symbols: {self.selected_symbols}[/cyan]")

    async def fetch_mark_price(self, symbol: str) -> float:
        ticker = await self.exchange.fetch_ticker(symbol, {"type": "swap"})
        return float(ticker.get("mark") or ticker.get("last") or 0)

    async def fetch_signal(self, symbol: str) -> Optional[str]:
        try:
            ohlcv = await self.exchange.fetch_ohlcv(symbol, timeframe=self.cfg.signal_timeframe, limit=self.cfg.signal_lookback, params={"type": "swap"})
            closes = [float(row[4]) for row in ohlcv if row and row[4] is not None]
            if len(closes) < max(self.cfg.fast_ma, self.cfg.slow_ma):
                return None

            fast = sum(closes[-self.cfg.fast_ma:]) / self.cfg.fast_ma
            slow = sum(closes[-self.cfg.slow_ma:]) / self.cfg.slow_ma
            drift_bps = ((fast / slow) - 1.0) * 10000 if slow > 0 else 0.0

            if drift_bps >= self.cfg.momentum_threshold_bps:
                return "buy"
            if drift_bps <= -self.cfg.momentum_threshold_bps:
                return "sell"
            return None
        except Exception:
            return None

    async def current_position(self, symbol: str) -> Optional[PositionState]:
        if self.cfg.paper_mode:
            return self.paper_positions.get(symbol)

        try:
            positions = await self.exchange.fetch_positions([symbol], {"type": "swap"})
            for p in positions:
                contracts = float(p.get("contracts", 0) or 0)
                if contracts <= 0:
                    continue
                side = "buy" if p.get("side") == "long" else "sell"
                entry = float(p.get("entryPrice") or p.get("entry_price") or 0)
                return PositionState(
                    symbol=symbol,
                    side=side,
                    contracts=contracts,
                    entry_price=entry,
                    opened_ts=time.time(),
                    paper=False,
                )
        except Exception:
            return None
        return None

    async def liquidation_buffer_ok(self, symbol: str) -> bool:
        if self.cfg.paper_mode:
            return True
        try:
            positions = await self.exchange.fetch_positions([symbol], {"type": "swap"})
            for p in positions:
                contracts = float(p.get("contracts", 0) or 0)
                if contracts <= 0:
                    continue
                liq = p.get("liquidationPrice")
                mark = p.get("markPrice") or p.get("info", {}).get("mark_price")
                side = p.get("side")
                if liq is None or mark is None:
                    continue
                liq = float(liq)
                mark = float(mark)
                if liq <= 0 or mark <= 0:
                    continue

                buffer_pct = (mark - liq) / mark if side == "long" else (liq - mark) / mark
                if buffer_pct < self.cfg.min_liq_buffer_pct:
                    return False
            return True
        except Exception:
            return True

    async def estimate_min_contracts(self, symbol: str, dca_leg_index: int = 0):
        snap = await self.get_balance_snapshot()
        if not snap["safe"]:
            return 0

        market = self.exchange.market(symbol)
        last = await self.fetch_mark_price(symbol)
        if last <= 0:
            return 0

        contract_size = float(market.get("contractSize") or 1)
        contract_notional = last * contract_size
        contract_margin = contract_notional / max(self.cfg.leverage, 1)
        if contract_margin <= 0:
            return 0

        equity = snap["equity"] if snap["equity"] > 0 else snap["free"]
        max_margin_this_trade = equity * self.cfg.per_trade_margin_pct * (self.cfg.dca_step_multiplier ** dca_leg_index)
        max_total_used = equity * self.cfg.max_total_margin_pct

        if contract_margin > max_margin_this_trade:
            return 0
        if snap["used"] + contract_margin > max_total_used:
            return 0
        if contract_margin > snap["free"] * 0.90:
            return 0

        min_amount = float(market.get("limits", {}).get("amount", {}).get("min") or 1)
        precision = int(market.get("precision", {}).get("amount", 0) or 0)
        return int(min_amount) if precision == 0 else float(min_amount)

    def _gross_pnl(self, pos: PositionState, price: float) -> float:
        if pos.side == "buy":
            return (price - pos.entry_price) * pos.contracts
        return (pos.entry_price - price) * pos.contracts

    def _net_pnl_if_closed_now(self, pos: PositionState, exit_price: float) -> float:
        gross = self._gross_pnl(pos, exit_price)
        approx_notional = pos.entry_price * pos.contracts
        fees = approx_notional * self.cfg.fee_rate_per_side * 2
        return gross - fees

    async def _place_limit(self, symbol: str, side: str, contracts, reduce_only: bool = False) -> bool:
        price = await self.fetch_mark_price(symbol)
        if price <= 0:
            return False
        offset = self.cfg.limit_offset_bps / 10000.0
        limit_price = price * (1 - offset) if side == "buy" else price * (1 + offset)
        if reduce_only:
            limit_price = price * (1 + offset) if side == "sell" else price * (1 - offset)

        if self.cfg.paper_mode:
            return True

        try:
            await self.exchange.set_leverage(self.cfg.leverage, symbol, {"type": "swap"})
        except Exception:
            pass

        try:
            await self.exchange.create_limit_order(
                symbol, side, contracts, limit_price,
                {"marginMode": self.cfg.margin_mode, "type": "swap", **({"reduceOnly": True} if reduce_only else {})},
            )
            return True
        except Exception as exc:
            console.print(f"[yellow][{symbol}] order failed: {exc}[/yellow]")
            return False

    async def place_entry(self, symbol: str, side: str) -> bool:
        if time.time() - self.last_entry_ts.get(symbol, 0) < self.cfg.entry_cooldown_sec:
            return False
        if not await self.liquidation_buffer_ok(symbol):
            return False

        contracts = await self.estimate_min_contracts(symbol, dca_leg_index=0)
        if not contracts:
            return False

        price = await self.fetch_mark_price(symbol)
        if price <= 0:
            return False

        if self.cfg.paper_mode:
            self.paper_positions[symbol] = PositionState(symbol=symbol, side=side, contracts=float(contracts), entry_price=price, opened_ts=time.time(), dca_count=0, last_dca_ts=0.0, paper=True)
            self.last_entry_ts[symbol] = time.time()
            console.print(f"[green][PAPER] OPEN {side.upper()} {contracts} {symbol} @ {price:.8f}[/green]")
            return True

        ok = await self._place_limit(symbol, side, contracts, reduce_only=False)
        if ok:
            self.last_entry_ts[symbol] = time.time()
        return ok

    async def maybe_dca(self, pos: PositionState, mark: float) -> bool:
        if pos.dca_count >= self.cfg.max_dca_legs:
            return False
        if time.time() - pos.last_dca_ts < self.cfg.dca_cooldown_sec:
            return False
        if not await self.liquidation_buffer_ok(pos.symbol):
            return False

        if pos.side == "buy":
            drawdown_pct = (pos.entry_price / mark) - 1.0 if mark > 0 else 0.0
        else:
            drawdown_pct = (mark / pos.entry_price) - 1.0 if pos.entry_price > 0 else 0.0

        trigger = self.cfg.dca_trigger_pct * (pos.dca_count + 1)
        if drawdown_pct < trigger:
            return False

        add_contracts = await self.estimate_min_contracts(pos.symbol, dca_leg_index=pos.dca_count + 1)
        if not add_contracts:
            return False

        if self.cfg.paper_mode:
            total_contracts = pos.contracts + float(add_contracts)
            avg_entry = ((pos.entry_price * pos.contracts) + (mark * float(add_contracts))) / total_contracts
            pos.entry_price = avg_entry
            pos.contracts = total_contracts
            pos.dca_count += 1
            pos.last_dca_ts = time.time()
            self.paper_positions[pos.symbol] = pos
            console.print(f"[cyan][PAPER] DCA {pos.symbol} {pos.side.upper()} +{add_contracts} @ {mark:.8f} -> avg {avg_entry:.8f} total {total_contracts}[/cyan]")
            return True

        ok = await self._place_limit(pos.symbol, pos.side, add_contracts, reduce_only=False)
        if ok:
            console.print(f"[cyan]{pos.symbol} DCA {pos.side.upper()} +{add_contracts}[/cyan]")
        return ok

    async def place_exit(self, pos: PositionState) -> bool:
        symbol = pos.symbol
        exit_side = "sell" if pos.side == "buy" else "buy"
        mark = await self.fetch_mark_price(symbol)
        if mark <= 0:
            return False

        est_net = self._net_pnl_if_closed_now(pos, mark)
        if est_net <= self.cfg.min_profit_buffer_usdt:
            return False

        if self.cfg.paper_mode:
            self.realized_pnl[symbol] = self.realized_pnl.get(symbol, 0.0) + est_net
            self.paper_positions.pop(symbol, None)
            console.print(f"[magenta][PAPER] CLOSE {symbol} @ {mark:.8f} net={est_net:.6f}[/magenta]")
            return True

        ok = await self._place_limit(symbol, exit_side, pos.contracts, reduce_only=True)
        if ok:
            console.print(f"[magenta]CLOSE {symbol} {pos.contracts} est_net={est_net:.6f}[/magenta]")
        return ok

    async def emergency_reduce_if_needed(self) -> None:
        if self.cfg.paper_mode or not self.cfg.emergency_flatten:
            return
        snap = await self.get_balance_snapshot()
        if snap["margin_ratio"] < 0.90:
            return
        console.print("[bold red]Emergency protection triggered.[/bold red]")
        for symbol in list(self.selected_symbols):
            pos = await self.current_position(symbol)
            if not pos:
                continue
            side = "sell" if pos.side == "buy" else "buy"
            try:
                await self._place_limit(symbol, side, pos.contracts, reduce_only=True)
            except Exception:
                pass

    async def manage_symbol(self, symbol: str) -> None:
        pos = await self.current_position(symbol)

        if pos is None:
            signal_side = await self.fetch_signal(symbol)
            if signal_side:
                await self.place_entry(symbol, signal_side)
            return

        mark = await self.fetch_mark_price(symbol)
        if mark <= 0:
            return

        est_net = self._net_pnl_if_closed_now(pos, mark)
        if est_net > self.cfg.min_profit_buffer_usdt:
            await self.place_exit(pos)
            return

        await self.maybe_dca(pos, mark)

    async def report(self) -> None:
        now = time.time()
        if now - self.last_report_ts < self.cfg.report_interval_sec:
            return
        self.last_report_ts = now

        snap = await self.get_balance_snapshot()
        table = Table(title="Profit-Only DCA Micro Bot")
        table.add_column("Mode")
        table.add_column("Equity")
        table.add_column("Free")
        table.add_column("Used")
        table.add_column("Margin")
        table.add_column("Symbols")
        table.add_column("Open")
        table.add_column("Realized")

        table.add_row(
            "PAPER" if self.cfg.paper_mode else "LIVE",
            f"{snap['equity']:.4f}",
            f"{snap['free']:.4f}",
            f"{snap['used']:.4f}",
            f"{snap['margin_ratio']:.2%}",
            ", ".join(self.selected_symbols) if self.selected_symbols else "-",
            str(len(self.paper_positions) if self.cfg.paper_mode else "live"),
            f"{sum(self.realized_pnl.values()):.6f}",
        )
        console.print(table)

    async def run(self) -> None:
        await self.initialize()
        console.print(
            f"[bold cyan]Starting {'PAPER' if self.cfg.paper_mode else 'LIVE'} profit-only DCA bot | "
            f"lev={self.cfg.leverage} | max_symbols={self.cfg.max_symbols}[/bold cyan]"
        )

        while self.running:
            try:
                await self.refresh_universe_if_needed()
                await self.emergency_reduce_if_needed()
                for symbol in self.selected_symbols:
                    if not self.running:
                        break
                    await self.manage_symbol(symbol)
                    await asyncio.sleep(self.cfg.loop_delay_sec)
                await self.report()
                self._save_state()
                await asyncio.sleep(0.2)
            except Exception as exc:
                console.print(f"[red]Main loop error: {exc}[/red]")
                await asyncio.sleep(2)


async def main() -> None:
    bot = ProfitOnlyDCABot(BotConfig())
    try:
        await bot.run()
    finally:
        await bot.cleanup()


if __name__ == "__main__":
    asyncio.run(main())
