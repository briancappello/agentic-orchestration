# smol-builder

`smol-builder` turns a project's development stack into a smolvm pack. A machine created from the pack has every toolchain the project's agents need.

A project declares its stack in `smol-builder.toml` at the root of its repository. The stack is a shared base, plus language layers from a pinned library, plus one optional layer of the project's own. `smol-builder` builds that chain with podman or docker, then packs the image with smolvm.

It is one static Go binary (no CGo). The layer library is embedded in it.

## Requirements

- podman or docker. podman is used when both are installed.
- smolvm 1.26.x, on a host where it can run machines (KVM on Linux).
- Go 1.26.1 or later, to build `smol-builder` itself.

`smol-builder` fails with an error naming the missing program when it cannot find a container engine or `smolvm` on `PATH`.

## Install

```sh
make build                      # writes bin/smol-builder
go install ./cmd/smol-builder   # or install it into $GOBIN
```

## The stack file

`smol-builder.toml` has two keys:

```toml
layers = ["go", "node"]                # library layers; may be empty
project_layer = "ci/agent.Dockerfile"  # optional; relative to the repository root
```

- `layers` lists names from the layer library. `base` is always applied and cannot be listed.
- `project_layer` is the path of a Dockerfile in the repository. Its build context is the directory that holds it.

`smol-builder` rejects the file, with an error that names the offending entry, when it has:

- a key other than `layers` and `project_layer`;
- a layer that is not in the library, or a layer listed twice;
- a `project_layer` that leaves the repository: an absolute path, a `..` path, or a symlink that resolves outside it;
- a `project_layer` that does not exist or is not a regular file;
- a `project_layer` whose first two instructions are not `ARG BASE` and `FROM ${BASE}`. Comments, blank lines, and parser directives before them are allowed. So is a stage name: `FROM ${BASE} AS dev`.

### Layer order

The chain is always: `base`, then the listed library layers in sorted order, then the project layer. The listing order does not matter: `["node", "go"]` and `["go", "node"]` build the same image.

Sorting is safe because every library layer is independent. Each layer installs into its own prefix and changes the environment only by extending variables such as `PATH`.

## The layer library

The library ships inside the binary (`layers/`). `--layers <dir>` selects another library: a directory with one subdirectory per layer, each holding a `Dockerfile`, and a `base` layer among them.

Every input is pinned. Base images are pinned by digest. Every download is pinned by version and SHA-256, and checked before use, so a tampered download fails the build of that layer.

