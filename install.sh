#!/bin/bash
# AI Hallucination Juror - One-command installer
# Usage: curl -fsSL https://raw.githubusercontent.com/Arnav2580/agentx/main/install.sh | bash

set -e

REPO="https://github.com/Arnav2580/agentx"
INSTALL_DIR="$HOME/.juror-app"
GREEN='\033[0;32m'
CYAN='\033[0;36m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo ""
echo -e "${GREEN}============================================${NC}"
echo -e "${GREEN}   AI HALLUCINATION JUROR${NC}"
echo -e "${GREEN}   Multi-agent verification system${NC}"
echo -e "${GREEN}============================================${NC}"
echo ""

echo -e "${CYAN}[1/6] Checking prerequisites...${NC}"

if ! command -v python3 >/dev/null 2>&1; then
  echo -e "${RED}ERROR: Python 3 required. Install from https://python.org${NC}"
  exit 1
fi
if ! command -v git >/dev/null 2>&1; then
  echo -e "${RED}ERROR: Git required. Install from https://git-scm.com${NC}"
  exit 1
fi

PYTHON="$(command -v python3)"
echo -e "     Python: $($PYTHON --version)"

echo -e "${CYAN}[2/6] Downloading Juror...${NC}"

if [ -d "$INSTALL_DIR/.git" ]; then
  echo "     Updating existing install..."
  git -C "$INSTALL_DIR" pull --quiet origin main
elif [ -d "$INSTALL_DIR" ]; then
  rm -rf "$INSTALL_DIR"
  git clone --quiet "$REPO" "$INSTALL_DIR"
else
  git clone --quiet "$REPO" "$INSTALL_DIR"
fi
echo -e "     OK Downloaded to $INSTALL_DIR"

echo -e "${CYAN}[3/6] Installing Python dependencies...${NC}"
cd "$INSTALL_DIR"
"$PYTHON" -m pip install -r requirements.txt -q --disable-pip-version-check
echo -e "     OK Dependencies installed"

echo -e "${CYAN}[4/6] Configuring API key...${NC}"

ENV_DIR="$HOME/.juror"
ENV_FILE="$ENV_DIR/.env"
mkdir -p "$ENV_DIR"

if [ -f "$ENV_FILE" ] && grep -q "^GEMINI_API_KEY=" "$ENV_FILE" 2>/dev/null; then
  echo -e "     OK Configuration already exists"
else
  echo ""
  echo -e "     Get a free key at: ${CYAN}https://aistudio.google.com/apikey${NC}"
  printf "     Enter Gemini API key: "
  read -r -s API_KEY
  echo ""
  cat > "$ENV_FILE" <<EOF
GEMINI_API_KEY=$API_KEY
MODEL=gemini-2.5-flash
SERVER_PORT=8000
EOF
  echo -e "     OK Saved to ~/.juror/.env"
fi

echo -e "${CYAN}[5/6] Installing juror command...${NC}"

BIN_DIR="$HOME/.local/bin"
mkdir -p "$BIN_DIR"

cat > "$BIN_DIR/juror" <<SCRIPT
#!/bin/bash
set -a
[ -f "$ENV_FILE" ] && source "$ENV_FILE"
set +a
cd "$INSTALL_DIR"
exec "$PYTHON" -m terminal.cli "\$@"
SCRIPT

chmod +x "$BIN_DIR/juror"

if [[ ":$PATH:" != *":$BIN_DIR:"* ]]; then
  SHELL_RC="$HOME/.bashrc"
  if [[ "$SHELL" == *"zsh"* ]]; then
    SHELL_RC="$HOME/.zshrc"
  fi
  echo "export PATH=\"\$PATH:$BIN_DIR\"" >> "$SHELL_RC"
  export PATH="$PATH:$BIN_DIR"
fi
echo -e "     OK juror command installed"

echo -e "${CYAN}[6/6] Installing VS Code extension...${NC}"

VSIX="$INSTALL_DIR/vscode-extension/ai-hallucination-juror-1.0.0.vsix"
CODE_CMD="$(command -v code || command -v code-insiders || echo "")"

if [ -n "$CODE_CMD" ] && [ -f "$VSIX" ]; then
  "$CODE_CMD" --install-extension "$VSIX" --force >/dev/null 2>&1
  echo -e "     OK VS Code extension installed"
else
  echo -e "     ${YELLOW}WARN VS Code not found - install manually:${NC}"
  echo -e "        code --install-extension $VSIX"
fi

CHROME_DIR="$INSTALL_DIR/chrome-extension"

echo ""
echo -e "${GREEN}============================================${NC}"
echo -e "${GREEN}   INSTALLATION COMPLETE${NC}"
echo -e "${GREEN}============================================${NC}"
echo ""
echo -e "  ${CYAN}Start server:${NC}   juror start"
echo -e "  ${CYAN}Dashboard:${NC}      http://localhost:8000"
echo -e "  ${CYAN}Terminal wrap:${NC}  juror run claude \"your prompt\""
echo -e "  ${CYAN}Shortcut:${NC}       Ctrl+Shift+J on any AI site"
echo -e "  ${CYAN}Uninstall:${NC}      juror uninstall --yes"
echo ""
echo -e "  ${YELLOW}Chrome extension (one-time, 30 seconds):${NC}"
echo -e "  1. Open ${CYAN}chrome://extensions${NC}"
echo -e "  2. Enable Developer Mode (top-right toggle)"
echo -e "  3. Click Load Unpacked -> select:"
echo -e "     ${CYAN}$CHROME_DIR${NC}"
echo ""
echo -e "  ${YELLOW}Claude Code MCP (optional):${NC}"
echo -e "  ${CYAN}claude mcp add juror http://localhost:8000/mcp${NC}"
echo ""

printf "  Start the server now? [Y/n]: "
read -r REPLY
if [[ "$REPLY" =~ ^[Yy]$|^$ ]]; then
  echo ""
  echo -e "  ${GREEN}Starting AI Hallucination Juror...${NC}"
  echo -e "  ${CYAN}Dashboard opening at http://localhost:8000${NC}"
  sleep 0.5
  (sleep 1.5 && python3 -c "import webbrowser; webbrowser.open('http://localhost:8000')" >/dev/null 2>&1 &)
  juror start
fi
