## Context

See proposal.md for the motivation. The starting point is the broker as change `acp-broker` built it, with Sortie's session control from change `sortie-session-control`.

What the broker has today:
- **One event loop owns all session state.** It knows each turn's start and end:
  - a driver `session/prompt` sent to the agent (directly, or from the queue on handback) and its answer;
  - the broker's own prompts, op `prompt` (human) and op `steer-turn`, and their answers.
  - It sees every `session/update`, and native steer results.
- **It records nothing about the model.** It reads only the session ID from `session/new` and the agent's name and version from `initialize`.
- **Session environment.** `sortieclient` reads `SORTIE_API_URL`, `SORTIE_ISSUE_IDENTIFIER`, `SORTIE_SESSION_PURPOSE`, `SORTIE_SESSION_TOKEN`, `SORTIE_RULE`, `SORTIE_CHAIN_ID`, and `SORTIE_ATTEMPT`. Sortie also sets `SORTIE_DISPATCH_ID`, but the broker does not read it yet.
- **No masking.** The broker masks nothing. The broker's `internal/secrets` is a registry of known secret values, with `Add`, `AddEnviron` (secret-like names only), `Mask`, and `MaskTruncated`, on the standard library only.
- **Constraints.** The broker plan said "standard library only", with no CGo. Adding a dependency needs the user's approval.

Observed agent behavior (2026-10-11):
- **Usage on the prompt result.** Claude returns `usage` with `inputTokens`, `outputTokens`, `cachedReadTokens`, `cachedWriteTokens`, and `totalTokens`. For example 4, 102, 53643, 307, 54056: input excludes cached reads. OpenCode reports the same fields. Pi reports none.
- **The model in `session/new`.** It comes back as a `configOptions` entry of category `model`. Claude returns `currentValue: "haiku"`, an alias. OpenCode returns `anthropic/claude-haiku-5-5`.
- **Langfuse.** It accepts OTLP over HTTP, as JSON or protobuf, on `/api/public/otel/v1/traces` with Basic auth. It maps `langfuse.*` and `gen_ai.*` attributes. Trace-level attributes must be on every span to filter reliably. Real-time ingestion needs `x-langfuse-ingestion-version: 4`. Self-hosted Langfuse needs v3.22.0 or later.

## Goals / Non-Goals

**Goals:**
- Record every turn of a broker session, whatever its origin, with no change to what the driver, the agent, or viewers see.
- Make cost per stage a Langfuse filter, not a custom report.
- Keep telemetry off the relay's path. A broken pipeline must never slow down or break a session.
- Export nothing that the masking cannot vouch for unless the operator asks.

**Non-Goals:**
- OpenTelemetry in the Sortie orchestrator process, and any change to its Prometheus metrics.
- Changing Sortie's token accounting or the `agent.max_tokens` ceiling. See Open Questions.
- Metrics and logs over OTLP. Only traces are exported; Langfuse derives cost from them.
- Per-LLM-call spans inside a turn. ACP reports usage per prompt, not per model call.
- Propagating trace context to the agent or to Sortie.
- Full Pi usage. It waits for pi-acp#106.

## Decisions

### D1. A recorder fed by the loop, an exporter outside it

A new package `acp-broker/internal/telemetry` holds the span model and a recorder. The loop calls the recorder at the points it already handles:
- a prompt sent to the agent;
- a prompt answered;
- a `session/update`;
- a native steer result;
- a configuration result;
- broker stop.

These calls only touch memory and never block. When a span ends, the recorder hands it to the exporter through a bounded channel with a non-blocking send. A full channel drops the oldest span and counts it. The exporter runs on its own goroutine and owns batching, encoding, masking, retries, and the final flush.

When telemetry is off, the loop holds a no-op recorder, so the loop has no telemetry branches. The loop stays the only owner of session state. The recorder is called only from the loop goroutine and needs no locks.

Alternative considered: deriving spans from the viewer event stream (`update`, `result`, and `state` events). Rejected because those events do not carry the driver's prompt IDs or the queue-to-send moment. Reconstructing turns from them would duplicate the loop's logic and drift from it.

### D2. Turn boundaries and origin come from the loop's own state

| Origin | Starts when | Ends when |
| --- | --- | --- |
| `driver` | a driver `session/prompt` is written to the agent: on arrival, or on handback for a queued prompt | the agent answers that ID |
| `human` | the broker sends its own prompt for op `prompt` | the agent answers that ID |
| `steer` | the broker sends its own prompt for op `steer-turn` | the agent answers that ID |

