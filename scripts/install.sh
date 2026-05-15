#!/bin/bash
set -e

echo "Installing AI Hallucination Juror..."

mkdir -p ~/.juror

if command -v pip >/dev/null 2>&1; then
  pip install -e .
else
  pip3 install -e .
fi

if [ ! -f .env ]; then
  cp .env.example .env
fi

if [ -z "$GROK_API_KEY" ]; then
  echo ""
  echo "Enter your Grok API key (optional, press Enter to skip):"
  read -r GROK_API_KEY
  if [ -n "$GROK_API_KEY" ]; then
    echo "GROK_API_KEY=$GROK_API_KEY" >> .env
  fi
fi

juror install-service

echo ""
echo "Install complete."
echo "Backend: http://localhost:8000"
echo "MCP:     http://localhost:8000/mcp"
