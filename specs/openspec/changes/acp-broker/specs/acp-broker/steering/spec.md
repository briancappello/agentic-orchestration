## Purpose

Lets a human correct a running session without taking it over, using the agent's own mid-turn injection when it has one, and an equivalent same-session turn when it does not.

## ADDED Requirements

### Requirement: Native steering when the agent advertises it
When the agent's `initialize` result advertises `_meta.steering.supported: true` and a driver turn is running, a viewer steer SHALL be sent as a `_session/steering` request for the driver's session. It SHALL carry `idleBehavior: "promptRequired"`. The floor SHALL stay with the driver. The viewer SHALL receive the agent's outcome.

#### Scenario: Steer an agent with native steering
- **WHEN** the agent advertised steering and a driver turn is running
- **AND** a viewer steers with "focus on the parser"
- **THEN** the agent receives `_session/steering` with that text
- **AND** the driver's turn is not cancelled

### Requirement: An idle session is steered with a same-session turn for every agent
When no driver turn is running, a viewer steer SHALL NOT be sent as native steering, even when the agent advertises it. The broker SHALL run the steer as a same-session turn, exactly as for an agent without native steering. A steer is never dropped because the session is idle.

#### Scenario: Steer an idle session of an agent with native steering
- **WHEN** the agent advertised steering and no driver turn is running
- **AND** a viewer steers with "check the logs first"
- **THEN** the agent receives a `session/prompt` with that text, and no `_session/steering`
- **AND** Sortie is asked to hold the run with reason `steer`
- **AND** a driver prompt that arrives meanwhile is queued
- **AND** when the steer prompt ends, the run is released and the queued driver prompt goes to the agent

### Requirement: A native steer the agent refuses as idle is not lost
When the agent answers a native steer with outcome `promptRequired`, the driver's turn ended before the agent took the steer. The broker SHALL NOT pass that outcome to viewers as final. Instead:
- If a driver turn is running when the answer arrives, the broker SHALL send the same `_session/steering` request once more.
- Otherwise, or when the resent steer is also answered `promptRequired`, the broker SHALL run the text as a same-session turn, as for an agent without native steering.
- If humans took the floor while the steer was in flight, the broker SHALL drop the steer and tell viewers to send a prompt instead, so that the steer turn's automatic handback cannot end their takeover.

#### Scenario: Native steer races the end of the driver's turn while a new turn starts
- **WHEN** the agent answers a native steer with `promptRequired`
- **AND** a new driver turn is running by then
- **THEN** the agent receives `_session/steering` with the same text again
- **AND** the driver's turn is not cancelled

#### Scenario: Native steer races the end of the driver's turn and the session stays idle
- **WHEN** the agent answers a native steer with `promptRequired`
- **AND** no driver turn is running
- **THEN** the agent receives a `session/prompt` with the steer text
- **AND** Sortie is asked to hold the run with reason `steer` until that prompt ends

### Requirement: Same-session turn when the agent cannot steer
When the agent does not advertise steering, a viewer steer SHALL work as a short takeover:
- If a driver turn is running, the broker SHALL cancel it and hold the driver's request.
- The broker SHALL then send the steer text as a `session/prompt` in the same session.
- When that prompt ends, the broker SHALL hand back automatically.
If no driver turn is running, the broker SHALL send the steer prompt at once and queue driver prompts until it ends.

#### Scenario: Steer an agent without native steering
- **WHEN** the agent did not advertise steering and driver prompt 7 is running
- **AND** a viewer steers with "focus on the parser"
- **THEN** the agent receives `session/cancel`, and then a `session/prompt` with that text
- **AND** when that prompt ends, the driver receives `end_turn` for prompt 7

### Requirement: One steer at a time
The broker SHALL reject a steer while another steer is in progress (a native steer awaiting its outcome, or a same-session steer turn waiting or running), while a human prompt is running, and while humans hold the floor.

#### Scenario: Steer while taken over
- **WHEN** a viewer holds the floor
- **AND** another viewer steers
- **THEN** the broker rejects the steer with a message to send a prompt instead
