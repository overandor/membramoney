# Micro Market Maker

A simple, public market maker for Gate.io micro-cap futures.

**Purpose:** Provide liquidity on micro-cap coins with configurable risk controls.

**Status:** Public, open-source, production-ready.

## ⚠️ Risk Warning

- Market making carries significant risk
- You can lose money if spreads move against you
- Start with small amounts (10-50 USDT)
- Monitor positions closely
- Use proper risk controls

## 🚀 Quick Start

```bash
# Install dependencies
pip install ccxt python-dotenv

# Configure API keys
cp .env.example .env
# Add your Gate.io API keys

# Run
python market_maker.py
```

## ⚙️ Configuration

Edit `.env`:
```bash
GATE_API_KEY=your_api_key
GATE_API_SECRET=your_api_secret

# Risk settings
MAX_POSITION_SIZE_USDT=50  # Max position per symbol
MAX_TOTAL_POSITIONS=3      # Max concurrent positions
MIN_SPREAD_PCT=0.003       # 0.3% minimum spread
QUOTE_SIZE_USDT=10         # Size per quote
```

## 📊 Features

- **Separate Long/Short MM**: Quote both sides independently (not hedged)
- **Risk Controls**: Max position size, max total positions, spread filters
- **Auto-refresh**: Cancel and re-quote when book moves
- **Position Tracking**: Real-time PnL monitoring
- **Trade Logging**: All trades logged to CSV
- **Simple Setup**: No complex configuration required

## 🧠 How It Works

1. **Quote both sides**: Post buy at bid, sell at ask
2. **On fill**: Record position, update quote
3. **Auto-refresh**: Cancel and re-quote when price moves >0.1%
4. **Risk limits**: Stop quoting if position exceeds limits
5. **Close positions**: Manual or auto-close at target

## 📈 Symbols

Default symbols (micro-cap futures):
- DOGS/USDT:USDT
- SLP/USDT:USDT
- MBOX/USDT:USDT
- ZK/USDT:USDT
- TLM/USDT:USDT

Edit `symbols.json` to customize.

## 🔐 Security

- Use API keys with trading permissions only
- Never enable withdrawals
- Use isolated margin mode
- Start with small test amounts

## 📝 License

MIT - Free to use, modify, distribute.

## 🤝 Contributing

Pull requests welcome. Keep it simple and safe.

## 📞 Support

Open an issue on GitHub for bugs or questions.
