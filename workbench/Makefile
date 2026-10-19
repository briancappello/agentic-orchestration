.PHONY: help test lint frontend wheel

help: ## Show the targets
	@grep -E '^[a-z-]+:.*## ' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  %-9s %s\n", $$1, $$2}'

test: ## Run the backend and frontend tests
	uv run pytest -q
	cd frontend && npx vitest run

lint: ## Type-check the frontend
	cd frontend && npm run check

frontend: ## Build the frontend into frontend/dist
	cd frontend && npm ci --silent && npx vite build --logLevel warn

wheel: frontend ## Build the wheel, with the frontend inside, into dist/
	uv build --wheel
