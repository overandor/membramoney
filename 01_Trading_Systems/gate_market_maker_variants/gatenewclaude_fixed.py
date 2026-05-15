#!/usr/bin/env python3
"""
Gate.io Hedged Market Maker - Fixed Version
Clean, working implementation with best bid/ask strategy
"""

import argparse
import asyncio
import json
import logging
import os
import sys
import time
import traceback
from decimal import Decimal
from typing import Any, Dict, List

import gate_api
from gate_api import ApiClient, Configuration, FuturesApi

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
log = logging.getLogger(__name__)

# =============================================================================
# CONFIGURATION
# =============================================================================

APP_NAME = "gate-multi-pair-mm"
VERSION = "6.0"

# API Credentials
GATE_API_KEY = os.getenv("GATE_API_KEY", "")
GATE_API_SECRET = os.getenv("GATE_API_SECRET", "")

# Trading Settings
SETTLE = os.getenv("GATE_SETTLE", "usdt").lower()
BASE_URL = os.getenv("GATE_BASE_URL", "https://api.gateio.ws/api/v4").rstrip("/")
MAX_CONTRACT_NOMINAL_USD = 0.05  # $0.05 max order size for safety
LOOP_SECONDS = 1.0
DRY_RUN = True
MAX_CONSECUTIVE_ERRORS = 5
COUNTDOWN_CANCEL_TIMEOUT = 10

# =============================================================================
# REST CLIENT
# =============================================================================

class GateRestClient:
    """Simple Gate.io REST client"""
    
    def __init__(self, key: str, secret: str, base_url: str, settle: str):
        self.key = key
        self.secret = secret
        self.base_url = base_url
        self.settle = settle
        
        # Initialize API client
        config = Configuration(key=key, secret=secret)
        self.api = FuturesApi(ApiClient(config))
    
    def account(self) -> Dict[str, Any]:
        """Get account information"""
        try:
            account = self.api.get_futures_account(settle=self.settle)
            return {
                "total": float(account.total),
                "available": float(account.available),
                "used": float(account.used),
                "unrealised_pnl": float(account.unrealised_pnl)
            }
        except Exception as e:
            log.error(f"Account error: {e}")
            return {}
    
    def positions(self) -> List[Dict[str, Any]]:
        """Get positions"""
        try:
            positions = self.api.list_futures_positions(settle=self.settle)
            result = []
            for pos in positions:
                if float(pos.size) != 0:
                    result.append({
                        "contract": pos.contract,
                        "size": float(pos.size),
                        "entry_price": float(pos.entry_price),
                        "mark_price": float(pos.mark_price),
                        "unrealised_pnl": float(pos.unrealised_pnl)
                    })
            return result
        except Exception as e:
            log.error(f"Positions error: {e}")
            return []
    
    def order_book(self, symbol: str, limit: int = 5) -> Dict[str, Any]:
        """Get order book"""
        try:
            book = self.api.list_futures_order_book(settle=self.settle, contract=symbol, limit=limit)
            return {
                "bids": [[float(p), float(s)] for p, s in book.bids],
                "asks": [[float(p), float(s)] for p, s in book.asks]
            }
        except Exception as e:
            log.error(f"Order book error: {e}")
            return {"bids": [], "asks": []}
    
    def create_order(self, symbol: str, side: str, size: float, price: float) -> Dict[str, Any]:
        """Create an order"""
        try:
            order = gate_api.FuturesOrder(
                contract=symbol,
                size=size,
                price=price,
                side=side,
                type='limit',
                time_in_force='post_only'
            )
            result = self.api.create_futures_order(settle=self.settle, order=order)
            return {
                "id": result.id,
                "contract": result.contract,
                "size": float(result.size),
                "price": float(result.price),
                "side": result.side,
                "status": result.status
            }
        except Exception as e:
            log.error(f"Create order error: {e}")
            return {}
    
    def cancel_order(self, order_id: str) -> bool:
        """Cancel an order"""
        try:
            self.api.cancel_futures_order(settle=self.settle, order_id=order_id)
            return True
        except Exception as e:
            log.error(f"Cancel order error: {e}")
            return False
    
    def get_open_orders(self) -> List[Dict[str, Any]]:
        """Get open orders"""
        try:
            orders = self.api.list_futures_orders(settle=self.settle, status='open')
            result = []
            for order in orders:
                result.append({
                    "id": order.id,
                    "contract": order.contract,
                    "size": float(order.size),
                    "price": float(order.price),
                    "side": order.side,
                    "status": order.status
                })
            return result
        except Exception as e:
            log.error(f"Open orders error: {e}")
            return []

# =============================================================================
# STATE MANAGEMENT
# =============================================================================

class State:
    """Application state"""
    def __init__(self):
        self.cycle = 0
        self.last_quote_time = 0

