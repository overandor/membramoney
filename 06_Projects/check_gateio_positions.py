#!/usr/bin/env python3
"""Check current positions on Gate.io account"""
import ccxt
import os
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv('GATE_API_KEY')
API_SECRET = os.getenv('GATE_API_SECRET')

if not API_KEY or not API_SECRET:
    print("❌ ERROR: GATE_API_KEY and GATE_API_SECRET must be set in .env")
    exit(1)

print("Connecting to Gate.io...")
exchange = ccxt.gateio({
    'apiKey': API_KEY,
    'secret': API_SECRET,
    'enableRateLimit': True,
    'timeout': 30000,
    'options': {
        'defaultType': 'swap',
        'defaultSettle': 'usdt'
    }
})

try:
    print("\n📊 Fetching positions...")
    positions = exchange.fetch_positions()
    
    # Filter for non-zero positions
    active_positions = [p for p in positions if float(p.get('contracts', 0)) != 0]
    
    if not active_positions:
        print("\n✅ No open positions found")
    else:
        print(f"\n📈 Found {len(active_positions)} open position(s):")
        print("-" * 80)
        for pos in active_positions:
            symbol = pos.get('symbol', 'N/A')
            contracts = pos.get('contracts', 0)
            side = pos.get('side', 'N/A')
            entry_price = pos.get('entryPrice', 0)
            mark_price = pos.get('markPrice', 0)
            unrealized_pnl = pos.get('unrealizedPnl', 0)
            
            print(f"Symbol: {symbol}")
            print(f"  Side: {side}")
            print(f"  Contracts: {contracts}")
            print(f"  Entry Price: ${entry_price}")
            print(f"  Mark Price: ${mark_price}")
            print(f"  Unrealized PnL: ${unrealized_pnl}")
            print("-" * 80)
    
    # Also check balance
    print("\n💰 Fetching balance...")
    balance = exchange.fetch_balance()
    usdt_total = balance.get('total', {}).get('USDT', 0)
    usdt_free = balance.get('free', {}).get('USDT', 0)
    usdt_used = balance.get('used', {}).get('USDT', 0)
    
    print(f"USDT Total: ${usdt_total}")
    print(f"USDT Free: ${usdt_free}")
    print(f"USDT Used: ${usdt_used}")
    
except Exception as e:
    print(f"\n❌ Error: {e}")
    import traceback
    traceback.print_exc()

finally:
    exchange.close()
