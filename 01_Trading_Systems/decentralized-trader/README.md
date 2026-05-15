# Decentralized Trader - No Registration Required

A complete decentralized trading system that operates without any registration. Only requires wallet connection and API keys for trading on multiple DEX protocols.

## 🚀 Features

- **No Registration Required** - Wallet-based authentication only
- **Multi-Protocol Support** - 1inch, Hyperliquid, Drift Protocol
- **Geolocation Compliance** - Automatic location validation
- **Non-Custodial** - Your keys, your crypto
- **Real-time Trading** - Live market data and execution
- **Leverage Trading** - Up to 100x on supported protocols
- **Beautiful UI** - Modern, responsive interface

## 📋 Supported Protocols

### 1inch
- **Type**: DEX Aggregator
- **Chains**: Ethereum, BSC, Polygon
- **Use Case**: Best rate token swaps
- **API Key**: Required (free tier available)

### Hyperliquid
- **Type**: Perpetual Trading
- **Features**: High leverage, low fees
- **API Key**: Required
- **Special**: No KYC for most regions

### Drift Protocol
- **Type**: Solana Perpetuals
- **Features**: Up to 101x leverage
- **Chain**: Solana
- **API Key**: Required

## 🛠️ Installation

### Prerequisites
- Python 3.11+
- Node.js (for frontend development)
- MetaMask or Phantom wallet

### Setup

1. **Clone and setup environment**
```bash
cd /Users/alep/Downloads/decentralized-trader
cp .env.example .env
```

2. **Install Python dependencies**
```bash
# Using conda (recommended)
conda create -n dex-trader python=3.11 -y
conda activate dex-trader
pip install -r requirements.txt

# Or using pip directly
pip install -r requirements.txt
```

3. **Configure API Keys**
Edit `.env` file with your API keys:
```bash
# Get API keys from:
# 1inch: https://business.1inch.com/
# Hyperliquid: https://app.hyperliquid.xyz/API
# Drift: https://docs.drift.trade/
```

4. **Run the application**
```bash
python app.py
```

5. **Access the interface**
Open your browser to: `http://localhost:8080`

## 🔐 Security Features

- **Client-side key management** - API keys stored locally
- **Location validation** - Automatic compliance checking
- **Non-custodial** - Never stores private keys
- **HTTPS ready** - Secure communication
- **Input validation** - Prevents common attacks

## 🌍 Geolocation & Compliance

The system automatically validates user location:
- **Restricted**: US users (use VPN if needed)
- **Allowed**: All other regions
- **VPN Compatible**: Works with most VPN services

## 💡 Usage Guide

### 1. Connect Wallet
- **Ethereum**: Click "Connect MetaMask"
- **Solana**: Click "Connect Phantom"

### 2. Configure API Keys
- Enter your API keys in the configuration section
- Keys are stored locally in your browser only

### 3. Select Protocol
- Choose between 1inch, Hyperliquid, or Drift
- Each protocol has different features

### 4. Execute Trades
- Select tokens and amount
- Adjust leverage if applicable
- Click "Execute Trade"

## 🔧 API Integration

### 1inch API
```python
# Get swap quote
quote = await oneinch.get_quote('ETH', 'USDC', 1.0)

# Execute swap
result = await oneinch.execute_swap('ETH', 'USDC', 1.0, wallet_address, private_key)
```

### Hyperliquid API
```python
# Get market data
markets = hyperliquid.get_market_data('ETH')

# Place order
order = await hyperliquid.place_order('ETH', 'buy', 1.0, leverage=10)
```

### Drift Protocol API
```python
# Get available markets
markets = await drift.get_markets()

# Place perpetual order
order = await drift.place_perp_order('SOL-PERP', 'buy', 10.0)
```

## 🚨 Important Notes

- **API Keys Required**: Each protocol requires an API key
- **VPN for US**: US users may need VPN for some protocols
- **Test First**: Always test with small amounts
- **Private Keys**: Never share your private keys
- **Gas Fees**: Network fees apply to all transactions

## 🛡️ Risk Disclaimer

- **High Risk**: Cryptocurrency trading is extremely risky
- **Leverage Danger**: High leverage can lead to liquidation
- **API Limits**: Rate limits may apply
- **Smart Contract Risk**: Protocol smart contracts have risks
- **Do Your Own Research**: Understand protocols before trading

## 📞 Support

### Getting API Keys

1. **1inch**: Visit https://business.1inch.com/
   - Sign up for free tier
   - Get API key from dashboard

2. **Hyperliquid**: Visit https://app.hyperliquid.xyz/API
   - Create API wallet
   - Configure permissions

3. **Drift**: Visit https://docs.drift.trade/
   - Follow integration guide
   - Get API access

### Troubleshooting

**Wallet Connection Issues**
- Ensure MetaMask/Phantom is installed
- Check browser is unlocked
- Try refreshing the page

**API Key Errors**
- Verify keys are correct
- Check API key permissions
- Ensure keys have trading access

**Location Errors**
- Try using a VPN
- Check IP geolocation
- Verify protocol restrictions

## 🔄 Development

### Running in Development
```bash
# Backend
python app.py

# Frontend (for development)
npm install
npm run dev
```

### Project Structure
```
decentralized-trader/
├── app.py              # Main Flask application
├── app.js              # Frontend JavaScript
├── index.html          # Main interface
├── requirements.txt    # Python dependencies
├── .env.example       # Environment variables template
└── README.md          # This file
```

## 📄 License

MIT License - Use at your own risk

## 🤝 Contributing

Contributions welcome! Please ensure:
- Code follows security best practices
- Tests are included
- Documentation is updated
- Risk warnings are prominent

---

**⚠️ WARNING: This is experimental software. Trading cryptocurrencies involves significant risk including potential loss of principal. Always do your own research and never risk more than you can afford to lose.**
