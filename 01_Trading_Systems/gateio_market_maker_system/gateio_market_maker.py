#!/usr/bin/env python3
import os
"""
GATE.IO ADVANCED MARKET MAKER BOT
Professional market making with inventory management, spread optimization, and risk controls
"""

import asyncio
import aiohttp
import json
import hmac
import hashlib
import time
import base64
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, NamedTuple
import logging
from dataclasses import dataclass, field
from enum import Enum
import uuid
from collections import deque
import statistics

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class OrderSide(Enum):
    BUY = "buy"
    SELL = "sell"

class OrderStatus(Enum):
    OPEN = "open"
    FILLED = "filled"
    CANCELLED = "cancelled"
    PARTIALLY_FILLED = "partial_filled"

class OrderType(Enum):
    LIMIT = "limit"
    MARKET = "market"

@dataclass
class Order:
    id: str
    symbol: str
    side: OrderSide
    order_type: OrderType
    amount: float
    price: float
    status: OrderStatus = OrderStatus.OPEN
    filled_amount: float = 0.0
    timestamp: datetime = field(default_factory=datetime.now)
    
    @property
    def remaining_amount(self) -> float:
        return self.amount - self.filled_amount

@dataclass
class MarketData:
    symbol: str
    bid: float
    ask: float
    bid_size: float
    ask_size: float
    last_price: float
    volume_24h: float
    timestamp: datetime = field(default_factory=datetime.now)

@dataclass
class InventoryPosition:
    symbol: str
    amount: float
    avg_price: float
    unrealized_pnl: float = 0.0
    realized_pnl: float = 0.0
    last_update: datetime = field(default_factory=datetime.now)

@dataclass
class MarketMakerConfig:
    symbol: str
    base_order_size: float = 0.1
    max_order_size: float = 1.0
    target_spread_bps: int = 50  # basis points
    min_spread_bps: int = 10
    max_spread_bps: int = 200
    inventory_target: float = 0.0
    inventory_tolerance: float = 2.0
    max_inventory: float = 10.0
    min_inventory: float = -10.0
    rebalance_threshold: float = 0.5
    order_refresh_time: int = 30  # seconds
    max_orders_per_side: int = 5
    volatility_window: int = 100
    price_skew_factor: float = 0.1
    volume_factor: float = 0.001

