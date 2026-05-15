#!/usr/bin/env python3
"""
Professional Hedging Market Maker
Places best bid/ask orders and executes profitable sells
"""

import os
import sys
import yaml
import time
import json
import requests
import hmac
import hashlib
import logging
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

@dataclass
class Order:
    id: str
    symbol: str
    side: str
    size: float
    price: float
    timestamp: float

@dataclass
class Position:
    symbol: str
    size: float
    entry_price: float
    unrealized_pnl: float

class HedgingMarketMaker:
    """Professional hedging market maker for Gate.io futures"""
    
    def __init__(self, config_path: str = None):
        # Load configuration
        if config_path is None:
            config_path = os.path.join(os.path.dirname(__file__), '..', 'config', 'hedging_config.yaml')
        
        with open(config_path, 'r') as f:
            self.config = yaml.safe_load(f)
        
        # Setup logging
        logging.basicConfig(
            level=getattr(logging, self.config['monitoring']['log_level']),
            format='%(asctime)s %(levelname)s %(message)s'
        )
        self.logger = logging.getLogger('HedgingMM')
        
        # API configuration
        self.api_key = os.getenv("GATE_API_KEY", "")
        self.api_secret = os.getenv("GATE_API_SECRET", "")
        self.base_url = self.config['api']['base_url']
        self.settle = self.config['api']['settle']
        
        # Trading parameters
        self.symbol = self.config['trading']['symbol']
        self.min_nominal = self.config['trading']['nominal_value_range']['min']
        self.max_nominal = self.config['trading']['nominal_value_range']['max']
        self.target_spread = self.config['trading']['target_spread']
        
        # State
        self.running = False
        self.orders = []
        self.positions = []
        self.cycle_count = 0
        
        self.logger.info("🚀 Hedging Market Maker initialized")
        self.logger.info(f"📊 Symbol: {self.symbol}")
        self.logger.info(f"💰 Nominal range: ${self.min_nominal}-${self.max_nominal}")
    
    def _sign_request(self, method: str, path: str, query_string: str, payload: str) -> Dict[str, str]:
        """Generate Gate.io API signature"""
        ts = str(int(time.time()))
        payload_hash = hashlib.sha512(payload.encode('utf-8')).hexdigest()
        sign_str = f"{method.upper()}\n{path}\n{query_string}\n{payload_hash}\n{ts}"
        sign = hmac.new(
            self.api_secret.encode("utf-8"),
            sign_str.encode("utf-8"),
            digestmod=hashlib.sha512,
        ).hexdigest()
        
        return {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "KEY": self.api_key,
            "Timestamp": ts,
            "SIGN": sign,
        }
    
    def _make_request(self, method: str, path: str, payload: str = "", private: bool = False) -> Optional[Dict]:
        """Make API request"""
        headers = self._sign_request(method, path, "", payload) if private else {
            "Accept": "application/json",
            "Content-Type": "application/json"
        }
        
        try:
            url = f"{self.base_url}{path}"
            response = requests.request(method, url, headers=headers, data=payload if payload else None, timeout=10)
            
            if response.status_code == 200:
                return response.json()
            else:
                self.logger.error(f"API Error {response.status_code}: {response.text}")
                return None
                
        except Exception as e:
            self.logger.error(f"Request exception: {e}")
            return None
    
    def get_market_price(self) -> Tuple[float, float]:
        """Get best bid and ask prices"""
        data = self._make_request(
            "GET", 
            f"/futures/{self.settle}/order_book?contract={self.symbol}&limit=1"
        )
        
        if data and data.get('asks') and data.get('bids'):
            best_bid = float(data['bids'][0]['p'])
            best_ask = float(data['asks'][0]['p'])
            return best_bid, best_ask
        
        return None, None
    
    def get_positions(self) -> List[Position]:
        """Get current positions"""
        data = self._make_request("GET", f"/futures/{self.settle}/positions", "", private=True)
        
        positions = []
        if data:
            for pos in data:
                if float(pos['size']) != 0 and pos['contract'] == self.symbol:
                    positions.append(Position(
                        symbol=pos['contract'],
                        size=float(pos['size']),
                        entry_price=float(pos['entry_price']),
                        unrealized_pnl=float(pos['unrealised_pnl'])
                    ))
        
        return positions
    
    def calculate_order_size(self, price: float) -> float:
        """Calculate order size for target nominal value"""
        target_nominal = (self.min_nominal + self.max_nominal) / 2  # Use middle of range
        size = target_nominal / price
        
        # Ensure minimum order size
        min_size = 0.001
        return max(size, min_size)
    
    def place_order(self, side: str, size: float, price: float) -> Optional[str]:
        """Place limit order"""
        order_data = {
            "settle": self.settle,
            "contract": self.symbol,
            "size": str(size),
            "price": str(price),
            "type": "limit",
            "tif": self.config['execution']['time_in_force']
        }
        
        payload = json.dumps(order_data, separators=(",", ":"))
        result = self._make_request("POST", f"/futures/{self.settle}/orders", payload, private=True)
        
        if result:
            order_id = result.get('id')
            self.logger.info(f"✅ Order placed: {side} {size:.6f} @ {price:.6f} (ID: {order_id})")
            return order_id
        else:
            self.logger.error(f"❌ Failed to place {side} order")
            return None
    
    def cancel_order(self, order_id: str) -> bool:
        """Cancel order"""
        result = self._make_request("DELETE", f"/futures/{self.settle}/orders/{order_id}", "", private=True)
        return result is not None
    
    def place_best_bid_ask(self):
        """Place orders at best bid and ask"""
        best_bid, best_ask = self.get_market_price()
        
        if best_bid is None or best_ask is None:
            self.logger.warning("❌ Cannot get market prices")
            return
        
        # Calculate order sizes
        bid_size = self.calculate_order_size(best_bid)
        ask_size = self.calculate_order_size(best_ask)
        
        # Place buy order at best bid
        bid_order_id = self.place_order("BUY", bid_size, best_bid)
        if bid_order_id:
            self.orders.append(Order(bid_order_id, self.symbol, "BUY", bid_size, best_bid, time.time()))
        
        # Place sell order at best ask
        ask_order_id = self.place_order("SELL", ask_size, best_ask)
        if ask_order_id:
            self.orders.append(Order(ask_order_id, self.symbol, "SELL", ask_size, best_ask, time.time()))
    
    def check_profit_opportunities(self):
        """Check for profitable selling opportunities"""
        positions = self.get_positions()
        best_bid, best_ask = self.get_market_price()
        
        if not positions or best_bid is None:
            return
        
        for position in positions:
            if position.size > 0:  # Long position
                profit_pct = (best_bid - position.entry_price) / position.entry_price
                
                if profit_pct >= self.config['hedging']['profit_threshold']:
                    # Sell for profit
                    sell_size = min(position.size, self.calculate_order_size(best_bid))
                    order_id = self.place_order("SELL", sell_size, best_bid)
                    
                    if order_id:
                        self.logger.info(f"💰 Profit sell: {sell_size:.6f} @ {best_bid:.6f} (Profit: {profit_pct:.2%})")
    
    def cleanup_orders(self):
        """Cancel old orders"""
        current_time = time.time()
        max_age = self.config['trading']['order_refresh_interval']
        
        orders_to_cancel = []
        for order in self.orders:
            if current_time - order.timestamp > max_age:
                orders_to_cancel.append(order)
        
        for order in orders_to_cancel:
            if self.cancel_order(order.id):
                self.logger.info(f"🗑️ Cancelled old order: {order.id}")
                self.orders.remove(order)
    
    def run_hedging_cycle(self):
        """Run one hedging cycle"""
        self.cycle_count += 1
        cycle_start = time.time()
        
        self.logger.info(f"🔄 Cycle {self.cycle_count} started")
        
        # Get current state
        positions = self.get_positions()
        best_bid, best_ask = self.get_market_price()
        
        if best_bid and best_ask:
            self.logger.info(f"📊 {self.symbol}: Bid ${best_bid:.6f} | Ask ${best_ask:.6f}")
            self.logger.info(f"💼 Positions: {len(positions)}")
        
        # Place best bid/ask orders
        self.place_best_bid_ask()
        
        # Check profit opportunities
        if self.config['hedging']['auto_sell_profit']:
            self.check_profit_opportunities()
        
        # Clean up old orders
        self.cleanup_orders()
        
        # Wait for next cycle
        elapsed = time.time() - cycle_start
        sleep_time = max(0, self.config['hedging']['rebalance_interval'] - elapsed)
        
        self.logger.info(f"⏳ Cycle completed in {elapsed:.2f}s, waiting {sleep_time:.2f}s")
        time.sleep(sleep_time)
    
    def run(self):
        """Main trading loop"""
        self.logger.info("🚀 Starting Hedging Market Maker")
        self.running = True
        
        try:
            while self.running:
                self.run_hedging_cycle()
                
        except KeyboardInterrupt:
            self.logger.info("🛑 Stopped by user")
        except Exception as e:
            self.logger.error(f"❌ Fatal error: {e}")
        finally:
            # Cancel all orders
            for order in self.orders:
                self.cancel_order(order.id)
            self.logger.info("✅ All orders cancelled")

def main():
    """Main function"""
    # Check environment variables
    if not os.getenv("GATE_API_KEY") or not os.getenv("GATE_API_SECRET"):
        print("❌ Missing GATE_API_KEY or GATE_API_SECRET")
        print("Run: export GATE_API_KEY='your-key' && export GATE_API_SECRET='your-secret'")
        return
    
    # Create and run hedging market maker
    hedger = HedgingMarketMaker()
    hedger.run()

if __name__ == "__main__":
    main()
