#!/bin/bash

# Connected 24/7 Hedging System Launcher

echo "🚀 CONNECTED 24/7 HEDGING SYSTEM"
echo "==============================="
echo "📊 Gate.io Futures + AI Integration"
echo "💰 Nominal Value: $0.01-$0.10 per trade"
echo "🤖 AI-powered trading decisions"
echo "🔊 Exchange sounds will indicate successful orders"
echo ""

# Check environment variables
echo "🔍 Checking environment variables..."
missing_vars=()

if [ -z "$GATE_API_KEY" ]; then
    missing_vars+=("GATE_API_KEY")
fi

if [ -z "$GATE_API_SECRET" ]; then
    missing_vars+=("GATE_API_SECRET")
fi

if [ -z "$OPENROUTER_API_KEY" ]; then
    echo "⚠️  OPENROUTER_API_KEY not set (AI features will be disabled)"
else
    echo "✅ OPENROUTER_API_KEY configured"
fi

if [ ${#missing_vars[@]} -gt 0 ]; then
    echo "❌ Missing required environment variables:"
    for var in "${missing_vars[@]}"; do
        echo "   $var"
    done
    echo ""
    echo "Please set them and restart:"
    for var in "${missing_vars[@]}"; do
        echo "   export $var='your-value'"
    done
    exit 1
fi

echo "✅ All required environment variables configured"
echo "🔑 Gate.io API: ${GATE_API_KEY:0:10}..."
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
echo "🔗 Testing system connections..."
echo "🚀 Starting Connected 24/7 Hedging System..."
echo "⚠️  LIVE TRADING MODE - Real orders will be placed!"
echo "🔊 Keep Gate.io exchange open in browser to hear order sounds"
echo ""
echo "System features:"
echo "  ✅ Real-time Gate.io API connection"
echo "  ✅ AI-powered trading decisions"
echo "  ✅ Automatic profit taking"
echo "  ✅ Best bid/ask order placement"
echo "  ✅ Exchange sound integration"
echo ""
echo "Logs are being saved to logs/hedging_connected_$(date +%Y%m%d).log"
echo ""

# Run the connected hedging system
python3 src/hedging_system_connected.py
