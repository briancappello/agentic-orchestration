## Purpose

Defines how the broker's turn spans leave the process: over OTLP/HTTP to a Collector, shaped so that Langfuse prices each turn and groups it by session and stage, and without ever affecting the session the broker relays.

## ADDED Requirements

### Requirement: OTLP/HTTP export to a configured endpoint
The operator SHALL configure telemetry with an OTLP/HTTP endpoint URL and, optionally, a file of request headers (for example, credentials for the Collector). The broker SHALL send its spans as OTLP trace export requests to the endpoint's `/v1/traces` path, with those headers. The broker SHALL send each span once it has ended, in batches, without waiting for the session to end. The broker SHALL refuse to start when the endpoint is not a valid `http` or `https` URL, or when the headers file cannot be read or parsed.

#### Scenario: Spans reach the Collector
- **WHEN** the endpoint is `http://127.0.0.1:4318` and a turn ends
- **THEN** a Collector listening there receives an OTLP trace export request on `/v1/traces` that contains the turn's span, while the session is still running

#### Scenario: Unreadable headers file
- **WHEN** the operator names a headers file that does not exist
- **THEN** the broker exits with a usage error before it starts the agent

### Requirement: Telemetry configuration does not reach the agent
The broker SHALL NOT pass its telemetry configuration to the agent. The agent's environment SHALL NOT gain any variable because telemetry is enabled.

#### Scenario: Agent environment
- **WHEN** telemetry is enabled with a headers file
- **THEN** the agent's environment is the same as it would be without telemetry

### Requirement: Spans follow Langfuse's OTLP mapping
The exported spans SHALL use the attributes Langfuse maps from OTLP, so that Langfuse shows each turn as a priced generation:
- Each turn SHALL be its own trace, rooted at its turn span. Its trace name SHALL name the origin.
- Every span SHALL carry the Langfuse session ID: the dispatch ID when set, otherwise the ACP session ID. So one Sortie dispatch is one Langfuse session.
- A turn span SHALL be observation type `generation`, with the model and the usage details mapped from the turn's token counts.
- A tool call span SHALL be observation type `tool`.
- Every span SHALL carry the session labels as top-level trace metadata, so Langfuse can filter and group by issue, rule, chain, dispatch, and attempt.

#### Scenario: A priced turn in Langfuse
- **WHEN** a driver turn with model `anthropic/claude-haiku-5-5` and reported usage is exported through a Collector to Langfuse
- **THEN** Langfuse shows a trace for that turn whose root observation is a generation with that model and those token counts, and a computed cost when Langfuse has a price for the model

#### Scenario: Cost per stage
- **WHEN** two dispatches of one chain run with rules `implement` and `review`
- **THEN** Langfuse can filter the turns, and sum their cost, by the `rule` metadata key

### Requirement: Export never affects the relay
Export SHALL run apart from the relay. A slow, failing, or unreachable endpoint SHALL NOT delay any message between the driver, the agent, and viewers. The broker SHALL hold ended spans in a bounded buffer. When the buffer is full, it SHALL drop the oldest spans, count them, and log the count. Export failures SHALL be logged, never sent to the driver, the agent, or viewers.

#### Scenario: Endpoint hangs
- **WHEN** the endpoint accepts connections and never answers
- **THEN** the session runs as it would without telemetry
- **AND** once the buffer is full, the broker logs how many spans it dropped

### Requirement: Retries and final flush
The broker SHALL retry an export that fails with a network error, `429`, or a `5xx` status, with capped backoff. It SHALL drop a batch that the endpoint refuses with any other `4xx` status, and log the refusal. When the session ends, the broker SHALL try once to send the spans it still holds, bounded by a short timeout. It SHALL then exit with the agent's exit code, whatever the outcome of that last export.

#### Scenario: Transient failure
- **WHEN** the endpoint answers `503` and then `200`
- **THEN** the batch is sent again and accepted, and no span is lost

#### Scenario: Exit with unsent spans
- **WHEN** the agent exits while the endpoint is down
- **THEN** the broker tries one last export, gives up within its timeout, and exits with the agent's exit code
