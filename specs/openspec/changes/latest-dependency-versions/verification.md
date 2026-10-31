# Verification: latest-dependency-versions

Run on 2026-10-31. smolvm 1.32.4 was installed in isolation under `/tmp/opencode/smolvm-latest`, with its own home directory, so the host's smolvm 1.26.1 and its machines were not touched. Commits are on branch `feat/latest-dependency-checks` in the Sortie fork and in this repository.

## Sortie fork

| Task | Commit | Verified by |
|---|---|---|
| 1.1 | `8ae08a7b` | Version-check tests: `1.26.1` refused naming `1.26.1` and `1.32.4`, `1.32.4` and `2.0.0` accepted, an unparsable version refused; the same at startup and on reload. |
| 1.2 | `36b3466c`, `8de27cde` | The full `SORTIE_SMOLVM_TEST=1` suite on 1.32.4: all 11 integration tests pass with `-race`, no machine left behind. The measured CLI facts match 1.26.1 except the stopped-VM error text (still recognized) and a new `:set-header=` option on `--credential`. New `ls --json` fixture from 1.32.4. |
| 1.3 | `047ad335`, `41708c3d` | The `TestLatest_*` tests skip without `SORTIE_LATEST_TEST`. With it, the host's 1.26.1 fails with `smolvm on PATH is not the latest release: ours 1.26.1, latest 1.32.4`, and 1.32.4 passes. |
| 1.4 | `cdc387e0` (partial) | Every Go module moved except `github.com/prometheus/common` (0.72.0; latest 0.73.1), held because 0.73.1 adds the dependency `github.com/pandatix/go-abnf`, which needs approval. |
| 1.5 | `a979288e` | `make lint-docs`: 0 errors. No smolvm `1.26` requirement left in the fork's docs. |

## smol-builder, acp-broker, repository

| Task | Commit | Verified by |
|---|---|---|
| 2.1 | `68f4667e` | The `TestLatest*` tests skip without `SMOL_BUILDER_LATEST_TEST`. With it, before 2.2, all 8 layer pins failed, each naming the dependency, our version and the latest; with no network each failure names its source. |
| 2.2 | `b956a671` | `make check-latest`, `make test`, `make lint` pass. `SMOL_BUILDER_SMOLVM_TEST=1` passes on 1.32.4. A pack with `["go","node","python","rust"]` ran git, cc, jq, rg, socat and opencode, and compiled or ran a Go, Node, Python, Rust and C program offline, with `SORTIE_STACK_LAYERS=base+go+node+python+rust`. |
| 2.3 | `af30d093` | Fake-CLI tests for a machine from another boot, a dead process, a reused PID (all deleted), a live build, an unlabeled and an old-style machine (all kept). Gated `TestIntegrationSweepsKilledBuild`: a build is SIGKILLed after its machine exists; the next build deletes that machine and its temporary directories, and succeeds. |
| 3.1 | `ef220121` | `make check-latest`, `make test`, `make lint` in acp-broker. |
| 4.1 | `034ce53e` | The root `make check-latest` runs acp-broker's and smol-builder's. |
| 4.2 | `34cce2f3` | `dev/stage0/test-smolvm-version.sh`: accepts 1.32.4, 1.32.10, 1.33.0, 2.0.0; refuses 1.32.3, 1.26.1, 1.4.99, `1.33.0-rc1`, unparsable output. |

Versions moved in the layers: Debian `trixie-slim` to its current digest, opencode 2.2.1 → 2.2.5, Go 1.27.2 → 1.27.3, Node 24.21.0 → 26.13.0 (newest LTS), uv 0.13.0 → 0.13.6, CPython 3.14.6 → 3.15.2, rustup 1.29.1 → 1.29.2, Rust 1.99.0 → 1.99.1. Each checksum was computed from a fresh download and matches the project's published value.
