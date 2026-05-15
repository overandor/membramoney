---
title: LLM 15m Signal Hunter
emoji: 🎯
colorFrom: orange
colorTo: red
sdk: docker
pinned: false
license: mit
---

# LLM 15-Minute Signal Hunter

Multi-coin cryptocurrency signal prediction system using LLM analysis of Gate.io futures, Jupiter DEX, and Solana onchain data.

## Features

- **Multi-Coin Coverage**: SOL, BTC, ETH, JUP, WIF, BONK, RENDER, PYTH, HNT, RAY
- **Multiple Data Sources**: Gate.io futures, Jupiter DEX quotes, Solana RPC
- **LLM Predictions**: Groq, OpenRouter, or Gemini for 15-minute directional signals
- **Heuristic Fallback**: Rule-based predictions when LLM unavailable
- **Real-time Dashboard**: Web interface with live predictions and market data
- **No Live Trading**: Predictions only for analysis and research

## How It Works

1. **Market Data Collection**: Scans Gate.io futures prices, Jupiter DEX liquidity, and Solana onchain metrics
2. **Feature Extraction**: Calculates returns, volatility, order book imbalance, funding rates, and signature velocity
3. **LLM Analysis**: Uses LLM to predict LONG/SHORT/NO_TRADE for next 15 minutes
4. **Signal Verification**: Heuristic cross-validation of LLM predictions
5. **Dashboard Display**: Real-time web interface shows predictions and market data

## Configuration

Set environment variables:
- `GROQ_API_KEY`: Groq API key (optional)
- `OPENROUTER_API_KEY`: OpenRouter API key (optional)  
- `GEMINI_API_KEY`: Google Gemini API key (optional)
- `SYMBOLS`: Comma-separated list of symbols to scan
- `PREDICTION_HORIZON_MINUTES`: Prediction horizon (default: 15)

## Deployment

This runs as an async web server on port 7860. Access the dashboard at the Space URL.

## System Law

**LLM predicts direction only. No trading approval. No real execution.**

This is a research and analysis tool, not a trading system.
