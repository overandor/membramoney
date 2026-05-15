#!/usr/bin/env python3
"""
Check all Gate.io futures symbols that allow 1 cent notional trading.
Finds symbols where 1 contract costs $0.01 or less.
"""

import ccxt
import asyncio
from rich.console import Console
from rich.table import Table

console = Console()

async def check_symbols():
    """Check all symbols for 1 cent notional capability."""
    exchange = ccxt.gateio({
        'enableRateLimit': True,
        'options': {
            'defaultType': 'swap',
            'defaultSettle': 'usdt',
        }
    })
    
    try:
        # Try loading markets with error handling
        markets = await exchange.load_markets()
        console.print(f'[green]Loaded {len(markets)} markets[/green]')
    except Exception as e:
        console.print(f'[red]Failed to load markets: {e}')
        console.print('[yellow]Trying alternative approach...[/yellow]')
        try:
            # Try to fetch markets directly
            markets = await exchange.fetch_markets()
            console.print(f'[green]Fetched {len(markets)} markets via alternative method[/green]')
        except Exception as e2:
            console.print(f'[red]Alternative method also failed: {e2}')
            return
    
    results = []
    
    for symbol, market in exchange.markets.items():
        # Only check USDT futures
        if market.get('type') != 'swap' or market.get('settle') != 'usdt':
            continue
        
        if not market.get('active', True):
            continue
        
        try:
            # Get ticker for price
            ticker = await exchange.fetch_ticker(symbol)
            price = float(ticker.get('last', 0))
            
            if price <= 0:
                continue
            
            # Get contract size
            contract_size = float(market.get('contractSize', 1) or 1)
            
            # Calculate notional per contract
            notional = price * contract_size
            
            # Get 24h volume
            volume = float(ticker.get('quoteVolume', 0) or 0)
            
            # Get min order size
            min_amount = market.get('limits', {}).get('amount', {}).get('min', 1)
            min_notional = notional * float(min_amount)
            
            results.append({
                'symbol': symbol,
                'price': price,
                'contract_size': contract_size,
                'notional': notional,
                'volume': volume,
                'min_amount': min_amount,
                'min_notional': min_notional
            })
            
        except Exception as e:
            continue
    
    # Filter for 1 cent notional or less
    one_cent_symbols = [r for r in results if r['notional'] <= 0.01]
    
    # Sort by volume (descending)
    one_cent_symbols.sort(key=lambda x: x['volume'], reverse=True)
    
    # Display results
    console.print(f'\n[bold cyan]Found {len(one_cent_symbols)} symbols with ≤ $0.01 notional per contract[/bold cyan]\n')
    
    table = Table(title='1 Cent Notional Symbols (Sorted by Volume)')
    table.add_column('Symbol', style='cyan')
    table.add_column('Price', style='green')
    table.add_column('Contract Size', style='yellow')
    table.add_column('Notional/Contract', style='magenta')
    table.add_column('Min Order', style='red')
    table.add_column('Min Notional', style='red')
    table.add_column('24h Volume', style='blue')
    
    for r in one_cent_symbols[:50]:  # Top 50
        table.add_row(
            r['symbol'],
            f'${r["price"]:.8f}',
            f'{r["contract_size"]}',
            f'${r["notional"]:.6f}',
            f'{r["min_amount"]}',
            f'${r["min_notional"]:.6f}',
            f'${r["volume"]:,.0f}'
        )
    
    console.print(table)
    
    # Also show symbols with slightly higher notional (up to $0.10)
    ten_cent_symbols = [r for r in results if 0.01 < r['notional'] <= 0.10]
    ten_cent_symbols.sort(key=lambda x: x['volume'], reverse=True)
    
    console.print(f'\n[bold cyan]Found {len(ten_cent_symbols)} symbols with $0.01-$0.10 notional per contract[/bold cyan]\n')
    
    table2 = Table(title='10 Cent Notional Symbols (Sorted by Volume)')
    table2.add_column('Symbol', style='cyan')
    table2.add_column('Price', style='green')
    table2.add_column('Contract Size', style='yellow')
    table2.add_column('Notional/Contract', style='magenta')
    table2.add_column('24h Volume', style='blue')
    
    for r in ten_cent_symbols[:30]:  # Top 30
        table2.add_row(
            r['symbol'],
            f'${r["price"]:.8f}',
            f'{r["contract_size"]}',
            f'${r["notional"]:.6f}',
            f'${r["volume"]:,.0f}'
        )
    
    console.print(table2)
    
    # Save to file
    with open('one_cent_symbols.json', 'w') as f:
        import json
        json.dump(one_cent_symbols, f, indent=2)
    
    console.print(f'\n[green]Saved {len(one_cent_symbols)} symbols to one_cent_symbols.json[/green]')
    
    await exchange.close()

if __name__ == '__main__':
    asyncio.run(check_symbols())
