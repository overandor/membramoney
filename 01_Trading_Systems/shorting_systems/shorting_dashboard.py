#!/usr/bin/env python3
import os
"""
REAL-TIME SHORTING DASHBOARD
Live monitoring of the advanced shorting system
"""

import asyncio
import json
from datetime import datetime, timedelta
import pandas as pd
from advanced_shorting_system import AdvancedShortingSystem

class ShortingDashboard:
    """Real-time dashboard for shorting system"""
    
    def __init__(self):
        self.system = AdvancedShortingSystem()
        self.start_time = datetime.now()
        
    def print_header(self):
        """Print dashboard header"""
        print("\n" + "="*100)
        print("🤖 ADVANCED CRYPTO SHORTING SYSTEM - LIVE DASHBOARD")
        print("="*100)
        print(f"🎯 Target: Micro-cap coins (1¢-10¢) with 10%+ pumps")
        print(f"📊 Exchanges: Binance, Bybit, KuCoin Futures")
        print(f"⏰ Started: {self.start_time.strftime('%Y-%m-%d %H:%M:%S')}")
        print("="*100)
    
    def print_real_time_status(self):
        """Print real-time status"""
        runtime = datetime.now() - self.start_time
        hours = runtime.total_seconds() / 3600
        
        print(f"\n📊 SYSTEM STATUS (Runtime: {hours:.1f}h)")
        print("-" * 100)
        print(f"🎯 Active Positions: {len(self.system.active_positions)}/{self.system.max_positions}")
        print(f"📈 Total Trades: {self.system.total_trades}")
        print(f"✅ Successful Shorts: {self.system.successful_shorts}")
        print(f"💰 Total PnL: ${self.system.total_pnl:.2f}")
        
        if self.system.total_trades > 0:
            success_rate = (self.system.successful_shorts / self.system.total_trades) * 100
            avg_pnl = self.system.total_pnl / self.system.total_trades
            print(f"📊 Success Rate: {success_rate:.1f}%")
            print(f"💵 Avg PnL per Trade: ${avg_pnl:.2f}")
        
        print(f"🔍 Last Scan: {self.system.last_scan_time.strftime('%H:%M:%S')}")
    
    def print_active_positions(self):
        """Print active positions details"""
        if not self.system.active_positions:
            print(f"\n📋 No active positions")
            return
        
        print(f"\n📋 ACTIVE POSITIONS ({len(self.system.active_positions)})")
        print("-" * 100)
        print(f"{'Symbol':<15} {'Exchange':<10} {'Entry':<10} {'Current':<10} {'PnL':<10} {'PnL%':<8} {'Target':<10} {'Stop':<10}")
        print("-" * 100)
        
        # Get current prices (mock for demo)
        import numpy as np
        
        for pos in self.system.active_positions:
            # Simulate current price with small movement
            change = np.random.normal(0, 0.005)
            current_price = pos.entry_price * (1 + change)
            pnl = (pos.entry_price - current_price) * pos.quantity
            pnl_pct = (pnl / (pos.entry_price * pos.quantity)) * 100
            
            # Color code PnL
            pnl_str = f"${pnl:.2f}"
            pnl_pct_str = f"{pnl_pct:+.1f}%"
            
            print(f"{pos.symbol:<15} {pos.exchange:<10} ${pos.entry_price:<9.4f} "
                  f"${current_price:<9.4f} {pnl_str:<10} {pnl_pct_str:<8} "
                  f"${pos.target_price:<9.4f} ${pos.stop_loss:<9.4f}")
    
    def print_recent_activity(self):
        """Print recent trading activity"""
        print(f"\n📈 RECENT ACTIVITY")
        print("-" * 100)
        
        # Simulate recent activity
        activities = [
            {"time": "12:30:45", "action": "SHORT PLACED", "symbol": "PEPE", "exchange": "Binance", "price": "$0.0123"},
            {"time": "12:28:12", "action": "PROFIT TAKEN", "symbol": "SHIB", "exchange": "Bybit", "pnl": "+$2.34"},
            {"time": "12:25:33", "action": "SHORT PLACED", "symbol": "DOGE", "exchange": "KuCoin", "price": "$0.0876"},
            {"time": "12:22:15", "action": "STOP LOSS", "symbol": "FLOKI", "exchange": "Binance", "pnl": "-$1.12"},
            {"time": "12:18:45", "action": "PROFIT TAKEN", "symbol": "BABYDOGE", "exchange": "Bybit", "pnl": "+$3.45"}
        ]
        
        for activity in activities:
            if "pnl" in activity:
                print(f"   {activity['time']} - {activity['action']}: {activity['symbol']} ({activity['pnl']})")
            else:
                print(f"   {activity['time']} - {activity['action']}: {activity['symbol']} @ {activity['price']}")
    
    def print_market_scan_results(self):
        """Print latest market scan results"""
        print(f"\n🔍 LATEST MARKET SCAN")
        print("-" * 100)
        
        # Simulate scan results
        scan_results = [
            {"symbol": "PEPE", "exchange": "Binance", "price": "$0.0123", "change": "+12.5%", "action": "SHORTED"},
            {"symbol": "SHIB", "exchange": "Bybit", "price": "$0.0234", "change": "+10.2%", "action": "SHORTED"},
            {"symbol": "DOGE", "exchange": "KuCoin", "price": "$0.0876", "change": "+11.3%", "action": "SHORTED"},
            {"symbol": "FLOKI", "exchange": "Binance", "price": "$0.0456", "change": "+15.7%", "action": "SHORTED"},
            {"symbol": "BABYDOGE", "exchange": "Bybit", "price": "$0.0321", "change": "+9.8%", "action": "MONITORING"}
        ]
        
        print(f"{'Symbol':<12} {'Exchange':<10} {'Price':<10} {'24h Change':<12} {'Action':<12}")
        print("-" * 100)
        
        for result in scan_results:
            print(f"{result['symbol']:<12} {result['exchange']:<10} {result['price']:<10} "
                  f"{result['change']:<12} {result['action']:<12}")
    
    def print_performance_metrics(self):
        """Print detailed performance metrics"""
        print(f"\n📊 PERFORMANCE METRICS")
        print("-" * 100)
        
        # Calculate metrics
        if self.system.total_trades > 0:
            success_rate = (self.system.successful_shorts / self.system.total_trades) * 100
            avg_pnl = self.system.total_pnl / self.system.total_trades
            
            # Simulate additional metrics
            total_invested = self.system.total_trades * self.system.position_size_usd
            total_return = (self.system.total_pnl / total_invested) * 100 if total_invested > 0 else 0
            
            print(f"📈 Win Rate: {success_rate:.1f}%")
            print(f"💰 Average PnL: ${avg_pnl:.2f}")
            print(f"💵 Total Invested: ${total_invested:.2f}")
            print(f"📊 Total Return: {total_return:.2f}%")
            print(f"⏱️  Avg Trade Duration: 2.3 hours")
            print(f"🎯 Best Trade: +$12.34 (+62%)")
            print(f"❌ Worst Trade: -$8.76 (-44%)")
        else:
            print("   No trades executed yet")
    
    def print_risk_metrics(self):
        """Print risk management metrics"""
        print(f"\n⚠️  RISK MANAGEMENT")
        print("-" * 100)
        
        total_risk = len(self.system.active_positions) * self.system.position_size_usd
        max_risk = self.system.max_positions * self.system.position_size_usd
        
        print(f"💸 Current Risk Exposure: ${total_risk:.2f}")
        print(f"📊 Maximum Risk Capacity: ${max_risk:.2f}")
        print(f"📈 Risk Utilization: {(total_risk/max_risk)*100:.1f}%")
        print(f"🛡️  Stop Loss Hit Rate: 23.4%")
        print(f"🎯 Target Hit Rate: 76.6%")
        print(f"⏰ Daily Loss Limit: $50.00 (5%)")
        print(f"💵 Current Daily Loss: ${max(0, -self.system.total_pnl):.2f}")
    
    async def run_dashboard(self):
        """Run the real-time dashboard"""
        self.print_header()
        
        # Simulate some initial activity
        self.system.total_trades = 15
        self.system.successful_shorts = 11
        self.system.total_pnl = 23.45
        
        # Create some mock positions
        import numpy as np
        symbols = ["PEPE", "SHIB", "DOGE", "FLOKI", "BABYDOGE"]
        exchanges = ["Binance", "Bybit", "KuCoin"]
        
        for i in range(7):
            symbol = np.random.choice(symbols)
            exchange = np.random.choice(exchanges)
            entry_price = np.random.uniform(0.01, 0.10)
            quantity = 10 / entry_price
            
            position = type('Position', (), {
                'symbol': symbol,
                'exchange': exchange,
                'entry_price': entry_price,
                'quantity': quantity,
                'entry_time': datetime.now() - timedelta(hours=np.random.uniform(0, 24)),
                'target_price': entry_price * 0.95,
                'stop_loss': entry_price * 1.03,
                'status': 'open'
            })()
            
            self.system.active_positions.append(position)
        
        # Update dashboard every 5 seconds
        while True:
            try:
                # Clear screen (for demo, just print separator)
                print("\n" + "="*100)
                print(f"🕐 UPDATE: {datetime.now().strftime('%H:%M:%S')}")
                print("="*100)
                
                self.print_real_time_status()
                self.print_active_positions()
                self.print_market_scan_results()
                self.print_performance_metrics()
                self.print_risk_metrics()
                
                print(f"\n💡 Next update in 5 seconds... (Press Ctrl+C to stop)")
                
                await asyncio.sleep(5)
                
            except KeyboardInterrupt:
                print(f"\n🛑 Dashboard stopped by user")
                break

async def main():
    """Main dashboard function"""
    print("🚀 STARTING REAL-TIME SHORTING DASHBOARD")
    print("="*100)
    print("📊 Live monitoring of crypto shorting system")
    print("🎯 Tracking micro-cap coins with 10%+ pumps")
    print("⚠️  SIMULATION MODE - Showing demo data")
    print("="*100)
    
    dashboard = ShortingDashboard()
    await dashboard.run_dashboard()

if __name__ == "__main__":
    asyncio.run(main())
