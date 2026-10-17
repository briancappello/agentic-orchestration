# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Stack

A FastAPI backend that serves a Vite build of a Svelte 5 and TypeScript frontend. The backend is the browser's only server. It reads the OpenSpec spec store, validates it with `planlib`, reads the synced plan and live agent state through Sortie, and relays the planning session from `acp-broker`. It never calls a tracker directly. The design prototype in `~/dev/huly-dag-prototype` was the starting point.

## Users

The primary user is a technical lead who plans software work as a dependency graph of tickets in Huly, and who has AI coding agents (dispatched by Sortie) carry out the unblocked tickets. They use this view to decide what to plan next, to see what is ready, and to watch the graph get done.

## Product Purpose

A standalone plan workbench with two panes. The graph pane (60% of the width) shows the plan as a dependency graph (DAG) instead of a backlog or kanban board. The chat pane (40%) holds a planning session with an agent that writes the OpenSpec change, its breakdown, and the plan of plans; the graph redraws as it writes. One graph combines three sources:

- **The spec store is the draft.** `planlib` validates its `plan.yaml` and every `breakdown.yaml` into one graph.
- **The tracker is the database**, read through Sortie's `/api/v1/plan/graph`: the synced issues, their states, parents, and dependencies.
- **Sortie is the live state:** which deliverables agents are running, retrying, or holding for budget right now.

Nodes match by plan key, so a deliverable keeps its identity from draft to synced to in flight. A sync writes the approved plan into the tracker only after a person confirms a preview.

Success: the user can see at a glance which work is unblocked, what is in flight, what is planned, and how far each epic is from done.

## Positioning

Planning and execution are shown in one graph. The tracker supplies the structure and the orchestrator supplies the live agent activity. The app forks neither Huly nor Sortie.

## Operating Context

- Hierarchy: Workspace > Project > Epic > Story. Epic and Story are Huly task types, and a story is a sub-issue of its epic. A project can span several interrelated apps or repos.
- Dependencies exist between epics and between stories, including stories in different epics. Sortie relies on the story-level dependencies to sequence work when epics run in parallel.
- A ticket is **planned** when it has an OpenSpec change. OpenSpec changes live in git, probably in a separate spec repo (an OpenSpec "store"), because work can span repos.
- Sortie starts a ticket only when every blocker is done, so the unblocked edge of the graph is exactly what agents can pick up.

## Capabilities and Constraints

Confirmed:
- The graph flows left to right. A ticket with no unfinished dependencies sits at the left. The further right a ticket sits, the more dependencies stand before it. The rightmost point means the epic or project is fully implemented. The view scrolls horizontally.
- The border color of a ticket shows its status: done, in progress, or todo.
- Planned and unplanned tickets must be distinguishable.
- Two levels of detail: a project view with the DAG of epics, and a drill-down into one epic that shows the DAG of its stories.
- No fork of Huly or Sortie. The app reads Huly's REST API and Sortie's state API.
- The human view may hide data that the machine data keeps. For example, cross-epic story dependencies exist in the data, and whether or how the view shows them is a design question.

Open (deliberately undecided):
- Which visual rules hide or show which edges at each level. This is being explored in the live designer.
- Whether the Huly ticket links to its OpenSpec change or the reverse.
- Whether the view is read-only or can edit dependencies and statuses.
- Which Huly dependency model is the source of truth: the `blockedBy` list or the typed `IssueRelation`.
- The home of the OpenSpec repo: the same repo as the project code, or a separate one.

## Evidence on Hand

- Project spec stores that the workbench creates from `src/workbench/store_template/`. `~/dev/agent-platform-specs` holds the platform's own design as stock OpenSpec changes, and it is not a workbench plan.
- A working local Huly (v0.7.426), and Sortie's Huly adapter with plan writes on the Sortie branch `plan-bench`.

## Product Principles

1. The graph is the plan. What the user sees at the epic level must agree with what the agents obey at the story level.
2. Readiness first. "What can start now" must be the easiest thing to find.
3. Two sources, one picture. Never make the user reconcile Huly and Sortie in their head.
4. Hide detail, never facts. A view may collapse detail, but it must not show a state that the data contradicts.
