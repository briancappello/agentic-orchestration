## Purpose

Defines how human clients (the terminal attach command, a herdr pane, a browser, a phone) connect to a broker, what they receive, and what they can send.

## ADDED Requirements

### Requirement: One protocol over two transports
The broker SHALL serve the same event and command protocol on two transports:
- a local Unix socket of newline-delimited JSON, always on
- an HTTP listener, on only when a listen address is configured

Over HTTP:
- `GET /events` SHALL stream events as Server-Sent Events.
- `POST /commands` SHALL accept one command and answer with its immediate result.
- `GET /state` SHALL return the current state.

#### Scenario: Same events on both transports
- **WHEN** one viewer is attached by socket and one by HTTP
- **THEN** both receive the same sequence of events

### Requirement: Events carry a sequence number
Every event SHALL carry a sequence number that increases by one per event, and the time it was produced. The event types SHALL be:
- `state`: the floor, the session ID, the driver turn state, and whether steering is supported
- `update`: a raw `session/update` params object
- `permission` and `permission_resolved`
- `result`: the outcome of a viewer command that ran a turn
- `error`

#### Scenario: Ordered events
- **WHEN** a viewer receives events 41 and 42
- **THEN** event 42 was produced after event 41

### Requirement: Late viewers get the session so far
The broker SHALL keep a replay buffer of the most recent events, by default the last 5000 or 16 MiB, whichever limit is reached first. A new viewer SHALL first receive the current `state`, then the buffered events in order, then live events. An HTTP viewer that reconnects with `Last-Event-ID` SHALL receive only the events after that ID that are still in the buffer. When older events were dropped, it SHALL first receive an event that says so.

#### Scenario: Attach mid-session
- **WHEN** a session has produced 300 events
- **AND** a viewer attaches
- **THEN** the viewer receives `state`, then events 1 to 300, then live events

#### Scenario: Phone reconnects
- **WHEN** an HTTP viewer reconnects with `Last-Event-ID: 280` and the buffer still holds event 281
- **THEN** the viewer receives events from 281 onward

### Requirement: Commands
The broker SHALL accept these commands:
- `steer`, `takeover`, `prompt`, `cancel`, and `handback`
- `permit`, with a request ID and an option
- `state`

An invalid command, or one not allowed in the current state, SHALL return an `error` that names the reason, and SHALL change nothing.

#### Scenario: Handback without takeover
- **WHEN** the driver holds the floor
- **AND** a viewer sends `handback`
- **THEN** the viewer receives an `error` event and the floor does not change

### Requirement: HTTP access requires a token
The HTTP listener SHALL require `Authorization: Bearer <token>`, or the same token in an `access_token` query parameter for `GET /events` in browsers. When no token is configured, the broker SHALL refuse to start the listener. The local socket SHALL be created with mode `0600` in a directory with mode `0700`.

#### Scenario: Missing token
- **WHEN** a client calls `GET /events` without a token
- **THEN** the broker answers `401`

#### Scenario: Listener without a token
- **WHEN** an HTTP listen address is configured but no token
- **THEN** the broker exits with an error naming the token setting

### Requirement: Slow viewers do not slow the session
A viewer that does not keep up SHALL be disconnected. It SHALL NOT delay the relay, other viewers, or the agent.

#### Scenario: Stalled phone connection
- **WHEN** one viewer stops reading
- **THEN** the driver and the agent continue at normal speed
- **AND** the broker disconnects that viewer once its buffer is full
