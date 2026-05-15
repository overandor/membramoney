#!/bin/bash
# Export Gate.io API keys as environment variables

export GATE_API_KEY="a925edf19f684946726f91625d33d123"
export GATE_API_SECRET="b18dcc2cee347aaf1e28407de1a3e8638e6597c3b311cd59cb7d3573bfb3fc05"

# Also add to current shell session
echo "✅ Gate.io API keys exported to environment"
echo ""
echo "To use in your current terminal:"
echo "  source /Users/alep/Downloads/export_gate_keys.sh"
echo ""
echo "Or add to your ~/.zshrc:"
echo "  echo 'export GATE_API_KEY=\"a925edf19f684946726f91625d33d123\"' >> ~/.zshrc"
echo "  echo 'export GATE_API_SECRET=\"b18dcc2cee347aaf1e28407de1a3e8638e6597c3b311cd59cb7d3573bfb3fc05\"' >> ~/.zshrc"
