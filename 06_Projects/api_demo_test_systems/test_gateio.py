#!/usr/bin/env python3
"""
GATE.IO CONNECTION TESTER
Test your Gate.io API connection and get real balance
"""

import gate_api
from gate_api import ApiClient, Configuration, SpotApi
import os

# Your API credentials
GATE_API_KEY = os.getenv("GATE_API_KEY", "")
GATE_API_SECRET = os.getenv("GATE_API_SECRET", "")

def test_gateio_connection():
    """Test Gate.io connection using official SDK"""
    print("🔌 TESTING GATE.IO CONNECTION")
    print("="*50)
    print(f"🔑 API Key: {GATE_API_KEY[:10]}...")
    print(f"🔑 API Secret: {GATE_API_SECRET[:10]}...")
    
    try:
        # Setup configuration exactly like the working gatefutures.py
        cfg = Configuration(key=GATE_API_KEY, secret=GATE_API_SECRET)
        client = SpotApi(ApiClient(cfg))
        
        print("✅ Gate.io SDK client initialized")
        
        # Test account balance
        print("\n💰 Getting account balances...")
        balances = client.list_spot_accounts()
        
        if balances:
            print("✅ SUCCESS! Account balances:")
            total_usdt = 0.0
            
            for balance in balances:
                currency = balance.currency
                available = float(balance.available)
                # Try different attribute names for total balance
                try:
                    total = float(balance.total)
                except AttributeError:
                    try:
                        total = float(balance.balance)
                    except AttributeError:
                        total = available  # Fallback to available
                
                if total > 0:
                    print(f"  🪙 {currency}: {total:.6f} (Available: {available:.6f})")
                    
                    if currency == 'USDT':
                        total_usdt = total
            
            print(f"\n💵 TOTAL USDT BALANCE: ${total_usdt:.2f}")
            
            if total_usdt > 0:
                print("🎉 READY FOR TRADING!")
                return True
            else:
                print("⚠️ No USDT balance found")
                return False
        else:
            print("❌ No balance data received")
            return False
            
    except Exception as e:
        print(f"❌ ERROR: {e}")
        print("\n🔧 TROUBLESHOOTING:")
        print("1. Check if API keys are correct")
        print("2. Check if API keys have proper permissions")
        print("3. Check if account is active and verified")
        return False

def test_market_data():
    """Test getting market data"""
    print("\n📊 TESTING MARKET DATA...")
    
    try:
        cfg = Configuration(key=GATE_API_KEY, secret=GATE_API_SECRET)
        client = SpotApi(ApiClient(cfg))
        
        # Get tickers
        tickers = client.list_tickers()
        
        if tickers:
            print(f"✅ Found {len(tickers)} tickers")
            
            # Show some micro-cap coins
            micro_caps = [t for t in tickers if float(t.last) < 0.1 and t.currency_pair.endswith('_USDT')]
            print(f"\n📈 Found {len(micro_caps)} micro-cap coins under $0.10:")
            
            for i, ticker in enumerate(micro_caps[:10]):
                price = float(ticker.last)
                change = float(ticker.change_percentage)
                symbol = ticker.currency_pair
                
                print(f"  {i+1:2d}. {symbol:<12} ${price:.6f} {change:+6.2f}%")
            
            return True
        else:
            print("❌ No ticker data")
            return False
            
    except Exception as e:
        print(f"❌ Market data error: {e}")
        return False

def main():
    print("🚀 GATE.IO TRADING BOT CONNECTION TEST")
    print("="*60)
    
    # Test connection
    if test_gateio_connection():
        # Test market data
        test_market_data()
        
        print("\n" + "="*60)
        print("🎯 NEXT STEPS:")
        print("1. ✅ Gate.io connection working")
        print("2. 🤖 Fix Ollama or use alternative AI")
        print("3. 🚀 Start trading with your micro-cap coins")
        
    else:
        print("\n❌ Fix Gate.io connection first")

if __name__ == "__main__":
    main()
