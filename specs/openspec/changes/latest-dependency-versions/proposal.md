## Why

We always run the latest stable release of every third-party dependency. Today Sortie refuses every smolvm release except `1.26.x`, while smolvm's latest release is `1.32.4`, and nothing tells us when a dependency falls behind. The smol-builder layers, smolvm, and the Go modules were all pinned on 2026-10-11 and have not moved since.

## What Changes

- **Sortie accepts any smolvm release at or above a minimum version**, instead of exactly `1.26.x`. The minimum is the release the smolvm checks were last run against, initially `1.32.4`. There is no upper bound. **BREAKING** for a host still on smolvm `1.26.x`: Sortie refuses it and names the minimum.
- **Version tests compare each dependency with its latest stable release**, fetched from the project's own release list at test time:
  - smolvm, opencode, and uv: GitHub releases, skipping prereleases and drafts;
  - rustup: its stable release channel;
  - Go: `go.dev/dl`, stable releases only;
  - Node: `nodejs.org/dist/index.json`, the newest LTS release;
  - Rust: the stable release channel;
  - CPython: the newest stable release;
  - the Debian base image: the current digest of its tag;
  - Go modules: `go list -m -u all`, for every Go module we own.
  A test fails, naming the dependency, our version, and the latest one, when we are behind.
- The version tests need the network and change their verdict whenever a project ships a release, so they run only when enabled: `SORTIE_LATEST_TEST=1` in the fork and `SMOL_BUILDER_LATEST_TEST=1` and `ACP_BROKER_LATEST_TEST=1` in this repository, each with a `check-latest` make target. They use `GH_TOKEN` for GitHub when it is set.
- Every pin moves to the latest stable release, so the version tests pass when this change lands.
- smol-builder deletes builder machines that an earlier, interrupted run left behind, such as after a host restart. Each builder machine is labeled with its process ID and the host's boot ID, so a build never deletes the machine of another build that is still running.
- A credential binding's `header` is passed to smolvm, which supports it since 1.32: the header is set on every HTTPS request to the binding's hosts. Sortie used to refuse it because smolvm 1.26 had no such option.
- Sortie recognizes smolvm's own failures, such as a missing or stopped machine, from the stable error codes smolvm prints with `--error-format json`, instead of matching its English error text, which changed between 1.26 and 1.32.
- `dev/stage0/stage0.sh` also accepts smolvm `1.32.4` or later, instead of exactly `1.26.x`.

## Capabilities

### New Capabilities

- `platform/dependency-versions`: the latest-release policy and the version tests that enforce it.

### Modified Capabilities

- `sortie/smolvm-environment`: the supported smolvm version becomes a minimum with no upper bound, and a credential's header is defined precisely.
- `smol-builder/stack-builder`: a build also deletes builder machines that interrupted earlier runs left behind.

## Impact

- Sortie fork: `internal/environment/smolvm` (the version check), a new gated version test, the Go modules, the smolvm guide, the workflow reference, and `CHANGELOG.md`.
- smol-builder: every layer's version and checksum, a gated version test, and its Go modules.
- acp-broker: a gated version test, and its Go modules.
- Operators: upgrade smolvm to `1.32.4` or later, and rebuild packs.
- Not covered by this change: the `go` directive and `toolchain` lines of each `go.mod`, and the workbench's Python and npm dependencies.
