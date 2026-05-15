#!/usr/bin/env python3
import os
"""
Simple API Demo - Show working Gate.io API connection
"""

import requests
import json
import hmac
import hashlib
import time

# API Configuration
GATE_API_KEY = os.getenv("GATE_API_KEY", "")
GATE_API_SECRET = os.getenv("GATE_API_SECRET", "")
BASE_URL = "https://api.gateio.ws"

def create_signature(method, path, query_string, payload, timestamp):
    """Create Gate.io API signature"""
    payload_hash = hashlib.sha512(payload.encode('utf-8')).hexdigest()
    sign_str = f"{method}\n{path}\n{query_string}\n{payload_hash}\n{timestamp}"
    signature = hmac.new(
        GATE_API_SECRET.encode('utf-8'),
        sign_str.encode('utf-8'),
        hashlib.sha512
    ).hexdigest()
    return signature

def make_private_request(method, endpoint, payload=""):
    """Make private API request"""
    timestamp = str(int(time.time()))
    signature = create_signature(method, endpoint, "", payload, timestamp)
    
    headers = {
        'Content-Type': 'application/json',
        'Accept': 'application/json',
        'KEY': GATE_API_KEY,
        'Timestamp': timestamp,
        'SIGN': signature
    }
    
    url = f"{BASE_URL}{endpoint}"
    
    try:
        if method == 'GET':
            response = requests.get(url, headers=headers)
        elif method == 'POST':
            response = requests.post(url, headers=headers, data=payload)
        
        return response.json() if response.status_code == 200 else None
    except Exception as e:
        print(f"Request error: {e}")
        return None

def test_api_connection():
    """Test API connection and show account info"""
    print("🔑 GATE.IO API CONNECTION TEST")
    print("=" * 40)
    
    # Test account balance
    print("💰 Testing account balance...")
    balance_data = make_private_request('GET', '/api/v4/futures/usdt/accounts')
    
    if balance_data:
        print("✅ API Connection Successful!")
        print(f"   Available: ${float(balance_data['available']):.2f}")
        print(f"   Total: ${float(balance_data['total']):.2f}")
        return True
    else:
        print("❌ API Connection Failed")
        return False

def get_order_book():
    """Get ENA_USDT order book"""
    print("\n📊 Getting ENA_USDT Order Book...")
    
    # Public endpoint - no signature needed
    url = f"{BASE_URL}/api/v4/futures/usdt/order_book?contract=ENA_USDT&limit=5"
    
    try:
        response = requests.get(url)
        if response.status_code == 200:
            data = response.json()
            
            if 'bids' in data and 'asks' in data and data['bids'] and data['asks']:
                best_bid = float(data['bids'][0][0])
                best_ask = float(data['asks'][0][0])
                mid_price = (best_bid + best_ask) / 2
                spread_bps = (best_ask - best_bid) / mid_price * 10000
                
                print(f"✅ Order Book Retrieved:")
                print(f"   Best Bid: ${best_bid:.4f}")
                print(f"   Best Ask: ${best_ask:.4f}")
                print(f"   Mid Price: ${mid_price:.4f}")
                print(f"   Spread: {spread_bps:.2f} bps")
                
                print(f"\n📈 Top 3 Bids:")
                for i, bid in enumerate(data['bids'][:3]):
                    print(f"   {i+1}. ${float(bid[0]):.4f} - {float(bid[1]):.1f}")
                
                print(f"\n📉 Top 3 Asks:")
                for i, ask in enumerate(data['asks'][:3]):
                    print(f"   {i+1}. ${float(ask[0]):.4f} - {float(ask[1]):.1f}")
                
                return best_bid, best_ask
            else:
                print("❌ No order book data available")
                return None, None
        else:
            print(f"❌ Order book error: {response.status_code}")
            return None, None
            
    except Exception as e:
        print(f"❌ Order book request failed: {e}")
        return None, None

def show_order_strategy(best_bid, best_ask):
    """Show order placement strategy"""
    print(f"\n🎯 BEST BID/ASK ORDER STRATEGY")
    print("=" * 40)
    
    print(f"💡 Current ENA_USDT Prices:")
    print(f"   Best Bid: ${best_bid:.4f}")
    print(f"   Best Ask: ${best_ask:.4f}")
    
    print(f"\n📋 Limit Order Placement:")
    print(f"   🟢 BUY Limit Order: ${best_bid:.4f} (at best bid)")
    print(f"   🔴 SELL Limit Order: ${best_ask:.4f} (at best ask)")
    
    # Calculate profit targets
    profit_target = 0.002  # 0.2% profit
    sell_target = best_bid * (1 + profit_target)
    buy_target = best_ask * (1 - profit_target)
    
    print(f"\n💰 Profit Taking Strategy:")
    print(f"   📈 If BUY fills at ${best_bid:.4f}")
    print(f"   🎯 SELL Market at > ${sell_target:.4f} (0.2% profit)")
    print(f"   ")
    print(f"   📉 If SELL fills at ${best_ask:.4f}")
    print(f"   🎯 BUY Market at < ${buy_target:.4f} (0.2% profit)")
    
    # Show sample order parameters
    order_size = 10.0
    buy_profit = (sell_target - best_bid) * order_size
    sell_profit = (best_ask - buy_target) * order_size
    
    print(f"\n💵 Sample Trade ({order_size} ENA):")
    print(f"   🟢 Buy→Sell Profit: ${buy_profit:.4f}")
    print(f"   🔴 Sell→Buy Profit: ${sell_profit:.4f}")
    
    print(f"\n📄 Order JSON Examples:")
    buy_order = {
        "contract": "ENA_USDT",
        "size": order_size,
        "price": best_bid,
        "side": "buy",
        "type": "limit",
        "time_in_force": "post_only"
    }
    print(f"   🟢 BUY: {json.dumps(buy_order)}")
    
    sell_order = {
        "contract": "ENA_USDT",
        "size": order_size,
        "price": best_ask,
        "side": "sell", 
        "type": "limit",
        "time_in_force": "post_only"
    }
    print(f"   🔴 SELL: {json.dumps(sell_order)}")

def main():
    """Main demo function"""
    print("🚀 SIMPLE GATE.IO API DEMO")
    print("=" * 50)
    print("This demonstrates:")
    print("✅ API key connection")
    print("📊 ENA_USDT order book")
    print("🎯 Best bid/ask strategy")
    print("=" * 50)
    
    # Test API connection
    if test_api_connection():
        # Get order book
        best_bid, best_ask = get_order_book()
        
        if best_bid and best_ask:
            # Show strategy
            show_order_strategy(best_bid, best_ask)
            
            print(f"\n✅ DEMONSTRATION COMPLETE")
            print(f"🔑 API keys are working")
            print(f"📊 Best bid/ask strategy ready")
            print(f"💰 Use ena_hedging_bot.py for live trading")
        else:
            print(f"\n⚠️ Could not get order book data")
    else:
        print(f"\n❌ API connection failed")
        print(f"🔑 Check API keys or network")

if __name__ == "__main__":
    main()
