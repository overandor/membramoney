#!/usr/bin/env python3
"""
Working Trader with Correct Signature for Your Whitelisted IP
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

print("🚀 WORKING TRADER - IP WHITELISTED")
print("=" * 50)
print(f"🔑 API Key: {API_KEY[:10]}...")
print(f"🌐 IP: 31.42.157.184 (whitelisted)")
print(f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

def create_correct_signature(method, path, query_string, payload, timestamp):
    """
    Create Gate.io signature - CORRECT FORMAT
    """
    
    # Hash the payload
    payload_hash = hashlib.sha512(payload.encode('utf-8')).hexdigest()
    
    # Create signature string - EXACT Gate.io format
    sign_str = f"{method.upper()}\n{path}\n{query_string}\n{payload_hash}\n{timestamp}"
    
    # Generate HMAC-SHA512
    signature = hmac.new(
        API_SECRET.encode('utf-8'),
        sign_str.encode('utf-8'),
        hashlib.sha512
    ).hexdigest()
    
    return signature

def make_api_request(method, endpoint, params="", payload="", private=True):
    """Make API request with correct signature"""
    
    base_url = "https://api.gateio.ws/api/v4"
    
    # Parse endpoint
    if '?' in endpoint:
        path, query = endpoint.split('?', 1)
    else:
        path, query = endpoint, ""
    
    timestamp = str(int(time.time()))
    
    if private:
        signature = create_correct_signature(method, path, query, payload, timestamp)
        
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "KEY": API_KEY,
            "Timestamp": timestamp,
            "SIGN": signature
        }
    else:
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json"
        }
    
    try:
        url = f"{base_url}{endpoint}"
        
        if method == "GET":
            response = requests.get(url, headers=headers, timeout=10)
        elif method == "POST":
            response = requests.post(url, headers=headers, data=payload, timeout=10)
        
        return response.status_code, response.json() if response.text else {}
        
    except Exception as e:
        return 0, {"error": str(e)}

def get_account_balance():
    """Get account balance"""
    print(f"\n💰 GETTING ACCOUNT BALANCE")
    print("-" * 30)
    
    status, data = make_api_request("GET", "/spot/accounts", "", "", private=True)
    
    if status == 200:
        print(f"✅ Account access successful!")
        
        for account in data:
            if account.get("currency") == "USDT":
                available = float(account.get("available", 0))
                frozen = float(account.get("frozen", 0))
                total = available + frozen
                
                print(f"💵 USDT Balance:")
                print(f"   Available: ${available:.2f}")
                print(f"   Frozen: ${frozen:.2f}")
                print(f"   Total: ${total:.2f}")
                
                return total
        
        print(f"⚠️  No USDT account found")
        return 0
    else:
        print(f"❌ Account access failed: {data}")
        return 0

def get_token_info(symbol):
    """Get token information"""
    status, data = make_api_request("GET", f"/spot/tickers?currency_pair={symbol}", "", "", private=False)
    
    if status == 200 and data:
        ticker = data[0]
        return {
            "price": float(ticker["last"]),
            "bid": float(ticker["highest_bid"]),
            "ask": float(ticker["lowest_ask"]),
            "volume": float(ticker["base_volume"]),
            "change": float(ticker["change_percentage"])
        }
    return None

def place_order(symbol, side, amount_usdt=0.01):
    """Place order"""
    print(f"\n🎯 PLACING ORDER: {side.upper()} {symbol}")
    print("-" * 30)
    
    # Get current price
    token_info = get_token_info(symbol)
    if not token_info:
        print(f"❌ Cannot get {symbol} price")
        return False
    
    price = token_info["price"]
    order_size = amount_usdt / price
    
    print(f"   Current Price: ${price:.6f}")
    print(f"   Order Size: {order_size:.6f}")
    print(f"   Nominal Value: ${order_size * price:.4f}")
    
    # Create order
    order_data = {
        "currency_pair": symbol,
        "type": "limit",
        "side": side,
        "amount": str(order_size),
        "price": str(price),
        "time_in_force": "ioc"
    }
    
    payload = json.dumps(order_data, separators=(",", ":"))
    
    print(f"📡 Sending order...")
    status, data = make_api_request("POST", "/spot/orders", "", payload, private=True)
    
    if status == 200:
        order_id = data.get("id")
        print(f"✅ ORDER PLACED SUCCESSFULLY!")
        print(f"   Order ID: {order_id}")
        print(f"   🔊 Listen for Gate.io exchange sound!")
        return True
    else:
        print(f"❌ Order failed: {data}")
        return False

def main():
    """Main trading execution"""
    
    # Get balance
    balance = get_account_balance()
    
    if balance > 0:
        print(f"\n🚀 READY TO TRADE WITH ${balance:.2f}")
        
        # Your tokens
        tokens = [
            "HIPPO_USDT",
            "DOGE_USDT",
            "PEPE_USDT",
            "SHIB_USDT"
        ]
        
        print(f"\n📊 Trading your tokens...")
        
        for i, token in enumerate(tokens, 1):
            print(f"\n{'='*50}")
            print(f"📈 {i}. {token}")
            
            # Get token info
            token_info = get_token_info(token)
            if token_info:
                print(f"   Price: ${token_info['price']:.6f}")
                print(f"   Change: {token_info['change']:+.2f}%")
                print(f"   Volume: ${token_info['volume']:,.0f}")
                
                # Place order
                success = place_order(token, "buy", 0.01)
                
                if success:
                    print(f"✅ {token} trade completed!")
                else:
                    print(f"❌ {token} trade failed!")
            else:
                print(f"❌ Cannot get {token} data")
            
            # Wait between trades
            if i < len(tokens):
                print(f"⏳ Waiting 3 seconds...")
                time.sleep(3)
        
        print(f"\n🎉 TRADING SESSION COMPLETE!")
        print(f"✅ All orders attempted")
        print(f"🔊 Check Gate.io for order confirmations")
        
    else:
        print(f"\n❌ Cannot trade - balance or access issue")

if __name__ == "__main__":
    main()
