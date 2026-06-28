# AI Sharpness Monitor — developer shortcuts

.PHONY: install run run-api run-bot run-dashboard test lint clean clean-db

install:
	pip install -r requirements.txt

run:
	python run.py

run-api:
	python run.py --api

run-bot:
	python run.py --bot

run-dashboard:
	streamlit run dashboard/app.py

test:
	pytest tests/ -v

lint:
	ruff check monitor/ api/ bot/ dashboard/ tests/

format:
	ruff format monitor/ api/ bot/ dashboard/ tests/

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null; true
	rm -rf .pytest_cache .mypy_cache

clean-db:
	@echo "WARNING: This will delete all probe history!"
	@read -p "Are you sure? [y/N] " ans && [ $${ans:-N} = y ] && rm -rf data/ || echo "Cancelled."
