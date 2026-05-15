# Simple Gate.io Market Maker ($3 Balance Protection)

Rule-based market making bot without AI dependencies. Focus on balance protection and reliable execution.

## Features

- **$3 Balance Protection**: Continuous monitoring with automatic position closure
- **Rule-Based Trading**: No AI dependencies - reliable and predictable
- **Market Making**: Provides liquidity on both sides of the order book
- **Risk Management**: Position size limits and spread thresholds
- **Simple Setup**: Only requires Gate.io API keys

## Setup

### 1. Install Dependencies

```bash
pip install aiohttp ccxt python-dotenv
```

### 2. Configure Environment

Create `.env` file with your Gate.io API keys:

```
GATE_API_KEY=your_gate_api_key_here
GATE_API_SECRET=your_gate_api_secret_here
```

### 3. Run the Bot

```bash
python simple_gate_mm_3dollar.py
```

## Configuration

- **MIN_BALANCE**: $3.00 (minimum balance protection)
- **TARGET_BALANCE**: $3.00 (target for trading)
- **MAX_POSITION_SIZE**: $1.00 (max per trade)
- **SPREAD_THRESHOLD**: 0.1% (minimum spread to trade)
- **RISK_PER_TRADE**: 10% of balance per trade

## Trading Strategy

**Rule-Based Market Making:**

1. **Spread Check**: Only trade if spread >= 0.1%
2. **Volume Check**: Only trade if 24h volume >= $10,000
3. **Balance Check**: Only trade if balance >= $3.00
4. **Position Sizing**: 10% of balance, max $1.00 per trade
5. **Order Placement**: Alternate between buy at bid and sell at ask

## Safety Features

- Continuous balance monitoring
- Automatic position closure when balance < $3.00
- Maximum position size limits
- Spread and volume thresholds
- Round-trip fee consideration

## Logs

Logs are saved to: `/Users/alep/Downloads/simple_gate_mm.log`

## Default Symbols

- FIO/USDT:USDT
- NTRN/USDT:USDT
- SKL/USDT:USDT

## Advantages Over AI Version

- No Ollama/AI setup required
- Faster execution (no LLM latency)
- More predictable behavior
- Lower resource usage
- Easier to debug

## When to Use AI Version

Use the AutoGen + Ollama version when:
- You want adaptive trading strategies
- You have Ollama working properly
- You want multi-agent decision making
- You can tolerate LLM latency

## Notes

- This bot uses rule-based logic for reliability
- Balance protection is the top priority
- Monitor logs for balance alerts and trading activity
