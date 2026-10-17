## MODIFIED Requirements

### Requirement: Node encoding
Every node SHALL show its plan key or tracker identifier, its title, and its state. The border colour SHALL encode done, in progress, or not started. A node without a spec SHALL be visibly distinct from a node with one, by fill and not only by colour. An epic node SHALL show its stories' progress as done out of total. A node with Sortie runtime state SHALL show it as a badge: running, retrying, or budget held. A story SHALL also show its plan status: draft, held, ready, released, frozen, or needs re-review.

#### Scenario: An unplanned story
- **WHEN** a story has no spec coverage
- **THEN** its node has the unplanned fill and a "no spec" marker

#### Scenario: A running agent
- **WHEN** Sortie reports a running worker on a story
- **THEN** that story's node shows a running badge
- **AND** its epic shows that an agent is running in it

#### Scenario: A held story
- **WHEN** a story is approved but a blocker is not
- **THEN** its node reads "held"

### Requirement: Selection details
Selecting a node SHALL show its details:
- spec reference and acceptance criteria;
- dependencies and what it unblocks;
- tracker link when synced;
- runtime state;
- for a story, its plan status and why: the blockers that hold it, the reason it needs re-review, or that it is frozen; its approver and review gate.

To a person with the `approver` role, a selected story SHALL offer the actions its status allows: approve a draft, pull back a released story that has not started, cancel, and confirm a supersede that its replacement declares. A selected epic with no approved story SHALL offer to approve the epic. The epic view SHALL let an approver approve every draft story of the epic at once.

Selecting a node SHALL also offer it to the chat as context. With nothing selected, the workbench SHALL list what is ready to start, where agents are active, and which nodes lack a spec.

#### Scenario: Nothing selected
- **WHEN** no node is selected at the project level
- **THEN** the workbench lists the epics that are ready to start, those with agent activity, and those without a spec

#### Scenario: A planner selects a draft
- **WHEN** a person with only the `planner` role selects a draft story
- **THEN** no approve action is offered

### Requirement: Sync with preview
The workbench SHALL offer a sync action. It SHALL request a preview from Sortie and show the writes listed there, releases and approvals included. The graph it sends SHALL carry, for each story, its approval, `release`, `review`, `approved_by`, and `approved_at`. The sync SHALL apply only after the person confirms. When the configured tracker lacks a needed capability, the workbench SHALL show which capability is missing and SHALL NOT offer to apply.

#### Scenario: Confirming a sync
- **WHEN** the person starts a sync
- **THEN** the workbench shows how many issues will be created and updated, how many relations will be added and removed, and how many stories will be released
- **AND** nothing reaches the tracker until the person confirms
