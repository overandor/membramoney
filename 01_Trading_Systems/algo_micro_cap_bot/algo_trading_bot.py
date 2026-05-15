#!/usr/bin/env python3
import os
"""
ALGO TRADING BOT - Trade your ALGO for micro-cap opportunities
"""

import gate_api
from gate_api import ApiClient, Configuration, SpotApi
import time
from datetime import datetime

# Your API credentials
GATE_API_KEY = os.getenv("GATE_API_KEY", "")
GATE_API_SECRET = os.getenv("GATE_API_SECRET", "")

class AlgoTradingBot:
    def __init__(self):
        self.cfg = Configuration(key=GATE_API_KEY, secret=GATE_API_SECRET)
        self.client = SpotApi(ApiClient(self.cfg))
        self.running = False
        
        print("🚀 ALGO TRADING BOT INITIALIZED")
        print("💰 Will trade your ALGO for micro-cap opportunities")
    
    def get_balance(self):
        """Get current balances"""
        try:
            balances = self.client.list_spot_accounts()
            balance_dict = {}
            
            for balance in balances:
                currency = balance.currency
                available = float(balance.available)
                if available > 0:
                    balance_dict[currency] = available
            
            return balance_dict
        except Exception as e:
            print(f"❌ Balance error: {e}")
            return {}
    
    def get_algo_price(self):
        """Get current ALGO price in USDT"""
        try:
            ticker = self.client.list_tickers(currency_pair='ALGO_USDT')[0]
            return float(ticker.last)
        except Exception as e:
            print(f"❌ ALGO price error: {e}")
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
                
                if 0.000001 <= price <= 0.10 and volume >= 1000:
                    micro_caps.append({
                        'symbol': ticker.currency_pair.replace('_USDT', ''),
                        'price': price,
                        'volume': volume,
                        'change': change,
                        'pair': ticker.currency_pair
                    })
            
            micro_caps.sort(key=lambda x: x['volume'], reverse=True)
            return micro_caps[:20]
            
        except Exception as e:
            print(f"❌ Market data error: {e}")
            return []
    
    def simple_trading_decision(self, coin):
        """Simple trading rules"""
        change = coin['change']
        volume = coin['volume']
        
        # Strong buy signals
        if change < -10.0 and volume > 5000:
            return "BUY", "Strong dump - high probability bounce"
        elif change < -7.0 and volume > 10000:
            return "BUY", "Major dump - accumulation opportunity"
        elif change < -5.0 and volume > 20000:
            return "BUY", "Moderate dump with high volume"
        
        # Hold signals
        else:
            return "HOLD", "No strong signal detected"
    
    def convert_algo_to_usdt(self, algo_amount):
        """Convert ALGO to USDT"""
        try:
            # Get current ALGO price
            algo_price = self.get_algo_price()
            if algo_price == 0:
                return False
            
            # Create sell order for ALGO
            order = gate_api.Order(
                currency_pair='ALGO_USDT',
                side='sell',
                type='market',
                amount=str(algo_amount),
                auto_borrow=False,
                time_in_force='ioc'  # Immediate or Cancel for market orders
            )
            
            result = self.client.create_order(order)
            usdt_received = algo_amount * algo_price
            
            print(f"✅ ALGO SOLD:")
            print(f"   Amount: {algo_amount} ALGO")
            print(f"   Price: ${algo_price:.6f}")
            print(f"   Received: ${usdt_received:.2f} USDT")
            
            return True
            
        except Exception as e:
            print(f"❌ ALGO sell failed: {e}")
            return False
    
    def buy_micro_cap(self, symbol, usdt_amount):
        """Buy micro-cap coin with USDT"""
        try:
            # Get current price
            ticker = self.client.list_tickers(currency_pair=f"{symbol}_USDT")[0]
            current_price = float(ticker.last)
            
            # Calculate quantity
            quantity = usdt_amount / current_price
            
            # Create buy order
            order = gate_api.Order(
                currency_pair=f"{symbol}_USDT",
                side='buy',
                type='market',
                amount=str(quantity),
                auto_borrow=False
            )
            
            result = self.client.create_order(order)
            
            print(f"✅ MICRO-CAP BOUGHT:")
            print(f"   Symbol: {symbol}")
            print(f"   Amount: ${usdt_amount} USDT")
            print(f"   Quantity: {quantity:.6f}")
            print(f"   Price: ${current_price:.6f}")
            
            return True
            
        except Exception as e:
            print(f"❌ Buy order failed: {e}")
            return False
    
    def scan_and_trade(self):
        """Main trading loop"""
        print("\n🔍 SCANNING FOR MICRO-CAP OPPORTUNITIES...")
        
        # Get current balances
        balances = self.get_balance()
        print(f"💰 Current Balances:")
        for currency, amount in balances.items():
            print(f"   {currency}: {amount:.6f}")
        
        algo_amount = balances.get('ALGO', 0)
        usdt_amount = balances.get('USDT', 0)
        
        if algo_amount < 0.1:  # Need at least 0.1 ALGO
            print("❌ Insufficient ALGO balance (need 0.1 ALGO minimum)")
            return
        
        # Get micro-cap opportunities
        coins = self.get_micro_cap_coins()
        if not coins:
            print("❌ No micro-cap opportunities found")
            return
        
        print(f"📊 Found {len(coins)} micro-cap opportunities")
        
        # Convert some ALGO to USDT for trading
        algo_to_sell = min(algo_amount * 0.5, 0.5)  # Sell up to 50% or 0.5 ALGO
        
        print(f"\n💱 Converting {algo_to_sell:.6f} ALGO to USDT...")
        if self.convert_algo_to_usdt(algo_to_sell):
            print("✅ ALGO converted successfully")
            time.sleep(2)  # Wait for conversion
            
            # Get updated USDT balance
            new_balances = self.get_balance()
            available_usdt = new_balances.get('USDT', 0)
            
            if available_usdt > 1.0:  # Need at least $1 USDT
                # Find best opportunity
                best_coin = None
                best_reason = ""
                
                for coin in coins:
                    decision, reason = self.simple_trading_decision(coin)
                    
                    print(f"\n📈 {coin['symbol']}: ${coin['price']:.6f} ({coin['change']:+.2f}%)")
                    print(f"🤖 Decision: {decision} - {reason}")
                    
                    if decision == "BUY":
                        best_coin = coin
                        best_reason = reason
                        break
                
                if best_coin:
                    trade_amount = min(available_usdt * 0.8, 5.0)  # Use 80% or max $5
                    print(f"\n⚡ BUYING {best_coin['symbol']}...")
                    print(f"💰 Trade Amount: ${trade_amount:.2f}")
                    print(f"📊 Reason: {best_reason}")
                    
                    if self.buy_micro_cap(best_coin['symbol'], trade_amount):
                        print("✅ Trade executed successfully!")
                    else:
                        print("❌ Trade failed")
                else:
                    print("❌ No strong buy signals found")
            else:
                print(f"❌ Insufficient USDT after conversion (${available_usdt:.2f})")
        else:
            print("❌ ALGO conversion failed")
    
    def start_trading(self):
        """Start the trading bot"""
        print("🚀 STARTING ALGO TRADING BOT...")
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
                    print("⏳ Waiting 5 minutes before next scan...")
                    time.sleep(300)  # 5 minutes
                    
        except KeyboardInterrupt:
            print("\n🛑 STOPPING TRADING BOT...")
            self.running = False
            print("✅ Bot stopped safely")

