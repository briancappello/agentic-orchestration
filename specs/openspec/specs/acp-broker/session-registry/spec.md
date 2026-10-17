# acp-broker/session-registry Specification

## Purpose
Lets human clients find the live session for an issue without knowing broker process IDs. An issue gets a new session for every Sortie dispatch, and clients follow it from one session to the next.

## Requirements

### Requirement: Each broker registers itself
Each broker SHALL write a registry record in the registry directory (`$XDG_RUNTIME_DIR/acp-broker`, or a configured path) when it starts. The record SHALL hold:
- the key and the process ID
- the socket path, and the HTTP URL when the listener is on
- the issue identifier, rule, chain ID, and attempt from the session environment
- the agent name and version from `initialize`, once known
- the session ID, once known
- the start time

The broker SHALL update the record when the session ID or the agent becomes known. It SHALL remove only its own record and socket when it exits.

#### Scenario: Record contents
- **WHEN** a broker for issue `LIVE-1` on rule `implement` has created its session
- **THEN** its registry record names `LIVE-1`, `implement`, the session ID, and its socket path

#### Scenario: Two sessions for one issue
- **WHEN** one broker for `LIVE-1` exits as the next one starts
- **THEN** the exiting broker removes its own record and socket only

### Requirement: The key is the issue
The registry key SHALL be `SORTIE_ISSUE_IDENTIFIER` when set, sanitized to a safe file name. Otherwise it SHALL be the base name of the working directory.

#### Scenario: Under Sortie
- **WHEN** `SORTIE_ISSUE_IDENTIFIER` is `PROJ-12`
- **THEN** the broker's key is `PROJ-12`

### Requirement: Credential checks are not listed
A broker whose `SORTIE_SESSION_PURPOSE` is `credential-check` SHALL relay normally, SHALL NOT register, and SHALL NOT serve viewers.

#### Scenario: Credential check
- **WHEN** Sortie runs a credential check through the broker
- **THEN** no registry record and no socket appear for that process

### Requirement: Clients can list and follow sessions
The broker command SHALL list live sessions: records whose process is alive and whose socket accepts a connection. It SHALL attach to the newest live session for a key. In follow mode, it SHALL move to the next session for that key when the current one ends. It SHALL ignore and remove stale records, meaning records whose process no longer exists.

#### Scenario: Follow across dispatches
- **WHEN** a viewer follows `LIVE-1`
- **AND** the current session ends and a new one starts
- **THEN** the viewer attaches to the new session without user action

#### Scenario: Stale record
- **WHEN** a record names a process that no longer exists
- **THEN** listing does not show it and removes it

### Requirement: Report the HTTP listener to Sortie
A broker that serves HTTP viewers and runs under Sortie, with `SORTIE_API_URL`, `SORTIE_ISSUE_IDENTIFIER`, and `SORTIE_SESSION_TOKEN` set, SHALL report its HTTP URL and its viewer token to Sortie (`sortie/worker-discovery`) after its listener accepts connections. It SHALL retry a failed report with backoff while the session lives. A failed report SHALL NOT stop the session or the relay. A broker without an HTTP listener, or without those variables, SHALL NOT report. A credential-check broker SHALL NOT report.

#### Scenario: A broker under Sortie
- **WHEN** a broker for `LIVE-1` starts with `-http 127.0.0.1:0` under Sortie
- **THEN** after its listener is up, Sortie's state shows its URL for `LIVE-1`

#### Scenario: Sortie unreachable
- **WHEN** the broker cannot reach Sortie
- **THEN** the session runs and viewers on the unix socket are served
- **AND** the broker retries the report
