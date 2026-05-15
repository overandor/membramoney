#!/usr/bin/env python3
"""
Check if API keys are for testnet or mainnet
"""

import os
import requests
import hmac
import hashlib
import time

# Your API keys
API_KEY = "a2df70aecc3ce759f6e2372f4d2237c0"
API_SECRET = "c0cbd91461248490a1b0839f2dc609567bac51b96d843e34bcb0cd9e71c38775"

print("🔍 CHECKING API KEY TYPE")
print("=" * 40)

def test_endpoint(base_url, name):
    """Test different endpoints"""
    print(f"\n🌐 Testing {name}: {base_url}")
    
    # Test public endpoint
    try:
        response = requests.get(f"{base_url}/spot/tickers?currency_pair=BTC_USDT", timeout=10)
        if response.status_code == 200:
            ticker = response.json()[0]
            print(f"   ✅ Public endpoint works")
            print(f"   BTC_USDT: ${float(ticker['last']):.2f}")
        else:
            print(f"   ❌ Public endpoint failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"   ❌ Public endpoint exception: {e}")
        return False
    
    # Test private endpoint with different signature formats
    endpoints_to_test = [
        ("/spot/accounts", "Accounts"),
        ("/spot/wallet", "Wallet"),
    ]
    
    for endpoint, desc in endpoints_to_test:
        print(f"   📡 Testing {desc} endpoint...")
        
        # Try multiple signature formats
        formats = [
            ("Standard", lambda ts, payload: f"GET\n{endpoint}\n{hashlib.sha512(payload.encode()).hexdigest()}\n{ts}"),
            ("With Query", lambda ts, payload: f"GET\n{endpoint}\n\n{hashlib.sha512(payload.encode()).hexdigest()}\n{ts}"),
            ("Lowercase", lambda ts, payload: f"get\n{endpoint}\n{hashlib.sha512(payload.encode()).hexdigest()}\n{ts}"),
        ]
        
        for format_name, sign_func in formats:
            timestamp = str(int(time.time()))
            payload = ""
            
            sign_str = sign_func(timestamp, payload)
            signature = hmac.new(API_SECRET.encode(), sign_str.encode(), hashlib.sha512).hexdigest()
            
            headers = {
                "Accept": "application/json",
                "Content-Type": "application/json",
                "KEY": API_KEY,
                "Timestamp": timestamp,
                "SIGN": signature
            }
            
            try:
                response = requests.get(f"{base_url}{endpoint}", headers=headers, timeout=10)
                
                if response.status_code == 200:
                    print(f"      ✅ {format_name} format works!")
                    if desc == "Accounts":
                        accounts = response.json()
                        for account in accounts:
                            if account.get("currency") == "USDT":
                                available = float(account.get("available", 0))
                                print(f"      💰 USDT Balance: ${available:.2f}")
                    return True
                elif "INVALID_SIGNATURE" not in response.text:
                    print(f"      ⚠️  {format_name}: {response.status_code} - {response.text[:100]}")
                
            except Exception as e:
                print(f"      ❌ {format_name}: {e}")
    
    return False

# Test different endpoints
endpoints = [
    ("https://api.gateio.ws/api/v4", "Mainnet"),
    ("https://api.gateio.ws/api/v4", "Mainnet (alternative path)"),
    ("https://fx-api.gateio.ws/api/v4", "Futures API"),
    ("https://api.gateio.ws", "Root API"),
]

success = False
for base_url, name in endpoints:
    if test_endpoint(base_url, name):
        success = True
        break

if not success:
    print(f"\n❌ No endpoint worked with these API keys")
    print(f"\n💡 Possible issues:")
    print(f"   1. API keys are for testnet (different URL)")
    print(f"   2. API keys don't have spot trading permissions")
    print(f"   3. API keys are expired or revoked")
    print(f"   4. Need different signature format")
    
    print(f"\n🔧 Try these solutions:")
    print(f"   1. Check Gate.io API settings for permissions")
    print(f"   2. Generate new API keys with 'Spot Trading' permission")
    print(f"   3. Verify keys are for 'Mainnet' not 'Testnet'")
    print(f"   4. Check if IP whitelist is blocking requests")
