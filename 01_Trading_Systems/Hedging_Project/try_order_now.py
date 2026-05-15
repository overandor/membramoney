#!/usr/bin/env python3
"""
Try to place order right now
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

print("🎯 TRYING TO PLACE ORDER NOW")
print("=" * 40)

def create_signature(method, path, query, payload, timestamp):
    """Create signature"""
    payload_hash = hashlib.sha512(payload.encode()).hexdigest()
    sign_str = f"{method.upper()}\n{path}\n{query}\n{payload_hash}\n{timestamp}"
    return hmac.new(API_SECRET.encode(), sign_str.encode(), hashlib.sha512).hexdigest()

def place_order():
    """Place order attempt"""
    
    # Get current price for HIPPO
    try:
        ticker_response = requests.get("https://api.gateio.ws/api/v4/spot/tickers?currency_pair=HIPPO_USDT", timeout=5)
        if ticker_response.status_code == 200:
            ticker = ticker_response.json()[0]
            price = float(ticker["last"])
            print(f"📊 HIPPO_USDT Price: ${price:.6f}")
        else:
            print("❌ Cannot get price")
            return False
    except Exception as e:
        print(f"❌ Price error: {e}")
        return False
    
    # Prepare order
    order_size = 0.01 / price  # 1 cent worth
    order_data = {
        "currency_pair": "HIPPO_USDT",
        "type": "limit",
        "side": "buy",
        "amount": str(order_size),
        "price": str(price),
        "time_in_force": "ioc"
    }
    
    payload = json.dumps(order_data, separators=(",", ":"))
    timestamp = str(int(time.time()))
    
    # Create signature
    signature = create_signature("POST", "/spot/orders", "", payload, timestamp)
    
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "KEY": API_KEY,
        "Timestamp": timestamp,
        "SIGN": signature
    }
    
    print(f"🎯 Placing BUY order: {order_size:.6f} HIPPO @ ${price:.6f}")
    print(f"💰 Nominal value: ${order_size * price:.4f}")
    
    try:
        response = requests.post(
            "https://api.gateio.ws/api/v4/spot/orders",
            headers=headers,
            data=payload,
            timeout=10
        )
        
        print(f"📡 Order Response: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            order_id = result.get("id")
            print(f"✅ ORDER PLACED SUCCESSFULLY!")
            print(f"   Order ID: {order_id}")
            print(f"   🔊 Listen for Gate.io exchange sound!")
            return True
        else:
            error_text = response.text
            print(f"❌ Order failed: {error_text}")
            
            if "FORBIDDEN" in error_text:
                print(f"   🔒 IP not whitelisted yet")
            elif "INVALID_SIGNATURE" in error_text:
                print(f"   🔑 Signature issue")
            elif "INSUFFICIENT" in error_text:
                print(f"   💰 Insufficient balance")
            
            return False
            
    except Exception as e:
        print(f"❌ Order exception: {e}")
        return False

# Try to place order
if __name__ == "__main__":
    success = place_order()
    
    if success:
        print(f"\n🎉 SUCCESS! Real trading is working!")
    else:
        print(f"\n⚠️  Order failed - check IP whitelist on Gate.io")
