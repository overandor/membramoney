#!/usr/bin/env python3
import os
"""
Check spot trading for ENA
"""

import requests

BASE_URL = "https://api.gateio.ws"

def get_spot_pairs():
    """Get available spot trading pairs"""
    print("💰 AVAILABLE SPOT TRADING PAIRS")
    print("=" * 40)
    
    url = f"{BASE_URL}/api/v4/spot/currency_pairs"
    
    try:
        response = requests.get(url)
        if response.status_code == 200:
            pairs = response.json()
            
            # Find ENA pairs
            ena_pairs = [p for p in pairs if 'ENA' in p['id'] and p['trade_status'] == 'tradable']
            
            if ena_pairs:
                print(f"✅ Found {len(ena_pairs)} ENA trading pairs:")
                for pair in ena_pairs:
                    print(f"   📈 {pair['id']} - Min: {pair.get('min_base_amount', 'N/A')}")
            else:
                print(f"❌ No ENA pairs found")
                # Show some popular USDT pairs
                usdt_pairs = [p for p in pairs if p['quote'] == 'USDT' and p['trade_status'] == 'tradable'][:10]
                print(f"💡 Popular USDT pairs:")
                for pair in usdt_pairs:
                    print(f"   📈 {pair['id']}")
            
            return ena_pairs
            
        else:
            print(f"❌ Error: {response.status_code}")
            return None
            
    except Exception as e:
        print(f"❌ Request failed: {e}")
        return None

def get_spot_order_book(pair):
    """Get spot order book"""
    print(f"\n📊 SPOT ORDER BOOK FOR {pair}")
    print("=" * 40)
    
    url = f"{BASE_URL}/api/v4/spot/order_book?currency_pair={pair}&limit=5"
    
    try:
        response = requests.get(url)
        if response.status_code == 200:
            data = response.json()
            
            if 'bids' in data and 'asks' in data and data['bids'] and data['asks']:
                best_bid = float(data['bids'][0][0])
                best_ask = float(data['asks'][0][0])
                mid_price = (best_bid + best_ask) / 2
                spread_bps = (best_ask - best_bid) / mid_price * 10000
                
                print(f"✅ Spot Order Book for {pair}:")
                print(f"   Best Bid: ${best_bid:.6f}")
                print(f"   Best Ask: ${best_ask:.6f}")
                print(f"   Mid Price: ${mid_price:.6f}")
                print(f"   Spread: {spread_bps:.2f} bps")
                
                return best_bid, best_ask
            else:
                print(f"❌ No order book data for {pair}")
                return None, None
        else:
            print(f"❌ Order book error: {response.status_code}")
            return None, None
            
    except Exception as e:
        print(f"❌ Order book request failed: {e}")
        return None, None

def show_spot_strategy(best_bid, best_ask, pair):
    """Show spot trading strategy"""
    print(f"\n🎯 SPOT BEST BID/ASK STRATEGY for {pair}")
    print("=" * 40)
    
    print(f"💡 Current {pair} Prices:")
    print(f"   Best Bid: ${best_bid:.6f}")
    print(f"   Best Ask: ${best_ask:.6f}")
    
    print(f"\n📋 Spot Order Placement:")
    print(f"   🟢 BUY Limit Order: ${best_bid:.6f} (at best bid)")
    print(f"   🔴 SELL Limit Order: ${best_ask:.6f} (at best ask)")
    
    # Calculate profit targets
    profit_target = 0.005  # 0.5% profit for spot
    sell_target = best_bid * (1 + profit_target)
    buy_target = best_ask * (1 - profit_target)
    
    print(f"\n💰 Profit Taking Strategy:")
    print(f"   📈 If BUY fills at ${best_bid:.6f}")
    print(f"   🎯 SELL Market at > ${sell_target:.6f} (0.5% profit)")
    print(f"   ")
    print(f"   📉 If SELL fills at ${best_ask:.6f}")
    print(f"   🎯 BUY Market at < ${buy_target:.6f} (0.5% profit)")

def main():
    pairs = get_spot_pairs()
    
    if pairs:
        # Check ENA_USDT spot
        ena_usdt = next((p for p in pairs if p['id'] == 'ENA_USDT'), None)
        if ena_usdt:
            best_bid, best_ask = get_spot_order_book('ENA_USDT')
            if best_bid and best_ask:
                show_spot_strategy(best_bid, best_ask, 'ENA_USDT')
                print(f"\n✅ ENA_USDT SPOT TRADING READY!")
        else:
            # Try first available pair
            if pairs:
                pair = pairs[0]['id']
                best_bid, best_ask = get_spot_order_book(pair)
                if best_bid and best_ask:
                    show_spot_strategy(best_bid, best_ask, pair)

if __name__ == "__main__":
    main()
