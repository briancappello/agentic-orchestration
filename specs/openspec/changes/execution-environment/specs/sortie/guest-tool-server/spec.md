## Purpose

Lets an agent running inside an execution environment use Sortie's MCP tools, while the tool server, the workflow file, the tracker credentials and the database stay on the host.

## ADDED Requirements

### Requirement: Tools are served from the host
For a session in a `smolvm` environment, Sortie SHALL listen on a per-issue Unix socket on the host, outside the workspace, and make it reachable in the guest at `/run/sortie/tools.sock`. For each connection, Sortie SHALL run its MCP tool server on the host, with the session's environment, connected to that socket.

The MCP configuration Sortie generates for the session SHALL launch, in the guest, a relay that connects to the socket. That relay SHALL be the Sortie binary from the read-only directory, run as `mcp-relay /run/sortie/tools.sock`. Agent kinds that read the MCP configuration from a path SHALL receive its guest path.

#### Scenario: Agent calls a Sortie tool
- **WHEN** an agent in the VM calls the `sortie_status` tool
- **THEN** the call returns the issue's status
- **AND** the tool server process ran on the host

#### Scenario: Tracker credentials stay on the host
- **WHEN** an agent session runs in the VM
- **THEN** no guest file or guest process environment holds the tracker credentials or the workflow file

### Requirement: Relay fails fast when no server listens
When the socket accepts a connection but no tool server answers, `mcp-relay` SHALL write `tool server unavailable` to standard error and exit with a non-zero status. It SHALL NOT wait for input indefinitely.

#### Scenario: Sortie not listening
- **WHEN** the host listener for the issue is not running
- **AND** the agent starts the relay
- **THEN** the relay exits non-zero with `tool server unavailable` on standard error

### Requirement: Tools survive a Sortie restart
After Sortie restarts, it SHALL listen again on the same socket path for every workspace that has a VM. A VM that was running SHALL reach the new listener without being restarted.

#### Scenario: Restart while a VM runs
- **WHEN** Sortie restarts while the VM of issue `VM-1` keeps running
- **AND** an agent in that VM starts the relay afterwards
- **THEN** the tool call succeeds

### Requirement: Socket scoped to its issue
Each socket SHALL serve only its own issue. The tool server started for a connection SHALL carry that issue's identity and that issue's workspace.

#### Scenario: Two issues
- **WHEN** issues `VM-1` and `VM-2` both have running VMs
- **AND** the agent in `VM-2` calls `sortie_status`
- **THEN** the result describes `VM-2`
