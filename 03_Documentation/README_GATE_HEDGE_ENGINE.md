# Gate Microcap Hedge Engine with LLM Reasoning

A continuous LLM-powered decision assistant for Gate.io futures market making with historical-error learning.

## Features

- **Historical Market Feature Builder**: Computes price, volume, spread, volatility, momentum, liquidity, and opportunity scores
- **LLM Symbol Selector**: Uses Groq LLM to rank symbols and recommend WATCH/OPEN/SKIP/HALT actions
- **Continuous LLM Thinking Loop**: Refreshes features every 20 seconds and updates LLM recommendations
- **Outcome Testing Loop**: Evaluates prior LLM decisions after 60 seconds and logs correctness
- **LLM Critic Loop**: Reviews errors every 90 seconds and updates trading policy
- **Execution Gate**: LLM must approve OPEN actions with confidence >= threshold
- **Safety-First Defaults**: Paper mode by default, tiny position sizes, live trading requires explicit ARM_LIVE=YES

## Installation

1. Copy environment template:
```bash
cp .env.example .env
```

2. Edit `.env` and add your API keys:
```bash
GATE_API_KEY=your_gate_api_key_here
GATE_API_SECRET=your_gate_api_secret_here
GROQ_API_KEY=your_groq_api_key_here
```

3. Install dependencies:
```bash
pip install aiohttp python-dotenv
```

## Configuration

### Required Environment Variables

```bash
# Gate.io API
GATE_API_KEY=your_gate_api_key_here
GATE_API_SECRET=your_gate_api_secret_here

# Groq LLM
GROQ_API_KEY=your_groq_api_key_here
GROQ_MODEL=llama-3.1-8b-instant

# LLM Feature Flags
USE_LLM_THINKER=1
ENABLE_LLM_CRITIC=1
ENABLE_LLM_POLICY_UPDATE=1

# LLM Timing
LLM_THINK_INTERVAL_SEC=20
LLM_OUTCOME_HORIZON_SEC=60
LLM_CRITIC_INTERVAL_SEC=90
LLM_MAX_ERROR_CONTEXT=20
LLM_MIN_CONFIDENCE_TO_OPEN=0.65

# Trading Safety
GATE_PAPER=1
ARM_LIVE=NO
LIVE_ONE_SHOT=1
ORDER_NOTIONAL_USD=10
MAX_TOTAL_EXPOSURE_USD=100
```

## Usage

### Paper Mode (Safe - Default)

```bash
GATE_PAPER=1 USE_LLM_THINKER=1 ENABLE_LLM_CRITIC=1 python gate_microcap_hedge_engine_fixed.py
```

### Live Mode (Requires ARM_LIVE=YES)

```bash
GATE_PAPER=0 ARM_LIVE=YES USE_LLM_THINKER=1 ENABLE_LLM_CRITIC=1 python gate_microcap_hedge_engine_fixed.py
```

## LLM Memory Files

The system creates and maintains three memory files:

- `llm_trade_memory.jsonl`: Logs all trade decisions with outcomes
- `llm_error_memory.jsonl`: Logs failed decisions for policy learning
- `llm_policy.json`: Current learned policy from LLM critic

## Execution Gate

The bot only opens positions when:

1. ✅ Deterministic spread/fee edge passes
2. ✅ Deterministic balance/exposure risk passes
3. ✅ LLM action exists for symbol
4. ✅ LLM action is OPEN (not WATCH/SKIP/HALT)
5. ✅ LLM confidence >= policy min_confidence_to_open

If LLM returns HALT, the bot sets global_halt with reason.
If LLM returns WATCH or SKIP, the bot does not open.

## Dashboard State

The engine exposes state via `engine.get_dashboard_state()`:

```python
{
  "llm": {
    "enabled": true,
    "model": "llama-3.1-8b-instant",
    "thesis": "market thesis",
    "risk_notes": "risk notes",
    "actions": {},
    "features": {}
  },
  "llm_learning": {
    "policy": {},
    "open_tests": 0,
    "recent_errors": []
  },
  "system": {
    "global_halt": false,
    "global_halt_reason": "",
    "active_symbols": [],
    "paper_mode": true
  }
}
```

## Safety

- **Paper Mode**: Default, no real trades
- **Live Trading**: Requires ARM_LIVE=YES (not set by default)
- **No Hardcoded Keys**: All API keys read from environment
- **Git Safety**: .env and memory files in .gitignore
- **Tiny Positions**: ORDER_NOTIONAL_USD=10 by default
- **Exposure Limits**: MAX_TOTAL_EXPOSURE_USD=100 by default

## Validation

After editing, validate the file compiles:

```bash
python -m py_compile gate_microcap_hedge_engine_fixed.py
```

Then run paper mode:

```bash
GATE_PAPER=1 USE_LLM_THINKER=1 ENABLE_LLM_CRITIC=1 python gate_microcap_hedge_engine_fixed.py
```

## Expected Results

- Dashboard starts
- Symbols are selected
- LLM thesis appears
- LLM actions appear
- Trade memory JSONL files are created
- Errors are logged and critic updates llm_policy.json
- No live trades occur (paper mode)

## LLM Actions

- **OPEN**: LLM approves opening position
- **WATCH**: LLM wants to monitor but not open yet
- **SKIP**: LLM recommends skipping this opportunity
- **HALT**: LLM triggers global halt (risk condition)

## Outcome Testing Rules

- **OPEN**: Wrong if spread collapses badly or movement becomes chaotic
- **WATCH**: Wrong if a large clean move was missed
- **SKIP**: Wrong if a strong clean opportunity occurred
- **HALT**: Wrong if no actual risk condition existed

## Policy Updates

The LLM critic can update:

- `avoid_conditions`: Conditions to avoid
- `prefer_conditions`: Conditions to prefer
- `confidence_adjustments`: Per-symbol confidence adjustments
- `min_confidence_to_open`: Threshold (clamped 0.55-0.95)
- `notes`: Summary of changes

The critic cannot modify source code, only llm_policy.json.

## Architecture

```
Polling Loop → Market Features → LLM Selector → LLM Actions
                                              ↓
                                    Execution Gate
                                              ↓
                                    Trade Decisions
                                              ↓
                              Outcome Testing Loop
                                              ↓
                                    Error Memory
                                              ↓
                                    Policy Critic
                                              ↓
                                    Policy Update
```

## Security Notes

⚠️ **NEVER commit .env or real API keys**
⚠️ **NEVER run live trading without ARM_LIVE=YES**
⚠️ **ALWAYS start with paper mode**
⚠️ **Monitor LLM decisions before enabling live trading**
