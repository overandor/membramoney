# Paper Fill Simulation Patch Plan

## Objective

Implement realistic paper fill simulation for `newclaude.py` to enable economic validation of the aggressive hedging strategy.

## Current Problem

Paper mode logs orders but never simulates fills:
- Orders marked as `OPEN` but never transition to `FILLED`
- Zero fees calculated
- Zero PnL calculated
- No position updates
- Cannot assess economic edge

## Solution Architecture

### 1. Fill Probability Model

**Concept**: Determine if an order should fill based on market conditions and execution mode.

**Factors**:
- Order side (LONG/SHORT)
- Order price relative to bid/ask
- Execution mode (MAKER_FIRST, AGGRESSIVE_LIMIT, TAKER_FALLBACK)
- Book depth at execution price
- Spread size
- Fill probability configuration

**Implementation**:
```python
class PaperFillModel:
    def __init__(self):
        self.fill_probability = {
            ExecMode.MAKER_FIRST: 0.3,      # 30% fill rate as maker
            ExecMode.AGGRESSIVE_LIMIT: 0.7, # 70% fill rate as taker at touch
            ExecMode.TAKER_FALLBACK: 0.85   # 85% fill rate with wider touch
        }
        self.slippage_bps = {
            ExecMode.MAKER_FIRST: 0,        # No slippage as maker
            ExecMode.AGGRESSIVE_LIMIT: 1,   # 1 bps slippage at touch
            ExecMode.TAKER_FALLBACK: 2      # 2 bps slippage wider
        }
    
    def should_fill(self, order: LimitOrder, book: BookTick) -> bool:
        """Determine if order should fill based on execution mode and market state."""
        prob = self.fill_probability.get(order.exec_mode, 0.5)
        
        # Adjust probability based on price placement
        if order.exec_mode == ExecMode.MAKER_FIRST:
            # Maker orders: higher probability if placed inside spread
            if order.side == Side.LONG and order.price < book.ask:
                prob *= 1.2  # Better chance if inside spread
            elif order.side == Side.SHORT and order.price > book.bid:
                prob *= 1.2
        elif order.exec_mode == ExecMode.AGGRESSIVE_LIMIT:
            # Aggressive limit: always fill if at touch
            if order.side == Side.LONG and order.price >= book.ask:
                prob = 1.0
            elif order.side == Side.SHORT and order.price <= book.bid:
                prob = 1.0
        
        # Random fill decision
        return random.random() < prob
    
    def get_fill_price(self, order: LimitOrder, book: BookTick) -> float:
        """Calculate realistic fill price with slippage."""
        base_price = order.price
        
        if order.exec_mode == ExecMode.MAKER_FIRST:
            # Maker fills at order price (no slippage)
            return base_price
        else:
            # Taker fills with slippage
            slippage = self.slippage_bps.get(order.exec_mode, 1) / 10000
            if order.side == Side.LONG:
                return base_price * (1 + slippage)  # Pay more
            else:
                return base_price * (1 - slippage)  # Receive less
```

### 2. Fee Simulation

**Concept**: Apply realistic fees based on execution mode.

**Implementation**:
```python
def calculate_fee(order: LimitOrder, fill_price: float, fill_size: int) -> float:
    """Calculate fee based on execution mode."""
    notional = fill_price * fill_size
    
    if order.exec_mode == ExecMode.MAKER_FIRST:
        # Maker gets rebate
        fee_rate = Cfg.MAKER_FEE_RATE  # -0.00015 (rebate)
    else:
        # Taker pays fee
        fee_rate = Cfg.TAKER_FEE_RATE  # 0.0005
    
    return abs(notional * fee_rate)
```

### 3. Position Update Logic

**Concept**: Update position accounting when paper fills occur.

**Implementation**:
```python
def simulate_paper_fill(order: LimitOrder, book: BookTick, 
                       fill_model: PaperFillModel) -> Optional[Dict]:
    """Simulate a paper fill and return fill details."""
    if not fill_model.should_fill(order, book):
        return None
    
    # Calculate fill details
    fill_price = fill_model.get_fill_price(order, book)
    fill_size = order.requested_size  # Full fill for IOC
    fee = calculate_fee(order, fill_price, fill_size)
    
    return {
        'size': fill_size,
        'price': fill_price,
        'fee': fee,
        'timestamp': time.time()
    }
```

### 4. Integration with Order Lifecycle

**Changes to `_emit_order()` method**:

