#!/usr/bin/env python3
import os
"""
ENA POSITION STRATEGY - Based on your current positions
"""

def analyze_ena_positions():
    """Analyze your current ENA positions and provide strategy"""
    
    print("🎯 YOUR ENA POSITIONS ANALYSIS")
    print("=" * 50)
    
    # Your current positions
    long_position = 2.0
    long_entry = 0.0822
    long_pnl = 0.0072
    
    short_position = 3.0
    short_entry = 0.0806
    short_pnl = -0.0607
    
    net_position = short_position - long_position  # -1.0 (net short)
    
    print(f"📈 LONG POSITION: {long_position} ENA @ ${long_entry}")
    print(f"   PnL: +${long_pnl}")
    print(f"")
    print(f"📉 SHORT POSITION: {short_position} ENA @ ${short_entry}")
    print(f"   PnL: {short_pnl}")
    print(f"")
    print(f"📊 NET POSITION: {net_position:+.1f} ENA (net short)")
    print(f"💰 Total PnL: ${long_pnl + short_pnl:+.4f}")
    
    return {
        'long_size': long_position,
        'long_entry': long_entry,
        'short_size': short_position,
        'short_entry': short_entry,
        'net_position': net_position
    }

def calculate_hedging_strategy(positions):
    """Calculate optimal hedging strategy"""
    
    print(f"\n🧠 SMART HEDGING STRATEGY")
    print("=" * 50)
    
    long_size = positions['long_size']
    long_entry = positions['long_entry']
    short_size = positions['short_size']
    short_entry = positions['short_entry']
    net_pos = positions['net_position']
    
    # Strategy scenarios based on market prices
    print(f"📋 HEDGING SCENARIOS:")
    
    # Scenario 1: Current market prices (estimated)
    current_bid = 0.0810  # Estimated current bid
    current_ask = 0.0815  # Estimated current ask
    
    print(f"\n1️⃣ CURRENT MARKET CONDITIONS:")
    print(f"   Estimated Bid: ${current_bid}")
    print(f"   Estimated Ask: ${current_ask}")
    
    # Analyze long position
    long_profit_potential = (current_ask - long_entry) / long_entry * 100
    print(f"\n   📈 LONG POSITION ANALYSIS:")
    print(f"      Entry: ${long_entry}")
    print(f"      Current Sell Price: ${current_ask}")
    print(f"      Profit Potential: {long_profit_potential:+.3f}%")
    
    if long_profit_potential > 0.2:
        profit = (current_ask - long_entry) * long_size
        print(f"      ✅ ACTION: SELL {long_size} ENA at market")
        print(f"      💰 Expected Profit: +${profit:.4f}")
    else:
        needed_sell_price = long_entry * 1.002
        print(f"      ⏳ WAIT: Need price > ${needed_sell_price:.4f} for 0.2% profit")
    
    # Analyze short position
    short_profit_potential = (short_entry - current_bid) / short_entry * 100
    print(f"\n   📉 SHORT POSITION ANALYSIS:")
    print(f"      Entry: ${short_entry}")
    print(f"      Current Buy Price: ${current_bid}")
    print(f"      Profit Potential: {short_profit_potential:+.3f}%")
    
    if short_profit_potential > 0.2:
        profit = (short_entry - current_bid) * short_size
        print(f"      ✅ ACTION: BUY {short_size} ENA at market")
        print(f"      💰 Expected Profit: +${profit:.4f}")
    else:
        needed_buy_price = short_entry * 0.998
        print(f"      ⏳ WAIT: Need price < ${needed_buy_price:.4f} for 0.2% profit")
    
    # Scenario 2: Optimal entry prices for new positions
    print(f"\n2️⃣ OPTIMAL LIMIT ORDER PLACEMENT:")
    print(f"   Strategy: Place orders at best bid/ask for profit")
    
    # Calculate optimal limit order prices
    optimal_buy = current_bid  # Buy at best bid
    optimal_sell = current_ask  # Sell at best ask
    
    print(f"   🟢 BUY Limit: ${optimal_buy:.4f} (Size: {net_position if net_pos < 0 else 2.0:.1f})")
    print(f"   🔴 SELL Limit: ${optimal_sell:.4f} (Size: {abs(net_pos) if net_pos > 0 else 2.0:.1f})")
    
    # Scenario 3: Profit targets
    print(f"\n3️⃣ PROFIT TARGETS:")
    
    long_target = long_entry * 1.002  # 0.2% profit target
    short_target = short_entry * 0.998  # 0.2% profit target
    
    print(f"   📈 Long Position Target: >${long_target:.4f}")
    print(f"   📉 Short Position Target: <${short_target:.4f}")
    
    # Current action recommendations
    print(f"\n🎯 IMMEDIATE ACTIONS:")
    
    actions = []
    
    # Check if long position should be closed
    if current_ask >= long_target:
        profit = (current_ask - long_entry) * long_size
        actions.append({
            'action': 'SELL_LONG',
            'size': long_size,
            'price': current_ask,
            'profit': profit,
            'reason': 'Profit target reached'
        })
        print(f"   ✅ SELL {long_size} ENA (close long position)")
        print(f"      Profit: +${profit:.4f}")
    
    # Check if short position should be closed
    if current_bid <= short_target:
        profit = (short_entry - current_bid) * short_size
        actions.append({
            'action': 'BUY_SHORT',
            'size': short_size,
            'price': current_bid,
            'profit': profit,
            'reason': 'Profit target reached'
        })
        print(f"   ✅ BUY {short_size} ENA (close short position)")
        print(f"      Profit: +${profit:.4f}")
    
    # If no immediate actions, provide waiting strategy
    if not actions:
        print(f"   ⏳ WAIT FOR BETTER PRICES:")
        print(f"      📈 Long: Wait for ask > ${long_target:.4f}")
        print(f"      📉 Short: Wait for bid < ${short_target:.4f}")
        
        # Suggest limit orders for new positions
        print(f"\n   🎯 PLACE LIMIT ORDERS:")
        print(f"      🟢 BUY {abs(net_pos):.1f} ENA @ ${optimal_buy:.4f}")
        print(f"      🔴 SELL 2.0 ENA @ ${optimal_sell:.4f}")
    
    return actions

