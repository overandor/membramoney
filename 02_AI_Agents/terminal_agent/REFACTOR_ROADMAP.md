# Refactor Roadmap: newclaude.py → Flagship Trading Bot

**Goal:** Transform from experimental script to production-minded, sellable trading framework

---

## Current State Assessment

### What's Working (Keep)
- ✅ Clean architecture: FSM, Leg, OrderStore separation
- ✅ 11-dimension risk engine
- ✅ Dashboard with real-time metrics
- ✅ Symbol selection with viability filters
- ✅ VWAP accounting for partial fills
- ✅ Fee model with maker/taker rates
- ✅ Database persistence (SQLite)
- ✅ Reconciler for crash recovery

### What's Broken (Fix)
- ❌ Paper fill simulation completely missing
- ❌ WS desync false positives in paper mode
- ❌ No session profitability reporting
- ❌ No end-to-end validation capability

### What's Missing (Add)
- ⚠️ Live trading verification
- ⚠️ Risk-adjusted performance metrics
- ⚠️ Configuration management
- ⚠️ Documentation for users
- ⚠️ Honest marketing materials

---

## Phase 1: Foundation (Week 1)

### Objective: Make paper mode economically meaningful

**Tasks:**
1. **Implement PaperFillSimulator** (Patch Plan Fix 1)
   - Add probabilistic fill model
   - Simulate slippage and fees
   - Make fills realistic, not guaranteed

2. **Suppress Paper Mode Noise** (Patch Plan Fix 2)
   - Skip WS desync checks when GATE_PAPER=1
   - Reduce log spam in paper mode

3. **Add Session Reporting** (Patch Plan Fix 3)
   - Real-time PnL tracking
   - Symbol viability ranking
   - End-of-session verdict

**Deliverable:** Functional paper trading with realistic fills

**Success Metrics:**
- Fill rate: 30-40% (configurable)
- PnL tracking: accurate to model
- Cancel rate: <70%
- Verdict: "Can validate strategy before live"

---

## Phase 2: Validation (Week 2)

### Objective: Prove strategy works in paper

**Tasks:**
1. **Paper Trading Campaign**
   - Run for 5 days minimum
   - Trade 3-5 symbols
   - Target: $0.50-1.00 notional per leg
   - Collect metrics

2. **Analyze Results**
   - Fill rate by symbol
   - PnL after fees
   - Win rate (hedge repairs vs successful opens)
   - Risk event frequency

3. **Tune Parameters**
   - Adjust fill_probability based on real Gate.io behavior
   - Optimize symbol selection criteria
   - Refine risk thresholds

**Deliverable:** Validated paper strategy with 30+ day backtest equivalent

**Success Metrics:**
- Net PnL after fees: positive
- Max drawdown: <$2.00 (configured limit)
- Fill rate: stable 35%+
- Symbols: 2-3 viable identified

---

## Phase 3: Live Transition (Week 3)

### Objective: Move from paper to live with safety

**Tasks:**
1. **Micro-Live Testing**
   - Start with $0.01 notional (smallest possible)
   - Single symbol only
   - 1-hour sessions max
   - Immediate halt if paper vs live diverge >50%

2. **Compare Paper vs Live**
   - Fill rate deviation
   - Slippage difference
   - Latency impact on PnL

3. **Gradual Scale**
   - $0.01 → $0.05 → $0.10 → $0.50 → $1.00 notional
   - Only scale if live PnL tracks paper

**Deliverable:** Live trading bot with verified edge

**Success Metrics:**
- Live PnL within 20% of paper prediction
- No risk breaches in first 10 live hours
- Consistent fills on viable symbols

---

## Phase 4: Production Hardening (Week 4)

### Objective: Make it production-ready

**Tasks:**
1. **Configuration System**
   - Move from hardcoded Cfg class to config file
   - Environment-specific configs (paper/live)
   - Hot-reload for non-critical params

2. **Observability**
   - Structured logging (JSON)
   - Metrics export (Prometheus/InfluxDB)
   - Alerting (Discord/Slack webhook on risk events)