```python
async def _emit_order(self, fsm: "HedgeFSM", side: Side, size: int,
                     price: float, tif: str, text: str = "") -> str:
    """Emit order (real or paper)."""
    client_id = f"{fsm.symbol}_{side.value}_{uuid.uuid4().hex[:8]}"
    
    o = LimitOrder(
        client_id=client_id,
        exchange_id="",  # No exchange ID in paper mode
        symbol=fsm.symbol,
        side=side,
        requested_size=size,
        price=price,
        tif=tif,
        exec_mode=Cfg.DEFAULT_EXEC_MODE,
    )
    
    await self._os.register(o)
    
    if Cfg.PAPER:
        log.info("PAPER %s %s ×%d @ %.8g %s",
                 side.value.upper(), fsm.symbol, size, price, tif)
        
        # SIMULATE FILL
        book = self._books.get(fsm.symbol)
        if book:
            fill_details = simulate_paper_fill(o, book, self._fill_model)
            
            if fill_details:
                # Record the fill
                o.record_fill(
                    fill_details['size'],
                    fill_details['price'],
                    fill_details['fee']
                )
                
                # Update position
                if side == Side.LONG:
                    fsm.long_leg.open_fill(
                        fill_details['size'],
                        fill_details['price'],
                        fill_details['fee']
                    )
                else:
                    fsm.short_leg.open_fill(
                        fill_details['size'],
                        fill_details['price'],
                        fill_details['fee']
                    )
                
                log.info("PAPER FILL %s %s ×%d @ %.8g fee=%.8g",
                         side.value.upper(), fsm.symbol,
                         fill_details['size'], fill_details['price'],
                         fill_details['fee'])
            else:
                # No fill - mark as cancelled
                o.status = OrderStatus.CANCELLED
                log.info("PAPER NOFILL %s %s ×%d @ %.8g",
                         side.value.upper(), fsm.symbol, size, price)
    else:
        # Real order placement
        # ... existing real order logic ...
```

### 5. Session Summary Implementation

**New class**:
```python
@dataclass
class SessionSummary:
    """Session-level economic summary."""
    start_time: float
    end_time: float = 0.0
    total_orders: int = 0
    total_fills: int = 0
    fill_rate: float = 0.0
    gross_notional: float = 0.0
    total_fees: float = 0.0
    realized_pnl: float = 0.0
    unrealized_pnl: float = 0.0
    total_cancels: int = 0
    cancels_per_order: float = 0.0
    symbol_performance: Dict[str, Dict] = field(default_factory=dict)
    
    def calculate_fill_rate(self) -> float:
        if self.total_orders == 0:
            return 0.0
        return (self.total_fills / self.total_orders) * 100.0
    
    def get_verdict(self) -> str:
        """Generate paper profitability verdict."""
        if self.fill_rate < 10:
            return "FAIL: Fill rate too low (<10%)"
        elif self.realized_pnl <= 0:
            return "FAIL: No realized profit"
        elif (self.realized_pnl - self.total_fees) <= 0:
            return "FAIL: Fees exceed gross profit"
        else:
            return f"PASS: Net profit ${(self.realized_pnl - self.total_fees):.4f}"
```

### 6. Symbol Viability Ranking

**New method**:
```python
def rank_symbol_viability(self) -> List[Tuple[str, float, str]]:
    """Rank symbols by economic performance."""
    rankings = []
    
    for symbol, perf in self.session_summary.symbol_performance.items():
        score = (
            perf['fill_rate'] * 0.4 +          # 40% weight on fill rate
            (perf['net_pnl'] * 100) * 0.3 +    # 30% weight on profit
            (perf['spread_quality'] * 10) * 0.2 + # 20% weight on spread
            (perf['order_efficiency'] * 10) * 0.1 # 10% weight on efficiency
        )
        
        verdict = "VIABLE" if score > 50 else "NOT VIABLE"
        rankings.append((symbol, score, verdict))
    
    return sorted(rankings, key=lambda x: x[1], reverse=True)
```

### 7. IOC Spam Prevention

**New logic**:
```python
def _should_quote(self, fsm: "HedgeFSM", book: BookTick) -> bool:
    """Determine if we should emit a quote (prevent IOC spam)."""
    
    # Check if book is stale
    if book.is_stale():
        return False
    
    # Check if book state is unchanged
    last_book = self._last_book_state.get(fsm.symbol)
    if last_book:
        bid_change = abs(book.bid - last_book['bid'])
        ask_change = abs(book.ask - last_book['ask'])
        
        # Only quote if meaningful price movement
        if bid_change < fsm.spec.tick_size and ask_change < fsm.spec.tick_size:
            return False
    
    # Check minimum time between quotes
    time_since_last = time.time() - self._last_quote_time.get(fsm.symbol, 0)
    if time_since_last < Cfg.MIN_QUOTE_INTERVAL_SEC:
        return False
    
    return True
```

