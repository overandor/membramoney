#!/usr/bin/env python3
import os
"""
COMPLETE GATE.IO TRADING DASHBOARD
Spot + Futures + Trading Strategy
Includes working futures account methods from gatefutures.py
"""

import gate_api
from gate_api import ApiClient, Configuration, SpotApi, MarginApi, FuturesApi
import time
from datetime import datetime
from typing import Optional, Dict, Any

# Your API credentials
GATE_API_KEY = os.getenv("GATE_API_KEY", "")
GATE_API_SECRET = os.getenv("GATE_API_SECRET", "")
SETTLE = 'usdt'

def safe_float(value, default=0.0):
    """Safely convert to float"""
    try:
        return float(value)
    except (ValueError, TypeError):
        return default

def with_retry(fn, *args, retries=3, base_delay=1.0, **kwargs):
    """Retry function from gatefutures.py"""
    delay = base_delay
    last_exc = None
    for attempt in range(1, retries + 1):
        try:
            return fn(*args, **kwargs)
        except Exception as exc:
            last_exc = exc
            print(f"⚠️ Retry {attempt} on {getattr(fn, '__name__', 'call')}: {exc}")
            if attempt >= retries:
                break
            time.sleep(delay)
            delay *= 2
    if last_exc:
        print(f"❌ Retry exhausted on {getattr(fn, '__name__', 'call')}: {last_exc}")
    return None

