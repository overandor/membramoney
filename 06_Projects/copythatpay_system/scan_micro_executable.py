#!/usr/bin/env python3
"""
Scan for symbols with smallest executable trade sizes.
Accounts for contract size AND minimum order constraints.
"""

import ccxt

def scan_micro_symbols():
    exchange = ccxt.gateio({
        'enableRateLimit': True,
        'options': {'defaultType': 'swap'},
    })

    try:
        markets = exchange.load_markets()
        print(f"Loaded {len(markets)} markets")
    except Exception as e:
        print(f"Failed to load markets: {e}")
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
            ticker = exchange.fetch_ticker(symbol)
            price = ticker['last']
            cs = float(market.get('contractSize', 1) or 1)
            min_ct = float(market.get('limits', {}).get('amount', {}).get('min', 1) or 1)

            if not price or not cs:
                continue

            notional_1ct = price * cs
            min_trade = notional_1ct * min_ct
            volume = ticker.get('quoteVolume', 0)

            results.append({
                'symbol': symbol,
                'price': price,
                'contractSize': cs,
                'min_ct': min_ct,
                'min_trade_notional': min_trade,
                'volume_24h': volume
            })

        except Exception as e:
            continue

    # Sort by smallest real trade size
    results.sort(key=lambda x: x['min_trade_notional'])

    print("\n" + "="*100)
    print("=== TRUE MICRO MARKETS (SMALLEST EXECUTABLE TRADE SIZE) ===")
    print("="*100)
    print(f"{'Symbol':<25} {'Price':<12} {'CS':<8} {'Min Ct':<8} {'Min Trade':<15} {'24h Volume':<15}")
    print("-"*100)
    
    for r in results[:40]:
        print(f"{r['symbol']:<25} ${r['price']:<11.6f} {r['contractSize']:<8} {r['min_ct']:<8} ${r['min_trade_notional']:<14.6f} ${r['volume_24h']:>14,.0f}")

    # Filter for <= $0.05
    ultra_micro = [r for r in results if r['min_trade_notional'] <= 0.05]
    print(f"\n=== ULTRA MICRO (<= $0.05 MIN TRADE): {len(ultra_micro)} symbols ===")
    for r in ultra_micro:
        print(f"{r['symbol']} | min_trade=${r['min_trade_notional']:.6f} | cs={r['contractSize']} | min_ct={r['min_ct']} | vol=${r['volume_24h']:,.0f}")

    # Filter for <= $0.10
    micro = [r for r in results if r['min_trade_notional'] <= 0.10]
    print(f"\n=== MICRO (<= $0.10 MIN TRADE): {len(micro)} symbols ===")
    for r in micro[:20]:
        print(f"{r['symbol']} | min_trade=${r['min_trade_notional']:.6f} | vol=${r['volume_24h']:,.0f}")

    pass  # sync gateio has no close()

if __name__ == '__main__':
    scan_micro_symbols()
