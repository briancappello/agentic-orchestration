## 1. Sortie fork

- [x] 1.1 Give `domain.LaunchCarrier` a workspace and a tool channel, drop `GuestPath`, and pass secret variables by name; verify with the agentcore launch-target tests.
- [x] 1.2 Serve a carrier session's relay over its tool channel in `agentcore.ToolSession`; verify with `TestToolSession_CarrierServesTheRelayOverItsChannel` and the gap test.
- [x] 1.3 Deliver the tool server inline on every adapter's carrier path; verify with the per-adapter carrier tests (claude, copilot, codex, opencode, clientprotocol).
- [x] 1.4 Start the guest `socat` listener at each VM start in `internal/environment/smolvm`, refusing a pack without it, and drop the binary mount; verify with the prepare and lifecycle tests.
- [x] 1.5 Write a carried session's MCP configuration to `.sortie-host`; verify with `TestGenerateMCPConfig_HostOnly` and the worker carrier test.
- [x] 1.6 Delete `internal/toolsocket`, the `mcp-relay` subcommand, and the orchestrator's socket registry; verify `go test ./...`, `go vet`, and `make lint`.
- [x] 1.7 Update the fork's architecture sections, workflow reference, smolvm guide, adapter notes, and changelog; verify `make lint-docs`.

## 2. smol-builder

- [x] 2.1 Add `socat` to the `base` layer; verify a built pack has `/usr/bin/socat`.

## 3. Proof

- [x] 3.1 Run Sortie with `environment.kind: smolvm` and `opencode acp` in the guest, with a prompt that calls `sortie_status`; verify the agent wrote the tool's result to `.sortie/tool-proof.txt` and Sortie logged `delivered tool server to session`.