### 8. Risk Logic Fix for Paper Mode

**Change to risk engine**:
```python
def check_private_ws_stale(self) -> bool:
    """Check private WebSocket staleness (skip in paper mode)."""
    if Cfg.PAPER:
        return False  # Skip check entirely in paper mode
    
    pvt_age = time.time() - self._last_pvt_ws
    if pvt_age > Cfg.PRIVATE_WS_STALE_SEC:
        self._breach(RiskEvent.WS_DESYNC, f"pvt_ws_age={pvt_age:.0f}s")
        return True
    return False
```

## Configuration Additions

```python
class Cfg:
    # ... existing config ...
    
    # Paper fill simulation
    PAPER_FILL_PROBABILITY: float = 0.5  # Base fill probability
    PAPER_SLIPPAGE_BPS: int = 1          # Slippage in basis points
    PAPER_FILL_DELAY_MS: int = 50        # Simulated fill delay
    
    # IOC spam prevention
    MIN_QUOTE_INTERVAL_SEC: float = 0.5  # Minimum time between quotes
    MIN_PRICE_CHANGE_TICKS: int = 1      # Minimum price movement to requote
    
    # Session analysis
    SESSION_SUMMARY_INTERVAL_SEC: float = 300  # Print summary every 5 minutes
```

## Implementation Order

### Phase 1: Core Fill Simulation (P0)
1. Add `PaperFillModel` class
2. Add `calculate_fee()` function
3. Add `simulate_paper_fill()` function
4. Integrate into `_emit_order()`
5. Test with different fill probabilities

### Phase 2: Position Accounting (P0)
6. Update position tracking on paper fills
7. Calculate PnL on paper fills
8. Update metrics with paper fill data
9. Verify accounting accuracy

### Phase 3: Session Summary (P0)
10. Add `SessionSummary` class
11. Track session-level metrics
12. Generate session verdict
13. Display summary on shutdown

### Phase 4: Risk Logic Fix (P0)
14. Suppress private WS checks in paper mode
15. Clean up risk breach logic
16. Test paper mode without breaches

### Phase 5: Viability Ranking (P1)
17. Track per-symbol performance
18. Implement ranking algorithm
19. Display rankings in dashboard
20. Add ranking to session summary

### Phase 6: IOC Spam Prevention (P1)
21. Add book change detection
22. Add minimum quote interval
23. Implement stale book suppression
24. Test with reduced order rate

## Testing Plan

### Unit Tests
1. Test fill probability model
2. Test fee calculation
3. Test position updates
4. Test session summary calculations
5. Test ranking algorithm

### Integration Tests
6. Test paper mode with fills
7. Test session summary generation
8. Test risk logic in paper mode
9. Test IOC spam prevention

### Validation Tests
10. Run 1-hour paper session
11. Verify fill rate > 0
12. Verify fees calculated
13. Verify PnL calculated
14. Verify session summary accurate
15. Verify rankings meaningful

## Success Criteria

### Minimum Viable
- Paper mode generates fills (not just orders)
- Fees are calculated and applied
- PnL is calculated correctly
- Session summary shows economic data

### Production Ready
- Fill rate configurable and realistic
- Slippage model implemented
- Symbol viability ranking working
- IOC spam prevented
- Clear profitability verdict generated
- Risk logic clean in paper mode

## Expected Outcomes

### Before Patch
- 0 fills/min
- 0 fees
- 0 PnL
- 62 cancels/min
- No economic meaning

### After Patch
- 5-20 fills/min (configurable)
- Fees calculated
- PnL calculated
- Reduced cancels/min
- Economic validation possible
- Session summary with verdict
- Symbol viability ranking

## Rollout Plan

1. **Develop Phase 1-2** (Core fill simulation) - 2 hours
2. **Test in isolated environment** - 1 hour
3. **Develop Phase 3-4** (Session summary + risk fix) - 1 hour
4. **Test full paper session** - 1 hour
5. **Develop Phase 5-6** (Ranking + spam prevention) - 1 hour
6. **Extended testing** - 2 hours
7. **Documentation** - 1 hour

**Total Estimated Time**: 9 hours

## Backward Compatibility

- Paper mode behavior will change significantly (fills will occur)
- Existing paper logs will not be comparable
- Configuration may need adjustment
- Risk breach behavior will change

**Migration**: Clear existing paper database and start fresh after patch.

---

**Patch Status**: DESIGN COMPLETE  
**Implementation Status**: NOT STARTED  
**Priority**: P0 (CRITICAL)  
**Estimated Effort**: 9 hours
