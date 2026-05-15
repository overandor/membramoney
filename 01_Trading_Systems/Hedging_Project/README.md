# Professional Hedging Project

A professional Gate.io futures hedging system that places best bid/ask orders and automatically takes profits.

## Features

- **Best Bid/Ask Trading**: Places orders at current market best bid and ask prices
- **Profit Taking**: Automatically sells positions when profit threshold is reached
- **Risk Management**: Configurable nominal value ranges (0.01-0.10 USD default)
- **Real-time Monitoring**: Live position and order tracking
- **Professional Architecture**: Clean, modular codebase with proper error handling

## Quick Start

### 1. Setup Environment Variables

```bash
export GATE_API_KEY="your-gateio-api-key"
export GATE_API_SECRET="your-gateio-api-secret"
```

### 2. Install Dependencies

```bash
pip install pyyaml requests
```

### 3. Run the Hedging System

```bash
cd Hedging_Project
python src/main.py

# Or run directly
python src/hedging_system.py
```

## Configuration

Edit `config/hedging_config.yaml` to customize:

- Trading symbol (default: ENA_USDT)
- Nominal value range (default: $0.01-$0.10)
- Profit thresholds
- Risk management parameters

## Architecture

```
Hedging_Project/
├── config/
│   └── hedging_config.yaml    # Configuration file
├── src/
│   ├── main.py                # Entry point
│   ├── hedging_system.py      # Core hedging logic
│   └── utils/
│       ├── gateio_client.py   # API client
│       └── position_manager.py # Position management
├── logs/                      # Log files (empty initially)
└── docs/                      # Documentation
```

## Trading Strategy

1. **Market Making**: Places buy orders at best bid and sell orders at best ask
2. **Profit Taking**: Automatically closes profitable positions when threshold is met
3. **Risk Control**: Limits nominal value to 1-10 cents per trade
4. **Continuous Operation**: Runs in 5-second cycles

## Safety Features

- ✅ Environment variable usage (no hardcoded keys)
- ✅ Proper error handling and logging
- ✅ Order size limits (1-10 cent nominal value)
- ✅ IOC (Immediate or Cancel) orders to prevent stuck positions
- ✅ Real-time position monitoring

## Warnings

⚠️ **LIVE TRADING**: This system places real orders with real money
⚠️ **TEST FIRST**: Use small nominal values and monitor closely
⚠️ **API ACCESS**: Requires valid Gate.io API keys with futures trading enabled

## Monitoring

The system provides real-time logs showing:
- Order placement status
- Market prices and spreads
- Position updates
- Profit taking events
- Error conditions

## Support

Ensure your Gate.io account has:
- Futures trading enabled
- Sufficient margin for trades
- API keys with trading permissions
