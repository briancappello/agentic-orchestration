## REMOVED Requirements

### Requirement: Sync with preview
**Reason**: The confirmation repeats the approval, which is already the person's decision to start work. A sync writes only approved stories, deletes nothing, and changes an issue's state only to release it.
**Migration**: Approving, pulling back, cancelling or superseding a story syncs the plan within about a second. The sync status in the top bar shows each sync's result and any failure.

## ADDED Requirements

### Requirement: The approved plan syncs on its own
The workbench SHALL sync a project's plan to the tracker, through Sortie's preview and apply, without asking for confirmation. It SHALL start a sync no more than 2 seconds after any of these: an approval, a pull-back, a cancel, a confirmed supersede, or a change to the project's validated graph. It SHALL run at most one sync of a project at a time. A trigger during a sync SHALL cause exactly one more sync after it. The graph it sends SHALL carry, for each story, its approval, `release`, `review`, `approved_by`, and `approved_at`. While the plan is invalid, the workbench SHALL NOT sync it. When Sortie reports a missing tracker capability, it SHALL NOT apply.

#### Scenario: Approval starts the work
- **WHEN** an approver approves story `billing/b1`, whose blockers are all approved or merged
- **THEN** within 2 seconds the workbench syncs, and `billing/b1` is released
- **AND** no dialog asks the person to confirm

#### Scenario: Several approvals in a row
- **WHEN** an approver approves three stories, one after another, while a sync runs
- **THEN** the workbench runs one more sync after the running one, and that sync carries all three approvals

#### Scenario: An invalid plan
- **WHEN** the planning agent leaves the plan invalid
- **THEN** no sync runs until the plan is valid again
- **AND** the sync status says the plan is invalid

### Requirement: A release asks Sortie to poll at once
After a sync that released at least one story, the workbench SHALL ask Sortie to poll its tracker at once (`POST /api/v1/refresh`, with Sortie's control token). A failure of that request SHALL NOT fail the sync; the story then starts at Sortie's next poll.

#### Scenario: A released story starts without waiting for the poll
- **WHEN** a sync releases `billing/b1`
- **THEN** the workbench calls Sortie's refresh once
- **AND** Sortie dispatches `billing/b1` on that poll, not on the next timed poll

### Requirement: Sync status
The workbench SHALL show each project's sync status in the top bar: syncing; synced, with the time of the last successful sync; or failed, with the reason. The status SHALL update live, as the graph does. Opening it SHALL show the last sync's result: the issues created and updated, the stories released, the orphaned issues, and any failed write. A failed sync SHALL be retried with backoff of at most 60 seconds, and at the next trigger. A person with the `planner` role SHALL be able to retry a failed sync at once.

#### Scenario: Sortie is unreachable
- **WHEN** a sync fails because Sortie does not answer
- **THEN** the top bar shows the sync as failed, and says Sortie is unreachable
- **AND** the workbench retries within 60 seconds, and the status turns to synced once a sync succeeds

#### Scenario: The last result
- **WHEN** a person opens the sync status after a sync that released `billing/b1` and orphaned `billing/old`
- **THEN** it lists `billing/b1` as released and `billing/old` as orphaned
