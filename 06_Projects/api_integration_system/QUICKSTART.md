# 🚀 Quick Start Guide - Digital Gold Forge

## ⚡ Setup in 5 Minutes

### 1. Install Dependencies
```bash
cd /Users/alep/Downloads/api_integration_system
pip install -r requirements.txt
```

### 2. Configure API Keys
```bash
cp .env.example .env
# Edit .env with your API keys
```

### 3. Test the System
```bash
# Test with a sample file
python digital_gold_forge.py ../config_data_files/README.md "Test post"
```

## 🤖 Trading Bot Commands

### List All Trading Bots
```bash
python trading_bot_orchestrator.py list
```

### Run a Specific Bot
```bash
python trading_bot_orchestrator.py run algo_micro_cap_bot
```

### Run All Bots
```bash
python trading_bot_orchestrator.py run-all
```

### Post Bot Results to Social Media
```bash
python trading_bot_orchestrator.py post algo_micro_cap_bot
```

### Generate Trading Report
```bash
python trading_bot_orchestrator.py report
```

### Generate and Post Report
```bash
python trading_bot_orchestrator.py report --post
```

## 🔑 Minimum Required API Keys

For basic functionality, you only need:

**Required:**
- `GROQ_API_KEY` (free at groq.com)
- `PINATA_API_KEY` and `PINATA_SECRET_KEY` (free at pinata.cloud)

**Optional (for full features):**
- Twitter API keys (for posting)
- TikTok API keys (for video posting)
- Google Drive credentials (for backup)
- Other platform keys as needed

## 📊 What Gets Organized

Your Downloads folder now contains **69 organized systems**:

- **34 Main Trading Systems** - Each in its own 5-word named folder
- **35 Supporting Systems** - Tests, tools, dashboards, etc.
- **API Integration System** - The new multi-platform forge

## 🎯 Common Workflows

### Workflow 1: Test a Trading Bot
```bash
python trading_bot_orchestrator.py run algo_micro_cap_bot
python trading_bot_orchestrator.py post algo_micro_cap_bot
```

### Workflow 2: Daily Trading Report
```bash
python trading_bot_orchestrator.py run-all
python trading_bot_orchestrator.py report --post
```

### Workflow 3: Process New Asset
```bash
python digital_gold_forge.py path/to/new_asset.png "New trading signal"
```

## 📝 Environment Variables Priority

The system checks for API keys in this order:
1. `.env` file in api_integration_system/
2. System environment variables
3. Hardcoded defaults (not recommended)

## 🔍 Troubleshooting

**Import errors?** Run: `pip install -r requirements.txt`

**API key errors?** Check `.env` file has correct keys

**Bot not found?** Run: `python trading_bot_orchestrator.py list`

**Permission denied?** Make sure Python has execute permissions

## 📚 Next Steps

1. Get free API keys from Groq and Pinata
2. Test with a simple file
3. Explore individual trading bots
4. Set up automated scheduling (cron, GitHub Actions)
5. Configure additional platforms as needed

## 💡 Tips

- Start with just Groq + Pinata (both free)
- Test each bot individually before running all
- Use `--dry-run` mode when available
- Monitor rate limits on free tiers
- Keep API keys secure - never commit `.env`

---

**Need help?** Check the full README.md for detailed documentation.
