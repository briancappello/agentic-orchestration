## Purpose

Lets each story name how its work is reviewed before it merges, so that Sortie can enforce it.

## ADDED Requirements

### Requirement: Each deliverable names its review gate
A deliverable MAY carry `review`, `human` or `criteria`. A deliverable without it SHALL read as `human`. The planning agent proposes the gate, and approving the story accepts it, because the gate is part of the story's digest. The graph a sync sends SHALL carry each story's gate, and Sortie enforces it (`sortie/review-gate`).

#### Scenario: Default gate
- **WHEN** a deliverable has no `review`
- **THEN** its graph node carries `review: human`

#### Scenario: Changing the gate needs a new approval
- **WHEN** the agent changes an approved story's `review` from `human` to `criteria`
- **THEN** the story reads as draft
