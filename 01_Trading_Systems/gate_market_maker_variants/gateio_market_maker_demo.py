#!/usr/bin/env python3
import os
"""
GATE.IO MARKET MAKER DEMO
Demonstrates market making functionality without live API calls
"""

import asyncio
import random
import time
from datetime import datetime, timedelta
from gateio_market_maker import (
    GateIOMarketMaker, MarketMakerConfig, Order, OrderSide, OrderStatus, 
    MarketData, InventoryPosition, OrderType
)

class MockMarketMaker(GateIOMarketMaker):
    """Mock market maker for demonstration"""
    
    def __init__(self, api_key: str, api_secret: str, config: MarketMakerConfig):
        # Initialize without API session
        self.api_key = api_key
        self.api_secret = api_secret
        self.base_url = "https://api.gateio.ws/api/v4"
        self.config = config
        self.session = None
        
        # Initialize trading state
        self.active_orders = {}
        self.inventory = {}
        self.price_history = []
        self.trade_history = []
        self.pnl_history = []
        
        # Mock market data
        self.mock_price = 50000.0  # Starting BTC price
        self.order_book = {"bids": [], "asks": []}
        self.current_market_data = None
        
        # Control flags
        self.is_running = False
        self.last_order_refresh = 0
        
        # Statistics
        self.total_trades = 0
        self.total_volume = 0.0
        self.total_pnl = 0.0
        self.spread_stats = []
        
        print(f"🤖 Mock Market Maker initialized for {config.symbol}")
    
    async def get_market_data(self) -> MarketData:
        """Generate mock market data"""
        # Simulate price movement
        price_change = random.uniform(-0.001, 0.001)  # ±0.1% movement
        self.mock_price *= (1 + price_change)
        
        # Generate order book
        spread = self.mock_price * 0.0005  # 0.05% spread
        bid_price = self.mock_price - spread / 2
        ask_price = self.mock_price + spread / 2
        
        # Mock order book depth
        bids = []
        asks = []
        for i in range(5):
            bid_price_level = bid_price - i * spread * 0.5
            ask_price_level = ask_price + i * spread * 0.5
            bid_size = random.uniform(0.1, 2.0)
            ask_size = random.uniform(0.1, 2.0)
            
            bids.append([bid_price_level, bid_size])
            asks.append([ask_price_level, ask_size])
        
        self.order_book = {"bids": bids, "asks": asks}
        
        market_data = MarketData(
            symbol=self.config.symbol,
            bid=bids[0][0] if bids else self.mock_price,
            ask=asks[0][0] if asks else self.mock_price,
            bid_size=bids[0][1] if bids else 1.0,
            ask_size=asks[0][1] if asks else 1.0,
            last_price=self.mock_price,
            volume_24h=random.uniform(1000, 5000)
        )
        
        self.price_history.append(market_data.last_price)
        if len(self.price_history) > self.config.volatility_window:
            self.price_history.pop(0)
        
        self.current_market_data = market_data
        
        print(f"📊 Mock Market Data: {market_data.symbol} @ ${market_data.last_price:.2f} (Spread: ${(market_data.ask - market_data.bid):.2f})")
        return market_data
    
    async def get_account_balance(self) -> dict:
        """Return mock balance"""
        return {
            "BTC": {"available": 1.0, "frozen": 0.0, "total": 1.0},
            "USDT": {"available": 50000.0, "frozen": 0.0, "total": 50000.0}
        }
    
    async def place_order(self, side: OrderSide, amount: float, price: float) -> Order:
        """Mock order placement"""
        order_id = f"mock_order_{int(time.time() * 1000)}"
        
        order = Order(
            id=order_id,
            symbol=self.config.symbol,
            side=side,
            order_type=OrderType.LIMIT,
            amount=amount,
            price=price,
            status=OrderStatus.OPEN
        )
        
        self.active_orders[order_id] = order
        print(f"📈 Mock Order Placed: {side.value.upper()} {amount:.6f} @ ${price:.2f}")
        
        # Simulate random fills
        if random.random() < 0.3:  # 30% chance of immediate fill
            await asyncio.sleep(random.uniform(0.5, 2.0))
            order.status = OrderStatus.FILLED
            order.filled_amount = amount
            await self.handle_order_fill(order)
            del self.active_orders[order_id]
        
        return order
    
    async def cancel_order(self, order_id: str) -> bool:
        """Mock order cancellation"""
        if order_id in self.active_orders:
            order = self.active_orders[order_id]
            order.status = OrderStatus.CANCELLED
            del self.active_orders[order_id]
            print(f"❌ Mock Order Cancelled: {order_id}")
            return True
        return False
    
    async def cancel_all_orders(self):
        """Cancel all mock orders"""
        order_ids = list(self.active_orders.keys())
        for order_id in order_ids:
            await self.cancel_order(order_id)
    
    async def update_order_status(self):
        """Mock order status updates - simulate random fills"""
        for order_id, order in list(self.active_orders.items()):
            if order.status == OrderStatus.OPEN:
                # Random chance of partial fill
                if random.random() < 0.1:  # 10% chance per update
                    fill_amount = order.amount * random.uniform(0.3, 0.7)
                    order.filled_amount += fill_amount
                    
                    if order.filled_amount >= order.amount:
                        order.status = OrderStatus.FILLED
                        await self.handle_order_fill(order)
                        del self.active_orders[order_id]
                    else:
                        await self.handle_partial_fill(order)

