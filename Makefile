.PHONY: dev dev-backend dev-frontend test test-backend test-frontend lint

dev:
	$(MAKE) --jobs=2 dev-backend dev-frontend

dev-backend:
	uv run uvicorn board.main:app --reload --app-dir src

dev-frontend:
	npm --prefix src/frontend run dev

test:
	$(MAKE) test-backend test-frontend

test-backend:
	uv run pytest

test-frontend:
	npm --prefix src/frontend test

lint:
	uv run ruff check src/board
	uv run ruff format --check src/board
	npm --prefix src/frontend run check
