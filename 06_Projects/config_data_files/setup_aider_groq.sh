#!/bin/bash
# Setup Aider with Groq API

echo "🚀 Setting up Aider with Groq API..."

# Check if GROQ_API_KEY is set
if [ -z "$GROQ_API_KEY" ]; then
    echo "❌ GROQ_API_KEY not set!"
    echo ""
    echo "Get your API key from: https://console.groq.com/keys"
    echo "Then run: export GROQ_API_KEY='your_key_here'"
    exit 1
fi

echo "✅ GROQ_API_KEY found"

# Create aider config for Groq
cat > .aider.conf.yml << EOF
# Aider with Groq API
openai-api-key: $GROQ_API_KEY
openai-api-base: https://api.groq.com/openai/v1
model: groq/llama-3.3-70b-versatile

# Settings
git-commit: true
dark-mode: true
stream: true
EOF

echo "✅ Configuration created: .aider.conf.yml"
echo ""
echo "🎯 Available Groq Models:"
echo "  - groq/llama-3.3-70b-versatile (recommended)"
echo "  - groq/llama-3.1-8b-instant (fastest)"
echo "  - groq/mixtral-8x7b-32768"
echo "  - groq/gemma-7b-it"
echo ""
echo "🚀 Start aider: aider"
