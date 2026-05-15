# 🛡️ ENA_USDT Hedging Project

**Intelligent ENA/USDT futures hedging strategy powered by Cascade AI**

## 📋 Project Overview

This project implements a sophisticated hedging strategy specifically designed for ENA/USDT futures trading on Gate.io. It features intelligent decision-making, real-time profit detection, and automated risk management.

## 🧠 Key Features

### 🤖 Cascade AI Assistant
- **Intelligent Market Analysis**: Real-time analysis of spread, volume, and price pressure
- **Risk Assessment**: Multi-factor risk evaluation with position and balance monitoring
- **Decision Making**: Smart decisions based on opportunity scoring and risk thresholds
- **Adaptive Strategy**: Aggressive or conservative hedging based on market conditions

### 🛡️ Advanced Hedging Strategy
- **Best Bid/Ask Placement**: Orders placed at optimal prices for execution
- **Profit Detection**: Automatic detection of profitable hedge positions
- **Market Closing**: Instant profit taking with market orders when thresholds are met
- **Age-Based Closing**: Automatic closure of old positions to free capital

### 📊 Real-Time Analytics
- **Live Market Data**: WebSocket integration for real-time price updates
- **Performance Tracking**: Detailed statistics and PnL monitoring
- **Risk Management**: Position limits, drawdown protection, and stop-loss mechanisms
- **UI Dashboard**: Modern interface with real-time updates and logging

## 🚀 Quick Start

### Prerequisites
- Python 3.8+
- Gate.io API credentials
- Sufficient futures account balance (recommended $10+)

### Installation

1. **Clone/Download the project**:
   ```bash
   cd /Users/alep/Downloads/ENA_Hedging_Project
   ```

2. **Install dependencies**:
   ```bash
   pip install gate-api numpy tkinter websockets
   ```

3. **Configure API credentials**:
   - Edit `config/ena_config.py`
   - Add your Gate.io API key and secret

4. **Run the hedging bot**:
   ```bash
   python src/ena_hedging_market_maker.py
   ```

## 📁 Project Structure

```
ENA_Hedging_Project/
├── src/                          # Source code
│   └── ena_hedging_market_maker.py  # Main hedging application
├── config/                       # Configuration files
│   └── ena_config.py               # Trading configuration
├── logs/                         # Log files
├── docs/                         # Documentation
├── README.md                     # This file
└── requirements.txt              # Python dependencies
```

## ⚙️ Configuration

### Key Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `min_profit_bps` | 1.5 | Minimum profit margin (1.5 bps = 0.015%) |
| `max_hedge_position` | 50.0 | Maximum ENA position size |
| `hedge_order_size_usd` | 3.0 | Order size in USD |
| `market_sell_threshold` | 3.0 | Profit threshold for market selling |
| `max_hedge_age_seconds` | 300 | Maximum age before forced closure |

### Risk Management

- **Position Limits**: Maximum 50 ENA tokens
- **Balance Protection**: Uses only 30% of available balance
- **Age Limits**: Automatic closure after 5 minutes
- **Stop Loss**: 10 bps stop-loss protection

## 🧠 Cascade AI Decision Logic

### Decision Tree

```
🔴 HIGH RISK (>0.8): REDUCE exposure
🚀 HIGH OPPORTUNITY (>0.6): AGGRESSIVE hedging
🛡️ MODERATE OPPORTUNITY (>0.3): CONSERVATIVE hedging
⏳ HIGH POSITION RISK: WAIT
👁️ NEUTRAL: MONITOR market
```

### Opportunity Scoring

- **Spread Analysis**: 40% weight (higher spread = better opportunity)
- **Volume Imbalance**: 30% weight (detects buying/selling pressure)
- **Price Pressure**: 30% weight (market momentum)

## 📊 Trading Flow

1. **Market Analysis** (Every 5 seconds)
   - Analyze spread, volume, and price pressure
   - Calculate risk and opportunity scores
   - Make intelligent trading decisions

2. **Hedge Placement** (When opportunities detected)
   - Place buy orders slightly above best bid
   - Place sell orders slightly below best ask
   - Ensure minimum profit margin

3. **Profit Monitoring** (Every 2 seconds)
   - Check profitability of active hedges
   - Close profitable positions with market orders
   - Close aged positions to free capital

4. **Risk Management** (Continuous)
   - Monitor position limits
   - Track balance and drawdown
   - Implement stop-loss and position reduction

## 📈 Performance Metrics

### Key Indicators

- **Hedge PnL**: Total profit from hedging operations
- **Success Rate**: Percentage of profitable hedge closures
- **Average Profit**: Mean profit per successful hedge
- **Risk Score**: Current risk assessment (0-1)
- **Opportunity Score**: Market opportunity rating (0-1)

### UI Features

- **Real-time Price Display**: Live bid/ask and mid prices
- **AI Decision Panel**: Current AI analysis and recommendations
- **Hedging Statistics**: Active positions and PnL tracking
- **Performance Charts**: Visual representation of trading performance
- **Activity Log**: Detailed trading history and decisions

## 🛠️ Development

### Adding New Features

1. **New Strategies**: Extend `CascadeAIAssistant` class
2. **Risk Rules**: Modify configuration parameters
3. **UI Components**: Update the main application UI
4. **Logging**: Add new log categories and levels

### Testing

```bash
# Development mode (safer settings)
python src/ena_hedging_market_maker.py --mode dev

# Production mode
python src/ena_hedging_market_maker.py --mode prod
```

## 🔒 Security

- **API Key Security**: Store credentials securely
- **Position Limits**: Hard-coded maximum positions
- **Balance Protection**: Never uses more than configured percentage
- **Emergency Stop**: Manual and automatic stop mechanisms

## 📞 Support

### Common Issues

1. **No Orders Placed**: Check API credentials and balance
2. **Connection Issues**: Verify WebSocket connectivity
3. **High Risk**: Reduce position size or increase confidence threshold

### Debug Mode

Enable debug logging in `config/ena_config.py`:
```python
self.log_level = "DEBUG"
```

## 📄 License

This project is for educational and personal use only. Trading cryptocurrencies involves substantial risk of loss.

## 🤖 About Cascade AI

Cascade AI is an intelligent trading assistant that:
- Analyzes market conditions in real-time
- Makes data-driven trading decisions
- Manages risk automatically
- Adapts to changing market conditions

**Built with ❤️ for ENA_USDT futures trading**

---

**⚠️ Risk Warning**: Cryptocurrency trading is highly risky. Never invest more than you can afford to lose. This software is for educational purposes.
