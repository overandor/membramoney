# Deployment Guide

## Local Deployment

### Prerequisites
- Python 3.8+
- Gate.io account with API access
- IP whitelisted in Gate.io API settings

### Setup
```bash
# Clone or navigate to repo
cd copythatpay_system

# Install dependencies
pip install -r requirements.txt

# Create .env file from example
cp .env.example .env
# Edit .env with your API keys

# Run
python3 copythatpay.py
```

## GitHub Deployment

### Push to GitHub
```bash
git init
git add .
git commit -m "Initial commit: CopyThatPay execution engine"
git branch -M main
git remote add origin https://github.com/yourusername/copythatpay.git
git push -u origin main
```

### Repository Structure
```
copythatpay_system/
├── copythatpay.py              # Main engine
├── huggingface_app.py          # Gradio interface
├── huggingface_requirements.txt
├── requirements.txt            # Full dependencies
├── .env.example
├── README.md
├── HUGGINGFACE_DEPLOYMENT.md
└── DEPLOYMENT.md
```

## Hugging Face Deployment

### Step 1: Get Hugging Face Space IP
1. Create a new Space at huggingface.co/new-space
2. Choose Gradio SDK
3. After creation, note the Space URL
4. The IP will be visible in the Space settings or logs

### Step 2: Whitelist IP in Gate.io
1. Go to Gate.io API settings
2. Add the Hugging Face Space IP to whitelist
3. Wait for whitelist to activate (usually instant)

### Step 3: Upload Files
Rename and upload:
- `huggingface_app.py` → `app.py`
- `huggingface_requirements.txt` → `requirements.txt`

### Step 4: Add Secrets
In Space Settings → Secrets, add:
- `GATE_API_KEY`
- `GATE_API_SECRET`
- `GROQ_API_KEY`

### Step 5: Deploy
The Space will auto-deploy. Monitor logs for any errors.

## Security Checklist

Before deployment:
- [ ] IP whitelisted in Gate.io
- [ ] API keys stored as secrets (not in code)
- [ ] Paper trading mode tested first
- [ ] Risk controls verified (max daily loss, position size)
- [ ] Edge ratio monitoring working
- [ ] Symbol performance tracking enabled

## Monitoring

### Key Metrics to Watch
- **Edge Ratio:** Should be > 0.8 for healthy system
- **Win Rate:** Track over time
- **Realized vs Expected PnL:** Gap indicates execution quality
- **Symbol Performance:** Auto-prune worst performers

### Alerts
- Daily stop loss hit
- Drawdown breach
- Edge ratio < 0.8
- API connection failures

## Troubleshooting

### API Connection Issues
- Verify IP is whitelisted
- Check API keys are correct
- Ensure Gate.io API is accessible from your location

### No Trades Executing
- Check MIN_REAL_SPREAD filter (0.4% minimum)
- Verify No Trade Zone filters (momentum)
- Check edge score threshold
- Review logs for "NO EDGE" messages

### Edge Ratio < 1.0
- This indicates execution quality issues
- Check slippage metrics
- Review fill quality
- Consider increasing SPREAD_TARGET_PCT

## Scaling Considerations

### From $9 to $100+
- Increase MAX_POSITION_USD
- Monitor fee impact
- Consider tier-based position sizing
- Track edge ratio at each scale

### Multi-User (Future)
- Implement Docker container per user
- Add Redis for state management
- Implement proper authentication
- Add PostgreSQL for trade history

## Support

For issues:
1. Check logs in console or Hugging Face Space
2. Verify API keys and IP whitelist
3. Review configuration parameters
4. Monitor edge ratio and win rate metrics
