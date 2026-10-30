## Purpose

Gives each project a home page that tells everyone working on it, at a glance and kept live, how far the project is from its goal, whether its agents will stay busy, and which work is not yet ready to execute, with one click from any item into the graph to plan it.

## ADDED Requirements

### Requirement: A project opens on its home
Opening a project SHALL show its home page. The graph view SHALL have its own address, and each of the two SHALL be one action away from the other. Every signed-in person SHALL see the same home. The home SHALL add no role check; an action offered on it SHALL keep the route check it has elsewhere.

#### Scenario: Opening a project
- **WHEN** a person opens project `ortus-nova-specs`
- **THEN** its home page shows
- **AND** one action opens the graph view

### Requirement: The timeline
The top of the home SHALL be a timeline across the page from the first milestone to the last, in dependency order. Each milestone SHALL be a labelled tick, and the goal's tick SHALL be marked as the goal. Each milestone's span SHALL be proportional to the work it counts (its stories and tasks, or their estimates when every story has one). A "we are here" marker SHALL sit at the share of that work that is done, with the done stretch drawn differently from the rest. Each unit of work that is not ready to execute for a reason that needs a person SHALL appear as a blocker mark at its milestone, and SHALL name its story or change on hover and on keyboard focus.

#### Scenario: Partway through M1
- **WHEN** M0 is done, M1 is a third done, and M2 is the goal
- **THEN** the marker sits a third of the way into M1's span
- **AND** M2's tick is marked as the goal

#### Scenario: A blocker that needs a person
- **WHEN** story `run-homelab-through-sortie/nested-opt-in`, in M1, has no spec
- **THEN** a blocker mark sits in M1's span
- **AND** focusing it names `run-homelab-through-sortie/nested-opt-in` and "no spec"

### Requirement: Execution health
The home SHALL show a verdict on whether the agents will stay busy, the first that applies of:

1. **stuck**: Sortie is unreachable, the last sync failed, or a run is held;
2. **done**: no planned story is left to run;
3. **idle now**: an agent slot is free and no released, unstarted story waits;
4. **will idle**: every slot is busy and fewer released, unstarted stories wait than there are slots;
5. **healthy**: every slot is busy and at least as many released, unstarted stories wait as there are slots.

With the verdict it SHALL show its reasons (each held run and why, the failed sync and why, or the free slots against the stories waiting), the agent slots in use and free, the stories running, and the runway: the count of released, unstarted stories, beside the slot count. Agent slots SHALL be Sortie's concurrency cap.

#### Scenario: Free slots and nothing ready
- **WHEN** Sortie runs 3 agents at most, none is running, and no released story waits
- **THEN** the verdict is "idle now", with the reason that 3 slots are free and 0 stories are ready

#### Scenario: A held run
- **WHEN** a run is held on a permission request
- **THEN** the verdict is "stuck", naming that story and "permission request"

#### Scenario: Healthy
- **WHEN** 3 slots are busy and 4 released stories wait
- **THEN** the verdict is "healthy", with a runway of 4 stories against 3 slots

### Requirement: Not ready to execute
The home SHALL list every story in an unfinished milestone that cannot run yet, and every included change with no breakdown, each with the first reason that applies: no breakdown; no spec (a `story`, not an enabler, that covers no requirement); needs re-review; not approved; held for approval (approved, but a blocker is not); waits on a person (an open person task in its milestone, named); waits on work (an unfinished blocker that is planned and approved). Reasons other than "waits on work" SHALL be marked as needing a person; "waits on work" items SHALL be shown less prominently. The list SHALL be ordered by urgency: earlier milestones first, then stories on the next milestone's critical path, then by how many unfinished stories transitively depend on the item, then plan order. Each item SHALL show whether it is on the critical path and how many stories wait behind it.

#### Scenario: Ordered by urgency
- **WHEN** M1 holds `nested-opt-in` (no spec, on the critical path, 4 stories behind it) and `vm-mirrors` (not approved, off the path, none behind it), and M2 holds `metal-apply` (waits on a person)
- **THEN** the list shows `nested-opt-in`, then `vm-mirrors`, then `metal-apply`
- **AND** `nested-opt-in` is marked on the critical path with 4 stories behind it

#### Scenario: Waiting only on time
- **WHEN** `homelab-image` is approved and waits only on approved stories that are running
- **THEN** it is listed as "waits on work", shown less prominently, and not marked as needing a person

### Requirement: Milestone progress on the home
Below the focal points, the home SHALL show each milestone with its stories, agent tasks and person tasks done against total (`planning/milestones`), as separate measures, and SHALL mark the next milestone and the goal. A milestone with no stories SHALL show its tasks, not "no stories".

#### Scenario: Hardware work left
- **WHEN** M2 counts 0 stories and 40 open metal tasks
- **THEN** M2 shows 0 of 40 person tasks done

### Requirement: Deep links into the graph
Every story, change and milestone shown on the home SHALL link into the graph view. A story SHALL open its epic with the story selected and attached to the planning chat; a change SHALL open its epic; a milestone SHALL open the project level with its changes marked.

#### Scenario: Planning the next item
- **WHEN** a person selects `nested-opt-in` in "not ready to execute"
- **THEN** the graph opens at epic `run-homelab-through-sortie` with `nested-opt-in` selected and attached to the planning chat

### Requirement: Live and readable at a distance
The home SHALL update as the plan, the tracker and the agents change, over the project's event stream, without a reload. A story whose state changed SHALL be marked for a few seconds. Motion SHALL stop under a reduced-motion preference. No state SHALL be shown by color alone.

#### Scenario: A story finishes
- **WHEN** a running story's pull request merges and Sortie marks it done
- **THEN** within one update the home's progress, timeline marker and execution health change, and the story is briefly marked

### Requirement: Honest when sources fail
When the plan is invalid, when Sortie is unreachable, or when the store has no milestones file, the home SHALL say so and SHALL show what it still knows. Without a milestones file it SHALL show the project as one milestone and SHALL say that milestones can be declared in `openspec/milestones.yaml`. It SHALL NOT show a count or verdict that its sources cannot support.

#### Scenario: Sortie unreachable
- **WHEN** Sortie does not answer
- **THEN** the verdict is "stuck" with the reason that Sortie is unreachable
- **AND** progress that comes from the store alone still shows, and story progress is marked as last known
