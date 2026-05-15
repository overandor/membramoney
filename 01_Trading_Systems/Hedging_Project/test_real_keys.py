#!/usr/bin/env python3
"""
Test Real API Keys with Working Signature Format
"""

import os
import requests
import hmac
import hashlib
import time
import json

# Your real API keys
API_KEY = "a2df70aecc3ce759f6e2372f4d2237c0"
API_SECRET = "c0cbd91461248490a1b0839f2dc609567bac51b96d843e34bcb0cd9e71c38775"

print("🚀 TESTING REAL API KEYS")
print("=" * 40)
print(f"API Key: {API_KEY[:10]}...")
print(f"API Secret: {API_SECRET[:10]}...")

def test_signature_format():
    """Test different signature formats"""
    
    base_url = "https://api.gateio.ws/api/v4"
    
    # Test formats
    formats = [
        ("Format 1: METHOD\\nPATH\\nHASH\\nTS", lambda method, path, payload, ts: f"{method.upper()}\n{path}\n{hashlib.sha512(payload.encode()).hexdigest()}\n{ts}"),
        ("Format 2: method\\npath\\nhash\\nts", lambda method, path, payload, ts: f"{method.lower()}\n{path}\n{hashlib.sha512(payload.encode()).hexdigest()}\n{ts}"),
        ("Format 3: METHOD\\nPATH\\nQUERY\\nHASH\\nTS", lambda method, path, payload, ts: f"{method.upper()}\n{path}\n\n{hashlib.sha512(payload.encode()).hexdigest()}\n{ts}"),
    ]
    
    for format_name, sign_func in formats:
        print(f"\n🔍 Testing {format_name}")
        
        try:
            timestamp = str(int(time.time()))
            payload = ""
            
            sign_str = sign_func("GET", "/spot/accounts", payload, timestamp)
            signature = hmac.new(API_SECRET.encode(), sign_str.encode(), hashlib.sha512).hexdigest()
            
            headers = {
                "Accept": "application/json",
                "Content-Type": "application/json",
                "KEY": API_KEY,
                "Timestamp": timestamp,
                "SIGN": signature
            }
            
            response = requests.get(f"{base_url}/spot/accounts", headers=headers, timeout=10)
            
            print(f"   Status: {response.status_code}")
            
            if response.status_code == 200:
                print(f"   ✅ SUCCESS! This format works!")
                accounts = response.json()
                for account in accounts:
                    if account.get("currency") == "USDT":
                        available = float(account.get("available", 0))
                        total = float(account.get("available", 0)) + float(account.get("frozen", 0))
                        print(f"   💰 YOUR BALANCE: ${available:.2f} available, ${total:.2f} total")
                        return True
            else:
                print(f"   ❌ Failed: {response.text}")
                
        except Exception as e:
            print(f"   ❌ Exception: {e}")
    
    return False

def test_public_endpoint():
    """Test public endpoint to verify API is reachable"""
    print(f"\n🔍 Testing Public Endpoint")
    
    try:
        response = requests.get("https://api.gateio.ws/api/v4/spot/tickers?currency_pair=HIPPO_USDT", timeout=10)
        
        if response.status_code == 200:
            ticker = response.json()[0]
            price = float(ticker["last"])
            volume = float(ticker["base_volume"])
            print(f"   ✅ HIPPO_USDT: ${price:.6f}, Volume: ${volume:,.0f}")
            return True
        else:
            print(f"   ❌ Public endpoint failed: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"   ❌ Public endpoint exception: {e}")
        return False

if __name__ == "__main__":
    # Test public endpoint first
    if test_public_endpoint():
        print(f"\n✅ Exchange is reachable!")
        
        # Test signature formats
        if test_signature_format():
            print(f"\n🎯 SUCCESS! Your API keys are working!")
            print(f"✅ Real exchange connection established!")
        else:
            print(f"\n❌ All signature formats failed")
            print(f"💡 Possible issues:")
            print(f"   - API keys are for testnet, not mainnet")
            print(f"   - API keys don't have spot trading permissions")
            print(f"   - Signature format still needs adjustment")
    else:
        print(f"\n❌ Cannot reach exchange")