| Layer | Provides | Pins |
|---|---|---|
| `base` | Debian trixie-slim; `git`, a C toolchain (`build-essential`, `pkg-config`, `make`), `curl`, `jq`, `ripgrep`, `xz-utils`, `procps`, `socat` (which carries Sortie's tool server into a VM); opencode with a policy-only config; `WORKDIR /workspace` | `debian:trixie-slim@sha256:918311b7b6c4c6f68b232ba516584925f6c78ad82b6fd534b98979df6438e483`; opencode 1.18.29, SHA-256 `ea800b7ff56226b70952126c9fc1e2517ca4c4b5682fd9d3f9e87449697a1194` |
| `go` | Go in `/usr/local/go`, `GOPATH=/root/go` | Go 1.27.2, SHA-256 `ecbadb99091a3f46e31f5f934b068b1864eafa7995211b39eaddf76996045fe5` |
| `node` | Node.js LTS and npm in `/opt/node` | Node 24.21.0, SHA-256 `fd8e59d5a511510f6a298afb548f18c7d2b1be404d8b4a27d94fbe49f56cb2d6` |
| `python` | uv and CPython in `/opt/uv-python` | uv 0.13.0, SHA-256 `1468ebd5a5541121837c5a2817b9972ba6090fa6caa3d142620850a47fb75154`; CPython 3.14.6, checked by uv against its own pinned hashes |
| `rust` | rustup and a minimal Rust toolchain with clippy and rustfmt in `/usr/local/cargo` | rustup 1.29.1, SHA-256 `dda7234360b7f578ca8b0ddcb80145646fa61a67c1720a5abc7051b35c9fcb71`; toolchain 1.99.0 |

The `base` layer's Debian packages come from the mirrors at build time. apt checks their signatures, but their versions are not pinned.

No layer holds a credential, a token, or an API key. The opencode config in `base` sets policy only. Credentials are bound to a machine when it is created, never baked into a pack.

Each layer appends its name to `SORTIE_STACK_LAYERS`. In a machine built from `layers = ["go", "node"]` it is `base+go+node`.

### Writing a library layer

A library layer other than `base` starts like a project layer, so it can go on top of any chain:

```dockerfile
ARG BASE
FROM ${BASE}
# Download with a pinned version, check the SHA-256, install into its own prefix.
ENV PATH=/opt/<tool>/bin:${PATH}
ENV SORTIE_STACK_LAYERS=${SORTIE_STACK_LAYERS}+<name>
```

## A project layer

`examples/go-libpq` is a repository that needs Go and the PostgreSQL client headers. Its `smol-builder.toml`:

```toml
layers = ["go"]
project_layer = "ci/agent.Dockerfile"
```

Its `ci/agent.Dockerfile`:

```dockerfile
ARG BASE
FROM ${BASE}

# The project's own system packages, applied on top of every library layer.
RUN apt-get update \
 && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends libpq-dev \
 && rm -rf /var/lib/apt/lists/*
```

`smol-builder` passes the previous step's image as `--build-arg BASE=<tag>`. The build context is `ci/`, so a `COPY` in this Dockerfile reads files from `ci/`. Keep the project layer in a small directory: every file in its build context is hashed for each build (`.git` is skipped).

## Building a pack

```sh
smol-builder build --repo <dir> --output <file>.smolmachine [--layers <dir>]
```

From a checkout of this repository:

```sh
make build
mkdir -p out
bin/smol-builder build --repo examples/go-libpq --output out/go-libpq.smolmachine > out/report.json
jq . out/report.json
sha256sum out/go-libpq.smolmachine
```

Create a machine from the pack and check the stack:

```sh
smolvm machine create --name sb-demo --from out/go-libpq.smolmachine --label smol-builder-example=1
smolvm machine start --name sb-demo
smolvm machine exec --name sb-demo -- sh -c 'go version && dpkg -s libpq-dev | grep Status && echo "$SORTIE_STACK_LAYERS" && pwd'
smolvm machine delete --name sb-demo -f
```

The exec prints the Go version, `Status: install ok installed`, `base+go`, and `/workspace`. The project layer does not change `SORTIE_STACK_LAYERS` unless its Dockerfile does.

### What a build does

1. Reads and validates `<repo>/smol-builder.toml`.
2. Resolves the chain and tags each step `localhost/smol-builder/chain:<hash>`. The hash covers the previous step's hash, the layer's name, and every file in its build context: relative paths, contents, and the executable bit.
3. Builds each step whose tag the engine does not have yet. A step that exists is reused, so a pack with `["go", "node"]` built after one with `["go"]` builds only `node`.
4. Saves the last image as an archive and reads its `Env` and `WorkingDir`.
5. Creates a builder machine from the archive, with that `Env` and `WorkingDir` passed as `-e` and `-w`, then starts and stops it.
6. Runs `smolvm pack create --from-vm` into a temporary name in the output's directory.
7. Deletes the builder machine.
8. Renames the pack onto the output path.

The output is replaced atomically. When a build fails, the file at the output path is left unchanged, and the temporary files are removed.

The builder machine is named `smol-builder-<hash>-<random>` and labelled `smol-builder=1`. It is deleted on every path, including a failed build and an interrupt (SIGINT or SIGTERM). If deleting it fails, the build fails and the error names the machine.

### The report

On success, `smol-builder` prints one JSON object to standard output. Diagnostics, including the engine's build output, go to standard error.

```json
{
  "layers": ["base", "go", "project"],
  "image": "localhost/smol-builder/chain:0123456789abcdef",
  "reused": ["base", "go"],
  "pack": "/abs/path/out/go-libpq.smolmachine",
  "pack_sha256": "<sha256 of the pack file>",
  "pack_bytes": 292742922,
  "timings": {
    "layers": {"base": 0, "go": 0, "project": 21.4},
    "save": 4.7,
    "builder": 6.4,
    "pack": 7.1,
    "total": 40.2
  }
}
```

| Field | Meaning |
|---|---|
| `layers` | The applied steps, in order: `base`, the library layers, then `project` when there is a project layer |
| `image` | The last step's image tag |
| `reused` | Steps that already existed in the engine and were not rebuilt |
| `pack` | The output path, made absolute |
| `pack_sha256`, `pack_bytes` | The pack file's SHA-256 and size |
| `timings` | Seconds per step: each layer's build (0 when reused), `save` (archive and inspect), `builder` (create, start, stop), `pack`, and `total` |

The exit status is 0 on success, 1 when the build fails, and 2 on a usage error.

## Gotchas (smolvm 1.26.1)

- **`pack create --from-vm` drops the image's `ENV` and `WORKDIR`.** It keeps the builder machine's own `-e` and `-w`, so `smol-builder` passes the image config through as flags. Without that, `PATH` loses every toolchain and the working directory is `/`.
- **`pack create --image` takes only registry references.** It refuses a local archive, so `smol-builder` goes through a builder machine and `--from-vm` instead.
- **`pack create -o STEM` writes two files:** `STEM.smolmachine`, the pack, and `STEM`, a launcher executable of about 50 MB. `smol-builder` keeps only the pack. Give the output a `.smolmachine` name.
- **Extracted packs are cached under `~/.cache/smolvm`.** The first `machine create --from` a new pack extracts it there, and the cache grows by hundreds of MiB per pack. Clean it with `smolvm pack prune`:

  ```sh
  smolvm pack prune --dry-run   # list what would go
  smolvm pack prune --keep 5    # keep at most 5 unused entries
  ```

- **Packs are not byte-reproducible.** Packing the same image twice gives files with different SHA-256s. `pack_sha256` identifies one pack file; the `image` tag identifies the stack.
- **Images stay in the engine.** Every chain step remains tagged under `localhost/smol-builder/chain`, so later builds can reuse it. Remove old ones with `podman image prune` or `podman rmi`.
- **The archive is written to the system temporary directory** (`$TMPDIR`, else `/tmp`). A stack with every layer makes an archive of about 2 GB.

## Development

```sh
make test    # unit tests with the race detector
make lint    # golangci-lint
make build   # static binary, CGO_ENABLED=0
SMOL_BUILDER_SMOLVM_TEST=1 go test -count=1 -run TestIntegration -v ./internal/build/
```

The integration test needs podman and smolvm. It builds `layers = ["go"]`, creates a machine from the pack, and checks that `go` resolves through `PATH` and the working directory is `/workspace`. It then forces two failures and checks that the previous pack is unchanged and no builder machine remains. Without `SMOL_BUILDER_SMOLVM_TEST=1` it is skipped.
