## Context

See proposal.md for the motivation. These facts about the Sortie fork shape the approach:

- Every agent adapter builds its own `exec.Cmd`, but each one, local or SSH, passes it through `agentcore.LaunchTarget.BindWorkspace`, or through `LaunchTarget.SSHOptions` for the remote carry. That gives one seam for the agent environment.
- Per-session values (`SORTIE_ISSUE_ID`, `SORTIE_DISPATCH_ID`, and others) already exist, but only in the MCP sidecar's environment in `.sortie/mcp.json` and in hook environments. The agent process itself inherits only the orchestrator's environment.
- Runtime state has a single writer, the orchestrator event loop. `POST /api/v1/refresh` already reaches it through a callback in `server.Params`.
- The turn timeout is a per-turn context deadline in the worker (`runBoundedTurn`). Stall detection runs in reconciliation and compares the time of the last agent event with `agent.stall_timeout_ms`.
- Outbound events go through `route.Router`, keyed by a fixed `domain.EventType` catalog.
- The HTTP server has no authentication. It binds to `127.0.0.1` by default.
- The spike showed that a held turn looks like an ordinary completed turn to Sortie. Nothing in the turn protocol needs to change.

## Goals / Non-Goals

**Goals:**
- Small, additive patches, each in its own commit, that rebase cleanly onto upstream.
- No change to how adapters talk to their runtimes.

**Non-Goals:**
- Sortie does not relay prompts or steering to agents. That stays in the ACP broker.
- No user accounts or roles. One shared control token is enough for one operator team.
- No time limit on a hold in this change. See Risks.
- Hold state does not survive a restart, because the running workers do not survive one either.

## Decisions

### D1. Session environment through `StartSessionParams`, applied at the launch seam

`StartSessionParams` gains a `SessionEnv` list of name and value pairs. The worker fills it from the values it already has for the run: the dispatch ID, rule name, chain ID, attempt, workspace, and the server address. `LaunchTarget` keeps the list. `BindWorkspace` sets the variables last, so they win over the inherited environment. `SSHOptions` adds them to the carried settings, which already travel on standard input, never as arguments. The credential-check launch sets `SORTIE_SESSION_PURPOSE=credential-check`; work sessions set `work`.

Alternatives:
- Change each adapter. Rejected: six places to keep in step, and it misses `AuxiliaryCommand`.
- Let wrappers read `.sortie/dispatch.json`. Rejected: no server address, a race at session start, and the file is writable by the agent.

### D2. Hold state on the running entry, changed only by the event loop

The running entry gets `HeldSince`, `HoldReason`, `Holder`, and `HeldTotal`. The server receives `HoldFn` and `ReleaseFn` callbacks, built like `RefreshFn`. Each sends a control message to the event loop and waits for the loop's reply, which gives the `200`, `404`, or `409`. The worker exit path ends any open hold and stores `HeldTotal` in run history. A migration adds `held_ms` to `run_history`.

### D3. Clocks that can pause

- **Stall:** reconciliation skips a held entry. On release, the loop sets the entry's stall base to the release time, so a hold never counts as silence.
- **Turn timeout:** `runBoundedTurn` replaces its fixed `context.WithTimeout` with a small turn clock that the event loop and the worker goroutine share. The clock's deadline is the turn start plus `turn_timeout_ms` plus the time held during that turn. A helper goroutine sleeps until the current deadline, checks it again, and cancels the turn only if the deadline has really passed and the run is not held.

Alternative: have the broker send keepalive updates. Rejected: fake activity hides real stalls, and the hold would not be visible to Sortie or to metrics.

### D4. Escalation is a new orchestrator event

`domain.EventType` gains `session.escalated`, allowed by `FromOrchestrator`. The escalate handler sends the request to the event loop. The loop checks for a running worker and the per-issue 60-second window, masks the message with `redact.Mask`, builds the notification envelope, and passes it to `Router.Route`. Delivery reuses the existing asynchronous delivery path. Tracker comments come for free when a `tracker_comment` entry lists the event.

Alternative: the broker posts to Slack itself. Rejected: it would duplicate destination configuration, secrets handling, and pacing.

