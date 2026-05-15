# Flagship Bot Refactor Roadmap

## Objective

Transform `newclaude.py` into one credible, production-minded, sellable trading system with honest limitations and documented capabilities.

## Current State

**Bot**: Gate Aggressive Hedge Engine v2.0  
**Status**: Operationally runnable, economically meaningless  
**Paper Mode**: IOC spam without fills  
**Profitability**: NOT PROVEN  
**Valuation**: $500 - $1,000 (before fixes)

## Target State

**Bot**: Production-Minded Paper/Live Trading Framework  
**Status**: Economically validated, honestly documented  
**Paper Mode**: Realistic simulation with fills  
**Profitability**: Validated through paper testing  
**Valuation**: $5,000 - $8,000 (after complete refactor)

---

## Phase 1: Critical Fixes (P0) - 9 Hours

### 1.1 Paper Fill Simulation - 4 Hours
**Status**: DESIGN COMPLETE, NOT IMPLEMENTED

**Tasks**:
- [ ] Implement `PaperFillModel` class
- [ ] Add fill probability logic
- [ ] Add slippage model
- [ ] Integrate into `_emit_order()`
- [ ] Test with various fill rates

**Deliverable**: Paper mode generates realistic fills

**Success Criteria**:
- Fill rate > 0% in paper mode
- Fees calculated correctly
- PnL calculated correctly
- Position accounting accurate

---

### 1.2 Session Summary - 2 Hours
**Status**: NOT STARTED

**Tasks**:
- [ ] Implement `SessionSummary` class
- [ ] Track session-level metrics
- [ ] Generate profitability verdict
- [ ] Display summary on shutdown
- [ ] Add to dashboard

**Deliverable**: Session-level economic analysis

**Success Criteria**:
- Gross notional tracked
- Fees tracked
- Fill rate calculated
- Realized PnL calculated
- Unrealized PnL calculated
- Cancels/order ratio tracked
- Clear verdict generated

---

### 1.3 Risk Logic Fix - 1 Hour
**Status**: NOT STARTED

**Tasks**:
- [ ] Suppress private WS checks in paper mode
- [ ] Clean up risk breach logic
- [ ] Test paper mode without breaches
- [ ] Update logging

**Deliverable**: Clean paper mode without false breaches

**Success Criteria**:
- No WS_DESYNC breaches in paper mode
- Risk logic appropriate for paper mode
- Clean logs

---

### 1.4 Integration Testing - 2 Hours
**Status**: NOT STARTED

**Tasks**:
- [ ] Run 1-hour paper session
- [ ] Verify all metrics working
- [ ] Verify session summary accurate
- [ ] Verify no risk breaches in paper mode
- [ ] Document behavior

**Deliverable**: Validated paper mode implementation

**Success Criteria**:
- All P0 features working together
- Session summary accurate
- No false risk breaches
- Documentation complete

---

## Phase 2: High Priority Features (P1) - 6 Hours

### 2.1 Symbol Viability Ranking - 2 Hours
**Status**: NOT STARTED

**Tasks**:
- [ ] Track per-symbol performance
- [ ] Implement ranking algorithm
- [ ] Display rankings in dashboard
- [ ] Add to session summary
- [ ] Test with multiple symbols

**Deliverable**: Symbol-level performance ranking

**Success Criteria**:
- Per-symbol fill rates tracked
- Per-symbol PnL tracked
- Ranking algorithm working
- Rankings displayed

---

### 2.2 IOC Spam Prevention - 2 Hours
**Status**: NOT STARTED

**Tasks**:
- [ ] Add book change detection
- [ ] Add minimum quote interval
- [ ] Implement stale book suppression
- [ ] Test with reduced order rate
- [ ] Tune parameters

**Deliverable**: Reduced IOC spam in paper mode

**Success Criteria**:
- Order rate reduced by 50%+
- Only meaningful quotes emitted
- Stale book detection working
- Configurable parameters

---

### 2.3 Paper Profitability Verdict - 2 Hours
**Status**: NOT STARTED

**Tasks**:
- [ ] Define pass/fail criteria
- [ ] Implement verdict logic
- [ ] Add to session summary
- [ ] Display prominently
- [ ] Document criteria

**Deliverable**: Clear profitability assessment

