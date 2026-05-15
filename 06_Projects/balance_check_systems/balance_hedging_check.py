#!/usr/bin/env python3
import os
"""
BALANCE & HEDGING CHECK - Simple script to check balance and show hedging strategy
"""

import gate_api
from gate_api import ApiClient, Configuration, FuturesApi
import json
import time
from datetime import datetime

# API Configuration
GATE_API_KEY = os.getenv("GATE_API_KEY", "")
GATE_API_SECRET = os.getenv("GATE_API_SECRET", "")

def check_balance():
    """Check account balance"""
    print("💰 CHECKING ACCOUNT BALANCE")
    print("=" * 50)
    
    try:
        # Initialize API client
        configuration = Configuration(
            key=GATE_API_KEY,
            secret=GATE_API_SECRET,
            host="https://api.gateio.ws"
        )
        
        api_client = ApiClient(configuration)
        futures_api = FuturesApi(api_client)
        
        # Get account balance
        accounts = futures_api.list_futures_accounts(settle='usdt')
        if accounts:
            account = accounts[0]
            print(f"✅ Balance Retrieved:")
            print(f"   Total Balance: ${float(account.total):.2f}")
            print(f"   Available: ${float(account.available):.2f}")
            print(f"   Unrealized PnL: ${float(account.unrealised_pnl):.2f}")
            print(f"   Margin: ${float(account.margin):.2f}")
            
            return float(account.available)
        else:
            print("❌ No account data found")
            return 0.0
            
    except Exception as e:
        print(f"❌ Balance check failed: {e}")
        return 0.0

def check_positions():
    """Check current positions"""
    print("\n📊 CHECKING CURRENT POSITIONS")
    print("=" * 50)
    
    try:
        configuration = Configuration(
            key=GATE_API_KEY,
            secret=GATE_API_SECRET,
            host="https://api.gateio.ws"
        )
        
        api_client = ApiClient(configuration)
        futures_api = FuturesApi(api_client)
        
        positions = futures_api.list_positions(settle='usdt')
        active_positions = [p for p in positions if float(p.size) != 0]
        
        if active_positions:
            print(f"✅ Found {len(active_positions)} active positions:")
            for pos in active_positions:
                side = "LONG" if float(pos.size) > 0 else "SHORT"
                print(f"   {pos.contract}: {side} {abs(float(pos.size)):.3f}")
                print(f"   Entry Price: ${float(pos.entry_price):.4f}")
                print(f"   Mark Price: ${float(pos.mark_price):.4f}")
                print(f"   PnL: ${float(pos.unrealised_pnl):+.4f}")
                print(f"   ---")
        else:
            print("✅ No active positions - Ready for fresh hedging")
            
        return active_positions
        
    except Exception as e:
        print(f"❌ Position check failed: {e}")
        return []

def get_market_data(symbol):
    """Get market data for a symbol"""
    try:
        configuration = Configuration(
            key=GATE_API_KEY,
            secret=GATE_API_SECRET,
            host="https://api.gateio.ws"
        )
        
        api_client = ApiClient(configuration)
        futures_api = FuturesApi(api_client)
        
        # Get order book
        book = futures_api.list_futures_order_book(settle='usdt', contract=symbol, limit=5)
        
        if book.bids and book.asks:
            best_bid = float(book.bids[0].p)
            best_ask = float(book.asks[0].p)
            mid_price = (best_bid + best_ask) / 2
            spread_bps = (best_ask - best_bid) / mid_price * 10000
            
            return {
                'symbol': symbol,
                'best_bid': best_bid,
                'best_ask': best_ask,
                'mid_price': mid_price,
                'spread_bps': spread_bps,
                'bid_size': float(book.bids[0].s),
                'ask_size': float(book.asks[0].s)
            }
        else:
            return None
            
    except Exception as e:
        print(f"❌ Market data for {symbol} failed: {e}")
        return None

def analyze_hedging_opportunity(market_data, positions):
    """Analyze hedging opportunity for a symbol"""
    symbol = market_data['symbol']
    best_bid = market_data['best_bid']
    best_ask = market_data['best_ask']
    mid_price = market_data['mid_price']
    spread_bps = market_data['spread_bps']
    
    print(f"\n🎯 HEDGING ANALYSIS FOR {symbol}")
    print("=" * 50)
    
    # Check if we have existing position
    existing_pos = next((p for p in positions if p.contract == symbol), None)
    
    if existing_pos:
        pos_size = float(existing_pos.size)
        entry_price = float(existing_pos.entry_price)
        
        if pos_size > 0:  # Long position
            profit_potential = (best_ask - entry_price) / entry_price * 100
            print(f"📈 CURRENT POSITION: LONG {pos_size:.3f} @ ${entry_price:.4f}")
            print(f"💰 Profit Potential: {profit_potential:+.3f}%")
            
            if profit_potential > 0.2:  # 0.2% profit threshold
                print(f"✅ RECOMMENDATION: SELL at market (${best_ask:.4f})")
                print(f"💰 Expected Profit: ${(best_ask - entry_price) * pos_size:+.4f}")
                return 'SELL_MARKET'
            else:
                print(f"⏳ RECOMMENDATION: HOLD - Wait for better price")
                return 'HOLD_LONG'
                
        else:  # Short position
            profit_potential = (entry_price - best_bid) / entry_price * 100
            print(f"📉 CURRENT POSITION: SHORT {abs(pos_size):.3f} @ ${entry_price:.4f}")
            print(f"💰 Profit Potential: {profit_potential:+.3f}%")
            
            if profit_potential > 0.2:  # 0.2% profit threshold
                print(f"✅ RECOMMENDATION: BUY at market (${best_bid:.4f})")
                print(f"💰 Expected Profit: ${(entry_price - best_bid) * abs(pos_size):+.4f}")
                return 'BUY_MARKET'
            else:
                print(f"⏳ RECOMMENDATION: HOLD - Wait for better price")
                return 'HOLD_SHORT'
    else:
        # No position - analyze entry opportunity
        print(f"🔄 NO CURRENT POSITION - Analyzing entry opportunity")
        
        if spread_bps < 10:  # Tight spread
            print(f"✅ TIGHT SPREAD: {spread_bps:.1f} bps - Good entry opportunity")
            print(f"🎯 RECOMMENDATION: Place limit orders at best bid/ask")
            print(f"   🟢 BUY Limit: ${best_bid:.4f}")
            print(f"   🔴 SELL Limit: ${best_ask:.4f}")
            
            # Calculate potential profit
            order_size = 10.0
            potential_profit = (best_ask - best_bid) * order_size
            print(f"💰 Potential Profit ({order_size} units): ${potential_profit:.4f}")
            
            return 'PLACE_LIMIT_ORDERS'
        else:
            print(f"⚠️ WIDE SPREAD: {spread_bps:.1f} bps - Wait for better opportunity")
            return 'WAIT'

