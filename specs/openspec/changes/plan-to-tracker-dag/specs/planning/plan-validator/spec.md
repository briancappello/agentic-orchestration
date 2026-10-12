## Purpose

Checks the plan where it is written, as part of planning itself. The planning agent and the workbench run the same validator. It turns the store's files into one checked graph, which is the only form of the plan that leaves the store.

## ADDED Requirements

### Requirement: One validator, run by the agent and the workbench
A validator SHALL check a spec store's `plan.yaml` and every `breakdown.yaml`. It SHALL be available as a command-line tool that the planning agent runs inside its session, and as a library the workbench backend calls. Both SHALL return identical results for the same files.

#### Scenario: The agent checks its own work
- **WHEN** the planning agent writes a breakdown and runs the validator
- **THEN** the agent sees every error in the same session, before the person reviews the change

### Requirement: Checks beyond the schema
The validator SHALL first check each file against its JSON Schema. It SHALL then check the combined graph:
- every id is unique within its change;
- every `depends_on` ref resolves to a deliverable in the store;
- every change in the plan exists;
- the epic graph and the deliverable graph each contain no cycle;
- every `covers` ref names a requirement that exists in the change's specs, as OpenSpec reports them;
- a dependency between deliverables in two changes agrees with the plan. When `x/a` depends on `y/b`, change `x` depends on change `y` in the plan, directly or through other changes.

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

### Requirement: The validated graph is the exchange format
When validation passes, the validator SHALL output the combined graph as JSON in a versioned graph format. The graph SHALL hold the schema version, a digest of the source files, and each node's plan key, kind, title, body, and approval state. It SHALL also hold the parent edges and the blocking edges. The JSON Schema for this graph format SHALL be published with the validator. When validation fails, the validator SHALL output no graph.

#### Scenario: Valid store
- **WHEN** the store's files pass validation
- **THEN** the validator outputs a graph document that matches the graph schema
