# 🔥 Digital Gold Forge

**Multi-Platform API Integration System for Automated Content Distribution & Trading**

A comprehensive Python system that integrates multiple APIs and platforms to create an automated pipeline for:
- IPFS file storage via Pinata
- AI-powered content generation (Groq, OpenRouter, Hugging Face)
- Social media distribution (Twitter/X, TikTok)
- NFT minting on marketplaces (Zora, OpenSea, Rarible)
- Cloud deployment management (Replit, Render)
- AI-assisted development (Jules)
- Trading bot orchestration

## 🚀 Features

### Core Pipeline
1. **Asset Storage**: Upload files to IPFS (Pinata) + Google Drive backup
2. **AI Content Engine**: Generate platform-specific content using multiple LLM providers
3. **Social Distribution**: Auto-post to Twitter, TikTok with AI-generated captions
4. **NFT Minting**: Automatically mint digital assets as NFTs on Zora
5. **Deployment Management**: Manage deployments on Replit, Render, GitHub Actions
6. **Trading Bot Integration**: Orchestrate multiple trading bots with unified API

### Supported Platforms

| Platform | Purpose | API Status |
|----------|---------|------------|
| **Groq** | Fast LLM inference | ✅ Free tier available |
| **OpenRouter** | Multi-model LLM router | ✅ Free tier available |
| **Hugging Face** | Model hosting & inference | ✅ Free tier available |
| **Twitter/X** | Social media posting | ✅ API integration |
| **TikTok** | Video content posting | ✅ API integration |
| **Pinata** | IPFS file pinning | ✅ Free tier (1GB) |
| **Google Drive** | Cloud storage backup | ✅ API integration |
| **Zora** | NFT marketplace | ✅ SDK available |
| **Replit** | Cloud development | ✅ API available |
| **Render** | Cloud deployment | ✅ API available |
| **Jules** | AI coding agent | ✅ API available |
| **GitHub** | CI/CD & repo management | ✅ API integration |

## 📋 Prerequisites

- Python 3.8 or higher
- API keys for desired platforms (see `.env.example`)
- Git (for GitHub integration)

## 🔧 Installation

1. **Clone or navigate to the directory:**
```bash
cd /Users/alep/Downloads/api_integration_system
```

2. **Install dependencies:**
```bash
pip install -r requirements.txt
```

3. **Configure environment variables:**
```bash
cp .env.example .env
# Edit .env with your actual API keys
```

## 🎯 Quick Start

### Basic Usage

```bash
# Process a single file through the entire pipeline
python digital_gold_forge.py path/to/your/file.png "Amazing digital art"

# The system will:
# 1. Upload to IPFS (Pinata)
# 2. Backup to Google Drive
# 3. Generate AI content for each platform
# 4. Post to Twitter and TikTok
# 5. Mint as NFT on Zora
# 6. Update deployments
```

### Trading Bot Integration

```python
from digital_gold_forge import DigitalGoldForge, load_credentials_from_env

# Load credentials
creds = load_credentials_from_env()

# Initialize the forge
forge = DigitalGoldForge(creds)

# Run trading bot analysis and auto-post results
results = forge.forge_digital_gold("trading_analysis.png", "Daily trading insights")
```

## 🔑 API Key Setup

### Free Tier Options

