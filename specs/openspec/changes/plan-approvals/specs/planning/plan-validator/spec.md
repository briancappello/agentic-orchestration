## MODIFIED Requirements

### Requirement: Checks beyond the schema
The validator SHALL first check each file against its JSON Schema. It SHALL then check the combined graph:
- every id is unique within its change;
- every `depends_on` ref resolves to a deliverable in the store;
- every `supersedes` ref resolves to a deliverable in the store, other than the deliverable itself, and no deliverable is superseded twice;
- every change in the plan exists;
- the epic graph and the deliverable graph each contain no cycle;
- every `covers` ref names a requirement that exists in the change's specs, as OpenSpec reports them;
- a dependency between deliverables in two changes agrees with the plan. When `x/a` depends on `y/b`, change `x` depends on change `y` in the plan, directly or through other changes;
- when the caller passes a set of frozen stories with their approved digests, no frozen story is removed and none has a different digest.

It SHALL report every problem it finds, each with the file, the change, and the deliverable. It SHALL NOT stop at the first problem.

#### Scenario: A cycle
- **WHEN** deliverable `a` depends on `b`, and `b` depends on `a`
- **THEN** validation fails and names both `a` and `b` as one cycle

#### Scenario: A cross-change dependency the plan does not allow
- **WHEN** `billing/invoice` depends on `search-index/indexer`
- **AND** the plan has no path from `billing` to `search-index`
- **THEN** validation fails and names both deliverables and both changes

#### Scenario: Several problems at once
- **WHEN** a breakdown has a duplicate id and a dangling ref
- **THEN** validation reports both problems

#### Scenario: A frozen story removed
- **WHEN** frozen story `billing/a3` is no longer in its breakdown
- **THEN** validation fails with `frozen`, naming `billing/a3`

### Requirement: The validated graph is the exchange format
When validation passes, the validator SHALL output the combined graph as JSON in a versioned graph format. The graph SHALL hold the schema version, a digest of the source files, and each node's plan key, kind, title, body, and approval state. Approval SHALL come from the approvals the caller passes, as plan key and digest; without them every story reads as draft. Each story SHALL also carry its review gate. It SHALL also hold the parent edges and the blocking edges, with the dependents of a superseded story pointing at its replacement. The JSON Schema for this graph format SHALL be published with the validator. When validation fails, the validator SHALL output no graph.

#### Scenario: Valid store
- **WHEN** the store's files pass validation
- **THEN** the validator outputs a graph document that matches the graph schema

#### Scenario: Run by the planning agent
- **WHEN** the planning agent runs `planlib validate` with no approvals
- **THEN** every story reads as draft, and validation still checks every file
