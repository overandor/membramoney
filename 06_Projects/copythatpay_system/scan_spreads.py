#!/usr/bin/env python3
"""Scan spreads on micro whitelist to find symbols with spread > 2x taker fee."""
import ccxt
import time

TAKER_FEE = 0.00075
MIN_EDGE = TAKER_FEE * 2  # 0.15%

WHITELIST = [
    'DOGS/USDT:USDT', 'SLP/USDT:USDT', 'MBOX/USDT:USDT', 'ZK/USDT:USDT',
    'TLM/USDT:USDT', 'SUN/USDT:USDT', 'RDNT/USDT:USDT', 'ICP/USDT:USDT',
    'BICO/USDT:USDT', 'FLOW/USDT:USDT', 'MEME/USDT:USDT', 'JASMY/USDT:USDT',
    'MINA/USDT:USDT', 'WAXP/USDT:USDT', 'PIXEL/USDT:USDT', 'ALT/USDT:USDT',
    'HOOK/USDT:USDT', 'MANA/USDT:USDT', 'FIL/USDT:USDT', 'FIO/USDT:USDT',
    'XAI/USDT:USDT', 'ME/USDT:USDT', 'IOST/USDT:USDT', 'GMT/USDT:USDT',
    'ACE/USDT:USDT', 'DEGO/USDT:USDT', 'W/USDT:USDT', 'DYDX/USDT:USDT',
    'HIPPO/USDT:USDT', 'COTI/USDT:USDT', 'NFP/USDT:USDT', 'USUAL/USDT:USDT',
    'ALICE/USDT:USDT', 'HFT/USDT:USDT', 'HMSTR/USDT:USDT', 'MOG/USDT:USDT',
    'FIDA/USDT:USDT', 'LRC/USDT:USDT', 'SAGA/USDT:USDT', 'ZKJ/USDT:USDT',
    'DYM/USDT:USDT', 'WOO/USDT:USDT', 'MOVR/USDT:USDT', 'MOVE/USDT:USDT',
    'RPL/USDT:USDT', 'C98/USDT:USDT', 'AI/USDT:USDT', 'BAND/USDT:USDT',
    'ONE/USDT:USDT', 'CRV/USDT:USDT', 'OGN/USDT:USDT', 'AEVO/USDT:USDT',
    'XVS/USDT:USDT', 'CELR/USDT:USDT', 'NTRN/USDT:USDT', 'MTL/USDT:USDT',
    'ETHW/USDT:USDT', 'SNX/USDT:USDT', 'ID/USDT:USDT', 'BLUR/USDT:USDT',
    'PHA/USDT:USDT', 'BIO/USDT:USDT', 'GALA/USDT:USDT', 'MAVIA/USDT:USDT',
    'CTSI/USDT:USDT', 'METIS/USDT:USDT', 'MERL/USDT:USDT', 'REZ/USDT:USDT',
    'ICX/USDT:USDT', 'SOLV/USDT:USDT', 'TNSR/USDT:USDT', 'YGG/USDT:USDT',
    'NOT/USDT:USDT', 'NIL/USDT:USDT', 'ZIL/USDT:USDT', 'MBABYDOGE/USDT:USDT',
    'SCR/USDT:USDT', 'S/USDT:USDT', 'TRU/USDT:USDT', 'STRK/USDT:USDT',
    'ETHFI/USDT:USDT', 'CATI/USDT:USDT', 'ILV/USDT:USDT', 'XCN/USDT:USDT',
    'ANIME/USDT:USDT', 'IOTX/USDT:USDT', 'RUNE/USDT:USDT', 'CORE/USDT:USDT',
    'ANKR/USDT:USDT',
]

exchange = ccxt.gateio({'options': {'defaultType': 'swap'}})
exchange.load_markets()

results = []
for sym in WHITELIST:
    try:
        book = exchange.fetch_order_book(sym, limit=5)
        bid = book['bids'][0][0] if book['bids'] else 0
        ask = book['asks'][0][0] if book['asks'] else 0
        if bid <= 0 or ask <= 0:
            continue
        mid = (bid + ask) / 2
        spread_pct = (ask - bid) / mid
        
        ticker = exchange.fetch_ticker(sym)
        vol = ticker.get('quoteVolume', 0) or 0
        
        net_edge = spread_pct - MIN_EDGE
        results.append({
            'symbol': sym,
            'spread': spread_pct,
            'net_edge': net_edge,
            'volume': vol,
            'profitable': spread_pct > MIN_EDGE,
        })
        time.sleep(0.15)
    except Exception as e:
        print(f"  {sym}: error {e}")

# Sort by net edge (best first)
results.sort(key=lambda x: x['net_edge'], reverse=True)

print(f"\n{'='*90}")
print(f"SPREAD SCAN — {len(results)} symbols | Min edge: {MIN_EDGE:.4%} (2x taker fee)")
print(f"{'='*90}")
print(f"{'Symbol':<25} {'Spread':>10} {'Net Edge':>10} {'Volume':>15} {'Tradeable':>10}")
print(f"{'-'*90}")

profitable_count = 0
for r in results:
    tag = "✅" if r['profitable'] else "❌"
    if r['profitable']:
        profitable_count += 1
    print(f"{r['symbol']:<25} {r['spread']:>9.4%} {r['net_edge']:>+9.4%} ${r['volume']:>13,.0f} {tag:>10}")

print(f"\n{'='*90}")
print(f"PROFITABLE: {profitable_count}/{len(results)} symbols have spread > {MIN_EDGE:.4%}")
print(f"\nTOP 5 for trading:")
top5 = [r for r in results if r['profitable']][:5]
for r in top5:
    short = r['symbol'].split('/')[0]
    print(f"  '{r['symbol']}',  # spread={r['spread']:.3%} net_edge={r['net_edge']:+.3%} vol=${r['volume']:,.0f}")
