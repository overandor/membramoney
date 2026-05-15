#!/usr/bin/env python3
import os
"""
DEEPSEEK MODEL TESTER
Test your DeepSeek-R1 model with simple prompts
"""

import requests
import json

def test_deepseek():
    """Test DeepSeek-R1 model"""
    print("🤖 Testing DeepSeek-R1 Model...")
    
    # Check if Ollama is running
    try:
        response = requests.get("http://localhost:11434/api/tags", timeout=5)
        if response.status_code == 200:
            models = response.json().get('models', [])
            model_names = [m['name'] for m in models]
            print(f"✅ Available models: {model_names}")
            
            if 'llama3.2:1b' in model_names:
                print("🧪 Testing Llama 3.2 1B (working model)...")
                model_to_test = "llama3.2:1b"
            elif 'deepseek-r1:latest' in model_names:
                print("🧪 Testing DeepSeek-R1 with a simple prompt...")
                model_to_test = "deepseek-r1:latest"
            else:
                print("❌ No suitable models found")
                return False
            
            # Simple test prompt
            payload = {
                "model": model_to_test,
                "prompt": "Say 'Hello from AI!' in one sentence.",
                "stream": False
            }
            
            try:
                response = requests.post("http://localhost:11434/api/generate", 
                                       json=payload, timeout=30)
                
                if response.status_code == 200:
                    result = response.json()
                    print(f"✅ Model Response: {result.get('response', '').strip()}")
                    return True
                else:
                    print(f"❌ Model Error: {response.status_code} - {response.text}")
                    return False
                    
            except requests.exceptions.Timeout:
                print("❌ Model timeout - model might be loading...")
                return False
            except Exception as e:
                print(f"❌ Model error: {e}")
                return False
        else:
            print(f"❌ Ollama not responding: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ Cannot connect to Ollama: {e}")
        return False

def test_trading_prompt():
    """Test DeepSeek with a trading prompt"""
    print("\n📊 Testing DeepSeek with trading analysis...")
    
    payload = {
        "model": "deepseek-r1:latest",
        "prompt": """
Analyze this micro-cap cryptocurrency:

COIN: VADER
PRICE: $0.001007
24h CHANGE: -10.72%
VOLUME: $11,136

TRADING STRATEGY:
- Micro-cap coins under $0.10
- Look for pumps (+5%+) and dumps (-5%-)
- Consider volume and momentum
- High volatility = high opportunity

DECISION: Should I BUY, SELL, or HOLD this coin?
Respond with only: BUY, SELL, or HOLD
""",
        "stream": False
    }
    
    try:
        response = requests.post("http://localhost:11434/api/generate", 
                               json=payload, timeout=30)
        
        if response.status_code == 200:
            result = response.json()
            decision = result.get('response', '').strip()
            print(f"🤖 DeepSeek Trading Decision: {decision}")
            return decision
        else:
            print(f"❌ Trading analysis error: {response.status_code}")
            return "HOLD"
            
    except Exception as e:
        print(f"❌ Trading analysis error: {e}")
        return "HOLD"

if __name__ == "__main__":
    print("🚀 DEEPSEEK MODEL TESTER")
    print("="*50)
    
    # Test basic connection
    if test_deepseek():
        print("\n✅ DeepSeek is working!")
        
        # Test trading prompt
        decision = test_trading_prompt()
        
        print(f"\n🎯 Final Decision: {decision}")
        print("💡 DeepSeek is ready for trading!")
        
    else:
        print("\n❌ DeepSeek test failed")
        print("💡 Try starting Ollama: 'ollama serve'")
        print("💡 Or use a lighter model: 'ollama pull llama3.2:1b'")
