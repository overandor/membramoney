#!/bin/bash

# Multi-Token Trading Dashboard Launcher

echo "🚀 MULTI-TOKEN TRADING DASHBOARD"
echo "==============================="
echo "📊 Trading 30 High-Volume Tokens with AI"
echo ""
echo "🎯 Trading Tokens:"
echo "   HIPPO, NATIX, TOSHI, ELIZAOS, ETH5S, PUMP, COMMON, XRP5L, MRLN, LINK5L"
echo "   XPIN, RLS, AVAX5L, MEMEFI, FARTCOIN5S, OMI, DOGE, PTB, DOGE3S, XEM"
echo "   BLUAI, ADA5L, TREAT, BTC5L, ROOBEE, PEPE5S, ART, XNL, HMSTR, BLAST"
echo ""
echo "💰 Features:"
echo "   ✅ Real-time analysis of 30 tokens"
echo "   ✅ AI-powered opportunity detection"
echo "   ✅ Volume and volatility filtering"
echo "   ✅ Automatic trade execution"
echo "   ✅ $0.01-$0.10 nominal per trade"
echo "   ✅ 10-second trading cycles"
echo ""

# Check environment variables
echo "🔍 Checking environment variables..."
if [ -z "$GATE_API_KEY" ] || [ -z "$GATE_API_SECRET" ]; then
    echo "⚠️  No API keys found - running in DEMO mode"
    echo "   Set GATE_API_KEY and GATE_API_SECRET for live trading"
else
    echo "✅ API keys configured"
    echo "🔑 API Key: ${GATE_API_KEY:0:10}..."
fi

# Change to project directory
cd "$(dirname "$0")")

# Create logs directory
mkdir -p logs

# Install dependencies if needed
echo "📦 Checking dependencies..."
python3 -c "import tkinter, requests" 2>/dev/null || {
    echo "📦 Installing required packages..."
    pip3 install requests
}

echo ""
echo "🚀 Starting Multi-Token Trading Dashboard..."
echo "🖥️  GUI window will open shortly..."
echo ""

# Run the multi-token trading dashboard
python3 src/multi_token_trader.py
