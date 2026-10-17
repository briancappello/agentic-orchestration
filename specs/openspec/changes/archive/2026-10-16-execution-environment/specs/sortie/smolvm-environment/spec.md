## Purpose

Defines the `smolvm` execution environment. Each issue gets its own microVM, built from a stack pack. The VM keeps the workspace on its own disk, shares only the control directory with the host, and reaches the network and credentials only as the workflow allows.

## ADDED Requirements

### Requirement: Supported smolvm version
With the `smolvm` kind, Sortie SHALL run the configured smolvm binary's version command when it starts, and on every reload that selects the kind. Sortie SHALL refuse a version outside the supported range, which is initially `1.26.x`. At startup the refusal SHALL stop Sortie. On reload the previous configuration SHALL be kept. The error SHALL name the version found and the supported range. A missing binary SHALL be refused the same way.

#### Scenario: Unsupported version at startup
- **WHEN** the workflow selects `smolvm` and `smolvm --version` prints `smolvm 1.30.0`
- **THEN** Sortie exits at startup with an error naming `1.30.0` and `1.26.x`

### Requirement: The pack must exist
`environment.smolvm.pack` SHALL be required with the `smolvm` kind. It SHALL name a readable file on the host. Validation SHALL fail when it is absent or unreadable.

#### Scenario: Missing pack
- **WHEN** `environment.smolvm.pack` names a file that does not exist
- **THEN** validation fails with an error naming the setting and the path

### Requirement: One VM per issue workspace
Sortie SHALL create at most one VM for each issue workspace. The VM's name SHALL be derived from the sanitized workspace key. Sortie SHALL label the VM as managed by Sortie, with its workspace key and the SHA-256 of the pack it was created from.

Sortie SHALL create the VM from the configured pack, with the configured `cpus`, `memory_mib`, and `storage_gib`, when the workspace is first prepared. `after_create` SHALL run only after a VM was created. The run history row of each run SHALL record the pack SHA-256 of the VM it ran in.

#### Scenario: First dispatch creates the VM
- **WHEN** issue `VM-1` has no workspace and is dispatched
- **THEN** a VM labeled with `VM-1`'s workspace key and the pack's SHA-256 exists
- **AND** `after_create` runs once, inside it

#### Scenario: Second dispatch reuses the VM
- **WHEN** `VM-1` is dispatched again after its first run ended
- **THEN** Sortie starts the existing VM instead of creating a new one
- **AND** `after_create` does not run again
- **AND** files the first run wrote in the guest workspace are still present

### Requirement: VMs are stopped between runs and removed with their workspace
When an issue's worker exits, Sortie SHALL stop the issue's VM. Wherever Sortie removes an issue workspace (terminal state, retention sweep, or removal by path), it SHALL run `before_remove` in the VM, delete the VM, and then remove the host workspace directory.

#### Scenario: Worker exit stops the VM
- **WHEN** the worker for `VM-1` exits
- **THEN** `VM-1`'s VM is stopped and still exists

#### Scenario: Terminal issue removes the VM
- **WHEN** `VM-1` reaches a terminal state and Sortie cleans up its workspace
- **THEN** `before_remove` ran inside the VM
- **AND** the VM no longer exists
- **AND** the host workspace directory no longer exists

### Requirement: Leftover VMs are deleted
At startup and on each periodic workspace sweep, Sortie SHALL delete every VM it labeled as managed for this workflow whose workspace directory no longer exists. It SHALL NOT delete a VM whose issue has a running worker. It SHALL NOT touch VMs without its label.

#### Scenario: Orphan after a crash
- **WHEN** Sortie restarts and finds a managed VM whose workspace directory was removed
- **THEN** Sortie deletes that VM
- **AND** a VM that Sortie did not label is left running

### Requirement: The workspace lives on the VM's disk
The guest workspace SHALL be `/workspace` on the VM's own disk. `SORTIE_WORKSPACE` SHALL be `/workspace` for every command Sortie runs in the VM. No part of the repository SHALL be on a host mount.

#### Scenario: Agent sees the guest path
- **WHEN** an agent session starts in the VM
- **THEN** its working directory is `/workspace`
- **AND** its `SORTIE_WORKSPACE` is `/workspace`

### Requirement: Only the control directory is shared
Sortie SHALL create the host workspace's `.sortie` directory before creating the VM, and share it read-write with the guest. After `after_create` succeeds, Sortie SHALL make `/workspace/.sortie` resolve to that shared directory. If `/workspace/.sortie` already exists then, for example because the repository commits one, preparation SHALL fail with an error naming it, and Sortie SHALL NOT modify that entry. Files the agent writes under `/workspace/.sortie` SHALL be read by Sortie on the host with the same link refusal and size limits as for a local workspace.

