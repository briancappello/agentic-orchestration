# sortie/held-runs Specification

## Purpose
Lets a human, through the ACP broker or another authorized caller, pause Sortie's clock on a running issue while a person works in its session, without Sortie treating the pause as a stall or a timeout.

## Requirements

### Requirement: Hold a running issue
Sortie SHALL accept `POST /api/v1/{identifier}/hold` with an optional JSON body `{"reason": "<text>", "holder": "<text>"}`. When the issue has a running worker, Sortie SHALL mark that run as held and answer `200` with the run's held state. When the issue has no running worker, Sortie SHALL answer `409`. When the identifier is unknown, Sortie SHALL answer `404`. Holding a run that is already held SHALL succeed and keep the original start time of the hold.

#### Scenario: Hold a running issue
- **WHEN** issue `LIVE-1` has a running worker
- **AND** a caller posts to `/api/v1/LIVE-1/hold` with reason `human takeover`
- **THEN** Sortie answers `200`
- **AND** `/api/v1/state` shows the run as held with reason `human takeover` and the time the hold began

#### Scenario: Hold an issue that is not running
- **WHEN** issue `LIVE-2` is known but has no running worker
- **AND** a caller posts to `/api/v1/LIVE-2/hold`
- **THEN** Sortie answers `409`

#### Scenario: Hold twice
- **WHEN** a run was held at 10:00
- **AND** a second hold request arrives at 10:05
- **THEN** Sortie answers `200`
- **AND** the hold still shows 10:00 as its start

### Requirement: Release a held issue
Sortie SHALL accept `POST /api/v1/{identifier}/release`. When the run is held, Sortie SHALL end the hold, add the held duration to the run's total held time, and answer `200`. When the run is not held, Sortie SHALL answer `200` and change nothing.

#### Scenario: Release after a takeover
- **WHEN** the run of `LIVE-1` has been held for 90 seconds
- **AND** a caller posts to `/api/v1/LIVE-1/release`
- **THEN** Sortie answers `200`
- **AND** the run is no longer held
- **AND** its total held time is at least 90 seconds

### Requirement: Holding suspends stall and turn timeouts
While a run is held, Sortie SHALL NOT stop it for stalling, and SHALL NOT end its current turn for exceeding `agent.turn_timeout_ms`. When the hold ends, the stall clock SHALL restart from the release time. The turn deadline SHALL be extended by the time the turn spent held.

#### Scenario: No stall during a long hold
- **WHEN** `agent.stall_timeout_ms` is 300000
- **AND** a run is held for 20 minutes with no agent events
- **THEN** Sortie does not stop the run for stalling during the hold

#### Scenario: Stall clock restarts at release
- **WHEN** a held run is released at 10:30
- **AND** no agent events arrive after the release
- **THEN** Sortie treats the run as stalled no earlier than 10:30 plus `agent.stall_timeout_ms`

#### Scenario: Turn deadline extended
- **WHEN** `agent.turn_timeout_ms` is 1800000
- **AND** a turn is held for 10 minutes in total
- **THEN** Sortie ends that turn for timeout no earlier than 40 minutes after it began

### Requirement: Holding does not suspend tracker safety
A hold SHALL NOT suspend reconciliation against the tracker. When the issue reaches a terminal state or leaves the active states, Sortie SHALL stop the held run exactly as it stops an unheld run. Holding SHALL NOT suspend the per-issue token ceiling.

#### Scenario: Issue closed while held
- **WHEN** a run is held
- **AND** the tracker reports the issue as `Done`
- **THEN** Sortie stops the run and ends the hold

### Requirement: A hold ends with its run
When a held run's worker exits for any reason, Sortie SHALL end the hold and record the held time for that run.

#### Scenario: Worker exits while held
- **WHEN** a run is held
- **AND** its worker exits
- **THEN** the issue is no longer shown as held
- **AND** the run history row for that run records its total held time

### Requirement: Held state is visible and measured
Sortie SHALL include, for every held run, in `/api/v1/state` and the per-issue detail: whether it is held, the hold reason, the holder, and the time the hold began. The dashboard SHALL mark held runs. Sortie SHALL expose a gauge of currently held runs. It SHALL also expose a counter of hold durations, so that held time per rule can be derived. Each run history row SHALL record the run's total held time in milliseconds.

#### Scenario: Metrics during a hold
- **WHEN** one run is held
- **THEN** the held-runs gauge reads 1

#### Scenario: Held time per stage
- **WHEN** runs on rule `implement` were held for 60 and 120 seconds
- **THEN** their run history rows record 60000 and 120000 milliseconds of held time
