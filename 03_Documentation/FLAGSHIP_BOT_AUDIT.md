# Flagship Trading Bot Audit - newclaude.py

## Executive Summary

**Bot**: Gate Aggressive Hedge Engine v2.0 (`newclaude.py`)  
**Status**: Most runnable live-looking paper engine  
**Profitability**: NOT PROVEN - zero fills in paper mode  
**Conclusion**: Operationally alive but economically meaningless in current state

---

## Critical Findings

### 1. Paper Mode Fill Simulation - BROKEN

**Current Behavior**:
- Orders are logged with `PAPER` prefix
- Order status set to `OPEN`
- No fill simulation logic exists
- Zero fills recorded in metrics
- Zero fees calculated
- Zero realized PnL

**Evidence from Code**:
```python
if Cfg.PAPER:
    log.info("PAPER %s %s ×%d @ %.8g %s",
             side.value.upper(), fsm.symbol, size, price, tif)
    o.status = OrderStatus.OPEN
    o.updated_at = time.time()
```

**Problem**: Orders are marked as `OPEN` but never transition to `FILLED`. There is no simulation logic to:
- Determine if an order should fill
- Calculate fill price
- Apply fees
- Update position accounting
- Calculate PnL

**Impact**: Paper mode produces order activity without economic validation. This is IOC spam, not strategy testing.

---

### 2. Private WebSocket Desync Breaches - SPAM IN PAPER MODE

**Current Behavior**:
- Risk engine checks private WebSocket staleness
- In paper mode, private WS is skipped (no real orders)
- But risk check still triggers breaches
- Lines 1171-1175 show the check is skipped, but breaches still appear in logs

**Evidence from Code**:
```python
# Skip private WS check in paper mode (no private WS needed)
if not Cfg.PAPER:
    pvt_age = time.time() - self._last_pvt_ws
    if pvt_age > Cfg.PRIVATE_WS_STALE_SEC:
        self._breach(RiskEvent.WS_DESYNC, f"pvt_ws_age={pvt_age:.0f}s")
```

**Problem**: Risk engine should suppress WS_DESYNC checks entirely in paper mode since private WS is intentionally disabled.

**Impact**: False risk breaches in paper mode, confusing logs, unnecessary noise.

---

### 3. IOC Spam Without Economic Validation

**Current Behavior**:
- Bot emits IOC orders continuously
- No fill rate tracking in paper mode
- High cancel rate (62 cancels/min in logs)
- Zero fills despite high order rate

**Evidence from Logs**:
```
fills_per_min: 0
cancels_per_min: 62
total_realized_pnl: $0.00
total_fees: $0.00
total_gross_notional: $0.00
```

**Problem**: Strategy assumes fills will happen, but paper mode doesn't simulate this. The bot is generating order activity without validating if those orders would be profitable.

**Impact**: Cannot determine if the strategy has any edge. High order rate with zero fills suggests the strategy may not be viable.

---

### 4. No Session Summary or Viability Ranking

**Current Behavior**:
- No session-level PnL summary
- No symbol-level viability ranking
- No fill rate tracking
- No economic verdict after session

**Problem**: No way to assess if the session was successful or which symbols performed best.

**Impact**: Cannot iterate on strategy or symbol selection based on results.

---

## Architecture Assessment

### Strengths

1. **State Machine**: Well-designed FSM with guarded transitions
2. **Risk Engine**: Comprehensive 11-dimension risk system
3. **Accounting**: VWAP-accurate position tracking
4. **Partial Fills**: Correct accumulation logic
5. **Symbol Selection**: Multi-criteria filtering
6. **Telemetry**: Detailed metrics collection
7. **Reconciliation**: Live state restoration

### Weaknesses

1. **Paper Simulation**: Non-existent fill simulation
2. **Risk Logic**: Paper mode WS checks not fully suppressed
3. **Session Analysis**: No summary or ranking
4. **Economic Validation**: No fill probability model
5. **Slippage Model**: No price impact simulation
6. **Fee Simulation**: Paper mode doesn't apply fees

---

## Configuration Audit

### Current Settings

```python
TARGET_NOTIONAL  : float = 0.07   # $0.07 per order (very small)
MIN_NOTIONAL     : float = 0.005  # $0.005 minimum
LEVERAGE         : int   = 10
QUOTE_TTL_SEC    : float = 4.0    # Cancel after 4 seconds
REPRICE_LOOP_SEC : float = 0.15   # Reprice every 150ms
```

**Issues**:
- Target notional is extremely small ($0.07)
- High reprice frequency (every 150ms)
- Short quote TTL (4 seconds)
- This creates high order churn with small size

**Recommendation**: These settings may be contributing to IOC spam. Consider larger notional and longer TTL for meaningful testing.

---

## Symbol Selection Audit

### Current Symbols (Paper Mode Fallback)
- FIO_USDT
- NTRN_USDT
- SKL_USDT

### Selection Criteria
```python
MIN_SPREAD_VIABILITY : float = 1.5    # spread >= 1.5× round-trip fee
MIN_BOOK_DEPTH       : int   = 50     # contracts at best bid/ask
MIN_VOLUME_24H       : float = 50_000.0  # contracts/day
```

**Issues**:
- No verification if selected symbols actually meet criteria in paper mode
- Fallback symbols used when API unreachable
- No dynamic ranking or viability scoring

---

## Honest Assessment