#### Scenario: Agent status reaches Sortie
- **WHEN** the agent writes `blocked` to `/workspace/.sortie/status` in the guest
- **THEN** Sortie reads the status `blocked` from the host workspace's `.sortie/status`

#### Scenario: Planted link refused
- **WHEN** the agent replaces `/workspace/.sortie/status` with a symbolic link to `/etc/passwd`
- **THEN** Sortie refuses to read it, as it refuses a link in a local workspace

#### Scenario: Repository with its own .sortie
- **WHEN** `after_create` clones a repository that contains a `.sortie` directory
- **THEN** preparation fails with an error naming `/workspace/.sortie`

### Requirement: Host resources given to the VM
Sortie SHALL give the VM exactly these host resources:

- the issue's `.sortie` directory, read-write
- the issue's tool-server socket
- a read-only directory that holds only the Sortie binary

Sortie SHALL NOT enable nested virtualization, system mounts, a Docker socket bridge, or published ports. It SHALL NOT mount any other host path.

#### Scenario: No other host paths
- **WHEN** a VM is created for an issue
- **THEN** listing its mounts shows exactly the three resources above

### Requirement: Egress is deny-by-default
The VM SHALL have no network access unless `environment.smolvm.allow_hosts` lists hosts. With a list, the VM SHALL reach only those hosts, plus the hosts of its credential bindings. Each entry SHALL be an exact host name or a `*.domain` pattern.

#### Scenario: Unlisted host blocked
- **WHEN** `allow_hosts` is `[openrouter.ai]`
- **AND** a guest command connects to `github.com`
- **THEN** the connection fails
- **AND** `smolvm machine egress-events` for the VM lists `github.com`

### Requirement: Credentials enter only as bindings
Each entry of `environment.smolvm.credentials` SHALL bind a host environment variable to a guest variable of the same name for the listed hosts, optionally setting one header. The guest SHALL see only a placeholder in that variable. The real value SHALL be substituted only on HTTPS requests to the listed hosts.

A host variable listed in `environment.smolvm.pass_env` SHALL reach the guest in plain text. That copy is opt-in.

Before dispatching, Sortie SHALL check every credential variable the session's agent kind declares. If one is set in Sortie's environment and is listed in neither `credentials` nor `pass_env`, the dispatch preflight SHALL fail with an error that names the variable. Sortie SHALL NOT copy any other host variable into the guest.

#### Scenario: Key used but never seen
- **WHEN** `credentials` binds `OPENROUTER_API_KEY` to `openrouter.ai`
- **AND** the agent in the VM calls the OpenRouter API
- **THEN** the call succeeds
- **AND** the key's value does not appear in any guest file or guest process environment

#### Scenario: Unbound agent credential refused
- **WHEN** the agent kind declares `ANTHROPIC_API_KEY`
- **AND** `ANTHROPIC_API_KEY` is set in Sortie's environment
- **AND** neither `credentials` nor `pass_env` lists it
- **THEN** the dispatch preflight fails with an error naming `ANTHROPIC_API_KEY`

### Requirement: Session identity in the guest
Sortie SHALL give guest commands these session variables:

- `SORTIE_ISSUE_ID`
- `SORTIE_ISSUE_IDENTIFIER`
- `SORTIE_DISPATCH_ID`
- `SORTIE_ATTEMPT`
- `SORTIE_RULE`
- `SORTIE_CHAIN_ID`
- `SORTIE_SESSION_PURPOSE`
- `SORTIE_WORKSPACE`

Hooks SHALL also receive `SORTIE_ENVIRONMENT=smolvm`. Sortie SHALL NOT put `SORTIE_SESSION_TOKEN` or `SORTIE_API_URL` in the guest.

#### Scenario: Token stays on the host
- **WHEN** an agent session runs in the VM with a host prefix
- **THEN** the prefix process has `SORTIE_SESSION_TOKEN`
- **AND** the agent process in the VM does not

### Requirement: The VM is visible in state
`/api/v1/state` and the per-issue detail SHALL show, for an issue whose workspace has a VM, the environment kind and the VM's name.

#### Scenario: Running issue shows its VM
- **WHEN** issue `VM-1` is running under `smolvm`
- **THEN** its entry in `/api/v1/state` names the kind `smolvm` and the VM's name
