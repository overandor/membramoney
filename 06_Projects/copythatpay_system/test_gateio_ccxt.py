#!/usr/bin/env python3
"""Test CCXT connectivity to Gate.io"""
import ccxt
import asyncio

async def test_ccxt():
    print("Testing CCXT Gate.io connectivity...")
    
    # Test 1: Simple sync initialization
    print("\n1. Testing sync initialization...")
    try:
        ex = ccxt.gateio({
            'timeout': 60000,
            'enableRateLimit': True,
            'headers': {'User-Agent': 'Mozilla/5.0'},
            'options': {'fetchCurrencies': False}
        })
        print(f"Exchange ID: {ex.id}")
        print(f"Timeout: {ex.timeout}ms")
    except Exception as e:
        print(f"Sync init failed: {e}")
        return
    
    # Test 2: Load markets (sync)
    print("\n2. Testing sync load_markets...")
    try:
        markets = ex.load_markets()
        print(f"Loaded {len(markets)} markets")
    except Exception as e:
        print(f"Sync load_markets failed: {e}")
    
    # Test 3: Async initialization
    print("\n3. Testing async initialization...")
    try:
        ex_async = ccxt.async_support.gateio({
            'timeout': 60000,
            'enableRateLimit': True,
            'headers': {'User-Agent': 'Mozilla/5.0'},
            'options': {'fetchCurrencies': False}
        })
        print(f"Async exchange ID: {ex_async.id}")
        
        print("\n4. Testing async load_markets...")
        await ex_async.load_markets()
        print(f"Async loaded {len(ex_async.markets)} markets")
        
        await ex_async.close()
    except Exception as e:
        print(f"Async failed: {e}")
    
    print("\n✓ Test complete")

if __name__ == '__main__':
    asyncio.run(test_ccxt())
