## Purpose

Protects the HTTP endpoints that change Sortie's runtime behavior, so they can safely be reached from a broker, a web client, or a phone.

## ADDED Requirements

### Requirement: Bearer token for state-changing endpoints
When `server.control_token` is set, Sortie SHALL require `Authorization: Bearer <token>` on every endpoint that changes runtime state: refresh, hold, release, and escalate. A missing or wrong token SHALL receive `401`, and Sortie SHALL take no action. Sortie SHALL compare tokens in constant time. The token SHALL support `$VAR` indirection like other secrets and SHALL be registered for masking.

#### Scenario: Missing token
- **WHEN** a control token is configured
- **AND** a caller posts to `/api/v1/LIVE-1/hold` without an `Authorization` header
- **THEN** Sortie answers `401`
- **AND** the run is not held

#### Scenario: Correct token
- **WHEN** a caller posts to `/api/v1/LIVE-1/hold` with the configured token
- **THEN** Sortie processes the request

### Requirement: No token, loopback only
When `server.control_token` is not set, Sortie SHALL serve state-changing endpoints only on a loopback bind address. Sortie SHALL refuse to start when `server.host` is not a loopback address and no control token is set, and SHALL report a configuration error that names `server.control_token`.

#### Scenario: Default local setup
- **WHEN** `server.host` is `127.0.0.1` and no control token is set
- **THEN** Sortie starts
- **AND** hold, release, escalate, and refresh work without a token

#### Scenario: Exposed without a token
- **WHEN** `server.host` is `0.0.0.0` and no control token is set
- **THEN** Sortie refuses to start with a configuration error naming `server.control_token`

### Requirement: Read-only endpoints unchanged
The dashboard, `/api/v1/state`, the per-issue detail, the health probes, and `/metrics` SHALL keep their current access rules. A control token SHALL NOT be required for them.

#### Scenario: Scrape with a token configured
- **WHEN** a control token is configured
- **AND** Prometheus scrapes `/metrics` without a token
- **THEN** Sortie serves the metrics