**Groq**: Sign up at [groq.com](https://groq.com) - Free tier with rate limits
**OpenRouter**: Sign up at [openrouter.ai](https://openrouter.ai) - Free tier available
**Hugging Face**: Sign up at [huggingface.co](https://huggingface.co) - Free inference API
**Pinata**: Sign up at [pinata.cloud](https://pinata.cloud) - 1GB free storage

### Paid Services (Optional)

**Twitter/X**: Developer portal required for posting
**TikTok**: Developer portal + app review required
**Google Drive**: Service account setup needed
**Zora**: Gas fees for NFT minting
**Replit/Render**: Free tiers available, paid for scaling

## 📁 Project Structure

```
api_integration_system/
├── digital_gold_forge.py      # Main orchestrator
├── .env.example               # API key template
├── requirements.txt           # Python dependencies
├── README.md                  # This file
└── digital_gold_output/       # Generated content (auto-created)
```

## 🔌 API Integration Details

### Groq (Free Tier)
- **Rate Limit**: ~30 requests/minute, 14,400/day
- **Models**: Llama 3.1 8B, Mixtral 8x7B, etc.
- **Usage**: Fast inference for content generation

### OpenRouter (Free Tier)
- **Rate Limit**: 50 requests/day (free), 1000/day with $10 balance
- **Models**: Access to 100+ models via unified API
- **Usage**: Fallback/alternative LLM provider

### Hugging Face (Free Tier)
- **Rate Limit**: Few hundred requests/hour
- **Models**: Thousands of open-source models
- **Usage**: Specialized model inference

### Pinata (Free Tier)
- **Storage**: 1GB total
- **Files**: 500 files max
- **Requests**: 10,000 gateway requests/month
- **Usage**: IPFS file pinning

### Twitter/X (Free Tier)
- **Rate Limit**: ~1,500 tweets/month
- **Requirements**: Payment method on file
- **Usage**: Social media posting

### TikTok (Content Posting API)
- **Requirements**: OAuth + app review
- **Video Limits**: Public URL required (Google Drive)
- **Usage**: Video content distribution

## 🤖 Trading Bot Integration

The system can integrate with your existing trading bots:

```python
# Connect to trading bot results
from algo_micro_cap_bot.algo_trading_bot import run_analysis
from gate_market_maker_variants.gateio_market_maker import MarketMaker

# Run trading analysis
analysis_result = run_analysis()

# Auto-generate and post insights
forge.forge_digital_gold(
    analysis_result['chart_path'],
    f"Trading signal: {analysis_result['signal']}"
)
```

## 🔧 Configuration

Edit the `.env` file to customize:

```bash
# Enable/disable specific features
DIGITAL_GOLD_POST_TO_TWITTER=true
DIGITAL_GOLD_POST_TO_TIKTOK=true
DIGITAL_GOLD_MINT_NFTS=true
DIGITAL_GOLD_AUTO_DEPLOY=true

# Output directories
DIGITAL_GOLD_OUTPUT_DIR=./digital_gold_output
DIGITAL_GOLD_LOG_DIR=./digital_gold_logs
```

## 📊 Monitoring & Logs

Results are saved to `digital_gold_results.json`:

```json
{
  "timestamp": "2024-01-15T10:30:00",
  "file_path": "asset.png",
  "ipfs_cid": "QmHash...",
  "drive_id": "1AbCdEf...",
  "social_posts": {
    "twitter": "Generated tweet content",
    "tiktok": "Generated TikTok description"
  },
  "nft_minted": true,
  "deployments": {}
}
```

## 🚦 Rate Limits & Best Practices

1. **Groq**: Respect 30 req/min limit
2. **OpenRouter**: Maintain $10 balance for higher limits
3. **Pinata**: Monitor 1GB storage limit
4. **Twitter**: Stay within 1,500 tweets/month
5. **TikTok**: Use proper OAuth flow

## 🔒 Security Best Practices

- Never commit `.env` file to version control
- Use environment variables for all API keys
- Rotate API keys regularly
- Use read-only permissions where possible
- Implement rate limiting in your code

## 🐛 Troubleshooting

**Import Errors**: Ensure all dependencies are installed via `pip install -r requirements.txt`

**API Key Errors**: Verify keys in `.env` file match platform dashboards

**Rate Limiting**: Implement exponential backoff for retries

**IPFS Upload Failures**: Check Pinata API key permissions

**Twitter Posting**: Verify Twitter API credentials and payment method

## 📝 License

This system is provided as-is for educational and development purposes.

## 🤝 Contributing

This is a personal project for multi-platform API integration. Feel free to extend it for your needs.

## 📞 Support

For issues with specific APIs, refer to:
- Groq: https://console.groq.com/docs
- OpenRouter: https://openrouter.ai/docs
- Pinata: https://docs.pinata.cloud
- Twitter: https://developer.twitter.com/en/docs
- TikTok: https://developers.tiktok.com

---

**Built with 🔥 for automated digital asset management and distribution**
