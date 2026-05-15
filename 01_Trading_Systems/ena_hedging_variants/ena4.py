import ccxt
import time
import requests   # <-- needed for the manual HTTP call
import hashlib
import hmac
import json
import httpx
from rich.console import Console
from datetime import datetime

# ==============================
#  API Credentials
# ==============================
API_KEY = '4efbe203fbac0e4bcd0003a0910c801b'
API_SECRET = '8b0e9cf47fdd97f2a42bca571a74105c53a5f906cd4ada125938d05115d063a0'

# ==============================
#  Initialize Exchange
# ==============================
exchange = ccxt.gateio({
    'apiKey': API_KEY,
    'secret': API_SECRET,
    'enableRateLimit': True,
    'options': {'defaultType': 'swap'}
})

# Gate.io V4 API base
API_BASE = 'https://api.gateio.ws/api/v4'

# ==============================
#  Trading Configuration
# ==============================
PAIR = "ENA_USDT"  # Replace with a valid symbol (e.g., "BTC_USDT")
LEVERAGE = 3
GROSS_THRESHOLD = 0.03
INITIAL_TRADE_SIZE = 1     # One contract per order
PRICE_OFFSET = 0.0000369   # For improving limit order price
LIMIT_RETRY_DELAY = 1
MAX_LIMIT_RETRIES = 9
API_RETRY_DELAY = 0.5
LOOP_DELAY = 0.5

# When one side closes, add this many contracts (DCA) on the opposite side.
DCA_SIZE = 0.69

# ==============================
#  Utility: Wait for Order Fill
# ==============================
def wait_for_fill(symbol, side, expected_size, timeout=10):
    """
    Polls the exchange for up to timeout seconds to verify that the position has been filled.
    Returns True if the position is filled (contracts >= expected_size), False otherwise.
    """
    start = time.time()
    while time.time() - start < timeout:
        positions = exchange.fetch_positions([symbol], params={'type': 'swap'})
        pos = next((p for p in positions if p.get('side') == ('long' if side=="buy" else 'short')), None)
        if pos and float(pos.get('contracts', 0)) >= expected_size:
            print(f"Position filled: {symbol} {side} {expected_size}")
            return True
        time.sleep(1)
    print(f"Position not filled: {symbol} {side} {expected_size}")
    return False

# ==============================
#  Open Position Function (using CCXT)
# ==============================
def open_position(symbol, side, size):
    """
    Opens a position on the given side (buy for LONG, sell for SHORT) using a CCXT limit order.
    Returns the approximate entry (limit) price used.
    """
    try:
        exchange.set_leverage(LEVERAGE, symbol, params={'type': 'swap'})
        ticker = exchange.fetch_ticker(symbol, params={'type': 'swap'})
        market_price = float(ticker['last'])
        if side == "buy":
            limit_price = market_price * (1 - PRICE_OFFSET)
        else:
            limit_price = market_price * (1 + PRICE_OFFSET)
        print(f"Opening {side.upper()} position of {size} @ ~{limit_price:.6f} (MP={market_price:.6f})")
        placed_order = None
        for attempt in range(1, MAX_LIMIT_RETRIES + 1):
            try:
                placed_order = exchange.create_limit_order(
                    symbol=symbol,
                    side=side,
                    amount=size,
                    price=limit_price,
                    params={'marginMode': 'cross', 'type': 'swap'}
                )
                print(f" [{attempt}/{MAX_LIMIT_RETRIES}] {side.upper()} order placed @ {limit_price:.6f}")
                break
            except Exception as e:
                print(f" [{attempt}/{MAX_LIMIT_RETRIES}] {side.upper()} order failed: {e}")
                time.sleep(LIMIT_RETRY_DELAY)
                if side == "buy":
                    limit_price *= (1 - PRICE_OFFSET)
                else:
                    limit_price *= (1 + PRICE_OFFSET)
        if placed_order is None:
            print(f" Could not open {side.upper()} position after max retries.")
            return None
        # Wait for the order to fill (optional)
        if wait_for_fill(symbol, side, size, timeout=6):
            print(f" {side.upper()} order filled.")
        else:
            print(f" {side.upper()} order not fully filled within timeout.")
        return limit_price
    except Exception as e:
        print(f" open_position error: {e}")
        return None

def cancel_pending_reduce_orders(symbol):
    try:
        # You can adjust the parameters based on your exchange's API requirements.
        open_orders = exchange.fetch_open_orders(symbol, params={'marginMode': 'cross', 'type': 'swap'})
        for order in open_orders:
            if order.get('params', {}).get('reduceOnly', False):
                exchange.cancel_order(order['id'], symbol, params={'marginMode': 'cross', 'type': 'swap'})
                print(f"Cancelled pending order {order['id']}")
    except Exception as e:
        print(f" Error cancelling pending orders: {e}")

