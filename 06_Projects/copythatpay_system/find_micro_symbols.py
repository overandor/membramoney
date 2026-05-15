#!/usr/bin/env python3
"""
Find Gate.io futures with smallest contract notional values.
This shows which symbols allow the smallest position sizes.
"""

import ccxt
import asyncio

async def find_micro_symbols():
    exchange = ccxt.gateio({
        'enableRateLimit': True,
    })

    try:
        markets = await exchange.load_markets()
        print(f"Loaded {len(markets)} markets")
    except Exception as e:
        print(f"Failed to load markets: {e}")
        print("Trying manual market fetch...")
        try:
            markets = await exchange.fetch_markets()
            print(f"Fetched {len(markets)} markets")
        except Exception as e2:
            print(f"Manual fetch also failed: {e2}")
            return

    results = []

    for symbol, market in exchange.markets.items():
        if not market.get('swap'):
            continue
        if market.get('quote') != 'USDT':
            continue
        if not market.get('active', True):
            continue

        try:
            ticker = await exchange.fetch_ticker(symbol)
            price = ticker['last']
            contract_size = float(market.get('contractSize', 1) or 1)

            if price and contract_size:
                notional = price * contract_size
                volume = ticker.get('quoteVolume', 0)

                results.append({
                    'symbol': symbol,
                    'price': price,
                    'contractSize': contract_size,
                    'min_notional_1ct': notional,
                    'volume_24h': volume
                })
        except Exception as e:
            continue

    # sort by smallest notional
    results = sorted(results, key=lambda x: x['min_notional_1ct'])

    print("\n" + "="*80)
    print("=== SMALLEST CONTRACT NOTIONAL VALUES ===")
    print("="*80)
    print(f"{'Symbol':<25} {'Price':<12} {'Contract Size':<15} {'1 Contract':<12} {'24h Volume':<15}")
    print("-"*80)
    
    for r in results[:30]:
        print(f"{r['symbol']:<25} ${r['price']:<11.6f} {r['contractSize']:<15} ${r['min_notional_1ct']:<11.6f} ${r['volume_24h']:>14,.0f}")

    # Also show symbols <= $0.10
    micro_symbols = [r for r in results if r['min_notional_1ct'] <= 0.10]
    print(f"\n=== SYMBOLS WITH <= $0.10 PER CONTRACT: {len(micro_symbols)} ===")
    
    for r in micro_symbols:
        print(f"{r['symbol']} | 1ct=${r['min_notional_1ct']:.6f} | vol=${r['volume_24h']:,.0f}")

    await exchange.close()

if __name__ == '__main__':
    asyncio.run(find_micro_symbols())
