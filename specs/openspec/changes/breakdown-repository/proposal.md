## Why

One Sortie now runs stories in several repositories (the Ortus Nova spec
store's `agent-platform-workers`, story `story-repository`). The plan has to
say which repository each story lands in, and an approval has to cover that
choice.

## What Changes

- A breakdown may name a `repository` for all its deliverables, and a
  deliverable may name its own, which overrides it. A name is kebab-case:
  the name Sortie's workflow lists the repository under.
- planlib puts the resolved name on each story's node in the plan graph, and
  leaves it off when the breakdown names none, so a Sortie that does not read
  it keeps working until a plan uses it.
- A story's approval digest covers its resolved repository, so changing the
  breakdown's default returns its stories to draft.

## Capabilities

### Modified Capabilities

- `planning/breakdown-artifact`: "Published schema" gains `repository`.

## Impact

- `workbench/src/planlib` (graph, approval, frozen check), the breakdown and
  plan-graph schemas the workbench ships, and their test fixtures.
- Sortie reads the field in the spec store's `agent-platform/story-repository`.
