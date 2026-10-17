## MODIFIED Requirements

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

## ADDED Requirements

### Requirement: Story approval before sync
Approval SHALL be recorded per story by the plan workbench (`planning/story-approval`), never in the breakdown file. Only stories that read as approved SHALL be synced. A breakdown's `status` SHALL NOT approve anything.

#### Scenario: Draft stories are not synced
- **WHEN** a story has no approval, or its content changed since its approval
- **THEN** a sync skips that story and reports it as a draft

#### Scenario: A status in the file
- **WHEN** a breakdown says `status: approved` and the workbench holds no approval for its stories, after the one-time import
- **THEN** its stories read as draft

## REMOVED Requirements

### Requirement: Approval before sync
**Reason**: Approval of a whole breakdown, recorded in the file the planning agent writes, is replaced by per-story approval that the workbench records (`planning/story-approval`).
**Migration**: The workbench imports a breakdown approved under the old format as batch 0 of its epic, the first time it opens the project. `status` and `approved_digest` stay accepted by the schema, and are ignored after that.
