# sortie/plan-graph-api Specification

## Purpose
Lets the workbench, and any other client, read the plan as the tracker holds it, in a shape that does not depend on any one tracker. Those clients never call a tracker directly.

## Requirements

### Requirement: Read the synced plan graph
Sortie SHALL provide `GET /api/v1/plan/graph`. It SHALL return the configured project's plan-keyed issues as nodes and their relations as edges.

Each node SHALL carry:
- id and identifier;
- plan key and kind (`epic` or `story`);
- title, state name, and whether that state is terminal;
- URL;
- parent id.

With plan control on, each story node SHALL also carry:
- its review gate, from its review label;
- its approver and approval time, when the adapter declares **approval fields**;
- its satisfaction: `merged`, `no_change_confirmed`, `unverified_no_change`, `canceled`, or `null`;
- its merge commit and its pull request (as `owner/repo#number`), when Sortie holds them;
- for each of its blockers that is not satisfied, the blocker's id and the reason (`sortie/blocker-satisfaction`);
- a proposed supersede, when its no-change claim cites a plan key (`sortie/no-change-evidence`).

Each edge SHALL carry the blocking issue's id and the blocked issue's id. Issues without a plan key SHALL be omitted unless the request sets `include_unkeyed=true`.

#### Scenario: Read after a sync
- **WHEN** a sync created 2 epics and 5 stories
- **AND** a client requests `/api/v1/plan/graph`
- **THEN** the response holds 7 nodes with their plan keys, parents, and states, and every blocking edge

#### Scenario: Unkeyed issues
- **WHEN** the project also holds a bug that no plan created
- **THEN** the default response omits it
- **AND** a request with `include_unkeyed=true` includes it with no plan key

#### Scenario: A merged story
- **WHEN** Sortie latched the merge commit of story `billing/a3`
- **THEN** its node carries satisfaction `merged`, the merge commit, and the pull request

#### Scenario: A story that waits
- **WHEN** story `billing/b1` is blocked by `billing/a3`, which is in `Canceled`
- **THEN** the node of `billing/b1` lists `billing/a3` with the reason `canceled`

### Requirement: Live state joined in
Each node SHALL also carry its Sortie runtime state when it has one: `running` with turn count and last message, `retrying` with attempt number, or `budget_held`. Nodes with none SHALL carry no runtime state. The response SHALL include the time it was generated.

#### Scenario: A running story
- **WHEN** story `billing/invoice` has a running worker
- **THEN** its node carries runtime state `running` with the worker's turn count

### Requirement: Tracker-independent shape
The response SHALL use the same fields whatever the tracker. When the adapter does not support a field, the field SHALL be `null`, never omitted. The response SHALL list the adapter's declared write capabilities, so a client can tell which actions are possible.

#### Scenario: Same shape on two trackers
- **WHEN** the same plan is synced to Huly and to another tracker that supports every capability
- **THEN** both responses have the same fields and the same plan keys, parents, and edges

### Requirement: Authentication and errors
The endpoint SHALL require the same authentication as Sortie's other API endpoints. A tracker failure SHALL produce an error response that carries the tracker error category. It SHALL NOT produce a partial graph.

#### Scenario: Tracker unavailable
- **WHEN** the tracker is unreachable
- **THEN** the endpoint answers with an error that carries `tracker_transport_error`
- **AND** returns no nodes
