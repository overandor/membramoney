#!/bin/bash

# Run Professional Hedging System

echo "🚀 PROFESSIONAL HEDGING PROJECT"
echo "================================"
echo "📊 Gate.io Futures Hedging System"
echo ""

# Check environment variables
if [ -z "$GATE_API_KEY" ] || [ -z "$GATE_API_SECRET" ]; then
    echo "❌ Missing environment variables!"
    echo "Please set:"
    echo "   export GATE_API_KEY='your-key'"
    echo "   export GATE_API_SECRET='your-secret'"
    echo ""
    echo "Or run: source ~/.zshrc"
    exit 1
fi

echo "✅ Environment variables found"
echo "🔑 API Key: ${GATE_API_KEY:0:10}..."
echo ""

# Change to project directory
cd "$(dirname "$0")"

# Create logs directory
mkdir -p logs

echo "🚀 Starting Hedging System..."
echo "⚠️  LIVE TRADING MODE - Real orders will be placed!"
echo "💰 Nominal value range: $0.01-$0.10"
echo "📊 Symbol: ENA_USDT"
echo ""
echo "Press Ctrl+C to stop"
echo ""

# Run the hedging system
python3 src/hedging_system.py
