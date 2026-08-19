ARGS ?= "Algarve, Portugal" psychologists --limit 100

all: install

install:
	uv sync

run:
	uv run python -m src $(ARGS)

test:
	uv run python -m unittest discover -v

lint:
	uv run flake8 src tests
	uv run mypy src

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type d -name ".mypy_cache" -exec rm -rf {} +
	find . -type d -name ".pytest_cache" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	rm -rf build dist *.egg-info
	rm -rf .venv

.PHONY: all install run test lint clean