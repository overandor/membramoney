#!/bin/bash

# Make environment variables permanent
echo "🔧 Making API keys permanent in ~/.zshrc"

# Backup existing .zshrc
if [ -f ~/.zshrc ]; then
    cp ~/.zshrc ~/.zshrc.backup.$(date +%Y%m%d_%H%M%S)
    echo "✅ Backed up ~/.zshrc"
fi

# Add environment variables to .zshrc
cat >> ~/.zshrc << 'EOF'

# Trading System Environment Variables
export GATE_API_KEY="a925edf19f684946726f91625d33d123"
export GATE_API_SECRET="b18dcc2cee347aaf1e28407de1a3e8638e6597c3b311cd59cb7d3573bfb3fc05"
export OPENROUTER_API_KEY="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"
export ENABLE_SOUND="1"
export ALERT_VOLUME="0.5"

# Trading aliases
alias trade-demo="python3 /Users/alep/Downloads/gate_working_demo.py"
alias trade-ai="python3 /Users/alep/Downloads/openrouter_ai_trader.py"
alias trade-alerts="python3 /Users/alep/Downloads/trading_system_with_alerts.py"
alias trade-spread="python3 /Users/alep/Downloads/gate.spread.py --dry"

EOF

echo "✅ Environment variables added to ~/.zshrc"
echo ""
echo "🔄 To activate in current session, run:"
echo "   source ~/.zshrc"
echo ""
echo "🚀 Or restart your terminal"
echo ""
echo "📊 Available trading commands:"
echo "   trade-demo     - Gate.io demo market maker"
echo "   trade-ai       - OpenRouter AI trader"
echo "   trade-alerts   - Trading system with sound alerts"
echo "   trade-spread   - Original Gate.io spread trader"
echo ""
echo "🔊 Sound alerts are enabled!"
echo "💡 All scripts now use environment variables - no hardcoded keys!"
