# acp-broker/telemetry-masking Specification

## Purpose
Defines what may leave the broker as telemetry and how it is masked first, because session transcripts and tool calls can contain secrets, and telemetry goes to systems with wider access than the session itself.

## Requirements

### Requirement: Known secrets are masked in everything exported
Before a span leaves the broker, the broker SHALL replace every known secret value in every exported string with a fixed marker. This covers attribute values, event attributes, status messages, and resource attributes. Known secrets SHALL include:
- the Sortie session token;
- the values of variables in the broker's environment whose names mark them as secrets (for example names ending in `TOKEN`, `KEY`, `SECRET`, or `PASSWORD`);
- the values in the telemetry headers file.

Masking SHALL also apply to text that was cut to a length limit, so that a cut-off secret does not leak its beginning.

#### Scenario: Session token in a tool title
- **WHEN** a tool call's title contains the value of `SORTIE_SESSION_TOKEN`
- **THEN** the exported tool call span carries the title with the marker in place of the token

#### Scenario: Secret-named variable in an error message
- **WHEN** the broker runs with `GITHUB_TOKEN` set, and a turn fails with an error message that contains its value
- **THEN** the exported turn span's status message carries the marker in place of the value

### Requirement: Transcript content is not exported by default
By default, the broker SHALL NOT export transcript content: prompt text, agent message and thought text, tool call input and output, tool call content, and permission request details. Spans SHALL still carry the structure, timing, outcome, usage, model, tool kind, tool title, and labels.

#### Scenario: Default export
- **WHEN** telemetry is enabled without the content option and a turn runs with a prompt, agent messages, and a tool call with input and output
- **THEN** the exported spans carry no prompt text, agent text, or tool input and output

### Requirement: Opt-in content export, masked and bounded
When the operator enables the content option, the broker SHALL also export each turn's prompt text as the turn's input and the agent's message text as its output, and each tool call's input and output. Each exported value SHALL be masked and then cut to a configured maximum length, with a marker showing that it was cut.

#### Scenario: Content enabled
- **WHEN** the content option is enabled and a human prompt "check the logs" runs
- **THEN** the exported turn span carries "check the logs" as its input

#### Scenario: Long output
- **WHEN** the content option is enabled and the agent's message text is longer than the maximum length
- **THEN** the exported output is cut to the maximum length and marked as cut

### Requirement: Viewers are unaffected
Masking for telemetry SHALL NOT change what the driver, the agent, or viewers receive, nor the replay kept for viewers.

#### Scenario: Viewer sees the unmasked session
- **WHEN** an agent message contains a known secret and telemetry is enabled
- **THEN** viewers receive the message unchanged, and only the exported span is masked
