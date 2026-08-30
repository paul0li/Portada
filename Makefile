.PHONY: install dev test lint fmt migrate preview clean

install:
	uv sync

dev:
	uv run uvicorn app.main:app --reload --port 8000

# PYTHONDONTWRITEBYTECODE: el .pyc guarda el mtime del fuente en SEGUNDOS. Dos
# ediciones del mismo tamano dentro del mismo segundo (un script que cambia algo
# y lo revierte) dejan bytecode obsoleto que Python considera valido. Ver CLAUDE.md.
test:
	PYTHONDONTWRITEBYTECODE=1 uv run pytest

lint:
	uv run ruff check app tests
	uv run ruff format --check app tests

fmt:
	uv run ruff check --fix app tests
	uv run ruff format app tests

migrate:
	uv run python -m app.core.migrations

preview:
	uv run python -m app.domains.composition.preview $(ARGS)

clean:
	rm -rf .pytest_cache .ruff_cache htmlcov .coverage
	find . -name __pycache__ -type d -prune -exec rm -rf {} +
