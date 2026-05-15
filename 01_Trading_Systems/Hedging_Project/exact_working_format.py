#!/usr/bin/env python3
"""
Exact Working Format - Using the signature that worked before
"""

import os
import requests
import hmac
import hashlib
import time
import json

# Your API keys
API_KEY = "57897b69c76df6aa01a1a25b8d9c6bc8"
API_SECRET = "ed43f2696c3767685e8470c4ba98ea0f7ea85e9adeb9c3d098182889756d79d9"

print("🔧 EXACT WORKING FORMAT TEST")
print("=" * 40)

def _signed_headers(method, path, query_string, payload):
    """Use the exact format that worked in earlier tests"""
    ts = str(int(time.time()))
    payload_hash = hashlib.sha512(payload.encode('utf-8')).hexdigest()
    
    # This is the format that worked before
    sign_str = f"{method.upper()}\n{path}\n{query_string}\n{payload_hash}\n{ts}"
    
    sign = hmac.new(
        API_SECRET.encode("utf-8"),
        sign_str.encode("utf-8"),
        digestmod=hashlib.sha512,
    ).hexdigest()
    
    return {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "KEY": API_KEY,
        "Timestamp": ts,
        "SIGN": sign,
    }

def test_connection():
    """Test connection with exact working format"""
    
    base_url = "https://api.gateio.ws/api/v4"
    
    # Test 1: Public endpoint (should work)
    print("1️⃣ Testing public endpoint...")
    try:
        response = requests.get(f"{base_url}/spot/tickers?currency_pair=HIPPO_USDT", timeout=10)
        if response.status_code == 200:
            ticker = response.json()[0]
            price = float(ticker["last"])
            print(f"   ✅ HIPPO_USDT: ${price:.6f}")
        else:
            print(f"   ❌ Public failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"   ❌ Public error: {e}")
        return False
    
    # Test 2: Private endpoint with exact format
    print("\n2️⃣ Testing private endpoint...")
    
    endpoint = "/spot/accounts"
    method = "GET"
    query_string = ""
    payload = ""
    
    headers = _signed_headers(method, endpoint, query_string, payload)
    
    try:
        response = requests.get(f"{base_url}{endpoint}", headers=headers, timeout=10)
        
        print(f"   📡 Response: {response.status_code}")
        
        if response.status_code == 200:
            accounts = response.json()
            print(f"   ✅ Private endpoint works!")
            
            for account in accounts:
                if account.get("currency") == "USDT":
                    available = float(account.get("available", 0))
                    total = available + float(account.get("frozen", 0))
                    print(f"   💰 USDT: ${available:.2f} available, ${total:.2f} total")
                    return True
        else:
            print(f"   ❌ Private failed: {response.text}")
            
            # Try different query string format
            print("\n3️⃣ Trying with empty query string...")
            headers = _signed_headers(method, endpoint, "", payload)
            response = requests.get(f"{base_url}{endpoint}", headers=headers, timeout=10)
            
            print(f"   📡 Response: {response.status_code}")
            if response.status_code == 200:
                print(f"   ✅ Worked with empty query!")
                return True
            else:
                print(f"   ❌ Still failed: {response.text}")
            
    except Exception as e:
        print(f"   ❌ Private error: {e}")
    
    return False

def place_test_order():
    """Place test order"""
    print("\n4️⃣ Testing order placement...")
    
    # Get current price
    base_url = "https://api.gateio.ws/api/v4"
    
    try:
        ticker_response = requests.get(f"{base_url}/spot/tickers?currency_pair=HIPPO_USDT", timeout=10)
        if ticker_response.status_code != 200:
            print(f"   ❌ Cannot get price")
            return False
        
        ticker = ticker_response.json()[0]
        price = float(ticker["last"])
        order_size = 0.01 / price
        
        print(f"   📊 HIPPO Price: ${price:.6f}")
        print(f"   📏 Order Size: {order_size:.6f}")
        
        # Create order
        order_data = {
            "currency_pair": "HIPPO_USDT",
            "type": "limit",
            "side": "buy",
            "amount": str(order_size),
            "price": str(price),
            "time_in_force": "ioc"
        }
        
        payload = json.dumps(order_data, separators=(",", ":"))
        
        # Sign order request
        endpoint = "/spot/orders"
        headers = _signed_headers("POST", endpoint, "", payload)
        
        response = requests.post(f"{base_url}{endpoint}", headers=headers, data=payload, timeout=10)
        
        print(f"   📡 Order Response: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            order_id = result.get("id")
            print(f"   ✅ ORDER PLACED!")
            print(f"   🎫 Order ID: {order_id}")
            print(f"   🔊 Gate.io sound should play!")
            return True
        else:
            print(f"   ❌ Order failed: {response.text}")
            return False
            
    except Exception as e:
        print(f"   ❌ Order error: {e}")
        return False

if __name__ == "__main__":
    print(f"🚀 Testing with exact working signature format...")
    
    if test_connection():
        print(f"\n✅ Connection successful!")
        
        if place_test_order():
            print(f"\n🎉 SUCCESS! Real trading is working!")
            print(f"🔊 You should hear Gate.io exchange sounds!")
        else:
            print(f"\n⚠️  Connection works but order failed")
    else:
        print(f"\n❌ Connection failed")
        print(f"💡 Check API key permissions on Gate.io")