def main():
    print("🚀 ALGO MICRO-CAP TRADING BOT")
    print("="*60)
    print("💰 Trade your ALGO for micro-cap opportunities")
    print("📊 Target: Coins under $0.10 with high volume")
    print("🤖 Rule-based trading for dump recovery")
    print("="*60)
    
    bot = AlgoTradingBot()
    
    # Show current status
    balances = bot.get_balance()
    algo_price = bot.get_algo_price()
    
    print(f"💰 ALGO Balance: {balances.get('ALGO', 0):.6f}")
    print(f"💰 USDT Balance: ${balances.get('USDT', 0):.6f}")
    print(f"📊 ALGO Price: ${algo_price:.6f}")
    
    algo_value = balances.get('ALGO', 0) * algo_price
    print(f"💵 ALGO Value: ${algo_value:.2f}")
    
    if balances.get('ALGO', 0) >= 0.1:
        print("✅ Ready for trading!")
        
        # Show opportunities
        coins = bot.get_micro_cap_coins()
        if coins:
            print(f"\n📊 Top 5 micro-cap opportunities:")
            for i, coin in enumerate(coins[:5]):
                decision, reason = bot.simple_trading_decision(coin)
                print(f"   {i+1}. {coin['symbol']:<12} ${coin['price']:.6f} ({coin['change']:+6.2f}%) -> {decision}")
        
        print("\n🚀 Starting automatic trading...")
        bot.start_trading()
        
    else:
        print("❌ Insufficient ALGO balance. Need at least 0.1 ALGO to start.")

if __name__ == "__main__":
    main()
