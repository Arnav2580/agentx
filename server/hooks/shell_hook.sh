#!/bin/bash
# Juror universal shell hook.
# Source from ~/.bashrc or ~/.zshrc:
#   source ~/.juror/hooks/shell_hook.sh

JUROR_URL="${JUROR_URL:-http://localhost:8000}"
JUROR_LOG="$HOME/.juror/activity.log"
JUROR_MIN_RISK_CMD="npm install|pip install|pip3 install|yarn add|pnpm add|rm -rf|curl.*|wget.*|sudo|chmod|eval|exec|dd if"
_JUROR_LAST_CMD=""
_JUROR_INSIDE_CHECK=""

_juror_log() {
  mkdir -p "$(dirname "$JUROR_LOG")"
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" >> "$JUROR_LOG" 2>/dev/null
}

_juror_json_escape() {
  python3 -c 'import json,sys; print(json.dumps(sys.argv[1]))' "$1"
}

_juror_check() {
  local cmd="$1"

  if [ -z "$cmd" ] || [ "$_JUROR_INSIDE_CHECK" = "1" ]; then
    return 0
  fi

  if ! echo "$cmd" | grep -qiE "$JUROR_MIN_RISK_CMD"; then
    return 0
  fi

  if ! curl -sf "$JUROR_URL/health" > /dev/null 2>&1; then
    return 0
  fi

  _JUROR_INSIDE_CHECK="1"
  local payload result verdict reasons suggestion
  payload="{\"command\": $(_juror_json_escape "$cmd"), \"source\": \"shell\"}"
  result=$(curl -sf -X POST "$JUROR_URL/check-command" \
    -H "Content-Type: application/json" \
    -d "$payload" 2>/dev/null)
  _JUROR_INSIDE_CHECK=""

  if [ -z "$result" ]; then
    return 0
  fi

  verdict=$(echo "$result" | python3 -c "import json,sys; print(json.load(sys.stdin).get('verdict','SAFE'))" 2>/dev/null)
  if [ "$verdict" = "SAFE" ]; then
    return 0
  fi

  reasons=$(echo "$result" | python3 -c "import json,sys; d=json.load(sys.stdin); [print('  -', r) for r in d.get('reasons', [])[:3]]" 2>/dev/null)
  suggestion=$(echo "$result" | python3 -c "import json,sys; print(json.load(sys.stdin).get('suggestion',''))" 2>/dev/null)

  echo ""
  if [ "$verdict" = "BLOCK" ]; then
    echo "JUROR BLOCKED: $cmd"
  else
    echo "JUROR WARNING: $cmd"
  fi
  echo "$reasons"
  if [ -n "$suggestion" ]; then
    echo "  -> Safer: $suggestion"
  fi
  echo ""

  _juror_log "$verdict shell cmd=$cmd"
  return 0
}

_juror_capture_and_check() {
  [ "$_JUROR_INSIDE_CHECK" = "1" ] && return
  local cmd
  cmd=$(history 1 | sed 's/^[[:space:]]*[0-9]*[[:space:]]*//')
  [ -z "$cmd" ] && return
  [ "$cmd" = "$_JUROR_LAST_CMD" ] && return
  _JUROR_LAST_CMD="$cmd"
  _juror_check "$cmd"
}

if [ -n "$ZSH_VERSION" ]; then
  autoload -Uz add-zsh-hook
  _juror_zsh_preexec() { _juror_check "$1"; }
  add-zsh-hook preexec _juror_zsh_preexec
elif [ -n "$BASH_VERSION" ]; then
  trap '_juror_capture_and_check' DEBUG
fi