A driver turn cancelled for a takeover carries `acp.turn.cancelled_for = takeover`. The loop already knows this when it holds the request. A native steer result becomes a span event `steer` on the open driver turn, with the outcome. The broker resends a native steer at most once, so a span can carry two events. On broker stop, open turns and tool calls end with `acp.unfinished = true`.

### D3. One trace per turn; a dispatch is a Langfuse session

Each turn is a trace rooted at its turn span. Tool calls are its children. Every span carries `langfuse.session.id`: the dispatch ID when set, otherwise the ACP session ID.

Alternative considered: one trace per broker session, with a long root span. Rejected for three reasons:
- The root span would end, and be exported, only at session end, and a crash would lose it. Langfuse needs the root to build a trace.
- Live cost would lag until the session ends.
- Langfuse sessions already give the per-session view: they group traces and replay them in order.

### D4. Attribute mapping

`langfuse.*` attributes drive the Langfuse view. Generic `acp.*` and `sortie.*` attributes keep the data readable in any OTLP backend.

| Data | Attributes |
| --- | --- |
| Resource | `service.name = acp-broker`, `service.version` |
| Turn span name | `turn <origin>`; `langfuse.trace.name = "agent turn (<origin>)"` |
| Observation type | turn: `langfuse.observation.type = generation`; tool call: `tool` |
| Origin, outcome | `acp.turn.origin`, `acp.turn.stop_reason`, `acp.turn.cancelled_for`, `acp.unfinished`; agent error: span status `ERROR` with the message |
| Model | `gen_ai.request.model` and `langfuse.observation.model.name` |
| Usage | `gen_ai.usage.input_tokens` and `gen_ai.usage.output_tokens`, plus `langfuse.observation.usage_details` as JSON with input, output, cached read, cached write, total, and reasoning when reported; absent usage: `acp.usage.reported = false` and no counts |
| Tool call | span name `tool <kind>`; `acp.tool.call_id`, `acp.tool.kind`, `acp.tool.title`, `acp.tool.status` |
| Labels, on every span | `langfuse.session.id`; `langfuse.trace.metadata.{issue, rule, chain_id, dispatch_id, attempt, origin, agent}`; also `sortie.issue.identifier`, `sortie.rule`, `sortie.chain.id`, `sortie.dispatch.id`, `sortie.attempt`, `acp.session.id`, `acp.agent.name`, `acp.agent.version` |
| Content, opt-in | `langfuse.observation.input` and `langfuse.observation.output` (JSON strings) on turns and tool calls |

The usage-detail key names must match the usage types of Langfuse's model price definitions, or Langfuse computes no cost. The planned keys are `input`, `output`, `cache_read_input_tokens`, `cache_creation_input_tokens`, and `total`. Task 4.2 checks them against a running Langfuse before they are fixed.

### D5. The model comes from the session configuration

The recorder keeps the current value of the `configOptions` entry with category `model`. It reads that value from:
- the `session/new` and `session/load` results;
- results of the driver's `session/set_config_option`;
- `config_option_update` session updates.

Each turn span takes the value current at its start. We read the configuration rather than the prompt result's vendor `_meta`, because it is part of ACP and every observed agent fills it. Claude's `_meta.quota.model_usage` names models per call, but Sortie found it names the serving model wrongly often enough that it does not read it (`internal/agent/clientprotocol/usage.go`).

### D6. Tool calls come from `session/update`

`tool_call` opens a child span keyed by `toolCallId` under the open turn. `tool_call_update` updates its title and status. Status `completed` or `failed` ends it, and `failed` sets span status `ERROR`.

An update with no open turn is not recorded, and the recorder counts it. This happens when an agent reports after it answered the prompt. Pairing such an update with the next turn would be wrong.

### D7. Masking at one point: the encoder

The exporter masks every string as it encodes a span: attribute values, event attributes, status messages, and resource attributes. It uses `acp-broker/internal/secrets`. Masking in the encoder, rather than where each value is recorded, means no attribute can skip it, including attributes added later.

At startup the broker registers its known secrets with `redact`:
- the session token, read before `sortieclient.AgentEnv` strips it from the agent's environment;
- `redact.AddEnviron(os.Environ())`, which registers secret-like names only;
- every value in the headers file.

Cut values go through `redact.MaskTruncated`, so a secret cut at the limit does not leak its start. The Sortie session token starts with `_` for this reason.

Transcript content is collected only when the content option is on. With it off, the recorder does not keep prompt or message text at all, so a later bug cannot export it. Tool titles are exported by default, masked and cut to 200 characters. They name the tool call, and for some agents they hold the command. They are what makes a trace readable.

