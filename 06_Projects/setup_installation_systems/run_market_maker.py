#!/usr/bin/env python3
"""
RUN GATE.IO MARKET MAKER - DEMO MODE
Runs the market maker with mock data for demonstration
"""

import asyncio
import sys
import os

# Add current directory to path for imports
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from gateio_market_maker_demo import MockMarketMaker, MarketMakerConfig

async def run_market_maker_demo():
    """Run market maker in demo mode"""
    
    print("🚀 STARTING GATE.IO MARKET MAKER - DEMO MODE")
    print("="*80)
    print("⚠️  This is running with MOCK data - no real trades")
    print("💰 To run with real trading, update API keys in gateio_market_maker.py")
    print("="*80)
    
    # Configuration for demo
    config = MarketMakerConfig(
        symbol="BTC_USDT",
        base_order_size=0.001,
        max_order_size=0.005,
        target_spread_bps=50,
        inventory_target=0.0,
        max_inventory=0.05,
        min_inventory=-0.05,
        order_refresh_time=15,  # 15 seconds for demo
        max_orders_per_side=3,
        volatility_window=50,
        price_skew_factor=0.1,
        volume_factor=0.001
    )
    
    # Initialize mock market maker
    market_maker = MockMarketMaker("demo_key", "demo_secret", config)
    
    try:
        print("📊 Getting initial market data...")
        await market_maker.get_market_data()
        
        print("💰 Getting account balance...")
        balance = await market_maker.get_account_balance()
        print(f"   BTC: {balance['BTC']['total']:.6f}")
        print(f"   USDT: ${balance['USDT']['total']:,.2f}")
        
        print(f"\n🤖 Starting market making (Press Ctrl+C to stop)...")
        market_maker.is_running = True
        
        # Run market making loop
        while market_maker.is_running:
            try:
                # Update market data
                await market_maker.get_market_data()
                
                # Update order status
                await market_maker.update_order_status()
                
                # Place maker orders
                await market_maker.place_maker_orders()
                
                # Calculate PnL
                market_maker.calculate_pnl()
                
                # Show status every 10 seconds
                if int(asyncio.get_event_loop().time()) % 10 == 0:
                    print(f"\n--- LIVE STATUS ---")
                    print(f"Active Orders: {len(market_maker.active_orders)}")
                    print(f"Total Trades: {market_maker.total_trades}")
                    print(f"Total Volume: {market_maker.total_volume:.6f} BTC")
                    print(f"Total PnL: ${market_maker.total_pnl:.2f}")
                    print(f"Current Price: ${market_maker.mock_price:.2f}")
                    
                    position = market_maker.inventory.get(config.symbol)
                    if position and position.amount != 0:
                        print(f"Inventory: {position.amount:.6f} BTC (Avg: ${position.avg_price:.2f})")
                        print(f"Unrealized PnL: ${position.unrealized_pnl:.2f}")
                    
                    print(f"Recent Orders:")
                    for order_id, order in list(market_maker.active_orders.items())[-3:]:
                        print(f"  {order.side.value.upper()} {order.amount:.6f} @ ${order.price:.2f}")
                
                await asyncio.sleep(1)
                
            except KeyboardInterrupt:
                print(f"\n🛑 Received interrupt signal")
                break
            except Exception as e:
                print(f"❌ Error: {e}")
                await asyncio.sleep(1)
        
    except Exception as e:
        print(f"❌ Fatal error: {e}")
    finally:
        print(f"\n🏁 Stopping market maker...")
        market_maker.is_running = False
        await market_maker.cancel_all_orders()
        market_maker.print_statistics()
        
        print(f"\n💡 SUMMARY:")
        print(f"   Total Trading Time: {len(market_maker.price_history)} seconds")
        print(f"   Total Trades Executed: {market_maker.total_trades}")
        print(f"   Total Volume: {market_maker.total_volume:.6f} BTC")
        print(f"   Final PnL: ${market_maker.total_pnl:.2f}")
        print(f"   Final Inventory: {market_maker.get_inventory_position():.6f} BTC")
        
        print(f"\n✅ Demo completed! To use with real API:")
        print(f"   1. Get Gate.io API keys from https://www.gate.io/")
        print(f"   2. Update keys in gateio_market_maker.py")
        print(f"   3. Run: python gateio_market_maker.py")

if __name__ == "__main__":
    try:
        asyncio.run(run_market_maker_demo())
    except KeyboardInterrupt:
        print(f"\n🛑 Demo stopped by user")