def show_execution_summary(actions):
    """Show execution summary"""
    
    print(f"\n🚀 EXECUTION SUMMARY")
    print("=" * 50)
    
    if actions:
        total_profit = sum(action['profit'] for action in actions)
        print(f"✅ READY TO EXECUTE {len(actions)} PROFITABLE ACTIONS:")
        
        for i, action in enumerate(actions, 1):
            print(f"\n   {i}. {action['action']}")
            print(f"      Size: {action['size']} ENA")
            print(f"      Price: ${action['price']:.4f}")
            print(f"      Profit: +${action['profit']:.4f}")
            print(f"      Reason: {action['reason']}")
        
        print(f"\n💰 TOTAL EXPECTED PROFIT: +${total_profit:.4f}")
        print(f"🎯 RECOMMENDATION: Execute these actions immediately")
        
    else:
        print(f"⏳ NO IMMEDIATE PROFITABLE ACTIONS")
        print(f"💡 STRATEGY: Place limit orders and wait for better prices")
        print(f"🎯 MONITOR: Watch for price movements to hit profit targets")

def main():
    """Main analysis"""
    
    print("🚀 ENA POSITION HEDGING STRATEGY")
    print("=" * 60)
    print("Based on your current ENA positions")
    print("=" * 60)
    
    # Analyze current positions
    positions = analyze_ena_positions()
    
    # Calculate hedging strategy
    actions = calculate_hedging_strategy(positions)
    
    # Show execution summary
    show_execution_summary(actions)
    
    print(f"\n📋 NEXT STEPS")
    print("=" * 50)
    print(f"1. Monitor ENA price movements")
    print(f"2. Execute profitable actions when targets are reached")
    print(f"3. Place limit orders at best bid/ask for new positions")
    print(f"4. Use automated bot for 24/7 hedging execution")
    print(f"5. Risk management: Keep position sizes manageable")

if __name__ == "__main__":
    main()
