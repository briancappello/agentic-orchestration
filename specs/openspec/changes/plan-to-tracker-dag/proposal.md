## Why

A plan starts in an agent session that writes an OpenSpec change: *what* we want to build. Nothing turns that into *how* we build it, meaning deliverables ordered in sequence or in parallel. Nothing turns those deliverables into tracker tickets that Sortie can dispatch. Today a person creates the epics, stories, and dependencies by hand in the tracker. A graph of work is slow to enter that way and easy to get wrong.

Planning is also a conversation, and today it happens blind: the agent writes files, and nobody can see the graph that is taking shape until it is finished. We want to plan in the same place we look at the plan. Chatting with the planning agent should redraw the graph as the agent writes it, and the same view should later show the live state of that graph while agents carry it out.

Sortie already starts only unblocked tickets, so a correct dependency graph in the tracker is all that sequencing needs. Sortie cannot write that graph. Its tracker contract can change status, comment, and add or remove labels. It cannot create an issue, set a parent, or add a dependency, in any tracker. Whatever we build must not tie us to Huly. It must work with every tracker Sortie supports now or adds later.

## What Changes

- Add a **breakdown** artifact to OpenSpec changes. It records the change's deliverables, each with an id, a title, acceptance criteria, the spec sections it covers, and `depends_on`. `depends_on` may name deliverables in other changes. An agent drafts it from the change's proposal, specs, and design, and a person reviews it before anything reaches a tracker. We add it through a custom schema forked from `spec-driven`, not by changing OpenSpec.
- Add a **plan of plans** file to the spec store. It lists the store's changes and the dependencies between them. OpenSpec has no dependencies between changes: upstream PR #1923 proposed them and was closed without merging. This file is the epic-level graph.
- Add a **plan workbench**: a standalone web app, outside both Sortie and the tracker, with two panes. It has a FastAPI backend and a Vite-built frontend. The UI library is open.
  - **Graph pane (60% of the width).** It draws the plan as a left-to-right DAG: epics at the project level, and one epic's stories after a drill-down. Border colour shows status, a hatch shows a deliverable without a spec, and badges show live agent activity from Sortie. The prototype in `~/dev/huly-dag-prototype` is the starting point.
  - **Chat pane (40% of the width).** It holds an interactive planning session with an agent. In that session you write the OpenSpec change, its breakdown, and the plan of plans.
  - **Two sources for one graph.** Before a sync, the graph pane draws the draft plan from the files in the spec store, and it redraws whenever the agent changes them. After a sync, it draws the tracker's issues and Sortie's live state. A deliverable keeps its identity across that boundary, so drafted, synced, and in-flight work all appear in one picture.
  - **The agent can see what you point at.** Selecting a node in the graph adds it to the chat's context, so you can say "split this one" or "this should wait for Billing".
  - **It runs `sortie plan sync` from the workbench, with a preview first.** A person approves the preview before anything is written to the tracker.
- Run the planning session through **`acp-broker`** (change `acp-broker`). The broker's authenticated HTTP transport (Server-Sent Events plus `POST`) carries the chat. The session works in the spec store as its workspace, and any ACP agent can run it. The workbench adds no agent integration of its own.
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
- `sortie/plan-sync`: syncing a plan into the tracker, as both the `sortie plan sync` command and an HTTP endpoint. Covers how a deliverable maps to an issue, idempotency, a preview, and refusal when the tracker lacks a needed capability.
- `sortie/plan-graph-api`: the HTTP endpoint that returns the synced plan graph from the tracker in a form that does not depend on the tracker.
- `sortie/tracker-api-planning-operations`: the new `tracker_api` operations and their project scoping.
- `planning/plan-workbench`: the two-pane web app, covering the layout, the graph rules (columns by dependency depth, status, planned and unplanned, drill-down), how the draft and tracker sources merge, live Sortie state, selection as chat context, and sync with a preview.
- `planning/planning-session`: the interactive planning session in the chat pane, covering how it starts, its workspace (the spec store), the artifacts it may write, and how its file changes reach the graph pane.

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
- Workbench: a new standalone app in its own repository, grown from `~/dev/huly-dag-prototype`. A FastAPI backend serves the Vite-built frontend and is the frontend's only server.
  - The backend reads the spec store and watches it for changes.
  - It reads Sortie's `/api/v1/state`, and reads the synced plan from the tracker through Sortie.
  - It runs the sync through Sortie.
  - It relays the planning session to and from `acp-broker`.
  - It never calls a tracker directly, so it works with any tracker Sortie supports.
- Sortie fork, HTTP API:
  - new endpoints that read the synced plan graph (issues, parents, dependencies, plan keys) through the configured adapter;
  - new endpoints that preview a sync and then apply it.

  The workbench may run on another machine than Sortie, so it uses these endpoints, not the subcommand.
- Depends on change `acp-broker`, for the HTTP viewer transport and the session registry.
- Out of scope:
  - write capabilities for adapters other than Huly;
  - syncing state back from the tracker into the breakdown;
  - editing the graph by drag and drop; in this change the graph changes only through the planning session.