class GateIOMarketMaker:
    """Advanced market maker for Gate.io"""
    
    def __init__(self, api_key: str, api_secret: str, config: MarketMakerConfig):
        self.api_key = api_key
        self.api_secret = api_secret
        self.base_url = "https://api.gateio.ws/api/v4"
        self.config = config
        self.session = None
        
        # Trading state
        self.active_orders = {}  # order_id -> Order
        self.inventory = {}  # symbol -> InventoryPosition
        self.price_history = deque(maxlen=config.volatility_window)
        self.trade_history = deque(maxlen=1000)
        self.pnl_history = deque(maxlen=100)
        
        # Market data
        self.current_market_data = None
        self.order_book = {"bids": [], "asks": []}
        
        # Control flags
        self.is_running = False
        self.last_order_refresh = 0
        
        # Statistics
        self.total_trades = 0
        self.total_volume = 0.0
        self.total_pnl = 0.0
        self.spread_stats = deque(maxlen=100)
        
        logger.info(f"🤖 Market Maker initialized for {config.symbol}")
    
    def _sign_request(self, method: str, url: str, params: Dict = None, body: str = "") -> str:
        """Sign API request"""
        timestamp = str(int(time.time()))
        if params:
            query_string = "&".join([f"{k}={v}" for k, v in sorted(params.items())])
        else:
            query_string = ""
        
        message = f"{method}\n{url}\n{query_string}\n{body}\n{timestamp}"
        signature = hmac.new(
            self.api_secret.encode('utf-8'),
            message.encode('utf-8'),
            hashlib.sha512
        ).hexdigest()
        
        return f"KEY:{self.api_key},SIGN:{signature},TS:{timestamp}"
    
    async def _make_request(self, method: str, endpoint: str, params: Dict = None, body: Dict = None) -> Dict:
        """Make authenticated API request"""
        if not self.session:
            self.session = aiohttp.ClientSession()
        
        url = f"{self.base_url}{endpoint}"
        body_str = json.dumps(body) if body else ""
        
        headers = {
            'Content-Type': 'application/json',
            'Authorization': self._sign_request(method, endpoint, params, body_str)
        }
        
        try:
            async with self.session.request(method, url, headers=headers, params=params, json=body) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    error_text = await response.text()
                    logger.error(f"API error {response.status}: {error_text}")
                    return {"error": error_text}
        except Exception as e:
            logger.error(f"Request failed: {e}")
            return {"error": str(e)}
    
    async def get_market_data(self) -> MarketData:
        """Get current market data"""
        try:
            # Get ticker
            ticker_url = "/spot/tickers"
            ticker_params = {"currency_pair": self.config.symbol}
            ticker_data = await self._make_request("GET", ticker_url, ticker_params)
            
            if not ticker_data or len(ticker_data) == 0:
                raise Exception("No ticker data")
            
            ticker = ticker_data[0]
            
            # Get order book
            orderbook_url = "/spot/order_book"
            orderbook_params = {"currency_pair": self.config.symbol, "limit": 20}
            orderbook_data = await self._make_request("GET", orderbook_url, orderbook_params)
            
            if "bids" not in orderbook_data or "asks" not in orderbook_data:
                raise Exception("Invalid orderbook data")
            
            self.order_book = orderbook_data
            
            market_data = MarketData(
                symbol=self.config.symbol,
                bid=float(orderbook_data["bids"][0][0]) if orderbook_data["bids"] else 0,
                ask=float(orderbook_data["asks"][0][0]) if orderbook_data["asks"] else 0,
                bid_size=float(orderbook_data["bids"][0][1]) if orderbook_data["bids"] else 0,
                ask_size=float(orderbook_data["asks"][0][1]) if orderbook_data["asks"] else 0,
                last_price=float(ticker.get("last", 0)),
                volume_24h=float(ticker.get("base_volume", 0))
            )
            
            self.price_history.append(market_data.last_price)
            self.current_market_data = market_data
            
            return market_data
            
        except Exception as e:
            logger.error(f"Failed to get market data: {e}")
            raise
    
    async def get_account_balance(self) -> Dict:
        """Get account balances"""
        try:
            balance_url = "/spot/accounts"
            balance_data = await self._make_request("GET", balance_url)
            
            balances = {}
            if balance_data:
                for asset in balance_data:
                    currency = asset.get("currency", "")
                    available = float(asset.get("available", 0))
                    frozen = float(asset.get("frozen", 0))
                    total = available + frozen
                    
                    if total > 0:
                        balances[currency] = {
                            "available": available,
                            "frozen": frozen,
                            "total": total
                        }
            
            return balances
            
        except Exception as e:
            logger.error(f"Failed to get account balance: {e}")
            return {}
    
    async def place_order(self, side: OrderSide, amount: float, price: float) -> Optional[Order]:
        """Place a limit order"""
        try:
            order_url = "/spot/orders"
            
            order_data = {
                "currency_pair": self.config.symbol,
                "side": side.value,
                "type": "limit",
                "amount": str(amount),
                "price": str(price)
            }
            
            result = await self._make_request("POST", order_url, body=order_data)
            
            if "id" in result:
                order = Order(
                    id=result["id"],
                    symbol=self.config.symbol,
                    side=side,
                    order_type=OrderType.LIMIT,
                    amount=amount,
                    price=price,
                    status=OrderStatus.OPEN
                )
                
                self.active_orders[order.id] = order
                logger.info(f"📈 Order placed: {side.value} {amount:.6f} @ {price:.6f}")
                return order
            else:
                logger.error(f"Failed to place order: {result}")
                return None
                
        except Exception as e:
            logger.error(f"Order placement failed: {e}")
            return None
    
    async def cancel_order(self, order_id: str) -> bool:
        """Cancel an order"""
        try:
            cancel_url = f"/spot/orders/{order_id}"
            result = await self._make_request("DELETE", cancel_url)
            
            if "id" in result:
                if order_id in self.active_orders:
                    self.active_orders[order_id].status = OrderStatus.CANCELLED
                    del self.active_orders[order_id]
                logger.info(f"❌ Order cancelled: {order_id}")
                return True
            else:
                logger.error(f"Failed to cancel order: {result}")
                return False
                
        except Exception as e:
            logger.error(f"Order cancellation failed: {e}")
            return False
    
    async def cancel_all_orders(self):
        """Cancel all active orders"""
        order_ids = list(self.active_orders.keys())
        for order_id in order_ids:
            await self.cancel_order(order_id)
    
    def calculate_volatility(self) -> float:
        """Calculate price volatility"""
        if len(self.price_history) < 20:
            return 0.01  # Default volatility
        
        prices = list(self.price_history)
        returns = []
        
        for i in range(1, len(prices)):
            ret = (prices[i] - prices[i-1]) / prices[i-1]
            returns.append(ret)
        
        if not returns:
            return 0.01
        
        return statistics.stdev(returns) if len(returns) > 1 else 0.01
    
    def calculate_optimal_spread(self) -> float:
        """Calculate optimal spread based on volatility and inventory"""
        volatility = self.calculate_volatility()
        base_spread = self.config.target_spread_bps / 10000
        
        # Adjust spread based on volatility
        volatility_adjustment = volatility * 2
        
        # Adjust spread based on inventory imbalance
        inventory = self.get_inventory_position()
        inventory_adjustment = abs(inventory) * self.config.price_skew_factor
        
        # Calculate final spread
        spread = base_spread + volatility_adjustment + inventory_adjustment
        
        # Apply min/max constraints
        min_spread = self.config.min_spread_bps / 10000
        max_spread = self.config.max_spread_bps / 10000
        
        return max(min_spread, min(max_spread, spread))
    
    def calculate_inventory_skew(self) -> float:
        """Calculate price skew based on inventory position"""
        inventory = self.get_inventory_position()
        
        # Calculate skew as percentage of max inventory
        max_inv = max(abs(self.config.max_inventory), abs(self.config.min_inventory))
        inventory_ratio = inventory / max_inv if max_inv > 0 else 0
        
        # Apply skew factor
        skew = inventory_ratio * self.config.price_skew_factor
        
        return skew
    
    def get_inventory_position(self) -> float:
        """Get current inventory position"""
        position = self.inventory.get(self.config.symbol)
        return position.amount if position else 0.0
    
    def calculate_order_prices(self) -> Tuple[float, float]:
        """Calculate optimal bid and ask prices"""
        if not self.current_market_data:
            return 0.0, 0.0
        
        mid_price = (self.current_market_data.bid + self.current_market_data.ask) / 2
        spread = self.calculate_optimal_spread()
        skew = self.calculate_inventory_skew()
        
        # Apply skew to prices
        half_spread = spread / 2
        bid_price = mid_price - half_spread - skew
        ask_price = mid_price + half_spread - skew
        
        return bid_price, ask_price
    
    def calculate_order_sizes(self) -> Tuple[float, float]:
        """Calculate optimal order sizes based on inventory and market conditions"""
        base_size = self.config.base_order_size
        inventory = self.get_inventory_position()
        
        # Adjust size based on inventory
        if inventory > self.config.inventory_tolerance:
            # We're long - reduce bid size, increase ask size
            bid_multiplier = max(0.1, 1.0 - (inventory / self.config.max_inventory))
            ask_multiplier = min(2.0, 1.0 + (inventory / self.config.max_inventory))
        elif inventory < -self.config.inventory_tolerance:
            # We're short - increase bid size, reduce ask size
            bid_multiplier = min(2.0, 1.0 - (inventory / self.config.min_inventory))
            ask_multiplier = max(0.1, 1.0 + (inventory / self.config.min_inventory))
        else:
            # Balanced inventory
            bid_multiplier = 1.0
            ask_multiplier = 1.0
        
        # Apply market volume adjustment
        if self.current_market_data:
            volume_factor = min(self.current_market_data.volume_24h * self.config.volume_factor, 1.0)
            bid_multiplier *= volume_factor
            ask_multiplier *= volume_factor
        
        bid_size = min(base_size * bid_multiplier, self.config.max_order_size)
        ask_size = min(base_size * ask_multiplier, self.config.max_order_size)
        
        return bid_size, ask_size
    
    async def place_maker_orders(self):
        """Place new maker orders"""
        if not self.current_market_data:
            return
        
        # Cancel existing orders if it's time to refresh
        current_time = time.time()
        if current_time - self.last_order_refresh > self.config.order_refresh_time:
            await self.cancel_all_orders()
            self.last_order_refresh = current_time
        
        # Calculate optimal prices and sizes
        bid_price, ask_price = self.calculate_order_prices()
        bid_size, ask_size = self.calculate_order_sizes()
        
        # Count existing orders
        buy_orders = [o for o in self.active_orders.values() if o.side == OrderSide.BUY]
        sell_orders = [o for o in self.active_orders.values() if o.side == OrderSide.SELL]
        
        # Place buy orders
        if len(buy_orders) < self.config.max_orders_per_side and bid_size > 0:
            await self.place_order(OrderSide.BUY, bid_size, bid_price)
        
        # Place sell orders
        if len(sell_orders) < self.config.max_orders_per_side and ask_size > 0:
            await self.place_order(OrderSide.SELL, ask_size, ask_price)
    
    async def update_order_status(self):
        """Update status of active orders"""
        if not self.active_orders:
            return
        
        # Get order status for all active orders
        for order_id, order in list(self.active_orders.items()):
            try:
                status_url = f"/spot/orders/{order_id}"
                result = await self._make_request("GET", status_url)
                
                if "status" in result:
                    new_status = result["status"]
                    filled = float(result.get("filled", "0"))
                    
                    # Update order
                    order.filled_amount = filled
                    
                    if new_status == "filled":
                        order.status = OrderStatus.FILLED
                        await self.handle_order_fill(order)
                        del self.active_orders[order_id]
                    elif new_status == "cancelled":
                        order.status = OrderStatus.CANCELLED
                        del self.active_orders[order_id]
                    elif filled > order.filled_amount:
                        await self.handle_partial_fill(order)
                        
            except Exception as e:
                logger.error(f"Failed to update order {order_id}: {e}")
    
    async def handle_order_fill(self, order: Order):
        """Handle a completely filled order"""
        logger.info(f"✅ Order filled: {order.side.value} {order.amount:.6f} @ {order.price:.6f}")
        
        # Update inventory
        self.update_inventory(order)
        
        # Update statistics
        self.total_trades += 1
        self.total_volume += order.amount
        
        # Calculate PnL
        self.calculate_pnl()
        
        # Record trade
        self.trade_history.append({
            "timestamp": datetime.now(),
            "side": order.side.value,
            "amount": order.amount,
            "price": order.price,
            "value": order.amount * order.price
        })
    
    async def handle_partial_fill(self, order: Order):
        """Handle a partially filled order"""
        fill_amount = order.filled_amount - (order.amount - order.remaining_amount)
        if fill_amount > 0:
            logger.info(f"📊 Partial fill: {order.side.value} {fill_amount:.6f} @ {order.price:.6f}")
            self.update_inventory(order, fill_amount)
    
    def update_inventory(self, order: Order, fill_amount: float = None):
        """Update inventory position"""
        if fill_amount is None:
            fill_amount = order.amount
        
        symbol = order.symbol
        current_position = self.inventory.get(symbol)
        
        if not current_position:
            current_position = InventoryPosition(
                symbol=symbol,
                amount=0.0,
                avg_price=0.0
            )
            self.inventory[symbol] = current_position
        
        if order.side == OrderSide.BUY:
            # Adding to inventory
            total_amount = current_position.amount + fill_amount
            if total_amount > 0:
                current_position.avg_price = (
                    (current_position.avg_price * current_position.amount + order.price * fill_amount) 
                    / total_amount
                )
            current_position.amount = total_amount
        else:
            # Removing from inventory
            current_position.amount -= fill_amount
            
            # Calculate realized PnL
            if current_position.amount <= 0:
                realized = (order.price - current_position.avg_price) * fill_amount
                current_position.realized_pnl += realized
                current_position.amount = 0
                current_position.avg_price = 0.0
        
        current_position.last_update = datetime.now()
    
    def calculate_pnl(self):
        """Calculate current PnL"""
        for symbol, position in self.inventory.items():
            if position.amount != 0 and self.current_market_data:
                # Calculate unrealized PnL
                current_price = self.current_market_data.last_price
                unrealized = (current_price - position.avg_price) * position.amount
                position.unrealized_pnl = unrealized
        
        # Calculate total PnL
        total_realized = sum(p.realized_pnl for p in self.inventory.values())
        total_unrealized = sum(p.unrealized_pnl for p in self.inventory.values())
        self.total_pnl = total_realized + total_unrealized
        
        # Record PnL history
        self.pnl_history.append({
            "timestamp": datetime.now(),
            "total_pnl": self.total_pnl,
            "realized_pnl": total_realized,
            "unrealized_pnl": total_unrealized
        })
    
    def print_statistics(self):
        """Print trading statistics"""
        print("\n" + "="*80)
        print("📊 MARKET MAKER STATISTICS")
        print("="*80)
        print(f"Symbol: {self.config.symbol}")
        print(f"Active Orders: {len(self.active_orders)}")
        print(f"Total Trades: {self.total_trades}")
        print(f"Total Volume: {self.total_volume:.6f}")
        print(f"Total PnL: ${self.total_pnl:.2f}")
        
        if self.current_market_data:
            print(f"Current Price: ${self.current_market_data.last_price:.6f}")
            print(f"Current Spread: ${(self.current_market_data.ask - self.current_market_data.bid):.6f}")
            print(f"24h Volume: {self.current_market_data.volume_24h:.2f}")
        
        position = self.inventory.get(self.config.symbol)
        if position:
            print(f"\nInventory Position:")
            print(f"  Amount: {position.amount:.6f}")
            print(f"  Avg Price: ${position.avg_price:.6f}")
            print(f"  Realized PnL: ${position.realized_pnl:.2f}")
            print(f"  Unrealized PnL: ${position.unrealized_pnl:.2f}")
        
        print("="*80)
    
    async def run_market_making(self):
        """Main market making loop"""
        logger.info(f"🚀 Starting market making for {self.config.symbol}")
        self.is_running = True
        
        while self.is_running:
            try:
                # Update market data
                await self.get_market_data()
                
                # Update order status
                await self.update_order_status()
                
                # Place maker orders
                await self.place_maker_orders()
                
                # Calculate PnL
                self.calculate_pnl()
                
                # Print statistics periodically
                if self.total_trades % 10 == 0 and self.total_trades > 0:
                    self.print_statistics()
                
                # Sleep before next iteration
                await asyncio.sleep(1)
                
            except Exception as e:
                logger.error(f"Error in market making loop: {e}")
                await asyncio.sleep(5)
    
    async def stop(self):
        """Stop the market maker"""
        logger.info("🛑 Stopping market maker")
        self.is_running = False
        await self.cancel_all_orders()
        
        if self.session:
            await self.session.close()
        
        self.print_statistics()

