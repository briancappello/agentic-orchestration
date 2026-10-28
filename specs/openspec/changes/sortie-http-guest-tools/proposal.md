## Why

Agents in a smolvm VM reach Sortie's tools through a relay the fork wrote: a per-issue host socket, and a copy of the host's Sortie binary mounted read-only in the guest as `mcp-relay`. The binary copy fails on any host whose OS or architecture differs from the guest's, and it keeps the fork apart from upstream. Upstream Sortie now serves its tools over Streamable HTTP with a per-session bearer (#1485). The agent platform design adopts it (agent-platform-workers, D9 and D10): the guest needs no Sortie binary.

## What Changes

- An agent in a VM reaches Sortie's tool server over HTTP, with upstream's per-session bearer, at `http://127.0.0.1:47800/mcp` in the guest. The tool server still runs on the host.
- The guest reaches it through the issue's socket, the one host path smolvm mounts besides the control directory: Sortie serves the socket on the host for each agent session and joins each connection to the tool server's loopback port, and a `socat` listener in the guest, started at each VM start, joins the guest port to the socket.
- The read-only Sortie binary mount (`/opt/sortie`) and the `mcp-relay` subcommand are removed. **BREAKING** for a pack without `socat`: preparation fails and names it. smol-builder's `base` layer gains `socat`.
- The generated MCP configuration of a VM session moves to the host-only `.sortie-host/mcp.json`, out of the shared control directory, because its env block carries the tool server's credentials.
- The tool socket no longer survives a Sortie restart: it lives as long as an agent session, and a restart ends the session.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `sortie/smolvm-environment`: the VM gets two host resources instead of three; the pack must contain `socat`; Sortie starts the guest's tool listener at each VM start.
- `sortie/guest-tool-server`: tools are served over HTTP with a per-session bearer through the issue's socket instead of a relay binary; the relay's fail-fast and restart requirements are removed.

## Impact

- Sortie fork: `internal/agent/agentcore` (tool session, tool channel, launch target), every agent adapter's carrier path, `internal/environment` and `internal/environment/smolvm`, `internal/orchestrator` (MCP config, worker), `cmd/sortie`; `internal/toolsocket` and `mcp-relay` are deleted. Fork documentation and `CHANGELOG.md`.
- smol-builder: `socat` in the `base` layer.
- Operators: rebuild packs with the new `base` layer.
