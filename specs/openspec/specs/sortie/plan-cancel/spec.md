# sortie/plan-cancel Specification

## Purpose
Lets a plan client cancel a story, which stops its worker if one runs, so that a story the plan no longer wants never finishes or retries.

## Requirements

### Requirement: Cancel a story
With plan control on, Sortie SHALL provide `POST /api/v1/plan/cancel` with a story's plan key. Sortie SHALL take the request on the same path that decides dispatch. Sortie SHALL:
- stop the story's worker when one runs, and end its agent session and its broker;
- drop the story's queued retry, its claim, and its pending reactions;
- move the issue to `tracker.cancel_state`;
- record the run as cancelled.

A cancelled story SHALL NOT be retried, and SHALL NOT be dispatched again while it stays in `tracker.cancel_state`. Its workspace SHALL be cleaned up as for any other terminal state. A story already in `tracker.cancel_state` SHALL get `200` and no change. A story in another terminal state SHALL get `409` with the code `already_terminal`. An unknown plan key SHALL get `404`.

#### Scenario: Cancel a running story
- **WHEN** story `billing/a3` has a running worker
- **AND** a client cancels it
- **THEN** the worker stops, and its agent process and broker exit
- **AND** the issue is in `Canceled`
- **AND** no retry is queued for it

#### Scenario: Cancel a story that waits
- **WHEN** story `billing/a3` is in `Backlog`
- **AND** a client cancels it
- **THEN** the issue is in `Canceled`

#### Scenario: Cancel a story that merged
- **WHEN** story `billing/a3` is in `Done`
- **AND** a client cancels it
- **THEN** Sortie answers `409` with `already_terminal`
- **AND** the issue stays in `Done`

#### Scenario: Cancel twice
- **WHEN** story `billing/a3` is already in `Canceled`
- **AND** a client cancels it again
- **THEN** Sortie answers `200` and changes nothing

### Requirement: Cancelling does not satisfy dependents
A cancelled story SHALL NOT satisfy any story that it blocks. This rule is stated in full in `sortie/blocker-satisfaction`.

#### Scenario: A dependent of a cancelled story
- **WHEN** story `billing/b1` is blocked by `billing/a3`
- **AND** a client cancels `billing/a3`
- **THEN** `billing/b1` is not dispatched
