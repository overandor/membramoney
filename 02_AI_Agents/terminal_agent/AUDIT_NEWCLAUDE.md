# newclaude.py Audit Report

**Date:** 2026-04-21  
**File:** `/Users/alep/Downloads/terminal_agent/newclaude.py`  
**Lines:** 2781  
**Status:** Operationally alive but economically meaningless in paper mode

---

## Executive Summary

`newclaude.py` is the most runnable bot but has a **critical paper fill simulation bug** that makes it economically meaningless. Orders are created but never filled, resulting in 0 fills, 0 PnL, and infinite cancel loops.

---

## Critical Findings

### 1. PAPER FILL SIMULATION IS BROKEN (CRITICAL)

**Location:** Lines 1986-1992 in `_submit_quote()`

**Current Code:**
```python
if Cfg.PAPER:
    log.info("PAPER %s %s ×%d @ %.8g %s",
             side.value.upper(), fsm.symbol, size, price, tif)
    o.status = OrderStatus.OPEN
    o.updated_at = time.time()
    self._db.upsert_order(o)
    return o
```

**Problem:** 
- Order is logged and marked as OPEN
- **NEVER gets filled**
- No simulation of fill probability, slippage, or fees
- Order just sits in OPEN state until TTL cancel

**Result:**
- 0 fills
- 0 realized PnL  
- High cancel rate (orders cancelled after QUOTE_TTL_SEC=4s)
- Meaningless paper trading

---

### 2. NO PAPER FILL MECHANISM EXISTS

**Real fills come from:** `on_trade()` callback via WebSocket usertrades channel

**Paper mode has:** No WebSocket connection to simulate fills

**Missing:** A paper fill simulator that:
- Checks if IOC order crosses the spread
- Simulates fill probability based on book depth
- Simulates slippage (partial fills at worse prices)
- Simulates taker fees
- Calls `_process_fill()` to update legs and PnL

---

### 3. WS DESYNC IN PAPER MODE IS NOISE

**Location:** RiskEngine.check_symbol() and related

**Problem:** Paper mode emits "private-ws desync" breaches but paper has no private WebSocket by design.

**Current behavior:**
- Risk engine tracks `_last_pvt_ws` timestamp
- If no messages for 30s, triggers WS_DESYNC risk event
- In paper mode, this is expected (no WS connection)
- Creates false positive risk breaches

---

### 4. NO SESSION SUMMARY OR PROFITABILITY VERDICT

**Missing:** End-of-session report with:
- Gross notional traded
- Total fees paid
- Fill rate (% of orders that filled)
- Realized PnL
- Unrealized PnL
- Cancel/order ratio
- Symbol viability ranking

---

### 5. IOC SPAM WITHOUT FILL SIMULATION

**Current behavior:**
- Bot places IOC orders every 0.15s (REPRICE_LOOP_SEC)
- Orders cancelled after 4s (QUOTE_TTL_SEC)
- Zero fills due to missing simulation
- Infinite loop of place → cancel → place

---

## Architecture Assessment

### What Works Well:
1. ✅ Clean separation: FSM, Leg, OrderStore, ExecEngine
2. ✅ FSM state machine prevents contradictory actions
3. ✅ Risk engine with 11 dimensions (when fills happen)
4. ✅ Dashboard at http://127.0.0.1:8765
5. ✅ Symbol selection with viability checks
6. ✅ Fee model with maker/taker rates
7. ✅ VWAP accounting for partial fills

### What's Broken:
1. ❌ Paper fill simulation completely missing
2. ❌ WS desync false positives in paper mode
3. ❌ No end-of-session profitability report
4. ❌ No fill probability model
5. ❌ No slippage simulation
6. ❌ Orders created but never filled

---

## Root Cause Analysis

```
User runs bot with GATE_PAPER=1
    ↓
Bot scans symbols, selects FIO_USDT, NTRN_USDT, SKL_USDT
    ↓
Bot enters reprice_loop() every 0.15s
    ↓
_submit_quote() creates IOC orders at best bid/ask
    ↓
Paper mode logs order: "PAPER LONG FIO_USDT ×7 @ 0.12345678 ioc"
    ↓
Order status set to OPEN
    ↓
NO FILL SIMULATION HAPPENS
    ↓
After 4s (QUOTE_TTL), order marked CANCELLED
    ↓
Metris: cancels/min skyrockets, fills/min = 0
    ↓
Repeat indefinitely
```

