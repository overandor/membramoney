#!/bin/bash

# Demo run script for autonomous CleanStat agent
# Sets environment variables and runs the agent

# Create demo environment variables
export OLLAMA_BASE_URL=http://localhost:11434
export OLLAMA_MODEL=llama3.1:8b
export CLEANSTAT_API_URL=http://localhost:8000
export CLEANSTAT_API_KEY=demo_key_not_real
export WORKSPACE_DIR=.

# Check if Ollama is running
if ! curl -s http://localhost:11434/api/tags > /dev/null 2>&1; then
    echo "⚠️  Ollama is not running. Starting with rule-based fallback..."
    echo "   To use Ollama: ollama serve"
fi

# Run the agent
echo "=== Starting Autonomous CleanStat Agent ==="
python main.py
