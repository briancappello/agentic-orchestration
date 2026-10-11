## Why

We cannot see what our agent sessions cost or do per stage. Sortie's Prometheus metrics count runs, holds, and the tokens Sortie itself measures. Over ACP, Sortie records OpenCode and Claude as unmeasured, and it never sees the turns humans start through the broker. The ACP broker sees every turn of a session: Sortie's, human prompts, and steer turns. It is therefore the one place that can report every turn with its usage, model, and tool calls. We want those traces in self-hosted Langfuse, for LLM traces and cost per stage.

## What Changes

- The broker emits one trace span per turn, labelled with the turn's origin: `driver` (Sortie), `human` (a viewer prompt), or `steer` (a steer the broker runs as a turn of its own). A native steer injected into a running turn is an event on that turn's span, not a turn.
- Each turn span carries the turn's usage from the prompt result: input, output, cached read, cached write, and total tokens. OpenCode and Claude report these today. Pi reports none until pi-acp#106 lands, and its spans say so.
- Each turn span carries the session's model, read from the agent's session configuration.
- Tool calls reported in `session/update` become child spans of their turn.
- Every span carries labels from the session environment Sortie gives the broker: `SORTIE_ISSUE_IDENTIFIER`, `SORTIE_RULE`, `SORTIE_CHAIN_ID`, `SORTIE_DISPATCH_ID`, and `SORTIE_ATTEMPT`. The broker starts reading `SORTIE_DISPATCH_ID`.
- The broker exports spans over OTLP/HTTP to an OpenTelemetry Collector, which forwards them to Langfuse. Span attributes follow Langfuse's OTLP mapping, so Langfuse prices each turn and groups cost by stage.
- Telemetry is off unless configured. Export never blocks or slows the relay. A credential-check broker never exports.
- Everything leaves masked. Known secrets are replaced in every exported string. Transcript content (prompt text, agent messages, tool input and output) is not exported unless the operator opts in.
- An example Collector configuration and a guide section show the pipeline to Langfuse.
- Sortie's own Prometheus metrics do not change.

## Capabilities

### New Capabilities

- `acp-broker/turn-telemetry`: what the broker observes and records for each turn: origin, timing, outcome, usage, model, tool calls, and session labels.
- `acp-broker/telemetry-export`: how spans leave the broker: the OTLP/HTTP exporter, its configuration, the Langfuse attribute mapping, and the guarantee that export never affects the relay.
- `acp-broker/telemetry-masking`: what may leave as telemetry, and the masking applied before it does.

### Modified Capabilities

None. The `acp-broker` change is not archived yet, so `openspec/specs/` has no broker capabilities to modify. Its relay, steering, and viewer requirements are unchanged.

## Impact

- **Code (`acp-broker`):** a new telemetry package under `acp-broker/internal`, hooks in the broker loop at turn start and end and on `session/update`, new flags in `acp-broker/cmd/acp-broker`, and `SORTIE_DISPATCH_ID` in `acp-broker/internal/sortieclient`. The masking uses `acp-broker/internal/secrets`.
- **Dependencies: a decision to take first.** The broker plan said "standard library only". The design compares the OpenTelemetry Go SDK with OTLP/HTTP written on the standard library. No dependency is added until the user chooses.
- **Dependencies:** the broker is a module that uses the standard library only. Any dependency it adds is one more module to vet and keep current.
- **Operations:** a Collector and a self-hosted Langfuse (v3.22.0 or later, for its OTLP endpoint) are needed to use the feature. Without them the broker behaves as it does today.
- **Docs (`acp-broker`):** `acp-broker/docs/guide.md` (flags, pipeline, masking), `acp-broker/docs/notes.md` (usage and model per agent), and an example Collector configuration.
- **Out of scope:** Sortie's own accounting (`run_history` tokens, `agent.max_tokens`) stays as it is. Whether it should count the usage the broker observes is an open question in the design.
