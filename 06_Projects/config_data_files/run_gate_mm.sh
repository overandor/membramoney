#!/bin/bash

# Gate.io Multi-Ticker Market Maker Launcher

echo "🚀 GATE.IO MULTI-TICKER MARKET MAKER"
echo "===================================="
echo ""

# Load environment
if [ -f ".env.gate_mm" ]; then
    export $(cat .env.gate_mm | grep -v '^#' | xargs)
    echo "✅ Environment loaded from .env.gate_mm"
else
    echo "❌ .env.gate_mm file not found!"
    exit 1
fi

echo "🔑 API Key: ${GATE_API_KEY:0:10}..."
echo "🌐 Base URL: $GATE_BASE_URL"
echo "📊 Live Trading: $LIVE_TRADING"
echo "💰 Risk per Contract: $CONTRACT_RISK_USD USDT"
echo "🎯 Max Mark Price: $MAX_MARK_PRICE USDT"
echo "📈 Max Symbols: $MAX_SYMBOLS"
echo ""

# Check mode
MODE=${1:-scan}

echo "🎮 Mode: $MODE"
echo ""

case $MODE in
    "scan")
        echo "🔍 Scanning for low-nominal futures contracts..."
        python3 gate_multi_ticker_mm_prod.py --mode scan
        ;;
    "backtest")
        echo "📊 Running backtest on available symbols..."
        python3 gate_multi_ticker_mm_prod.py --mode backtest
        ;;
    "paper")
        echo "📝 Starting paper trading simulation..."
        echo "⚠️  This will simulate trades without real money"
        python3 gate_multi_ticker_mm_prod.py --mode paper
        ;;
    "live")
        if [ "$LIVE_TRADING" != "true" ]; then
            echo "❌ LIVE_TRADING is set to false in .env.gate_mm"
            echo "   Set LIVE_TRADING=true to enable live trading"
            exit 1
        fi
        echo "🔴 STARTING LIVE TRADING!"
        echo "⚠️  THIS WILL PLACE REAL ORDERS WITH REAL MONEY!"
        echo "   Press Ctrl+C to stop immediately"
        echo ""
        read -p "Are you absolutely sure? Type 'LIVE' to continue: " confirm
        if [ "$confirm" = "LIVE" ]; then
            python3 gate_multi_ticker_mm_prod.py --mode live
        else
            echo "❌ Live trading cancelled"
            exit 1
        fi
        ;;
    *)
        echo "❌ Invalid mode: $MODE"
        echo ""
        echo "Available modes:"
        echo "  scan     - Scan for low-nominal contracts"
        echo "  backtest - Run backtest analysis"
        echo "  paper    - Paper trading simulation"
        echo "  live     - Live trading (requires LIVE_TRADING=true)"
        echo ""
        echo "Usage: $0 [mode]"
        exit 1
        ;;
esac
