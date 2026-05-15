#!/usr/bin/env python3
"""
Final Working Trader - Using Known Working Signature Format
"""

import os
import requests
import hmac
import hashlib
import time
import json
from datetime import datetime

# Your API keys
API_KEY = "57897b69c76df6aa01a1a25b8d9c6bc8"
API_SECRET = "ed43f2696c3767685e8470c4ba98ea0f7ea85e9adeb9c3d098182889756d79d9"

print("🚀 FINAL WORKING TRADER")
print("=" * 40)
print(f"🔑 API Key: {API_KEY[:10]}...")
print(f"🌐 IP: 31.42.157.184")

def sign_request(method, path, query_string, payload):
    """Sign request using Gate.io format"""
    timestamp = str(int(time.time()))
    payload_hash = hashlib.sha512(payload.encode('utf-8')).hexdigest()
    
    # Try the working format from earlier successful tests
    sign_str = f"{method.upper()}\n{path}\n{query_string}\n{payload_hash}\n{timestamp}"
    
    sign = hmac.new(
        API_SECRET.encode("utf-8"),
        sign_str.encode("utf-8"),
        digestmod=hashlib.sha512,
    ).hexdigest()
    
    return {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "KEY": API_KEY,
        "Timestamp": timestamp,
        "SIGN": sign,
    }

def test_request(endpoint, method="GET", payload="", private=True):
    """Test API request"""
    
    base_url = "https://api.gateio.ws/api/v4"
    
    # Parse endpoint
    if '?' in endpoint:
        path, query = endpoint.split('?', 1)
    else:
        path, query = endpoint, ""
    
    headers = {}
    if private:
        headers = sign_request(method, path, query, payload)
    else:
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json"
        }
    
    try:
        if method == "GET":
            response = requests.get(f"{base_url}{endpoint}", headers=headers, timeout=10)
        elif method == "POST":
            response = requests.post(f"{base_url}{endpoint}", headers=headers, data=payload, timeout=10)
        
        print(f"📡 {method} {endpoint}")
        print(f"📥 Status: {response.status_code}")
        
        if response.status_code == 200:
            return {"success": True, "data": response.json()}
        else:
            print(f"❌ Error: {response.text}")
            return {"success": False, "error": response.text}
            
    except Exception as e:
        print(f"❌ Exception: {e}")
        return {"success": False, "error": str(e)}

def get_balance():
    """Get account balance"""
    print(f"\n💰 CHECKING BALANCE")
    print("-" * 25)
    
    result = test_request("/spot/accounts", "GET", "", private=True)
    
    if result["success"]:
        accounts = result["data"]
        for account in accounts:
            if account.get("currency") == "USDT":
                available = float(account.get("available", 0))
                total = available + float(account.get("frozen", 0))
                print(f"✅ USDT Balance: ${available:.2f} available, ${total:.2f} total")
                return total
    else:
        print(f"❌ Balance check failed")
    
    return 0

def place_buy_order(symbol, amount_usdt=0.01):
    """Place buy order"""
    print(f"\n🎯 BUYING {symbol}")
    print("-" * 25)
    
    # Get current price
    ticker_result = test_request(f"/spot/tickers?currency_pair={symbol}", "GET", "", private=False)
    
    if not ticker_result["success"]:
        print(f"❌ Cannot get price for {symbol}")
        return False
    
    ticker = ticker_result["data"][0]
    price = float(ticker["last"])
    
    # Calculate order size
    order_size = amount_usdt / price
    
    print(f"   Price: ${price:.6f}")
    print(f"   Size: {order_size:.6f}")
    print(f"   Value: ${order_size * price:.4f}")
    
    # Create order
    order_data = {
        "currency_pair": symbol,
        "type": "limit",
        "side": "buy",
        "amount": str(order_size),
        "price": str(price),
        "time_in_force": "ioc"
    }
    
    payload = json.dumps(order_data, separators=(",", ":"))
    
    # Place order
    result = test_request("/spot/orders", "POST", payload, private=True)
    
    if result["success"]:
        order_id = result["data"].get("id")
        print(f"✅ ORDER PLACED!")
        print(f"   ID: {order_id}")
        print(f"   🔊 Gate.io sound should play!")
        return True
    else:
        print(f"❌ Order failed")
        return False

def main():
    """Main execution"""
    print(f"\n🚀 STARTING TRADING SESSION")
    print(f"📅 {datetime.now().strftime('%H:%M:%S')}")
    print("=" * 40)
    
    # Check balance
    balance = get_balance()
    
    if balance > 0:
        print(f"\n✅ Ready to trade with ${balance:.2f}")
        
        # Trade your tokens
        tokens = ["HIPPO_USDT", "DOGE_USDT", "PEPE_USDT"]
        
        for token in tokens:
            print(f"\n{'='*40}")
            success = place_buy_order(token, 0.01)
            
            if success:
                print(f"✅ {token} trade successful!")
            else:
                print(f"❌ {token} trade failed!")
            
            time.sleep(2)  # Wait between trades
        
        print(f"\n🎉 TRADING COMPLETE!")
        print(f"🔊 Check Gate.io for all order sounds!")
        
    else:
        print(f"\n❌ Cannot trade - balance or API issue")

if __name__ == "__main__":
    main()
