# acp-broker/turn-telemetry Specification

## Purpose
Defines what the broker records about each turn of its session, whoever started it, so that the cost and behavior of every turn can be traced per issue and per stage.

## Requirements

### Requirement: Telemetry is off unless configured
The broker SHALL record and export nothing unless the operator configures a telemetry endpoint. A broker that runs a credential check SHALL record and export nothing, even when an endpoint is configured.

#### Scenario: No endpoint configured
- **WHEN** the broker runs a session without a telemetry endpoint
- **THEN** no span is recorded and no network connection is made for telemetry

#### Scenario: Credential check
- **WHEN** Sortie starts the broker with `SORTIE_SESSION_PURPOSE=credential-check` and an endpoint is configured
- **THEN** the broker exports nothing

### Requirement: One span per turn, with its origin
The broker SHALL record one turn span for each `session/prompt` the agent runs in the session. The span SHALL start when the prompt is sent to the agent and end when the agent answers it. Each turn span SHALL carry its origin:
- `driver` for a prompt from the driver;
- `human` for a prompt a viewer sends;
- `steer` for a steer the broker runs as a turn of its own.

A driver prompt that the broker queues while humans hold the floor SHALL start its span when it is sent to the agent, not when it is queued.

#### Scenario: Driver, human, and steer turns
- **WHEN** a session runs a driver turn, then a steer turn, then a human turn
- **THEN** three turn spans are recorded, with origins `driver`, `steer`, and `human`, in that order

#### Scenario: Queued driver prompt
- **WHEN** a driver prompt arrives while a viewer holds the floor, and is sent to the agent on handback
- **THEN** its turn span starts at handback

### Requirement: The turn's outcome
Each turn span SHALL carry the stop reason the agent returned. A turn that the agent answers with an error SHALL be marked as failed, with the error message. A turn cancelled by a viewer interrupt SHALL record that it was cancelled for an interrupt. A turn still running when the broker stops SHALL end at that moment and be marked unfinished.

#### Scenario: Interrupt cancels a driver turn
- **WHEN** a viewer interrupts during driver prompt 7, and the agent answers it with stop reason `cancelled`
- **THEN** the turn span for prompt 7 ends with stop reason `cancelled` and records that the cancel came from an interrupt

#### Scenario: Broker stops mid-turn
- **WHEN** the agent exits while a turn is running
- **THEN** that turn's span ends when the broker stops and is marked unfinished

### Requirement: A native steer is an event on the running turn
Steers that the agent accepts into a running turn through native steering SHALL be recorded as an event on that turn's span, with the agent's outcome and the number of steers delivered together. They SHALL NOT be recorded as a turn. A steer turn's span SHALL carry the number of steers it delivered.

#### Scenario: Native steer accepted
- **WHEN** a viewer steers during a driver turn and the agent answers `injected`
- **THEN** the driver turn's span carries a steer event with outcome `injected`
- **AND** no additional turn span is recorded

### Requirement: Per-turn usage from the prompt result
When the agent's answer to a prompt carries usage, the turn span SHALL carry each reported count: input, output, cached read, cached write, and total tokens, plus reasoning tokens when reported. Each count SHALL be the value the agent reported, without adjustment. When the answer carries no usage, the turn span SHALL say that usage was not reported, and SHALL NOT carry zero counts.

#### Scenario: Agent reports usage
- **WHEN** the agent answers a prompt with usage `inputTokens` 4, `outputTokens` 102, `cachedReadTokens` 53643, `cachedWriteTokens` 307, `totalTokens` 54056
- **THEN** the turn span carries exactly those five counts

#### Scenario: Agent reports no usage
- **WHEN** the agent answers a prompt without usage
- **THEN** the turn span marks usage as not reported and carries no token counts

### Requirement: The session's model
Each turn span SHALL carry the model the session uses when the turn starts, as the agent reports it in its session configuration: the configuration option of category `model`, from the result of `session/new` or `session/load` and from later configuration changes in the session. When the agent reports no model, the span SHALL carry none.

#### Scenario: Model reported at session start
- **WHEN** the agent's `session/new` result has a configuration option of category `model` with current value `anthropic/claude-haiku-5-5`
- **THEN** the session's turn spans carry that model

#### Scenario: Model changed during the session
- **WHEN** the agent reports a new current value for the model option between two turns
- **THEN** the second turn's span carries the new model

### Requirement: Tool calls are child spans of their turn
Each tool call the agent reports in `session/update` during a turn SHALL be recorded as a child span of that turn's span. It SHALL start at the first update for its tool call ID and end at the update that reports it completed or failed. It SHALL carry the tool call's kind, its title, and its final status. A tool call still open when its turn ends SHALL end with the turn and be marked unfinished.

#### Scenario: Tool call completes
- **WHEN** during a turn the agent reports `tool_call` with ID `call_1`, kind `read`, title "Read main.go", and later `tool_call_update` for `call_1` with status `completed`
- **THEN** the turn span has one child span for `call_1` with kind `read`, that title, and status `completed`

#### Scenario: Tool call left open
- **WHEN** a turn ends while tool call `call_2` has not reported completed or failed
- **THEN** the child span for `call_2` ends with the turn and is marked unfinished

### Requirement: Session labels on every span
Every span SHALL carry the labels Sortie gives the broker in its environment, when set: the issue identifier (`SORTIE_ISSUE_IDENTIFIER`), the dispatch rule (`SORTIE_RULE`), the chain ID (`SORTIE_CHAIN_ID`), the dispatch ID (`SORTIE_DISPATCH_ID`), and the attempt (`SORTIE_ATTEMPT`). Every span SHALL also carry the agent's name and version from its `initialize` result, and the ACP session ID. A label whose variable is unset SHALL be omitted, not sent empty.

#### Scenario: Broker under Sortie
- **WHEN** Sortie starts the broker with `SORTIE_ISSUE_IDENTIFIER=LIVE-1`, `SORTIE_RULE=implement`, `SORTIE_CHAIN_ID=c-42`, `SORTIE_DISPATCH_ID=D1`, and `SORTIE_ATTEMPT=2`
- **THEN** every turn span and tool call span carries those five labels

#### Scenario: Standalone broker
- **WHEN** the broker runs without any `SORTIE_*` variables
- **THEN** spans carry the agent and session labels and no Sortie labels
