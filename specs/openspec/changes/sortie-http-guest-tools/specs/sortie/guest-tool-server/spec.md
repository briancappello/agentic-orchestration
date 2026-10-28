## MODIFIED Requirements

### Requirement: Tools are served from the host
For an agent session in a `smolvm` environment, Sortie SHALL run its MCP tool server on the host, over Streamable HTTP on a loopback port, with a bearer valid only for that session, as it does for an SSH worker. While the session runs, Sortie SHALL listen on the issue's tool channel socket on the host, outside the workspace and mounted in the guest at `/run/sortie/tools.sock`, and SHALL join each connection to the tool server's port.

The agent SHALL receive Sortie's tool server as the HTTP server `http://127.0.0.1:47800/mcp`, declared inline, never as a file path. The bearer SHALL reach the agent by variable name, with a value that never appears on a command line. Stdio servers from the operator's `mcp_config` SHALL be left out, and the session SHALL declare the gap. The generated MCP configuration SHALL be written to the host-only `.sortie-host` directory, not to the shared `.sortie`.

#### Scenario: Agent calls a Sortie tool
- **WHEN** an agent in the VM calls the `sortie_status` tool
- **THEN** the call returns the issue's status
- **AND** the tool server process ran on the host

#### Scenario: Tracker credentials stay on the host
- **WHEN** an agent session runs in the VM
- **THEN** no guest file or guest process environment holds the tracker credentials or the workflow file
- **AND** `/workspace/.sortie/mcp.json` does not exist in the guest

#### Scenario: A request without the bearer
- **WHEN** a guest process connects to `127.0.0.1:47800` without the session's bearer
- **THEN** the tool server refuses the request

### Requirement: Socket scoped to its issue
Each socket SHALL serve only its own issue, and only while one of its agent sessions runs. It SHALL lead only to that session's tool server, which carries that issue's identity and that issue's workspace.

#### Scenario: Two issues
- **WHEN** issues `VM-1` and `VM-2` both have running VMs
- **AND** the agent in `VM-2` calls `sortie_status`
- **THEN** the result describes `VM-2`

## REMOVED Requirements

### Requirement: Relay fails fast when no server listens
**Reason**: The guest runs no Sortie relay. A runtime that cannot reach the HTTP tool server reports the server as failed itself, and Sortie declares the tool-server gap when no runtime connects within the read timeout.
**Migration**: None.

### Requirement: Tools survive a Sortie restart
**Reason**: The socket now lives as long as an agent session, and a Sortie restart ends every session; the next session serves the socket again.
**Migration**: None. A `tool-session.json` left in `<state dir>/env/<key>/` by an earlier version is unused.
