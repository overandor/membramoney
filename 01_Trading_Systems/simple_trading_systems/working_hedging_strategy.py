#!/usr/bin/env python3
import os
"""
WORKING HEDGING STRATEGY - Uses correct API to check balance and show hedging
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

def get_balance():
    """Get account balance"""
    print("💰 CHECKING ACCOUNT BALANCE")
    print("=" * 40)
    
    balance_data = make_private_request('GET', '/api/v4/futures/usdt/accounts')
    
    if balance_data:
        available = float(balance_data['available'])
        total = float(balance_data['total'])
        unrealized = float(balance_data['unrealised_pnl'])
        
        print(f"✅ Balance Retrieved:")
        print(f"   Available: ${available:.2f}")
        print(f"   Total: ${total:.2f}")
        print(f"   Unrealized PnL: ${unrealized:+.2f}")
        
        return available, total, unrealized
    else:
        print("❌ Failed to get balance")
        return 0, 0, 0

def get_positions():
    """Get current positions"""
    print("\n📊 CHECKING POSITIONS")
    print("=" * 40)
    
    positions_data = make_private_request('GET', '/api/v4/futures/usdt/positions')
    
    if positions_data:
        active_positions = [p for p in positions_data if float(p['size']) != 0]
        
        if active_positions:
            print(f"✅ Found {len(active_positions)} active positions:")
            for pos in active_positions:
                size = float(pos['size'])
                side = "LONG" if size > 0 else "SHORT"
                print(f"   {pos['contract']}: {side} {abs(size):.3f}")
                print(f"   Entry: ${float(pos['entry_price']):.4f}")
                print(f"   PnL: ${float(pos['unrealised_pnl']):+.4f}")
                print(f"   ---")
        else:
            print("✅ No active positions")
        
        return active_positions
    else:
        print("❌ Failed to get positions")
        return []

def get_order_book(symbol):
    """Get order book for symbol"""
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
                
                return {
                    'symbol': symbol,
                    'best_bid': best_bid,
                    'best_ask': best_ask,
                    'mid_price': mid_price,
                    'spread_bps': spread_bps,
                    'bid_size': float(data['bids'][0][1]),
                    'ask_size': float(data['asks'][0][1])
                }
    except Exception as e:
        print(f"❌ Order book error for {symbol}: {e}")
    
    return None

def analyze_hedging_strategy(market_data, positions, balance):
    """Analyze hedging strategy for a symbol"""
    symbol = market_data['symbol']
    best_bid = market_data['best_bid']
    best_ask = market_data['best_ask']
    mid_price = market_data['mid_price']
    spread_bps = market_data['spread_bps']
    
    print(f"\n🎯 HEDGING STRATEGY FOR {symbol}")
    print("=" * 50)
    
    # Check existing position
    existing_pos = next((p for p in positions if p['contract'] == symbol), None)
    
    if existing_pos:
        pos_size = float(existing_pos['size'])
        entry_price = float(existing_pos['entry_price'])
        
        if pos_size > 0:  # Long position
            profit_potential = (best_ask - entry_price) / entry_price * 100
            print(f"📈 LONG POSITION: {pos_size:.3f} @ ${entry_price:.4f}")
            print(f"💰 Profit Potential: {profit_potential:+.3f}%")
            
            if profit_potential > 0.2:
                print(f"✅ ACTION: SELL at market (${best_ask:.4f})")
                profit = (best_ask - entry_price) * pos_size
                print(f"💵 Expected Profit: ${profit:+.4f}")
                return 'SELL_MARKET'
            else:
                print(f"⏳ ACTION: HOLD - Need >0.2% profit")
                return 'HOLD_LONG'
        else:  # Short position
            profit_potential = (entry_price - best_bid) / entry_price * 100
            print(f"📉 SHORT POSITION: {abs(pos_size):.3f} @ ${entry_price:.4f}")
            print(f"💰 Profit Potential: {profit_potential:+.3f}%")
            
            if profit_potential > 0.2:
                print(f"✅ ACTION: BUY at market (${best_bid:.4f})")
                profit = (entry_price - best_bid) * abs(pos_size)
                print(f"💵 Expected Profit: ${profit:+.4f}")
                return 'BUY_MARKET'
            else:
                print(f"⏳ ACTION: HOLD - Need >0.2% profit")
                return 'HOLD_SHORT'
    else:
        # No position - entry analysis
        print(f"🔄 NO POSITION - Entry Analysis")
        
        if spread_bps < 15:  # Reasonable spread
            print(f"✅ GOOD SPREAD: {spread_bps:.1f} bps")
            print(f"🎯 STRATEGY: Place limit orders at best bid/ask")
            
            # Calculate position size based on balance
            max_position_value = balance * 0.1  # Use 10% of balance
            position_size = min(max_position_value / mid_price, 10.0)  # Max 10 units
            
            print(f"   🟢 BUY Limit: ${best_bid:.4f} (Size: {position_size:.3f})")
            print(f"   🔴 SELL Limit: ${best_ask:.4f} (Size: {position_size:.3f})")
            
            potential_profit = (best_ask - best_bid) * position_size
            print(f"💰 Potential Profit: ${potential_profit:.4f}")
            
            return 'PLACE_LIMIT_ORDERS'
        else:
            print(f"⚠️ WIDE SPREAD: {spread_bps:.1f} bps - Wait")
            return 'WAIT'

def show_multi_ticker_hedging():
    """Show hedging analysis for multiple tickers"""
    symbols = ["BTC_USDT", "ETH_USDT", "SOL_USDT", "ENA_USDT"]
    
    print(f"\n🔄 MULTI-TICKER SMART HEDGING")
    print("=" * 60)
    
    # Get balance and positions
    available, total, unrealized = get_balance()
    positions = get_positions()
    
    if available <= 0:
        print("❌ No available balance for hedging")
        return
    
    print(f"\n💵 Available for trading: ${available:.2f}")
    
    # Analyze each symbol
    actionable_opportunities = []
    
    for symbol in symbols:
        market_data = get_order_book(symbol)
        
        if market_data:
            print(f"\n📊 {symbol}:")
            print(f"   Bid: ${market_data['best_bid']:.4f}")
            print(f"   Ask: ${market_data['best_ask']:.4f}")
            print(f"   Spread: {market_data['spread_bps']:.1f} bps")
            
            action = analyze_hedging_strategy(market_data, positions, available)
            
            if action in ['SELL_MARKET', 'BUY_MARKET', 'PLACE_LIMIT_ORDERS']:
                actionable_opportunities.append({
                    'symbol': symbol,
                    'action': action,
                    'spread_bps': market_data['spread_bps'],
                    'market_data': market_data
                })
        else:
            print(f"\n❌ {symbol}: No market data")
    
    # Summary of actionable opportunities
    print(f"\n📋 ACTIONABLE HEDGING OPPORTUNITIES")
    print("=" * 50)
    
    if actionable_opportunities:
        # Sort by spread (tightest first)
        actionable_opportunities.sort(key=lambda x: x['spread_bps'])
        
        print(f"✅ Found {len(actionable_opportunities)} opportunities:")
        
        for i, opp in enumerate(actionable_opportunities, 1):
            symbol = opp['symbol']
            action = opp['action']
            spread = opp['spread_bps']
            bid = opp['market_data']['best_bid']
            ask = opp['market_data']['best_ask']
            
            if action == 'SELL_MARKET':
                print(f"   {i}. 🔴 {symbol}: SELL at market (~${ask:.4f}) - {spread:.1f}bps")
            elif action == 'BUY_MARKET':
                print(f"   {i}. 🟢 {symbol}: BUY at market (~${bid:.4f}) - {spread:.1f}bps")
            else:
                print(f"   {i}. 🎯 {symbol}: Place limits at ${bid:.4f}/${ask:.4f} - {spread:.1f}bps")
        
        # Best opportunity
        best = actionable_opportunities[0]
        print(f"\n🏆 BEST OPPORTUNITY: {best['symbol']}")
        print(f"   Spread: {best['spread_bps']:.1f} bps")
        print(f"   Action: {best['action']}")
        
        if best['action'] == 'PLACE_LIMIT_ORDERS':
            print(f"   Orders: BUY ${best['market_data']['best_bid']:.4f} / SELL ${best['market_data']['best_ask']:.4f}")
        
    else:
        print(f"⏳ No immediate action needed")
        print(f"💡 Monitor for tighter spreads or profit opportunities")
    
    return actionable_opportunities

def main():
    """Main execution"""
    print("🚀 WORKING SMART HEDGING STRATEGY")
    print("=" * 60)
    print("✅ Checking balance and positions")
    print("🎯 Analyzing multi-ticker hedging opportunities")
    print("💰 Best bid/ask order placement strategy")
    print("=" * 60)
    
    opportunities = show_multi_ticker_hedging()
    
    print(f"\n🎯 FINAL SUMMARY")
    print("=" * 50)
    
    if opportunities:
        print(f"✅ Ready to execute smart hedging on {len(opportunities)} symbols")
        print(f"💰 Strategy: Place orders at best bid/ask prices")
        print(f"🎯 Profit target: >0.2% per trade")
        print(f"⚡ Execution: Use automated hedging bot for best results")
    else:
        print(f"⏳ Wait for better market conditions")
        print(f"💡 Monitor spreads and volatility")

if __name__ == "__main__":
    main()
