## Context

Upstream Sortie runs its tool server per session as `sortie mcp-server --http` on a host loopback port, with a per-session bearer, and an SSH worker reaches it through a reverse forward on the launch's connection. A smolvm guest has no such forward. Measured on smolvm 1.26.1 with the flags Sortie creates VMs with: the guest reaches neither the host's loopback (`127.0.0.1` is the guest's own) nor the host through its gateway (`100.96.0.1`); the egress policy covers neither. smolvm can mount a host Unix socket into the guest (`--mount-socket`), and a socket recreated on the host after the VM started is reached by the guest's next connection.

## Goals / Non-Goals

**Goals:**

- The agent uses upstream's HTTP tool server and bearer, unchanged.
- No Sortie binary, no secret, and no host path but the control directory and one socket in the guest.
- No new host exposure: the guest reaches the session's tool server and nothing else on the host.

**Non-Goals:**

- The remote worker path (stage 0): there the worker daemon carries this channel, and Pomerium gates it.
- Operator stdio MCP servers inside the VM: they are left out, as upstream leaves them out on SSH.

## Decisions

### D1. A mounted socket, not an allowed host

The tool server stays on the host loopback. Sortie listens on the issue's socket for each agent session and joins each connection to the tool server's port; smolvm mounts the socket at `/run/sortie/tools.sock`; a `socat` listener in the guest serves it on `127.0.0.1:47800`. The bearer authorizes each request; the channel carries bytes only.

*Alternative rejected:* allowing the host's gateway in the egress policy. smolvm's policy has no port filter, so the guest would reach every host loopback service: Sortie's control API, the tracker, the forge, local model servers.

*How to reverse:* change `toolListenerArgv` and the channel in `internal/environment/smolvm`, or give the carrier no `ToolChannel`, which leaves the session without Sortie's tools and declares the gap.

### D2. socat in the pack

The guest needs one listener that joins TCP to a Unix socket. `socat` is a standard Debian package, added to smol-builder's `base` layer; it is not a Sortie binary and needs no matching OS or architecture. Sortie starts it detached at each VM start (`smolvm machine exec -d`), and checks for it first, retrying because right after a start smolvm can run a command before the pack's root filesystem is in place (measured: two of 17 starts failed the first check).

*Alternative rejected:* a forwarder in perl or in the agent runtime. Neither is in every pack, and both are harder to read than one `socat` line.

### D3. Inline delivery, bearer by name

A carried session is a remote session for tool delivery: the tool server is declared inline at the guest port (Claude Code and Copilot CLI `--mcp-config <document>`, Codex overrides, OpenCode's configuration document, the ACP `session/new` request), and the bearer travels by variable name, passed with `smolvm machine exec --secret-env`, so no value is in a command line. The generated configuration, whose env block carries the tool server's credentials, moves to `.sortie-host/mcp.json`, out of the directory the guest shares.

## Risks / Trade-offs

- A pack built before this change has no `socat`: preparation fails until the pack is rebuilt. The error names `socat`.
- A runtime that accepts no HTTP tool server gets no Sortie tools in a VM. All five supported kinds accept one.
- Any guest process can reach the tool port; without the bearer it gets nothing. The agent and the processes it starts can already call the tools.
