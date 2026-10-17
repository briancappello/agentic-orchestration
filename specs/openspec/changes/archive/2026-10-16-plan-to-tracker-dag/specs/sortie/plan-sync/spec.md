## Purpose

Makes the tracker match the approved plan. It creates, updates, parents, and links issues through the configured adapter, so the tracker's dependency graph is the one Sortie dispatches from.

## ADDED Requirements

### Requirement: Sync from a validated plan graph
Sortie SHALL provide `sortie plan sync --graph <file>` and `POST /api/v1/plan/sync`. Both SHALL take a plan graph document in the format the plan validator outputs. Sortie SHALL NOT read or parse the spec store's files. Using only the graph's approved nodes, Sortie SHALL make the configured tracker match it:
- every epic has an issue;
- every story has an issue;
- every story issue is parented to its epic issue;
- every blocking edge in the graph is a relation in the tracker.

The command and the endpoint SHALL behave identically.

#### Scenario: A first sync
- **WHEN** the graph holds `accounts-api` with 3 approved deliverables and `billing` with 2
- **AND** the tracker holds none of them
- **THEN** after the sync the tracker holds 2 epics and 5 stories, with the graph's parents and blocking relations

### Requirement: Reject a malformed graph
Sortie SHALL reject a graph document before it contacts the tracker in any of these cases:
- the document's schema version is not one Sortie supports;
- the document does not match the graph schema;
- an edge names a node that is not in the document.

The rejection SHALL name the problem. Sortie SHALL NOT repeat the planning checks that the validator owns.

#### Scenario: An unsupported version
- **WHEN** a client posts a graph whose schema version Sortie does not support
- **THEN** Sortie answers with a payload error that names both versions
- **AND** no tracker request is made

### Requirement: Preview before apply
A sync SHALL first compute a preview: the issues to create, the issues to update, and the parents and relations to add or remove. A sync SHALL change the tracker only when it is applied. The preview SHALL be returned by `sortie plan sync --dry-run` and by `POST /api/v1/plan/sync` with `"apply": false`. An apply SHALL carry the id of the preview it applies. Sortie SHALL refuse an apply when the graph's source digest or the tracker has changed since that preview was computed.

#### Scenario: A preview writes nothing
- **WHEN** a caller requests a preview
- **THEN** the response lists the planned writes
- **AND** the tracker is unchanged

#### Scenario: A stale preview
- **WHEN** a caller applies a preview
- **AND** sends a graph whose source digest differs from the previewed one
- **THEN** Sortie refuses with a conflict error and writes nothing

### Requirement: Idempotent by plan key
A sync SHALL find existing issues by plan key. It SHALL update an issue it finds and SHALL NOT create a second issue for the same plan key. Running the same sync twice SHALL make no writes the second time.

#### Scenario: A second run
- **WHEN** a sync is applied and then applied again with no changes to the graph
- **THEN** the second preview lists no writes

#### Scenario: A changed title
- **WHEN** a deliverable's title changes in the graph
- **THEN** the next sync updates the existing issue's title and creates no issue

### Requirement: What a sync never does
A sync SHALL NOT change an issue's status, assignee, or labels. A sync SHALL NOT delete an issue. When a deliverable leaves the graph, the sync SHALL report its issue as orphaned and SHALL remove the blocking relations that the graph no longer holds. It SHALL NOT remove relations that people added that do not involve plan-keyed issues.

#### Scenario: A deliverable removed from the plan
- **WHEN** a deliverable that was synced is no longer in the graph
- **THEN** the next preview lists its issue as orphaned
- **AND** the issue still exists in the tracker after the apply

### Requirement: Refuse what the tracker cannot hold
Before it writes anything, a sync SHALL check the adapter's declared capabilities against what the preview needs. When the plan holds blocking relations and the adapter lacks **link dependency**, or the preview needs any other undeclared capability, the sync SHALL fail before its first write. The failure SHALL name the missing capabilities.

#### Scenario: A tracker without dependencies
- **WHEN** the configured adapter does not declare **link dependency**
- **AND** the plan holds blocking relations
- **THEN** the sync fails with `tracker_unsupported_operation` and makes no writes

### Requirement: Partial failure is reported and resumable
When a write fails partway through an apply, the sync SHALL stop. It SHALL report which writes succeeded and which failed. A later sync SHALL complete the remaining work through plan keys, without duplicating anything.

#### Scenario: A transport error midway
- **WHEN** the tracker fails on the fourth of seven creates
- **THEN** the apply reports three created and one failed
- **AND** the next sync creates only the remaining issues

### Requirement: Sync runs outside the orchestrator
Running a sync SHALL NOT change orchestrator state, dispatch, or the orchestrator's three tracker write points. The sync endpoint SHALL require the same authentication as Sortie's other control endpoints.

#### Scenario: Sync while agents run
- **WHEN** a sync is applied while workers are running
- **THEN** the running workers are unaffected
- **AND** new stories become candidates on the next poll only when they are in an active state and unblocked