# ==============================
#  Close Position at Target Function
# ==============================
def close_position_at_target(symbol, side, target_price, size):
    """
    Closes an existing position on the specified side using a limit order at the target price.
    For LONG positions (side 'buy'), we send a SELL order.
    For SHORT positions (side 'sell'), we send a BUY order.
    Returns True if successful, False otherwise.
    """
    try:
        if side == "buy":
            close_side = "sell"
        else:
            close_side = "buy"
        
        # Before attempting a new close order, cancel any pending reduce-only orders.
        cancel_pending_reduce_orders(symbol)
        
        print(f" Attempting to close {side.upper()} position of size {size} @ target ~{target_price:.6f}")
        close_order = None
        # Use exponential backoff for retry attempts
        delay = LIMIT_RETRY_DELAY
        for attempt in range(1, MAX_LIMIT_RETRIES + 1):
            try:
                close_order = exchange.create_limit_order(
                    symbol=symbol,
                    side=close_side,
                    amount=size,
                    price=target_price,
                    params={'marginMode': 'cross', 'reduceOnly': True, 'type': 'swap'}
                )
                print(f" [{attempt}/{MAX_LIMIT_RETRIES}] Close order placed @ {target_price:.6f}")
                break  # order placed successfully
            except Exception as e:
                print(f" [{attempt}/{MAX_LIMIT_RETRIES}] Close attempt failed: {e}")
                time.sleep(delay)
                delay *= 2  # Exponential backoff
                # Optionally try cancelling pending orders again
                cancel_pending_reduce_orders(symbol)
        if close_order is None:
            print(f" Could not close {side.upper()} position after max retries.")
            return False
        return True
    except Exception as e:
        print(f" close_position_at_target error: {e}")
        return False

# ==============================
#  Profit Check & Closure Function
# ==============================
def check_profit_and_close():
    """
    Checks each open position's unrealized profit and closes it via a limit order
    if the unrealized profit meets or exceeds the effective threshold.
    Returns (closed_long, closed_short) booleans.
    """
    closed_long = closed_short = False

    # Define your base desired net profit and estimated fee cost per contract:
    base_profit_per_contract = 0.0369   # e.g., $0.0369 net profit per contract
    fee_cost_per_contract = 0.002       # e.g., $0.002 per contract to cover fees & slippage

    # Get all open positions
    positions = exchange.fetch_positions([PAIR], params={'type': 'swap'})

    # Process LONG positions
    for pos in (p for p in positions if p.get('side') == 'long'):
        size = float(pos.get('contracts', 0))
        entry_price = float(pos.get('entryPrice', 0))
        unrealized = float(pos.get('unrealizedPnl', 0))
        if size > 0:
            effective_threshold = (base_profit_per_contract + fee_cost_per_contract) * size
            target_exit = entry_price + (effective_threshold / size)
            if unrealized >= effective_threshold:
                if close_position_at_target(PAIR, "buy", target_exit, size):
                    closed_long = True

    # Process SHORT positions
    for pos in (p for p in positions if p.get('side') == 'short'):
        size = float(pos.get('contracts', 0))
        entry_price = float(pos.get('entryPrice', 0))
        unrealized = float(pos.get('unrealizedPnl', 0))
        if size > 0:
            effective_threshold = (base_profit_per_contract + fee_cost_per_contract) * size
            target_exit = entry_price - (effective_threshold / size)
            if unrealized >= effective_threshold:
                if close_position_at_target(PAIR, "sell", target_exit, size):
                    closed_short = True

    return (closed_long, closed_short)
    # Define your base desired net profit and estimated fee cost per contract:
    base_profit_per_contract = 0.0369   # e.g., $0.01 net profit per contract
    fee_cost_per_contract = 0.002        # e.g., $0.002 per contract to cover fees & slippage
    
    positions = exchange.fetch_positions([PAIR], params={'type': 'swap'})
    
    # Process LONG positions
    long_pos = next((p for p in positions if p.get('side') == 'long'), None)
    if long_pos:
        size = float(long_pos.get('contracts', 0))
        entry_price = float(long_pos.get('entryPrice', 0))
        unrealized = float(long_pos.get('unrealizedPnl', 0))
        if size > 0:
            effective_threshold = (base_profit_per_contract + fee_cost_per_contract) * size
            target_exit = entry_price + (effective_threshold / size)
            print(f"[LONG] Entry: {entry_price:.6f}, Size: {size:.6f}, Unrealized PnL: ${unrealized:.6f}, Effective TP: ${effective_threshold:.6f}, Target Exit: {target_exit:.6f}")
            if unrealized >= effective_threshold:
                print(f" LONG profit threshold reached (Unrealized: ${unrealized:.6f} >= ${effective_threshold:.6f})")
                if close_position_at_target(PAIR, "buy", target_exit, size):
                    closed_long = True

    # Process SHORT positions
    short_pos = next((p for p in positions if p.get('side') == 'short'), None)
    if short_pos:
        size = float(short_pos.get('contracts', 0))
        entry_price = float(short_pos.get('entryPrice', 0))
        unrealized = float(short_pos.get('unrealizedPnl', 0))
        if size > 0:
            effective_threshold = (base_profit_per_contract + fee_cost_per_contract) * size
            target_exit = entry_price - (effective_threshold / size)
            print(f"[SHORT] Entry: {entry_price:.6f}, Size: {size:.6f}, Unrealized PnL: ${unrealized:.6f}, Effective TP: ${effective_threshold:.6f}, Target Exit: {target_exit:.6f}")
            if unrealized >= effective_threshold:
                print(f" SHORT profit threshold reached (Unrealized: ${unrealized:.6f} >= ${effective_threshold:.6f})")
                if close_position_at_target(PAIR, "sell", target_exit, size):
                    closed_short = True