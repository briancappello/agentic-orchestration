## MODIFIED Requirements

### Requirement: Sync from a validated plan graph
Sortie SHALL provide `sortie plan sync --graph <file>` and `POST /api/v1/plan/sync`. Both SHALL take a plan graph document in the format the plan validator outputs. Sortie SHALL NOT read or parse the spec store's files. Using only the graph's approved nodes, Sortie SHALL make the configured tracker match it:
- every epic has an issue;
- every story has an issue;
- every story issue is parented to its epic issue;
- every blocking edge in the graph is a relation in the tracker.

Sortie SHALL decide approval node by node. An approved story SHALL be synced even when other stories of its epic are drafts. A draft story SHALL be skipped, and the preview SHALL list it as skipped. An epic SHALL be synced when it is approved, or when any of its stories is approved. A blocking edge SHALL be synced only when both of its nodes are synced.

The command and the endpoint SHALL behave identically.

#### Scenario: A first sync
- **WHEN** the graph holds `accounts-api` with 3 approved deliverables and `billing` with 2
- **AND** the tracker holds none of them
- **THEN** after the sync the tracker holds 2 epics and 5 stories, with the graph's parents and blocking relations

#### Scenario: New drafts beside approved stories
- **WHEN** epic `billing` holds 4 approved stories and 2 draft stories
- **THEN** the sync writes the 4 approved stories
- **AND** the preview lists the 2 drafts as skipped

### Requirement: What a sync never does
A sync SHALL NOT change an issue's assignee. A sync SHALL change an issue's status only to release a story (`sortie/plan-release`). A sync SHALL change an issue's labels only to keep its one review label (`sortie/review-gate`). A sync SHALL NOT delete an issue. When a deliverable leaves the graph, the sync SHALL report its issue as orphaned and SHALL remove the blocking relations that the graph no longer holds. It SHALL NOT remove relations that people added that do not involve plan-keyed issues.

#### Scenario: A deliverable removed from the plan
- **WHEN** a deliverable that was synced is no longer in the graph
- **THEN** the next preview lists its issue as orphaned
- **AND** the issue still exists in the tracker after the apply

#### Scenario: Other labels are kept
- **WHEN** a person added the label `customer-visible` to a synced story
- **THEN** the next sync keeps that label

#### Scenario: No release, no status change
- **WHEN** a synced story's node carries `release: false`
- **THEN** the sync leaves the issue's status as it is
