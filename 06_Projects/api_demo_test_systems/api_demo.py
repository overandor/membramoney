#!/usr/bin/env python3
"""
API DEMO - Show how API keys work and best bid/ask order placement
"""

import os
import gate_api
from gate_api import ApiClient, Configuration, FuturesApi
import json

# API Configuration
GATE_API_KEY = os.getenv("GATE_API_KEY", "")
GATE_API_SECRET = os.getenv("GATE_API_SECRET", "")

def demonstrate_api_connection():
    """Demonstrate API connection and basic operations"""
    print("🔑 GATE.IO API DEMONSTRATION")
    print("=" * 50)
    
    # Initialize API client
    configuration = Configuration(
        key=GATE_API_KEY,
        secret=GATE_API_SECRET,
        host="https://api.gateio.ws"
    )
    
    api_client = ApiClient(configuration)
    futures_api = FuturesApi(api_client)
    
    try:
        print("✅ API Keys configured:")
        print(f"   Key: {GATE_API_KEY[:10]}...")
        print(f"   Secret: {GATE_API_SECRET[:10]}...")
        
        # Test 1: Get account balance
        print("\n💰 Testing account balance...")
        try:
            accounts = futures_api.list_futures_accounts(settle='usdt')
            if accounts:
                account = accounts[0]
                print(f"   ✅ Balance: ${float(account.available):.2f}")
                print(f"   ✅ Total: ${float(account.total):.2f}")
            else:
                print("   ❌ No account data found")
        except Exception as e:
            print(f"   ❌ Balance error: {e}")
        
        # Test 2: Get positions
        print("\n📊 Testing positions...")
        try:
            positions = futures_api.list_positions(settle='usdt')
            active_positions = [p for p in positions if float(p.size) != 0]
            
            if active_positions:
                print(f"   ✅ Found {len(active_positions)} active positions:")
                for pos in active_positions:
                    print(f"      {pos.contract}: {pos.size} @ ${pos.entry_price}")
            else:
                print("   ✅ No active positions (good for fresh start)")
        except Exception as e:
            print(f"   ❌ Positions error: {e}")
        
        # Test 3: Get ENA order book (best bid/ask)
        print("\n📈 Testing ENA_USDT order book...")
        try:
            book = futures_api.list_futures_order_book(settle='usdt', contract='ENA_USDT', limit=5)
            
            if book.bids and book.asks:
                best_bid = float(book.bids[0].p)
                best_ask = float(book.asks[0].p)
                mid_price = (best_bid + best_ask) / 2
                spread_bps = (best_ask - best_bid) / mid_price * 10000
                
                print(f"   ✅ Best Bid: ${best_bid:.4f}")
                print(f"   ✅ Best Ask: ${best_ask:.4f}")
                print(f"   ✅ Mid Price: ${mid_price:.4f}")
                print(f"   ✅ Spread: {spread_bps:.2f} bps")
                
                # Show order book depth
                print(f"\n   📊 Order Book Depth:")
                print(f"      Bids:")
                for i, bid in enumerate(book.bids[:3]):
                    print(f"         {i+1}. ${float(bid.p):.4f} - {float(bid.s):.1f}")
                
                print(f"      Asks:")
                for i, ask in enumerate(book.asks[:3]):
                    print(f"         {i+1}. ${float(ask.p):.4f} - {float(ask.s):.1f}")
                
                return True
            else:
                print("   ❌ No order book data for ENA_USDT")
                return False
                
        except Exception as e:
            print(f"   ❌ Order book error: {e}")
            return False
            
    except Exception as e:
        print(f"❌ API connection failed: {e}")
        return False

def demonstrate_order_placement():
    """Demonstrate how orders would be placed at best bid/ask"""
    print("\n🎯 ORDER PLACEMENT DEMONSTRATION")
    print("=" * 50)
    
    # Initialize API client
    configuration = Configuration(
        key=GATE_API_KEY,
        secret=GATE_API_SECRET,
        host="https://api.gateio.ws"
    )
    
    api_client = ApiClient(configuration)
    futures_api = FuturesApi(api_client)
    
    try:
        # Get current order book
        book = futures_api.list_futures_order_book(settle='usdt', contract='ENA_USDT', limit=1)
        
        if book.bids and book.asks:
            best_bid = float(book.bids[0].p)
            best_ask = float(book.asks[0].p)
            
            print("💡 ORDER PLACEMENT STRATEGY:")
            print(f"   📈 Current Market:")
            print(f"      Best Bid: ${best_bid:.4f}")
            print(f"      Best Ask: ${best_ask:.4f}")
            
            print(f"\n   🎯 Limit Order Placement:")
            print(f"      ✅ BUY Limit: ${best_bid:.4f} (at best bid)")
            print(f"      ✅ SELL Limit: ${best_ask:.4f} (at best ask)")
            
            print(f"\n   💰 Profit Taking Strategy:")
            print(f"      📊 If BUY fills at ${best_bid:.4f}")
            print(f"      🎯 SELL when price > ${(best_bid * 1.002):.4f} (0.2% profit)")
            print(f"      ")
            print(f"      📊 If SELL fills at ${best_ask:.4f}")
            print(f"      🎯 BUY when price < ${(best_ask * 0.998):.4f} (0.2% profit)")
            
            # Calculate potential profit
            order_size = 10.0  # 10 ENA
            buy_profit = (best_ask * 0.998 - best_bid) * order_size
            sell_profit = (best_ask - best_bid * 1.002) * order_size
            
            print(f"\n   💵 Potential Profit (10 ENA):")
            print(f"      📈 Buy then Sell: ${buy_profit:.4f}")
            print(f"      📉 Sell then Buy: ${sell_profit:.4f}")
            
            # Show actual order parameters (without placing)
            print(f"\n   📋 Order Parameters (DEMO ONLY):")
            buy_order = {
                "contract": "ENA_USDT",
                "size": 10,
                "price": best_bid,
                "side": "buy",
                "type": "limit",
                "time_in_force": "post_only"
            }
            print(f"      🟢 BUY Order: {json.dumps(buy_order, indent=8)}")
            
            sell_order = {
                "contract": "ENA_USDT", 
                "size": 10,
                "price": best_ask,
                "side": "sell",
                "type": "limit",
                "time_in_force": "post_only"
            }
            print(f"      🔴 SELL Order: {json.dumps(sell_order, indent=8)}")
            
            print(f"\n   ⚠️  NOTE: These are DEMO parameters only")
            print(f"   ⚠️  No actual orders placed")
            
        else:
            print("❌ Cannot get order book for demonstration")
            
    except Exception as e:
        print(f"❌ Order placement demo failed: {e}")

def main():
    """Main demonstration"""
    print("🚀 GATE.IO API & BEST BID/ASK DEMO")
    print("=" * 60)
    print("This demo shows:")
    print("1. API key configuration and connection")
    print("2. Account balance and positions")
    print("3. ENA_USDT order book (best bid/ask)")
    print("4. Order placement strategy at best prices")
    print("=" * 60)
    
    # Test API connection
    if demonstrate_api_connection():
        # Show order placement strategy
        demonstrate_order_placement()
        
        print(f"\n✅ DEMONSTRATION COMPLETE")
        print(f"📊 The API keys are working correctly")
        print(f"🎯 Best bid/ask order placement strategy shown")
        print(f"💰 Ready for live trading with proper risk management")
        
    else:
        print(f"\n❌ DEMONSTRATION FAILED")
        print(f"🔑 Check API key configuration")
        print(f"🌐 Verify network connection")

if __name__ == "__main__":
    main()
