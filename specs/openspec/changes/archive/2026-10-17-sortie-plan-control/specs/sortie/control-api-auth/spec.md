## MODIFIED Requirements

### Requirement: Bearer token for state-changing endpoints
When `server.control_token` is set, Sortie SHALL require `Authorization: Bearer <token>` on every endpoint that changes runtime state or returns a secret: refresh, hold, release, escalate, plan pull-back, plan cancel, the broker report, and the broker read. The token SHALL be either the control token, or a session token where the per-session rules below allow it. A missing or unknown token SHALL receive `401`, and Sortie SHALL take no action. Sortie SHALL compare tokens in constant time. The token SHALL support `$VAR` indirection like other secrets and SHALL be registered for masking.

#### Scenario: Missing token
- **WHEN** a control token is configured
- **AND** a caller posts to `/api/v1/LIVE-1/hold` without an `Authorization` header
- **THEN** Sortie answers `401`
- **AND** the run is not held

#### Scenario: Correct token
- **WHEN** a caller posts to `/api/v1/LIVE-1/hold` with the configured token
- **THEN** Sortie processes the request

#### Scenario: Cancel without a token
- **WHEN** a control token is configured
- **AND** a caller posts to `/api/v1/plan/cancel` without an `Authorization` header
- **THEN** Sortie answers `401`
- **AND** nothing is cancelled

### Requirement: Per-session scoped tokens
For each work session it launches, Sortie SHALL mint a random session token of at least 128 bits and pass it to the agent process as `SORTIE_SESSION_TOKEN`. Credential-check launches SHALL NOT receive one. A session token SHALL be accepted, as `Authorization: Bearer <token>`, only on the hold, release, escalate, and broker report endpoints, and only for the issue whose run it was minted for. On any other endpoint, or for any other issue, it SHALL receive `403`, and Sortie SHALL take no action. A session token SHALL stop working when the run it was minted for ends. Sortie SHALL keep session tokens only in memory, SHALL register them for masking, and SHALL NOT write them to run history or logs.

#### Scenario: Broker holds its own run
- **WHEN** the run for `LIVE-1` received session token `T`
- **AND** a caller posts to `/api/v1/LIVE-1/hold` with `Authorization: Bearer T`
- **THEN** Sortie holds the run

#### Scenario: Broker reports its own address
- **WHEN** the run for `LIVE-1` received session token `T`
- **AND** a caller posts to `/api/v1/LIVE-1/broker` with `Authorization: Bearer T`
- **THEN** Sortie keeps the reported address

#### Scenario: Token used for another issue
- **WHEN** a caller posts to `/api/v1/LIVE-2/hold` with the session token minted for `LIVE-1`
- **THEN** Sortie answers `403`
- **AND** the run of `LIVE-2` is not held

#### Scenario: Token used for refresh
- **WHEN** a caller posts to `/api/v1/refresh` with a session token
- **THEN** Sortie answers `403`

#### Scenario: Token used to cancel
- **WHEN** a caller posts to `/api/v1/plan/cancel` with a session token
- **THEN** Sortie answers `403`
- **AND** nothing is cancelled

#### Scenario: Token after the run ends
- **WHEN** the run for `LIVE-1` has ended
- **AND** a caller posts to `/api/v1/LIVE-1/escalate` with that run's session token
- **THEN** Sortie answers `401`

#### Scenario: Each run gets a new token
- **WHEN** issue `LIVE-1` is dispatched twice
- **THEN** the two work sessions receive different session tokens

#### Scenario: Token is masked
- **WHEN** an agent writes its session token into a status statement or a tool output that Sortie logs
- **THEN** every log record and notification shows the token masked
