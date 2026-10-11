## Purpose

Lets a human correct a running session without taking it over, using the agent's own mid-turn injection when it has one, and an equivalent same-session turn when it does not.

## ADDED Requirements

### Requirement: Native steering when the agent advertises it
When the agent's `initialize` result advertises `_meta.steering.supported: true`, a viewer steer SHALL be sent as a `_session/steering` request for the driver's session. It SHALL carry `idleBehavior: "promptRequired"`. The floor SHALL stay with the driver. The viewer SHALL receive the agent's outcome.

#### Scenario: Steer an agent with native steering
- **WHEN** the agent advertised steering and a driver turn is running
- **AND** a viewer steers with "focus on the parser"
- **THEN** the agent receives `_session/steering` with that text
- **AND** the driver's turn is not cancelled

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
The broker SHALL reject a steer while a fallback steer turn or a human prompt is running, and while humans hold the floor.

#### Scenario: Steer while taken over
- **WHEN** a viewer holds the floor
- **AND** another viewer steers
- **THEN** the broker rejects the steer with a message to send a prompt instead
