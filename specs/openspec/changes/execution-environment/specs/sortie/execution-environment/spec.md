## Purpose

Lets a workflow choose where workspace code runs. Every operation that runs code from an issue's workspace goes through the workflow's execution environment, so a sandboxed environment covers all of them, not only the agent.

## ADDED Requirements

### Requirement: Workflow selects an execution environment kind
Sortie SHALL read `environment.kind` from the workflow front matter. The accepted values are `local` and `smolvm`. When `environment` or `environment.kind` is absent, the kind SHALL be `local`. An unknown kind SHALL fail validation with an error that names the setting and the value.

At startup, a validation failure SHALL stop Sortie. On reload, Sortie SHALL keep the previous configuration and report the failure through `LastLoadError()`.

#### Scenario: No environment block
- **WHEN** a workflow has no `environment` block
- **THEN** Sortie runs every issue with the `local` kind

#### Scenario: Unknown kind on reload
- **WHEN** a running Sortie reloads a workflow that sets `environment.kind: firecracker`
- **THEN** Sortie keeps running with the previous configuration
- **AND** `LastLoadError()` reports an error that names `environment.kind` and `firecracker`

### Requirement: The local kind preserves current behavior
With the `local` kind, Sortie SHALL run agents, hooks, verification commands, reaction triage, and git inspection exactly as it does without this change, on the host, in the host workspace directory.

#### Scenario: Existing workflow unchanged
- **WHEN** a workflow that ran before this change runs with no `environment` block
- **THEN** its hooks, agent sessions, and handoff evidence behave as before

### Requirement: Workspace code runs inside the environment
Sortie SHALL run each of the following through the issue's execution environment, with the workspace as the working directory:

- the agent session, including the credential check session
- auxiliary agent commands
- the `after_create`, `before_run`, `after_run`, and `before_remove` hooks
- self-review verification commands
- reaction triage
- every `git` command Sortie runs to inspect the workspace

None of these SHALL run on the host when the kind is not `local`.

#### Scenario: Hook runs in the VM
- **WHEN** the kind is `smolvm`
- **AND** `after_create` is `uname -n > created-on`
- **THEN** after preparation, the file `created-on` exists in the guest workspace and holds the VM's hostname
- **AND** no file named `created-on` exists in the host workspace directory

#### Scenario: Handoff evidence reads git in the VM
- **WHEN** the kind is `smolvm`
- **AND** the agent commits in the guest workspace during a run
- **THEN** Sortie's handoff evidence reports that the commit moved
- **AND** Sortie starts no `git` process on the host for that inspection

### Requirement: A host prefix stays on the host
When `environment.host_prefix` is set to a non-empty list of strings, Sortie SHALL launch the agent session and the credential check as that list followed by the environment's launch command for the agent. The prefix SHALL run on the host with the session's full environment. Hooks, verification commands, triage, auxiliary commands, and git inspection SHALL NOT use the prefix. An empty list, or a list with an empty element, SHALL fail validation.

#### Scenario: Broker on the host, agent in the VM
- **WHEN** the kind is `smolvm`
- **AND** `host_prefix` is `[acp-broker, --]`
- **AND** the agent command is `opencode acp`
- **THEN** the `acp-broker` process runs on the host and receives `SORTIE_SESSION_TOKEN`
- **AND** `opencode acp` runs inside the issue's VM

### Requirement: smolvm excludes SSH workers
Validation SHALL fail when `environment.kind` is `smolvm` and `worker.ssh_hosts` is non-empty. The error SHALL name both settings.

#### Scenario: Both configured
- **WHEN** a workflow sets `environment.kind: smolvm` and lists one SSH host
- **THEN** validation fails with an error naming `environment.kind` and `worker.ssh_hosts`

### Requirement: No fallback to local execution
When an issue's environment cannot be prepared, Sortie SHALL fail that workspace preparation and handle it as it handles any preparation failure today. It SHALL NOT run the issue's hooks or agent on the host instead.

#### Scenario: VM fails to start
- **WHEN** the kind is `smolvm`
- **AND** the VM for issue `ENV-1` fails to start
- **THEN** the run for `ENV-1` ends with a workspace preparation error and is scheduled for retry
- **AND** no hook or agent process for `ENV-1` starts on the host

### Requirement: Changing the kind recreates a workspace
Sortie SHALL record the environment kind that created a workspace. When an issue is dispatched and its existing workspace was created by a different kind, Sortie SHALL remove the workspace and its environment, then prepare a new one, so that `after_create` runs again. A workspace without a record SHALL count as created by `local`.

#### Scenario: Switch from local to smolvm
- **WHEN** issue `ENV-2` has a workspace created under `local`
- **AND** the workflow now sets `environment.kind: smolvm`
- **AND** `ENV-2` is dispatched
- **THEN** Sortie removes the host workspace and creates a VM
- **AND** `after_create` runs in that VM