3. **Documentation**
   - README.md with setup instructions
   - ARCHITECTURE.md explaining components
   - OPERATIONS.md for running live
   - LIMITATIONS.md with honest caveats

4. **Safety Enhancements**
   - Circuit breaker on consecutive losses
   - Auto-flatten on API errors
   - Position size caps per symbol

**Deliverable:** Production-ready trading framework

---

## Phase 5: Productization (Week 5-6)

### Objective: Make it sellable/distributable

**Tasks:**
1. **Rebrand & Package**
   - Rename from "newclaude.py" to "gate-hedge-engine"
   - Clean repo structure
   - requirements.txt with versions pinned
   - Docker container for easy deployment

2. **Honest Marketing**
   - README: "Aggressive hedge strategy for Gate.io futures"
   - Clear statement: "Captures spread minus fees, not guaranteed profit"
   - Performance disclaimer: "Past paper results ≠ future live results"
   - Risk disclosure: "Can lose up to configured daily limit"

3. **Pricing Model**
   - Open source core (GitHub)
   - Paid add-ons: hosted version, advanced analytics
   - Support tiers: community/free, professional/paid

4. **Community Building**
   - Discord server for users
   - Weekly performance reports (anonymized)
   - Strategy improvement proposals

**Deliverable:** Sellable product with honest positioning

---

## Repository Structure (Target)

```
gate-hedge-engine/
├── README.md                 # Product overview
├── ARCHITECTURE.md          # Technical deep dive
├── OPERATIONS.md            # Runbook
├── LIMITATIONS.md           # Honest caveats
├── CHANGELOG.md             # Version history
├── LICENSE                  # MIT or commercial
├── requirements.txt         # Pinned deps
├── Dockerfile               # Container
├── docker-compose.yml       # Easy start
├── config/
│   ├── paper.yaml          # Paper mode config
│   └── live.yaml           # Live trading config
├── src/
│   ├── __init__.py
│   ├── main.py             # Entry point
│   ├── config.py           # Configuration mgmt
│   ├── exchange/
│   │   ├── gate_rest.py    # REST API client
│   │   ├── gate_ws.py      # WebSocket client
│   │   └── paper_sim.py    # Paper fill simulator
│   ├── engine/
│   │   ├── fsm.py          # Hedge state machine
│   │   ├── leg.py          # Position accounting
│   │   ├── order_store.py  # Order lifecycle
│   │   ├── exec_engine.py  # Quote/fill logic
│   │   └── risk_engine.py  # 11-dimension risk
│   ├── strategy/
│   │   ├── symbol_selector.py
│   │   ├── fee_model.py
│   │   └── viability.py
│   ├── metrics/
│   │   ├── metrics.py      # Runtime metrics
│   │   ├── session_reporter.py
│   │   └── dashboard.py    # Web dashboard
│   └── db/
│       ├── models.py
│       └── persistence.py
├── tests/
│   ├── test_fill_sim.py
│   ├── test_accounting.py
│   └── test_fsm.py
├── scripts/
│   ├── run_paper.sh
│   ├── run_live.sh
│   └── backtest.sh
└── docs/
    ├── setup.md
    ├── strategy.md
    └── faq.md
```

---

## Key Refactoring Tasks

### 1. Split Monolithic File

**Current:** 2781 lines in single file

**Target:** Modular structure
- `src/exchange/gate_rest.py` (~200 lines)
- `src/exchange/gate_ws.py` (~200 lines)
- `src/engine/fsm.py` (~150 lines)
- `src/engine/leg.py` (~100 lines)
- `src/engine/exec_engine.py` (~400 lines)
- `src/engine/risk_engine.py` (~300 lines)
- `src/metrics/dashboard.py` (~300 lines)
- `src/main.py` (~100 lines)

**Benefit:** Testability, maintainability, code reuse

---

### 2. Configuration Management

**Current:**
```python
class Cfg:
    PAPER = os.getenv("GATE_PAPER", "0") == "1"
    TARGET_NOTIONAL = 0.07
```

