## Purpose

Defines what may change about a story once agents have started it, and what happens to the stories that depend on one that is cancelled or replaced.

## ADDED Requirements

### Requirement: A started story is frozen
A story SHALL be frozen once an agent has started it: Sortie reports runtime for it, a satisfaction, or a tracker state other than the backlog and release states. The validator SHALL refuse any change to a frozen story's content and any removal of it, naming the story. After a story starts, scope SHALL change only through new stories.

#### Scenario: An edit to a running story
- **WHEN** story `billing/a3` is running
- **AND** the agent edits its title
- **THEN** validation fails with `frozen`, naming `billing/a3`

### Requirement: Amend
An amendment SHALL be a new story that depends on the story it amends. It SHALL be approved and released like any other story.

#### Scenario: More work after a merge
- **WHEN** the agent adds `billing/a3-tax-rounding`, which depends on the merged `billing/a3`
- **THEN** after approval it is ready, since `billing/a3` is approved

### Requirement: Supersede
A deliverable MAY name the story it replaces with `supersedes`. The graph SHALL then send every dependent of the replaced story to the replacement instead. An approver SHALL confirm a supersede in the workbench, which cancels the replaced story through Sortie. The dependents SHALL keep their approval.

#### Scenario: Replacing a running story
- **WHEN** `billing/a3b` declares `supersedes: a3`, and `billing/b1` depends on `a3`
- **AND** an approver confirms the supersede
- **THEN** Sortie cancels `billing/a3`
- **AND** `billing/b1` waits on `billing/a3b`, still approved

### Requirement: Cancel
An approver SHALL be able to cancel a story through Sortie. The direct dependents of a cancelled story SHALL lose their approval, and SHALL read as `needs_rereview` with the reason `blocker_canceled` and the cancelled story's key. A dependent SHALL leave that state when an approver approves it again. Stories further down SHALL only stay held.

#### Scenario: Cancelled without a replacement
- **WHEN** an approver cancels `billing/a3`, and `billing/b1` depends on it
- **THEN** `billing/b1` reads as `needs_rereview`: "blocker billing/a3 was cancelled"

### Requirement: Unverified claims need a person
A story whose no-change claim Sortie reports as `unverified_no_change` SHALL read as `needs_rereview` with that reason. An approver SHALL resolve it by superseding the story or cancelling it.

#### Scenario: A claim without evidence
- **WHEN** Sortie reports `billing/retry` with satisfaction `unverified_no_change`
- **THEN** the workbench shows `billing/retry` as needing re-review, with the reason
