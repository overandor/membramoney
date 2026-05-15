#!/usr/bin/env python3
"""Flatten all open positions and cancel all orders. Emergency cleanup."""
import ccxt.async_support as ccxt
import asyncio
import os
from dotenv import load_dotenv

load_dotenv()

async def flatten():
    exchange = ccxt.gateio({
        'apiKey': os.getenv('GATE_API_KEY', ''),
        'secret': os.getenv('GATE_API_SECRET', ''),
        'enableRateLimit': True,
        'options': {'defaultType': 'swap', 'defaultSettle': 'usdt'},
    })
    
    try:
        # Cancel all open orders
        print("Cancelling all open orders...")
        try:
            orders = await exchange.fetch_open_orders(params={'type': 'swap'})
            for o in orders:
                try:
                    await exchange.cancel_order(o['id'], o['symbol'], {'type': 'swap'})
                    print(f"  Cancelled {o['id']} on {o['symbol']}")
                except Exception as e:
                    print(f"  Cancel failed: {e}")
        except Exception as e:
            print(f"  Fetch orders failed: {e}")
        
        # Close all positions
        print("\nClosing all positions...")
        positions = await exchange.fetch_positions(params={'type': 'swap'})
        has_positions = False
        for pos in positions:
            ct = float(pos.get('contracts', 0) or 0)
            if ct <= 0:
                continue
            has_positions = True
            sym = pos['symbol']
            side = pos['side']
            close_side = 'sell' if side == 'long' else 'buy'
            print(f"  {sym}: {side} {ct}ct → closing with {close_side} market order")
            try:
                await exchange.create_market_order(
                    sym, close_side, ct,
                    {'marginMode': 'isolated', 'reduceOnly': True, 'type': 'swap'})
                print(f"  ✓ Closed {sym} {side}")
            except Exception as e:
                print(f"  ✗ Failed: {e}")
            await asyncio.sleep(0.5)
        
        if not has_positions:
            print("  No open positions found.")
        
        # Show final balance
        balance = await exchange.fetch_balance({'type': 'swap'})
        total = float(balance.get('total', {}).get('USDT', 0))
        print(f"\nFinal balance: ${total:.4f}")
        
    finally:
        await exchange.close()

if __name__ == '__main__':
    asyncio.run(flatten())
