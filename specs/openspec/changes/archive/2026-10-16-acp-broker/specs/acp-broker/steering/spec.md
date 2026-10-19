## Purpose

Lets a human add a message to the session's conversation without stopping the agent. A steer is one entry in the session's log. It always lands, and it lands before the driver gets control back. Interrupting the agent is a separate, explicit action.

## ADDED Requirements

### Requirement: A steer is queued, never refused for the session's state
The broker SHALL accept a viewer steer with non-empty text in any state of a session that exists:
- whoever holds the floor;
- whether or not a turn is running;
- while other steers are pending.

It SHALL queue accepted steers in the order they arrive. A steer SHALL never cancel or interrupt a turn. The broker SHALL reject a steer only when its text is empty or no session exists yet.

#### Scenario: Several steers while a turn runs
- **WHEN** a driver turn is running on an agent without native steering
- **AND** viewers steer with "focus on the parser" and then "add a test"
- **THEN** both steers are accepted and queued in that order
- **AND** the agent receives no `session/cancel`

#### Scenario: Steer while taken over
- **WHEN** a viewer holds the floor
- **AND** another viewer steers
- **THEN** the steer is accepted

### Requirement: Queued steers are delivered together as one message
When the broker delivers queued steers, it SHALL deliver every steer queued at that moment as one message, one text block per steer, in queue order, with the text as the viewer wrote it. Steers that arrive while that message is being delivered SHALL be queued for the next delivery.

#### Scenario: Two queued steers delivered
- **WHEN** "focus on the parser" and "add a test" are queued and the broker delivers them
- **THEN** the agent receives one message whose prompt holds two text blocks, "focus on the parser" then "add a test"

### Requirement: Native injection into a running turn
When the agent's `initialize` result advertises `_meta.steering.supported: true` and a turn is running, the broker SHALL deliver queued steers at once as a `_session/steering` request for the session, with `idleBehavior: "promptRequired"`. This applies to driver, human, and steer turns. The floor SHALL NOT change. The broker SHALL send at most one `_session/steering` request at a time. The viewer SHALL receive the agent's final outcome.

#### Scenario: Steer an agent with native steering
- **WHEN** the agent advertised steering and a driver turn is running
- **AND** a viewer steers with "focus on the parser"
- **THEN** the agent receives `_session/steering` with that text
- **AND** the driver's turn is not cancelled

### Requirement: Without injection, steers run as the next turn
When no turn is running, queued steers SHALL be delivered at once as a `session/prompt` in the same session, a steer turn. This applies to every agent. When a turn is running and the agent cannot take a native steer, queued steers SHALL wait. The broker SHALL deliver them as a steer turn as soon as that turn ends.

#### Scenario: Steer an idle session
- **WHEN** no turn is running
- **AND** a viewer steers with "check the logs first"
- **THEN** the agent receives a `session/prompt` with that text, and no `_session/steering`, whether or not the agent advertised steering

#### Scenario: Steer waits for the running turn on an agent without native steering
- **WHEN** the agent did not advertise steering and driver prompt 7 is running
- **AND** a viewer steers with "focus on the parser"
- **THEN** the agent receives no `session/cancel` and no new prompt while prompt 7 runs
- **AND** when the agent answers prompt 7, the agent receives a `session/prompt` with that text

### Requirement: The driver gets control back only after its steers land
When a driver turn ends while steers are queued or a native steer awaits its outcome, the broker SHALL withhold the agent's answer from the driver. It SHALL pass that answer to the driver, unchanged, only once every pending steer has landed: injected into a turn, or run as a steer turn that ended. While the driver's answer is withheld, or a steer turn runs with the floor at the driver, the following SHALL hold:
- the broker SHALL ask Sortie to hold the run with reason `steer`;
- the broker SHALL queue any driver `session/prompt`;
- the broker SHALL forward session updates to the driver.

When the last steer turn ends, the broker SHALL release the hold, pass the withheld answer, and then send any queued driver prompt. The floor stays with the driver throughout.

#### Scenario: Steer queued at the end of the driver's last turn
- **WHEN** a steer is queued while driver prompt 7 runs on an agent without native steering
- **AND** the agent answers prompt 7 with stop reason `end_turn`
- **THEN** the driver does not yet receive the answer to prompt 7, and Sortie is asked to hold the run with reason `steer`
- **AND** the agent receives the steer as a `session/prompt`
- **AND** when that prompt ends, the driver receives the agent's original answer to prompt 7 and the run is released

#### Scenario: Idle steer with a driver prompt arriving
- **WHEN** a steer turn runs while the floor is with the driver
- **AND** the driver sends prompt 8
- **THEN** the agent does not receive prompt 8 until the steer turn ends

### Requirement: A native steer the agent refuses as idle is delivered as a turn
When the agent answers a native steer with outcome `promptRequired`, the turn ended before the agent took the steer. The broker SHALL put those steers back at the front of the queue. It SHALL deliver them as a steer turn as soon as no turn is running, and SHALL NOT pass `promptRequired` to viewers as final. The broker SHALL NOT send the same steers as a native steer a second time.

#### Scenario: Native steer races the end of the driver's turn
- **WHEN** a native steer is in flight and the agent answers driver prompt 7
- **AND** the agent then answers the steer with `promptRequired`
- **THEN** the driver does not yet receive the answer to prompt 7
- **AND** the agent receives the steer text as a `session/prompt`
- **AND** when that prompt ends, the driver receives the agent's answer to prompt 7

### Requirement: Steers when humans hold the floor
While humans hold the floor, steers SHALL be delivered by the same rules: injected into a running turn, or run as a steer turn when no turn runs. A steer turn SHALL NOT change the floor. Humans keep it until they hand back.

#### Scenario: Steer after an interrupt
- **WHEN** a viewer interrupted the driver's turn and holds the floor, with no turn running
- **AND** another viewer steers with "look at the failing test"
- **THEN** the agent receives a `session/prompt` with that text
- **AND** when it ends, the floor is still with humans and the driver's request is still held
