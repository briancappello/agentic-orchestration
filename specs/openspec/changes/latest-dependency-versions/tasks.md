## 1. Sortie fork

- [ ] 1.1 Replace the exact `1.26.x` smolvm version check with a minimum of `1.32.4` and no upper bound; verify with version-check tests for an older, an equal, a newer, and an unparsable version, at startup and on reload.
- [ ] 1.2 Re-run every smolvm check Sortie relies on against smolvm `1.32.4` (the `SORTIE_SMOLVM_TEST=1` suite, and the measured CLI facts: exec output with and without `--stream`, credential egress, credential value source, the pre-start error texts, the name limit, `machine ls --json`, the credential header option) and fix every difference; verify the full gated suite passes on `1.32.4`.
- [ ] 1.3 Add the `SORTIE_LATEST_TEST=1` version tests (installed smolvm against its latest GitHub release, Go modules against `go list -m -u all`) and a `check-latest` make target; verify they skip without the variable, and fail naming the dependency when one is behind.
- [ ] 1.4 Update every Go module to its latest release; verify `make test`, `make lint`, and `make check-latest`.
- [ ] 1.5 Update the smolvm guide, the workflow reference, and `CHANGELOG.md`; verify `make lint-docs`.

## 2. smol-builder

- [ ] 2.1 Add the `SMOL_BUILDER_LATEST_TEST=1` version tests for every layer pin (Debian digest, opencode, Go, Node LTS, uv, CPython, rustup, Rust) and the Go modules, and a `check-latest` make target; verify they skip without the variable and name the dependency when one is behind.
- [ ] 2.2 Move every layer pin to the latest stable release with its new checksum, and update the Go modules; verify `make check-latest`, `make test`, `make lint`, and the `SMOL_BUILDER_SMOLVM_TEST=1` build test with smolvm `1.32.4`, including every toolchain running in a machine created from a pack with all layers.

- [ ] 2.3 Label each builder machine with the build's process ID and the host's boot ID, and delete left-behind builder machines before creating one; verify with fake-CLI tests (a machine from another boot, a machine whose process is dead, a live build's machine kept, an unlabeled machine kept) and a gated test that kills a build after its builder machine exists and checks the next build removes it.

## 3. acp-broker

- [ ] 3.1 Add the `ACP_BROKER_LATEST_TEST=1` Go module version test and a `check-latest` make target, and update its Go modules; verify `make check-latest`, `make test`, and `make lint`.

## 4. Repository

- [ ] 4.1 Add a root `check-latest` target that runs every component's; verify it runs them all.
- [ ] 4.2 Make `dev/stage0/stage0.sh` accept smolvm `1.32.4` or later; verify it accepts `1.32.4` and a newer version, and refuses `1.26.1`.
