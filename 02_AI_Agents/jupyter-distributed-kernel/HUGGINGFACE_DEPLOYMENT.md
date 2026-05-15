# On-Chain Profit Agent - Hugging Face Deployment

Deploy the AI-powered profit agent to Hugging Face Spaces for cloud execution.

## Features

- ✅ AI-powered on-chain profit analysis
- ✅ Starts with 0 balance
- ✅ Identifies arbitrage, MEV, and flash loan opportunities
- ✅ Runs on cloud (Hugging Face Spaces)
- ✅ Free tier available
- ✅ Real-time analysis via Groq API

## Quick Deploy to Hugging Face

### Option 1: Web Interface (Easiest)

1. Go to https://huggingface.co/new-space
2. Choose **Gradio** as the SDK
3. Name your space (e.g., `onchain-profit-agent`)
4. Make it **Public** (free tier)
5. Click **Create Space**

6. Upload these files to your Space:
   - `app.py` (rename `huggingface_app.py` to `app.py`)
   - `requirements.txt` (rename `huggingface_requirements.txt` to `requirements.txt`)
   - `.env` (add your API keys)

7. Add API keys as Space Secrets:
   - Go to Settings → Secrets
   - Add `GROQ_API_KEY` = `your_groq_key`
   - Add `HUGGING_FACE_API_KEY` = `your_hf_key`

8. The Space will automatically build and deploy!

### Option 2: Git Deployment

```bash
# Clone your space
git clone https://huggingface.co/spaces/YOUR_USERNAME/onchain-profit-agent
cd onchain-profit-agent

# Copy files
cp huggingface_app.py app.py
cp huggingface_requirements.txt requirements.txt

# Commit and push
git add .
git commit -m "Deploy on-chain profit agent"
git push
```

## API Keys Required

Get your Groq API key from https://console.groq.com/ (free tier available)

```bash
GROQ_API_KEY=gsk_...
HUGGING_FACE_API_KEY=hf_...
```

## Usage

Once deployed, your Hugging Face Space will be available at:
```
https://huggingface.co/spaces/YOUR_USERNAME/onchain-profit-agent
```

### Example Prompts

- "Find arbitrage opportunities between Uniswap and Sushiswap"
- "Identify liquidation opportunities on Aave"
- "Find flash loan arbitrage on Polygon"
- "Analyze MEV opportunities on Solana"
- "Find profitable DEX arbitrage on Ethereum"

## Profit Strategies Detected

The AI analyzes:
1. **DEX Arbitrage** - Price differences between exchanges
2. **Flash Loan Arbitrage** - Borrow without collateral, arbitrage, repay
3. **MEV Extraction** - Front-running, sandwich attacks
4. **Liquidation Opportunities** - Undercollateralized positions
5. **Cross-Chain Arbitrage** - Price differences across chains

## From 0 to Profitable

The agent is designed to:
1. Start with 0 balance
2. Find opportunities requiring no initial capital
3. Execute strategies (flash loans, arbitrage)
4. Accumulate profits
5. Reinvest for compound growth

## Local Testing

Test locally before deploying:

```bash
# Install dependencies
pip install -r huggingface_requirements.txt

# Set API keys
export GROQ_API_KEY="your_key"

# Run locally
python3 huggingface_app.py
```

## Production Deployment

For production use:
1. Use a dedicated Hugging Face Space (Pro tier)
2. Implement real on-chain execution (web3.py)
3. Add risk management and position sizing
4. Implement proper error handling
5. Add monitoring and alerts
6. Use production API keys

## Security Notes

- Never commit API keys to git
- Use Hugging Face Secrets for API keys
- Start with paper trading
- Test thoroughly with small amounts
- Implement proper gas estimation

## Cost

- **Hugging Face Spaces**: Free tier available
- **Groq API**: Free tier available (up to limits)
- **Gas fees**: Required for on-chain execution

## Troubleshooting

**Build fails:**
- Check requirements.txt dependencies
- Ensure app.py is named correctly
- Check Hugging Face build logs

**API errors:**
- Verify API keys in Secrets
- Check Groq API quota
- Test API keys locally first

**No opportunities found:**
- Try different prompts
- Be more specific about chains/DEXs
- Check current market conditions

## Next Steps

1. Deploy to Hugging Face Spaces
2. Test with various prompts
3. Implement real on-chain execution
4. Add backtesting capabilities
5. Deploy to production with real capital