Viewers keep their unmasked stream. Masking happens only in the exporter, after the loop has handed the span over.

### D8. The exporter: OTLP/HTTP JSON on the standard library (decided 2026-10-11)

The broker plan said "standard library only", and adding a dependency needs the user's approval. The user chose Option A on 2026-10-11. Both options meet the specs, and the recorder (D1) does not depend on the choice; Option B is kept below as the recorded alternative.

**Option A: OTLP/HTTP with JSON encoding, on the standard library.** About 300 to 400 lines in `acp-broker/internal/telemetry/otlp`: OTLP JSON structs, a batcher, retry with backoff, and the final flush.
- Pros:
  - No new modules.
  - It keeps the broker plan's "standard library only".
  - Both the Collector and Langfuse accept HTTP/JSON.
  - We export one signal and a few span shapes, so the surface is small.
- Cons:
  - We own encoding correctness. OTLP JSON departs from the standard protobuf JSON mapping: trace and span IDs are hex, not base64; 64-bit integers are strings; enums are numbers. Langfuse accepts malformed spans and rewrites them rather than refusing them, so mistakes can be silent.
  - No semantic-convention constants, and no built-in batch processor.
  - Moving to OTLP metrics or logs later means more hand-written code.
- Mitigation: golden tests of the JSON against the OTLP proto JSON examples, plus a check against a real Collector (task 4.1).

**Option B: the OpenTelemetry Go SDK with `otlptracehttp`.**
- Pros:
  - The reference implementation: correct encoding (protobuf), batching, retry, and standard `OTEL_*` configuration.
  - Semantic-convention packages, and an easy path to metrics, logs, or gRPC.
- Cons, measured on 2026-10-11 with a minimal program using `otlptracehttp` and the SDK batcher:
  - It compiles in 23 modules, all of them new to the broker: `go.opentelemetry.io/{otel, otel/sdk, otel/trace, otel/metric, otel/log, auto/sdk, proto/otlp, exporters/otlp/otlptrace, …/otlptracehttp}`, `google.golang.org/grpc`, `github.com/grpc-ecosystem/grpc-gateway/v2`, `google.golang.org/genproto/googleapis/{api,rpc}`, `golang.org/x/net`, `golang.org/x/text`, `github.com/go-logr/{logr,stdr}`, and `github.com/cenkalti/backoff/v5`. `protobuf`, `x/sys`, `xxhash`, and `uuid` are already present.
  - The minimal program is 21.7 MB. Today's whole broker binary is 11.7 MB.
  - The broker gains about 15 modules to vet and keep current.
  - It does not fit the broker plan's "standard library only".
  - Its `OTEL_*` variables, if used for configuration, would also reach the agent (see D10).

**Decision: Option A.** We emit one signal, from one process, in a handful of shapes, and Langfuse is the main consumer. The encoding risk is bounded by tests. Option B's cost falls on every rebase onto upstream. If we later need OTLP metrics or logs from the broker, we revisit, and the change stays inside the exporter package.

Neither option uses CGo. Tasks 2.x implement Option A.

### D9. Exporter limits

- buffer: 2048 ended spans;
- batches of up to 256 spans, or every 2 s;
- request timeout: 10 s;
- backoff from 1 s up to 30 s on network errors, `429`, and `5xx`, honoring `Retry-After`;
- other `4xx`: drop the batch and log;
- final flush: one attempt bounded by 3 s, the same bound as the final Sortie release.

The drop counter and the last export error are logged at most once a minute.

### D10. Configured by broker flags, not `OTEL_*` variables

New flags:
- `-otlp-endpoint URL`: enables telemetry;
- `-otlp-headers-file PATH`: one `Name: value` per line, mode `0600` recommended;
- `-telemetry-content`: off by default;
- `-telemetry-content-max N`: bytes per value, default 4096.

The broker passes its environment to the agent. Claude Code and other runtimes read `OTEL_*` variables and would switch on their own exporters, which double-counts and sends unmasked data. Flags keep the broker's configuration to the broker. The flags go into the `agent.command` prefix in WORKFLOW.md, like the broker's other flags. Credentials live in the headers file, not on the command line, where `ps` would show them.

### D11. The pipeline: Collector, then Langfuse

An example at `acp-broker/examples/telemetry/collector.yaml`:
- receiver: OTLP over HTTP on `127.0.0.1:4318`;
- processors: `memory_limiter` and `batch`;
- exporter: `otlphttp/langfuse` to `<langfuse>/api/public/otel`, with `Authorization: Basic ${env:LANGFUSE_AUTH}` and `x-langfuse-ingestion-version: "4"`.

