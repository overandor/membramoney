#!/bin/bash

# OpenRouter API Key Export Script
echo "🔑 Exporting OpenRouter API Key..."

# Export OpenRouter API key
export OPENROUTER_API_KEY="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"

# Also keep Gate.io keys for trading bots
export GATE_API_KEY="a925edf19f684946726f91625d33d123"
export GATE_API_SECRET="b18dcc2cee347aaf1e28407de1a3e8638e6597c3b311cd59cb7d3573bfb3fc05"

echo "✅ OpenRouter API key exported"
echo "✅ Gate.io API keys exported"
echo ""
echo "🚀 API Keys Ready:"
echo "   OpenRouter: ${OPENROUTER_API_KEY:0:20}..."
echo "   Gate.io: ${GATE_API_KEY:0:10}..."
echo ""
echo "💡 To make these permanent, add to your ~/.zshrc:"
echo "   echo 'export OPENROUTER_API_KEY=\"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\"' >> ~/.zshrc"
echo "   echo 'export GATE_API_KEY=\"a925edf19f684946726f91625d33d123\"' >> ~/.zshrc"
echo "   echo 'export GATE_API_SECRET=\"b18dcc2cee347aaf1e28407de1a3e8638e6597c3b311cd59cb7d3573bfb3fc05\"' >> ~/.zshrc"
