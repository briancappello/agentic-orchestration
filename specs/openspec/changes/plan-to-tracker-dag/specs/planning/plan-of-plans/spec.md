## Purpose

Orders a spec store's changes against each other, which OpenSpec cannot express. It is the epic-level graph that the deliverable breakdowns sit under.

## ADDED Requirements

### Requirement: Plan file in the store
A spec store that uses planning SHALL have one plan file at `openspec/plan.md`. The file SHALL hold one section per planned change, headed `### <change-name>`, followed by a line `- Depends on: <change-name>, <change-name>` or `- Depends on: none`. Each name SHALL be an active change in the store. A change that has a breakdown but no section in the plan SHALL NOT be synced.

#### Scenario: Two changes in order
- **WHEN** `plan.md` lists `accounts-api` with `Depends on: none` and `billing` with `Depends on: accounts-api`
- **THEN** the plan graph holds epics `accounts-api` and `billing`, with `billing` blocked by `accounts-api`

#### Scenario: A change missing from the plan
- **WHEN** change `search-index` has an approved breakdown but no section in `plan.md`
- **THEN** a sync reports `search-index` as unplanned at the epic level and does not create it

### Requirement: Plan validation
The plan SHALL be valid only when every listed change exists, no change is listed twice, and the dependencies between changes form no cycle. A dependency between deliverables in two different changes SHALL be consistent with the plan: when deliverable `x/a` depends on `y/b`, change `x` SHALL depend on change `y` in the plan, directly or through other changes.

#### Scenario: An unknown change
- **WHEN** `plan.md` lists `payments`, which has no change directory
- **THEN** validation fails and names `payments`

#### Scenario: A cross-change dependency the plan does not allow
- **WHEN** deliverable `billing/invoice` depends on `search-index/indexer`
- **AND** the plan has no path from `billing` to `search-index`
- **THEN** validation fails and names both deliverables and both changes

### Requirement: One combined graph
Readers SHALL combine the plan and every breakdown into one graph:
- one epic node per planned change;
- one story node per deliverable;
- a parent edge from each deliverable to its change;
- blocking edges between epics from the plan;
- blocking edges between deliverables from the breakdowns.

Each node SHALL have a plan key: `<change-name>` for an epic, and `<change-name>/<id>` for a deliverable. The plan key SHALL stay the same as long as the name and id stay the same.

#### Scenario: Plan keys
- **WHEN** change `billing` has deliverable `invoice`
- **THEN** the epic's plan key is `billing`
- **AND** the story's plan key is `billing/invoice`
