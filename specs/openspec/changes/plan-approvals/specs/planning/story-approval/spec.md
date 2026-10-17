## Purpose

Records which plan stories a person approved, in the plan workbench, where the planning agent cannot write, so that approval can safely send work to agents.

## ADDED Requirements

### Requirement: Approval is recorded by the workbench
The workbench SHALL record each approval in its own database, never in the spec store. A record SHALL hold the story's plan key, the digest of the story's content at approval, the approver's stable identity and display name (`planning/workbench-identity`), and the time. Only a person with the `approver` role SHALL approve. The planning agent SHALL have no way to create, change, or remove a record.

#### Scenario: The agent cannot approve
- **WHEN** the planning agent writes `status: approved` into a breakdown
- **THEN** no story of that change reads as approved

#### Scenario: A planner cannot approve
- **WHEN** a person with only the `planner` role asks to approve a story
- **THEN** the workbench answers `403` with `role_required` and records nothing

### Requirement: Each story has its own digest
The digest of a story SHALL cover every field of its deliverable: id, title, kind, `depends_on`, `covers`, `acceptance_criteria`, `notes`, `review`, and `supersedes`. A story SHALL read as approved only while its current digest equals the digest of its approval. A change to one story SHALL return only that story to draft.

#### Scenario: One story edited
- **WHEN** epic `billing` has four approved stories
- **AND** the agent edits the acceptance criteria of `billing/tax`
- **THEN** `billing/tax` reads as draft
- **AND** the other three still read as approved

### Requirement: The first approval covers the epic
An approver SHALL be able to approve an epic that has no approved story yet. That approval SHALL approve every story the epic has at that moment (batch 0), each with its own digest. After that, an approver SHALL approve draft stories of the epic one at a time or several together. An epic SHALL read as approved once any of its stories is approved.

#### Scenario: Batch 0, then one more
- **WHEN** an approver approves epic `billing` with stories `a`, `b`, and `c`
- **AND** the agent then adds story `d`
- **THEN** `a`, `b`, and `c` read as approved and `d` reads as draft
- **AND** approving `d` alone leaves the other three approved

### Requirement: Approvals made in a breakdown before this change are imported
When the workbench opens a project whose breakdown says `status: approved` with an `approved_digest` that still matches, and the workbench holds no approval for that change, it SHALL import the change as batch 0, recorded as approved by `migration`. It SHALL ignore `status` and `approved_digest` after that.

#### Scenario: An existing approved epic
- **WHEN** a project's `billing` breakdown was approved under the old format
- **THEN** after the workbench opens it, every story of `billing` reads as approved by `migration`