async def demo_market_maker():
    """Demonstrate market making functionality"""
    
    print("🚀 GATE.IO MARKET MAKER DEMO")
    print("="*80)
    
    # Configuration
    config = MarketMakerConfig(
        symbol="BTC_USDT",
        base_order_size=0.001,
        max_order_size=0.005,
        target_spread_bps=50,
        inventory_target=0.0,
        max_inventory=0.05,
        min_inventory=-0.05,
        order_refresh_time=10,  # Shorter for demo
        max_orders_per_side=2,
        volatility_window=50,
        price_skew_factor=0.1,
        volume_factor=0.001
    )
    
    # Initialize mock market maker
    market_maker = MockMarketMaker("mock_key", "mock_secret", config)
    
    try:
        print("📊 Getting initial market data...")
        await market_maker.get_market_data()
        
        print("💰 Getting account balance...")
        balance = await market_maker.get_account_balance()
        print(f"   BTC: {balance['BTC']['total']:.6f}")
        print(f"   USDT: ${balance['USDT']['total']:,.2f}")
        
        print(f"\n🤖 Starting market making demo (30 seconds)...")
        market_maker.is_running = True
        
        # Run for limited time for demo
        start_time = time.time()
        while time.time() - start_time < 30:  # 30 second demo
            try:
                # Update market data
                await market_maker.get_market_data()
                
                # Update order status
                await market_maker.update_order_status()
                
                # Place maker orders
                await market_maker.place_maker_orders()
                
                # Calculate PnL
                market_maker.calculate_pnl()
                
                # Show status every 5 seconds
                if int(time.time() - start_time) % 5 == 0:
                    print(f"\n--- Status Update ({int(time.time() - start_time)}s) ---")
                    print(f"Active Orders: {len(market_maker.active_orders)}")
                    print(f"Total Trades: {market_maker.total_trades}")
                    print(f"Current Price: ${market_maker.mock_price:.2f}")
                    
                    position = market_maker.inventory.get(config.symbol)
                    if position and position.amount != 0:
                        print(f"Inventory: {position.amount:.6f} BTC (Avg: ${position.avg_price:.2f})")
                        print(f"Unrealized PnL: ${position.unrealized_pnl:.2f}")
                
                await asyncio.sleep(1)
                
            except Exception as e:
                print(f"❌ Error: {e}")
                await asyncio.sleep(1)
        
        print(f"\n🏁 Demo completed!")
        
    except KeyboardInterrupt:
        print(f"\n🛑 Demo interrupted")
    finally:
        market_maker.is_running = False
        await market_maker.cancel_all_orders()
        market_maker.print_statistics()

async def demo_market_maker_features():
    """Demonstrate specific market maker features"""
    
    print("\n🔬 MARKET MAKER FEATURES DEMO")
    print("="*80)
    
    config = MarketMakerConfig(
        symbol="BTC_USDT",
        base_order_size=0.001,
        target_spread_bps=50,
        volatility_window=20
    )
    
    mm = MockMarketMaker("mock_key", "mock_secret", config)
    
    # Test volatility calculation
    print("📈 Testing volatility calculation...")
    for i in range(25):
        price = 50000 + random.uniform(-100, 100)
        mm.price_history.append(price)
    
    volatility = mm.calculate_volatility()
    print(f"   Calculated volatility: {volatility:.6f} ({volatility*100:.2f}%)")
    
    # Test spread calculation
    print("\n💰 Testing spread calculation...")
    await mm.get_market_data()
    
    spread = mm.calculate_optimal_spread()
    print(f"   Optimal spread: {spread:.6f} ({spread*10000:.1f} bps)")
    
    # Test inventory skew
    print("\n⚖️  Testing inventory skew...")
    mm.inventory[config.symbol] = InventoryPosition(
        symbol=config.symbol,
        amount=0.02,  # Long position
        avg_price=50000
    )
    
    skew = mm.calculate_inventory_skew()
    print(f"   Inventory skew: {skew:.6f}")
    
    # Test price calculation
    print("\n🎯 Testing price calculation...")
    bid_price, ask_price = mm.calculate_order_prices()
    print(f"   Bid price: ${bid_price:.2f}")
    print(f"   Ask price: ${ask_price:.2f}")
    print(f"   Calculated spread: ${(ask_price - bid_price):.2f}")
    
    # Test order sizing
    print("\n📊 Testing order sizing...")
    bid_size, ask_size = mm.calculate_order_sizes()
    print(f"   Bid size: {bid_size:.6f} BTC")
    print(f"   Ask size: {ask_size:.6f} BTC")
    
    print("\n✅ Features demo completed!")

if __name__ == "__main__":
    print("🤖 Gate.io Market Maker Bot Demo")
    print("📋 This demo shows market making functionality without live API calls")
    
    # Run features demo
    asyncio.run(demo_market_maker_features())
    
    # Run full market making demo
    asyncio.run(demo_market_maker())
    
    print(f"\n💡 To use with real Gate.io API:")
    print(f"   1. Get Gate.io API keys from https://www.gate.io/")
    print(f"   2. Replace mock keys in gateio_market_maker.py")
    print(f"   3. Configure your trading parameters")
    print(f"   4. Run: python gateio_market_maker.py")
