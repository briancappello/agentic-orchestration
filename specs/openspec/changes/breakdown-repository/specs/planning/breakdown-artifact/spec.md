## MODIFIED Requirements

### Requirement: Published schema
The breakdown format SHALL be defined by a versioned JSON Schema file, checked into the spec store. Every breakdown SHALL carry `schema_version`. The schema SHALL define these fields:
- the top-level `status` and `approved_digest`, both optional and deprecated: they are read only to import approvals made before approvals moved to the workbench;
- the top-level `repository`, optional and kebab-case: the repository every deliverable lands in, by the name Sortie's workflow lists it under;
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
- `supersedes`, optional, a ref to the deliverable it replaces;
- `repository`, optional and kebab-case, which overrides the top-level `repository`.

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

#### Scenario: A repository name with a space
- **WHEN** a deliverable has `repository: Not OK`
- **THEN** checking the file against the schema fails
- **AND** the error names the deliverable and `repository`
