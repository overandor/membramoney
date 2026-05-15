#!/usr/bin/env bash
set -euo pipefail

if [ ! -f .env.local ]; then
  echo "Missing .env.local file."
  exit 1
fi

source .env.local

case "${PROVIDER:-openrouter}" in
  openrouter)
    export OPENAI_API_BASE="${OPENROUTER_API_BASE}"
    export OPENAI_API_KEY="${OPENROUTER_API_KEY}"
    MODEL="${OPENROUTER_MODEL}"
    ;;
  groq)
    export OPENAI_API_BASE="${GROQ_API_BASE}"
    export OPENAI_API_KEY="${GROQ_API_KEY}"
    MODEL="${GROQ_MODEL}"
    ;;
  *)
    echo "Unsupported PROVIDER='${PROVIDER}'. Use 'openrouter' or 'groq'."
    exit 1
    ;;
esac

echo "Using provider: ${PROVIDER}"
echo "Using model: ${MODEL}"

aider --model "${MODEL}" --env-file .env.local aider_prompt.md
