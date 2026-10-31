# platform/dependency-versions Specification

## Purpose
Keeps every third-party dependency of the platform on its latest stable release, and makes falling behind visible as a failing test.

## Requirements

### Requirement: Dependencies track the latest stable release
Every third-party dependency that a component pins or requires SHALL be at the latest stable release its project publishes. This covers the Go modules of every Go module we own, the smolvm release on the Sortie host, and every artifact a smol-builder layer downloads: its base image, its tools, and its toolchains. A pin SHALL still fix its exact version and checksum, so a download is checked before use.

"Latest stable" SHALL mean the newest release that its project does not mark as a prerelease, draft, release candidate, or beta. For Node it SHALL mean the newest LTS release.

#### Scenario: A new release ships
- **WHEN** smolvm publishes `1.33.0` while the host runs `1.32.4`
- **THEN** the version test for smolvm fails

### Requirement: Version tests fetch the release lists
Each component SHALL have version tests that fetch the latest stable release of each of its dependencies from the project's own release list at test time, and compare it with the version the component uses. A test SHALL fail when the component is behind, with a message that names the dependency, the version in use, and the latest stable version. A test SHALL also fail when the release list cannot be fetched or parsed, naming the source.

The sources SHALL be:

- GitHub releases, skipping prereleases and drafts, for smolvm, opencode, and uv;
- rustup's stable release channel (`static.rust-lang.org/rustup/release-stable.toml`) for rustup;
- `go.dev/dl` for Go, stable releases only;
- `nodejs.org/dist/index.json` for Node, LTS releases only;
- the Rust stable release channel for Rust;
- python.org's release list for CPython, final releases only;
- the registry's current digest of the tag, for a base image pinned by digest;
- `go list -m -u all` for Go modules.

When `GH_TOKEN` is set, requests to GitHub SHALL send it.

#### Scenario: A layer falls behind
- **WHEN** the `node` layer pins `24.21.0` and the newest Node LTS release is `24.22.0`
- **THEN** the version test fails with a message naming `node`, `24.21.0`, and `24.22.0`

#### Scenario: Source unreachable
- **WHEN** the version tests run without network access
- **THEN** each test fails with a message naming the source it could not fetch

### Requirement: Version tests run only when enabled
The version tests SHALL run only when their component's variable is `1`: `SORTIE_LATEST_TEST` in the Sortie fork, `SMOL_BUILDER_LATEST_TEST` in smol-builder, and `ACP_BROKER_LATEST_TEST` in acp-broker. Without it they SHALL skip. Each component SHALL have a `check-latest` make target that runs them with the variable set.

#### Scenario: Ordinary test run
- **WHEN** `make test` runs without the variable
- **THEN** the version tests skip and make no network request
