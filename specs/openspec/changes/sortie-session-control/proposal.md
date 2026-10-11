## Why

Humans must be able to watch, steer, and take over a session that Sortie drives, then hand it back. The ACP broker spike proved the mechanics, but Sortie gives the broker nothing to work with. The agent process does not know which issue, stage, or run it serves. A human-held turn trips Sortie's stall and turn timeouts. An agent question has no path to a person. And the HTTP API that would carry these controls has no authentication.

## What Changes

- The agent process receives the session's identity in its environment: issue ID and identifier, dispatch ID, rule (stage), chain ID, attempt, and the address of Sortie's control API. Today only the MCP sidecar gets part of this, through `.sortie/mcp.json`.
- New authenticated endpoints let a caller mark a running issue as held and release it. While a run is held, Sortie suspends its stall and turn timeouts for that run. The held state appears in `/api/v1/state`, in the per-issue detail, on the dashboard, and in metrics. Sortie records held time per run.
- A new authenticated endpoint lets a caller escalate a running issue to people, with a message. Sortie delivers it as a new notification event through its existing routing (Slack, webhook, tracker comment).
- Every endpoint that changes state requires a bearer token once a token is configured. Sortie refuses to bind to a non-loopback address without a token. `POST /api/v1/refresh` also falls under this rule. **BREAKING** for a deployment that binds to a non-loopback address today: it must configure a token.
- Read-only endpoints and the metrics endpoint keep their current access.

## Capabilities

### New Capabilities
- `sortie/agent-session-context`: the session identity Sortie passes to the agent process, locally and over SSH.
- `sortie/held-runs`: how a run is held and released, what holding suspends, and how a held run is shown and recorded.
- `sortie/operator-escalation`: how a caller escalates a running issue to people through Sortie's notification routing.
- `sortie/control-api-auth`: authentication for Sortie's state-changing HTTP endpoints, and the binding rule.

### Modified Capabilities

None. This store holds no specs yet.

## Impact

- Code, all in the Sortie fork (`~/dev/sortie`):
  - `internal/domain` (`StartSessionParams`, new event type)
  - `internal/agent/agentcore` (`LaunchTarget.BindWorkspace` and the SSH carry)
  - `internal/orchestrator` (worker, reconcile, state, exit, run history)
  - `internal/server`
  - `internal/persistence` (one migration)
  - `internal/config`
- Configuration: new `server` keys for the token. A new event name for `notifications` subscriptions.
- Documentation in the fork: the architecture sections on observability, the HTTP server and notifications; `docs/workflow-reference.md`; `CHANGELOG.md`.
- Upstream: every change is additive and small, and is kept as separate commits so it can be rebased onto upstream or offered upstream.
- Consumers: the ACP broker (change `acp-broker`) is the first caller of hold, release, and escalate, and reads the session environment.
