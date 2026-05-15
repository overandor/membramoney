#!/bin/bash

# 24/7 Professional Hedging System Launcher

echo "🚀 24/7 PROFESSIONAL HEDGING SYSTEM"
echo "=================================="
echo "📊 Continuous Gate.io Futures Trading"
echo "💰 Nominal Value: $0.01-$0.10 per trade"
echo "🔊 Exchange sounds will indicate successful orders"
echo ""

# Check environment variables
echo "🔍 Checking environment variables..."
if [ -z "$GATE_API_KEY" ]; then
    echo "❌ GATE_API_KEY not set"
    echo "   export GATE_API_KEY='your-key'"
    exit 1
fi

if [ -z "$GATE_API_SECRET" ]; then
    echo "❌ GATE_API_SECRET not set"
    echo "   export GATE_API_SECRET='your-secret'"
    exit 1
fi

echo "✅ Environment variables configured"
echo "🔑 API Key: ${GATE_API_KEY:0:10}..."
echo ""

# Change to project directory
cd "$(dirname "$0")"

# Create logs directory
mkdir -p logs

# Install dependencies if needed
echo "📦 Checking dependencies..."
python3 -c "import yaml, requests" 2>/dev/null || {
    echo "📦 Installing required packages..."
    pip3 install pyyaml requests
}

echo ""
echo "🚀 Starting 24/7 Hedging System..."
echo "⚠️  LIVE TRADING MODE - Real orders will be placed!"
echo "🔊 Keep Gate.io exchange open in browser to hear order sounds"
echo ""
echo "System will run continuously. Press Ctrl+C to stop."
echo "Logs are being saved to logs/hedging_247_$(date +%Y%m%d).log"
echo ""

# Run the 24/7 hedging system
python3 src/hedging_system_247.py
