#!/usr/bin/env bash
# =============================================================================
# AI Sharpness Monitor — one-shot local setup
# Usage: bash setup.sh
# =============================================================================
set -euo pipefail

RED='\033[0;31m'; YELLOW='\033[1;33m'; GREEN='\033[0;32m'
CYAN='\033[0;36m'; BOLD='\033[1m'; RESET='\033[0m'

log()  { echo -e "${CYAN}▶ $*${RESET}"; }
ok()   { echo -e "${GREEN}✓ $*${RESET}"; }
warn() { echo -e "${YELLOW}⚠ $*${RESET}"; }
err()  { echo -e "${RED}✗ $*${RESET}"; exit 1; }

echo -e ""
echo -e "${BOLD}╔══════════════════════════════════════════╗${RESET}"
echo -e "${BOLD}║      AI Sharpness Monitor — Setup        ║${RESET}"
echo -e "${BOLD}╚══════════════════════════════════════════╝${RESET}"
echo -e ""

# ─── 1. Python version check ────────────────────────────────────────────────
log "Checking Python version..."
PY=$(python3 --version 2>&1 | awk '{print $2}')
PY_MAJOR=$(echo "$PY" | cut -d. -f1)
PY_MINOR=$(echo "$PY" | cut -d. -f2)
if [[ "$PY_MAJOR" -lt 3 || ( "$PY_MAJOR" -eq 3 && "$PY_MINOR" -lt 11 ) ]]; then
  err "Python 3.11+ required (found $PY). Install it from https://python.org"
fi
ok "Python $PY"

# ─── 2. Virtual environment ──────────────────────────────────────────────────
if [[ ! -d .venv ]]; then
  log "Creating virtual environment (.venv)..."
  python3 -m venv .venv
  ok "Virtual environment created"
else
  ok "Virtual environment already exists (.venv)"
fi

# shellcheck disable=SC1091
source .venv/bin/activate

# ─── 3. Pip dependencies ────────────────────────────────────────────────────
log "Installing dependencies..."
pip install --upgrade pip --quiet
pip install -r requirements.txt --quiet
ok "Dependencies installed"

# ─── 4. .env setup ──────────────────────────────────────────────────────────
if [[ ! -f .env ]]; then
  log "Creating .env from .env.example..."
  cp .env.example .env
else
  ok ".env already exists — skipping"
fi

# ─── 5. Collect required keys interactively ─────────────────────────────────
echo -e ""
echo -e "${BOLD}── API Keys ──────────────────────────────────────${RESET}"
echo -e "Cerebras is FREE: https://cloud.cerebras.ai (no credit card)"
echo -e ""

CURRENT_CEREBRAS=$(grep -E '^CEREBRAS_API_KEY=' .env | cut -d= -f2- | tr -d '"' | xargs)
if [[ -z "$CURRENT_CEREBRAS" || "$CURRENT_CEREBRAS" == "csk-changeme" ]]; then
  read -rp "  Cerebras API key (csk-...): " CEREBRAS_KEY
  if [[ -n "$CEREBRAS_KEY" ]]; then
    # cross-platform sed
    if sed --version 2>&1 | grep -q GNU; then
      sed -i "s|^CEREBRAS_API_KEY=.*|CEREBRAS_API_KEY=$CEREBRAS_KEY|" .env
    else
      sed -i '' "s|^CEREBRAS_API_KEY=.*|CEREBRAS_API_KEY=$CEREBRAS_KEY|" .env
    fi
    ok "Cerebras key saved"
  else
    warn "No Cerebras key entered — probes will fail until you set it in .env"
  fi
else
  ok "Cerebras key already configured"
fi

echo -e ""
CURRENT_TG=$(grep -E '^TELEGRAM_BOT_TOKEN=' .env | cut -d= -f2- | tr -d '"' | xargs)
if [[ -z "$CURRENT_TG" || "$CURRENT_TG" == "" ]]; then
  read -rp "  Telegram Bot Token (optional, press Enter to skip): " TG_TOKEN
  if [[ -n "$TG_TOKEN" ]]; then
    if sed --version 2>&1 | grep -q GNU; then
      sed -i "s|^TELEGRAM_BOT_TOKEN=.*|TELEGRAM_BOT_TOKEN=$TG_TOKEN|" .env
    else
      sed -i '' "s|^TELEGRAM_BOT_TOKEN=.*|TELEGRAM_BOT_TOKEN=$TG_TOKEN|" .env
    fi
    ok "Telegram token saved"
  else
    warn "Telegram bot disabled — you can add it later in .env"
  fi
else
  ok "Telegram token already configured"
fi

# ─── 6. Create data/ directory ───────────────────────────────────────────────
mkdir -p data
ok "data/ directory ready (SQLite + feedback will be stored here)"

# ─── 7. Quick smoke test ─────────────────────────────────────────────────────
echo -e ""
log "Running smoke tests..."
python -m pytest tests/ -q --tb=short 2>&1 | tail -5 || warn "Some tests failed — check output above"

# ─── 8. Done ─────────────────────────────────────────────────────────────────
echo -e ""
echo -e "${BOLD}${GREEN}╔══════════════════════════════════════════╗"
echo -e "║           Setup complete! ✓              ║"
echo -e "╚══════════════════════════════════════════╝${RESET}"
echo -e ""
echo -e "  ${BOLD}Start everything:${RESET}"
echo -e "    source .venv/bin/activate && make run"
echo -e ""
echo -e "  ${BOLD}Or one-liner (auto-activates venv):${RESET}"
echo -e "    make dev"
echo -e ""
echo -e "  ${BOLD}Open dashboard (once API is running):${RESET}"
echo -e "    make dashboard  →  http://localhost:8000/dashboard"
echo -e ""
echo -e "  ${BOLD}Docs:${RESET}  http://localhost:8000/docs"
echo -e ""
