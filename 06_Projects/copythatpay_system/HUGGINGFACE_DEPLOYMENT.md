# Hugging Face Deployment Guide

## ⚠️ Architecture Requirement

**This system uses a split architecture:**

- **Hugging Face App:** UI + API Client (NO direct exchange access)
- **Backend Server:** FastAPI + CCXT + Execution Engine (with static IP, whitelisted in Gate.io)

**Hugging Face does NOT provide static outbound IPs.** Direct exchange access from HF is impossible with IP whitelisting enabled.

## Quick Start

### Step 1: Deploy Backend (Static IP Server)

Choose a platform with static IP:
- **Fly.io** (recommended, free tier available)
- **Render** (easy deployment)
- **AWS EC2** (full control)

**On Fly.io:**
```bash
# Install flyctl
curl -L https://fly.io/install.sh | sh

# Login
flyctl auth login

# Initialize
flyctl launch

# Set environment variables
flyctl secrets set GATE_API_KEY=your_key
flyctl secrets set GATE_API_SECRET=your_secret
flyctl secrets set GROQ_API_KEY=your_groq_key

# Deploy
flyctl deploy
```

**Get your backend URL** (e.g., `https://your-app.fly.dev`)

### Step 2: Whitelist Backend IP in Gate.io

1. Get your backend server's static IP
2. Go to Gate.io API settings
3. Add the IP to whitelist
4. Wait for whitelist to activate

### Step 3: Deploy Hugging Face App

1. Go to [huggingface.co/new-space](https://huggingface.co/new-space)
2. Choose **Gradio** SDK
3. Name your space (e.g., `copythatpay-ui`)
4. Make it **Public** or **Private** (your choice)

### Step 4: Upload Files to Hugging Face

Rename and upload:
- `huggingface_app.py` → `app.py`
- `huggingface_requirements.txt` → `requirements.txt`

### Step 5: Add Backend URL Secret

In Hugging Face Space settings, add secret:
- `BACKEND_URL` - Your backend URL (e.g., `https://your-app.fly.dev`)

## Architecture

```
User → Hugging Face (UI + API Client) → Backend API (Static IP) → Gate.io
                                           ↓
                                       CCXT
                                           ↓
                                   Execution Engine
                                           ↓
                                   Risk Engine
```

## What Gets Deployed

### Hugging Face App
- **Status Tab** - Start/stop engine via backend API
- **Metrics Tab** - Real-time performance from backend
- **Symbol Performance Tab** - Per-symbol analytics
- **Configuration Tab** - Risk controls documentation
- **Info Tab** - Architecture documentation
- **Connection Status** - Backend health check

### Backend Server
- FastAPI with CORS enabled
- Bot lifecycle management (start/stop)
- Real-time metrics endpoint
- Symbol performance tracking
- Auto-prune functionality
- Configuration management

## Security

- **Backend:** Static IP whitelisted in Gate.io, API keys stored as secrets
- **Hugging Face:** No exchange keys, no CCXT, no direct exchange access
- **Communication:** HTTPS only, backend validates requests

## Current Mode

The backend runs in **demo mode** with mock data. To connect to the real engine:

1. Integrate `copythatpay.py` into `backend.py`
2. Replace mock state with real engine calls
3. Ensure API keys are set in backend secrets

## Security Notes

- API keys are stored as Hugging Face Secrets (never exposed in code)
- Paper trading mode is default (no real money at risk)
- Risk controls are enforced (max daily loss, position size limits)
- No user data is stored or shared

## Monitoring

The Space includes:
- Real-time metrics dashboard
- Symbol performance tracking
- Auto-pruning of underperforming symbols
- Edge ratio monitoring

## Scaling

For production deployment:
1. Upgrade to Space Pro for GPU/CPU resources
2. Add Redis for multi-user state management
3. Add PostgreSQL for trade history persistence
4. Implement proper authentication

## Support

For issues or questions:
- Check the main README.md for system architecture
- Review the configuration parameters in copythatpay.py
- Monitor the edge ratio metric (should be > 0.8 for healthy system)