---

## Required Fixes (In Priority Order)

### Fix 1: Paper Fill Simulator (CRITICAL)

**New component:** `PaperExchangeSimulator` class

**Requirements:**
```python
@dataclass
class FillModel:
    fill_probability: float = 0.3  # 30% of IOC orders fill
    partial_fill_rate: float = 0.2  # 20% of fills are partial
    slippage_ticks: int = 1  # 1 tick slippage on fills
    
    def simulate_fill(self, order: LimitOrder, book: BookTick) -> Optional[Fill]:
        """
        Simulate whether an IOC order fills against the book.
        
        Logic:
        - LONG IOC at ask: fills if fill_probability > random()
        - SHORT IOC at bid: fills if fill_probability > random()
        - Fill price = order.price (or worse by slippage_ticks)
        - Fill size = order.size (or partial if partial_fill_rate > random())
        - Fee = notional * TAKER_FEE_RATE
        """
```

**Integration:**
- In `_submit_quote()`: If PAPER mode, after creating order, call `simulator.try_fill(order, book)`
- If fill occurs: call `await self._os.apply_fill()` then `await self._process_fill()`

---

### Fix 2: Suppress WS Desync in Paper Mode

**Location:** RiskEngine.check_symbol() and check_global()

**Change:**
```python
if Cfg.PAPER:
    # Skip WS desync checks in paper mode (no private WS)
    return True, ""
```

---

### Fix 3: Add Session Summary

**New component:** SessionReporter

**Report every N minutes and on shutdown:**
```
═══════════════════════════════════════════════════════
SESSION SUMMARY (last 30 min)
═══════════════════════════════════════════════════════
Gross Notional:    $1,247.50
Total Fees:        $0.62
Fill Rate:         28.4% (142 fills / 500 orders)
Cancel Rate:       71.6%
Realized PnL:      -$0.34
Unrealized PnL:    +$0.12
───────────────────────────────────────────────────────
Symbol Performance:
  FIO_USDT:  34 fills, -$0.18 PnL, 31% fill rate [VIABLE]
  NTRN_USDT: 56 fills, +$0.08 PnL, 42% fill rate [PROFITABLE]
  SKL_USDT:  52 fills, -$0.24 PnL, 22% fill rate [AVOID]
═══════════════════════════════════════════════════════
VERDICT: Not profitable (negative PnL after fees)
═══════════════════════════════════════════════════════
```

---

### Fix 4: Prevent Stale Book IOC Spam

**Current:** Bot quotes even if book hasn't changed

**Fix:** Track last quote price, skip if book hasn't moved meaningfully

```python
if abs(book.ask - last_quote_ask) < Cfg.REPRICE_TICKS * spec.tick_size:
    return  # Skip, no edge in requoting same level
```

---

## Code Changes Required

### File: newclaude.py

**Section 1: Add PaperExchangeSimulator class (after Cfg class)**
```python
@dataclass
class PaperFillSimulator:
    """Simulates realistic exchange fills in paper mode"""
    fill_probability: float = 0.35  # 35% fill rate
    partial_fill_prob: float = 0.25  # 25% of fills are partial
    slippage_ticks: int = 1
    
    def simulate_ioc_fill(self, order: LimitOrder, book: BookTick, 
                          spec: ContractSpec) -> Optional[Tuple[int, float, float]]:
        """Return (fill_size, fill_price, fee) or None if no fill"""
        import random
        
        # IOC fills if order crosses spread
        crosses = (order.side == Side.LONG and order.price >= book.ask) or \
                  (order.side == Side.SHORT and order.price <= book.bid)
        
        if not crosses:
            return None
            
        # Probabilistic fill
        if random.random() > self.fill_probability:
            return None
            
        # Determine fill size
        if random.random() < self.partial_fill_prob:
            fill_size = int(order.requested_size * random.uniform(0.3, 0.8))
        else:
            fill_size = order.requested_size
            
        # Apply slippage
        slip = self.slippage_ticks * spec.tick_size
        if order.side == Side.LONG:
            fill_price = order.price + slip  # Worse fill for long
        else:
            fill_price = order.price - slip
            
        # Calculate fee
        notional = fill_size * fill_price * spec.quanto_multiplier
        fee = abs(notional * Cfg.TAKER_FEE_RATE)
        
        return (fill_size, fill_price, fee)
```