### What This Bot Actually Does

**In Paper Mode**:
1. Scans for viable symbols (or uses fallback)
2. Connects to public WebSocket for order book data
3. Emits IOC orders at bid/ask prices
4. Logs orders as "PAPER"
5. Cancels orders after TTL
6. Reprices when market moves
7. Tracks risk breaches
8. Displays metrics dashboard

**What It Does NOT Do**:
1. Simulate fills
2. Calculate fees
3. Update positions
4. Calculate PnL
5. Validate economic edge
6. Provide session summary
7. Rank symbol viability

### Economic Verdict

**Current State**: NOT ECONOMICALLY MEANINGFUL

**Reasons**:
- Zero fills = zero economic activity
- High cancel rate = potential inefficiency
- No fee simulation = hidden costs
- No slippage model = unrealistic execution
- No PnL calculation = cannot assess profitability

**Conclusion**: The bot demonstrates operational capability (it runs, connects, emits orders) but does not demonstrate economic viability (no fills, no PnL, no edge validation).

---

## Comparison to Other Bots

### simple_gate_mm_3dollar.py
- **Status**: Broken (event loop issue)
- **Issue**: `asyncio.run() cannot be called from a running event loop`
- **Fix**: Use `asyncio.get_event_loop()` instead
- **Potential**: Simpler logic, easier to fix

### algo_trading_bot.py
- **Status**: Broken (TIF bug)
- **Issue**: Market orders sent with invalid `gtc` TIF
- **Error**: `TimeInForce gtc is not support for market order`
- **Fix**: Use `ioc` or remove TIF for market orders
- **Potential**: Different strategy (micro-cap trading)

### metamask_python_bridge.py
- **Status**: Running locally
- **Purpose**: Web3/UI experiment, not trading
- **Deployment**: Failed due to invalid API keys
- **Role**: Separate from main trading product

**Conclusion**: `newclaude.py` is indeed the most runnable, but that doesn't mean it's the most profitable. None of the bots have proven profitability.

---

## Required Fixes Priority

### P0 - Critical (Must Fix for Economic Meaning)

1. **Implement Paper Fill Simulation**
   - Fill probability model
   - Price execution model
   - Fee calculation
   - Position updates
   - PnL calculation

2. **Suppress Paper Mode WS Breaches**
   - Remove private WS checks in paper mode
   - Clean up risk logic for paper mode

3. **Add Session Summary**
   - Gross notional
   - Fees
   - Fill rate
   - Realized PnL
   - Unrealized PnL
   - Cancels/order ratio

### P1 - High (Important for Validation)

4. **Add Symbol Viability Ranking**
   - Per-symbol fill rate
   - Per-symbol PnL
   - Per-symbol spread quality
   - Ranking output

5. **Prevent IOC Spam**
   - Detect stale/unchanged book state
   - Suppress reprice when no meaningful change
   - Add minimum time between quotes

6. **Add Paper Profitability Verdict**
   - Session-level economic assessment
   - Pass/fail criteria
   - Clear output

### P2 - Medium (Quality Improvements)

7. **Fix Other Bots**
   - `simple_gate_mm_3dollar.py` event loop
   - `algo_trading_bot.py` TIF bug
   - Keep as separate experiments

8. **Improve Configuration**
   - Larger target notional for meaningful testing
   - Longer quote TTL to reduce churn
   - Configurable fill probability

---

## Security Note

**API Keys**: The API keys shown in logs should be treated as compromised and rotated immediately.

**Action Required**:
1. Revoke all exposed API keys
2. Generate new keys with appropriate scopes
3. Update environment variables
4. Never commit keys to version control

---

## Next Steps

1. **Implement paper fill simulation** (P0)
2. **Add session summary** (P0)
3. **Suppress paper WS breaches** (P0)
4. **Test with realistic fill rates** (P1)
5. **Add viability ranking** (P1)
6. **Generate economic verdict** (P1)
7. **Assess actual profitability** (after fixes)

---

## Current Valuation

**Before Fixes**: $500 - $1,000

**Reasoning**:
- Operationally runnable (connects, emits orders)
- Well-architected (FSM, risk engine, accounting)
- But economically meaningless (no fills, no PnL)
- Requires significant work to validate edge
- Not yet a sellable product

**After Fixes**: $2,000 - $4,000

**Reasoning**:
- Economic validation possible
- Realistic paper trading
- Session summaries and rankings
- Honest limitations documented
- Production-ready testing framework

**Final Valuation (Complete)**: $5,000 - $8,000

**Requirements**:
- All P0 fixes complete
- P1 fixes complete
- Proven paper profitability
- Comprehensive documentation
- Clean separation from experiments

---

## Conclusion

`newclaude.py` is the most operationally capable bot in the current portfolio, but it is NOT the most profitable. No bot has proven profitability.

The current paper mode implementation generates order activity without economic validation. This is IOC spam, not strategy testing.

To make this a credible flagship bot, we must:
1. Implement realistic paper fill simulation
2. Add session-level economic analysis
3. Suppress paper-mode-specific risk breaches
4. Provide honest profitability verdicts
5. Document limitations transparently

Only after these fixes can we assess whether this strategy has any economic edge.

---

**Audit Date**: April 19, 2026  
**Auditor**: Cascade AI Assistant  
**Status**: HONEST ASSESSMENT - NO PROFITABILITY CLAIMS
