


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
# 🎯 API Credentials
# ==============================
API_KEY = '4efbe203fbac0e4bcd0003a0910c801b'
API_SECRET = '8b0e9cf47fdd97f2a42bca571a74105c53a5f906cd4ada125938d05115d063a0'

# Gate.io V4 API base
API_BASE = 'https://api.gateio.ws/api/v4'


# ✅ Initialize CCXT for Gate.io perpetual futures (swap) using cross margin
exchange = ccxt.gateio({
    'apiKey': API_KEY,
    'secret': API_SECRET,
    'enableRateLimit': True,
    'options': {
        'defaultType': 'swap',
        'defaultSettle': 'usdt',
    }
})

console = Console()

# ==============================
# 🔲 Trading Configuration
# ==============================
PAIR = "MELANIA_USDT"  # Replace with a valid symbol (e.g., "BTC_USDT")
LEVERAGE = 10
# The gross threshold (in dollars) to exit a position. This number is set so that after fees and slippage your net profit is as desired.
GROSS_THRESHOLD = 0.0369
INITIAL_TRADE_SIZE = 1     # One contract per order
PRICE_OFFSET = 0.0000369   # For improving limit order price
LIMIT_RETRY_DELAY = 1
MAX_LIMIT_RETRIES = 9
API_RETRY_DELAY = 1
LOOP_DELAY = 1

# When one side closes, add this many contracts (DCA) on the opposite side.
DCA_SIZE = 1

# ==============================
# 1) Utility: Wait for Order Fill
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
            return True
        time.sleep(1)
    return False

# ==============================
# 2) Open Position Function (using CCXT)
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
        console.print(f"📌 Opening {side.upper()} position of {size} @ ~{limit_price:.6f} (MP={market_price:.6f})", style="bold cyan")
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
                console.print(f"✅ [{attempt}/{MAX_LIMIT_RETRIES}] {side.upper()} order placed @ {limit_price:.6f}", style="bold green")
                break
            except Exception as e:
                console.print(f"⚠️ Attempt {attempt}/{MAX_LIMIT_RETRIES} failed: {e}", style="bold yellow")
                time.sleep(LIMIT_RETRY_DELAY)
                if side == "buy":
                    limit_price *= (1 - PRICE_OFFSET)
                else:
                    limit_price *= (1 + PRICE_OFFSET)
        if placed_order is None:
            console.print(f"🚨 Could not open {side.upper()} position after max retries.", style="bold red")
            return None
        # Wait for the order to fill (optional)
        if wait_for_fill(symbol, side, size, timeout=10):
            console.print(f"✅ {side.upper()} order filled.", style="bold green")
        else:
            console.print(f"⚠️ {side.upper()} order not fully filled within timeout.", style="bold yellow")
        return limit_price
    except Exception as e:
        console.print(f"⚠️ open_position error: {e}", style="bold red")
        return None
def cancel_pending_reduce_orders(symbol):
    try:
        # You can adjust the parameters based on your exchange's API requirements.
        open_orders = exchange.fetch_open_orders(symbol, params={'marginMode': 'cross', 'type': 'swap'})
        for order in open_orders:
            if order.get('params', {}).get('reduceOnly', False):
                exchange.cancel_order(order['id'], symbol, params={'marginMode': 'cross', 'type': 'swap'})
                console.print(f"Cancelled pending order {order['id']}", style="bold magenta")
    except Exception as e:
        console.print(f"⚠️ Error cancelling pending orders: {e}", style="bold red")
# ==============================
# 3) Close Position at Target Function
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
        console.print(f"📌 Closing {side.upper()} position of size {size} @ target ~{target_price:.6f}", style="bold cyan")
        close_order = None
        for attempt in range(1, MAX_LIMIT_RETRIES + 1):
            try:
                close_order = exchange.create_limit_order(
                    symbol=symbol,
                    side=close_side,
                    amount=size,
                    price=target_price,
                    params={'marginMode': 'cross', 'reduceOnly': True, 'type': 'swap'}
                )
                console.print(f"✅ [{attempt}/{MAX_LIMIT_RETRIES}] Close order placed @ {target_price:.6f}", style="bold green")
                break
            except Exception as e:
                console.print(f"⚠️ Close attempt {attempt}/{MAX_LIMIT_RETRIES} failed: {e}", style="bold yellow")
                time.sleep(LIMIT_RETRY_DELAY)
        if close_order is None:
            console.print(f"🚨 Could not close {side.upper()} position after max retries.", style="bold red")
            return False
        return True
    except Exception as e:
        console.print(f"⚠️ close_position_at_target error: {e}", style="bold red")
        return False