**Success Criteria**:
- Pass/fail criteria defined
- Verdict generated each session
- Displayed in dashboard
- Documented in README

---

## Phase 3: Secondary Cleanup (P2) - 4 Hours

### 3.1 Fix simple_gate_mm_3dollar.py - 1 Hour
**Status**: NOT STARTED

**Tasks**:
- [ ] Fix event loop architecture
- [ ] Replace `asyncio.run()` with `asyncio.get_event_loop()`
- [ ] Test in isolated environment
- [ ] Document as separate experiment

**Deliverable**: Working simple market maker

**Success Criteria**:
- Event loop error resolved
- Bot runs without errors
- Documented as separate from flagship

---

### 3.2 Fix algo_trading_bot.py - 1 Hour
**Status**: NOT STARTED

**Tasks**:
- [ ] Fix market order TIF bug
- [ ] Remove `gtc` from market orders
- [ ] Use `ioc` or no TIF
- [ ] Test order placement
- [ ] Document as separate experiment

**Deliverable**: Working algo trading bot

**Success Criteria**:
- TIF error resolved
- Market orders execute
- Documented as separate from flagship

---

### 3.3 Configuration Improvements - 1 Hour
**Status**: NOT STARTED

**Tasks**:
- [ ] Increase target notional for testing
- [ ] Add configurable fill probability
- [ ] Add configurable slippage
- [ ] Add minimum quote interval
- [ ] Document all parameters

**Deliverable**: Improved configuration

**Success Criteria**:
- All new parameters configurable
- Documentation updated
- Sensible defaults set

---

### 3.4 Documentation Updates - 1 Hour
**Status**: NOT STARTED

**Tasks**:
- [ ] Update README with paper mode details
- [ ] Document fill simulation model
- [ ] Document limitations
- [ ] Add troubleshooting guide
- [ ] Add configuration guide

**Deliverable**: Complete documentation

**Success Criteria**:
- Paper mode fully documented
- Fill model documented
- Limitations clearly stated
- Troubleshooting guide complete

---

## Phase 4: Production Readiness - 4 Hours

### 4.1 Live Mode Testing - 2 Hours
**Status**: NOT STARTED

**Tasks**:
- [ ] Test with small live position
- [ ] Verify real order placement
- [ ] Verify real fill handling
- [ ] Verify risk engine in live mode
- [ ] Compare paper vs live behavior

**Deliverable**: Validated live mode

**Success Criteria**:
- Live orders place correctly
- Live fills handled correctly
- Risk engine appropriate
- Paper/live comparison documented

---

### 4.2 Error Handling - 1 Hour
**Status**: NOT STARTED

**Tasks**:
- [ ] Add comprehensive error handling
- [ ] Add recovery logic
- [ ] Add graceful degradation
- [ ] Test error scenarios
- [ ] Document error modes

**Deliverable**: Robust error handling

**Success Criteria**:
- All error paths handled
- Recovery logic working
- Graceful degradation tested
- Error modes documented

---

### 4.3 Security Hardening - 1 Hour
**Status**: NOT STARTED

**Tasks**:
- [ ] Add API key validation
- [ ] Add rate limiting
- [ ] Add input sanitization
- [ ] Add audit logging
- [ ] Document security measures

**Deliverable**: Security-hardened system

**Success Criteria**:
- API keys validated
- Rate limiting active
- Inputs sanitized
- Audit logging working
- Security documented

---

## Phase 5: Product Framing - 2 Hours

### 5.1 Honest Positioning - 1 Hour
**Status**: NOT STARTED

**Tasks**:
- [ ] Write honest product description
- [ ] Document capabilities clearly
- [ ] Document limitations clearly
- [ ] Remove any misleading claims
- [ ] Add disclaimers

**Deliverable**: Honest product positioning

**Success Criteria**:
- No fake profitability claims
- Capabilities clearly stated
- Limitations clearly stated
- Appropriate disclaimers

---

### 5.2 Sales Documentation - 1 Hour
**Status**: NOT STARTED

**Tasks**:
- [ ] Create sales deck
- [ ] Create technical overview
- [ ] Create pricing guide
- [ ] Create support SLA
- [ ] Create deployment guide

**Deliverable**: Complete sales package

