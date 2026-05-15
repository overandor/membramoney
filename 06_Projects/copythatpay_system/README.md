# CopyThatPay — Selective Microstructure Scalper

**Status:** Experimental micro-market-making system for Gate.io futures.

**⚠️ SECURITY REQUIREMENT:** This system is designed for **Gate.io whitelisted IP addresses only**. You must whitelist your IP address in Gate.io API settings before using this system. Do not use without IP whitelisting enabled.

**WARNING:** This is NOT a money printer. With $9 capital and current parameters, fees will likely dominate any edge. This is a learning/experimental framework, not a production trading system.

---

## What This System Does

**CopyThatPay** is a selective microstructure scalper with real edge filters.

**Core Strategy:**
- Trade ONLY when real spread exists (0.4% minimum)
- One-side trading based on edge (bullish = long only, bearish = short only)
- Maker entries only - no taker fallback (no forced losses)
- Small achievable exits (0.3% target)
- Hard adverse selection exits (0.2% max adverse move)
- Skip dead markets (momentum < 0.05%) and too volatile (momentum > 1%)
- Daily stop loss (-2%) to prevent death spirals

**Risk Controls:**
- Max 2% equity drawdown per symbol, 10% global — hard enforced
- Time-based exits flatten stale positions automatically
- Volatility kill-switch pauses trading in abnormal conditions
- Inventory control (max 10 contracts net exposure per symbol)
- Edge ratio kill switch (pause if realized/expected < 80%)
- Every action logged with reason + risk state for audit

---

## Critical Issues (Read This)

### 1. Fee Structure Destroys Edge
- Entry (maker): ~0.075%
- Exit (maker): ~0.075%
- Round trip per leg: 0.15%
- Two legs: **0.30% total cost**
- Current spread target: **0.3%**

**Result:** Break-even before slippage. Negative edge in practice.

### 2. One-Leg Fill Risk
- Market moves after one leg fills
- "Hedge" becomes directional exposure
- DCA logic makes this worse (revenge trading)

### 3. Micro-Account Problems
- $9 capital = no diversification
- Minimum contract sizes limit flexibility
- One bad fill wipes multiple "wins"

---

## Required Fixes

| Issue | Current | Required |
|-------|---------|----------|
| Spread target | 0.3% | 0.8% minimum |
| Panic exit | 300s (5 min) | 60s (1 min) |
| DCA | Enabled | **Remove entirely** |
| Inventory cap | None | $0.50 force flatten |
| Pre-entry filter | None | Spread > 0.5%, volume > $10k |

---

## File Structure

```
copythatpay_system/
├── copythatpay.py    # Main engine (2195 lines)
└── README.md         # This file
```

---

## Configuration (Hardcoded)

Edit these values in `copythatpay.py`:

```python
MIN_REAL_SPREAD = 0.004         # 0.4% minimum spread to trade (real edge only)
SPREAD_TARGET_PCT = 0.003       # 0.3% target per leg (smaller wins = achievable exits)
PANIC_EXIT_SEC = 60             # Faster panic (was 300)
MAX_POSITION_USD = 0.45         # Max $0.45 per leg
MAX_NOTIONAL_PER_CONTRACT = 1.00 # $1.00 max notional (was 0.01 - too restrictive)
EDGE_RATIO_THRESHOLD = 0.8      # Pause if realized/expected < 80%
MAX_NET_CONTRACTS = 10          # Inventory control per symbol
MAX_ADVERSE_MOVE = 0.002        # 0.2% hard adverse selection exit
DAILY_STOP = -0.02              # -2% daily stop loss
```

---

## To Run (Not Recommended Without Fixes)

```bash
cd copythatpay_system
python3 copythatpay.py
```

---

## Hugging Face Deployment

**⚠️ Architecture Requirement:** This system uses a split architecture:
- **Hugging Face App:** UI + API Client (NO direct exchange access)
- **Backend Server:** FastAPI + CCXT + Execution Engine (static IP, whitelisted in Gate.io)

Hugging Face does NOT provide static outbound IPs. Direct exchange access from HF is impossible with IP whitelisting.

**Quick Deploy:**
1. Deploy backend on Fly.io/Render/AWS (static IP)
2. Whitelist backend IP in Gate.io API settings
3. Deploy Hugging Face app (UI only)
4. Set BACKEND_URL secret in HF Space

**See [HUGGINGFACE_DEPLOYMENT.md](HUGGINGFACE_DEPLOYMENT.md) for full details.**

---

## What You Actually Need Before This Works

### 1. Gate.io API Keys
Create `.env` file:

```bash
GATE_API_KEY=your_key
GATE_API_SECRET=your_secret
GROQ_API_KEY=your_groq_key  # for LLM symbol selection
```

### 2. IP Whitelisting (CRITICAL)
**Gate.io requires IP whitelisting for API access.** Add your server IP to Gate.io API settings before using this system. Do not use without IP whitelisting enabled.

### 3. Python Dependencies

```bash
pip install ccxt python-dotenv aiohttp groq rich pandas numpy
```

---

## What Works

- Risk engine structure
- Audit logging
- Hedge state recovery
- Edge tracking (expected vs realized)

## What's Broken

- Edge is negative after fees
- DCA is dangerous
- Panic exit too slow
- No inventory caps
- No pre-entry filters

---

## Next Steps

1. Apply fixes above
2. Paper trade for 100+ cycles
3. Measure actual edge (realized/expected profit ratio)
4. Only trade live if edge > 1.2 consistently

---

**Bottom line:** This is a sophisticated fee generator for the exchange. Fix it or don't trade it.
