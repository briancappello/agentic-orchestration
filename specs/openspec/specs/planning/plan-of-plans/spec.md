# planning/plan-of-plans Specification

## Purpose
Orders a spec store's changes against each other, which OpenSpec cannot express. It is the epic-level graph that the deliverable breakdowns sit under.

## Requirements

### Requirement: Plan file in the store
A spec store that uses planning SHALL have one plan file, `openspec/plan.yaml`. A versioned JSON Schema in the store SHALL define its format. The file SHALL hold `schema_version` and a list `changes`. Each entry SHALL have a `name`, which is an active change in the store, and a `depends_on` list of change names. A change that has a breakdown but is not listed in the plan SHALL NOT be synced.

#### Scenario: Two changes in order
- **WHEN** `plan.yaml` lists `accounts-api` with no dependencies and `billing` depending on `accounts-api`
- **THEN** the plan graph holds epics `accounts-api` and `billing`, with `billing` blocked by `accounts-api`

#### Scenario: A change missing from the plan
- **WHEN** change `search-index` has an approved breakdown but is not listed in `plan.yaml`
- **THEN** the plan reports `search-index` as unplanned at the epic level, and a sync does not create it

### Requirement: One combined graph
The plan and every breakdown SHALL combine into one graph:
- one epic node for each planned change;
- one story node for each deliverable;
- a parent edge from each deliverable to its change;
- blocking edges between epics, from the plan;
- blocking edges between deliverables, from the breakdowns.

Each node SHALL have a plan key: `<change-name>` for an epic and `<change-name>/<id>` for a deliverable. The plan key SHALL stay the same as long as the name and the id do.

#### Scenario: Plan keys
- **WHEN** change `billing` has deliverable `invoice`
- **THEN** the epic's plan key is `billing`
- **AND** the story's plan key is `billing/invoice`
