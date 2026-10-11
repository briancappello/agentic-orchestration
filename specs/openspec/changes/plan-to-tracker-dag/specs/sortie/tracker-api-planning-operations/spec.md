## Purpose

Gives agents running under Sortie the same planning writes as the sync command, through the `tracker_api` tool. The writes are scoped to the configured project and gated by the adapter's declared capabilities.

## ADDED Requirements

### Requirement: Planning operations in tracker_api
The `tracker_api` tool SHALL accept four new operations, each backed by the matching adapter capability:
- `create_issue`, with title, body, kind, plan key, and an optional parent;
- `update_issue`, with issue id and the fields to change;
- `set_parent`, with issue id and a parent id or null;
- `link_dependency`, with the blocking id, the blocked id, and `add` or `remove`.

Each operation SHALL return the affected issue in the same shape as `fetch_issue`.

#### Scenario: An agent creates a story under an epic
- **WHEN** an agent calls `create_issue` with kind `story`, plan key `billing/tax`, and the `billing` epic as parent
- **THEN** the tracker holds the new story parented to the epic
- **AND** the tool returns it with plan key `billing/tax`

### Requirement: Advertised only when supported
The tool SHALL list a planning operation in its description and accept it only when the configured adapter declares the matching capability. A call to an operation the adapter lacks SHALL return the failure code `unsupported_operation`.

#### Scenario: Adapter without write support
- **WHEN** the configured adapter declares no write capabilities
- **THEN** the tool's description lists no planning operations
- **AND** a call to `create_issue` returns `unsupported_operation`

### Requirement: Project scope
Every planning operation SHALL act only on issues in the configured project, as the tool's existing operations do. An operation naming an issue outside the project SHALL return `project_scope_violation` and SHALL write nothing.

#### Scenario: Linking outside the project
- **WHEN** an agent links an issue in the project to an issue in another project
- **THEN** the tool returns `project_scope_violation`
- **AND** the tracker is unchanged
