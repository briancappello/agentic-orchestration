GO ?= go
LINTER ?= $(HOME)/go/bin/golangci-lint
BIN ?= bin/smol-builder

export CGO_ENABLED := 0

.PHONY: help
help: ## List targets
	@grep -E '^[a-z-]+:.*## ' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "%-8s %s\n", $$1, $$2}'

.PHONY: build
build: ## Build the static binary into bin/
	$(GO) build -trimpath -o $(BIN) ./cmd/smol-builder

.PHONY: test
test: ## Run unit tests with the race detector (RUN=TestFoo)
	CGO_ENABLED=1 $(GO) test -race -count=1 ./... $(if $(RUN),-run '$(RUN)',)

.PHONY: vet
vet: ## Run go vet
	$(GO) vet ./...

.PHONY: lint
lint: ## Run golangci-lint
	$(LINTER) run ./...
