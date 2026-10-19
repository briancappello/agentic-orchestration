# ACP broker guide

`acp-broker` sits between Sortie and an Agent Client Protocol (ACP) agent. Sortie drives the session as usual. People can watch it, steer it, interrupt it, and hand it back, all in the same session. When the agent asks for permission or asks a question that nobody watching answers, the broker asks Sortie to call people.

This guide is for operators. For the upstream work the broker depends on and what each agent does over ACP, see [ACP broker notes](notes.md).

## Build

The broker is one binary, built from this directory with the Go toolchain alone. `make build` builds `bin/acp-broker`, or:

```sh
go build -o acp-broker ./cmd/acp-broker
```

## Quick start

Run the broker in front of an agent, without Sortie. The broker reads the client's requests on standard input and writes the agent's answers on standard output, so this prints the agent's `initialize` result:

```sh
printf '%s\n' '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":1}}' \
  | ./acp-broker -key demo -- opencode acp
```

The broker exits when the agent exits, with the agent's exit code. While it runs, `./acp-broker ls` lists it, and `./acp-broker attach -key demo` shows the session.

## Use it with Sortie

Prefix `agent.command` of an `agent-client-protocol` workflow with the broker and its flags, then `--`, then the agent command. Removing the prefix rolls the change back.

```yaml
agent:
  kind: agent-client-protocol
  command: /usr/local/bin/acp-broker -http 127.0.0.1:7700 -viewer-token-file /etc/sortie/viewer-token -- env XDG_CONFIG_HOME=/var/lib/sortie/opencode-config opencode acp

server:
  port: 7678

notifications:
  - kind: slack
    webhook_url: $SORTIE_SLACK_WEBHOOK
    events: [session.escalated]
```

Under Sortie the broker reads the session environment Sortie gives every agent launch:

| Variable | What the broker does with it |
| --- | --- |
| `SORTIE_ISSUE_IDENTIFIER` | Registry key, the issue in calls to Sortie, and a label on every telemetry span. |
| `SORTIE_SESSION_PURPOSE` | `credential-check`: the broker only relays. It registers nothing, opens no socket or HTTP listener, and sends permission requests to Sortie at once. |
| `SORTIE_API_URL` | Where it calls Sortie's hold, release, and escalate endpoints. |
| `SORTIE_SESSION_TOKEN` | The bearer token of those calls. It authorizes them for this run's issue only and expires with the run. The broker removes it from the agent's environment and passes every other variable through. |
| `SORTIE_RULE`, `SORTIE_CHAIN_ID`, `SORTIE_ATTEMPT` | Shown in the registry record, and labels on every telemetry span. |
| `SORTIE_DISPATCH_ID` | A label on every telemetry span, and the Langfuse session ID. |

When any of the first four is missing, or the purpose is not `work`, the broker makes no Sortie calls and works as a plain relay with viewers.

What the broker tells Sortie:

- **Hold** while people hold the session: after an interrupt (reason `interrupt`), while Sortie's turn waits for steers to land (reason `steer`), and while a permission request or question waits for an answer. Sortie then pauses the run's stall and turn clocks. The broker releases the hold on handback, when the request is resolved, and on exit. Calls that fail are retried with capped backoff and never block the session.
- **Escalate** a permission request or question that nobody answers. List `session.escalated` in a `notifications` entry to receive it.

Sortie never gives the broker its operator `server.control_token`. In local mode the agent runs as the same user as the broker and can read the session token anyway, so a leaked token can at most hold or escalate its own run. Running the agent in a sandbox VM, with the broker on the host, closes that gap.

To do that, use the `smolvm` execution environment and put the broker in `environment.host_prefix` instead of `agent.command`. The broker then runs on the host with the session token and the API URL, and Sortie puts the VM launch behind it, so only the agent runs in the VM and never sees either value:

```yaml
agent:
  kind: agent-client-protocol
  command: opencode acp

environment:
  kind: smolvm
  host_prefix: [/usr/local/bin/acp-broker, -http, 127.0.0.1:7700, -viewer-token-file, /etc/sortie/viewer-token, --]
  smolvm:
    pack: /var/lib/smol-builder/app.smolmachine
```

