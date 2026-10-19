## Why

We want autonomous agent sessions that people can watch, steer, take over, and hand back, all within one session. The broker spike proved this with OpenCode, Claude, and Pi. The spike is not ready for daily use:
- Viewers connect only over a local Unix socket, with no authentication.
- A viewer that attaches late sees nothing that already happened.
- Agent questions only reach a person who is already attached.
- Sortie does not know a human is working in the session, so a long takeover can trip its timeouts.

## What Changes

- Turn the spike into a supported component, `acp-broker`. It sits between Sortie and any ACP agent and keeps one session with two input vectors: the autonomous driver and humans.
- Keep the spike's proven behavior as the contract:
  - relay
  - take over, hold the driver's turn, and hand back
  - prompts in the same session
  - queued driver prompts
  - the driver's own cancel winning
  - steering as a queue of messages that always land, natively when the agent supports it and as a same-session turn otherwise; interrupting is a separate command
  - permission requests going to viewers first
- Tell Sortie when a human holds the session: the broker calls Sortie's hold and release endpoints (change `sortie-session-control`), so Sortie's clocks pause.
- Escalate agent questions and permission requests to people through Sortie's escalation endpoint when no viewer answers. The request waits for an answer for a configurable time.
- Add an authenticated HTTP transport for web and phone clients, next to the local socket. Events stream as Server-Sent Events, and commands arrive as `POST` requests. Browsers log in once and use an `HttpOnly` cookie, so the token never appears in a URL. It uses only the Go standard library.
- Authenticate calls to Sortie with the per-run session token Sortie mints (`SORTIE_SESSION_TOKEN`), scoped to the run's own issue, and keep that token out of the agent's environment.
- Add a replay buffer, so a viewer that attaches late gets the session so far.
- Add a session registry, so clients find the live session for an issue without knowing process IDs. Credential-check sessions are left out.
- Record **deferred work**: full Pi parity (native steering over ACP, per-turn usage, MCP passed through) waits on upstream `svkozak/pi-acp` #115, #106, and #145. Until then Pi uses the steering fallback and the MCP wrapper in `acp-broker/examples/pi`.

## Capabilities

### New Capabilities
- `acp-broker/session-relay`: relaying one ACP session between the driver and the agent. Floor control, interrupt and handback, queued and cancelled driver prompts, and Sortie hold integration.
- `acp-broker/steering`: queuing human messages into a session so they always land, natively mid-turn when the agent supports it and as a same-session turn when it does not.
- `acp-broker/permission-escalation`: routing agent permission requests and questions to viewers, escalating to people through Sortie, and falling back to the driver.
- `acp-broker/viewer-transport`: the viewer protocol over a local socket and authenticated HTTP (Server-Sent Events plus `POST`). Covers the event and command shapes and replay for late viewers.
- `acp-broker/session-registry`: how clients find live sessions by issue key, and what a session advertises about itself.

### Modified Capabilities

None.

## Impact

- Code: `acp-broker/`, a Go module of its own. No new dependencies: the HTTP transport and the client for Sortie's control API use the standard library.
- Depends on change `sortie-session-control` for the session environment, the per-session token, hold and release, and escalation.
- Configuration: broker flags and environment for the listen address, the viewer token, the Sortie token, and the timeouts.
- Docs: `acp-broker/docs/notes.md` (upstream tracking and runtime observations), plus a new operator guide for the broker.
- Unblocks the `agent-telemetry` and `human-surfaces` changes, which consume the broker's events and registry.
