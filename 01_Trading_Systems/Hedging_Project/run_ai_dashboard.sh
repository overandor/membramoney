#!/bin/bash

# AI Trading Dashboard Launcher

echo "🚀 AI TRADING DASHBOARD - 24/7 HEDGING SYSTEM"
echo "=============================================="
echo "📊 Complete Trading Interface with AI Optimization"
echo "💰 Nominal Value: $0.01-$0.10 per trade"
echo "🤖 AI-powered decisions and optimization"
echo "🔊 Exchange sounds on successful orders"
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
    echo "⚠️  Dashboard will start in DEMO mode"
    echo "   Set variables for live trading:"
    for var in "${missing_vars[@]}"; do
        echo "   export $var='your-value'"
    done
    echo ""
else
    echo "✅ All required environment variables configured"
    echo "🔑 Gate.io API: ${GATE_API_KEY:0:10}..."
    echo ""
fi

# Change to project directory
cd "$(dirname "$0")"

# Create logs directory
mkdir -p logs

# Install dependencies if needed
echo "📦 Checking dependencies..."
python3 -c "import tkinter, yaml, requests" 2>/dev/null || {
    echo "📦 Installing required packages..."
    pip3 install pyyaml requests
}

echo ""
echo "🎯 Dashboard Features:"
echo "  ✅ Real-time market data display"
echo "  ✅ AI decision making and optimization"
echo "  ✅ Live trading activity monitoring"
echo "  ✅ Profit/loss tracking"
echo "  ✅ System status indicators"
echo "  ✅ Interactive controls"
echo "  ✅ Comprehensive logging"
echo "  ✅ 24/7 automated trading"
echo ""
echo "🚀 Starting AI Trading Dashboard..."
echo "🖥️  GUI window will open shortly..."
echo ""

# Run the AI trading dashboard
python3 src/trading_dashboard_ai.py