`host_prefix` wraps only the session and its credential check, not Sortie's auxiliary commands. See the [smolvm environment guide](../../sortie/docs/smolvm-environment-guide.md) and [the `environment` block](../../sortie/docs/workflow-reference.md#212-environment--execution-environment).

## Flags

| Flag | Default | Meaning |
| --- | --- | --- |
| `-key KEY` | `SORTIE_ISSUE_IDENTIFIER`, else the working directory's base name | Registry key. Sanitized to letters, digits, `-`, and `_`. |
| `-registry-dir DIR` | `$XDG_RUNTIME_DIR/acp-broker` | Where records, sockets, and logs live. Created with mode `0700`. |
| `-socket PATH` | `KEY.PID.sock` in the registry directory | Viewer socket, created with mode `0600`. |
| `-log PATH` | `KEY.log` in the registry directory | Broker log. The agent's standard error goes to the broker's. |
| `-http ADDR` | off | HTTP listener for web and phone viewers. Requires `-viewer-token-file`. |
| `-viewer-token-file PATH` | none | File holding the viewer token. Keep it at mode `0600`. |
| `-public-url URL` | none | Address people use to reach the HTTP listener. Escalations link to it; an `https` URL makes the session cookie `Secure`. |
| `-cookie-ttl D` | `12h` | Lifetime of a browser session cookie. |
| `-escalate-after D` | `30s` | How long a permission request or question waits for a viewer before Sortie is asked to call someone. With no viewer attached, the broker asks at once. |
| `-permission-timeout D` | `10m` | How long a request waits for any answer before the driver decides. `0` waits without a bound. Under Sortie, the driver refuses every request. |
| `-handback-grace D` | `60s` | How long people keep the session after the last viewer leaves. |
| `-replay-events N`, `-replay-bytes N` | `5000`, `16777216` | Bounds of the history a viewer receives when it attaches. |
| `-otlp-endpoint URL` | off | OTLP/HTTP endpoint, such as `http://127.0.0.1:4318`. Each turn is exported there as a trace. See [Telemetry](#telemetry). |
| `-otlp-headers-file PATH` | none | File of `Name: value` lines sent as headers with every export, for example the Collector's credentials. Blank lines and lines starting with `#` are skipped. Keep it at mode `0600`. |
| `-telemetry-content` | off | Also export prompt text, agent messages, and tool input and output, masked and cut. |
| `-telemetry-content-max N` | `4096` | Bytes of each transcript value exported with `-telemetry-content`. |

## Tokens

- **Viewer token.** One shared token per broker, read from `-viewer-token-file`. HTTP clients send it as `Authorization: Bearer <token>`. The broker never reads a token from a URL. Browsers trade it once for a cookie (see below). Do not put it in the environment of the agent command: the broker passes that environment to the agent.
- **Session token.** `SORTIE_SESSION_TOKEN`, minted by Sortie per run. See [Use it with Sortie](#use-it-with-sortie).
- **Socket access.** The Unix socket needs no token. Its mode `0600` in a `0700` directory limits it to the user the broker runs as.

## Viewers

Every broker serves the same protocol on its socket and, with `-http`, over HTTP.

**Through Sortie.** A broker with `-http` that runs under Sortie reports its address and viewer token to Sortie once its listener is up. A client with Sortie's control token finds every running session without access to this host's files: `GET /api/v1/state` lists each running issue's `broker.http_url`, and `GET /api/v1/<identifier>/broker` returns the address with the token. The plan workbench attaches to workers this way. With several workers at once, give `-http` port `0` (`127.0.0.1:0`) so each broker binds a port of its own. A broker that cannot reach Sortie keeps relaying and retries the report.

**From a terminal:**

```sh
acp-broker ls                         # live sessions: key, issue, rule, agent, session, HTTP URL, socket
acp-broker attach -key LIVE-1         # history so far, then live events; type a line to prompt
acp-broker attach -key LIVE-1 -follow # move to the issue's next session when this one ends
acp-broker send -key LIVE-1 interrupt # one command
```

In `attach`, a line starting with `/` is a command: `/interrupt`, `/handback`, `/state`, `/steer TEXT`, `/permit ID OPTION`. Any other line is a prompt, which needs the session interrupted first.

**Commands.** Each is one JSON object, such as `{"op":"steer","text":"focus on the parser"}`:

| Op | Effect |
| --- | --- |
| `steer` | Add a message to the session without stopping anything. It is always accepted and always lands before Sortie gets control back. A steer never cancels a turn. Steers queue in order, and every steer queued at delivery goes to the agent as one message, one text block each. The broker delivers them in one of three ways. While any turn runs on an agent that advertises steering, it injects them into that turn. While a turn runs on an agent without native steering, they wait for that turn to end. When no turn runs, they run at once as a turn of their own in the same session. If Sortie's turn ends while steers are pending, the broker withholds the agent's answer from Sortie and holds the run with reason `steer`. It queues Sortie's next prompt, runs the steers, and then passes the answer on unchanged. A native steer the agent answers `promptRequired`, because the turn ended first, runs as a turn of its own instead. Under an interrupt, steers land the same way and the floor stays with people. |
| `interrupt` | Take the floor, like Esc in a terminal agent. A running turn is cancelled. For Sortie's turn, its request is held open and its prompts are queued. Queued steers then go out. People keep the floor until `handback`, even when nothing runs. Also accepted as `takeover` and `cancel`. |
| `prompt` | Send a prompt in the same session, after an interrupt. |
| `handback` | Return the floor. The held driver turn ends with `end_turn`, or the answer withheld from it is passed on, and a queued driver prompt goes to the agent. |
| `permit` | Answer a waiting permission request: `id` as the `permission` event showed it, and `option` as an option ID or kind (`allow_once`, `reject_once`), or `cancel`. |
| `state` | Return the current state. |

A refused command returns an `error` event naming the reason and changes nothing.

**Events.** Each carries `seq`, which rises by one per event, and `time`. Types are `state` (floor, session ID, driver turn, steering support, and `steersQueued`, the steers not yet landed), `update` (a raw `session/update`), `permission`, `permission_resolved`, `result`, and `error`. A viewer that attaches receives the current state, then the history the broker kept, then live events. The initial state, command replies, and the note that history was cut short carry `seq` 0, because they are not part of the session's history.

**Over HTTP:**

| Endpoint | Meaning |
| --- | --- |
| `GET /events` | Server-Sent Events. Each event's ID is its `seq`; a client that reconnects with `Last-Event-ID` receives only what it missed, preceded by an `error` event when part of it is no longer kept. A comment line every 15 seconds keeps the connection open. |
| `POST /commands` | One command. Answers `200` with the new state, `409` with the reason when it was refused, `400` for a malformed command. |
| `GET /state` | The current state. |
| `POST /login` | With the bearer token: answers `204` and sets an `HttpOnly`, `SameSite=Strict` session cookie, so a browser's `EventSource` needs no header. Cookies live in memory and end when the broker exits. |
| `POST /logout` | Ends the cookie's session. |

```sh
curl -N -H "Authorization: Bearer $(cat viewer-token)" http://127.0.0.1:7700/events
curl -H "Authorization: Bearer $(cat viewer-token)" -d '{"op":"interrupt"}' http://127.0.0.1:7700/commands
```

A viewer that stops reading is disconnected; it never slows the session. Browsers open about six HTTP/1.1 connections per host, which limits how many sessions one tab can watch; a TLS front end with HTTP/2, such as Tailscale serve, removes that limit and lets the cookie be `Secure`.

**Permission requests and questions.** While viewers are attached, a request goes to them first, and the first valid answer reaches the agent. A request is a question when none of its options allows anything; it is escalated with kind `question` and its option names. A request that waits `-escalate-after`, or arrives with nobody watching, is escalated once through Sortie, and the run is held while it waits. After `-permission-timeout` the driver decides. Cancelling the turn that asked answers the request as `cancelled`.

**Leaving.** When the last viewer leaves while people hold the session and no human prompt runs, the broker hands back after `-handback-grace`. Attaching again within the grace keeps the floor.

## Telemetry

With `-otlp-endpoint`, the broker exports every turn of its session as a trace: Sortie's turns, human prompts, and steer turns. Use it to see what each turn did and cost, per issue and per stage, in Langfuse or any OTLP backend. Sortie's own Prometheus metrics are separate and do not change.

**What a trace holds.** Each turn is its own trace. Its root span is the turn, and its child spans are the turn's tool calls.
- **The turn span:**
  - its origin: `driver`, `human`, or `steer`;
  - the stop reason, with `cancelled_for: interrupt` when a viewer interrupted it;
  - the model, from the agent's session configuration;
  - the token usage the agent reported for the turn;
  - an event for each steer the agent took into the running turn natively.
- **Each tool call span:** its kind, title, and final status. A failed tool call is marked as an error.
- **Every span:** the session's labels from Sortie (`SORTIE_ISSUE_IDENTIFIER`, `SORTIE_RULE`, `SORTIE_CHAIN_ID`, `SORTIE_DISPATCH_ID`, `SORTIE_ATTEMPT`), the ACP session ID, and the agent's name and version.

A credential-check broker exports nothing.

**The pipeline.** Run an OpenTelemetry Collector next to the broker, and point the broker at its loopback OTLP/HTTP receiver. The Collector forwards traces to Langfuse, so the broker never holds Langfuse's keys. `examples/telemetry/collector.yaml` is a working configuration. Give it `LANGFUSE_OTLP_ENDPOINT` (`<langfuse>/api/public/otel`) and `LANGFUSE_AUTH`, the base64 of `<public key>:<secret key>`. Self-hosted Langfuse needs v3.22.0 or later for its OTLP endpoint.

```sh
export LANGFUSE_OTLP_ENDPOINT=http://127.0.0.1:3000/api/public/otel
export LANGFUSE_AUTH=$(printf '%s' "pk-lf-...:sk-lf-..." | base64 -w0)
otelcol-contrib --config examples/telemetry/collector.yaml
```

```yaml
agent:
  command: acp-broker -otlp-endpoint http://127.0.0.1:4318 -- opencode acp
```

Export runs apart from the session. A slow or unreachable endpoint never delays the driver, the agent, or viewers.
- Ended spans wait in a buffer of 2048. When it is full, the oldest are dropped, and the count is logged at most once a minute.
- Failed exports are retried with backoff up to 30 seconds, honoring `Retry-After`. Any `4xx` other than `429` drops the batch.
- When the session ends, the broker tries once more for up to 3 seconds, then exits with the agent's exit code.

The broker reads its telemetry configuration only from its flags. It does not use `OTEL_*` variables, because it passes its environment to the agent, and agents such as Claude Code read those variables themselves.

**In Langfuse.**
- Each turn is a generation, priced from its model and usage. Each tool call is a tool observation.
- A Sortie dispatch is one Langfuse session, keyed by `SORTIE_DISPATCH_ID`, or by the ACP session ID without Sortie.
- The labels are top-level metadata keys: `issue`, `rule`, `chain_id`, `dispatch_id`, `attempt`, `origin`, and `agent`.
- **Cost per stage** is a filter on `rule`, or on `chain_id` for one ticket's chain. In a dashboard, or through the v2 metrics API:

```sh
curl -u "$PK:$SK" -G "$LANGFUSE/api/public/v2/metrics" --data-urlencode 'query={
  "view": "observations",
  "metrics": [{"measure": "totalCost", "aggregation": "sum"}],
  "dimensions": [],
  "filters": [{"column": "metadata", "operator": "contains", "key": "rule", "value": "implement", "type": "stringObject"}],
  "fromTimestamp": "2026-10-01T00:00:00Z", "toTimestamp": "2026-11-01T00:00:00Z"}'
```

**Model names Langfuse cannot price.** Langfuse prices a generation when a model definition's pattern matches its model name. OpenCode reports the full name, such as `anthropic/claude-haiku-5-5`, which Langfuse's own definitions match. Claude reports the alias it was configured with, such as `haiku`. Add a definition for the alias, with the prices of the model it currently stands for: in Project Settings > Models, or through the API.

```sh
curl -u "$PK:$SK" -H 'Content-Type: application/json' -X POST "$LANGFUSE/api/public/models" -d '{
  "modelName": "claude-code-haiku-alias", "matchPattern": "(?i)^haiku$", "unit": "TOKENS",
  "pricingTiers": [{"name": "Standard", "isDefault": true, "priority": 0, "conditions": [],
    "prices": {"input": 1e-07, "output": 5e-07, "cache_read_input_tokens": 1e-08, "cache_creation_input_tokens": 1.25e-07}}]}'
```

The usage keys are `input`, `output`, `cache_read_input_tokens`, `cache_creation_input_tokens`, and `total`, with `reasoning` when the agent reports it. Langfuse requires these counts not to overlap. OpenCode and Claude report them that way: input excludes cached tokens, and the total is their sum. The broker exports them unchanged.

**Masking.** Before a span leaves, the broker replaces known secrets in every exported string with `[redacted]`. Known secrets are:
- `SORTIE_SESSION_TOKEN`;
- the values of variables in its environment whose names mark them as secrets (ending in `TOKEN`, `KEY`, `SECRET`, `PASSWORD`, and similar);
- the values in `-otlp-headers-file`.

Tool titles are exported, masked and cut to 200 characters. Some agents put the command in the title. Transcript content is not exported unless you add `-telemetry-content`; it then goes out masked and cut to `-telemetry-content-max` bytes. Masking matches known values only, not secret-looking patterns: a credential the agent reads from a file is not known to the broker. Keep content off unless the agent runs where it cannot reach secrets, such as a sandbox. Viewers always see the session unmasked.

## Isolate the agent's own configuration

The broker runs whatever command follows `--`. Agents load user-level configuration, hooks, plugins, and MCP servers by default, and those then run inside every Sortie session. Give each agent a configuration home of its own in the command, as below. The broker's job is the session, not the agent's setup.

**OpenCode (`opencode acp`).** Point `XDG_CONFIG_HOME` at a directory that holds only the `opencode/opencode.json` Sortie runs should use, with the model set there. OpenCode has no native steering, so a steer waits for the running turn to end and then runs as a same-session turn. It reports usage on each prompt result. It asks for permission over ACP only for tools its configuration sets to `ask`.

```sh
acp-broker -- env XDG_CONFIG_HOME=/var/lib/sortie/opencode-config opencode acp
```

**Claude (`claude-agent-acp`).** Native steering. Add `"disableAllHooks": true` to the workspace's `.claude/settings.json`, for example from a `hooks.after_create` script; otherwise the user's own hooks run inside the session. The adapter loads user-level MCP servers too, so run it under an account or a `HOME` that has none you do not want.

```yaml
hooks:
  after_create: |
    mkdir -p .claude
    printf '%s\n' '{"disableAllHooks": true}' > .claude/settings.json
agent:
  kind: agent-client-protocol
  command: acp-broker -- claude-agent-acp
```

**Pi (`pi-acp`).** Pi runs tools without asking, which is why it belongs in a sandbox. `examples/pi` holds a wrapper and an extension: `PI_ACP_PI_COMMAND` names the wrapper, and `PI_SORTIE_AGENT_DIR` is a Pi agent directory just for Sortie runs, with the provider and model set there. Steering and per-turn usage wait on upstream work; see the notes.

```sh
acp-broker -- env PI_ACP_PI_COMMAND=/opt/acp-broker/examples/pi/pi-sortie \
  PI_SORTIE_AGENT_DIR=/var/lib/sortie/pi-agent pi-acp
```