The Collector decouples the broker from Langfuse. The broker never holds Langfuse keys. The Collector can buffer, retry, filter, or fan out to other backends. The broker talks to a Collector on loopback, with no credentials or with a local token.

Cost per stage in Langfuse: filter traces by the `rule` metadata, or by `chain_id` for one ticket's chain, and sum cost. The guide documents the filter. A saved Langfuse dashboard is a follow-up.

## Risks / Trade-offs

- [`redact` masks only values it was told about. A secret the agent reads from a file, or one it prints in a new form, is not known] → Transcript content is off by default. Titles are cut to 200 characters. Sandboxes keep production secrets out of the agent's reach. Pattern-based masking is an open question.
- [Tool titles can carry commands, paths, or file names, which may be sensitive even when they are not secrets] → They are masked and cut. If that is not enough, an operator option to drop titles is a small follow-up. It does not change the specs' default.
- [Agents differ in what their usage counts mean, for example whether input includes cached reads] → The spec exports counts as reported, without adjustment. The broker notes record each agent's meaning. Claude's input excludes cached reads, as observed; OpenCode is checked in task 4.2.
- [Claude reports the model as an alias (`haiku`), which Langfuse cannot price] → Langfuse lets an operator add a model definition that matches the alias, and the guide shows how. Whether the broker should resolve aliases is an open question.
- [Langfuse rewrites malformed spans instead of refusing them, so encoding bugs can be silent] → Golden tests on the encoder, and a live check through a real Collector into a real Langfuse that asserts type, model, usage, and cost (tasks 4.1 and 4.2).
- [Unbounded growth of span state in a very long turn with many tool calls] → Open tool spans are capped per turn (1024). Beyond the cap, tool calls are counted on the turn span and not recorded one by one.
- [The viewer token is shared, so a human turn cannot name its person] → Spans record origin `human` without a user. Per-user tokens are a later change, and `langfuse.user.id` can follow then.
- [Option A puts OTLP encoding in our code] → See D8. The exporter is behind one interface, so a later move to the SDK stays inside that package.

## Migration Plan

1. Implement behind the flags. A broker without `-otlp-endpoint` behaves exactly as before.
2. Run a Collector and Langfuse (v3.22.0 or later) next to Sortie, and configure the Collector from the example.
3. Add `-otlp-endpoint http://127.0.0.1:4318` to the broker prefix in a workflow's `agent.command`.
4. Rollback: remove the flag. No state is stored, and Sortie is not involved.

## Open Questions

These are listed, not decided. None changes the specs or the task breakdown of this change.

1. **Should Sortie's own accounting count the usage the broker observes?** This covers `run_history` tokens and the `agent.max_tokens` ceiling, including human and steer turns.
   - Today Sortie records OpenCode and Claude over ACP as unmeasured. It treats prompt-result usage as a lower bound only (`internal/agent/clientprotocol/usage.go`).
   - A likely design is an ACP usage source in `internal/agent/clientprotocol/usagesource` that reads a run total the broker writes, as the Gemini source reads its telemetry file. Gemini's `Claim` hands the runtime an output path through its environment, and `Drain` reads it.
   - Points to settle:
     - whether human-turn spend should count against a ceiling meant for the autonomous driver;
     - whether broker-reported counts are complete enough to be `Accounted` rather than `Partial`;
     - how the broker learns the path without reading Sortie internals.
   - That is a separate change in both repositories.
2. **Model aliases.** Should the broker resolve an alias such as Claude's `haiku` to a priced model ID? It could use the configuration option's display name or `_meta.quota.model_usage`. Or should this stay a Langfuse model definition?
3. **Pattern-based masking.** Should well-known token formats (cloud keys, GitHub tokens, JWTs) be masked by pattern, on top of known values? That would belong in the broker's secrets package, beside the registry of known values.
4. **Usage-detail keys.** Which keys does the deployed Langfuse version price for each provider? Task 4.2 settles them for Anthropic models via OpenCode and Claude. Other providers may need more keys.
5. **Pi usage.** When pi-acp#106 lands, are Pi's counts per turn or cumulative? The spec requires per-turn counts as reported. A cumulative report would need a difference, which is an agent-specific rule to place in the broker notes.
6. **OTLP metrics.** Should the broker also emit OTLP metrics (turns, tokens, and holds per rule) for Prometheus through the Collector? Langfuse covers cost; this would only matter for alerting outside Langfuse.
7. **Standard `OTEL_*` variables.** Should the broker also accept them, for example `OTEL_EXPORTER_OTLP_ENDPOINT`, and strip them from the agent's environment? D10 avoids them for now.
