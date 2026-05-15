#!/usr/bin/env python3
import os
"""
Check available futures contracts
"""

import requests

BASE_URL = "https://api.gateio.ws"

def get_contracts():
    """Get all available futures contracts"""
    print("📊 AVAILABLE FUTURES CONTRACTS")
    print("=" * 40)
    
    url = f"{BASE_URL}/api/v4/futures/usdt/contracts"
    
    try:
        response = requests.get(url)
        if response.status_code == 200:
            contracts = response.json()
            
            # Filter for active contracts
            active_contracts = [c for c in contracts if c.get('status') == 'open']
            
            print(f"✅ Found {len(active_contracts)} active contracts:")
            
            # Show some popular ones
            popular = ['BTC_USDT', 'ETH_USDT', 'SOL_USDT', 'DOGE_USDT', 'ENA_USDT']
            
            for contract in active_contracts:
                symbol = contract['name']
                if symbol in popular:
                    print(f"   🌟 {symbol} - {contract.get('quanto_multiplier', 'N/A')}")
                elif len(active_contracts) <= 20:  # Show all if not too many
                    print(f"   📈 {symbol}")
            
            # Check specifically for ENA
            ena_found = any(c['name'] == 'ENA_USDT' for c in active_contracts)
            if ena_found:
                print(f"\n✅ ENA_USDT is available for trading!")
            else:
                print(f"\n❌ ENA_USDT not found in available contracts")
                print(f"💡 Available alternatives:")
                for c in active_contracts[:5]:
                    print(f"   📈 {c['name']}")
            
            return active_contracts
            
        else:
            print(f"❌ Error: {response.status_code}")
            return None
            
    except Exception as e:
        print(f"❌ Request failed: {e}")
        return None

def get_order_book(symbol):
    """Get order book for a specific symbol"""
    print(f"\n📊 ORDER BOOK FOR {symbol}")
    print("=" * 40)
    
    url = f"{BASE_URL}/api/v4/futures/usdt/order_book?contract={symbol}&limit=5"
    
    try:
        response = requests.get(url)
        if response.status_code == 200:
            data = response.json()
            
            if 'bids' in data and 'asks' in data and data['bids'] and data['asks']:
                best_bid = float(data['bids'][0][0])
                best_ask = float(data['asks'][0][0])
                mid_price = (best_bid + best_ask) / 2
                spread_bps = (best_ask - best_bid) / mid_price * 10000
                
                print(f"✅ Order Book for {symbol}:")
                print(f"   Best Bid: ${best_bid:.4f}")
                print(f"   Best Ask: ${best_ask:.4f}")
                print(f"   Mid Price: ${mid_price:.4f}")
                print(f"   Spread: {spread_bps:.2f} bps")
                
                return best_bid, best_ask
            else:
                print(f"❌ No order book data for {symbol}")
                return None, None
        else:
            print(f"❌ Order book error: {response.status_code}")
            return None, None
            
    except Exception as e:
        print(f"❌ Order book request failed: {e}")
        return None, None

def main():
    contracts = get_contracts()
    
    if contracts:
        # Try to get order book for a popular contract
        popular_contracts = ['BTC_USDT', 'ETH_USDT', 'SOL_USDT']
        
        for symbol in popular_contracts:
            if any(c['name'] == symbol for c in contracts):
                best_bid, best_ask = get_order_book(symbol)
                if best_bid and best_ask:
                    print(f"\n🎯 READY FOR {symbol} TRADING!")
                    print(f"💰 Use this symbol for best bid/ask strategy")
                    break

if __name__ == "__main__":
    main()
