# Verification: latest-dependency-versions

Run on 2026-10-31. smolvm 1.32.4 was installed in isolation under `/tmp/opencode/smolvm-latest`, with its own home directory, so the host's smolvm 1.26.1 and its machines were not touched. The fork commits are the rebased ones merged by ortusnova/sortie#16 (`dd8f5df2`); this repository's merged with #21 (`126e07c8`), and #22 (`95af461a`) pins the fork. After the merge, p1's stage 0 runs the new Sortie on smolvm 1.32.4.

## Sortie fork

| Task | Commit | Verified by |
|---|---|---|
| 1.1 | `f50ddff6` | Version-check tests: `1.26.1` refused naming `1.26.1` and `1.32.4`, `1.32.4` and `2.0.0` accepted, an unparsable version refused; the same at startup and on reload. |
| 1.2 | `43c1aac7`, `05e3a2da` | The full `SORTIE_SMOLVM_TEST=1` suite on 1.32.4: all 11 integration tests pass with `-race`, no machine left behind. The measured CLI facts match 1.26.1 except the stopped-VM error text (still recognized) and a new `:set-header=` option on `--credential`. New `ls --json` fixture from 1.32.4. |
| 1.3 | `d9758385`, `283cf911` | The `TestLatest_*` tests skip without `SORTIE_LATEST_TEST`. With it, the host's 1.26.1 fails with `smolvm on PATH is not the latest release: ours 1.26.1, latest 1.32.4`, and 1.32.4 passes. |
| 1.4 | `2a6ce17c`, `125c2ce5` | Every Go module at its latest release; `prometheus/common` 0.72.0 → 0.73.1 after `github.com/pandatix/go-abnf` (MIT, pure Go) was approved. `make check-latest` passes fully. |
| 1.2 (header) | `a72543ac`, `db43f2ed` | Argv and config tests for the `:set-header=` binding, 15 refused names. Gated `TestIntegration_CredentialHeaderIsSetOnTheHost` on 1.32.4 against httpbin.org: the header arrives with the real value even when the guest sends its own, and is absent on other hosts. Removing it from the VM spec makes the test fail. |
| 1.6 | `e89ca8e6`, `ff7129d8` | Every machine command runs with `--error-format json`. `TestConnectionFailed_EachCodeThroughTheLaunch` covers all 11 codes; `TestConnectionFailed` has 26 cases, including near-misses (an extra key, a non-string code, trailing text). Gated `TestIntegration_ConnectionFailedOnRealExits` on 1.32.4: missing VM, stopped VM, a VM stopped under a running command, an unset secret, and guest output that only looks like smolvm's. |
| 1.5 | `fc157b13`, `56ffacaa` | `make lint-docs`: 0 errors. No smolvm `1.26` requirement left in the fork's docs. |

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

## Leftovers of a missing machine

Fork commit `e8f5be7f`: a stop, delete or exec on a machine that no longer exists makes smolvm 1.32.4 leave an empty directory or lock under its cache. Release, Remove, Sweep and Prepare remove exactly that machine's leftovers, only when empty. Gated `TestIntegration_MissingVMLeavesNoResidue` passes, and the cache listing was identical before and after the full gated suite.
