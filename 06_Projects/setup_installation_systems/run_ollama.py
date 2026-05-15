#!/usr/bin/env python3
import os
"""
OLLAMA RUNNER - Step by Step Guide
Shows exactly how to run Ollama and test it
"""

import subprocess
import time
import requests
import json

def step1_check_ollama_installation():
    """Step 1: Check if Ollama is installed"""
    print("🔍 STEP 1: Checking Ollama installation...")
    
    # Check different paths
    paths = [
        '/opt/homebrew/bin/ollama',
        '/Applications/Ollama.app/Contents/MacOS/ollama',
        'ollama'
    ]
    
    ollama_path = None
    for path in paths:
        try:
            if path == 'ollama':
                result = subprocess.run(['which', 'ollama'], capture_output=True, text=True)
                if result.returncode == 0:
                    ollama_path = 'ollama'
                    break
            else:
                if subprocess.run(['test', '-f', path]).returncode == 0:
                    ollama_path = path
                    break
        except:
            continue
    
    if ollama_path:
        print(f"✅ Found Ollama at: {ollama_path}")
        return ollama_path
    else:
        print("❌ Ollama not found")
        return None

def step2_start_ollama_server(ollama_path):
    """Step 2: Start Ollama server"""
    print("\n🚀 STEP 2: Starting Ollama server...")
    
    try:
        # Start Ollama server in background
        process = subprocess.Popen([ollama_path, 'serve'], 
                                 stdout=subprocess.PIPE, 
                                 stderr=subprocess.PIPE)
        
        print("✅ Ollama server starting...")
        print("⏳ Waiting 5 seconds for server to be ready...")
        time.sleep(5)
        
        return process
    except Exception as e:
        print(f"❌ Failed to start server: {e}")
        return None

def step3_check_server_status():
    """Step 3: Check if server is responding"""
    print("\n🔗 STEP 3: Checking server status...")
    
    try:
        response = requests.get("http://localhost:11434/api/tags", timeout=5)
        if response.status_code == 200:
            models = response.json().get('models', [])
            model_names = [m['name'] for m in models]
            print(f"✅ Server is running! Available models: {model_names}")
            return model_names
        else:
            print(f"❌ Server not responding: {response.status_code}")
            return []
    except Exception as e:
        print(f"❌ Cannot connect to server: {e}")
        return []

def step4_test_simple_prompt(model_name):
    """Step 4: Test simple prompt"""
    print(f"\n🤖 STEP 4: Testing {model_name} with simple prompt...")
    
    payload = {
        "model": model_name,
        "prompt": "Hello! Please say 'I am working correctly!' in exactly one sentence.",
        "stream": False
    }
    
    try:
        print("📤 Sending prompt...")
        response = requests.post("http://localhost:11434/api/generate", 
                               json=payload, timeout=30)
        
        if response.status_code == 200:
            result = response.json()
            response_text = result.get('response', '').strip()
            print(f"📥 Model Response: {response_text}")
            print("✅ SUCCESS! Model is working!")
            return True
        else:
            print(f"❌ Error: {response.status_code} - {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def step5_test_trading_prompt(model_name):
    """Step 5: Test trading prompt"""
    print(f"\n📊 STEP 5: Testing {model_name} with trading analysis...")
    
    payload = {
        "model": model_name,
        "prompt": """
Analyze this cryptocurrency for trading:

COIN: VADER
PRICE: $0.001007  
CHANGE: -10.72%
VOLUME: $11,136

MICRO-CAP TRADING STRATEGY:
- Coins under $0.10
- Look for pumps (+5%+) and dumps (-5%-)
- High volatility = opportunity

DECISION: Should I BUY, SELL, or HOLD?
Respond with only one word: BUY, SELL, or HOLD
""",
        "stream": False
    }
    
    try:
        print("📤 Sending trading analysis prompt...")
        response = requests.post("http://localhost:11434/api/generate", 
                               json=payload, timeout=30)
        
        if response.status_code == 200:
            result = response.json()
            decision = result.get('response', '').strip().upper()
            print(f"📥 Trading Decision: {decision}")
            print("✅ Trading analysis complete!")
            return decision
        else:
            print(f"❌ Error: {response.status_code}")
            return "HOLD"
            
    except Exception as e:
        print(f"❌ Error: {e}")
        return "HOLD"

def main():
    print("🚀 OLLAMA RUNNER - STEP BY STEP GUIDE")
    print("="*60)
    
    # Step 1: Check installation
    ollama_path = step1_check_ollama_installation()
    if not ollama_path:
        print("\n❌ Please install Ollama first:")
        print("brew install ollama")
        return
    
    # Step 2: Start server
    server_process = step2_start_ollama_server(ollama_path)
    if not server_process:
        return
    
    # Step 3: Check server
    models = step3_check_server_status()
    if not models:
        print("\n❌ Server not ready. Waiting 10 more seconds...")
        time.sleep(10)
        models = step3_check_server_status()
        if not models:
            print("❌ Server still not responding")
            return
    
    # Step 4: Test simple prompt
    working_model = None
    for model in models:
        if step4_test_simple_prompt(model):
            working_model = model
            break
    
    if not working_model:
        print("\n❌ No models are working")
        return
    
    # Step 5: Test trading prompt
    decision = step5_test_trading_prompt(working_model)
    
    print("\n" + "="*60)
    print("🎉 OLLAMA SETUP COMPLETE!")
    print(f"✅ Working Model: {working_model}")
    print(f"📊 Trading Decision: {decision}")
    print("🚀 Ready for trading bot integration!")
    
    # Keep server running
    print(f"\n💡 Ollama server is running (PID: {server_process.pid})")
    print("💡 Press Ctrl+C to stop the server")
    
    try:
        server_process.wait()
    except KeyboardInterrupt:
        print("\n🛑 Stopping Ollama server...")
        server_process.terminate()
        print("✅ Server stopped")

if __name__ == "__main__":
    main()
