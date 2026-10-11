## Why

A plan starts in an agent session that writes an OpenSpec change: *what* we want to build. Nothing turns that into *how* we build it, meaning deliverables ordered in sequence or in parallel. Nothing turns those deliverables into tracker tickets that Sortie can dispatch. Today a person creates the epics, stories, and dependencies by hand in the tracker. A graph of work is slow to enter that way and easy to get wrong.

Sortie already starts only unblocked tickets, so a correct dependency graph in the tracker is all that sequencing needs. Sortie cannot write that graph. Its tracker contract can change status, comment, and add or remove labels. It cannot create an issue, set a parent, or add a dependency, in any tracker. Whatever we build must not tie us to Huly. It must work with every tracker Sortie supports now or adds later.

## What Changes

- Add a **breakdown** artifact to OpenSpec changes. It records the change's deliverables, each with an id, a title, acceptance criteria, the spec sections it covers, and `depends_on`. `depends_on` may name deliverables in other changes. An agent drafts it from the change's proposal, specs, and design, and a person reviews it before anything reaches a tracker. We add it through a custom schema forked from `spec-driven`, not by changing OpenSpec.
- Add a **plan of plans** file to the spec store. It lists the store's changes and the dependencies between them. OpenSpec has no dependencies between changes: upstream PR #1923 proposed them and was closed without merging. This file is the epic-level graph.
- Add **tracker write capabilities** to Sortie's tracker contract as optional interfaces, alongside `BlockerReader`:
  - create an issue with a title, a body, and a kind (epic or story);
  - update those fields;
  - set an issue's parent;
  - add and remove a blocking dependency.

  Each adapter declares which capabilities it has at registration. An adapter that cannot store dependencies says so, and a sync to it fails before it writes anything. The core `TrackerAdapter` interface does not change.
- Add **`sortie plan sync`**, a subcommand that reads a plan of plans and its approved breakdowns, and creates or updates the matching tracker issues and links through the configured adapter:
  - one epic per change and one story per deliverable;
  - each story parented to its epic;
  - dependencies between stories and between epics.

  It is idempotent: each issue carries a stable key to the deliverable it came from, so a second run updates and never duplicates. It is a subcommand, not orchestrator behavior, so the orchestrator still writes tracker state only at its three documented points.
- Add matching operations to the agent's **`tracker_api`** tool (create issue, set parent, link dependency), gated by the same capabilities, so a planning agent can do the same work through Sortie.
- Implement the capabilities first in the **Huly adapter** (Sortie branch `prototype/huly-tracker`). Huly epics and stories are task types, a story is a sub-issue of its epic, and dependencies go in `blockedBy`.

## Capabilities

### New Capabilities
- `planning/breakdown-artifact`: the breakdown format, its rules (unique ids, no cycles, dependencies that resolve), and how it relates to the change it belongs to.
- `planning/plan-of-plans`: the store-level file that orders changes, and how it combines with breakdowns into one graph.
- `sortie/tracker-write-capabilities`: the optional adapter interfaces for creating issues, parenting, and dependencies, how an adapter declares them, and the errors each returns.
- `sortie/plan-sync`: the `sortie plan sync` command, including how a deliverable maps to an issue, idempotency, a dry run, and refusal when the tracker lacks a needed capability.
- `sortie/tracker-api-planning-operations`: the new `tracker_api` operations and their project scoping.

### Modified Capabilities

None.

## Impact

- Spec store: a custom OpenSpec schema with the breakdown artifact, and a plan-of-plans file. Changes already in flight (`acp-broker`, `sortie-session-control`, `agent-telemetry`) can adopt it as their first users.
- Sortie fork:
  - new optional interfaces in `internal/domain`;
  - capability metadata in `internal/registry`;
  - a new `plan` subcommand in `cmd/sortie`;
  - new operations in `internal/tool/trackerapi`;
  - write support in the Huly adapter.

  Every addition is additive, so upstream rebases stay small. Other adapters keep working and declare no write capabilities until someone implements them.
- Docs in the fork:
  - the tracker-contract section;
  - the workflow reference for the new subcommand;
  - the Huly adapter notes.
- Downstream: the DAG viewer prototype (`~/dev/huly-dag-prototype`) reads the graph this change creates. It reads the tracker, so it inherits the same independence from any one tracker.
- Out of scope:
  - the viewer itself;
  - write capabilities for adapters other than Huly;
  - syncing state back from the tracker into the breakdown;
  - deciding who runs the breakdown step (an agent stage in Sortie or an interactive session). Design weighs that last choice.
