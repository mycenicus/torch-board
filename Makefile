.PHONY: dev dev-backend dev-frontend test lint

dev:
	$(MAKE) --jobs=2 dev-backend dev-frontend

dev-backend:
	uv run uvicorn board.main:app --reload --app-dir src

dev-frontend:
	npm --prefix src/frontend run dev

test:
	uv run pytest

lint:
	uv run ruff check src/board
	uv run ruff format --check src/board
