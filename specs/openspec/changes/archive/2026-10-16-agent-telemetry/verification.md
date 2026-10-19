# Verification: agent-telemetry

## Task 4.1: a real OpenTelemetry Collector accepts the broker's exports

Code: `acp-broker`. Collector: `otelcol-contrib` 0.162.0 in a podman container (`docker.io/otel/opentelemetry-collector-contrib:latest`), host network, the OTLP/HTTP receiver on `127.0.0.1:4318`, and the `debug` exporter at `verbosity: detailed`. Harness: `/tmp/opencode/otel-live`.
- `agent.py` is a scripted ACP agent. It reports a model in `session/new` `configOptions`. On each prompt it sends two tool calls (one completed, one failed) and an agent message, then answers with usage.
- `driver.py` sends `initialize`, `session/new`, two prompts, and then closes the broker's input.

```
podman run -d --name otel-live-debug --network host \
  -v $PWD/collector-debug.yaml:/etc/otelcol-contrib/config.yaml:Z \
  docker.io/otel/opentelemetry-collector-contrib:latest
env SORTIE_ISSUE_IDENTIFIER=LIVE-7 SORTIE_RULE=implement SORTIE_CHAIN_ID=c-77 SORTIE_DISPATCH_ID=DISPATCH77 \
    SORTIE_ATTEMPT=1 SORTIE_SESSION_PURPOSE=work \
  python3 driver.py 2 -- ./acp-broker -otlp-endpoint http://127.0.0.1:4318 -- python3 agent.py
prompt 0 -> {"stopReason": "end_turn", "usage": {"inputTokens": 1200, ...}}
prompt 1 -> {"stopReason": "end_turn", "usage": {"inputTokens": 1200, ...}}
broker exit 0
```

The Collector logged 6 spans (2 turns and 4 tool calls). There were no errors, rejections, or dropped-attribute counts. Excerpt of a turn span from the `debug` exporter:

```
Resource attributes:
-> service.name: Str(acp-broker)
-> service.version: Str((devel))
InstrumentationScope acp-broker (devel)
Span #2
Trace ID       : 2c9f39fb6aa22d73f6af9ca90502ad65
Parent ID      :
ID             : 127eaa3f19223ede
Name           : turn driver
Kind           : Internal
Status code    : Unset
Attributes:
-> langfuse.session.id: Str(DISPATCH77)
-> langfuse.trace.name: Str(agent turn (driver))
-> langfuse.trace.metadata.issue: Str(LIVE-7)
-> langfuse.trace.metadata.rule: Str(implement)
-> langfuse.trace.metadata.chain_id: Str(c-77)
-> langfuse.trace.metadata.dispatch_id: Str(DISPATCH77)
-> langfuse.trace.metadata.attempt: Str(1)
-> langfuse.trace.metadata.origin: Str(driver)
-> langfuse.trace.metadata.agent: Str(scripted-agent)
-> sortie.issue.identifier: Str(LIVE-7)
   ... sortie.rule, sortie.chain.id, sortie.dispatch.id, sortie.attempt ...
-> acp.session.id: Str(sess-live)
-> acp.agent.name: Str(scripted-agent)
-> acp.agent.version: Str(0.1.0)
-> langfuse.observation.type: Str(generation)
-> acp.turn.origin: Str(driver)
-> acp.turn.stop_reason: Str(end_turn)
-> gen_ai.request.model: Str(anthropic/claude-haiku-4-5)
-> langfuse.observation.model.name: Str(anthropic/claude-haiku-4-5)
-> langfuse.observation.usage_details: Str({"cache_creation_input_tokens":150,"cache_read_input_tokens":8000,"input":1200,"output":340,"total":9690})
-> gen_ai.usage.input_tokens: Int(1200)
-> gen_ai.usage.output_tokens: Int(340)
```

A tool call span in the same trace, its parent being the turn:

```
Trace ID       : 2c9f39fb6aa22d73f6af9ca90502ad65
Parent ID      : 127eaa3f19223ede
Name           : tool execute
Status code    : Error
Status message : tool call failed
 -> langfuse.observation.type: Str(tool)
 -> acp.tool.call_id: Str(call_1_2)
 -> acp.tool.kind: Str(execute)
 -> acp.tool.title: Str(go test ./... with $LIVE_TEST_TOKEN)
 -> acp.tool.status: Str(failed)
```

The Collector decoded every rule the encoder owns: hex trace and span IDs, the parent link, integers as `Int`, the numeric span kind and status code, and string attributes. Every D4 attribute is present on turn and tool spans. The full output is in `/tmp/opencode/otel-live/collector-debug.log`.

## Task 4.2: self-hosted Langfuse behind the Collector, with OpenCode and Claude under Sortie

Code: `acp-broker`, with the example Collector configuration from task 5.1.

### Setup

