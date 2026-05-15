#!/usr/bin/env python3
import os
"""
ENA FOCUSED HEDGING - Smart hedging for your ENA positions
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
        return None

def get_ena_positions():
    """Get ENA positions"""
    print("🎯 GETTING ENA POSITIONS")
    print("=" * 40)
    
    positions_data = make_private_request('GET', '/api/v4/futures/usdt/positions')
    
    if positions_data:
        ena_positions = [p for p in positions_data if p['contract'] == 'ENA_USDT' and float(p['size']) != 0]
        
        if ena_positions:
            print(f"✅ Found {len(ena_positions)} ENA positions:")
            total_long = 0
            total_short = 0
            avg_long_entry = 0
            avg_short_entry = 0
            
            for pos in ena_positions:
                size = float(pos['size'])
                entry_price = float(pos['entry_price'])
                pnl = float(pos['unrealised_pnl'])
                
                if size > 0:
                    total_long += size
                    avg_long_entry = entry_price  # Simplified
                    print(f"   📈 LONG: {size:.3f} @ ${entry_price:.4f} (PnL: ${pnl:+.4f})")
                else:
                    total_short += abs(size)
                    avg_short_entry = entry_price  # Simplified
                    print(f"   📉 SHORT: {abs(size):.3f} @ ${entry_price:.4f} (PnL: ${pnl:+.4f})")
            
            net_position = total_long - total_short
            print(f"\n📊 NET ENA POSITION: {net_position:+.3f}")
            print(f"   Total Long: {total_long:.3f}")
            print(f"   Total Short: {total_short:.3f}")
            
            return ena_positions, net_position, avg_long_entry, avg_short_entry
        else:
            print("❌ No ENA positions found")
            return [], 0, 0, 0
    else:
        print("❌ Failed to get positions")
        return [], 0, 0, 0

def get_ena_order_book():
    """Get ENA order book"""
    print("\n📈 GETTING ENA ORDER BOOK")
    print("=" * 40)
    
    url = f"{BASE_URL}/api/v4/futures/usdt/order_book?contract=ENA_USDT&limit=10"
    
    try:
        response = requests.get(url)
        if response.status_code == 200:
            data = response.json()
            
            if 'bids' in data and 'asks' in data and data['bids'] and data['asks']:
                print(f"✅ ENA Order Book Retrieved:")
                
                # Show top 5 levels
                print(f"\n   📊 TOP 5 BIDS:")
                for i, bid in enumerate(data['bids'][:5]):
                    price = float(bid[0])
                    size = float(bid[1])
                    print(f"      {i+1}. ${price:.4f} - {size:.1f}")
                
                print(f"\n   📊 TOP 5 ASKS:")
                for i, ask in enumerate(data['asks'][:5]):
                    price = float(ask[0])
                    size = float(ask[1])
                    print(f"      {i+1}. ${price:.4f} - {size:.1f}")
                
                best_bid = float(data['bids'][0][0])
                best_ask = float(data['asks'][0][0])
                mid_price = (best_bid + best_ask) / 2
                spread_bps = (best_ask - best_bid) / mid_price * 10000
                
                print(f"\n📈 MARKET SUMMARY:")
                print(f"   Best Bid: ${best_bid:.4f}")
                print(f"   Best Ask: ${best_ask:.4f}")
                print(f"   Mid Price: ${mid_price:.4f}")
                print(f"   Spread: {spread_bps:.1f} bps")
                
                return {
                    'best_bid': best_bid,
                    'best_ask': best_ask,
                    'mid_price': mid_price,
                    'spread_bps': spread_bps,
                    'bid_size': float(data['bids'][0][1]),
                    'ask_size': float(data['asks'][0][1]),
                    'full_bids': [[float(b[0]), float(b[1])] for b in data['bids']],
                    'full_asks': [[float(a[0]), float(a[1])] for a in data['asks']]
                }
            else:
                print("❌ Empty order book")
                return None
        else:
            print(f"❌ Order book error: {response.status_code}")
            return None
    except Exception as e:
        print(f"❌ Order book request failed: {e}")
        return None

def analyze_ena_hedging(positions, net_position, avg_long_entry, avg_short_entry, order_book):
    """Analyze ENA hedging strategy"""
    print(f"\n🧠 ENA HEDGING STRATEGY ANALYSIS")
    print("=" * 50)
    
    best_bid = order_book['best_bid']
    best_ask = order_book['best_ask']
    mid_price = order_book['mid_price']
    spread_bps = order_book['spread_bps']
    
    actions = []
    
    # Analyze long positions
    if net_position > 0 or any(float(p['size']) > 0 for p in positions):
        print(f"\n📈 LONG POSITION ANALYSIS:")
        
        for pos in positions:
            size = float(pos['size'])
            if size > 0:
                entry_price = float(pos['entry_price'])
                profit_potential = (best_ask - entry_price) / entry_price * 100
                
                print(f"   Position: {size:.3f} @ ${entry_price:.4f}")
                print(f"   Profit Potential: {profit_potential:+.3f}%")
                
                if profit_potential > 0.2:  # 0.2% threshold
                    profit = (best_ask - entry_price) * size
                    print(f"   ✅ ACTION: SELL {size:.3f} at market (${best_ask:.4f})")
                    print(f"   💰 Expected Profit: ${profit:+.4f}")
                    actions.append({
                        'type': 'SELL_MARKET',
                        'size': size,
                        'price': best_ask,
                        'profit': profit,
                        'reason': f'Profit opportunity {profit_potential:.3f}%'
                    })
                else:
                    needed_price = entry_price * 1.002  # Need 0.2% profit
                    print(f"   ⏳ WAIT: Need price > ${needed_price:.4f} for profit")
    
    # Analyze short positions
    if net_position < 0 or any(float(p['size']) < 0 for p in positions):
        print(f"\n📉 SHORT POSITION ANALYSIS:")
        
        for pos in positions:
            size = float(pos['size'])
            if size < 0:
                entry_price = float(pos['entry_price'])
                profit_potential = (entry_price - best_bid) / entry_price * 100
                
                print(f"   Position: {abs(size):.3f} @ ${entry_price:.4f}")
                print(f"   Profit Potential: {profit_potential:+.3f}%")
                
                if profit_potential > 0.2:  # 0.2% threshold
                    profit = (entry_price - best_bid) * abs(size)
                    print(f"   ✅ ACTION: BUY {abs(size):.3f} at market (${best_bid:.4f})")
                    print(f"   💰 Expected Profit: ${profit:+.4f}")
                    actions.append({
                        'type': 'BUY_MARKET',
                        'size': abs(size),
                        'price': best_bid,
                        'profit': profit,
                        'reason': f'Profit opportunity {profit_potential:.3f}%'
                    })
                else:
                    needed_price = entry_price * 0.998  # Need 0.2% profit
                    print(f"   ⏳ WAIT: Need price < ${needed_price:.4f} for profit")
    
    # Net position analysis
    print(f"\n🎯 NET POSITION: {net_position:+.3f} ENA")
    
    if abs(net_position) < 0.001:
        # No net position - look for entry opportunities
        print(f"🔄 NO NET POSITION - ENTRY OPPORTUNITY ANALYSIS:")
        
        if spread_bps < 20:  # Reasonable spread
            print(f"✅ GOOD SPREAD: {spread_bps:.1f} bps")
            print(f"🎯 STRATEGY: Place limit orders at best bid/ask")
            
            # Calculate optimal order size
            order_size = min(5.0, max(1.0, abs(net_position) if net_position != 0 else 2.0))
            
            print(f"   🟢 BUY Limit: ${best_bid:.4f} (Size: {order_size:.3f})")
            print(f"   🔴 SELL Limit: ${best_ask:.4f} (Size: {order_size:.3f})")
            
            potential_profit = (best_ask - best_bid) * order_size
            print(f"💰 Potential Profit: ${potential_profit:.4f}")
            
            actions.append({
                'type': 'PLACE_LIMIT_ORDERS',
                'buy_size': order_size,
                'sell_size': order_size,
                'buy_price': best_bid,
                'sell_price': best_ask,
                'potential_profit': potential_profit,
                'reason': f'Tight spread {spread_bps:.1f} bps'
            })
        else:
            print(f"⚠️ WIDE SPREAD: {spread_bps:.1f} bps - Wait for better opportunity")
    
    return actions

def show_execution_plan(actions):
    """Show execution plan for hedging actions"""
    print(f"\n🚀 HEDGING EXECUTION PLAN")
    print("=" * 50)
    
    if not actions:
        print(f"⏳ No immediate actions needed")
        print(f"💡 Monitor market for better opportunities")
        return
    
    print(f"✅ Found {len(actions)} actionable hedging actions:")
    
    total_potential_profit = 0
    
    for i, action in enumerate(actions, 1):
        print(f"\n   {i}. {action['type']}")
        
        if action['type'] == 'SELL_MARKET':
            print(f"      📴 SELL {action['size']:.3f} ENA at market (~${action['price']:.4f})")
            print(f"      💰 Profit: ${action['profit']:+.4f}")
            print(f"      📝 Reason: {action['reason']}")
            total_potential_profit += action['profit']
            
        elif action['type'] == 'BUY_MARKET':
            print(f"      📵 BUY {action['size']:.3f} ENA at market (~${action['price']:.4f})")
            print(f"      💰 Profit: ${action['profit']:+.4f}")
            print(f"      📝 Reason: {action['reason']}")
            total_potential_profit += action['profit']
            
        elif action['type'] == 'PLACE_LIMIT_ORDERS':
            print(f"      🟢 BUY Limit: {action['buy_size']:.3f} @ ${action['buy_price']:.4f}")
            print(f"      🔴 SELL Limit: {action['sell_size']:.3f} @ ${action['sell_price']:.4f}")
            print(f"      💰 Potential Profit: ${action['potential_profit']:.4f}")
            print(f"      📝 Reason: {action['reason']}")
            total_potential_profit += action['potential_profit']
    
    print(f"\n💰 TOTAL POTENTIAL PROFIT: ${total_potential_profit:+.4f}")
    
    if total_potential_profit > 0:
        print(f"✅ RECOMMENDATION: Execute these actions for profit")
        print(f"⚡ Use automated bot for best execution timing")
    else:
        print(f"⚠️ Some actions may result in losses - review carefully")

def main():
    """Main ENA hedging analysis"""
    print("🚀 ENA FOCUSED SMART HEDGING")
    print("=" * 60)
    print("🎯 Analyzing your ENA positions for profit opportunities")
    print("💰 Best bid/ask hedging strategy")
    print("⚡ Real-time market analysis")
    print("=" * 60)
    
    # Get ENA positions
    positions, net_position, avg_long_entry, avg_short_entry = get_ena_positions()
    
    if not positions:
        print("❌ No ENA positions to hedge")
        return
    
    # Get ENA order book
    order_book = get_ena_order_book()
    
    if not order_book:
        print("❌ Cannot get ENA market data")
        return
    
    # Analyze hedging strategy
    actions = analyze_ena_hedging(positions, net_position, avg_long_entry, avg_short_entry, order_book)
    
    # Show execution plan
    show_execution_plan(actions)
    
    print(f"\n🎯 FINAL RECOMMENDATION")
    print("=" * 50)
    
    if actions:
        print(f"✅ Ready to execute smart ENA hedging")
        print(f"💰 Strategy: Best bid/ask order placement")
        print(f"🎯 Target: >0.2% profit per trade")
        print(f"⚡ Next: Use automated hedging bot for execution")
    else:
        print(f"⏳ Wait for better ENA price opportunities")
        print(f"💡 Monitor spread and volatility")

if __name__ == "__main__":
    main()
