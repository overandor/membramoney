#!/usr/bin/env python3
"""
Simple Trader - Uses your API keys from environment
"""

import os
import requests
import hmac
import hashlib
import time
import json

# GET API KEYS FROM ENVIRONMENT
API_KEY = os.getenv("GATE_API_KEY", "")
API_SECRET = os.getenv("GATE_API_SECRET", "")

print("🚀 SIMPLE TRADER")
print("=" * 30)
print(f"API Key: {API_KEY[:10] if API_KEY else 'NOT_SET'}...")
print(f"API Secret: {API_SECRET[:10] if API_SECRET else 'NOT_SET'}...")

if not API_KEY or not API_SECRET:
    print("❌ SET YOUR API KEYS FIRST:")
    print("export GATE_API_KEY='your_key_here'")
    print("export GATE_API_SECRET='your_secret_here'")
    exit(1)

def sign_request(method, path, payload):
    """Sign request with your API keys - Gate.io v4 format"""
    timestamp = str(int(time.time()))
    payload_hash = hashlib.sha512(payload.encode()).hexdigest()
    
    # Gate.io v4 signature format: METHOD\nPATH\nPAYLOAD_HASH\nTIMESTAMP
    sign_str = f"{method.upper()}\n{path}\n{payload_hash}\n{timestamp}"
    
    signature = hmac.new(API_SECRET.encode(), sign_str.encode(), hashlib.sha512).hexdigest()
    
    return {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "KEY": API_KEY,
        "Timestamp": timestamp,
        "SIGN": signature
    }

def get_balance():
    """Get your real balance"""
    headers = sign_request("GET", "/spot/accounts", "")
    
    try:
        response = requests.get("https://api.gateio.ws/api/v4/spot/accounts", headers=headers, timeout=10)
        
        if response.status_code == 200:
            accounts = response.json()
            for account in accounts:
                if account.get("currency") == "USDT":
                    available = float(account.get("available", 0))
                    total = float(account.get("available", 0)) + float(account.get("frozen", 0))
                    print(f"💰 YOUR REAL BALANCE: ${available:.2f} available, ${total:.2f} total")
                    return total
        else:
            print(f"❌ Balance error: {response.text}")
    except Exception as e:
        print(f"❌ Balance exception: {e}")
    
    return 0

def place_order(symbol, side, amount_usdt=0.01):
    """Place a real order"""
    # Get current price
    try:
        ticker_response = requests.get(f"https://api.gateio.ws/api/v4/spot/tickers?currency_pair={symbol}", timeout=5)
        if ticker_response.status_code == 200:
            ticker = ticker_response.json()[0]
            price = float(ticker["last"])
        else:
            print(f"❌ Cannot get price for {symbol}")
            return False
    except:
        print(f"❌ Price error for {symbol}")
        return False
    
    # Calculate order size
    order_size = amount_usdt / price
    
    print(f"🎯 PLACING ORDER: {side} {order_size:.6f} {symbol} @ ${price:.6f}")
    print(f"💰 Nominal value: ${order_size * price:.4f}")
    
    # Create order
    order_data = {
        "currency_pair": symbol,
        "type": "limit",
        "side": side,
        "amount": str(order_size),
        "price": str(price),
        "time_in_force": "ioc"
    }
    
    payload = json.dumps(order_data)
    headers = sign_request("POST", "/spot/orders", payload)
    
    try:
        response = requests.post("https://api.gateio.ws/api/v4/spot/orders", headers=headers, data=payload, timeout=10)
        
        if response.status_code == 200:
            result = response.json()
            order_id = result.get("id")
            print(f"✅ ORDER PLACED SUCCESSFULLY!")
            print(f"   Order ID: {order_id}")
            print(f"   🔊 Listen for Gate.io exchange sound!")
            return True
        else:
            print(f"❌ Order failed: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Order exception: {e}")
        return False

# MAIN EXECUTION
if __name__ == "__main__":
    print("\n🔍 CHECKING YOUR REAL ACCOUNT...")
    
    balance = get_balance()
    
    if balance > 0:
        print(f"\n🚀 READY TO TRADE WITH ${balance:.2f}")
        
        # Trade your tokens
        tokens = ["HIPPO_USDT", "DOGE_USDT", "PEPE_USDT"]
        
        for token in tokens:
            print(f"\n📊 Trading {token}...")
            success = place_order(token, "buy", 0.01)  # Buy 1 cent worth
            
            if success:
                print(f"✅ {token} trade successful!")
            else:
                print(f"❌ {token} trade failed!")
            
            time.sleep(2)  # Wait between trades
        
        print(f"\n✅ TRADING COMPLETE!")
        print(f"🎯 Your API keys are working and hitting the real exchange!")
    else:
        print(f"\n❌ Cannot trade - balance issue or API keys invalid")
