## Purpose

Defines how the broker relays one ACP session between the autonomous driver and the agent, and how humans take that session over and give it back, without the driver or the agent seeing a protocol they do not expect.

## ADDED Requirements

### Requirement: Transparent relay
The broker SHALL launch the agent command it is given, and SHALL act as the agent toward the driver on its standard input and output. Messages the broker does not handle SHALL pass unchanged in both directions. The broker SHALL exit when the agent exits, with the agent's exit code. When the driver closes its input, the broker SHALL close the agent's input.

#### Scenario: Unhandled message passes through
- **WHEN** the driver sends a request the broker does not handle
- **THEN** the agent receives the same bytes
- **AND** the driver receives the agent's response unchanged

#### Scenario: Agent exits
- **WHEN** the agent exits with code 3
- **THEN** the broker exits with code 3

### Requirement: Session updates reach the driver only during its turns
The broker SHALL forward every `session/update` to all viewers. It SHALL forward a `session/update` to the driver only while the driver has a prompt running or held.

#### Scenario: Update during a human turn with a held driver turn
- **WHEN** the driver's turn is held and a human prompt runs
- **THEN** the driver and all viewers receive the human turn's updates

### Requirement: Takeover holds the driver's turn
On a takeover, the broker SHALL give the floor to humans. If a driver prompt is running, the broker SHALL cancel it with `session/cancel` and keep the driver's request open: the agent's answer to that prompt SHALL NOT reach the driver. While humans hold the floor, a new driver `session/prompt` SHALL be queued and not sent to the agent.

#### Scenario: Takeover mid-turn
- **WHEN** the driver's prompt 7 is running
- **AND** a viewer takes over
- **THEN** the agent receives `session/cancel`
- **AND** the agent's answer to prompt 7 does not reach the driver

#### Scenario: Driver prompt while held
- **WHEN** humans hold the floor
- **AND** the driver sends prompt 8
- **THEN** the agent does not receive prompt 8 until handback

### Requirement: Human prompts use the same session
While humans hold the floor, a viewer prompt SHALL be sent to the agent as a `session/prompt` for the same session ID the driver uses. The broker SHALL reject a viewer prompt while another human prompt is running.

#### Scenario: Human prompt
- **WHEN** a viewer holding the floor sends a prompt
- **THEN** the agent receives `session/prompt` with the driver's session ID

### Requirement: Handback ends the held turn normally
On handback, the broker SHALL give the floor back to the driver. It SHALL answer the held driver request with stop reason `end_turn`, and SHALL then send any queued driver prompt to the agent. The broker SHALL reject a handback while a human prompt is running.

#### Scenario: Handback after takeover
- **WHEN** prompt 7 is held and prompt 8 is queued
- **AND** a viewer hands back
- **THEN** the driver receives a response to prompt 7 with stop reason `end_turn`
- **AND** the agent receives prompt 8

### Requirement: The driver's cancel wins
When the driver cancels its own turn, the broker SHALL forward the cancel to the agent and answer any held or queued driver prompt with stop reason `cancelled`. If the driver cancels while a takeover is waiting for the agent to end the turn, the agent's answer to that turn SHALL reach the driver.

#### Scenario: Driver cancels during a takeover
- **WHEN** a viewer took over and the agent has not yet answered prompt 7
- **AND** the driver sends `session/cancel`
- **THEN** the driver receives the agent's answer to prompt 7

### Requirement: Sortie is told about holds
When the broker runs under Sortie, which it recognizes from `SORTIE_API_URL` and `SORTIE_ISSUE_IDENTIFIER`, it SHALL call Sortie's hold endpoint when humans take the floor, and the release endpoint when the floor returns to the driver or the broker exits. A failed call SHALL be logged and retried with backoff. It SHALL NOT block the relay.

#### Scenario: Takeover under Sortie
- **WHEN** the broker runs for issue `LIVE-1` under Sortie
- **AND** a viewer takes over
- **THEN** the broker posts to `/api/v1/LIVE-1/hold` with holder `acp-broker` and a reason naming the action

#### Scenario: Sortie unreachable
- **WHEN** the hold call fails
- **THEN** the takeover still happens
- **AND** the broker retries the hold until it succeeds or the floor returns to the driver

### Requirement: Floor returns to the driver when humans leave
When the last viewer disconnects while humans hold the floor and no human prompt is running, the broker SHALL hand back after a grace period, 60 seconds by default and configurable.

#### Scenario: Viewer closes the laptop
- **WHEN** a viewer took over and then disconnected
- **AND** no viewer attaches within the grace period
- **THEN** the broker hands back and the driver continues
