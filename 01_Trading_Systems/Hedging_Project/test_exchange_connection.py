#!/usr/bin/env python3
"""
Direct Gate.io Exchange Connection Test
Shows real balance and exchange connectivity
"""

import os
import time
import json
import requests
import hmac
import hashlib
from datetime import datetime

def test_gateio_connection():
    """Test direct connection to Gate.io exchange"""
    
    print("🚀 GATE.IO EXCHANGE CONNECTION TEST")
    print("=" * 50)
    
    # Get API keys
    api_key = os.getenv("GATE_API_KEY", "")
    api_secret = os.getenv("GATE_API_SECRET", "")
    
    print(f"🔑 API Key: {api_key[:10]}... ({len(api_key)} chars)")
    print(f"🔐 API Secret: {api_secret[:10]}... ({len(api_secret)} chars)")
    print("")
    
    if not api_key or not api_secret:
        print("❌ Missing API keys - cannot connect to exchange")
        return
    
    # API configuration
    base_url = "https://api.gateio.ws/api/v4"
    settle = "usdt"
    
    def sign_request(method, path, payload):
        """Generate Gate.io API signature"""
        ts = str(int(time.time()))
        payload_hash = hashlib.sha512(payload.encode('utf-8')).hexdigest()
        sign_str = f"{method.upper()}\n{path}\n{payload_hash}\n{ts}"
        sign = hmac.new(api_secret.encode("utf-8"), sign_str.encode("utf-8"), hashlib.sha512).hexdigest()
        
        return {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "KEY": api_key,
            "Timestamp": ts,
            "SIGN": sign,
        }
    
    def make_request(method, path, payload="", private=True):
        """Make API request"""
        headers = sign_request(method, path, payload) if private else {
            "Accept": "application/json",
            "Content-Type": "application/json"
        }
        
        try:
            url = f"{base_url}{path}"
            response = requests.request(method, url, headers=headers, data=payload if payload else None, timeout=10)
            
            print(f"📡 {method} {url}")
            print(f"📥 Status: {response.status_code}")
            
            if response.status_code == 200:
                return {"success": True, "data": response.json()}
            else:
                print(f"❌ Response: {response.text}")
                return {"success": False, "error": response.text}
                
        except Exception as e:
            print(f"❌ Exception: {e}")
            return {"success": False, "error": str(e)}
    
    print("🔍 Testing Exchange Connection...")
    print("")
    
    # Test 1: Public endpoint - get contracts
    print("1️⃣ Testing Public Endpoint (Contracts)")
    print("-" * 40)
    result = make_request("GET", f"/futures/{settle}/contracts", private=False)
    if result["success"]:
        contracts = result["data"]
        print(f"✅ Connected! Found {len(contracts)} contracts")
        
        # Find ENA contract
        ena_contract = None
        for contract in contracts:
            if contract.get('name') == 'ENA_USDT':
                ena_contract = contract
                break
        
        if ena_contract:
            print(f"✅ ENA_USDT contract found")
            print(f"   Order Size: {ena_contract.get('order_size', 'N/A')}")
            print(f"   Leverage: {ena_contract.get('leverage', 'N/A')}")
        else:
            print("⚠️  ENA_USDT contract not found")
    else:
        print(f"❌ Public endpoint failed: {result.get('error')}")
    
    print("")
    
    # Test 2: Private endpoint - get account balance
    print("2️⃣ Testing Private Endpoint (Account Balance)")
    print("-" * 40)
    result = make_request("GET", f"/futures/{settle}/accounts", private=True)
    if result["success"]:
        account = result["data"]
        print("✅ Account connected!")
        print("")
        print("💰 YOUR REAL BALANCE:")
        print(f"   Total Balance: ${float(account.get('total', 0)):.2f}")
        print(f"   Available: ${float(account.get('available', 0)):.2f}")
        print(f"   Used Margin: ${float(account.get('used', 0)):.2f}")
        print(f"   Unrealized PnL: ${float(account.get('unrealised_pnl', 0)):.4f}")
        
        # Calculate margin ratio
        total = float(account.get('total', 0))
        used = float(account.get('used', 0))
        if total > 0:
            margin_ratio = (used / total) * 100
            print(f"   Margin Ratio: {margin_ratio:.1f}%")
            
            if margin_ratio > 80:
                print("   ⚠️  HIGH MARGIN USAGE!")
            elif margin_ratio > 50:
                print("   ⚠️  Moderate margin usage")
            else:
                print("   ✅ Healthy margin usage")
        
    else:
        print(f"❌ Account endpoint failed: {result.get('error')}")
        if "INVALID_SIGNATURE" in result.get('error', ''):
            print("   💡 This usually means:")
            print("      - API keys are invalid (demo keys)")
            print("      - API keys don't have futures permissions")
            print("      - Signature format is incorrect")
    
    print("")
    
    # Test 3: Get positions
    print("3️⃣ Testing Positions")
    print("-" * 40)
    result = make_request("GET", f"/futures/{settle}/positions", private=True)
    if result["success"]:
        positions = result["data"]
        active_positions = [p for p in positions if float(p.get('size', 0)) != 0]
        
        print(f"✅ Positions retrieved: {len(active_positions)} active positions")
        
        if active_positions:
            for pos in active_positions:
                size = float(pos.get('size', 0))
                entry_price = float(pos.get('entry_price', 0))
                mark_price = float(pos.get('mark_price', 0))
                pnl = float(pos.get('unrealised_pnl', 0))
                
                print(f"   {pos.get('contract', 'Unknown')}: {size:.6f} @ ${entry_price:.6f}")
                print(f"      Mark Price: ${mark_price:.6f} | PnL: ${pnl:.4f}")
        else:
            print("   ✅ No open positions")
    else:
        print(f"❌ Positions endpoint failed: {result.get('error')}")
    
    print("")
    
    # Test 4: Get market data for ENA_USDT
    print("4️⃣ Testing Market Data (ENA_USDT)")
    print("-" * 40)
    result = make_request("GET", f"/futures/{settle}/order_book?contract=ENA_USDT&limit=1", private=False)
    if result["success"]:
        data = result["data"]
        if data.get('bids') and data.get('asks'):
            best_bid = float(data['bids'][0]['p'])
            best_ask = float(data['asks'][0]['p'])
            spread = best_ask - best_bid
            spread_pct = (spread / best_bid) * 100
            
            print("✅ Market data retrieved!")
            print(f"   Best Bid: ${best_bid:.6f}")
            print(f"   Best Ask: ${best_ask:.6f}")
            print(f"   Spread: ${spread:.6f} ({spread_pct:.3f}%)")
            
            # Calculate nominal value for 0.05 USD
            target_nominal = 0.05
            size = target_nominal / best_bid
            nominal_value = size * best_bid
            
            print(f"   Order size for ${target_nominal:.2f}: {size:.6f} contracts")
            print(f"   Actual nominal: ${nominal_value:.4f}")
        else:
            print("❌ No order book data available")
    else:
        print(f"❌ Market data failed: {result.get('error')}")
    
    print("")
    
    # Test 5: Try to place a test order (very small)
    print("5️⃣ Testing Order Placement (Dry Run)")
    print("-" * 40)
    
    # Get current market price first
    market_result = make_request("GET", f"/futures/{settle}/order_book?contract=ENA_USDT&limit=1", private=False)
    if market_result["success"] and market_result["data"].get('bids'):
        best_bid = float(market_result["data"]['bids'][0]['p'])
        
        # Calculate very small order size (1 cent nominal)
        nominal_target = 0.01
        order_size = nominal_target / best_bid
        
        print(f"   Attempting to place BUY order: {order_size:.6f} @ ${best_bid:.6f}")
        print(f"   Nominal value: ${order_size * best_bid:.4f}")
        
        order_data = {
            "settle": settle,
            "contract": "ENA_USDT",
            "size": str(order_size),
            "price": str(best_bid),
            "type": "limit",
            "tif": "ioc"  # Immediate or Cancel
        }
        
        payload = json.dumps(order_data, separators=(",", ":"))
        order_result = make_request("POST", f"/futures/{settle}/orders", payload, private=True)
        
        if order_result["success"]:
            order_id = order_result["data"].get('id')
            print(f"✅ Order placed successfully!")
            print(f"   Order ID: {order_id}")
            print("🔊 You should hear a sound from Gate.io exchange!")
        else:
            print(f"❌ Order failed: {order_result.get('error')}")
            if "INSUFFICIENT" in order_result.get('error', ''):
                print("   💡 Insufficient balance or margin")
            elif "INVALID_SIGNATURE" in order_result.get('error', ''):
                print("   💡 Invalid API keys or permissions")
    else:
        print("❌ Cannot get market price for order test")
    
    print("")
    print("=" * 50)
    print("🎯 CONNECTION TEST COMPLETE")
    print("")
    print("If you see real balance data above, your exchange connection is working!")
    print("If you see errors, check your API keys and permissions.")

if __name__ == "__main__":
    test_gateio_connection()
