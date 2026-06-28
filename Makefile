# AI Sharpness Monitor — developer shortcuts

.PHONY: install setup dev run run-api run-bot dashboard check test lint format clean clean-db

# ─── First-time setup ────────────────────────────────────────────────────────

## Full interactive setup: venv + deps + .env config + smoke test
setup:
	@bash setup.sh

## Install deps into current Python env (assumes venv already active)
install:
	pip install -r requirements.txt

# ─── Run ─────────────────────────────────────────────────────────────────────

## Activate venv + start API + bot (one-liner for daily use)
dev:
	@echo "Activating .venv and starting..."
	@( . .venv/bin/activate && python run.py )

## Start API + bot (venv must already be active)
run:
	python run.py

## API only
run-api:
	python run.py --api

## Telegram bot only
run-bot:
	python run.py --bot

# ─── Dashboard ───────────────────────────────────────────────────────────────

## Open dashboard in browser (API must be running)
dashboard:
	@echo "Opening dashboard at http://localhost:8000/dashboard"
	@python -c "import webbrowser; webbrowser.open('http://localhost:8000/dashboard')"

# ─── Health check ────────────────────────────────────────────────────────────

## Quick health check against running API
check:
	@curl -s http://localhost:8000/health | python -m json.tool || echo "API not running — start with: make run"

# ─── Tests & Quality ─────────────────────────────────────────────────────────

test:
	pytest tests/ -v

lint:
	ruff check monitor/ api/ bot/ tests/

format:
	ruff format monitor/ api/ bot/ tests/

# ─── Cleanup ─────────────────────────────────────────────────────────────────

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null; true
	rm -rf .pytest_cache .mypy_cache

clean-db:
	@echo "WARNING: This will delete ALL probe history and feedback!"
	@read -p "Are you sure? [y/N] " ans && [ $${ans:-N} = y ] && rm -rf data/ || echo "Cancelled."

# ─── Help ────────────────────────────────────────────────────────────────────

help:
	@echo ""
	@echo "  AI Sharpness Monitor — available commands"
	@echo ""
	@echo "  First time:"
	@echo "    make setup       Interactive setup (venv + deps + .env + tests)"
	@echo ""
	@echo "  Daily use:"
	@echo "    make dev          Activate venv + start everything"
	@echo "    make run          Start API + bot (venv already active)"
	@echo "    make dashboard    Open http://localhost:8000/dashboard"
	@echo "    make check        Health check against running API"
	@echo ""
	@echo "  Individual:"
	@echo "    make run-api      API only"
	@echo "    make run-bot      Telegram bot only"
	@echo ""
	@echo "  Quality:"
	@echo "    make test         pytest -v"
	@echo "    make lint         ruff check"
	@echo "    make format       ruff format"
	@echo ""
	@echo "  Cleanup:"
	@echo "    make clean        Remove __pycache__ etc."
	@echo "    make clean-db     Delete data/ (with confirmation)"
	@echo ""
