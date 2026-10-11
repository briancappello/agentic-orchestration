## Context

See proposal.md for the motivation. Starting point: the broker spike. Its tests and the live runs proved these points:

- A single event loop that owns all session state works well. Readers and timers only post events to it.
- Sortie treats a held-then-handed-back turn as an ordinary completed turn.
- Sortie starts two agent processes per dispatch: a credential check, then the work session. So sessions must be found by issue, not by a fixed path.
- Runtime differences that the broker has to handle:
  - steering is native only on `claude-agent-acp` (and on `pi-acp` with PR #115)
  - usage on the prompt result comes from OpenCode and Claude
  - Pi never asks for permission

Constraints: the code is its own Go module, `acp-broker/`; no new dependencies; Go standard library only; no CGo.

## Goals / Non-Goals

**Goals:**
- Keep the spike's proven contract. Harden it, and add HTTP transport, replay, a registry, and integration with Sortie.
- The broker stays usable without Sortie: it runs as a plain ACP proxy, and the Sortie calls are skipped.

**Non-Goals:**
- OpenTelemetry export. That is change `agent-telemetry`; this change only keeps events in a form that change can read.
- The herdr plugin and any web UI. That is change `human-surfaces`.
- Isolating the agent's own configuration (hooks, plugins, MCP servers). That belongs to the agent command or its wrapper, as shown in `acp-broker/examples`. The broker runs whatever command it is given.
- Running the broker inside a sandbox VM. The broker runs on the host; only the agent command runs in the VM (change `execution-environment`).
- Full Pi parity. It is deferred until upstream `pi-acp` #115, #106, and #145 land.

## Decisions

### D1. Package layout around one event loop

`acp-broker/internal/broker` keeps the loop and the protocol rules. It has no input or output of its own. Around it sit four packages:

- `acp-broker/internal/transport`: the Unix socket and the HTTP listener. Both turn connections into the same viewer interface.
- `acp-broker/internal/registry`: registry records, listing, and stale-record cleanup.
- `acp-broker/internal/sortieclient`: hold, release, and escalate calls with retry.
- `acp-broker/cmd/acp-broker`: flags, process launch, and the `ls`, `attach`, and `send` subcommands.

The loop keeps the spike's rule: only the loop changes state. Timers (permission escalation, answer timeout, handback grace) post events to the loop instead of acting directly.

### D2. Event log with sequence numbers

The loop gives each outgoing viewer event a sequence number and keeps it in a ring buffer, bounded by event count and by bytes. A new viewer gets the current state, then a copy of the buffer, then live events, all through one bounded channel per viewer. A full channel disconnects that viewer. This replaces the spike's broadcast-only design, and lets HTTP clients use `Last-Event-ID` with no extra state.

### D3. HTTP with Server-Sent Events and `POST`, standard library only

Endpoints: `GET /events` (Server-Sent Events, with a heartbeat comment every 15 seconds), `POST /commands`, and `GET /state`. The token is compared in constant time. Browsers cannot set headers on an `EventSource`, so `GET /events` also accepts an `access_token` query parameter.

Alternative: WebSocket. Rejected because it adds a dependency or a hand-written implementation. The stream only flows one way, and commands are rare.

### D4. Sortie integration through the session environment and a token file

The broker reads `SORTIE_API_URL`, `SORTIE_ISSUE_IDENTIFIER`, and `SORTIE_SESSION_PURPOSE` from the environment Sortie gives it (change `sortie-session-control`). Change `sortie-session-control` keeps Sortie's control token out of the agent environment, and Sortie launches the broker as the agent command. So the broker reads the token from a file named by `-sortie-token-file`, readable only by the operator user. The broker always runs on the host, so this works with sandboxed agents too.

### D5. Hold state is reconciled, not fired and forgotten

`sortieclient` keeps the desired hold state (held or released, with a reason) and one worker goroutine that brings Sortie to that state, retrying with capped backoff. The loop only sets the desired state, so a slow or down Sortie never blocks the relay. On exit, the broker makes a final release attempt with a short bound.

### D6. Permission requests and questions

Each waiting request gets two loop timers: escalation (default 30 seconds, or at once with no viewer attached) and the answer timeout (default 10 minutes). Escalation sets the desired hold and calls escalate with kind `permission` or `question`. A request is a question when none of its options has an allow kind. Any resolution clears both timers and the hold taken for that request. Free-text questions are out of scope, because the agents signal them in incompatible ways.

### D7. Steering selection

The broker reads steering support once, from the `initialize` result. Native: `_session/steering` with `idleBehavior: "promptRequired"`. Fallback: the spike's same-session turn with automatic handback. When ACP PR #1261 (`session/inject`) lands, the broker prefers it whenever the agent advertises it, and keeps the vendor extension as the second choice. The broker notes track this.

### D8. Credential-check sessions are pass-through

When `SORTIE_SESSION_PURPOSE=credential-check`, the broker relays but does not register, open a socket, or start HTTP. This removes the race that the spike hit on its fixed socket path, and keeps lists clean.

## Risks / Trade-offs

- [The token in the `access_token` query parameter can end up in proxy or browser logs] → Accept it only on `GET /events`. Recommend Tailscale serve or another TLS front end. A later change can add short-lived tokens issued by `POST /session-token`.
- [A forgotten takeover holds a run and its slot] → Automatic handback after the viewer grace period (D1 timers). Sortie's held-runs gauge allows an alert.
- [The default 10-minute permission wait can stall a run that nobody watches] → It is configurable per broker, and 0 means no limit. Escalation shows the wait in Sortie's held state and metrics.
- [Agents change their ACP behavior: new steering methods, permission shapes, usage fields] → The broker notes record what each agent does. The behavior is pinned by tests with a fake agent, plus one live check per supported agent before each upgrade.
- [Replay sends transcripts, which may contain secrets, to every viewer] → Viewers need the token or local user access, the same trust as the session itself. Masking before telemetry is handled in change `agent-telemetry`.
- [The broker and Sortie disagree about the hold after a crash] → A hold ends when the worker exits (change `sortie-session-control`). The broker reconciles its desired state again after each failed call.

## Migration Plan

1. Start from the spike's code. Keep its tests as the regression base.
2. Deploy change `sortie-session-control` first. Without it, the broker runs and skips the Sortie calls.
3. Switch a workflow by prefixing `agent.command` with the broker command and its flags. Rollback means removing the prefix.
