.PHONY: help build test lint

help: ## Show the targets
	@grep -E '^[a-z-]+:.*## ' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  %-8s %s\n", $$1, $$2}'

build: ## Build bin/acp-broker
	CGO_ENABLED=0 go build -o bin/acp-broker ./cmd/acp-broker

test: ## Run the tests with the race detector (RUN=TestFoo to pick tests)
	go test -race -count=1 $(if $(RUN),-run '$(RUN)') ./...

lint: ## Lint for Linux, macOS and Windows
	@for os in linux darwin windows; do echo "golangci-lint: GOOS=$$os"; GOOS=$$os golangci-lint run ./... || exit 1; done

NAME := acp-broker

# Release archives. The version is the module's latest tag, such as
# NAME/v0.1.0, or the commit when there is none.
PLATFORMS ?= linux/amd64 linux/arm64 darwin/amd64 darwin/arm64
VERSION ?= $(shell git describe --tags --match '$(NAME)/v*' --always --dirty 2>/dev/null | sed 's#^$(NAME)/##')

.PHONY: dist
dist: ## Build a release archive per platform, with LICENSE and README, and SHA256SUMS, into dist/
	rm -rf dist && mkdir -p dist
	@set -e; for p in $(PLATFORMS); do \
	  os=$${p%/*}; arch=$${p#*/}; dir=$(NAME)_$(VERSION)_$${os}_$${arch}; \
	  mkdir -p dist/$$dir; \
	  CGO_ENABLED=0 GOOS=$$os GOARCH=$$arch go build -trimpath -ldflags='-s -w' -o dist/$$dir/$(NAME) ./cmd/$(NAME); \
	  cp LICENSE README.md dist/$$dir/; \
	  tar -C dist -czf dist/$$dir.tar.gz $$dir; rm -r dist/$$dir; \
	  echo "dist/$$dir.tar.gz"; \
	done
	cd dist && sha256sum *.tar.gz > SHA256SUMS
