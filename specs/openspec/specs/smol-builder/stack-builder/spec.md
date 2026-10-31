# smol-builder/stack-builder Specification

## Purpose
Defines `smol-builder`, the separate tool that turns a project's stack definition into a smolvm pack that a Sortie workflow can name, and what it reports about the result.

## Requirements

### Requirement: Build a pack from a repository
`smol-builder build --repo <dir> --output <path>` SHALL read `<dir>/smol-builder.toml`, build the stack's image with the host's container engine, and write a smolvm pack to `<path>`. The layer library SHALL default to the one shipped with the tool. `--layers <dir>` SHALL select another one.

The tool SHALL require podman or docker, and smolvm. It SHALL fail with an error naming the missing program when either is absent.

#### Scenario: Build succeeds
- **WHEN** a repository declares `layers = ["go"]`
- **AND** `smol-builder build --repo . --output /var/lib/smol-builder/app.smolmachine` runs
- **THEN** the file exists and a smolvm machine created from it runs `go version`

### Requirement: The pack keeps the image's environment
A machine created from a pack SHALL see the image's environment variables and working directory, including every `PATH` entry the layers added.

#### Scenario: Toolchain on PATH
- **WHEN** a pack is built with the `go` layer
- **AND** a machine is created from the pack
- **THEN** `go` resolves through `PATH` without an absolute path
- **AND** the working directory is `/workspace`

### Requirement: Unchanged layers are reused
The tool SHALL identify each step of a layer chain by a content hash of the base, of every layer applied so far, and of their files. It SHALL reuse a step that already exists in the container engine instead of rebuilding it.

#### Scenario: Shared prefix
- **WHEN** a pack with `["go"]` was built
- **AND** a pack with `["go", "node"]` is built next
- **THEN** the second build builds only the `node` step

### Requirement: Output is atomic
The tool SHALL write the pack under a temporary name in the output's directory, and rename it to the output path only after the pack is complete. When a build fails, the file previously at the output path SHALL be left unchanged.

#### Scenario: Failed rebuild
- **WHEN** `/var/lib/smol-builder/app.smolmachine` exists
- **AND** a rebuild fails in the `rust` step
- **THEN** the existing file is unchanged

### Requirement: Temporary machines are cleaned up
Any smolvm machine, and any temporary file or directory, the tool creates while building SHALL be deleted before the tool exits, whether the build succeeded or failed.

The tool SHALL also delete, before it creates a machine, every machine and temporary directory an earlier run of the tool left behind, for example when that run was killed or the host restarted. It SHALL mark each machine (with labels) and each temporary directory (with an owner file) with its own process ID, that process's start time, and the host's boot ID. It SHALL treat a marked machine or directory as left behind only when its boot ID is not the current one, or no process with that ID and start time runs. It SHALL NOT delete a machine or directory of a build that is still running, and SHALL NOT delete any machine or directory without its mark.

#### Scenario: Build interrupted by a failure
- **WHEN** packing fails after the builder machine was created
- **THEN** no machine created by the tool remains in `smolvm machine ls`

#### Scenario: Builder left by a restart
- **WHEN** the host restarted while a build ran, leaving its builder machine
- **AND** a new build starts
- **THEN** the new build deletes that machine, and that build's temporary directories, before creating its own

#### Scenario: Two builds at once
- **WHEN** a second build starts while the first build's builder machine exists
- **THEN** the first build's machine is not deleted

### Requirement: Build report
On success, the tool SHALL print one JSON object to standard output with:

- `layers`: the applied layer list, in order, including `project` when present
- `image`: the image tag
- `pack`: the output path
- `pack_sha256`: the pack's SHA-256
- `pack_bytes`: the pack's size
- `timings`: timings per step, in seconds

Diagnostics SHALL go to standard error.

#### Scenario: Report names the digest
- **WHEN** a build succeeds
- **THEN** standard output is one JSON object whose `pack_sha256` equals the SHA-256 of the file at the output path
