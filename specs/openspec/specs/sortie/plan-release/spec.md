# sortie/plan-release Specification

## Purpose
Lets a plan client release approved stories to the agents, and pull back a released story that no worker has started yet, without a person changing the story's state in the tracker.

## Requirements

### Requirement: Plan control settings
Sortie SHALL turn on plan control when `tracker.release_state` is set. With plan control on, Sortie SHALL require these settings and SHALL refuse to start, and refuse a reload, when one of them is missing or wrong:
- `tracker.release_state`: the state a released story moves to. It SHALL be in `tracker.active_states`.
- `tracker.backlog_state`: the state a story waits in before it is released, and returns to on a pull-back. It SHALL be in neither `tracker.active_states` nor `tracker.terminal_states`.
- `tracker.cancel_state`: the state a cancelled story moves to. It SHALL be in `tracker.terminal_states`.
- `tracker.done_state`: the state that satisfies a blocker without a plan key. It SHALL be in `tracker.terminal_states`.
- `reactions.merge_completion`, configured.

The configuration error SHALL name each setting that is missing or wrong. When the adapter can list the project's states, Sortie SHALL also refuse a state name the project does not have. With plan control off, Sortie SHALL behave as it did before this change.

#### Scenario: Plan control on
- **WHEN** a workflow sets `release_state: Todo`, `backlog_state: Backlog`, `cancel_state: Canceled`, and `done_state: Done`, and configures merge completion
- **THEN** Sortie starts with plan control on

#### Scenario: A release state that is not active
- **WHEN** `tracker.release_state` is `Backlog`, and `Backlog` is not in `tracker.active_states`
- **THEN** Sortie refuses to start with a configuration error that names `tracker.release_state`

#### Scenario: Plan control without merge completion
- **WHEN** `tracker.release_state` is set and `reactions.merge_completion` is not configured
- **THEN** Sortie refuses to start with a configuration error that names `reactions.merge_completion`

### Requirement: Release through sync
With plan control on, each story node in the plan graph SHALL carry `release`, `true` or `false`. A sync SHALL move a story whose node carries `release: true` to `tracker.release_state` only when the story's issue is in `tracker.backlog_state`. The preview SHALL list each such move as a release. A sync SHALL NOT move an issue in any other state, and SHALL NOT move an issue whose node carries `release: false`. A sync SHALL NOT release an epic. New issues that a sync creates SHALL start in `tracker.backlog_state`. A sync SHALL release a new issue in the same apply that creates it, only after its blocking relations are written.

#### Scenario: Release a ready story
- **WHEN** story `billing/invoice` is in `Backlog` and its node carries `release: true`
- **THEN** the preview lists one release for `billing/invoice`
- **AND** after the apply the issue is in `Todo`

#### Scenario: A held story stays put
- **WHEN** story `billing/refund` is in `Backlog` and its node carries `release: false`
- **THEN** the sync does not move it

#### Scenario: A story a person moved on
- **WHEN** story `billing/invoice` carries `release: true` and is in `In Progress`
- **THEN** the sync does not move it, and the preview lists no release for it

#### Scenario: A new story released in one apply
- **WHEN** a sync creates story `billing/tax`, which carries `release: true` and is blocked by `billing/invoice`
- **THEN** the apply creates the issue in `Backlog`, writes its blocking relation, and then moves it to `Todo`

### Requirement: Atomic pull-back
Sortie SHALL provide `POST /api/v1/plan/pull-back` with a story's plan key. Sortie SHALL take the request on the same path that decides dispatch, so that the request and a dispatch cannot both win. When no worker runs, retries, or holds a claim on the story, Sortie SHALL move its issue to `tracker.backlog_state`. Sortie SHALL then not dispatch that story until a poll no longer reports its issue in an active state. That block SHALL expire after a bounded time, so that a tracker that never shows the move cannot block the story forever. When a worker already claimed the story, Sortie SHALL answer `409` with the code `already_claimed`, and SHALL change nothing. A story that is not in `tracker.release_state` SHALL get `409` with the code `not_released`. An unknown plan key SHALL get `404`.

#### Scenario: Pull back before dispatch
- **WHEN** story `billing/invoice` is in `Todo` and no worker has claimed it
- **AND** a client pulls it back
- **THEN** the issue is in `Backlog`
- **AND** the next poll does not dispatch it

#### Scenario: Pull back loses to dispatch
- **WHEN** a worker claimed story `billing/invoice`, and the tracker still shows `Todo`
- **AND** a client pulls it back
- **THEN** Sortie answers `409` with `already_claimed`
- **AND** the worker keeps running

#### Scenario: The mark outlives a stale poll
- **WHEN** a client pulled back `billing/invoice`
- **AND** the next poll still reads the issue in `Todo` from a stale tracker read
- **THEN** Sortie does not dispatch it
