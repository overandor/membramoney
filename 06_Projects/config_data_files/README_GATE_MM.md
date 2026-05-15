# Gate.io Multi-Ticker Market Maker

## 🚀 Overview
Production-ready multi-ticker market maker for Gate.io USDT perpetual contracts with low nominal values (0-0.10 USDT).

## 📊 Backtest Results
Top performing symbols based on historical analysis:

### ✅ **Allowed for Trading** (High Win Rate & Profitable)
1. **4_USDT** - 65.2% win rate, $9.84 PnL, 2.72 Sharpe
2. **PEPE_USDT** - 85.3% win rate, $2.92 PnL, 6.04 Sharpe ⭐
3. **PIPPIN_USDT** - 73.0% win rate, $2.33 PnL, 2.63 Sharpe
4. **DOGE_USDT** - 70.8% win rate, $1.98 PnL, 6.18 Sharpe ⭐
5. **GALA_USDT** - 64.9% win rate, $0.72 PnL, 1.22 Sharpe
6. **ENA_USDT** - 62.8% win rate, $0.39 PnL, 0.53 Sharpe

### ❌ **Rejected** (Low Win Rate or Unprofitable)
- TRU_USDT, NOM_USDT, JOE_USDT, BULLA_USDT, SWARMS_USDT, DRIFT_USDT

## 🎯 Key Features
- **AI-Powered Alpha**: Microstructure + trend/mean-reversion signals
- **Risk Management**: $15 USD risk per contract, 2x leverage
- **Maker-Only**: Places limit orders for fee optimization
- **Backtesting**: Execution-aware with realistic fill probabilities
- **Real-time**: WebSocket market data + REST API integration
- **SQLite**: Local state persistence and trade journaling

## ⚙️ Configuration
- **Max Mark Price**: $0.10 USDT (filters low-nominal contracts)
- **Min Volume**: $100,000 24h quote volume
- **Max Symbols**: 12 concurrent symbols
- **Entry Edge**: 5 bps minimum expected edge
- **Stop Loss**: 1.6x ATR multiplier
- **Take Profit**: 1.0x ATR multiplier

## 🛠️ Installation & Setup

### 1. Dependencies
```bash
pip install aiohttp websockets pandas numpy python-dotenv
```

### 2. Environment Configuration
Copy `.env.gate_mm` and configure your API keys:
```bash
# Set your Gate.io API credentials
GATE_API_KEY=your_api_key_here
GATE_API_SECRET=your_api_secret_here

# Keep LIVE_TRADING=false for testing
LIVE_TRADING=false
```

### 3. Running the Bot

#### Scan for Symbols
```bash
./run_gate_mm.sh scan
```

#### Run Backtest
```bash
./run_gate_mm.sh backtest
```

#### Paper Trading (Simulation)
```bash
./run_gate_mm.sh paper
```

#### Live Trading (Real Money)
⚠️ **WARNING**: This places real orders!
```bash
# 1. Set LIVE_TRADING=true in .env.gate_mm
# 2. Run with confirmation:
./run_gate_mm.sh live
```

## 📈 Performance Metrics

### Best Performers
- **PEPE_USDT**: Exceptional 85.3% win rate with 6.04 Sharpe ratio
- **DOGE_USDT**: Strong 70.8% win rate with 6.18 Sharpe ratio
- **4_USDT**: Highest absolute PnL at $9.84 with good risk metrics

### Risk Management
- Maximum drawdown limits enforced
- Position sizing based on ATR volatility
- Inventory limits per symbol
- Cooldown periods between trades

## 🔧 Technical Details

### Market Making Strategy
1. **Signal Generation**: Combines EMA trends, mean reversion, order flow
2. **Entry**: Maker orders at best bid/ask with edge requirements
3. **Exit**: Take profit and stop loss orders automatically placed
4. **Reconciliation**: Continuous order state synchronization

### Alpha Model Components
- **Trend**: EMA8 vs EMA21 momentum (25% weight)
- **Mean Reversion**: Z-score deviation (20% weight)
- **Order Flow**: Bid/ask size imbalance (20% weight)
- **Microstructure**: Spread analysis (10% weight)
- **Volume**: Volume Z-score (5% weight)

## ⚠️ Risk Disclaimer
- This is software infrastructure, not a guarantee of profit
- Past performance does not indicate future results
- Cryptocurrency trading involves substantial risk
- Start with paper trading to validate performance
- Never risk more than you can afford to lose

## 📞 Support
The bot includes comprehensive logging and SQLite database for:
- Trade execution tracking
- Performance analytics
- Error monitoring
- State persistence

## 🚀 Next Steps
1. Run paper trading for 24-48 hours
2. Monitor performance against backtest expectations
3. Adjust parameters based on live market conditions
4. Consider enabling live trading only after validation