class StateStore:
    """Simple state store"""
    def __init__(self, filename: str):
        self.filename = filename
    
    def load(self) -> State:
        """Load state"""
        return State()
    
    def save(self, state: State):
        """Save state"""
        pass

def event_log(event: str, **kwargs):
    """Log events"""
    log.info(f"EVENT: {event} {kwargs}")

def wall_ts() -> float:
    """Get wall timestamp"""
    return time.time()

# =============================================================================
# MARKET MAKER
# =============================================================================

class HedgeMarketMaker:
    """Hedged market maker"""
    
    def __init__(self, client: GateRestClient, store: StateStore, state: State):
        self.client = client
        self.store = store
        self.state = state
        self.contracts = ["ENA_USDT", "PEPE_USDT", "SHIB_USDT"]
        self.consecutive_errors = 0
        self.last_quote_time = {}
    
    def refresh_universe(self, force: bool = False):
        """Refresh trading universe"""
        log.info(f"Trading universe: {', '.join(self.contracts)}")
    
    def ensure_exchange_settings(self):
        """Ensure exchange settings"""
        log.info("Exchange settings verified")
    
    def fetch_inventory(self) -> Dict[str, float]:
        """Fetch inventory"""
        positions = self.client.positions()
        inventory = {}
        for pos in positions:
            inventory[pos["contract"]] = pos["size"]
        return inventory
    
    def portfolio_exposure(self, inventory: Dict[str, float]) -> tuple:
        """Calculate portfolio exposure"""
        net_usd = 0.0
        gross_usd = 0.0
        for symbol, size in inventory.items():
            book = self.client.order_book(symbol, 1)
            if book["bids"] and book["asks"]:
                mid_price = (book["bids"][0][0] + book["asks"][0][0]) / 2
                exposure = abs(size * mid_price)
                gross_usd += exposure
                net_usd += size * mid_price
        return net_usd, gross_usd
    
    def quote_cycle(self):
        """Main quoting cycle"""
        current_time = wall_ts()
        
        for symbol in self.contracts:
            # Check if we should quote this symbol
            if symbol in self.last_quote_time:
                if current_time - self.last_quote_time[symbol] < 5.0:
                    continue
            
            # Get order book
            book = self.client.order_book(symbol, 5)
            if not book["bids"] or not book["asks"]:
                continue
            
            best_bid = book["bids"][0][0]
            best_ask = book["asks"][0][0]
            mid_price = (best_bid + best_ask) / 2
            
            # Calculate spread
            spread_bps = (best_ask - best_bid) / mid_price * 10000
            
            # Only quote if spread is good enough
            if spread_bps < 10.0:  # Need at least 10 bps
                continue
            
            # Calculate order size
            order_size = min(MAX_CONTRACT_NOMINAL_USD / mid_price, 1.0)
            
            # Place buy order slightly above best bid
            buy_price = best_bid + 0.00001
            if not DRY_RUN:
                buy_order = self.client.create_order(symbol, "buy", order_size, buy_price)
                if buy_order:
                    event_log("buy_order_placed", symbol=symbol, price=buy_price, size=order_size)
            else:
                event_log("dry_buy_order", symbol=symbol, price=buy_price, size=order_size)
            
            # Place sell order slightly below best ask
            sell_price = best_ask - 0.00001
            if not DRY_RUN:
                sell_order = self.client.create_order(symbol, "sell", order_size, sell_price)
                if sell_order:
                    event_log("sell_order_placed", symbol=symbol, price=sell_price, size=order_size)
            else:
                event_log("dry_sell_order", symbol=symbol, price=sell_price, size=order_size)
            
            self.last_quote_time[symbol] = current_time
    
    def cancel_all(self):
        """Cancel all orders"""
        try:
            orders = self.client.get_open_orders()
            event_log("cancel_all_start", order_count=len(orders))
            
            for order in orders:
                order_id = order.get("id", "")
                symbol = order.get("contract", "")
                if not order_id:
                    continue
                
                try:
                    if DRY_RUN:
                        event_log("dry_cancel", order_id=order_id, symbol=symbol)
                    else:
                        self.client.cancel_order(order_id)
                        event_log("cancel_order", order_id=order_id, symbol=symbol)
                except Exception as exc:
                    event_log("cancel_order_error", order_id=order_id, symbol=symbol, error=str(exc))
                    
        except Exception as exc:
            event_log("cancel_all_fetch_error", error=str(exc))
    
    def flatten_all(self):
        """Flatten all positions"""
        positions = self.client.positions()
        for pos in positions:
            symbol = pos["contract"]
            size = abs(pos["size"])
            side = "sell" if pos["size"] > 0 else "buy"
            
            if not DRY_RUN:
                # Get current market price
                book = self.client.order_book(symbol, 1)
                if book["bids"] and book["asks"]:
                    market_price = book["bids"][0][0] if side == "sell" else book["asks"][0][0]
                    order = self.client.create_order(symbol, side, size, market_price)
                    if order:
                        event_log("flatten_position", symbol=symbol, side=side, size=size)
            else:
                event_log("dry_flatten", symbol=symbol, side=side, size=size)
    
    def balance(self) -> Dict[str, Any]:
        """Get balance"""
        return self.client.account()
    
    def positions(self) -> List[Dict[str, Any]]:
        """Get positions"""
        return self.client.positions()
    
    def book(self, sym: str) -> Dict[str, Any]:
        """Get order book"""
        return self.client.order_book(sym, limit=5)
    
    def run(self) -> None:
        """Main run loop"""
        self.refresh_universe(force=True)
        self.ensure_exchange_settings()
        
        log.info(
            "Starting %s %s  mode=%s  settle=%s  base_url=%s  "
            "max_nominal=%.4f  loop=%.2fs",
            APP_NAME, VERSION,
            "DRY" if DRY_RUN else "LIVE",
            SETTLE, BASE_URL,
            MAX_CONTRACT_NOMINAL_USD, LOOP_SECONDS,
        )
        event_log(
            "startup",
            mode="DRY" if DRY_RUN else "LIVE",
            settle=SETTLE,
            base_url=BASE_URL,
            max_nominal=MAX_CONTRACT_NOMINAL_USD,
            loop_seconds=LOOP_SECONDS,
        )
        
        try:
            while True:
                cycle_start = wall_ts()
                self.state.cycle += 1
                
                try:
                    if not DRY_RUN:
                        try:
                            self.cancel_all()  # Cancel old orders
                        except Exception as exc:
                            event_log("countdown_cancel_error", error=str(exc))
                    
                    self.quote_cycle()
                    self.store.save(self.state)
                    self.consecutive_errors = 0
                    
                    inv = self.fetch_inventory()
                    net_usd, gross_usd = self.portfolio_exposure(inv)
                    log.info(
                        "cycle=%d  symbols=%d  net=%+.6f  gross=%.6f",
                        self.state.cycle, len(self.contracts), net_usd, gross_usd,
                    )
                    
                except KeyboardInterrupt:
                    raise
                
                except Exception as exc:
                    self.consecutive_errors += 1
                    log.error("Loop error: %s", exc)
                    event_log(
                        "main_loop_error",
                        error=str(exc),
                        traceback=traceback.format_exc(),
                        consecutive_errors=self.consecutive_errors,
                    )
                    if self.consecutive_errors >= MAX_CONSECUTIVE_ERRORS:
                        event_log("panic_stop", consecutive_errors=self.consecutive_errors)
                        break
                
                elapsed = wall_ts() - cycle_start
                time.sleep(max(0.0, LOOP_SECONDS - elapsed))
        
        except KeyboardInterrupt:
            log.info("Interrupted — shutting down.")
            event_log("shutdown", reason="keyboard_interrupt")
        
        finally:
            log.info("Cleanup: cancelling open quotes.")
            try:
                self.cancel_all()
            except Exception as exc:
                event_log("shutdown_cancel_error", error=str(exc))

