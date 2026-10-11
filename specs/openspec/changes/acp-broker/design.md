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

Endpoints: `GET /events` (Server-Sent Events, with a heartbeat comment every 15 seconds), `POST /commands`, `GET /state`, `POST /login`, and `POST /logout`. Non-browser clients send the viewer token as a bearer header. Browsers cannot set headers on an `EventSource`, so they call `POST /login` once with the token. The broker answers with an `HttpOnly`, `SameSite=Strict` cookie whose value is a random session ID, kept only in the broker's memory. `SameSite=Strict` also covers cross-site request forgery on `POST /commands`. Tokens and session IDs are compared in constant time.

Why Server-Sent Events:
- `EventSource` reconnects by itself and sends `Last-Event-ID`, which maps directly onto the replay buffer (D2). That matters most on phones, where connections drop often.
- Debugging needs only `curl`.
- It needs no dependency.

Alternative: WebSocket. Rejected:
- It needs a dependency or a hand-written implementation, and its own resume handshake.
- It has the same browser header limit, so it would not avoid the cookie.
- It only pays off for full-duplex terminal streaming, which the viewers do not do.

Transports sit behind the viewer interface (D1), so adding WebSocket later stays additive. Browsers allow about six HTTP/1.1 connections per host, which limits how many sessions one tab can watch. A TLS front end with HTTP/2, such as Tailscale serve, removes that limit.

### D4. Sortie integration through the session environment and a scoped session token

The broker reads `SORTIE_API_URL`, `SORTIE_ISSUE_IDENTIFIER`, `SORTIE_SESSION_PURPOSE`, and `SORTIE_SESSION_TOKEN` from the environment Sortie gives it (change `sortie-session-control`). The session token only authorizes hold, release, and escalate for this run's issue, and it expires with the run. So the broker needs no operator setup, and the worst a leaked token can do is affect its own run. The broker removes the token from the agent's environment before launching the agent.

In local mode this does not hide the token: the agent runs as the same user and can read the broker's environment through `/proc`. The scoping is what limits the harm. Once the agent runs in a sandbox VM and the broker stays on the host (change `execution-environment`), removing the token from the agent's environment becomes a real boundary.

Alternative: an operator token file named by a broker flag. Rejected:
- it needs per-workflow setup
- it gives power over every issue
- it is just as readable in local mode

### D5. Hold state is reconciled, not fired and forgotten

`sortieclient` keeps the desired hold state (held or released, with a reason) and one worker goroutine that brings Sortie to that state, retrying with capped backoff. The loop only sets the desired state, so a slow or down Sortie never blocks the relay. On exit, the broker makes a final release attempt with a short bound.

### D6. Permission requests and questions

Each waiting request gets two loop timers: escalation (default 30 seconds, or at once with no viewer attached) and the answer timeout (default 10 minutes). Escalation sets the desired hold and calls escalate with kind `permission` or `question`. A request is a question when none of its options has an allow kind. Any resolution clears both timers and the hold taken for that request. Free-text questions are out of scope, because the agents signal them in incompatible ways.

### D7. Steering selection

The broker reads steering support once, from the `initialize` result. Native: `_session/steering` with `idleBehavior: "promptRequired"`. Fallback: the spike's same-session turn with automatic handback.

Native steering only applies while a driver turn is running. An agent with native steering answers a steer on an idle session with `{"outcome":"promptRequired"}` and drops the text, so an idle session is steered with the same-session turn for every agent: the broker holds Sortie with reason `steer`, queues driver prompts, and hands back when the turn ends. A native steer can still race the end of the driver's turn. When it comes back `promptRequired`, the broker resends it once if a new driver turn is running by then, and otherwise runs it as a same-session turn. A second `promptRequired` also becomes a same-session turn (cancelling a driver turn that is running, as the fallback does), so a steer is never resent in a loop. If humans took the floor while the steer was in flight, the steer is dropped with a message to send a prompt, because the steer turn's automatic handback would end their takeover. We chose this over omitting `idleBehavior`, which makes Claude start a turn itself: the broker would not see that turn as its own, so it could not hold Sortie or queue driver prompts around it. When ACP PR #1261 (`session/inject`) lands, the broker prefers it whenever the agent advertises it, and keeps the vendor extension as the second choice. The broker notes track this.

### D8. Credential-check sessions are pass-through

When `SORTIE_SESSION_PURPOSE=credential-check`, the broker relays but does not register, open a socket, or start HTTP. This removes the race that the spike hit on its fixed socket path, and keeps lists clean.

## Risks / Trade-offs

- [The viewer token is long-lived and shared] → It never travels in URLs. Browsers trade it once for a cookie that expires and dies with the broker. Recommend a TLS front end (Tailscale serve) so the cookie can be `Secure`. Per-user tokens are a later change.
- [A local agent reads `SORTIE_SESSION_TOKEN` from the broker's environment] → Accepted. The token is scoped to its own run (see D4), and the sandbox closes the gap.
- [A forgotten takeover holds a run and its slot] → Automatic handback after the viewer grace period (D1 timers). Sortie's held-runs gauge allows an alert.
- [The default 10-minute permission wait can stall a run that nobody watches] → It is configurable per broker, and 0 means no limit. Escalation shows the wait in Sortie's held state and metrics.
- [Agents change their ACP behavior: new steering methods, permission shapes, usage fields] → The broker notes record what each agent does. The behavior is pinned by tests with a fake agent, plus one live check per supported agent before each upgrade.
- [Replay sends transcripts, which may contain secrets, to every viewer] → Viewers need the token or local user access, the same trust as the session itself. Masking before telemetry is handled in change `agent-telemetry`.
- [The broker and Sortie disagree about the hold after a crash] → A hold ends when the worker exits (change `sortie-session-control`). The broker reconciles its desired state again after each failed call.

## Migration Plan

1. Start from the spike's code. Keep its tests as the regression base.
2. Deploy change `sortie-session-control` first. Without it, the broker runs and skips the Sortie calls.
3. Switch a workflow by prefixing `agent.command` with the broker command and its flags. Rollback means removing the prefix.