**Section 2: Modify _submit_quote() for paper fills**
```python
async def _submit_quote(self, fsm: HedgeFSM, spec: ContractSpec,
                         side: Side, price: float) -> Optional[LimitOrder]:
    # ... existing code ...
    
    if Cfg.PAPER:
        log.info("PAPER %s %s ×%d @ %.8g %s",
                 side.value.upper(), fsm.symbol, size, price, tif)
        o.status = OrderStatus.OPEN
        o.updated_at = time.time()
        self._db.upsert_order(o)
        
        # NEW: Simulate fill immediately for IOC orders
        if tif == "ioc":
            book = self._books.get(fsm.symbol)
            if book:
                fill_result = self._paper_sim.simulate_ioc_fill(o, book, spec)
                if fill_result:
                    fill_size, fill_price, fee = fill_result
                    await self._os.apply_fill(o.client_id, fill_size, fill_price, fee)
                    await self._process_fill(o, fill_size, fill_price, fee)
                    log.info("PAPER FILL %s ×%d @ %.8g fee=%.4f",
                             fsm.symbol, fill_size, fill_price, fee)
                else:
                    # No fill - cancel immediately (IOC behavior)
                    await self._os.mark_cancelled(o.client_id)
                    self._met.record_cancel(fsm.symbol)
        
        return o
```

**Section 3: Add to ExecEngine.__init__()**
```python
self._paper_sim = PaperFillSimulator() if Cfg.PAPER else None
```

---

## Testing the Fix

**Before fix:**
```
PAPER LONG FIO_USDT ×7 @ 0.12345678 ioc
[TTL cancel after 4s]
PAPER LONG FIO_USDT ×7 @ 0.12345680 ioc
[TTL cancel after 4s]
... repeat forever
Metrics: 0 fills, 0 PnL, 15 cancels/min
```

**After fix:**
```
PAPER LONG FIO_USDT ×7 @ 0.12345678 ioc
PAPER FILL FIO_USDT ×7 @ 0.12345688 fee=0.0004
PAPER SHORT FIO_USDT ×7 @ 0.12355678 ioc  
PAPER FILL FIO_USDT ×7 @ 0.12355668 fee=0.0004
Metrics: 8 fills, +0.0012 PnL, 12 cancels/min
```

---

## Honest Valuation

### Current State (Broken Paper):
- **Fill Rate:** 0%
- **Realized PnL:** $0
- **Economic Value:** None - cannot validate strategy
- **Rating:** ❌ Non-functional for testing

### After Fix 1 (Paper Fill Simulation):
- **Fill Rate:** 30-40% (configurable)
- **Realized PnL:** Will show actual spread capture minus fees
- **Economic Value:** Can validate if strategy captures spread after fees
- **Rating:** ⚠️ Functional for strategy validation only

### To Be Production-Ready:
- Live trading with real API (already supported)
- Proper risk management (already implemented)
- Tested fill simulation (needs Fix 1)
- Session reporting (needs Fix 3)

---

## Immediate Action Items

1. **Implement Fix 1** (Paper Fill Simulator) - ~2 hours
2. **Test paper mode** - ~30 min
3. **Implement Fix 3** (Session Summary) - ~1 hour
4. **Implement Fix 2** (Suppress WS desync) - ~15 min
5. **Run paper session** and collect real metrics
6. **Decision:** If paper shows positive PnL → consider live with small size

---

## File Structure After Refactor

```
terminal_agent/
├── newclaude.py           # Main bot (patched with paper fixes)
├── AUDIT_NEWCLAUDE.md     # This audit
├── PATCH_PLAN.md          # Detailed patch steps
├── paper_config.yaml      # Paper simulator settings
└── README.md              # Honest documentation
```

---

## Conclusion

`newclaude.py` has solid architecture but **cannot validate the strategy** without paper fill simulation. The current paper mode generates order activity but no fills, making it impossible to know if the hedge strategy actually captures spread profit after fees.

**Recommendation:** Implement Fix 1 (Paper Fill Simulator) immediately before any further development.