# ==============================
# 4) Profit Check & Closure Function
# ==============================
def check_profit_and_close():
    """
    Checks each open position's unrealized profit. For a position with total contracts N, 
    it computes an effective threshold:
    
        effective_threshold = (base_profit + fee_cost) * N
        
    and then sets the target exit price as:
    
        For LONG: target_exit = entryPrice + (effective_threshold / N)
        For SHORT: target_exit = entryPrice - (effective_threshold / N)
    
    Closes positions via a limit order if the unrealized profit meets or exceeds the effective threshold.
    Returns (closed_long, closed_short) booleans.
    """
    closed_long = False
    closed_short = False
    
    # Define your base desired net profit and estimated fee cost per contract:
    base_profit_per_contract = 0.0369    # e.g., $0.01 net profit per contract
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
            console.print(f"[LONG] Entry: {entry_price:.6f}, Size: {size:.6f}, Unrealized PnL: ${unrealized:.6f}, Effective TP: ${effective_threshold:.6f}, Target Exit: {target_exit:.6f}", style="bold blue")
            if unrealized >= effective_threshold:
                console.print(f"✅ LONG profit threshold reached (Unrealized: ${unrealized:.6f} >= ${effective_threshold:.6f})", style="bold green")
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
            console.print(f"[SHORT] Entry: {entry_price:.6f}, Size: {size:.6f}, Unrealized PnL: ${unrealized:.6f}, Effective TP: ${effective_threshold:.6f}, Target Exit: {target_exit:.6f}", style="bold blue")
            if unrealized >= effective_threshold:
                console.print(f"✅ SHORT profit threshold reached (Unrealized: ${unrealized:.6f} >= ${effective_threshold:.6f})", style="bold green")
                if close_position_at_target(PAIR, "sell", target_exit, size):
                    closed_short = True
    return closed_long, closed_short

# ==============================
# 5) Hedge & DCA Manager Loop
# ==============================
prev_long_size = 0.0
prev_short_size = 0.0

def manage_hedged_positions():
    """
    Maintains exactly one LONG and one SHORT position.
    - At startup, opens one order per side.
    - In each loop, it logs the current entry, TP, and unrealized profit for each side.
    - If profit threshold is reached, it closes that side.
    - Then it DCA the opposite side by adding DCA_SIZE and reopens the closed side at INITIAL_TRADE_SIZE.
    """
    global prev_long_size, prev_short_size
    while True:
        try:
            closed_long, closed_short = check_profit_and_close()

            positions = exchange.fetch_positions([PAIR], params={'type': 'swap'})
            long_pos = next((p for p in positions if p.get('side') == 'long'), None)
            short_pos = next((p for p in positions if p.get('side') == 'short'), None)
            current_long = float(long_pos['contracts']) if long_pos else 0.0
            current_short = float(short_pos['contracts']) if short_pos else 0.0

            # Log current positions and unrealized PnL
            if long_pos:
                entry_long = float(long_pos.get('entryPrice', 0))
                unreal_long = float(long_pos.get('unrealizedPnl', 0))
                console.print(f"[HEDGE] LONG: Size = {current_long}, Entry = {entry_long:.6f}, Unrealized PnL = {unreal_long:.2f}", style="bold blue")
            else:
                console.print("[HEDGE] LONG: None", style="bold blue")
            if short_pos:
                entry_short = float(short_pos.get('entryPrice', 0))
                unreal_short = float(short_pos.get('unrealizedPnl', 0))
                console.print(f"[HEDGE] SHORT: Size = {current_short}, Entry = {entry_short:.6f}, Unrealized PnL = {unreal_short:.2f}", style="bold blue")
            else:
                console.print("[HEDGE] SHORT: None", style="bold blue")

            # Fresh start: if no positions exist, open one LONG and one SHORT.
            if current_long == 0 and current_short == 0 and prev_long_size == 0 and prev_short_size == 0:
                console.print("No positions found. Opening 1 LONG + 1 SHORT...", style="bold cyan")
                open_position(PAIR, "buy", INITIAL_TRADE_SIZE)
                open_position(PAIR, "sell", INITIAL_TRADE_SIZE)
            
            # If LONG just closed
            if current_long == 0 and prev_long_size > 0:
                console.print("🔻 LONG side closed (profit threshold reached).", style="bold yellow")
                if current_short > 0:
                    console.print(f"🆙 DCA on SHORT by +{DCA_SIZE}", style="bold cyan")
                    open_position(PAIR, "sell", DCA_SIZE)
                console.print(f"🔄 Reopening LONG with size={INITIAL_TRADE_SIZE}", style="bold magenta")
                open_position(PAIR, "buy", INITIAL_TRADE_SIZE)
            
            # If SHORT just closed
            if current_short == 0 and prev_short_size > 0:
                console.print("🔻 SHORT side closed (profit threshold reached).", style="bold yellow")
                if current_long > 0:
                    console.print(f"🆙 DCA on LONG by +{DCA_SIZE}", style="bold cyan")
                    open_position(PAIR, "buy", DCA_SIZE)
                console.print(f"🔄 Reopening SHORT with size={INITIAL_TRADE_SIZE}", style="bold magenta")
                open_position(PAIR, "sell", INITIAL_TRADE_SIZE)
            
            # If any side is missing, open it.
            if current_long == 0:
                console.print("No LONG found. Opening...", style="bold magenta")
                open_position(PAIR, "buy", INITIAL_TRADE_SIZE)
            if current_short == 0:
                console.print("No SHORT found. Opening...", style="bold magenta")
                open_position(PAIR, "sell", INITIAL_TRADE_SIZE)
            
            prev_long_size = current_long
            prev_short_size = current_short

        except Exception as e:
            console.print(f"⚠️ Hedge loop error: {e}", style="bold red")
            time.sleep(API_RETRY_DELAY)
        time.sleep(LOOP_DELAY)

# ==============================
# 6) Main Entry Point
# ==============================
def main():
    manage_hedged_positions()

if __name__ == '__main__':
    main()
