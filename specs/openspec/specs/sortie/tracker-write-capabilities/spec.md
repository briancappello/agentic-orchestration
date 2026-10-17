# sortie/tracker-write-capabilities Specification

## Purpose
Lets Sortie create and link issues in any tracker that supports it. Each tracker adapter states up front which write abilities it has, so no caller depends on one tracker's model.

## Requirements

### Requirement: Optional write capabilities
Sortie's tracker contract SHALL define four optional capabilities, separate from the operations every adapter must have:
- **create issue**: create an issue with a title, a markdown body, a kind (`epic` or `story`), and a plan key, and return its id and identifier;
- **update issue**: change an issue's title, body, or kind;
- **set parent**: make one issue the parent of another, or remove the parent;
- **link dependency**: add or remove a "blocks" relation between two issues.

An adapter that does not implement a capability SHALL keep working for every operation it already supports. Adding these capabilities SHALL NOT change the operations every adapter must have.

#### Scenario: An existing adapter without write support
- **WHEN** Sortie runs with an adapter that declares none of the four capabilities
- **THEN** polling, dispatch, transitions, comments, and labels work as before

### Requirement: Declared at registration
Each adapter SHALL declare at registration which of the four capabilities it supports. An adapter SHALL also declare how it records a plan key on an issue. Callers SHALL be able to read these declarations before calling anything. An adapter SHALL NOT declare a capability it does not implement.

#### Scenario: Reading capabilities
- **WHEN** a caller asks for the capabilities of the configured tracker kind
- **THEN** the answer lists exactly the capabilities that adapter declared

#### Scenario: A tracker without dependencies
- **WHEN** an adapter's tracker has no blocking relation, as on GitLab Community Edition
- **THEN** the adapter does not declare **link dependency**

### Requirement: Plan keys are readable
An adapter that declares **create issue** SHALL store the plan key on each issue it creates. A later read of that issue SHALL return the plan key. An adapter SHALL find an issue by its plan key within the configured project. A plan key SHALL survive edits that people make to the issue's title, status, and labels.

#### Scenario: Find by plan key
- **WHEN** an issue was created with plan key `billing/invoice`
- **AND** a person later renames the issue
- **THEN** a lookup by plan key `billing/invoice` returns that issue

### Requirement: Kinds map to the tracker's own model
Each adapter SHALL map `epic` and `story` to its tracker's own concepts, and SHALL document that mapping in its adapter notes. On Huly, `epic` and `story` SHALL be project task types, and a story's parent SHALL be its epic's issue.

#### Scenario: Huly epic and story
- **WHEN** the Huly adapter creates an epic and then a story parented to it
- **THEN** Huly shows the story as a sub-issue of the epic with task type Story

### Requirement: Write errors
Each write SHALL return the existing tracker error categories: transport, auth, API, not found, and payload. A call to a capability the adapter did not declare SHALL return a distinct `tracker_unsupported_operation` error and SHALL send no request. Adding a dependency that already exists, or setting a parent that is already set, SHALL succeed and change nothing.

#### Scenario: Undeclared capability
- **WHEN** a caller asks an adapter without **link dependency** to link two issues
- **THEN** the call returns `tracker_unsupported_operation`
- **AND** no request reaches the tracker

#### Scenario: Linking twice
- **WHEN** issue A already blocks issue B
- **AND** a caller links A as blocking B again
- **THEN** the call succeeds and the tracker holds one relation
