## Purpose

Lets a spec store say which outcomes its plan works toward, as milestones that collect changes and stories, and lets planlib report each milestone's progress and critical path, counting work done by hand and by people as well as by agents.

## ADDED Requirements

### Requirement: Milestones file
A spec store MAY hold `openspec/milestones.yaml`, checked against a published schema, `milestones.schema.json`, beside the other planning schemas. It SHALL carry `schema_version` and a list `milestones`. Each milestone SHALL have:

- `id`, kebab-case and unique in the file;
- `title`;
- `depends_on`, a list of milestone ids;
- `includes`, a list whose entries are either `{change: <change-name>}` with an optional `tasks` of `agent`, `metal`, `operator` or `all` (default `all`), or `{story: <change-name>/<id>}`;
- `gate`, optional, a story ref;
- `goal`, optional, a boolean.

Unknown fields SHALL be rejected.

#### Scenario: A milestone that collects a change and a story
- **WHEN** milestone `m1` includes change `billing` and story `accounts/close`
- **THEN** `m1` holds every story of `billing` and the story `accounts/close`

#### Scenario: An unknown field
- **WHEN** a milestone carries `owner: ann`
- **THEN** validation fails with an error naming the milestone and `owner`

### Requirement: Milestones are validated with the plan
planlib SHALL validate `milestones.yaml` with the plan. It SHALL report, each naming the milestone: an included change that `plan.yaml` does not list, an included or gate story that no breakdown holds, a `depends_on` id that no milestone has, a dependency cycle among milestones, and more than one milestone with `goal: true`. A store without the file SHALL validate as before.

#### Scenario: A cycle
- **WHEN** `m1` depends on `m2` and `m2` depends on `m1`
- **THEN** validation fails with an error naming both

#### Scenario: Two goals
- **WHEN** `m2` and `m3` both set `goal: true`
- **THEN** validation fails with an error naming both

#### Scenario: No milestones file
- **WHEN** a store has no `milestones.yaml`
- **THEN** it validates exactly as it did before this capability existed

### Requirement: The goal milestone
The goal SHALL be the milestone with `goal: true`. Without one, it SHALL be the last milestone in dependency order, ties broken by file order. Without a milestones file, the project SHALL be one implicit milestone that includes every planned change, and that milestone SHALL be the goal.

#### Scenario: No goal declared
- **WHEN** milestones `m1`, `m2`, `m3` form a chain and none sets `goal`
- **THEN** `m3` is the goal

### Requirement: Task kinds
planlib SHALL read each change's `tasks.md` checklist items. An item whose line ends with `[metal]` SHALL be a metal task, one ending with `[operator]` an operator task, and any other an agent task. A ticked box SHALL count as done. Metal and operator tasks together SHALL be person tasks.

#### Scenario: Three kinds
- **WHEN** `tasks.md` holds `- [x] 1.1 Add rules.`, `- [ ] 1.2 Apply rules on metal. [metal]` and `- [ ] 1.3 Enroll the key. [operator]`
- **THEN** planlib reports one agent task (done), one metal task and one operator task (both open)

### Requirement: Milestone progress
For each milestone, planlib SHALL report, separately and never summed: its stories done and total, its agent tasks done and total, and its person tasks done and total. A story SHALL count as done when its tracker issue is in the tracker's done state. The tasks counted SHALL be those of each included change whose kind its `tasks` setting selects. A milestone SHALL be done when its gate story is done, or, without a gate, when every story and task it counts is done.

#### Scenario: A change finished by hand
- **WHEN** milestone `m0` includes change `move-plan`, whose five stories were never synced, and whose `tasks.md` items are all ticked
- **THEN** `m0` reports 0 of 5 stories and 12 of 12 agent tasks done, and is not reported as having no progress

#### Scenario: One change in two milestones
- **WHEN** `m1` includes `p3` with `tasks: agent` and `m2` includes `p3` with `tasks: metal`
- **THEN** `p3`'s untagged tasks count in `m1` and its `[metal]` tasks count in `m2`

### Requirement: The next milestone and its critical path
The next milestone SHALL be the first milestone, in dependency order, that is not done. Its critical path SHALL be the longest chain of unfinished stories within it, by dependency, that ends at its gate story, or at any story with no unfinished dependent in the milestone when it has no gate. Each story SHALL count as one, unless it carries an estimate, in which case the estimate SHALL be its length. Ties SHALL break by plan order.

#### Scenario: A chain to the gate
- **WHEN** the next milestone's gate `g` depends on `b`, `b` depends on `a`, and `c` depends on nothing
- **AND** none of them is done
- **THEN** the critical path is `a`, `b`, `g`
