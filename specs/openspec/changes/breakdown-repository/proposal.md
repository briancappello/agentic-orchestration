## Why

One Sortie now runs stories in several repositories (the Ortus Nova spec
store's `agent-platform-workers`, story `story-repository`). The plan has to
say which repository each story lands in, and an approval has to cover that
choice.

## What Changes

- A breakdown may name a `repository` for all its deliverables, and a
  deliverable may name its own, which overrides it. A name is kebab-case:
  the name Sortie's workflow lists the repository under.
- The plan graph does not carry it yet. Its schema is the contract with
  Sortie, which publishes its own copy; Sortie's `story-repository` adds the
  node field, and planlib emits it after that.
- A story's approval digest covers its resolved repository, so changing the
  breakdown's default returns its stories to draft.

## Capabilities

### Modified Capabilities

- `planning/breakdown-artifact`: "Published schema" gains `repository`.

## Impact

- `workbench/src/planlib` (approval, frozen check), the breakdown schema the
  workbench ships, and its test fixture.
- Sortie reads the field in the spec store's `agent-platform/story-repository`.
