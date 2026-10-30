## Why

A project's page opens on the dependency graph. The graph is the right place
to plan, but it is the wrong place to ask "how are we doing?", and today it
answers that question wrongly:

- Progress counts only stories Sortie saw merge. A change finished by hand
  reads `0/5 done`; a change whose remaining work is hardware tasks in its
  `tasks.md` reads "no stories".
- "Ready to start" means "no unfinished blocker in the graph", so it lists
  finished changes and changes whose remaining work only a person can do.
- There is no milestone, no goal, and no critical path, so nobody can see how
  far the project is from the outcome it exists for.
- Nothing says whether the agents will stay busy. Free agent slots next to an
  empty queue of approved work is the most expensive state a project can be
  in, and the page does not show it.
- Work that is not ready to execute (no spec, no breakdown, no approval, a
  person's task in the way) is scattered across story cards, or not shown.

The plan of plans, the tracker, the live agents and the change checklists
already hold the facts. They need one front page that tells the truth.

## What Changes

- **Milestones.** A spec store may declare milestones in
  `openspec/milestones.yaml`: each one collects whole changes or single
  stories, may count a change's hardware or operator tasks, names the story
  that proves it done, and depends on earlier milestones. One may be the
  project's goal. planlib validates the file.
- **Task kinds.** A `tasks.md` item may carry a trailing `[metal]` or
  `[operator]` tag. Untagged items are agent work. planlib counts each kind.
- **The project home.** Opening a project shows its home page; the graph is
  one click away. Every signed-in person sees the same page. It has two focal
  points:
  - **Execution health:** a verdict on whether agents will stay busy (healthy,
    will idle, idle now, stuck), with its reasons, the agent slots, and the
    runway of ready, approved work.
  - **Not ready to execute:** every unit of planned work that cannot run yet,
    with its reason, ordered by urgency.
- **A timeline across the page:** milestone ticks, a "we are here" marker, and
  a mark for each upcoming blocker that needs a person. The axis is work size
  now, and wall-clock time once estimates exist.
- **Deep links.** Every story, change and milestone on the home opens the
  graph at that spot, with the story selected and attached to the planning
  chat.

## Capabilities

### New Capabilities

- `planning/milestones`: the milestones file, task kinds, and how planlib
  computes milestone membership, progress and the critical path.
- `planning/project-home`: the home page, its two focal points, the timeline
  and the deep links.

### Modified Capabilities

## Impact

- `workbench/src/planlib`: read and validate `milestones.yaml`, parse
  `tasks.md` items and their kinds, compute progress and the critical path.
- `workbench/src/workbench`: a home endpoint and its live updates; it reads
  Sortie's state for agent slots and held runs.
- `workbench/frontend`: the home page, routing (a project opens on its home),
  deep links into the graph.
- The schemas the workbench ships: a new `milestones.schema.json`.
- Sortie: none. It already reports running, retrying and held runs and the
  agent concurrency cap.