def show_multi_ticker_analysis():
    """Show analysis for multiple tickers"""
    symbols = ["BTC_USDT", "ETH_USDT", "SOL_USDT", "ENA_USDT"]
    
    print(f"\n🔄 MULTI-TICKER HEDGING ANALYSIS")
    print("=" * 60)
    
    positions = check_positions()
    opportunities = []
    
    for symbol in symbols:
        market_data = get_market_data(symbol)
        if market_data:
            print(f"\n📊 {symbol} Market Data:")
            print(f"   Best Bid: ${market_data['best_bid']:.4f}")
            print(f"   Best Ask: ${market_data['best_ask']:.4f}")
            print(f"   Mid Price: ${market_data['mid_price']:.4f}")
            print(f"   Spread: {market_data['spread_bps']:.1f} bps")
            
            recommendation = analyze_hedging_opportunity(market_data, positions)
            opportunities.append({
                'symbol': symbol,
                'recommendation': recommendation,
                'spread_bps': market_data['spread_bps'],
                'market_data': market_data
            })
        else:
            print(f"\n❌ {symbol}: No market data available")
    
    # Summary
    print(f"\n📋 HEDGING SUMMARY")
    print("=" * 50)
    
    for opp in opportunities:
        symbol = opp['symbol']
        rec = opp['recommendation']
        spread = opp['spread_bps']
        
        if rec == 'SELL_MARKET':
            status = "🔴 TAKE PROFIT (SELL)"
        elif rec == 'BUY_MARKET':
            status = "🟢 TAKE PROFIT (BUY)"
        elif rec == 'PLACE_LIMIT_ORDERS':
            status = "🎯 ENTER MARKET"
        else:
            status = "⏳ WAIT"
            
        print(f"   {symbol}: {status} (Spread: {spread:.1f} bps)")
    
    # Best opportunities
    print(f"\n🏆 BEST OPPORTUNITIES:")
    best_opp = sorted(opportunities, key=lambda x: x['spread_bps'])[:2]
    for opp in best_opp:
        symbol = opp['symbol']
        spread = opp['spread_bps']
        rec = opp['recommendation']
        
        if rec in ['SELL_MARKET', 'BUY_MARKET', 'PLACE_LIMIT_ORDERS']:
            print(f"   🌟 {symbol}: {spread:.1f} bps spread - ACTION READY")
    
    return opportunities

def main():
    """Main function"""
    print("🚀 BALANCE & SMART HEDGING ANALYSIS")
    print("=" * 60)
    print(f"⏰ Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    
    # Check balance
    balance = check_balance()
    if balance <= 0:
        print("\n❌ Cannot proceed - no available balance")
        return
    
    # Show multi-ticker analysis
    opportunities = show_multi_ticker_analysis()
    
    # Final recommendations
    print(f"\n🎯 FINAL RECOMMENDATIONS")
    print("=" * 50)
    
    actionable = [opp for opp in opportunities if opp['recommendation'] in ['SELL_MARKET', 'BUY_MARKET', 'PLACE_LIMIT_ORDERS']]
    
    if actionable:
        print(f"✅ Found {len(actionable)} actionable opportunities:")
        for opp in actionable:
            symbol = opp['symbol']
            rec = opp['recommendation']
            bid = opp['market_data']['best_bid']
            ask = opp['market_data']['best_ask']
            
            if rec == 'SELL_MARKET':
                print(f"   🔴 {symbol}: SELL at market (~${ask:.4f})")
            elif rec == 'BUY_MARKET':
                print(f"   🟢 {symbol}: BUY at market (~${bid:.4f})")
            else:
                print(f"   🎯 {symbol}: Place limit orders at ${bid:.4f}/${ask:.4f}")
        
        print(f"\n💰 Ready to execute smart hedging strategy!")
        print(f"💡 Use ena_hedging_bot.py for automated execution")
    else:
        print(f"⏳ No immediate action needed - monitor market conditions")
        print(f"💡 Wait for tighter spreads or better profit opportunities")

if __name__ == "__main__":
    main()
