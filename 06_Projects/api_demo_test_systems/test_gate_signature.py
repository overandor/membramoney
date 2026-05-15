#!/usr/bin/env python3
"""
Test Gate.io API signature generation
"""

import os
import time
import hashlib
import hmac
import requests
import json

GATE_API_KEY = os.getenv("GATE_API_KEY", "")
GATE_API_SECRET = os.getenv("GATE_API_SECRET", "")

def test_signature_formats():
    print(f"API Key: {GATE_API_KEY}")
    print(f"Secret: {GATE_API_SECRET}")
    
    if not GATE_API_KEY or not GATE_API_SECRET:
        print("❌ Missing API credentials")
        return
    
    # Test different signature formats
    method = "GET"
    path = "/futures/usdt/accounts"
    query_string = ""
    payload = ""
    ts = str(int(time.time()))
    
    print(f"\n🔍 Testing signature formats...")
    print(f"Method: {method}")
    print(f"Path: {path}")
    print(f"Timestamp: {ts}")
    
    # Format 1: Original (from file)
    payload_hash1 = hashlib.sha512(payload.encode('utf-8')).hexdigest()
    sign_str1 = f"{method.upper()}\n{path}\n{query_string}\n{payload_hash1}\n{ts}"
    sign1 = hmac.new(
        GATE_API_SECRET.encode("utf-8"),
        sign_str1.encode("utf-8"),
        digestmod=hashlib.sha512,
    ).hexdigest()
    
    print(f"\nFormat 1 (Current):")
    print(f"Sign string: {repr(sign_str1)}")
    print(f"Signature: {sign1}")
    
    # Format 2: Alternative (without payload hash)
    sign_str2 = f"{method.upper()}\n{path}\n{query_string}\n{ts}"
    sign2 = hmac.new(
        GATE_API_SECRET.encode("utf-8"),
        sign_str2.encode("utf-8"),
        digestmod=hashlib.sha512,
    ).hexdigest()
    
    print(f"\nFormat 2 (No payload hash):")
    print(f"Sign string: {repr(sign_str2)}")
    print(f"Signature: {sign2}")
    
    # Test both formats
    headers1 = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "KEY": GATE_API_KEY,
        "Timestamp": ts,
        "SIGN": sign1,
    }
    
    headers2 = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "KEY": GATE_API_KEY,
        "Timestamp": ts,
        "SIGN": sign2,
    }
    
    url = "https://api.gateio.ws/api/v4/futures/usdt/accounts"
    
    print(f"\n🧪 Testing Format 1...")
    try:
        response = requests.get(url, headers=headers1)
        print(f"Status: {response.status_code}")
        print(f"Response: {response.text[:200]}")
    except Exception as e:
        print(f"Error: {e}")
    
    print(f"\n🧪 Testing Format 2...")
    try:
        response = requests.get(url, headers=headers2)
        print(f"Status: {response.status_code}")
        print(f"Response: {response.text[:200]}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_signature_formats()
