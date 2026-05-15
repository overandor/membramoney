# Gate Aggressive Hedge Engine v2.0

A production-grade hedged spread-capture engine for Gate.io USDT Perpetual Futures with FSM state management, VWAP-accurate PnL accounting, and comprehensive risk controls.

## Features

### Core Trading Engine
- **FSM State Machine**: Explicit state transitions (FLAT → OPENING → HEDGED → BROKEN_HEDGE → REPAIRING → REDUCING → HALTED)
- **VWAP Accounting**: Volume-Weighted Average Price tracking for accurate PnL calculation
- **Risk Engine**: 11 risk dimensions including daily loss, gross exposure, leg imbalance, API error rate
- **Execution Modes**: MAKER_FIRST, AGGRESSIVE_LIMIT, TAKER_FALLBACK
- **Pre-Quote Profitability**: Viability filtering before order placement

### Architecture
- **Dual-Position Mode**: Support for simultaneous long/short positions
- **Order Store**: Independent order lifecycle management with partial-fill tracking
- **Book Cache**: Thread-safe order book cache with staleness detection
- **WebSocket Integration**: Real-time market data and private order/trade updates
- **REST API Adapter**: Full Gate.io futures API integration with rate limiting

### Monitoring & Safety
- **Dashboard**: Real-time web dashboard at http://localhost:8765
- **Persistence**: SQLite database for orders, fills, and events
- **Reconciliation**: Startup reconciliation against live exchange state
- **Emergency Controls**: Kill switch, forced flatten, manual halt

## Requirements

### Python Version
- Python 3.12+ (tested on 3.13)

### Dependencies
```bash
pip install aiohttp websockets
```

### Environment Variables

**For Live Trading:**
```bash
export GATE_API_KEY="your_api_key"
export GATE_API_SECRET="your_api_secret"
```

**For Paper Trading (No Real Orders):**
```bash
export GATE_PAPER=1
```

## Installation

1. Clone or download the engine files
2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Configure environment variables
4. Run the engine

## Usage

### Paper Trading Mode (Recommended for Testing)
```bash
GATE_PAPER=1 python gate_aggressive_hedge_v2.py
```

### Live Trading Mode
```bash
export GATE_API_KEY="your_key"
export GATE_API_SECRET="your_secret"
python gate_aggressive_hedge_v2.py
```

### Manual Symbol Selection
Edit the configuration to manually specify symbols:
```python
Cfg.SYMBOLS = ["BTC_USDT", "ETH_USDT", "SOL_USDT"]
```

## Configuration

Key configuration parameters in the `Cfg` class:

### Sizing
- `TARGET_NOTIONAL`: USD target per order (default: 0.07)
- `MIN_NOTIONAL`: Minimum order notional (default: 0.005)
- `LEVERAGE`: Trading leverage (default: 10)
- `MAX_INVENTORY`: Maximum contracts per leg (default: 5)

### Risk Management
- `MAX_DAILY_LOSS_USD`: Daily loss limit (default: 1.00)
- `KILL_SWITCH_USD`: Emergency stop threshold (default: 2.00)
- `MAX_GROSS_EXPOSURE_USD`: Total exposure limit (default: 5.00)
- `MAX_SYM_EXPOSURE_USD`: Per-symbol exposure limit (default: 1.50)

### Execution
- `DEFAULT_EXEC_MODE`: Execution mode (MAKER_FIRST, AGGRESSIVE_LIMIT, TAKER_FALLBACK)
- `QUOTE_TTL_SEC`: Order time-to-live (default: 4.0)
- `REPRICE_LOOP_SEC`: Reprice check interval (default: 0.15)

## Dashboard

Access the real-time dashboard at:
```
http://localhost:8765
```

Dashboard features:
- Per-symbol FSM state and inventory
- Real-time PnL tracking (realized/unrealized)
- Risk status and breach alerts
- Recent fills and events
- Performance metrics per symbol

## Architecture Overview

### State Machine (HedgeFSM)
```
FLAT → OPENING → HEDGED → BROKEN_HEDGE → REPAIRING → REDUCING → HALTED
```

Each state transition is logged with reason, preventing contradictory actions.

### Position Accounting (Leg)
- VWAP entry price calculation
- Proportional cost-basis reduction on closes
- Separate realized/unrealized PnL tracking
- Quanto multiplier support for contract specifications

### Order Lifecycle (OrderStore)
- Independent order tracking from position accounting
- Partial-fill accumulation
- Exchange-ID to client-ID mapping
- Database persistence with restore capability

## Safety Features

### Risk Dimensions
1. Daily loss monitoring
2. Kill switch on severe losses
3. Gross exposure limits
4. Per-symbol exposure limits
5. Leg imbalance duration tracking
6. Stale book detection
7. WebSocket desync detection
8. Reconciliation mismatch alerts
9. API error rate monitoring
10. Maximum open orders per symbol
11. Manual halt capability

### Emergency Controls
- **Kill Switch**: Immediate halt on severe loss
- **Forced Flatten**: Close all positions IOC
- **Manual Halt**: Per-symbol or global halt
- **Stale Book Pause**: Stop quoting on stale data
- **WS Desync Halt**: Halt on private WebSocket disconnect

## Database Schema

### Orders Table
- client_id, exchange_id, symbol, side
- requested_size, price, tif, exec_mode, status
- filled_size, remaining_size, avg_fill_price, fees_paid
- created_at, updated_at

### Fills Table
- fill_id, client_oid, exchange_oid
- symbol, side, size, price, fee
- pnl, is_close, ts

### Legs Table
- symbol, side, contracts, total_cost
- realized_pnl, fees_paid, fill_count

### Events Table
- level, message, symbol, data, ts

## Troubleshooting

### Python 3.13 Signal Handling
If you encounter `AttributeError: module 'asyncio' has no attribute 'SIGINT'`, the engine includes a fix using the `signal` module instead.

### Database Schema Mismatch
If you see `KeyError` or `OperationalError` related to database columns, delete the old database file:
```bash
rm gate_hedge_v2.db
```

### Paper Mode API Connectivity
In paper mode, the engine uses fallback symbols when the Gate.io API is unreachable. Check logs for "using fallback symbols for paper mode".

### WebSocket Desync Warnings
In paper mode, private WebSocket is skipped to avoid authentication errors. This is expected behavior.

## Performance Characteristics

### Throughput
- Book tick processing: ~150ms intervals
- Reprice checks: Every 150ms
- Risk monitoring: Every 5 seconds
- Order placement: Rate-limited to 8 RPS (private), 15 RPS (public)

### Latency
- Order submission: <100ms (network dependent)
- Fill processing: <50ms
- State transitions: <10ms

### Scalability
- Maximum symbols: 5 (configurable)
- Maximum concurrent orders: 8 per symbol
- Maximum inventory: 5 contracts per leg

## Known Limitations

See `KNOWN_ISSUES.md` for current limitations and known issues.

## Development History

See `CHANGELOG.md` for the complete development history and evolution of the system.

## License

This is proprietary trading software. Use at your own risk. Cryptocurrency trading involves substantial risk of loss.

## Support

For issues or questions, refer to the documentation files in the `docs/` directory.
