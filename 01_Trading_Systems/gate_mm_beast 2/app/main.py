
from __future__ import annotations
import asyncio
import logging
import math
import signal
import time

import pandas as pd

from app.config import Settings
from app.logging_setup import setup_logging
from app.persistence.db import Database
from app.persistence.order_repository import OrderRepository
from app.persistence.position_repository import PositionRepository
from app.persistence.fill_repository import FillRepository
from app.persistence.decision_repository import DecisionRepository
from app.persistence.event_repository import EventRepository
from app.persistence.snapshot_repository import SnapshotRepository
from app.connectors.gateio.rest_public import GatePublicRest
from app.connectors.gateio.rest_private import GatePrivateRest
from app.connectors.gateio.ws_public import GatePublicWS
from app.market_data.market_data_service import MarketDataService, SymbolRuntime
from app.market_data.candles_service import CandlesService, add_features
from app.oms.execution_service import ExecutionService
from app.oms.order_manager import OrderManager
from app.portfolio.position_manager import PositionManager
from app.portfolio.inventory_manager import InventoryManager
from app.portfolio.pnl_manager import PnLManager
from app.risk.limits import RiskLimits
from app.risk.kill_switch import KillSwitch
from app.risk.risk_manager import RiskManager
from app.strategy.alpha_model import estimate_alpha
from app.strategy.quote_engine import QuoteEngine
from app.backtest.replay_engine import ReplayEngine
from app.observability.metrics import Metrics
from app.api.server import APIServer

log = logging.getLogger("gate_mm_beast")


def _synthetic_candles(symbol: str, limit: int) -> pd.DataFrame:
    base = {
        "DOGE_USDT": 0.10,
        "XRP_USDT": 0.55,
        "TRX_USDT": 0.12,
    }.get(symbol, 1.0)
    rows: list[dict] = []
    for i in range(max(limit, 120)):
        drift = math.sin(i / 9.0) * base * 0.005
        close = max(base + drift, 1e-8)
        high = close * 1.0015
        low = close * 0.9985
        open_px = close * (0.9995 if i % 2 else 1.0005)
        rows.append(
            {
                "timestamp": pd.Timestamp.utcnow() - pd.Timedelta(minutes=max(limit, 120) - i),
                "open": open_px,
                "high": high,
                "low": low,
                "close": close,
                "volume": 1000.0 + (i % 17) * 23.0,
            }
        )
    return add_features(pd.DataFrame(rows)).dropna().reset_index(drop=True)