**Langfuse.** Langfuse `4.56.0` runs from its upstream `docker-compose.yml` under podman-compose, project `lfagent`, in `/tmp/opencode/langfuse`. The local copy changes two things:
- Only the web UI is published, on `127.0.0.1:3100`. Postgres and Redis already run on this host.
- The `LANGFUSE_INIT_*` variables seed an org, a project, and API keys.

The worker started before the web container finished its database migrations, so its first load of the default model prices failed (`relation "pricing_tiers" does not exist`). Restarting the worker loaded 186 models. This is a startup race in that compose stack, not in our data.

**Collector.** `otelcol-contrib` 0.162.0 runs with `acp-broker/examples/telemetry/collector.yaml`. `LANGFUSE_OTLP_ENDPOINT` is `http://127.0.0.1:3100/api/public/otel`, and `LANGFUSE_AUTH` is the base64 of the project keys. `otelcol-contrib validate --config` passes. The example uses the current exporter name `otlp_http`: the Collector warned that `otlphttp`, the name Langfuse's docs still show, is deprecated.

**Reading the data back.** Langfuse v4 runs in "events_only" mode, where `/api/public/traces` and `/api/public/metrics` are unavailable. The checks use `/api/public/v2/observations` and `/api/public/v2/metrics`. Langfuse v4 stores span attributes in `metadata` as `attributes.<key>`, next to the `langfuse.trace.metadata.*` keys, which become top-level metadata.

### Usage keys and their meaning (settles design D4 and Open Question 4)

- **Key names.** Langfuse prices the usage keys `input`, `output`, `cache_read_input_tokens`, and `cache_creation_input_tokens` for its current Anthropic definitions (upstream `default-model-prices.json`, for example `claude-haiku-4-5-20251001` and `claude-haiku-5-5`). Those are the keys the encoder sends.
- **No overlap.** Langfuse requires the buckets not to overlap, and stores `langfuse.observation.usage_details` unchanged. Both agents already report non-overlapping counts, because each reported total equals the sum of the buckets:
  - Claude: 4 + 102 + 53643 + 307 = 54056.
  - OpenCode: 2 + 34 + 16310 + 89 = 16435.
  
  So OpenCode's `inputTokens` excludes cached reads, like Claude's, and exporting the counts unadjusted (as the spec requires) cannot double-count.

A scripted turn (`anthropic/claude-haiku-4-5`: input 1200, output 340, cached read 8000, cached write 150) was priced per key at Haiku 4.5's list prices:

```
cost 0.0038875 {'input': 0.0012, 'output': 0.0017, 'cache_read_input_tokens': 0.0008, 'cache_creation_input_tokens': 0.0001875}
```

### Cost per stage

Two scripted dispatches of chain `c-88` were filtered by the `rule` metadata through `/api/public/v2/metrics`, with filter `{"column":"metadata","operator":"contains","key":"rule","value":"<rule>","type":"stringObject"}`:

```
rule=implement -> {"data":[{"sum_totalCost":0.007775,"count_count":6}]}    (2 turns, 4 tool calls)
rule=review    -> {"data":[{"sum_totalCost":0.0038875,"count_count":3}]}   (1 turn, 2 tool calls)
```

### Live runs under Sortie

The harness is `/tmp/opencode/scs-live`, with `-otlp-endpoint http://127.0.0.1:4318` in the broker prefix. Sortie runs with `LIVE_PLANTED_TOKEN=plantedSecret-1a2b3c4d5e` in its environment, which the broker inherits. Each ticket asks the agent to run `echo plantedSecret-1a2b3c4d5e > /dev/null`, so the value appears in a tool title.

Claude reports its model as the alias `haiku`. For it, a model definition was added through `POST /api/public/models`: `claude-code-haiku-alias`, match `(?i)^haiku$`, with `claude-haiku-5-5`'s prices. The prompt result's `_meta.quota.model_usage` confirms that Claude served `claude-haiku-5-5` behind the alias. OpenCode's `anthropic/claude-haiku-5-5` matches Langfuse's own definition.

```
./run.sh opencode queue     # a driver turn, then two queued steers as one steer turn
./run.sh opencode takeover  # an interrupted driver turn, then a human turn
./run.sh claude idle        # a driver turn, an idle steer turn, a second driver turn
./run.sh claude takeover    # an interrupted driver turn, then a human turn
```

All four runs finished `succeeded`. The brokers logged no export failure. What Langfuse holds for them, read from `/api/public/v2/observations`:

```
session T3B3BF2ALP3LX777BHPEUZZUBW agent=OpenCode tools=7
   turn driver  origin=driver model=anthropic/claude-haiku-5-5 cost=0.000227455 stop=end_turn
   turn steer   origin=steer  model=anthropic/claude-haiku-5-5 cost=0.000191425 stop=end_turn steer.count=2
session XHTOTA7OEPELS6HMCMK3AAOMWV agent=OpenCode tools=4
   turn driver  origin=driver model=anthropic/claude-haiku-5-5 cost=0 stop=cancelled cancelled_for=interrupt
   turn human   origin=human  model=anthropic/claude-haiku-5-5 cost=0.00018111 stop=end_turn
session XN52HI2OPJYI6CSHI5YRPGRPXB agent=@agentclientprotocol/claude-agent-acp tools=7
   turn driver  origin=driver model=haiku cost=0.00292636  stop=end_turn
   turn steer   origin=steer  model=haiku cost=0.000634365 stop=end_turn steer.count=1
   turn driver  origin=driver model=haiku cost=0.001419895 stop=end_turn
session WSHQ227LHUHX7TWVOUIPT5BS3G agent=@agentclientprotocol/claude-agent-acp tools=4
   turn driver  origin=driver model=haiku cost=0.00260962  stop=cancelled cancelled_for=interrupt
   turn human   origin=human  model=haiku cost=0.00070395  stop=end_turn
planted value in Langfuse: False | marker: 4
TOOL T3B3BF2A title: sleep 20 && echo [redacted] > /dev/null
TOOL XN52HI2O title: echo [redacted] > /dev/null
```

Each session ID is the Sortie dispatch ID, so Langfuse groups each dispatch's turns as one session. The live workflow has no dispatch rules, so these runs carry no `rule`; the scripted runs above cover the rule filter.

OpenCode answers a cancelled turn with all-zero usage, so the interrupted OpenCode driver turn shows cost 0. That is the agent's report, exported unchanged.

### Result

| Check | Result |
| --- | --- |
| Each turn is a generation with its model and usage | yes, for every driver, steer, and human turn of both agents |
| A cost for OpenCode's model | yes, from Langfuse's default `claude-haiku-5-5` definition |
| A cost for Claude once an alias definition is added | yes, with `(?i)^haiku$` priced as `claude-haiku-5-5` |
| A dispatch groups its turns as a session | yes, the session ID is the dispatch ID |
| Filtering by `rule` sums cost per stage | yes, through the v2 metrics API |
| No secret planted in the session environment appears in any span | yes, the planted value is absent and masked in tool titles |
| Usage-detail keys settled | `input`, `output`, `cache_read_input_tokens`, `cache_creation_input_tokens`, `total` |
| OpenCode's input-token meaning | it excludes cached reads, like Claude's |

Another program on this host also exports to `127.0.0.1:4318`: an `ai_pair.daemon.heartbeat` span appeared in Langfuse. It is not ours, and the checks above filter on `issue` metadata.

## Task 5.1: documentation

Code: `acp-broker`.

The changes:
- **`acp-broker/docs/guide.md`:**
  - the four telemetry flags in the flag table, and the telemetry labels in the environment table;
  - a new "Telemetry" section: what a trace holds, the Collector-to-Langfuse pipeline, the export guarantees, why `OTEL_*` variables are not used, what Langfuse shows, the cost-per-stage filter, a model definition for Claude's alias, the usage keys, and masking.
- **`acp-broker/docs/notes.md`:** per-agent usage meaning and model reporting, and Pi's missing usage.
- **`CHANGELOG.md`** and **`docs/README.md`.**
- **`acp-broker/examples/telemetry/collector.yaml`.**

The example configuration validates:

```
$ podman run --rm -v $EX:/cfg.yaml:Z -e LANGFUSE_OTLP_ENDPOINT=http://127.0.0.1:3100/api/public/otel -e LANGFUSE_AUTH=eA== \
    docker.io/otel/opentelemetry-collector-contrib:latest validate --config /cfg.yaml
validate exit 0
```

The guide's example broker command was run as written: `acp-broker -otlp-endpoint http://127.0.0.1:4318 -- opencode acp`, with `opencode` on `PATH`, the isolated `XDG_CONFIG_HOME` in the environment, and `SORTIE_DISPATCH_ID=GUIDE-CHECK`. The collector from the example sat in front of Langfuse. One real OpenCode turn arrived priced:

```
prompt 0 -> {"stopReason": "end_turn", "usage": {"inputTokens": 4, "outputTokens": 4, "totalTokens": 13777, "cachedWriteTokens": 13769}, "_meta": {}}
broker exit 0
GENERATION turn driver anthropic/claude-haiku-5-5 {'cache_creation_input_tokens': 13769, 'input': 4, 'output': 4, 'total': 13777} 0.001723525
```

OpenCode left out the zero `cachedReadTokens`, and the export carried only the counts reported, as the spec requires.

## Final checks

- `make test` in `acp-broker/` passes, the new `otlp` package included, with no failures. `make lint` reports 0 issues.
- Broker and telemetry tests went from 82 to 117. Each new rule was also checked by breaking it and seeing its test fail; the commits' sessions list the breaks.
- `openspec validate agent-telemetry --strict --store agent-platform-specs` passes.
