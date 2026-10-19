# Build, test, and lint every component of this repository.
# Each component also has its own targets in its directory.

.PHONY: help test lint

help: ## Show the targets
	@grep -E '^[a-z-]+:.*## ' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  %-14s %s\n", $$1, $$2}'

test: ## Run every component's tests

lint: ## Lint every component