class Application:
    def __init__(self, cfg: Settings) -> None:
        self.cfg = cfg
        self.db = Database(cfg.db_path)
        self.order_repo = OrderRepository(self.db)
        self.position_repo = PositionRepository(self.db)
        self.fill_repo = FillRepository(self.db)
        self.decision_repo = DecisionRepository(self.db)
        self.event_repo = EventRepository(self.db)
        self.snapshot_repo = SnapshotRepository(self.db)

        self.public_rest = GatePublicRest(cfg)
        self.private_rest = GatePrivateRest(cfg)
        self.market = MarketDataService()
        self.candles_service = CandlesService(self.public_rest)

        self.execution = ExecutionService(self.private_rest)
        self.order_manager = OrderManager(self.order_repo, self.execution)
        self.position_manager = PositionManager(self.position_repo)
        self.inventory = InventoryManager()
        self.pnl = PnLManager()
        self.risk = RiskManager(RiskLimits(), KillSwitch())
        self.quote_engine = QuoteEngine()
        self.replay = ReplayEngine(cfg.take_atr_mult, cfg.stop_atr_mult)
        self.metrics = Metrics()
        self.shutdown = False
        self.offline_paper_mode = False

        self.live_orders: dict[str, dict[str, dict]] = {}
        self.last_rest_refresh: dict[str, float] = {}
        self.last_sync_ts = 0.0

        self.app_state = {"healthy": True, "message": "ok"}
        self.engine_state = {"mode": cfg.mode, "symbols": cfg.symbols, "status": "starting"}

        self.api = None
        if cfg.enable_api:
            self.api = APIServer(cfg.api_host, cfg.api_port, {
                "app_state": self.app_state,
                "metrics": self.metrics,
                "position_repo": self.position_repo,
                "order_repo": self.order_repo,
                "symbols": cfg.symbols,
                "engine_state": self.engine_state,
            })

    async def bootstrap(self) -> None:
        runtimes = {}
        specs = {}
        try:
            contracts = await self.public_rest.list_contracts()
            specs = {str(c.get("name") or c.get("contract") or ""): c for c in contracts}
        except Exception as exc:
            if self.cfg.mode != "paper":
                raise
            self.offline_paper_mode = True
            self.app_state["message"] = f"paper offline bootstrap: {exc}"
            log.warning("falling back to offline paper bootstrap: %s", exc)

        for symbol in self.cfg.symbols:
            spec = specs.get(symbol, {})
            tick = float(spec.get("order_price_round") or 0.0001)
            multiplier = float(spec.get("quanto_multiplier") or 1.0)
            rt = SymbolRuntime(symbol=symbol, tick=tick, multiplier=multiplier)
            if self.offline_paper_mode and self.cfg.mode == "paper":
                rt.candles = _synthetic_candles(symbol, self.cfg.bar_limit)
            else:
                try:
                    rt.candles = await self.candles_service.load(symbol, self.cfg.bar_interval, self.cfg.bar_limit)
                except Exception as exc:
                    if self.cfg.mode != "paper":
                        raise
                    self.offline_paper_mode = True
                    log.warning("using synthetic candles for %s: %s", symbol, exc)
                    rt.candles = _synthetic_candles(symbol, self.cfg.bar_limit)
            if rt.candles is None or rt.candles.empty:
                rt.candles = _synthetic_candles(symbol, self.cfg.bar_limit)
                self.offline_paper_mode = self.cfg.mode == "paper" or self.offline_paper_mode

            last_close = float(rt.candles.iloc[-1]["close"])
            spread = max(rt.tick * 2.0, last_close * 0.0005)
            rt.book.bid = last_close - spread / 2.0
            rt.book.ask = last_close + spread / 2.0
            rt.book.bid_size = 1000.0
            rt.book.ask_size = 1000.0
            rt.book.ts = time.time()
            runtimes[symbol] = rt
        self.market.set_symbols(runtimes)

        if self.cfg.mode == "live" and self.cfg.startup_sync:
            await self._sync_exchange_state(force=True)
            if self.cfg.cancel_all_on_start:
                await self._cancel_all_open_orders()

    def _advance_offline_books(self, step: int) -> None:
        for idx, symbol in enumerate(self.market.symbols()):
            rt = self.market.get(symbol)
            if not rt or rt.candles is None or rt.candles.empty:
                continue
            last_close = float(rt.candles.iloc[-1]["close"])
            wave = math.sin((step + idx) / 5.0) * max(last_close * 0.001, rt.tick)
            mid = max(last_close + wave, rt.tick)
            spread = max(rt.tick * 2.0, mid * 0.0005)
            rt.book.bid = mid - spread / 2.0
            rt.book.ask = mid + spread / 2.0
            rt.book.bid_size = 1000.0 + (step % 7) * 25.0
            rt.book.ask_size = 1000.0 + ((step + 3) % 7) * 25.0
            rt.book.ts = time.time()
            rt.recent_mid.append(mid)

    async def _refresh_book_via_rest(self, symbol: str) -> None:
        now = time.time()
        if now - self.last_rest_refresh.get(symbol, 0.0) < self.cfg.rest_book_refresh_seconds:
            return
        data = await self.public_rest.order_book(symbol, limit=1)
        bids = data.get("bids") or []
        asks = data.get("asks") or []
        if not bids or not asks:
            return
        bid = bids[0]
        ask = asks[0]
        bid_px = float(bid[0] if isinstance(bid, (list, tuple)) else bid.get("p") or bid.get("price") or 0.0)
        ask_px = float(ask[0] if isinstance(ask, (list, tuple)) else ask.get("p") or ask.get("price") or 0.0)
        bid_sz = float(bid[1] if isinstance(bid, (list, tuple)) and len(bid) > 1 else bid.get("s") or bid.get("size") or 0.0)
        ask_sz = float(ask[1] if isinstance(ask, (list, tuple)) and len(ask) > 1 else ask.get("s") or ask.get("size") or 0.0)
        rt = self.market.get(symbol)
        if rt and bid_px > 0 and ask_px > 0:
            rt.book.bid = bid_px
            rt.book.ask = ask_px
            rt.book.bid_size = bid_sz
            rt.book.ask_size = ask_sz
            rt.book.ts = now
            rt.recent_mid.append(rt.book.mid)
            self.last_rest_refresh[symbol] = now

    def _book_is_stale(self, symbol: str) -> bool:
        rt = self.market.get(symbol)
        return (not rt) or (time.time() - rt.book.ts > self.cfg.book_stale_seconds) or rt.book.bid <= 0 or rt.book.ask <= 0

    async def _sync_exchange_state(self, force: bool = False) -> None:
        now = time.time()
        if not force and now - self.last_sync_ts < max(self.cfg.loop_seconds, 3.0):
            return
        self.last_sync_ts = now
        positions = await self.private_rest.list_positions()
        open_orders = await self.private_rest.list_open_orders()
        inv = {}
        for pos in positions or []:
            symbol = str(pos.get("contract") or pos.get("symbol") or "")
            size = int(float(pos.get("size") or 0))
            if symbol:
                inv[symbol] = size
        self.inventory.net_by_symbol = inv
        live_orders: dict[str, dict[str, dict]] = {symbol: {} for symbol in self.cfg.symbols}
        for order in open_orders or []:
            symbol = str(order.get("contract") or order.get("symbol") or "")
            if symbol not in live_orders:
                live_orders[symbol] = {}
            size = int(abs(float(order.get("size") or 0)))
            side = "buy" if float(order.get("size") or 0) > 0 else "sell"
            live_orders[symbol][side] = {
                "order_id": str(order.get("id") or order.get("order_id") or ""),
                "price": float(order.get("price") or 0.0),
                "size": size,
                "reduce_only": bool(order.get("reduce_only", False)),
                "symbol": symbol,
                "side": side,
            }
        self.live_orders = live_orders
        self.snapshot_repo.set("inventory", self.inventory.net_by_symbol)
        self.snapshot_repo.set("live_orders", self.live_orders)

    async def _cancel_all_open_orders(self) -> None:
        open_orders = await self.private_rest.list_open_orders()
        for order in open_orders or []:
            order_id = str(order.get("id") or order.get("order_id") or "")
            if not order_id:
                continue
            try:
                await self.private_rest.cancel_order(order_id)
            except Exception:
                log.exception("cancel_all_open_orders failed for %s", order_id)
        self.live_orders = {symbol: {} for symbol in self.cfg.symbols}

    async def _cancel_live_order(self, symbol: str, side: str) -> None:
        order = self.live_orders.get(symbol, {}).get(side)
        if not order:
            return
        order_id = order.get("order_id")
        if not order_id:
            return
        await self.private_rest.cancel_order(order_id)
        self.live_orders.setdefault(symbol, {}).pop(side, None)

    async def _place_live_order(self, symbol: str, side: str, price: float, size: int, reduce_only: bool = False) -> None:
        if not self.cfg.live_enable_trading:
            return
        signed_size = size if side == "buy" else -size
        tif = "poc" if self.cfg.post_only_mode else self.cfg.quote_tif
        resp = await self.private_rest.create_order(symbol, signed_size, price, f"mm_{side}_{symbol}", reduce_only=reduce_only, tif=tif)
        order_id = str(resp.get("id") or resp.get("order_id") or "")
        self.live_orders.setdefault(symbol, {})[side] = {
            "order_id": order_id,
            "price": price,
            "size": size,
            "reduce_only": reduce_only,
            "symbol": symbol,
            "side": side,
        }
        self.metrics.inc("orders_submitted")

    async def _manage_live_quotes(self, symbol: str, quote: dict, net_qty: int) -> None:
        if self.order_repo.count_open_orders() >= self.cfg.max_total_open_orders:
            self.app_state["healthy"] = False
            self.app_state["message"] = "max total open orders exceeded"
            return

        target_buy_size = int(max(min(quote["bid_size"], self.cfg.max_abs_position_per_symbol - max(net_qty, 0)), 0))
        target_sell_size = int(max(min(quote["ask_size"], self.cfg.max_abs_position_per_symbol - max(-net_qty, 0)), 0))
        targets = {
            "buy": {"price": quote["bid_px"], "size": target_buy_size},
            "sell": {"price": quote["ask_px"], "size": target_sell_size},
        }

        for side, target in targets.items():
            current = self.live_orders.setdefault(symbol, {}).get(side)
            desired_size = int(target["size"])
            desired_price = float(target["price"])
            if desired_size <= 0:
                if current:
                    await self._cancel_live_order(symbol, side)
                continue

            replace = current is None
            if current is not None:
                ticks_apart = abs(desired_price - float(current.get("price") or 0.0)) / max(self.market.get(symbol).tick, 1e-12)
                size_changed = int(current.get("size") or 0) != desired_size
                reduce_only_changed = bool(current.get("reduce_only", False))
                replace = ticks_apart >= self.cfg.replace_threshold_ticks or size_changed or reduce_only_changed

            if replace and current:
                await self._cancel_live_order(symbol, side)
                await asyncio.sleep(0.05)

            if replace:
                await self._place_live_order(symbol, side, desired_price, desired_size, reduce_only=False)

        self.snapshot_repo.set(f"live_quote:{symbol}", self.live_orders.get(symbol, {}))

    async def process_symbol(self, symbol: str) -> None:
        rt = self.market.get(symbol)
        if not rt or rt.candles is None or len(rt.candles) < 80:
            return
        if self.cfg.mode == "live" and self._book_is_stale(symbol):
            try:
                await self._refresh_book_via_rest(symbol)
            except Exception as exc:
                log.warning("rest book refresh failed for %s: %s", symbol, exc)
        if rt.book.bid <= 0 or rt.book.ask <= 0:
            return

        alpha = estimate_alpha(rt)
        self.decision_repo.insert(symbol, alpha["score"], alpha["confidence"], {"alpha": alpha})
        base_size = max(int((self.cfg.risk_usd * self.cfg.leverage) / max(rt.book.mid * max(rt.multiplier, 1e-9), 1e-9)), 1)
        max_abs_qty = max(self.cfg.max_abs_position_per_symbol, base_size)
        quote = self.quote_engine.build(
            symbol=symbol,
            mid=rt.book.mid,
            bid=rt.book.bid,
            ask=rt.book.ask,
            tick=rt.tick,
            base_size=base_size,
            alpha_score=alpha["score"],
            volatility_score=min(abs(alpha["score"]), 1.0),
            net_qty=self.inventory.net(symbol),
            max_abs_qty=max_abs_qty,
        )
        quote_data = {
            "bid_px": quote.bid_px,
            "ask_px": quote.ask_px,
            "bid_size": quote.bid_size,
            "ask_size": quote.ask_size,
            "alpha_score": quote.alpha_score,
            "fair_value": quote.fair_value,
            "meta": quote.meta,
        }
        self.snapshot_repo.set(f"quote:{symbol}", quote_data)
        self.engine_state["status"] = "running"
        self.engine_state["last_symbol"] = symbol
        self.engine_state["last_quote"] = quote_data

        if self.cfg.mode == "paper":
            return

        if not self.cfg.gate_api_key or not self.cfg.gate_api_secret:
            self.app_state["healthy"] = False
            self.app_state["message"] = "live mode requires Gate.io credentials"
            return

        try:
            await self._manage_live_quotes(symbol, quote_data, self.inventory.net(symbol))
            self.metrics.inc("quotes_live")
        except Exception as exc:
            self.app_state["healthy"] = False
            self.app_state["message"] = f"live quote management error: {exc}"
            log.exception("live quote management failed for %s", symbol)

    async def run(self) -> int:
        try:
            await self.bootstrap()
        except Exception as exc:
            self.app_state["healthy"] = False
            self.app_state["message"] = f"bootstrap failed: {exc}"
            log.exception("bootstrap failed")
            await self.public_rest.close()
            await self.private_rest.close()
            return 1
        tasks: list[asyncio.Task] = []

        if not self.offline_paper_mode:
            ws = GatePublicWS(self.cfg, self.market.on_book_ticker)
            tasks.append(asyncio.create_task(ws.run_book_ticker(self.market.symbols())))
        else:
            self.engine_state["status"] = "offline-paper"
            self.app_state["message"] = "offline paper mode with synthetic market data"

        if self.api:
            try:
                self.api.start_in_thread()
            except OSError as exc:
                self.app_state["message"] = f"api disabled: {exc}"
                log.warning("api server not started: %s", exc)
                self.api = None

        stop_event = asyncio.Event()

        def stop():
            self.shutdown = True
            stop_event.set()
            for task in tasks:
                if not task.done():
                    task.cancel()

        loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                loop.add_signal_handler(sig, stop)
            except NotImplementedError:
                pass

        step = 0
        try:
            while not self.shutdown:
                if self.offline_paper_mode:
                    self._advance_offline_books(step)
                    step += 1
                elif self.cfg.mode == "live":
                    try:
                        await self._sync_exchange_state()
                    except Exception as exc:
                        self.app_state["healthy"] = False
                        self.app_state["message"] = f"exchange sync error: {exc}"
                        log.warning("exchange sync failed: %s", exc)
                for symbol in self.market.symbols():
                    await self.process_symbol(symbol)
                await asyncio.sleep(self.cfg.loop_seconds)
        finally:
            stop()
            for task in tasks:
                try:
                    await task
                except asyncio.CancelledError:
                    pass
                except Exception:
                    log.exception("background task stopped with error")
            await self.public_rest.close()
            await self.private_rest.close()
            if self.api:
                self.api.stop()
        return 0


def run() -> int:
    cfg = Settings()
    setup_logging(cfg.log_level)
    return asyncio.run(Application(cfg).run())


if __name__ == "__main__":
    raise SystemExit(run())
