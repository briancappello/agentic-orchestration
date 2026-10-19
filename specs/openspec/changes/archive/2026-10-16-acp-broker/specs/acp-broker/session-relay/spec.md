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
The broker SHALL forward every `session/update` to all viewers. It SHALL forward a `session/update` to the driver only while the driver has a prompt running or held, or while its answer is withheld for pending steers.

#### Scenario: Update during a human turn with a held driver turn
- **WHEN** the driver's turn is held and a human prompt runs
- **THEN** the driver and all viewers receive the human turn's updates

### Requirement: Interrupt gives humans the floor
A viewer `interrupt` SHALL give the floor to humans. The broker SHALL also accept it as `takeover` and as `cancel`. If a turn is running, the broker SHALL cancel it with `session/cancel`. For a cancelled driver turn, the broker SHALL keep the driver's request open: the agent's answer to that prompt SHALL NOT reach the driver. Steers queued at that moment SHALL be delivered once the cancelled turn ends, by the steering rules. While humans hold the floor, a new driver `session/prompt` SHALL be queued and not sent to the agent. Only a handback SHALL return the floor to the driver.

#### Scenario: Interrupt mid-turn
- **WHEN** the driver's prompt 7 is running
- **AND** a viewer interrupts
- **THEN** the agent receives `session/cancel`
- **AND** the agent's answer to prompt 7 does not reach the driver
- **AND** humans hold the floor

#### Scenario: Interrupt during a steer turn
- **WHEN** a steer turn runs while the driver's answer to prompt 7 is withheld
- **AND** a viewer interrupts
- **THEN** the agent receives `session/cancel` for the steer turn
- **AND** humans hold the floor, and the driver does not receive the answer to prompt 7 until handback

#### Scenario: Interrupt when idle
- **WHEN** no turn is running and the floor is with the driver
- **AND** a viewer interrupts
- **THEN** humans hold the floor and the agent receives no `session/cancel`

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
On handback, the broker SHALL give the floor back to the driver. It SHALL answer the held driver request with stop reason `end_turn`. If instead the agent's answer to the driver's turn was withheld for steers, it SHALL pass that answer unchanged. It SHALL then send any queued driver prompt to the agent. The broker SHALL reject a handback while a human prompt is running.

#### Scenario: Handback after an interrupt
- **WHEN** prompt 7 is held and prompt 8 is queued
- **AND** a viewer hands back
- **THEN** the driver receives a response to prompt 7 with stop reason `end_turn`
- **AND** the agent receives prompt 8

### Requirement: The driver's cancel wins
When the driver cancels its own turn, the broker SHALL forward the cancel to the agent. It SHALL answer any held or queued driver prompt with stop reason `cancelled`, and pass at once any answer it withheld for steers. If the driver cancels while an interrupt is waiting for the agent to end the turn, the agent's answer to that turn SHALL reach the driver. Steers queued at that moment SHALL stay queued and be delivered once the turn ends, as for an idle session. The driver's answer SHALL NOT be withheld for them.

#### Scenario: Driver cancels during an interrupt
- **WHEN** a viewer interrupted and the agent has not yet answered prompt 7
- **AND** the driver sends `session/cancel`
- **THEN** the driver receives the agent's answer to prompt 7

#### Scenario: Driver cancels with a steer queued
- **WHEN** a steer is queued while driver prompt 7 runs on an agent without native steering
- **AND** the driver cancels prompt 7
- **THEN** the driver receives the agent's answer to prompt 7
- **AND** the agent then receives the steer as a `session/prompt`

### Requirement: Sortie is told about holds
When the broker runs under Sortie, which it recognizes from `SORTIE_API_URL`, `SORTIE_ISSUE_IDENTIFIER`, and `SORTIE_SESSION_TOKEN`, it SHALL call Sortie's hold endpoint when humans take the floor, and the release endpoint when the floor returns to the driver or the broker exits. These calls SHALL authenticate with `SORTIE_SESSION_TOKEN`. A failed call SHALL be logged and retried with backoff. It SHALL NOT block the relay.

#### Scenario: Calls use the session token
- **WHEN** the broker holds the run for `LIVE-1`
- **THEN** its request carries `Authorization: Bearer` with the value of `SORTIE_SESSION_TOKEN`

#### Scenario: Interrupt under Sortie
- **WHEN** the broker runs for issue `LIVE-1` under Sortie
- **AND** a viewer interrupts
- **THEN** the broker posts to `/api/v1/LIVE-1/hold` with holder `acp-broker` and a reason naming the action

#### Scenario: Sortie unreachable
- **WHEN** the hold call fails
- **THEN** the interrupt still happens
- **AND** the broker retries the hold until it succeeds or the floor returns to the driver

### Requirement: The agent does not inherit the session token
The broker SHALL remove `SORTIE_SESSION_TOKEN` from the environment of the agent command it launches. It SHALL pass every other variable through unchanged.

#### Scenario: Agent environment
- **WHEN** the broker launches its agent command under Sortie
- **THEN** the agent process has `SORTIE_ISSUE_IDENTIFIER`
- **AND** has no `SORTIE_SESSION_TOKEN`

### Requirement: Floor returns to the driver when humans leave
When the last viewer disconnects while humans hold the floor and no human prompt is running, the broker SHALL hand back after a grace period, 60 seconds by default and configurable.

#### Scenario: Viewer closes the laptop
- **WHEN** a viewer interrupted and then disconnected
- **AND** no viewer attaches within the grace period
- **THEN** the broker hands back and the driver continues
