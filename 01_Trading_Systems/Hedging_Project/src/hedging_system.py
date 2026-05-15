#!/usr/bin/env python3
"""
Professional Hedging System
Places best bid/ask orders and manages profitable sells
"""

import os
import sys
import time
import logging
from datetime import datetime
from typing import Dict, List, Optional

from utils.gateio_client import GateIOClient
from utils.position_manager import PositionManager

class HedgingSystem:
    """Professional hedging system for Gate.io futures"""
    
    def __init__(self, symbol: str = "ENA_USDT", nominal_range: tuple = (0.01, 0.10)):
        self.symbol = symbol
        self.min_nominal, self.max_nominal = nominal_range
        self.target_nominal = (self.min_nominal + self.max_nominal) / 2
        
        # Initialize clients
        self.client = GateIOClient()
        self.position_manager = PositionManager(self.client, profit_threshold=0.002)
        
        # Setup logging
        self.logger = logging.getLogger('HedgingSystem')
        
        # State
        self.running = False
        self.cycle_count = 0
        self.active_orders = {}
        
        self.logger.info("🚀 Hedging System initialized")
        self.logger.info(f"📊 Symbol: {self.symbol}")
        self.logger.info(f"💰 Nominal range: ${self.min_nominal}-${self.max_nominal}")
    
    def place_best_bid_ask_orders(self) -> bool:
        """Place orders at best bid and ask prices"""
        # Get current market prices
        best_bid, best_ask = self.client.get_best_bid_ask(self.symbol)
        
        if best_bid is None or best_ask is None:
            self.logger.warning("❌ Cannot get market prices")
            return False
        
        # Calculate order sizes
        bid_size = self.client.calculate_nominal_size(best_bid, self.target_nominal)
        ask_size = self.client.calculate_nominal_size(best_ask, self.target_nominal)
        
        # Place buy order at best bid
        bid_result = self.client.place_order(
            symbol=self.symbol,
            side="BUY",
            size=bid_size,
            price=best_bid,
            order_type="limit",
            tif="ioc"
        )
        
        if bid_result.success:
            order_id = bid_result.data.get('id')
            self.active_orders[order_id] = {
                'side': 'BUY',
                'size': bid_size,
                'price': best_bid,
                'timestamp': time.time()
            }
            self.logger.info(f"✅ Buy order placed: {bid_size:.6f} @ ${best_bid:.6f}")
        else:
            self.logger.error(f"❌ Buy order failed: {bid_result.error}")
        
        # Place sell order at best ask
        ask_result = self.client.place_order(
            symbol=self.symbol,
            side="SELL", 
            size=ask_size,
            price=best_ask,
            order_type="limit",
            tif="ioc"
        )
        
        if ask_result.success:
            order_id = ask_result.data.get('id')
            self.active_orders[order_id] = {
                'side': 'SELL',
                'size': ask_size,
                'price': best_ask,
                'timestamp': time.time()
            }
            self.logger.info(f"✅ Sell order placed: {ask_size:.6f} @ ${best_ask:.6f}")
        else:
            self.logger.error(f"❌ Sell order failed: {ask_result.error}")
        
        return bid_result.success or ask_result.success
    
    def check_and_take_profits(self) -> int:
        """Check for profitable positions and take profits"""
        profitable_positions = self.position_manager.get_profitable_positions()
        profits_taken = 0
        
        for position in profitable_positions:
            if self.position_manager.should_sell_position(position):
                success = self.position_manager.close_position_for_profit(position)
                if success:
                    profits_taken += 1
        
        return profits_taken
    
    def cleanup_old_orders(self):
        """Remove old order records"""
        current_time = time.time()
        max_age = 60  # Keep records for 1 minute
        
        old_orders = [
            order_id for order_id, order in self.active_orders.items()
            if current_time - order['timestamp'] > max_age
        ]
        
        for order_id in old_orders:
            del self.active_orders[order_id]
        
        if old_orders:
            self.logger.debug(f"🗑️ Cleaned up {len(old_orders)} old order records")
    
    def get_market_status(self) -> Dict:
        """Get current market status"""
        best_bid, best_ask = self.client.get_best_bid_ask(self.symbol)
        positions = self.position_manager.get_positions()
        
        return {
            'symbol': self.symbol,
            'best_bid': best_bid,
            'best_ask': best_ask,
            'spread': (best_ask - best_bid) / best_bid if best_bid and best_ask else None,
            'position_count': len(positions),
            'active_orders': len(self.active_orders)
        }
    
    def run_hedging_cycle(self):
        """Run one complete hedging cycle"""
        self.cycle_count += 1
        cycle_start = time.time()
        
        self.logger.info(f"🔄 Cycle {self.cycle_count} started")
        
        # Get market status
        status = self.get_market_status()
        self.logger.info(f"📊 {status['symbol']}: Bid ${status['best_bid']:.6f} | Ask ${status['best_ask']:.6f}")
        self.logger.info(f"💼 Positions: {status['position_count']} | Active Orders: {status['active_orders']}")
        
        # Place best bid/ask orders
        self.logger.info("🎯 Placing best bid/ask orders...")
        orders_placed = self.place_best_bid_ask_orders()
        
        # Check for profit opportunities
        self.logger.info("💰 Checking profit opportunities...")
        profits_taken = self.check_and_take_profits()
        
        # Cleanup
        self.cleanup_old_orders()
        
        # Cycle summary
        elapsed = time.time() - cycle_start
        self.logger.info(f"✅ Cycle {self.cycle_count} completed in {elapsed:.2f}s")
        self.logger.info(f"📈 Orders placed: {orders_placed} | Profits taken: {profits_taken}")
        
        # Wait for next cycle
        sleep_time = max(0, 5 - elapsed)  # 5 second cycles
        if sleep_time > 0:
            self.logger.info(f"⏳ Waiting {sleep_time:.2f}s for next cycle...")
            time.sleep(sleep_time)
    
    def run(self):
        """Main trading loop"""
        self.logger.info("🚀 Starting Professional Hedging System")
        self.logger.info("⚠️  LIVE TRADING MODE - Real orders will be placed!")
        
        try:
            self.running = True
            while self.running:
                self.run_hedging_cycle()
                
        except KeyboardInterrupt:
            self.logger.info("🛑 Hedging system stopped by user")
        except Exception as e:
            self.logger.error(f"❌ Fatal error: {e}")
        finally:
            self.logger.info("✅ Hedging system shutdown complete")

def main():
    """Main function for testing"""
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s %(name)s %(levelname)s %(message)s'
    )
    
    # Check API keys
    if not os.getenv("GATE_API_KEY") or not os.getenv("GATE_API_SECRET"):
        print("❌ Missing GATE_API_KEY or GATE_API_SECRET")
        print("Set environment variables and try again")
        return
    
    # Create and run hedging system
    hedger = HedgingSystem(
        symbol="ENA_USDT",
        nominal_range=(0.01, 0.10)  # 1-10 cent nominal value
    )
    
    hedger.run()

if __name__ == "__main__":
    main()
