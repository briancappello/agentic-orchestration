## 1. Decision and session facts

- [x] 1.1 Get the user's choice for the exporter dependency. Decided 2026-10-11: Option A, OTLP/HTTP JSON on the standard library (design D8).
- [x] 1.2 Read `SORTIE_DISPATCH_ID` into the broker's session environment alongside the other `SORTIE_*` labels. Verify with a `sortieclient` test that reads all five labels, and one where they are unset.
- [x] 1.3 Track the session's model in the loop: the `configOptions` entry of category `model`, from `session/new` and `session/load` results, from results of the driver's `session/set_config_option`, and from `config_option_update` session updates. Verify with loop tests using a fake agent for each source and for an agent that reports no model.

## 2. Recorder, exporter, masking

- [x] 2.1 Add `acp-broker/internal/telemetry` with the span model and a recorder called from the loop (design D1, D2, D6). It covers turn start and end for each origin, the queued-prompt start at handback, takeover cancels, native steer events, tool call child spans with the per-turn cap, updates outside a turn counted and dropped, and open spans ended as unfinished on stop. Use a no-op recorder when telemetry is off. Verify with loop tests that capture ended spans, one per scenario in `acp-broker/turn-telemetry`.
- [x] 2.2 Add the OTLP/HTTP exporter (design D8 Option A, D9): bounded buffer that drops the oldest span and counts it, batching by size and time, retry with capped backoff and `Retry-After` on network errors, `429`, and `5xx`, and dropping the batch on other `4xx`. Add a final flush bounded by 3 s. Verify with `httptest` tests: `503` then `200` loses nothing; a hanging endpoint fills the buffer and logs the drop count; exit with the endpoint down returns within the bound. Add a loop test that shows relay latency unchanged while the exporter is blocked.
- [x] 2.3 Encode spans as OTLP JSON with the attribute mapping of design D4: hex trace and span IDs, 64-bit integers as strings, numeric enums, one trace per turn, `langfuse.session.id` from the dispatch ID or else the ACP session ID, labels as `langfuse.trace.metadata.*` on every span, and `generation` and `tool` observation types. Verify with golden tests for a driver turn with usage and two tool calls, a steer turn without usage, and a failed human turn.
- [x] 2.4 Mask in the encoder (design D7). Register the session token before it is stripped from the agent's environment, secret-named environment values, and header values. Apply `MaskTruncated` to cut values. Collect transcript content only with the content option, and cut it to the configured maximum. Verify with tests for each scenario in `acp-broker/telemetry-masking`, including that a viewer receives the unmasked message.

## 3. Command-line wiring

- [x] 3.1 Add `-otlp-endpoint`, `-otlp-headers-file`, `-telemetry-content`, and `-telemetry-content-max` to `acp-broker` (design D10). An invalid endpoint or an unreadable headers file is a usage error (exit 2) before the agent starts. A credential-check broker exports nothing. The agent's environment is unchanged by telemetry. Verify with process tests in `acp-broker/cmd/acp-broker` for each of these, and run `go test -race ./acp-broker/...` and `make lint`.

## 4. End-to-end checks

- [x] 4.1 Run the broker with the fake agent against a real OpenTelemetry Collector (`otelcol-contrib` binary or container, operator tooling, not a Go dependency) with the `debug` exporter at detailed verbosity. Verify that the Collector accepts every export with no rejections, and that its output shows the D4 attributes on turn and tool spans. Record the commands and output in this change's `verification.md`.
- [x] 4.2 Run self-hosted Langfuse (v3.22.0 or later) behind the Collector from the example configuration. Run the live harness under Sortie with OpenCode (primary) and Claude, with a driver turn, a steer turn, and a human turn. Verify in Langfuse:
  - each turn is a generation with its model and usage;
  - a cost appears for OpenCode's model, and for Claude once an alias model definition is added;
  - the dispatch groups the turns as a session;
  - filtering by `rule` sums cost per stage;
  - no secret planted in the session environment appears in any span.

  Settle the usage-detail key names (design D4) and OpenCode's input-token meaning. Record everything in `verification.md`.

## 5. Documentation

- [x] 5.1 Update the broker's docs in the same change:
  - `acp-broker/docs/guide.md`: telemetry flags, the Collector-to-Langfuse pipeline, what is masked and what the content option exports, the cost-per-stage filter, and a model definition for Claude's alias;
  - `acp-broker/docs/notes.md`: usage meaning and model reporting per agent, and Pi's pending usage;
  - `CHANGELOG.md`;
  - `acp-broker/examples/telemetry/collector.yaml`.

  Verify that `otelcol-contrib validate --config acp-broker/examples/telemetry/collector.yaml` succeeds, and that the guide's example broker command runs as written.
