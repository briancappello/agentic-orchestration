## Purpose

Tells the agent process, and any wrapper that launches it, which issue, stage, and run it serves. Telemetry, the ACP broker, and human tools can then label and find the session without guessing from the working directory.

## ADDED Requirements

### Requirement: Agent process receives session identity
When Sortie launches an agent process for a work session, the process environment SHALL contain these variables:

- `SORTIE_ISSUE_ID`
- `SORTIE_ISSUE_IDENTIFIER`
- `SORTIE_DISPATCH_ID`
- `SORTIE_ATTEMPT`, the attempt number, or empty for a first dispatch
- `SORTIE_RULE`, the selected dispatch rule name, or empty when no named rule applies
- `SORTIE_CHAIN_ID`, the stage chain identifier, or empty when the run belongs to no chain
- `SORTIE_WORKSPACE`, the workspace path
- `SORTIE_API_URL`, the base URL of Sortie's HTTP server, or empty when the server is disabled

Each value SHALL be the one Sortie records for the same run in its run history.

#### Scenario: Local launch carries the identity
- **WHEN** Sortie starts a local agent process for issue `LIVE-1` on rule `implement` in chain `c-42`
- **THEN** the process environment has `SORTIE_ISSUE_IDENTIFIER=LIVE-1`, `SORTIE_RULE=implement`, and `SORTIE_CHAIN_ID=c-42`
- **AND** the run history row for that run has the same rule name and chain ID

#### Scenario: Server disabled
- **WHEN** `server.port` is `0`
- **THEN** the agent process has `SORTIE_API_URL` set to the empty string

### Requirement: Remote launch carries the identity
When Sortie launches an agent process on an SSH worker host, the remote process SHALL receive the same session identity variables with the same values as a local launch. Sortie SHALL deliver them the way it already delivers other variables to the remote agent, never as process arguments.

#### Scenario: SSH launch
- **WHEN** Sortie starts the agent for issue `LIVE-1` on an SSH worker host
- **THEN** the remote agent process has `SORTIE_ISSUE_IDENTIFIER=LIVE-1`
- **AND** no session identity value appears in the SSH command line

### Requirement: Credential check launches are marked
A launch that only verifies credentials, and runs no work, SHALL set `SORTIE_SESSION_PURPOSE=credential-check`. Every work session launch SHALL set `SORTIE_SESSION_PURPOSE=work`. This lets wrappers and the ACP broker ignore the short-lived credential session.

#### Scenario: Credential check before work
- **WHEN** Sortie runs a credential check and then a work session for one dispatch
- **THEN** the first agent process has `SORTIE_SESSION_PURPOSE=credential-check`
- **AND** the second has `SORTIE_SESSION_PURPOSE=work`

### Requirement: Session identity does not override operator variables
A session identity variable SHALL override a variable of the same name from the orchestrator's own environment. Sortie SHALL NOT add, remove, or change any other variable in the agent environment because of this capability.

#### Scenario: Stale value in the orchestrator environment
- **WHEN** the orchestrator process was started with `SORTIE_ISSUE_ID=old`
- **AND** Sortie launches an agent for issue ID `42`
- **THEN** the agent process has `SORTIE_ISSUE_ID=42`
