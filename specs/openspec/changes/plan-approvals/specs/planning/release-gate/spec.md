## Purpose

Decides which approved stories go to the agents: a story is released once it and every story it directly depends on are approved, and Sortie's own blocker check orders the rest.

## ADDED Requirements

### Requirement: Held and ready
An approved story SHALL be `ready` when every story it directly depends on is approved, in its own epic or another, and `held` otherwise. A held story SHALL name the blockers that are not approved. The graph a sync sends SHALL carry `release: true` for every ready story and `release: false` for every other story.

#### Scenario: A blocker in an epic that is not approved
- **WHEN** `billing/b1` is approved and depends on `accounts/a3`, a draft
- **THEN** `billing/b1` is held, naming `accounts/a3`
- **AND** a sync does not release it

#### Scenario: Only direct blockers count
- **WHEN** `c` depends on `b`, `b` depends on `a`, and all three are approved
- **AND** `a` is not merged yet
- **THEN** `c` is ready, and Sortie holds it on `b` until `b` merges

### Requirement: Release is one-way
A released story SHALL stay released while it sits in the tracker. Only a pull-back SHALL undo a release. A release SHALL happen through a sync, never by itself.

#### Scenario: Approval withdrawn after release
- **WHEN** a released story's approval is withdrawn because a blocker was cancelled
- **AND** the story has not started
- **THEN** the workbench pulls it back before anything else changes

### Requirement: An edit to a released story pulls it back
When the content of a released story that has not started changes, the workbench SHALL pull it back through Sortie before the next sync. When the pull-back fails because a worker claimed the story first, the story SHALL be frozen (`planning/story-lifecycle`) and the edit SHALL be refused as an edit to a frozen story.

#### Scenario: An edit before dispatch
- **WHEN** story `billing/tax` is in `Todo`, not yet dispatched
- **AND** the agent edits it
- **THEN** the workbench pulls it back to the backlog state
- **AND** the story reads as draft until an approver approves it again
