## Purpose

Defines the interactive agent session in the workbench's chat pane. In that session a person and an agent write the OpenSpec change, its breakdown, and the plan of plans, and see the result in the graph as they work.

## ADDED Requirements

### Requirement: Session over acp-broker
The workbench SHALL run each planning session as an ACP session through `acp-broker`. The chat pane SHALL show the session's messages, tool calls, and permission requests through the broker's viewer transport. The chat pane SHALL send the person's messages and permission answers through the same transport. The workbench SHALL work with any ACP agent the broker supports.

#### Scenario: Starting a session
- **WHEN** a person opens the chat pane and starts a planning session for the store
- **THEN** a broker session starts with an ACP agent
- **AND** the chat pane shows the agent's replies as they stream

#### Scenario: A permission request
- **WHEN** the agent asks permission to run a command
- **THEN** the chat pane shows the request with allow and deny controls
- **AND** the person's answer reaches the agent

### Requirement: The spec store is the workspace
A planning session SHALL use the spec store as its working directory. The session's instructions SHALL limit its writes to the store's `openspec/` tree: change artifacts, breakdowns, and `plan.yaml`. The instructions SHALL require the agent to run the plan validator after each change to a breakdown or the plan, and to fix every error it reports before handing back to the person. A planning session SHALL NOT write to tracker issues. Writing to the tracker happens only through a sync that a person approves.

#### Scenario: The agent writes a breakdown
- **WHEN** the person asks the agent to break the `billing` change into deliverables
- **THEN** the agent writes `openspec/changes/billing/breakdown.yaml` in the store and runs the validator
- **AND** no tracker issue changes

### Requirement: Sessions survive a reload
A planning session SHALL outlive the browser tab. When the person reloads the page or opens the workbench elsewhere, the chat pane SHALL reattach to the running session and show its history, using the broker's replay.

#### Scenario: A reload mid-conversation
- **WHEN** the person reloads the workbench during a session
- **THEN** the chat pane shows the earlier messages and continues the same session

### Requirement: The agent can read the selection
When the person selects one or more graph nodes, the workbench SHALL include them in the next message it sends: their plan keys, titles, and kinds, and for synced nodes their tracker identifiers. The chat pane SHALL show which nodes are attached and SHALL let the person remove them before sending.

#### Scenario: Pointing at a node
- **WHEN** the person selects deliverable `billing/invoice` and writes "split this into two"
- **THEN** the message the agent receives names `billing/invoice` and its title
