# AI Sharpness Monitor — developer shortcuts

.PHONY: install run run-api run-bot test lint clean

install:
	pip install -r requirements.txt

run:
	python run.py

run-api:
	python run.py --api

run-bot:
	python run.py --bot

test:
	pytest tests/ -v

lint:
	ruff check monitor/ api/ bot/ tests/
	ruff format --check monitor/ api/ bot/ tests/

format:
	ruff format monitor/ api/ bot/ tests/

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null; true
	rm -rf .pytest_cache .mypy_cache
	# Note: data/ is intentionally NOT cleaned here (contains your SQLite history)

clean-db:
	@echo "WARNING: This will delete all probe history and scores!"
	@read -p "Are you sure? [y/N] " ans && [ $${ans:-N} = y ] && rm -rf data/ || echo "Cancelled."
