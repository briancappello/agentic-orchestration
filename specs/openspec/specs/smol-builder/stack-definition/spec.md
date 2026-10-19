# smol-builder/stack-definition Specification

## Purpose
Lets each project declare, in its own repository, the development stack its agents need. The stack is a shared base plus language layers from a pinned library, and optionally one layer of the project's own.

## Requirements

### Requirement: A stack is declared in the project's repository
A project SHALL declare its stack in a file named `smol-builder.toml` at the root of its repository. The file SHALL have:

- `layers`: a list of layer names from the layer library. It may be empty.
- `project_layer`: optional. The path, relative to the repository root, of a Dockerfile.

Any other key SHALL be rejected. So SHALL an unknown layer name, a layer listed twice, and a `project_layer` path that leaves the repository or does not exist. Each error SHALL name the offending entry.

#### Scenario: Valid stack
- **WHEN** `smol-builder.toml` holds `layers = ["go", "node"]`
- **THEN** the stack is base plus go plus node

#### Scenario: Unknown layer
- **WHEN** `smol-builder.toml` holds `layers = ["go", "haskell"]` and the library has no `haskell` layer
- **THEN** the definition is rejected with an error naming `haskell`

#### Scenario: Project layer outside the repository
- **WHEN** `project_layer` is `../other/Dockerfile`
- **THEN** the definition is rejected with an error naming the path

### Requirement: Layer order is deterministic
Library layers SHALL be applied on top of the base in sorted order of their names, whatever order the file lists them in. The project layer, when present, SHALL be applied last. Two definitions with the same set of layers and the same project layer SHALL produce the same image.

#### Scenario: Listing order ignored
- **WHEN** one project lists `["node", "go"]` and another lists `["go", "node"]`, neither with a project layer
- **THEN** both build the same image

### Requirement: The base layer
The base layer SHALL provide:

- a Linux userland
- `git`
- a C toolchain
- `curl`, `jq`, and `ripgrep`
- the supported agent CLIs
- `/workspace` as the working directory

It SHALL hold agent policy configuration only. No layer SHALL contain a credential, a token, or an API key.

#### Scenario: Base-only stack
- **WHEN** a pack is built from `layers = []`
- **AND** a VM is created from it
- **THEN** `git`, `cc`, `jq`, `rg`, and `opencode` run in the VM
- **AND** the working directory is `/workspace`

### Requirement: Layers are pinned and independent
Every library layer SHALL fix its inputs:

- its base image, by digest;
- every downloaded artifact, by version and SHA-256, checked before use.

A failed check SHALL fail the build. Each library layer SHALL install into its own prefix. It SHALL change the environment only by extending variables such as `PATH`, so that any set of library layers composes in sorted order. A layer SHALL record its name in the image's `SORTIE_STACK_LAYERS` variable.

#### Scenario: Tampered download
- **WHEN** a layer's download does not match its recorded SHA-256
- **THEN** the build fails and names the layer

#### Scenario: Composed toolchains
- **WHEN** a pack is built from `layers = ["go", "node", "python", "rust"]`
- **THEN** in a VM created from it, a Go, a Node, a Python, and a Rust program each compile or run without network access
- **AND** `SORTIE_STACK_LAYERS` is `base+go+node+python+rust`

### Requirement: The project layer
A project layer SHALL be a Dockerfile whose first instructions are `ARG BASE` and `FROM ${BASE}`. Its build context SHALL be the directory that holds it. A project layer whose first instructions differ SHALL be rejected.

#### Scenario: Project adds a system package
- **WHEN** `project_layer` installs `libpq-dev`
- **THEN** the pack contains every library layer listed and `libpq-dev`
