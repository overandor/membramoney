# Diagnostic Guide - Why Orders Aren't Filling

## Problem: Positions Empty on Gate.io

Your bot is running but not filling orders. This is typically caused by:

1. **postOnly orders never fill** - Waiting for someone to cross the spread
2. **Filters too strict** - Edge score, momentum, spread, volume requirements
3. **Order size too small** - Below minimum contract size
4. **Wrong wallet** - Trading in spot instead of futures
5. **Silent failures** - Orders failing without clear error messages

## Diagnostic Tools Added

Two new configuration flags in `copythatpay.py`:

### 1. FORCE_TAKER_MODE (Line 126)
```python
FORCE_TAKER_MODE = False  # If True, disables postOnly to force fills (TESTING ONLY)
```

**Purpose:** Disables `postOnly` flag on orders, allowing them to cross the spread and fill immediately.

**When to use:** To test if the system can place and fill orders when not waiting for passive fills.

**Risk:** Will pay taker fees (~0.075%) instead of maker fees, but guarantees fills.

### 2. DIAGNOSTIC_MODE (Line 127)
```python
DIAGNOSTIC_MODE = False  # If True, disables all filters to test order placement
```

**Purpose:** Disables ALL trading filters except safety checks:
- Skips volatility checks
- Skips spread requirements
- Skips volume requirements  
- Skips edge score requirements
- Forces both long and short quoting

**When to use:** To test if the system can place orders at all, regardless of market conditions.

**Risk:** Will trade in ANY market condition - use only for brief testing with small sizes.

## Enhanced Logging

### Order Placement Logging
Now shows:
- Order ID for tracking
- Exact error type and message on failure
- Symbol, side, and contract count on failure
- Invalid price failures with bid/ask values

### Filter Logging
Already shows why symbols are being skipped:
- `[SYMBOL] DEAD MARKET (momentum=X) → skipping`
- `[SYMBOL] TOO VOLATILE (momentum=X) → skipping`
- `[SYMBOL] NO EDGE (score=X): reasons → skipping`

## How to Diagnose

### Step 1: Check if Orders Are Being Placed

Run the bot and watch for:
- `QUOTE BUY/SYMBOL` messages = orders are being placed
- `ORDER FAILED` messages = orders are failing
- No quote messages = filters are blocking orders

### Step 2: Test with FORCE_TAKER_MODE

1. Set `FORCE_TAKER_MODE = True` in `copythatpay.py` (line 126)
2. Run the bot
3. Watch for `TAKER (forced) QUOTE` messages
4. Check if positions appear

If positions appear: Your system works, but postOnly orders aren't being filled.
If no positions: Orders are failing for another reason.

### Step 3: Test with DIAGNOSTIC_MODE

1. Set `DIAGNOSTIC_MODE = True` in `copythatpay.py` (line 127)
2. Run the bot
3. Watch for `[DIAGNOSTIC] SYMBOL: Skipping all filters` messages
4. Check if orders are placed

If orders appear: Your filters are too strict.
If no orders: There's a deeper issue (API, wallet, size).

### Step 4: Check Open Orders

Add this to test if orders are sitting unfilled:

```python
# In the main loop
orders = await self.exchange.fetch_open_orders()
console.print(f"Open orders: {len(orders)}")
for order in orders:
    console.print(f"  {order['symbol']}: {order['side']} {order['amount']} @ {order['price']}")
```

### Step 5: Verify Wallet

On Gate.io:
1. Go to Futures trading
2. Check USDT balance in futures account
3. Verify it's not in spot wallet

The bot uses `'type': 'swap'` which requires futures wallet.

## Common Issues

### Issue: "No eligible symbols"
**Cause:** No symbols passed the initial filter (likely volume or spread).
**Fix:** Use DIAGNOSTIC_MODE to bypass, or lower MIN_REAL_SPREAD/volume requirements.

### Issue: Orders placed but never fill
**Cause:** postOnly waiting for counterparty, low liquidity symbols.
**Fix:** Use FORCE_TAKER_MODE or trade higher volume symbols.

### Issue: "ORDER FAILED: Invalid price"
**Cause:** Order book empty or bid/ask = 0.
**Fix:** Check symbol liquidity, try different symbols.

### Issue: "ORDER FAILED: Insufficient balance"
**Cause:** Trading in wrong wallet (spot vs futures).
**Fix:** Transfer USDT to futures wallet on Gate.io.

## Recommended Testing Sequence

1. **Run normally** - Observe filter logging
2. **FORCE_TAKER_MODE** - Test if fills work when crossing spread
3. **DIAGNOSTIC_MODE** - Test if orders can be placed at all
4. **Check open orders** - See if orders are sitting unfilled
5. **Verify wallet** - Confirm funds in futures account

## Production Settings

After testing, revert to:
```python
FORCE_TAKER_MODE = False  # Use maker orders for lower fees
DIAGNOSTIC_MODE = False   # Enable all filters for safety
```

Consider tuning filters if they're too strict:
- Lower `MIN_REAL_SPREAD` from 0.004 to 0.002
- Lower volume requirement from $10k to $5k
- Lower edge score threshold from 2 to 1.5
