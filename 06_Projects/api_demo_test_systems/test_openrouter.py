#!/usr/bin/env python3
"""
Test OpenRouter API key and create AI trading supervisor
"""

import os
import requests
import json

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")

def test_openrouter_api():
    """Test OpenRouter API connection"""
    print("🧪 Testing OpenRouter API...")
    print(f"API Key: {OPENROUTER_API_KEY[:20]}...")
    
    if not OPENROUTER_API_KEY:
        print("❌ Missing OPENROUTER_API_KEY")
        return False
    
    try:
        # Test with a simple request
        headers = {
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/alep/trading-bot",
            "X-Title": "Trading Bot AI"
        }
        
        data = {
            "model": "anthropic/claude-3-haiku",
            "messages": [
                {"role": "user", "content": "Say 'OpenRouter API is working!' in exactly those words."}
            ],
            "max_tokens": 50
        }
        
        response = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers=headers,
            json=data,
            timeout=10
        )
        
        print(f"Status: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            message = result["choices"][0]["message"]["content"]
            print(f"✅ Response: {message}")
            return True
        else:
            print(f"❌ Error: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Exception: {e}")
        return False

def list_available_models():
    """List available models on OpenRouter"""
    print("\n📋 Available Models:")
    
    try:
        headers = {
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
            "Content-Type": "application/json"
        }
        
        response = requests.get(
            "https://openrouter.ai/api/v1/models",
            headers=headers,
            timeout=10
        )
        
        if response.status_code == 200:
            models = response.json()["data"]
            
            # Show some good models for trading
            trading_models = [
                "anthropic/claude-3-haiku",
                "anthropic/claude-3-sonnet", 
                "openai/gpt-4o-mini",
                "google/gemini-flash-1.5",
                "meta-llama/llama-3.1-8b-instruct"
            ]
            
            for model in trading_models:
                model_info = next((m for m in models if m["id"] == model), None)
                if model_info:
                    pricing = model_info.get("pricing", {})
                    prompt_price = pricing.get("prompt", "N/A")
                    print(f"  ✅ {model}: ${prompt_price}/1K tokens")
                else:
                    print(f"  ❓ {model}: Not found")
                    
        else:
            print(f"❌ Failed to get models: {response.text}")
            
    except Exception as e:
        print(f"❌ Exception: {e}")

if __name__ == "__main__":
    success = test_openrouter_api()
    if success:
        list_available_models()
        print("\n🚀 OpenRouter API is ready for AI trading!")
    else:
        print("\n❌ OpenRouter API test failed")
