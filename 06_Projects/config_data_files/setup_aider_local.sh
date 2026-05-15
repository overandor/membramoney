#!/bin/bash
# Setup Aider with Local Ollama Model

echo "🚀 Setting up Aider with Local Ollama..."

# Check if Ollama is installed
if ! command -v ollama &> /dev/null; then
    echo "❌ Ollama not installed!"
    echo "Installing Ollama..."
    curl -fsSL https://ollama.com/install.sh | sh
fi

# Check if Ollama is running
if ! curl -s http://localhost:11434/api/tags &> /dev/null; then
    echo "🔄 Starting Ollama..."
    ollama serve &
    sleep 5
fi

echo "✅ Ollama is running"

# Pull recommended models
echo "📥 Downloading models..."
ollama pull llama3.2:1b
ollama pull qwen2.5:0.5b

echo "✅ Models downloaded"

# Create aider config for local models
cat > .aider.conf.yml << EOF
# Aider with Local Ollama
model: ollama/llama3.2:1b

# Alternative models (uncomment to use):
# model: ollama/qwen2.5:0.5b
# model: ollama/deepseek-coder:1.3b

# Settings
git-commit: true
dark-mode: true
stream: true
cache-prompts: true
EOF

echo "✅ Configuration created: .aider.conf.yml"
echo ""
echo "🎯 Available Local Models:"
echo "  - ollama/llama3.2:1b (fast, good for coding)"
echo "  - ollama/qwen2.5:0.5b (very fast)"
echo "  - ollama/deepseek-coder:1.3b (coding specialist)"
echo ""
echo "🚀 Start aider: aider"
echo ""
echo "💡 To use a different model:"
echo "  aider --model ollama/qwen2.5:0.5b"
