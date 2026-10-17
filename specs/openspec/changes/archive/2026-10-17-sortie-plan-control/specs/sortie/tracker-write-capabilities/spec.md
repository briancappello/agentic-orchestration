## MODIFIED Requirements

### Requirement: Optional write capabilities
Sortie's tracker contract SHALL define five optional capabilities, separate from the operations every adapter must have:
- **create issue**: create an issue with a title, a markdown body, a kind (`epic` or `story`), and a plan key, and return its id and identifier;
- **update issue**: change an issue's title, body, or kind;
- **set parent**: make one issue the parent of another, or remove the parent;
- **link dependency**: add or remove a "blocks" relation between two issues;
- **approval fields**: set an issue's approver and approval time in fields of their own (`sortie/approval-fields`).

An adapter that does not implement a capability SHALL keep working for every operation it already supports. Adding these capabilities SHALL NOT change the operations every adapter must have.

#### Scenario: An existing adapter without write support
- **WHEN** Sortie runs with an adapter that declares none of the five capabilities
- **THEN** polling, dispatch, transitions, comments, and labels work as before

### Requirement: Declared at registration
Each adapter SHALL declare at registration which of the five capabilities it supports. An adapter SHALL also declare how it records a plan key on an issue. Callers SHALL be able to read these declarations before calling anything. An adapter SHALL NOT declare a capability it does not implement.

#### Scenario: Reading capabilities
- **WHEN** a caller asks for the capabilities of the configured tracker kind
- **THEN** the answer lists exactly the capabilities that adapter declared

#### Scenario: A tracker without dependencies
- **WHEN** an adapter's tracker has no blocking relation, as on GitLab Community Edition
- **THEN** the adapter does not declare **link dependency**
