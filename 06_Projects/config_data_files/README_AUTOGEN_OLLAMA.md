# AutoGen + Ollama Gate.io Market Maker

AI-powered market making bot using AutoGen for multi-agent coordination and Ollama for local LLM inference.

## Features

- **AI-Powered Trading**: Uses AutoGen agents for intelligent trading decisions
- **Local LLM**: Ollama integration for privacy and cost efficiency
- **Balance Protection**: $3 minimum balance with continuous monitoring
- **Risk Management**: Multi-agent risk validation before trades
- **Market Making**: Provides liquidity on Gate.io futures

## Setup

### 1. Install Dependencies

```bash
pip install -r autogen_ollama_requirements.txt
```

### 2. Install Ollama

```bash
# On macOS
brew install ollama

# Pull the model
ollama pull llama3.2
```

### 3. Configure Environment

Copy the example env file and add your keys:

```bash
cp autogen_ollama.env.example .env
```

Edit `.env` with your Gate.io API keys:
```
GATE_API_KEY=your_key
GATE_API_SECRET=your_secret
OLLAMA_MODEL=llama3.2
OLLAMA_BASE_URL=http://localhost:11434
```

### 4. Start Ollama

```bash
# Restart Ollama if models aren't responding
pkill ollama
ollama serve
```

### 5. Verify Ollama Models

```bash
# Check available models
curl http://localhost:11434/api/tags

# Test a model
curl http://localhost:11434/api/generate -d '{"model":"qwen2.5:0.5b","prompt":"test","stream":false}'
```

If Ollama models aren't responding, restart the service:
```bash
pkill ollama && ollama serve
```

### 6. Run the Bot

```bash
python autogen_ollama_gate_mm.py
```

## Configuration

- **MIN_BALANCE**: $3.00 (minimum balance protection)
- **TARGET_BALANCE**: $3.00 (target for trading)
- **MAX_POSITION_SIZE**: $1.00 (max per trade)
- **SPREAD_THRESHOLD**: 0.1% (minimum spread to trade)
- **RISK_PER_TRADE**: 10% of balance per trade

## Trading Strategy

The bot uses three AutoGen agents:

1. **MarketMaker Agent**: Analyzes market data and generates trading signals
2. **Risk Agent**: Validates signals against risk parameters
3. **Balance Agent**: Monitors balance and enforces minimum balance

## Safety Features

- Continuous balance monitoring
- Automatic position closure on low balance
- Risk validation before every trade
- Maximum position size limits
- Confidence threshold for AI signals

## Logs

Logs are saved to: `/Users/alep/Downloads/autogen_ollama_gate_mm.log`

## Default Symbols

- FIO/USDT:USDT
- NTRN/USDT:USDT
- SKL/USDT:USDT

## Notes

- This bot runs in paper mode by default for testing
- Ensure Ollama is running before starting the bot
- Monitor logs for balance alerts and trading activity