### D5. Auth as a wrapper on state-changing routes

A new `server.control_token` setting is resolved with `$VAR` and registered for masking. One wrapper guards refresh, hold, release, and escalate, comparing tokens in constant time. Startup validation rejects a non-loopback `server.host` without a token. Read-only routes are not wrapped.

Alternatives:
- A Unix socket for control. Rejected: web and phone clients need HTTP.
- Mutual TLS. Rejected: too much operational weight for one operator team.

### D5a. Per-session scoped tokens for the broker

**Problem.** The ACP broker has to call hold, release, and escalate. Sortie launches the broker as the agent command, so anything Sortie gives the broker also reaches the agent. In local mode the agent runs as the same user and can read whatever the broker can: files, `/proc`, its environment. No secret can be hidden from a local agent that runs tools freely. The goal is to limit what a leaked credential can do.

**Decision.** When the worker starts a work session, it mints a token from `crypto/rand` (32 bytes, base64url). It records the token on the running entry together with the issue ID, and adds it to `SessionEnv` as `SORTIE_SESSION_TOKEN`. The auth wrapper then works like this:
1. The control token is accepted everywhere.
2. Otherwise it looks up the token among the running entries. A token that matches no running entry gets `401`.
3. A token that matches a running entry gets `403` unless the route is hold, release, or escalate and the issue in the path is the entry's own.

The token is removed with the running entry, so it ends with the run. Each token is registered with the masking registry when it is minted and removed when the run ends.

**Why not the alternatives:**
- An operator token file named by a broker flag: it needs per-workflow operator setup; a leaked token can act on any issue; and it protects nothing in local mode anyway.
- The operator token in the environment, stripped by the broker: Sortie cannot tell whether `agent.command` is a broker, so every agent without a broker would receive a full-power token.
- The broker inside the Sortie process: no token would be needed, but it would restructure Sortie's agent layer far away from upstream.

**Accepted abuse.** An agent that finds its own token can hold its own run, which pauses the stall watchdog, and can escalate about itself. Limits that still apply: the turn timeout, extended only by real held time; tracker reconciliation; the token ceiling; the 60-second escalation rate limit; and the visible held state. The stall watchdog exists to catch hung agents, not hostile ones. Hostile agents are the sandbox's job (change `execution-environment`).

### D6. Commit and documentation discipline

There is one commit per capability, plus one for its docs. Each commit updates the fork's docs in the same change: the architecture sections on the HTTP server, observability, and notifications; `docs/workflow-reference.md`; and `CHANGELOG.md`. ADRs stay untouched; any ADR that becomes stale is reported instead.

## Risks / Trade-offs

- [A hold that nobody releases keeps a run and its agent slot forever] → The broker releases the hold when the last viewer disconnects or hands back (change `acp-broker`). The held-runs gauge and the hold start time in `/api/v1/state` allow an alert. A hard time limit can be added later as a separate requirement.
- [Held runs consume agent slots and reduce throughput] → This is accepted for now. Held time per rule is recorded, so the cost is visible before we decide on a separate limit for held runs.
- [The agent can read its session token] → By design (see D5a). The token is scoped to its own run, so the worst case is self-hold or self-escalation, both bounded and visible. The operator control token never enters the agent environment.
- [A session token appears in agent output] → Tokens are registered for masking when minted, so logs, status statements, and notifications show them masked.
- [Turn clock races between the worker and the event loop] → The clock has its own mutex and is read only by the deadline helper. Unit tests cover holds that begin before, during, and right at the deadline.
- [Upstream changes the worker or server code these patches touch] → The patches stay small and in separate commits. Any rebase conflict lands in at most four files: the worker, reconcile, the server router, and the launch target.

## Migration Plan

1. Deploy the fork build. The new `run_history.held_ms` column is added by migration and defaults to `0`.
2. Deployments that bind to loopback need no change.
3. A deployment that binds to a non-loopback address sets `server.control_token` before upgrading. Otherwise it fails to start with an error that names the setting.
4. Rollback means deploying the previous build. The extra column is ignored by older builds.
