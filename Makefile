.PHONY: dev test lint

dev:
	uv run uvicorn board.main:app --reload --app-dir src

test:
	uv run pytest

lint:
	uv run ruff check .
