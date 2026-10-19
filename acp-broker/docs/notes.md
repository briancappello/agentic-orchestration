# ACP broker notes

The ACP broker sits between Sortie and an ACP agent. Sortie and a human
share one agent session through it. Sortie drives the session by default.
A human can watch it, interrupt it, send prompts into it, and give control
back to Sortie.

This file records the upstream work that the broker depends on or could
replace, and what each agent does over ACP. Check each item again before
you change the broker's protocol behavior. To run the broker, see the
[ACP broker guide](guide.md).

## Upstream ACP work to track

Last checked: 2026-10-11.

### Pull requests

| PR | Title | State | Why it matters |
| --- | --- | --- | --- |
| [#533](https://github.com/agentclientprotocol/agent-client-protocol/pull/533) | RFD: Multi-Client Session Attach | Open | Standard way for several clients to share one session. If it lands, the broker's fan-out and attach can follow it. |
| [#1261](https://github.com/agentclientprotocol/agent-client-protocol/pull/1261) | docs(rfd): mid-turn input via session/inject (queue and steer) | Open | Standard way to add input during a turn. If it lands, a human nudge does not need cancel-then-prompt. |
| [#986](https://github.com/agentclientprotocol/agent-client-protocol/pull/986) | RFD: session/status — session liveness check | Open | Standard liveness check. The broker can use it to report that a held session is still alive. |

### Agent adapters

| Item | State | Why it matters |
| --- | --- | --- |
| [svkozak/pi-acp#115](https://github.com/svkozak/pi-acp/pull/115) `_session/steering` | Open, mergeable | Gives pi native mid-turn steering over ACP. Verified with the broker on 2026-10-11. |
| [svkozak/pi-acp#106](https://github.com/svkozak/pi-acp/issues/106) usage updates from session stats | Open | Per-turn usage and cost on the prompt result. Pi's `get_session_stats` already has the totals. |
| [svkozak/pi-acp#145](https://github.com/svkozak/pi-acp/pull/145) pass MCP servers to pi | Open | Would replace the wrapper and extension in `examples/pi`. |

### RFDs

| RFD | State | Why it matters |
| --- | --- | --- |
| [Agent Extensions via ACP Proxies](https://agentclientprotocol.com/rfds/proxy-chains) | Draft | Defines `proxy/initialize` and `proxy/successor` for a chain of proxies. The broker is a proxy. If this stabilizes, the broker can speak it. |
| [End-Turn Token Usage](https://agentclientprotocol.com/rfds/end-turn-token-usage) | Draft | Adds per-turn token counts to the prompt response. Today only `usage_update` (`used`, `size`, optional `cost`) is stable. |
| [Streamable HTTP & WebSocket Transport](https://agentclientprotocol.com/rfds/streamable-http-websocket-transport) | Active | A standard remote transport. Human viewers could attach over it instead of a broker-specific API. |

### Vendor extensions in use

- `claude-agent-acp` 0.89.1 advertises `_meta.steering.supported: true` in its `initialize` result. It also serves the `_session/steering` request, which injects a message into the turn that is running. Without a running turn it starts a new turn. With `_meta.steering.idleBehavior: "promptRequired"`, it instead returns `{"outcome":"promptRequired"}` so the client can send a normal `session/prompt`. If #1261 lands, the standard method should replace this extension.

## Runtime observations

Observed on 2026-10-11 through Sortie's `agent-client-protocol` kind.

| Runtime | Steering | Per-turn usage | Model | Notes |
| --- | --- | --- | --- | --- |
| `opencode acp` 1.18.29 | Not advertised. A steer waits for the running turn to end, then runs as a turn of its own in the same session; the driver's answer is withheld until it lands. | `PromptResponse.usage` (input, output, cached read and write, total). The counts do not overlap: input excludes cached tokens, and the total is their sum. A count that is zero may be left out. A cancelled turn reports all zeros. | `configOptions` entry of category `model`, full name, such as `anthropic/claude-haiku-5-5` | Asks for permission through ACP for `bash` rules set to `ask`. Option IDs are `once`, `always`, and `reject`. |
| `pi-acp` 0.0.34 with `pi` 1.1.0 | Released `pi-acp` does not advertise it. With [svkozak/pi-acp#115](https://github.com/svkozak/pi-acp/pull/115) merged locally onto `main`, it serves `_session/steering`: a steer returns `injected`, and pi delivers it after the running tool call, without cancelling the turn. | None on the prompt result; `usage_update` carries context occupancy only. Pi's session files record usage and cost for each assistant message. Telemetry marks Pi turns as reporting no usage. | Not checked. | Pi runs tools without asking. That is the reason to run it in a sandbox. `pi-acp` asks for permission only for Pi extension dialogs. `pi-acp` does not pass ACP MCP servers to pi. Pi has MCP built in, and `examples/pi` registers Sortie's servers through an extension, loaded by a wrapper that `PI_ACP_PI_COMMAND` names. Project files under `.pi` load only in trusted projects, and RPC mode does not ask; a dedicated `PI_CODING_AGENT_DIR` sets the model instead. Capabilities: `loadSession`, `list`, `delete`; no `resume` or `close`. |
| `claude-agent-acp` 0.89.1 | `_session/steering` | `PromptResponse.usage`, plus `_meta.quota.model_usage` per model. The counts do not overlap, like OpenCode's. | `configOptions` entry of category `model`, holding the configured alias, such as `haiku`; `_meta.quota.model_usage` names the model served (`claude-haiku-5-5` for `haiku` on 2026-10-11) | Ignored the allow rules in the workspace's `.claude/settings.json` and asked for permission anyway. User-level hooks and MCP servers load inside the session. |

Facts about Sortie that shape the broker:

- Each dispatch starts two agent processes: a credential check, then the work session. Each dispatch is a new process and a new session. So viewers find a session by its issue key, not by a fixed socket path. Sortie marks the credential check with `SORTIE_SESSION_PURPOSE=credential-check`, and the broker only relays it.
- Sortie refuses every permission request. The broker therefore asks viewers first, escalates through Sortie when nobody answers, and holds the run while the request waits; only after its answer timeout does the request reach Sortie, which refuses it.
- A turn that a viewer interrupted and handed back looks like an ordinary completed turn to Sortie. So does a turn whose answer the broker withheld while steers ran. The broker holds the run while people hold the session or steers run, so Sortie's stall and turn clocks pause.
- Sortie sends its next prompt within about a millisecond of a turn ending, and closes the session within a few milliseconds of its last turn. That is why the broker withholds the turn's answer while steers are pending: a steer queued for "after this turn" would otherwise race Sortie, or be lost after the last turn.
- Native steering with `idleBehavior: "promptRequired"` returns `{"outcome":"promptRequired"}` when no turn runs, and the agent drops the text. The broker therefore sends native steers only while a turn runs. An idle session is steered with a same-session turn for every agent. A native steer can still lose the race with the end of the turn. The driver's answer is withheld while it is in flight, so on `promptRequired` the broker runs the steer as a same-session turn before the driver continues. It never resends it natively. Viewers see only the final outcome.

## Deferred: Pi parity

Pi works through the broker today, but not on par with OpenCode and Claude. The gaps wait on upstream `pi-acp` work, tracked in the table above. Until they land:

| Gap | Today | Closes with |
| --- | --- | --- |
| Native steering | Released `pi-acp` does not advertise `_session/steering`, so a steer to Pi waits for the running turn to end and then runs as a same-session turn. | [svkozak/pi-acp#115](https://github.com/svkozak/pi-acp/pull/115). Once it is released, the broker picks native steering up from the `initialize` result with no change. |
| Per-turn usage | The prompt result carries no usage, so Sortie records Pi runs as unmeasured, and telemetry marks Pi turns as reporting none. | [svkozak/pi-acp#106](https://github.com/svkozak/pi-acp/issues/106). |
| MCP servers | `pi-acp` does not pass ACP MCP servers to Pi. `examples/pi` registers Sortie's servers through a Pi extension, loaded by a wrapper that `PI_ACP_PI_COMMAND` names. | [svkozak/pi-acp#145](https://github.com/svkozak/pi-acp/pull/145); then drop the wrapper and extension. |

Pi parity is not part of the broker's supported scope until these land. Check them again before each `pi-acp` upgrade.

### Related projects

These are references, not dependencies.

- [lsaether/acp-mux](https://github.com/lsaether/acp-mux) (Rust, MIT): WebSocket mux with pending-permission tracking, cancel translation, session rebinding on `session/load`, and a replay log. Its logic can be reused with attribution.
- [ElleNajt/acp-multiplex](https://github.com/ElleNajt/acp-multiplex) (Go, no license): one primary client and N secondary clients, ID rewriting, and an update replay cache. Use its ideas only. Do not copy its code unless it gets a license.
