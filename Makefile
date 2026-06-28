# AI Sharpness Monitor — developer shortcuts

.PHONY: install run run-api run-bot dashboard test lint format clean clean-db

install:
	pip install -r requirements.txt

run:
	python run.py

run-api:
	python run.py --api

run-bot:
	python run.py --bot

dashboard:
	@echo "Opening dashboard..."
	@python -c "import webbrowser; webbrowser.open('http://localhost:8000/dashboard')"
	@echo "Dashboard: http://localhost:8000/dashboard"
	@echo "(API must be running: make run)"

test:
	pytest tests/ -v

lint:
	ruff check monitor/ api/ bot/ tests/

format:
	ruff format monitor/ api/ bot/ tests/

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null; true
	rm -rf .pytest_cache .mypy_cache

clean-db:
	@echo "WARNING: This will delete ALL probe history and feedback!"
	@read -p "Are you sure? [y/N] " ans && [ $${ans:-N} = y ] && rm -rf data/ || echo "Cancelled."
