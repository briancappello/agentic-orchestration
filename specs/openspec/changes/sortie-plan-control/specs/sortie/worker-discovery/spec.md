## Purpose

Lets a client find the broker of each running worker through Sortie, and get the token to watch it, without access to the files on Sortie's host.

## ADDED Requirements

### Requirement: The broker reports its address
Sortie SHALL provide `POST /api/v1/{identifier}/broker`, which takes the broker's HTTP URL and its viewer token. Sortie SHALL accept it only with the session token minted for that issue's current run (`sortie/control-api-auth`). Sortie SHALL keep the URL and the token only in memory, with the running entry, and SHALL forget both when the run ends. Sortie SHALL register the viewer token for masking and SHALL NOT write it to run history or logs. A report for an issue that has no running worker SHALL get `404`.

#### Scenario: A broker reports
- **WHEN** the broker of `LIVE-1` posts its URL and viewer token with the session token of the current run
- **THEN** Sortie keeps both with the running entry of `LIVE-1`

#### Scenario: The run ends
- **WHEN** the run of `LIVE-1` ends
- **THEN** Sortie no longer reports a broker for `LIVE-1`

### Requirement: The address is in the state
`GET /api/v1/state` and `GET /api/v1/{identifier}` SHALL carry, for each running issue whose broker reported, `broker.http_url`. They SHALL NOT carry the viewer token. An issue whose broker did not report SHALL carry `broker: null`.

#### Scenario: The address without the token
- **WHEN** the broker of `LIVE-1` reported
- **THEN** `/api/v1/state` shows `LIVE-1` with its `broker.http_url`
- **AND** the response holds no viewer token

### Requirement: The token needs operator scope
Sortie SHALL provide `GET /api/v1/{identifier}/broker`. It SHALL return the broker's URL and viewer token. It SHALL require the control token, and SHALL refuse a session token with `403`. An issue with no reported broker SHALL get `404`.

#### Scenario: A client gets the token
- **WHEN** a client with the control token requests `/api/v1/LIVE-1/broker`
- **THEN** the response holds the URL and the viewer token

#### Scenario: A session token cannot read it
- **WHEN** a caller requests `/api/v1/LIVE-1/broker` with a session token
- **THEN** Sortie answers `403`
