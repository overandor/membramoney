#!/usr/bin/env python3
"""
Gate.io Futures Market Making Demo - WORKING VERSION
This version works in dry mode without requiring valid API keys
"""

import asyncio
import json
import logging
import os
import time
from datetime import datetime
from decimal import Decimal

# Configuration
GATE_API_KEY = os.getenv("GATE_API_KEY", "")
GATE_API_SECRET = os.getenv("GATE_API_SECRET", "")
SETTLE = "usdt"
REST_BASE_URL = "https://api.gateio.ws/api/v4"

# Demo settings
DRY_RUN = True  # Always true in demo mode
SYMBOLS = ["BTC_USDT", "ETH_USDT", "SOL_USDT", "ENA_USDT"]

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("GATE-DEMO")

class MockGateClient:
    """Mock client that simulates Gate.io API responses"""
    
    def __init__(self):
        self.mock_prices = {
            "BTC_USDT": 65000.0,
            "ETH_USDT": 3500.0,
            "SOL_USDT": 180.0,
            "ENA_USDT": 0.85
        }
    
    def list_contracts(self):
        """Mock contracts list"""
        contracts = []
        for symbol in SYMBOLS:
            contracts.append({
                "name": symbol,
                "last_price": str(self.mock_prices[symbol]),
                "quanto_multiplier": "1",
                "order_size_min": "0.001",
                "order_size_max": "1000",
                "order_price_round": "0.01",
                "leverage_min": 1,
                "leverage_max": 100,
                "volume_24h_quote": "1000000",
                "status": "trading"
            })
        return contracts
    
    def positions(self):
        """Mock empty positions"""
        return []
    
    def open_orders(self):
        """Mock empty orders"""
        return []
    
    def account(self):
        """Mock account info"""
        return {
            "total": "10000.0",
            "available": "10000.0",
            "unrealised_pnl": "0.0"
        }

class SimpleMarketMaker:
    """Simple market making demo"""
    
    def __init__(self):
        self.client = MockGateClient()
        self.running = False
        self.cycle = 0
    
    async def run_demo(self):
        """Run the market making demo"""
        log.info("🚀 Starting Gate.io Market Making Demo")
        log.info(f"📊 Symbols: {', '.join(SYMBOLS)}")
        log.info(f"💰 Mode: DRY RUN (No real trading)")
        
        self.running = True
        
        while self.running:
            self.cycle += 1
            cycle_start = time.time()
            
            try:
                # Get mock data
                contracts = self.client.list_contracts()
                positions = self.client.positions()
                orders = self.client.open_orders()
                account = self.client.account()
                
                # Simulate market making
                log.info(f"🔄 Cycle {self.cycle}: Processing {len(contracts)} symbols")
                
                for contract in contracts:
                    symbol = contract["name"]
                    price = float(contract["last_price"])
                    
                    # Calculate mock bid/ask
                    spread_pct = 0.001  # 0.1% spread
                    bid_price = price * (1 - spread_pct)
                    ask_price = price * (1 + spread_pct)
                    
                    log.info(f"  📈 {symbol}: ${price:.2f} | Bid: ${bid_price:.2f} | Ask: ${ask_price:.2f}")
                    
                    # Simulate placing orders (dry run only)
                    if symbol == "ENA_USDT":  # Focus on ENA as requested
                        log.info(f"    🎯 HEDGING MODE: Would place orders for {symbol}")
                        log.info(f"    ✅ BUY at best bid: ${bid_price:.4f}")
                        log.info(f"    ✅ SELL at best ask: ${ask_price:.4f}")
                
                # Show portfolio status
                total_usd = float(account["total"])
                log.info(f"💰 Portfolio: ${total_usd:.2f} | Positions: {len(positions)} | Orders: {len(orders)}")
                
                # Wait before next cycle
                elapsed = time.time() - cycle_start
                sleep_time = max(0, 5.0 - elapsed)  # 5 second cycles
                await asyncio.sleep(sleep_time)
                
            except KeyboardInterrupt:
                log.info("🛑 Demo stopped by user")
                break
            except Exception as e:
                log.error(f"❌ Error in cycle {self.cycle}: {e}")
                await asyncio.sleep(1)
        
        log.info("✅ Demo completed")

async def main():
    """Main function"""
    print("🚀 GATE.IO MARKET MAKING DEMO")
    print("=" * 50)
    print("This is a working demo that simulates trading")
    print("without requiring real API credentials.")
    print("=" * 50)
    
    # Check if we have API keys (optional for demo)
    if GATE_API_KEY and GATE_API_SECRET:
        log.info("🔑 API keys detected (but using mock data for demo)")
    else:
        log.info("⚠️  No API keys - running in pure demo mode")
    
    # Create and run demo
    demo = SimpleMarketMaker()
    await demo.run_demo()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Demo stopped!")
