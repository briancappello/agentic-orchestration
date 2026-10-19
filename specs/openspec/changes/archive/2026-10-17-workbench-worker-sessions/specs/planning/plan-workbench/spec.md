## MODIFIED Requirements

### Requirement: Two-pane layout
The workbench SHALL show a graph pane and a chat pane side by side. On viewports at least 1200px wide, the graph pane SHALL take 60% of the width and the chat pane 40%. On narrower viewports, the panes SHALL stack, with the graph first. The chat pane SHALL hold the planning session, or a worker's session that a person watches (`planning/worker-sessions`), and SHALL say which it holds. The workbench SHALL be a standalone application. It SHALL NOT be embedded in Sortie or in the tracker.

#### Scenario: Desktop layout
- **WHEN** the workbench opens at 1440px wide
- **THEN** the graph pane is 864px wide and the chat pane 576px

#### Scenario: The chat pane holds a worker
- **WHEN** a person watches the worker of `billing/b1`
- **THEN** the chat pane's header names `billing/b1` and its tracker identifier, and offers a return to planning

### Requirement: Selection details
Selecting a node SHALL show its details:
- spec reference and acceptance criteria;
- dependencies and what it unblocks;
- tracker link when synced;
- runtime state, and, for a running story whose broker reported, an offer to watch its worker;
- for a story, its plan status and why: the blockers that hold it, the reason it needs re-review, or that it is frozen; its approver and review gate.

To a person with the `approver` role, a selected story SHALL offer the actions its status allows: approve a draft, pull back a released story that has not started, cancel, and confirm a supersede that its replacement declares. A selected epic with no approved story SHALL offer to approve the epic. The epic view SHALL let an approver approve every draft story of the epic at once.

Selecting a node SHALL also offer it to the chat as context. With nothing selected, the workbench SHALL list what is ready to start, where agents are active, and which nodes lack a spec.

#### Scenario: Nothing selected
- **WHEN** no node is selected at the project level
- **THEN** the workbench lists the epics that are ready to start, those with agent activity, and those without a spec

#### Scenario: A planner selects a draft
- **WHEN** a person with only the `planner` role selects a draft story
- **THEN** no approve action is offered

#### Scenario: A running story offers its worker
- **WHEN** a person selects a story whose worker runs and whose broker reported
- **THEN** its details offer to watch the worker
