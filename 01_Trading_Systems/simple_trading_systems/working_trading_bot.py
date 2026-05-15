#!/usr/bin/env python3
import os
"""
WORKING TRADING BOT - No Ollama Required
Uses simple rules for micro-cap trading
"""

import gate_api
from gate_api import ApiClient, Configuration, SpotApi
import time
import random
from datetime import datetime

# Your API credentials
GATE_API_KEY = os.getenv("GATE_API_KEY", "")
GATE_API_SECRET = os.getenv("GATE_API_SECRET", "")

class WorkingTradingBot:
    def __init__(self):
        self.cfg = Configuration(key=GATE_API_KEY, secret=GATE_API_SECRET)
        self.client = SpotApi(ApiClient(self.cfg))
        self.running = False
        
        # Trading parameters
        self.min_price = 0.000001  # Minimum price to consider
        self.max_price = 0.10      # Maximum price for micro-caps
        self.min_volume = 1000     # Minimum volume in USDT
        self.trade_amount = 1.0    # Trade $1 USDT per trade
        
        print("🚀 WORKING TRADING BOT INITIALIZED")
        print(f"💰 Trade Amount: ${self.trade_amount} per trade")
        print(f"📊 Price Range: ${self.min_price} - ${self.max_price}")
    
    def get_balance(self):
        """Get current USDT balance"""
        try:
            balances = self.client.list_spot_accounts()
            for balance in balances:
                if balance.currency == 'USDT':
                    return float(balance.available)
            return 0.0
        except Exception as e:
            print(f"❌ Balance error: {e}")
            return 0.0
    
    def get_micro_cap_coins(self):
        """Get micro-cap coins under $0.10"""
        try:
            tickers = self.client.list_tickers()
            micro_caps = []
            
            for ticker in tickers:
                if not ticker.currency_pair.endswith('_USDT'):
                    continue
                
                price = float(ticker.last)
                volume = float(ticker.base_volume)
                change = float(ticker.change_percentage)
                
                if (self.min_price <= price <= self.max_price and 
                    volume >= self.min_volume):
                    
                    micro_caps.append({
                        'symbol': ticker.currency_pair.replace('_USDT', ''),
                        'price': price,
                        'volume': volume,
                        'change': change,
                        'pair': ticker.currency_pair
                    })
            
            # Sort by volume (highest first)
            micro_caps.sort(key=lambda x: x['volume'], reverse=True)
            return micro_caps[:50]  # Return top 50
            
        except Exception as e:
            print(f"❌ Market data error: {e}")
            return []
    
    def simple_trading_decision(self, coin):
        """Simple trading rules without AI"""
        price = coin['price']
        change = coin['change']
        volume = coin['volume']
        
        # BUY signals
        if change < -8.0 and volume > 5000:  # Big dump with good volume
            return "BUY", "Dump detected - potential bounce"
        elif change < -5.0 and volume > 10000:  # Medium dump
            return "BUY", "Moderate dump - buying opportunity"
        elif -2.0 <= change <= 2.0 and volume > 20000:  # Stable with high volume
            return "BUY", "Stable price with high volume"
        
        # SELL signals  
        elif change > 15.0:  # Big pump
            return "SELL", "Big pump - take profits"
        elif change > 10.0 and volume < 5000:  # Pump with low volume
            return "SELL", "Weak pump - likely to fall"
        
        # HOLD signals
        else:
            return "HOLD", "No clear signal"
    
    def place_order(self, symbol, side, amount_usdt):
        """Place a real order"""
        try:
            # Get current price
            ticker = self.client.list_tickers(currency_pair=f"{symbol}_USDT")[0]
            current_price = float(ticker.last)
            
            # Calculate quantity
            quantity = amount_usdt / current_price
            
            # Create order
            order = gate_api.Order(
                currency_pair=f"{symbol}_USDT",
                side=side.lower(),
                type='market',
                amount=str(quantity),
                auto_borrow=False
            )
            
            # Place order
            result = self.client.create_order(order)
            
            print(f"✅ {side.upper()} ORDER PLACED:")
            print(f"   Symbol: {symbol}")
            print(f"   Amount: ${amount_usdt}")
            print(f"   Quantity: {quantity:.6f}")
            print(f"   Price: ${current_price}")
            
            return True
            
        except Exception as e:
            print(f"❌ Order failed: {e}")
            return False
    
    def scan_and_trade(self):
        """Main trading loop"""
        print("\n🔍 SCANNING FOR TRADES...")
        
        # Get micro-cap coins
        coins = self.get_micro_cap_coins()
        if not coins:
            print("❌ No micro-cap coins found")
            return
        
        print(f"📊 Found {len(coins)} micro-cap coins")
        
        # Check balance
        balance = self.get_balance()
        print(f"💰 Available USDT: ${balance}")
        
        if balance < self.trade_amount:
            print(f"❌ Insufficient balance. Need ${self.trade_amount}, have ${balance}")
            return
        
        # Analyze each coin
        trades_made = 0
        max_trades = 3  # Limit trades per scan
        
        for coin in coins:
            if trades_made >= max_trades:
                break
            
            decision, reason = self.simple_trading_decision(coin)
            
            print(f"\n📈 {coin['symbol']}: ${coin['price']:.6f} ({coin['change']:+.2f}%)")
            print(f"🤖 Decision: {decision} - {reason}")
            
            if decision in ["BUY", "SELL"] and balance >= self.trade_amount:
                print(f"⚡ Placing {decision} order...")
                if self.place_order(coin['symbol'], decision, self.trade_amount):
                    trades_made += 1
                    balance -= self.trade_amount
                    print(f"✅ Trade executed! Remaining balance: ${balance:.2f}")
                else:
                    print("❌ Order failed")
            
            time.sleep(0.5)  # Small delay between analyses
        
        print(f"\n📊 Scan complete. Made {trades_made} trades.")
    
    def start_trading(self):
        """Start the trading bot"""
        print("🚀 STARTING AUTOMATIC TRADING...")
        print("Press Ctrl+C to stop")
        
        self.running = True
        scan_count = 0
        
        try:
            while self.running:
                scan_count += 1
                print(f"\n{'='*60}")
                print(f"🔄 SCAN #{scan_count} - {datetime.now().strftime('%H:%M:%S')}")
                print(f"{'='*60}")
                
                self.scan_and_trade()
                
                if self.running:
                    print("⏳ Waiting 60 seconds before next scan...")
                    time.sleep(60)
                    
        except KeyboardInterrupt:
            print("\n🛑 STOPPING TRADING BOT...")
            self.running = False
            print("✅ Bot stopped safely")

def main():
    print("🚀 MICRO-CAP TRADING BOT")
    print("="*60)
    print("💰 Real Trading - Gate.io API")
    print("📊 Micro-cap coins under $0.10")
    print("🤖 Simple rule-based trading (no Ollama needed)")
    print("="*60)
    
    bot = WorkingTradingBot()
    
    # Test connection
    balance = bot.get_balance()
    print(f"💰 Current USDT Balance: ${balance}")
    
    if balance >= 1.0:
        print("✅ Ready for trading!")
        
        # Show some sample coins
        coins = bot.get_micro_cap_coins()
        if coins:
            print(f"\n📊 Top 10 micro-cap opportunities:")
            for i, coin in enumerate(coins[:10]):
                decision, reason = bot.simple_trading_decision(coin)
                print(f"   {i+1:2d}. {coin['symbol']:<12} ${coin['price']:.6f} ({coin['change']:+6.2f}%) -> {decision}")
        
        print("\n🚀 Starting automatic trading...")
        bot.start_trading()
        
    else:
        print("❌ Insufficient balance. Please deposit at least $1 USDT to start trading.")
        print("💡 Current balance will work for ALGO trading if you want to trade other pairs")

if __name__ == "__main__":
    main()
