#!/usr/bin/env python3
"""
SIMPLE OLLAMA TESTER - Working Solution
Shows how to run Ollama and test it properly
"""

import subprocess
import time
import requests
import json
import os

def kill_existing_ollama():
    """Kill any existing Ollama processes"""
    print("🛑 Killing existing Ollama processes...")
    subprocess.run(['pkill', '-f', 'ollama'], capture_output=True)
    time.sleep(2)

def start_ollama_cpu_only():
    """Start Ollama in CPU-only mode"""
    print("🚀 Starting Ollama in CPU-only mode...")
    
    # Set environment variables for CPU-only mode
    env = {
        'OLLAMA_GPU': '0',
        'OLLAMA_NUM_PARALLEL': '1',
        'OLLAMA_MAX_QUEUE': '1'
    }
    
    # Start Ollama server
    process = subprocess.Popen(['/opt/homebrew/bin/ollama', 'serve'], 
                             env={**os.environ, **env},
                             stdout=subprocess.PIPE, 
                             stderr=subprocess.PIPE)
    
    print("⏳ Waiting for server to start...")
    time.sleep(8)
    
    return process

def test_simple_response():
    """Test a simple response"""
    print("🤖 Testing simple response...")
    
    payload = {
        "model": "qwen2.5:0.5b",
        "prompt": "Hello",
        "stream": False,
        "options": {
            "num_ctx": 512,
            "num_batch": 512,
            "temperature": 0.1
        }
    }
    
    try:
        response = requests.post("http://localhost:11434/api/generate", 
                               json=payload, timeout=60)
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ Response: {result.get('response', '').strip()}")
            return True
        else:
            print(f"❌ Error: {response.status_code}")
            print(f"Details: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Exception: {e}")
        return False

def main():
    print("🚀 SIMPLE OLLAMA TESTER")
    print("="*40)
    
    import os
    
    # Step 1: Kill existing processes
    kill_existing_ollama()
    
    # Step 2: Start Ollama CPU-only
    server_process = start_ollama_cpu_only()
    
    # Step 3: Test response
    if test_simple_response():
        print("\n🎉 SUCCESS! Ollama is working!")
        print("💡 You can now use this in your trading bot")
    else:
        print("\n❌ Ollama still having issues")
        print("💡 Alternative: Use a different AI service")
    
    print(f"\n📝 Server running (PID: {server_process.pid})")
    print("💡 Press Ctrl+C to stop")
    
    try:
        server_process.wait()
    except KeyboardInterrupt:
        print("\n🛑 Stopping server...")
        server_process.terminate()

if __name__ == "__main__":
    main()
