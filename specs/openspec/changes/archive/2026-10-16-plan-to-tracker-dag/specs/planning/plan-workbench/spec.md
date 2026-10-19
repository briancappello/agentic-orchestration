## Purpose

Defines the standalone web app where a person shapes the plan with a planning agent, watches the graph change, syncs it to the tracker, and then follows its execution. It shows draft, synced, and in-flight work as one graph.

## ADDED Requirements

### Requirement: Two-pane layout
The workbench SHALL show a graph pane and a chat pane side by side. On viewports at least 1200px wide, the graph pane SHALL take 60% of the width and the chat pane 40%. On narrower viewports, the panes SHALL stack, with the graph first. The workbench SHALL be a standalone application. It SHALL NOT be embedded in Sortie or in the tracker.

#### Scenario: Desktop layout
- **WHEN** the workbench opens at 1440px wide
- **THEN** the graph pane is 864px wide and the chat pane 576px

### Requirement: Graph flows from ready to done
The graph pane SHALL place each node in a column by the length of its longest chain of dependencies within the current view. Nodes with no dependencies in the view SHALL sit in the leftmost column. The view SHALL end on the right at a completion marker. The pane SHALL scroll horizontally when the columns do not fit. Edges SHALL run from blocking node to blocked node.

#### Scenario: A chain of three
- **WHEN** C depends on B and B depends on A
- **THEN** A, B, and C sit in three columns from left to right

### Requirement: Two levels of detail
The project level SHALL show only epics and the dependencies between epics. Opening an epic SHALL show only that epic's stories and the dependencies between them. A story's dependencies on stories in other epics SHALL be shown at the story level as references to those stories, and the person SHALL be able to hide them. The person SHALL be able to return to the project level in one action.

#### Scenario: Drilling down
- **WHEN** the person opens epic `billing`
- **THEN** the graph shows only `billing`'s stories
- **AND** a story that depends on `accounts-api/accounts-close` shows that dependency as a reference to it

### Requirement: Node encoding
Every node SHALL show its plan key or tracker identifier, its title, and its state. The border colour SHALL encode done, in progress, or not started. A node without a spec SHALL be visibly distinct from a node with one, by fill and not only by colour. An epic node SHALL show its stories' progress as done out of total. A node with Sortie runtime state SHALL show it as a badge: running, retrying, or budget held.

#### Scenario: An unplanned story
- **WHEN** a story has no spec coverage
- **THEN** its node has the unplanned fill and a "no spec" marker

#### Scenario: A running agent
- **WHEN** Sortie reports a running worker on a story
- **THEN** that story's node shows a running badge
- **AND** its epic shows that an agent is running in it

### Requirement: One graph from three sources
The workbench backend SHALL build the graph from three sources, matching nodes by plan key:
- the validated plan graph, from running the plan validator on the store;
- Sortie's `/api/v1/plan/graph`;
- Sortie's runtime state.

A node only in the store SHALL appear as a draft. A node in both SHALL appear as synced and SHALL show the tracker's state. A node in the tracker but no longer in the store SHALL appear as orphaned. The backend SHALL never call a tracker directly.

#### Scenario: Draft beside synced
- **WHEN** `billing/invoice` is synced and the agent has just added `billing/tax` to the breakdown
- **THEN** both appear in the `billing` epic
- **AND** `billing/tax` is marked as a draft

### Requirement: Live redraw
When a file in the store's `openspec/` tree changes, the graph pane SHALL redraw within two seconds without a page reload, and SHALL keep the person's current level, selection, and scroll position. The graph pane SHALL refresh Sortie runtime state at least every ten seconds.

#### Scenario: The agent adds a deliverable
- **WHEN** the planning agent saves a breakdown with a new deliverable
- **THEN** the new node appears within two seconds
- **AND** the view stays on the same epic

### Requirement: Invalid plans are shown, not hidden
When the plan or a breakdown fails validation, the workbench SHALL keep showing the last valid graph. It SHALL show every validation error with the deliverable or change it names. Selecting an error SHALL select the affected node when that node exists.

#### Scenario: The agent introduces a cycle
- **WHEN** a saved breakdown contains a dependency cycle
- **THEN** the graph keeps its previous state
- **AND** the workbench lists the cycle with the deliverables involved

### Requirement: Selection details
Selecting a node SHALL show its details:
- spec reference and acceptance criteria;
- dependencies and what it unblocks;
- tracker link when synced;
- runtime state.

Selecting a node SHALL also offer it to the chat as context. With nothing selected, the workbench SHALL list what is ready to start, where agents are active, and which nodes lack a spec.

#### Scenario: Nothing selected
- **WHEN** no node is selected at the project level
- **THEN** the workbench lists the epics that are ready to start, those with agent activity, and those without a spec

### Requirement: Sync with preview
The workbench SHALL offer a sync action. It SHALL request a preview from Sortie and show the writes listed there. The sync SHALL apply only after the person confirms. When the configured tracker lacks a needed capability, the workbench SHALL show which capability is missing and SHALL NOT offer to apply.

#### Scenario: Confirming a sync
- **WHEN** the person starts a sync
- **THEN** the workbench shows how many issues will be created and updated and how many relations will be added and removed
- **AND** nothing reaches the tracker until the person confirms

### Requirement: Access
The workbench SHALL require a person to sign in before showing any plan or chat. It SHALL use its own server-side credentials for Sortie and `acp-broker`, and SHALL never expose those credentials to the browser.

#### Scenario: Credentials stay server-side
- **WHEN** a person uses the workbench
- **THEN** no response to the browser contains the Sortie or broker token
