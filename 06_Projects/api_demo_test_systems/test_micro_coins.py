#!/usr/bin/env python3
import requests

r = requests.get('https://api.gateio.ws/api/v4/spot/tickers')
data = r.json()
micro = [t for t in data if t.get('currency_pair', '').endswith('_USDT') and float(t.get('last', 999)) < 0.10]
micro_sorted = sorted(micro, key=lambda x: float(x.get('quote_volume', 0)), reverse=True)

print("=" * 60)
print("🪙 GATE.IO MICRO COINS ($0 - $0.10)")
print("=" * 60)
print(f"\nFound {len(micro_sorted)} coins under $0.10\n")

print("Top 30 by volume:")
for t in micro_sorted[:30]:
    symbol = t['currency_pair'].replace('_USDT', '')
    price = float(t['last'])
    vol = float(t.get('quote_volume', 0))
    print(f"  {symbol:12} ${price:.6f}  (Vol: ${vol:,.0f})")

print("\n" + "=" * 60)
print("COPY-PASTE LIST (comma-separated):")
print("=" * 60)
symbols_list = [t['currency_pair'].replace('_USDT', '') for t in micro_sorted]
print(", ".join(symbols_list[:50]))
