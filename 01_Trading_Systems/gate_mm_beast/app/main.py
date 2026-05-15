from __future__ import annotations
import asyncio
import contextlib
import logging
import signal
import time
from app.config import Settings
from app.logging_setup import setup_logging
from app.constants import ORDER_STATE_FILLED
from app.core.ids import client_order_id
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
from app.market_data.candles_service import CandlesService
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
from app.services.unified_balance_service import UnifiedBalanceService

log = logging.getLogger("gate_mm_beast")

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
        self.unified_balance_service = UnifiedBalanceService(cfg)
        self.shutdown = False
        self.last_paper_fill_ts: dict[str, float] = {}

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
                "unified_balance_service": self.unified_balance_service,
            })

    def restore_runtime_memory(self) -> None:
        self.app_state.update(self.snapshot_repo.get("app_state", self.app_state.copy()))
        self.engine_state.update(self.snapshot_repo.get("engine_state", self.engine_state.copy()))
        self.inventory.import_state(self.snapshot_repo.get("inventory", {}))

        quote_snaps = self.snapshot_repo.get_prefix("quote:")
        if not quote_snaps:
            return

        restored = []
        for key, snap in quote_snaps.items():
            symbol = key.split(":", 1)[-1]
            rt = self.market.get(symbol)
            if not rt:
                continue
            bid = float(snap.get("bid_px") or 0.0)
            ask = float(snap.get("ask_px") or 0.0)
            if bid > 0 and ask > 0 and ask >= bid:
                rt.book.bid = bid
                rt.book.ask = ask
                rt.book.bid_size = float(snap.get("bid_size") or 0.0)
                rt.book.ask_size = float(snap.get("ask_size") or 0.0)
                restored.append(symbol)

        if restored:
            self.engine_state["restored_quotes"] = restored

    def persist_runtime_memory(self) -> None:
        self.snapshot_repo.set("app_state", self.app_state)
        self.snapshot_repo.set("engine_state", self.engine_state)
        self.snapshot_repo.set("inventory", self.inventory.export_state())

    async def bootstrap(self) -> None:
        contracts = await self.public_rest.list_contracts()
        specs = {str(c.get("name") or c.get("contract") or ""): c for c in contracts}
        runtimes = {}
        for symbol in self.cfg.symbols:
            spec = specs.get(symbol, {})
            tick = float(spec.get("order_price_round") or 0.0001)
            multiplier = float(spec.get("quanto_multiplier") or 1.0)
            rt = SymbolRuntime(symbol=symbol, tick=tick, multiplier=multiplier)
            rt.candles = await self.candles_service.load(symbol, self.cfg.bar_interval, self.cfg.bar_limit)
            runtimes[symbol] = rt
        self.market.set_symbols(runtimes)
        self.restore_runtime_memory()

    async def process_symbol(self, symbol: str) -> None:
        rt = self.market.get(symbol)
        if not rt or rt.candles is None or len(rt.candles) < 80:
            return
        if rt.book.bid <= 0 or rt.book.ask <= 0:
            return
        alpha = estimate_alpha(rt)
        self.decision_repo.insert(symbol, alpha["score"], alpha["confidence"], {"alpha": alpha})
        base_size = max(int((self.cfg.risk_usd * self.cfg.leverage) / max(rt.book.mid * max(rt.multiplier, 1e-9), 1e-9)), 1)
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
            max_abs_qty=10,
        )
        self.snapshot_repo.set(f"quote:{symbol}", {
            "bid_px": quote.bid_px,
            "ask_px": quote.ask_px,
            "bid_size": quote.bid_size,
            "ask_size": quote.ask_size,
            "alpha_score": quote.alpha_score,
            "fair_value": quote.fair_value,
            "meta": quote.meta,
        })
        self.engine_state["status"] = "running"
        self.engine_state["last_symbol"] = symbol
        self.engine_state["last_quote"] = self.snapshot_repo.get(f"quote:{symbol}")
        self.metrics.values["quotes_live"] = len(self.market.symbols())
        self.persist_runtime_memory()

        if self.cfg.mode == "paper":
            self._simulate_paper_activity(symbol, quote)
            return

    def _simulate_paper_activity(self, symbol: str, quote) -> None:
        now = time.time()
        last_ts = self.last_paper_fill_ts.get(symbol, 0.0)
        if (now - last_ts) < max(self.cfg.loop_seconds * 2.0, 4.0):
            return

        side = "buy" if quote.alpha_score >= 0 else "sell"
        signed_qty = int(quote.bid_size if side == "buy" else -quote.ask_size)
        size = abs(signed_qty)
        if size <= 0:
            return

        price = float(quote.bid_px if side == "buy" else quote.ask_px)
        coid = client_order_id("paper", symbol)

        self.order_repo.insert(
            symbol=symbol,
            client_order_id=coid,
            exchange_order_id="paper",
            side=side,
            role="entry",
            state=ORDER_STATE_FILLED,
            price=price,
            size=size,
            payload={"mode": "paper", "simulated": True},
        )
        self.order_repo.update_state(coid, ORDER_STATE_FILLED, filled_size=size, avg_fill_price=price)
        self.fill_repo.insert(
            symbol=symbol,
            client_order_id=coid,
            exchange_order_id="paper",
            side=side,
            fill_qty=size,
            fill_price=price,
            payload={"mode": "paper", "simulated": True},
        )
        self.inventory.apply_fill(symbol, signed_qty)
        self.metrics.inc("orders_submitted", 1)
        self.metrics.inc("fills", 1)
        self.event_repo.write("INFO", "paper_fill", symbol, {
            "client_order_id": coid,
            "side": side,
            "size": size,
            "price": price,
            "net_inventory": self.inventory.net(symbol),
        })
        self.last_paper_fill_ts[symbol] = now

    async def _unified_balance_loop(self) -> None:
        while not self.shutdown:
            try:
                await self.unified_balance_service.refresh()
            except Exception as exc:
                self.event_repo.write("ERROR", "unified_balance_refresh_failed", "", {"error": str(exc)})
            await asyncio.sleep(max(5, self.cfg.unified_balance_refresh_seconds))

    async def run(self) -> int:
        await self.bootstrap()
        await self.unified_balance_service.refresh()
        ws = GatePublicWS(self.cfg, self.market.on_book_ticker)
        tasks = [
            asyncio.create_task(ws.run_book_ticker(self.market.symbols())),
            asyncio.create_task(self._unified_balance_loop()),
        ]

        if self.api:
            self.api.start_in_thread()

        stop_event = asyncio.Event()

        def stop():
            ws.shutdown = True
            self.shutdown = True
            stop_event.set()

        loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                loop.add_signal_handler(sig, stop)
            except NotImplementedError:
                pass

        try:
            while not self.shutdown:
                for symbol in self.market.symbols():
                    try:
                        await self.process_symbol(symbol)
                    except Exception as exc:
                        self.app_state["healthy"] = False
                        self.app_state["message"] = f"symbol_processing_error:{symbol}"
                        self.event_repo.write("ERROR", "process_symbol_failed", symbol, {"error": str(exc)})
                await asyncio.sleep(self.cfg.loop_seconds)
        finally:
            stop()
            self.engine_state["status"] = "stopped"
            self.persist_runtime_memory()
            for task in tasks:
                task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await task
            await self.public_rest.close()
            await self.private_rest.close()
            await self.unified_balance_service.close()
            if self.api:
                self.api.stop()
        return 0

def run() -> int:
    cfg = Settings()
    setup_logging(cfg.log_level)
    return asyncio.run(Application(cfg).run())

if __name__ == "__main__":
    raise SystemExit(run())
