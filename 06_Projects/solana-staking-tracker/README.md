# Solana Staking Tracker

Real-time Solana staking analysis system with wallet tracking and prediction.

## Features

- **Real Marinade Finance Integration** - Pulls actual staking data
- **Wallet Performance Analysis** - Track ROI and growth rates
- **$0 to $20,000 Wallet Detection** - Find high-growth wallets
- **Audio Prediction System** - Voice-based thought prediction
- **Web Dashboard** - Interactive analysis interface
- **Multi-Platform Deployment** - GitHub Actions, Vercel, Netlify

## Quick Start

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Run Marinade data extraction:
```bash
python real_marinade_extractor.py
```

3. Start web dashboard:
```bash
python marinade_deploy.py
```

4. Start audio prediction:
```bash
python audio_prediction_system.py
```

## API Endpoints

- `GET /` - Main dashboard
- `POST /api/collect` - Collect Marinade data
- `GET /api/leaderboard` - Get top performers
- `GET /api/0-to-20k` - Find $0→$20K wallets
- `POST /api/recording/start` - Start audio recording

## Deployment

### GitHub Actions
Automatic deployment on push to main branch.

### Vercel
```bash
vercel --prod
```

### Netlify
```bash
netlify deploy --prod --dir=.
```

## Real Data Sources

- Marinade Finance API: https://snapshots-api.marinade.finance/v1/stakers/ns/all
- Solana Explorer: https://explorer.solana.com
- CoinGecko API: https://api.coingecko.com/api/v3/simple/price

## Database

Uses SQLite for local storage:
- `real_marinade_wallets.db` - Staking wallet data
- `audio_prediction.db` - Audio analysis data
- `marinade_deploy.db` - Deployment cache

## License

MIT License