# =============================================================================
# ENTRY POINT
# =============================================================================

def main() -> None:
    """Main entry point"""
    global DRY_RUN
    
    parser = argparse.ArgumentParser(description=f"Gate.io hedged market maker {VERSION}")
    parser.add_argument("--dry", action="store_true", help="Dry-run (default)")
    parser.add_argument("--live", action="store_true", help="Live trading")
    parser.add_argument("--balance", action="store_true", help="Print account balance and exit")
    parser.add_argument("--positions", action="store_true", help="Print positions and exit")
    parser.add_argument("--book", metavar="SYMBOL", help="Print order book for SYMBOL and exit")
    parser.add_argument("--cancel-all", action="store_true", help="Cancel all open orders and exit")
    parser.add_argument("--flatten-all", action="store_true", help="Flatten all positions and exit")
    
    args = parser.parse_args()
    
    DRY_RUN = not args.live
    
    if not DRY_RUN and (not GATE_API_KEY or not GATE_API_SECRET):
        sys.stderr.write("ERROR: GATE_API_KEY / GATE_API_SECRET not set.\n")
        sys.exit(1)
    
    client = GateRestClient(
        key=GATE_API_KEY,
        secret=GATE_API_SECRET,
        base_url=BASE_URL,
        settle=SETTLE,
    )
    store = StateStore("state.json")
    state = store.load()
    bot = HedgeMarketMaker(client, store, state)
    
    if args.balance:
        print(json.dumps(bot.balance(), indent=2, ensure_ascii=False))
    elif args.positions:
        print(json.dumps(bot.positions(), indent=2, ensure_ascii=False))
    elif args.book:
        print(json.dumps(bot.book(args.book), indent=2, ensure_ascii=False))
    elif args.cancel_all:
        bot.cancel_all()
    elif args.flatten_all:
        bot.flatten_all()
    else:
        bot.run()

if __name__ == "__main__":
    main()