**Target:**
```yaml
# config/paper.yaml
mode: paper
symbols:
  selection: auto
  max_count: 5
  filters:
    min_spread_viability: 1.5
    min_volume_24h: 50000

sizing:
  target_notional: 0.07
  max_inventory: 5
  leverage: 10

execution:
  mode: aggressive_limit
  quote_ttl_sec: 4.0

paper_sim:
  fill_probability: 0.35
  slippage_ticks: 1
  partial_fill_prob: 0.25

risk:
  max_daily_loss_usd: 1.00
  kill_switch_usd: 2.00
```

---

### 3. Testing Infrastructure

**Unit Tests:**
```python
def test_paper_fill_simulation():
    sim = PaperFillSimulator(fill_probability=1.0)  # Always fill
    order = LimitOrder(..., price=100.0, side=Side.LONG)
    book = BookTick(ask=99.0, bid=98.0)  # Order crosses
    
    result = sim.simulate_ioc_fill(order, book, spec)
    
    assert result is not None
    assert result[0] > 0  # fill_size
    assert result[2] > 0  # fee
```

**Integration Tests:**
```python
async def test_full_hedge_cycle():
    engine = Engine(config="config/paper.yaml")
    await engine.start()
    
    # Wait for hedge to open
    await asyncio.sleep(5)
    
    # Verify both legs have positions
    fsm = engine._fsm_map["FIO_USDT"]
    assert fsm.long_leg.contracts > 0
    assert fsm.short_leg.contracts > 0
    
    await engine.stop()
```

---

### 4. Documentation

**README.md (Product Page):**
```markdown
# Gate Hedge Engine

**Status:** Experimental / Seeking validation  
**Risk Level:** High (aggressive hedging with small size)  
**Expected Edge:** Captures spread minus fees (not guaranteed)

## Quick Start

```bash
# Paper trading (recommended first)
docker-compose -f docker-compose.paper.yml up

# Check dashboard
open http://localhost:8765
```

## Performance (Paper Mode)

| Metric | Value |
|--------|-------|
| Fill Rate | 35% (IOC crossing orders) |
| Avg Spread Capture | 0.12% |
| Taker Fee | 0.05% |
| Net per fill | ~0.07% |
| Notional per leg | $0.50-1.00 |
| Expected daily | $0.05-0.20 (highly variable) |

## Limitations

- **Paper ≠ Live:** Latency, queue position, adverse selection not fully modeled
- **Small size only:** Not designed for large positions
- **High frequency:** Many orders, most cancel
- **Exchange risk:** Gate.io-specific, API changes can break

## License

MIT - Use at your own risk.
```

---

## Timeline Summary

| Week | Focus | Key Deliverable |
|------|-------|-----------------|
| 1 | Paper fixes | Working paper simulation |
| 2 | Validation | Proven paper strategy |
| 3 | Live testing | Verified live edge |
| 4 | Hardening | Production framework |
| 5-6 | Product | Sellable package |

---

## Success Criteria

**Technical:**
- [ ] Paper fills realistically
- [ ] Live PnL matches paper within 20%
- [ ] No unhandled exceptions in 48h runtime
- [ ] Risk engine halts before major losses

**Business:**
- [ ] Honest documentation published
- [ ] GitHub repo with 10+ stars
- [ ] 3+ users running paper mode
- [ ] 1+ user running live with positive results

**Honest Valuation:**
- Current: $0 (broken paper mode)
- After Phase 1: $500-1000 (working paper framework)
- After Phase 3: $2000-5000 (validated live edge)
- After Phase 6: $5000-10000 (sellable product with users)

---

## Immediate Next Steps

1. **Implement Patch Plan** (today)
   - Add PaperFillSimulator
   - Add SessionReporter
   - Fix WS desync noise

2. **Test Paper Mode** (tomorrow)
   - Run for 4 hours
   - Collect fill metrics
   - Verify PnL tracking

3. **Decision Point** (day 3)
   - If paper shows positive PnL → proceed to micro-live
   - If paper shows negative PnL → tune or abandon strategy

---

**Bottom Line:** 4-6 weeks from broken paper mode to sellable trading framework, assuming paper validation succeeds. If paper shows no edge, pivot to different strategy.