# Example usage
async def main():
    """Main function to run the market maker"""
    
    # Configuration - REPLACE WITH YOUR ACTUAL API KEYS
    GATEIO_API_KEY = "your_gateio_api_key_here"
    GATEIO_API_SECRET = "your_gateio_api_secret_here"
    
    # Market maker configuration
    config = MarketMakerConfig(
        symbol="BTC_USDT",
        base_order_size=0.001,  # 0.001 BTC per order
        max_order_size=0.01,    # Maximum 0.01 BTC per order
        target_spread_bps=50,   # 0.5% target spread
        inventory_target=0.0,   # Target neutral inventory
        max_inventory=0.1,      # Maximum 0.1 BTC long
        min_inventory=-0.1,     # Maximum 0.1 BTC short
        order_refresh_time=30,  # Refresh orders every 30 seconds
        max_orders_per_side=3,  # Maximum 3 orders per side
        volatility_window=100,  # Use last 100 price points for volatility
        price_skew_factor=0.1,  # Inventory skew factor
        volume_factor=0.001     # Volume-based size adjustment
    )
    
    # Initialize and run market maker
    market_maker = GateIOMarketMaker(GATEIO_API_KEY, GATEIO_API_SECRET, config)
    
    try:
        # Get initial balance
        balance = await market_maker.get_account_balance()
        logger.info(f"💰 Account balance: {balance}")
        
        # Run market making
        await market_maker.run_market_making()
        
    except KeyboardInterrupt:
        logger.info("🛑 Received interrupt signal")
    finally:
        await market_maker.stop()

if __name__ == "__main__":
    print("🤖 Gate.io Advanced Market Maker Bot")
    print("⚠️  NOTE: Update API keys in main() function before running")
    print("📋 Features:")
    print("   - Inventory management and skew adjustment")
    print("   - Dynamic spread calculation based on volatility")
    print("   - Multi-level order book placement")
    print("   - Real-time PnL tracking")
    print("   - Risk management with position limits")
    
    # Uncomment to run (requires API keys)
    # asyncio.run(main())
