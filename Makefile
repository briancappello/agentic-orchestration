# Build, test, and lint every component of this repository. Each component
# also has its own Makefile, with build and release targets.

GO_MODULES := acp-broker smol-builder
COMPONENTS := workbench $(GO_MODULES)

.PHONY: help test lint licenses specs dist

help: ## Show the targets
	@grep -E '^[a-z-]+:.*## ' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  %-10s %s\n", $$1, $$2}'

test: ## Run every component's tests
	@set -e; for c in $(COMPONENTS); do echo "== $$c: test"; $(MAKE) -s -C $$c test; done

lint: licenses specs ## Lint every component, check the license copies, and validate the specs
	@set -e; for c in $(COMPONENTS); do echo "== $$c: lint"; $(MAKE) -s -C $$c lint; done

licenses: ## Check that each component ships the repository's LICENSE unchanged
	@set -e; for c in $(COMPONENTS); do cmp -s LICENSE $$c/LICENSE || { echo "$$c/LICENSE differs from LICENSE"; exit 1; }; done; echo "licenses: ok"

specs: ## Validate the OpenSpec store in specs/
	@cd specs && openspec validate --all --no-interactive > /dev/null && echo "specs: ok"

dist: ## Build the release artifacts: Go archives and the workbench wheel
	@set -e; for m in $(GO_MODULES); do $(MAKE) -s -C $$m dist; done; $(MAKE) -s -C workbench wheel
