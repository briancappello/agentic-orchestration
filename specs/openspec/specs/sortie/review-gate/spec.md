# sortie/review-gate Specification

## Purpose
Makes each story pass its own review before it merges: either a person merges the pull request in the forge, or a separate agent checks the story's acceptance criteria and Sortie merges it.

## Requirements

### Requirement: Each story names its gate
With plan control on, each story node in the plan graph SHALL carry `review`, `human` or `criteria`. A sync SHALL record that gate on the story's issue as the label `sortie-review:human` or `sortie-review:criteria`, and SHALL keep exactly one such label on it. A sync SHALL NOT add, change, or remove any other label. Dispatch rules SHALL be able to match these labels like any other label.

#### Scenario: The gate is on the issue
- **WHEN** story `billing/invoice` carries `review: criteria`
- **THEN** after the sync its issue carries the label `sortie-review:criteria` and no `sortie-review:human`

#### Scenario: The gate changes before release
- **WHEN** story `billing/invoice` changes from `review: criteria` to `review: human`
- **THEN** the next sync replaces `sortie-review:criteria` with `sortie-review:human`

### Requirement: The human gate
A story with the label `sortie-review:human` SHALL reach the merge only when a person merges its pull request in the forge. Sortie's auto-merge SHALL NOT merge it.

#### Scenario: Auto-merge leaves a human story alone
- **WHEN** auto-merge is configured
- **AND** the pull request of a `sortie-review:human` story is clean, approved, and green
- **THEN** Sortie does not merge it

### Requirement: The criteria gate
A story with the label `sortie-review:criteria` SHALL pass a criteria stage before it merges. A criteria stage is a stage in a chain (`next`) whose session SHALL be a new agent session, separate from every session that implemented the story. It SHALL check the story's acceptance criteria against the pull request. When it passes, Sortie's auto-merge SHALL be allowed to merge the pull request. When it fails, Sortie SHALL NOT merge, SHALL send the story back for implementation or escalate it as the workflow configures, and SHALL say which criteria failed. The self-review of an implementing session SHALL NOT count as the criteria stage. Sortie SHALL refuse, at start and on reload, a plan-control workflow whose rules match `sortie-review:criteria` but offer no criteria stage.

#### Scenario: Criteria pass
- **WHEN** the criteria stage of `billing/invoice` passes every acceptance criterion
- **THEN** auto-merge may merge its pull request
- **AND** after the merge, `billing/invoice` satisfies the stories it blocks

#### Scenario: Criteria fail
- **WHEN** the criteria stage finds that criterion 2 of `billing/invoice` is not met
- **THEN** the pull request is not merged
- **AND** the story's tracker comment names criterion 2

#### Scenario: Self-review is not the gate
- **WHEN** the implementing session of a `sortie-review:criteria` story writes a passing self-review verdict
- **THEN** auto-merge still does not merge the pull request until a criteria stage passes
