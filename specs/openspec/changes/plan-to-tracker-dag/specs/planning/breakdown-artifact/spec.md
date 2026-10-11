## Purpose

Records how one OpenSpec change will be built. It breaks the change into deliverables and records the dependencies among them, in a file that people can review and that tools can read.

## ADDED Requirements

### Requirement: Breakdown file in every planned change
A change that uses the planning schema SHALL have a `breakdown.md` artifact in its change directory. The schema SHALL make `breakdown.md` depend on the proposal, specs, and design, so the breakdown can only be written once those exist. A change without a `breakdown.md` SHALL count as unplanned.

#### Scenario: Status lists the breakdown
- **WHEN** a person runs `openspec status` for a change that uses the planning schema
- **THEN** `breakdown` appears among the change's artifacts
- **AND** it is blocked until the proposal, specs, and design are complete

#### Scenario: A change with no breakdown
- **WHEN** a change has a proposal but no `breakdown.md`
- **THEN** every tool that reads the plan treats the change as unplanned

### Requirement: Deliverable entries
`breakdown.md` SHALL hold one section per deliverable. The section heading SHALL be `### <id>: <title>`. `<id>` SHALL be kebab-case and unique within the change. Under the heading the section SHALL hold these lines:
- `- Kind: story` or `- Kind: enabler`. A story is user-visible behavior. An enabler is technical groundwork that stories need.
- `- Depends on: <ref>, <ref>`, or `- Depends on: none`. A ref is a deliverable id in the same change, or `<change-name>/<id>` for a deliverable in another change.
- `- Covers: <ref>, <ref>`. Each ref names a requirement in the change's specs as `<capability-path>#<requirement name>`.
- An `Acceptance criteria` list with at least one checkbox item.

Free text MAY follow these lines.

#### Scenario: A valid deliverable
- **WHEN** `breakdown.md` holds `### accounts-close: Close an account` with Kind `story`, Depends on `accounts-model`, Covers `accounts/close#Close an account`, and two acceptance criteria
- **THEN** a reader of the plan reports the deliverable `accounts-close` with those values

#### Scenario: A dependency on another change
- **WHEN** a deliverable in change `billing` lists `Depends on: accounts-api/accounts-close`
- **THEN** the plan graph holds an edge from `accounts-api/accounts-close` to that deliverable

### Requirement: Breakdown validation
A breakdown SHALL be valid only when all of these hold:
- every id is unique within the change;
- every `Depends on` ref resolves to a deliverable that exists in this change or in a change in the same store;
- the dependencies within the change, together with every dependency between changes, form no cycle;
- every `Covers` ref names a requirement that exists in the change's specs;
- every deliverable has at least one acceptance criterion.

Validation SHALL report every violation it finds, each with the deliverable id. Validation SHALL NOT stop at the first violation.

#### Scenario: A cycle
- **WHEN** deliverable `a` depends on `b` and `b` depends on `a`
- **THEN** validation fails and names both `a` and `b` as part of a cycle

#### Scenario: A dangling ref
- **WHEN** a deliverable depends on `billing/does-not-exist`
- **THEN** validation fails and names the deliverable and the unresolved ref

#### Scenario: Several problems at once
- **WHEN** a breakdown has a duplicate id and a deliverable with no acceptance criteria
- **THEN** validation reports both problems

### Requirement: Approval before sync
A breakdown SHALL carry an approval state, either `draft` or `approved`, in a front-matter field `status`. Only a person SHALL set it to `approved`. Any change to a deliverable after approval SHALL return the breakdown to `draft` until it is approved again. Sync SHALL read only approved breakdowns.

#### Scenario: Draft breakdowns are not synced
- **WHEN** a breakdown's status is `draft`
- **THEN** a sync skips that change and reports that it is still a draft

#### Scenario: An edit after approval
- **WHEN** an approved breakdown gains a new deliverable
- **THEN** its status becomes `draft`
