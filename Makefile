ARGS ?= "Algarve, Portugal" psychologists --limit 100

all: install

install:
	uv sync

run:
	uv run python -m src $(ARGS)

lint:
	uv run flake8 src
	uv run mypy src

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type d -name ".mypy_cache" -exec rm -rf {} +
	find . -type d -name ".pytest_cache" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	rm -rf build dist *.egg-info
	rm -rf .venv

.PHONY: all install run lint clean