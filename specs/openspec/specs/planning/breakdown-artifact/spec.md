# planning/breakdown-artifact Specification

## Purpose
Records how one OpenSpec change will be built, as a typed, versioned data file. The file lists the change's deliverables and the dependencies among them. People can review it and every tool can check it against the same published schema.

## Requirements

### Requirement: Breakdown file in every planned change
A change that uses the planning schema SHALL have a `breakdown.yaml` artifact in its change directory. The schema SHALL make `breakdown.yaml` depend on the specs and design, so it can be written only once both exist. A change without a `breakdown.yaml` SHALL count as unplanned.

#### Scenario: Status lists the breakdown
- **WHEN** a person runs `openspec status` for a change that uses the planning schema
- **THEN** `breakdown` appears among the change's artifacts
- **AND** it is blocked until the specs and design are complete

#### Scenario: A change with no breakdown
- **WHEN** a change has a proposal but no `breakdown.yaml`
- **THEN** every tool that reads the plan treats the change as unplanned

### Requirement: Published schema
The breakdown format SHALL be defined by a versioned JSON Schema file, checked into the spec store. Every breakdown SHALL carry `schema_version`. The schema SHALL define these fields:
- the top-level `status` and `approved_digest`, both optional and deprecated: they are read only to import approvals made before approvals moved to the workbench;
- a list `deliverables`.

Each deliverable SHALL have these fields:
- `id`, kebab-case;
- `title`;
- `kind`, either `story` or `enabler`;
- `depends_on`, a list of refs. A ref is a deliverable id in the same change, or `<change-name>/<id>` for a deliverable in another change;
- `covers`, a list of requirement refs in the form `<capability-path>#<requirement name>`;
- `acceptance_criteria`, a list of at least one string;
- `notes`, an optional string;
- `review`, optional, `human` or `criteria`;
- `supersedes`, optional, a ref to the deliverable it replaces.

Unknown fields SHALL be rejected.

#### Scenario: A file that breaks the schema
- **WHEN** a deliverable has `kind: task`
- **THEN** checking the file against the schema fails
- **AND** the error names the deliverable and the field

#### Scenario: An unsupported version
- **WHEN** a breakdown's `schema_version` is newer than the version a tool supports
- **THEN** the tool refuses to read the file and names both versions

#### Scenario: A breakdown without status
- **WHEN** a breakdown has no `status`
- **THEN** it passes the schema

### Requirement: Story approval before sync
Approval SHALL be recorded per story by the plan workbench (`planning/story-approval`), never in the breakdown file. Only stories that read as approved SHALL be synced. A breakdown's `status` SHALL NOT approve anything.

#### Scenario: Draft stories are not synced
- **WHEN** a story has no approval, or its content changed since its approval
- **THEN** a sync skips that story and reports it as a draft

#### Scenario: A status in the file
- **WHEN** a breakdown says `status: approved` and the workbench holds no approval for its stories, after the one-time import
- **THEN** its stories read as draft
