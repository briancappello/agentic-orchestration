.PHONY: help build test lint

help: ## Show the targets
	@grep -E '^[a-z-]+:.*## ' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  %-8s %s\n", $$1, $$2}'

build: ## Build bin/acp-broker
	CGO_ENABLED=0 go build -o bin/acp-broker ./cmd/acp-broker

test: ## Run the tests with the race detector (RUN=TestFoo to pick tests)
	go test -race -count=1 $(if $(RUN),-run '$(RUN)') ./...

lint: ## Lint for Linux, macOS and Windows
	@for os in linux darwin windows; do echo "golangci-lint: GOOS=$$os"; GOOS=$$os golangci-lint run ./... || exit 1; done
