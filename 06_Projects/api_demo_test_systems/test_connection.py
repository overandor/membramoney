#!/usr/bin/env python3
"""
SIMPLE TEST SCRIPT - FOCUS ON:
1. Getting REAL Gate.io account balance
2. Connecting to Ollama
"""

import os
import requests
import subprocess
import time
import hmac
import hashlib
import aiohttp
import asyncio

# Your REAL Gate.io API credentials
GATE_API_KEY = os.getenv("GATE_API_KEY", "")
GATE_API_SECRET = os.getenv("GATE_API_SECRET", "")
GATE_BASE_URL = "https://api.gateio.ws"

# Ollama config
OLLAMA_URL = "http://localhost:11434"

def test_gateio_balance():
    """Test getting REAL account balance"""
    print("🔐 Testing Gate.io API Connection...")
    print(f"🔑 API Key: {GATE_API_KEY[:10]}...")
    print(f"🔑 API Secret: {GATE_API_SECRET[:10]}...")
    
    try:
        # Test with different signature methods
        print("\n🧪 Method 1: Simple timestamp signature...")
        
        timestamp = str(int(time.time()))
        endpoint = "/api/v4/spot/accounts"
        
        # Method 1: Simple signature (timestamp only)
        sign_string = f"{timestamp}GET{endpoint}"
        signature = hmac.new(
            GATE_API_SECRET.encode('utf-8'),
            sign_string.encode('utf-8'),
            hashlib.sha512
        ).hexdigest()
        
        headers = {
            'KEY': GATE_API_KEY,
            'Timestamp': timestamp,
            'SIGN': signature
        }
        
        url = f"{GATE_BASE_URL}{endpoint}"
        print(f"📡 Requesting: {url}")
        print(f"🔏 Signature string: {sign_string}")
        print(f"🔏 Signature: {signature[:20]}...")
        
        response = requests.get(url, headers=headers, timeout=10)
        print(f"📊 Response status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print("✅ SUCCESS! Account balance data:")
            for balance in data:
                currency = balance['currency']
                available = float(balance['available'])
                total = float(balance['total'])
                if total > 0:
                    print(f"  💰 {currency}: {total:.6f} (Available: {available:.6f})")
            
            # Calculate total USDT
            usdt_total = next((b['total'] for b in data if b['currency'] == 'USDT'), 0)
            print(f"\n💵 TOTAL USDT BALANCE: ${usdt_total}")
            return True
        else:
            print(f"❌ FAILED: {response.text}")
            
            # Try Method 2
            print("\n🧪 Method 2: Empty query string signature...")
            
            sign_string2 = f"{timestamp}GET{endpoint}"  # Same as method 1
            signature2 = hmac.new(
                GATE_API_SECRET.encode('utf-8'),
                sign_string2.encode('utf-8'),
                hashlib.sha512
            ).hexdigest()
            
            headers2 = {
                'KEY': GATE_API_KEY,
                'Timestamp': timestamp,
                'SIGN': signature2
            }
            
            response2 = requests.get(url, headers=headers2, timeout=10)
            print(f"📊 Method 2 Response status: {response2.status_code}")
            
            if response2.status_code == 200:
                print("✅ Method 2 SUCCESS!")
                return True
            else:
                print(f"❌ Method 2 FAILED: {response2.text}")
            
            return False
    
    except Exception as e:
        print(f"❌ ERROR: {e}")
        return False

def test_ollama_connection():
    """Test Ollama connection"""
    print("\n🤖 Testing Ollama Connection...")
    
    # Check if Ollama app exists
    if os.path.exists('/Applications/Ollama.app'):
        print("✅ Ollama app found in /Applications")
    else:
        print("❌ Ollama app not found")
        return False
    
    # Try to start Ollama service
    print("🚀 Starting Ollama service...")
    try:
        # Try different ways to start Ollama
        ollama_paths = [
            '/Applications/Ollama.app/Contents/MacOS/ollama',
            '/usr/local/bin/ollama',
            'ollama'
        ]
        
        ollama_started = False
        for ollama_path in ollama_paths:
            try:
                if ollama_path == 'ollama':
                    subprocess.run(['which', 'ollama'], check=True, capture_output=True)
                
                subprocess.Popen([ollama_path, 'serve'], 
                               stdout=subprocess.DEVNULL, 
                               stderr=subprocess.DEVNULL)
                print(f"✅ Ollama service started with: {ollama_path}")
                ollama_started = True
                break
            except (subprocess.CalledProcessError, FileNotFoundError):
                continue
        
        if not ollama_started:
            print("❌ Could not start Ollama service")
            print("💡 Please start Ollama manually: Open the Ollama app")
            return False
        
        # Wait for service to start
        print("⏳ Waiting for Ollama service to start...")
        time.sleep(5)
        
        # Test connection
        print("🔗 Testing Ollama API connection...")
        response = requests.get(f"{OLLAMA_URL}/api/tags", timeout=10)
        
        if response.status_code == 200:
            models = response.json().get('models', [])
            model_names = [m['name'] for m in models]
            print(f"✅ Ollama connected! Available models: {model_names}")
            
            # Test a simple generation
            if model_names:
                test_model = model_names[0]
                print(f"🧪 Testing model: {test_model}")
                
                payload = {
                    "model": test_model,
                    "prompt": "Say 'Hello from Ollama!'",
                    "stream": False
                }
                
                response = requests.post(f"{OLLAMA_URL}/api/generate", 
                                       json=payload, timeout=30)
                
                if response.status_code == 200:
                    result = response.json()
                    print(f"✅ Model response: {result.get('response', '').strip()}")
                    return True
                else:
                    print(f"❌ Model test failed: {response.status_code}")
            
            return True
        else:
            print(f"❌ Ollama API not responding: {response.status_code}")
            return False
    
    except Exception as e:
        print(f"❌ Ollama error: {e}")
        return False

def main():
    print("🚀 SIMPLE CONNECTION TEST")
    print("="*50)
    print("1. Testing Gate.io Balance")
    print("2. Testing Ollama Connection")
    print("="*50)
    
    # Test Gate.io balance
    gateio_success = test_gateio_balance()
    
    # Test Ollama
    ollama_success = test_ollama_connection()
    
    print("\n" + "="*50)
    print("📊 RESULTS:")
    print(f"Gate.io Balance: {'✅ SUCCESS' if gateio_success else '❌ FAILED'}")
    print(f"Ollama Connection: {'✅ SUCCESS' if ollama_success else '❌ FAILED'}")
    
    if gateio_success and ollama_success:
        print("\n🎉 BOTH SYSTEMS WORKING! Ready for trading!")
    elif gateio_success:
        print("\n💰 Gate.io works - Start Ollama manually to enable AI trading")
    elif ollama_success:
        print("\n🤖 Ollama works - Fix Gate.io API to enable real trading")
    else:
        print("\n❌ Both systems need fixing")

if __name__ == "__main__":
    main()