**Success Criteria**:
- Professional sales deck
- Technical overview accurate
- Pricing appropriate
- Support SLA defined
- Deployment guide complete

---

## Phase 6: Repository Cleanup - 2 Hours

### 6.1 Separate Experiments - 1 Hour
**Status**: NOT STARTED

**Tasks**:
- [ ] Move simple_gate_mm_3dollar.py to experiments/
- [ ] Move algo_trading_bot.py to experiments/
- [ ] Move metamask_python_bridge.py to experiments/
- [ ] Update documentation
- [ ] Clean up main directory

**Deliverable**: Clean repository structure

**Success Criteria**:
- Flagship bot in main directory
- Experiments in separate folder
- Clear separation documented
- No confusion

---

### 6.2 Final Testing - 1 Hour
**Status**: NOT STARTED

**Tasks**:
- [ ] Run full paper session
- [ ] Verify all features working
- [ ] Verify documentation accurate
- [ ] Verify no misleading claims
- [ ] Sign-off on production readiness

**Deliverable**: Production-ready flagship bot

**Success Criteria**:
- All features tested
- Documentation accurate
- No misleading claims
- Production ready

---

## Timeline Summary

| Phase | Duration | Dependencies | Status |
|-------|----------|--------------|--------|
| Phase 1: Critical Fixes | 9 hours | None | NOT STARTED |
| Phase 2: High Priority | 6 hours | Phase 1 | NOT STARTED |
| Phase 3: Secondary Cleanup | 4 hours | Phase 1 | NOT STARTED |
| Phase 4: Production Readiness | 4 hours | Phase 2 | NOT STARTED |
| Phase 5: Product Framing | 2 hours | Phase 4 | NOT STARTED |
| Phase 6: Repository Cleanup | 2 hours | Phase 5 | NOT STARTED |
| **Total** | **27 hours** | | **NOT STARTED** |

---

## Valuation Progression

### Current State ($500 - $1,000)
- Operationally runnable
- Well-architected
- Economically meaningless
- No paper validation

### After Phase 1 ($1,500 - $2,500)
- Paper fills simulated
- Session summaries working
- Risk logic clean
- Economic validation possible

### After Phase 2 ($2,500 - $4,000)
- Symbol ranking working
- IOC spam prevented
- Profitability verdict clear
- Configurable parameters

### After Phase 3 ($3,000 - $5,000)
- Other bots fixed
- Configuration improved
- Documentation complete
- Clean repository

### After Phase 4 ($4,000 - $6,000)
- Live mode validated
- Error handling robust
- Security hardened
- Production ready

### After Phase 5 ($5,000 - $7,000)
- Honestly positioned
- Professional documentation
- Sales package complete
- Appropriate pricing

### After Phase 6 ($5,000 - $8,000)
- Clean repository
- Fully tested
- Production ready
- Sellable product

---

## Success Criteria

### Minimum Viable (After Phase 1)
- Paper mode generates fills
- Session summaries working
- Risk logic clean
- Economic validation possible

### Production Ready (After Phase 4)
- Paper and live modes working
- Error handling robust
- Security hardened
- Documentation complete

### Sellable Product (After Phase 6)
- Honestly positioned
- Clean repository
- Fully tested
- Professional documentation
- Appropriate valuation

---

## Risk Mitigation

### Technical Risks
- **Risk**: Fill simulation unrealistic
- **Mitigation**: Configurable parameters, validation against live data

- **Risk**: Paper mode doesn't predict live performance
- **Mitigation**: Clear documentation of limitations, live mode testing

### Business Risks
- **Risk**: Overpromising capabilities
- **Mitigation**: Honest positioning, clear limitations

- **Risk**: Misleading profitability claims
- **Mitigation**: No claims without live validation, disclaimers

---

## Next Steps

1. **Start Phase 1.1** - Implement paper fill simulation
2. **Complete Phase 1** - All critical fixes
3. **Validate Phase 1** - Economic validation possible
4. **Proceed to Phase 2** - High priority features
5. **Complete all phases** - Production-ready flagship bot

---

**Roadmap Status**: COMPLETE  
**Implementation Status**: NOT STARTED  
**Total Estimated Effort**: 27 hours  
**Current Valuation**: $500 - $1,000  
**Target Valuation**: $5,000 - $8,000