class GateClient:
    """Enhanced Gate.io client with futures strategy from gatefutures.py"""
    
    def __init__(self):
        self.cfg = Configuration(key=GATE_API_KEY, secret=GATE_API_SECRET)
        self._spot_client = SpotApi(ApiClient(self.cfg))
        self._futures_client = FuturesApi(ApiClient(self.cfg))
        self._margin_client = MarginApi(ApiClient(self.cfg))
    
    def get_futures_account(self) -> Optional[Dict[str, float]]:
        """Get futures account - from gatefutures.py"""
        if not self._futures_client:
            return None

        def _call() -> Any:
            return self._futures_client.list_futures_accounts(SETTLE)

        result = with_retry(_call)
        if result is None:
            return None

        acct = result[0] if isinstance(result, list) and result else result

        return {
            "total": safe_float(getattr(acct, "total", 0.0)),
            "available": safe_float(getattr(acct, "available", 0.0)),
            "position_margin": safe_float(getattr(acct, "position_margin", 0.0)),
            "order_margin": safe_float(getattr(acct, "order_margin", 0.0)),
            "unrealised_pnl": safe_float(getattr(acct, "unrealised_pnl", 0.0)),
            "currency": SETTLE.upper(),
        }

    def get_position(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Get specific position - from gatefutures.py"""
        if not self._futures_client:
            return None

        def _call() -> Any:
            return self._futures_client.get_position(SETTLE, symbol)

        pos = with_retry(_call)
        if pos is None:
            return None

        return {
            "contract": str(getattr(pos, "contract", symbol)),
            "size": safe_float(getattr(pos, "size", 0.0)),
            "entry_price": safe_float(getattr(pos, "entry_price", 0.0)),
            "mark_price": safe_float(getattr(pos, "mark_price", 0.0)),
            "liq_price": safe_float(getattr(pos, "liq_price", 0.0)),
            "unrealised_pnl": safe_float(getattr(pos, "unrealised_pnl", 0.0)),
            "mode": str(getattr(pos, "mode", "")),
            "leverage": str(getattr(pos, "leverage", "")),
        }

    def get_order_book(self, symbol: str, limit: int = 20) -> Optional[Dict[str, Any]]:
        """Get order book - from gatefutures.py"""
        if not self._futures_client:
            return None

        def _call() -> Any:
            return self._futures_client.list_futures_order_book(SETTLE, contract=symbol, limit=limit)

        book = with_retry(_call)
        if book is None:
            return None

        asks = getattr(book, "asks", []) or []
        bids = getattr(book, "bids", []) or []

        return {
            "contract": symbol,
            "best_ask": safe_float(asks[0].p, 0.0) if asks else 0.0,
            "best_bid": safe_float(bids[0].p, 0.0) if bids else 0.0,
            "ask_size_top": safe_float(asks[0].s, 0.0) if asks else 0.0,
            "bid_size_top": safe_float(bids[0].s, 0.0) if bids else 0.0,
            "asks": [
                {"price": safe_float(x.p, 0.0), "size": safe_float(x.s, 0.0)}
                for x in asks[:limit]
            ],
            "bids": [
                {"price": safe_float(x.p, 0.0), "size": safe_float(x.s, 0.0)}
                for x in bids[:limit]
            ],
        }

def print_separator(title):
    print(f"\n{'='*70}")
    print(f"🔍 {title}")
    print(f"{'='*70}")

def check_spot_balances(client):
    """Check spot account balances"""
    try:
        print("📊 SPOT ACCOUNT BALANCES:")
        balances = client._spot_client.list_spot_accounts()
        
        total_usdt_value = 0.0
        has_balance = False
        
        for balance in balances:
            available = float(balance.available)
            
            if available > 0:
                has_balance = True
                print(f"  🪙 {balance.currency:<8} {available:>12.6f}")
                
                # Calculate USDT value if not USDT
                if balance.currency != 'USDT' and available > 0:
                    try:
                        ticker = client._spot_client.list_tickers(currency_pair=f"{balance.currency}_USDT")[0]
                        price = float(ticker.last)
                        usdt_value = available * price
                        total_usdt_value += usdt_value
                        print(f"     💵 Value: ${usdt_value:.6f} @ ${price:.6f}")
                    except:
                        print(f"     💵 Value: Unknown price")
                elif balance.currency == 'USDT':
                    total_usdt_value += available
        
        if not has_balance:
            print("  ❌ No balances found")
        
        print(f"\n💰 Total Spot Value: ${total_usdt_value:.6f}")
        return total_usdt_value
        
    except Exception as e:
        print(f"❌ Spot balance error: {e}")
        return 0.0

def check_futures_account(client):
    """Check futures account using gatefutures.py methods"""
    try:
        print("📊 FUTURES ACCOUNT BALANCES:")
        
        # Get futures account using gatefutures.py method
        account = client.get_futures_account()
        if account:
            print(f"  💰 Total Balance: ${account['total']:.6f}")
            print(f"  💵 Available: ${account['available']:.6f}")
            print(f"  📊 Position Margin: ${account['position_margin']:.6f}")
            print(f"  📋 Order Margin: ${account['order_margin']:.6f}")
            print(f"  📈 Unrealized PNL: ${account['unrealised_pnl']:.6f}")
            print(f"  💱 Currency: {account['currency']}")
            
            return account['total']
        else:
            print("  ❌ Could not get futures account")
            
        # Fallback: Show positions
        try:
            positions = client._futures_client.list_positions(settle='usdt')
            active_positions = [p for p in positions if float(p.size) != 0]
            
            if active_positions:
                print(f"  📈 Active Positions: {len(active_positions)}")
                total_unrealized = 0.0
                
                for pos in active_positions[:10]:  # Show top 10
                    size = float(pos.size)
                    pnl = float(pos.unrealised_pnl)
                    total_unrealized += pnl
                    
                    direction = "LONG" if size > 0 else "SHORT"
                    print(f"     {pos.contract:<15} {direction:<5} Size:{abs(size):>8} PNL:${pnl:>8.2f}")
                
                print(f"  💰 Total Unrealized PNL: ${total_unrealized:.2f}")
            
        except Exception as e:
            print(f"  ⚠️ Positions error: {e}")
        
        return 0.0
        
    except Exception as e:
        print(f"❌ Futures balance error: {e}")
        return 0.0

def check_futures_positions(client):
    """Detailed futures position analysis"""
    try:
        print("📊 FUTURES POSITION ANALYSIS:")
        
        # Get all positions
        positions = client._futures_client.list_positions(settle='usdt')
        active_positions = [p for p in positions if float(p.size) != 0]
        
        if not active_positions:
            print("  ❌ No active futures positions")
            return
        
        print(f"  📈 Total Active Positions: {len(active_positions)}")
        
        total_pnl = 0.0
        total_margin = 0.0
        
        for pos in active_positions:
            symbol = pos.contract
            size = float(pos.size)
            pnl = float(pos.unrealised_pnl)
            
            # Get detailed position info using gatefutures.py method
            detail = client.get_position(symbol)
            if detail:
                entry_price = detail['entry_price']
                mark_price = detail['mark_price']
                liq_price = detail['liq_price']
                leverage = detail['leverage']
                
                direction = "🟢 LONG" if size > 0 else "🔴 SHORT"
                
                print(f"\n  {direction} {symbol}")
                print(f"     Size: {abs(size):.2f}")
                print(f"     Entry: ${entry_price:.6f}")
                print(f"     Mark:  ${mark_price:.6f}")
                print(f"     PNL:   ${pnl:+.2f}")
                print(f"     Liq:   ${liq_price:.6f}" if liq_price > 0 else "     Liq:   N/A")
                print(f"     Lev:   {leverage}x")
                
                total_pnl += pnl
                
                # Calculate approximate margin used
                if mark_price > 0 and leverage:
                    margin = abs(size) * mark_price / float(leverage) if leverage.replace('.', '').isdigit() else 0
                    total_margin += margin
        
        print(f"\n  📊 SUMMARY:")
        print(f"     Total PNL: ${total_pnl:+.2f}")
        print(f"     Est. Margin: ${total_margin:.2f}")
        print(f"     ROI: {(total_pnl/total_margin*100 if total_margin > 0 else 0):+.2f}%")
        
    except Exception as e:
        print(f"❌ Position analysis error: {e}")

def check_market_opportunities(client):
    """Check current market opportunities"""
    try:
        print("📊 MARKET OPPORTUNITIES:")
        
        # Get top futures contracts by volume
        tickers = client._futures_client.list_futures_tickers(settle='usdt')
        
        if tickers:
            # Sort by volume
            high_volume = sorted(tickers, key=lambda x: float(x.base_volume), reverse=True)[:10]
            
            print("  🔥 TOP VOLUME FUTURES:")
            for ticker in high_volume:
                contract = ticker.contract
                price = float(ticker.last)
                volume = float(ticker.base_volume)
                change = float(ticker.change_percentage)
                
                direction = "📈" if change > 0 else "📉"
                print(f"     {contract:<15} ${price:.6f} Vol:{volume:>10.0f} {direction}{change:+.2f}%")
        
        # Get order book for top contract
        if high_volume:
            top_contract = high_volume[0].contract
            book = client.get_order_book(top_contract, limit=5)
            
            if book:
                print(f"\n  📊 ORDER BOOK: {top_contract}")
                print(f"     Best Bid: ${book['best_bid']:.6f} (Size: {book['bid_size_top']:.2f})")
                print(f"     Best Ask: ${book['best_ask']:.6f} (Size: {book['ask_size_top']:.2f})")
                print(f"     Spread: ${book['best_ask'] - book['best_bid']:.6f}")
        
    except Exception as e:
        print(f"❌ Market opportunities error: {e}")

def main():
    print("🚀 COMPLETE GATE.IO TRADING DASHBOARD")
    print("="*70)
    print(f"🔑 API Key: {GATE_API_KEY[:10]}...")
    print(f"🔑 Using enhanced client from gatefutures.py")
    
    # Initialize enhanced client
    client = GateClient()
    
    # Check all accounts
    print_separator("SPOT ACCOUNT")
    spot_value = check_spot_balances(client)
    
    print_separator("FUTURES ACCOUNT")
    futures_value = check_futures_account(client)
    
    print_separator("FUTURES POSITION ANALYSIS")
    check_futures_positions(client)
    
    print_separator("MARKET OPPORTUNITIES")
    check_market_opportunities(client)
    
    # Summary
    print_separator("TRADING SUMMARY")
    total_value = spot_value + futures_value
    print(f"💰 Total Account Value: ${total_value:.6f}")
    print(f"   Spot Trading: ${spot_value:.6f}")
    print(f"   Futures Trading: ${futures_value:.6f}")
    
    print(f"\n✅ Dashboard complete!")
    print(f"🕐 Checked at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"🚀 Ready for trading decisions!")

if __name__ == "__main__":
    main()
