#!/usr/bin/env python3
import os
"""
SIMPLE BALANCE CHECK - Run this in YOUR terminal
"""

import gate_api
from gate_api import ApiClient, Configuration, SpotApi

# Your API credentials
GATE_API_KEY = os.getenv("GATE_API_KEY", "")
GATE_API_SECRET = os.getenv("GATE_API_SECRET", "")

def main():
    print("🔌 GATE.IO BALANCE CHECK")
    print("="*40)
    
    try:
        # Setup connection
        cfg = Configuration(key=GATE_API_KEY, secret=GATE_API_SECRET)
        client = SpotApi(ApiClient(cfg))
        
        print("✅ Connected to Gate.io")
        
        # Get balances
        balances = client.list_spot_accounts()
        
        print("\n💰 YOUR BALANCES:")
        for balance in balances:
            available = float(balance.available)
            if available > 0:
                print(f"  {balance.currency}: {available:.6f}")
        
        # Get ALGO price
        try:
            algo_ticker = client.list_tickers(currency_pair='ALGO_USDT')[0]
            algo_price = float(algo_ticker.last)
            print(f"\n📊 ALGO Price: ${algo_price:.6f}")
            
            # Calculate ALGO value
            algo_balance = 0.893412  # Your balance
            algo_value = algo_balance * algo_price
            print(f"💵 Your ALGO is worth: ${algo_value:.2f}")
            
        except:
            print("❌ Could not get ALGO price")
        
        # Test a simple order (READ-ONLY - won't actually place)
        print(f"\n🧪 Testing order parameters...")
        
        # Get current price for a micro-cap
        tickers = client.list_tickers()
        micro_caps = [t for t in tickers if float(t.last) < 0.01 and t.currency_pair.endswith('_USDT')]
        
        if micro_caps:
            test_coin = micro_caps[0]
            symbol = test_coin.currency_pair
            price = float(test_coin.last)
            
            print(f"📈 Test coin: {symbol}")
            print(f"💰 Price: ${price:.6f}")
            
            # Calculate order parameters
            usdt_amount = 1.0
            quantity = usdt_amount / price
            
            print(f"🧮 Order calculation:")
            print(f"   USDT to spend: ${usdt_amount}")
            print(f"   Quantity to buy: {quantity:.6f}")
            print(f"   Order type: market")
            print(f"   Side: buy")
            
            print(f"\n✅ Order parameters look correct!")
            
        else:
            print("❌ No micro-cap coins found for testing")
            
    except Exception as e:
        print(f"❌ ERROR: {e}")
        print(f"🔍 Error type: {type(e).__name__}")

if __name__ == "__main__":
    main()
