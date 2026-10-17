# planning/worker-sessions Specification

## Purpose
Lets people watch the workers Sortie runs for a project's stories from the plan workbench, follow a story from run to run, and, with the approver role, steer or cancel them. The workbench relays each worker's broker, so no broker token reaches the browser.

## Requirements

### Requirement: Worker list
Each project view SHALL show the project's workers: the stories that Sortie runs, retries, or holds. For each worker it SHALL show the story, the tracker identifier, its status (running, retrying, or held), its stage (the workflow rule that runs it), its attempt when retrying, its turn count, its last message, and who holds the floor when a person took over. The workbench SHALL read this from Sortie's state (`GET /api/v1/state`) and its plan graph on every poll. A running worker whose broker reported its address (`sortie/worker-discovery`) SHALL be marked as one a person can watch. Selecting a worker SHALL select its node on the graph.

#### Scenario: A worker is listed
- **WHEN** Sortie runs `PLAT-3`, the issue of story `billing/b1`, under rule `implement`, and its broker reported
- **THEN** the project's worker list shows `billing/b1` as running, at stage `implement`, with its turn count and last message, and offers to watch it

#### Scenario: A project Sortie does not dispatch
- **WHEN** a project is not Sortie's configured project
- **THEN** its worker list is empty and says that agents are not dispatched for it

### Requirement: Watch a worker
A person with the `planner` role SHALL be able to watch a worker. Watching SHALL show the worker's session in the chat pane, in place of the planning session, labeled with the story, the tracker identifier, and the stage. The pane SHALL show the session from its start, as the broker replays earlier events to a late viewer, and the commands people sent to it, each with the name of who sent it. A control SHALL return the pane to the planning session. The planning session SHALL keep running while a person watches a worker.

#### Scenario: Watch, then return
- **WHEN** a person watches `PLAT-3` and then returns to planning
- **THEN** the chat pane showed `PLAT-3`'s session from its first event, and then shows the planning session, which was not stopped

### Requirement: The backend relays the worker's broker
The workbench backend SHALL read a worker's broker address and viewer token from Sortie (`GET /api/v1/{identifier}/broker`) with its Sortie token, and SHALL relay the broker's events and commands under the person's workbench session. The broker's address and token SHALL NOT reach the browser. The backend SHALL relay only workers of the project named in the request, and SHALL refuse another identifier with `404`.

#### Scenario: No token in the browser
- **WHEN** a person watches `PLAT-3`
- **THEN** no response to the browser carries the broker's viewer token or address

#### Scenario: A worker of another project
- **WHEN** a request for project `billing` names an issue that is not a story of `billing`
- **THEN** the workbench answers `404` and asks Sortie for no broker

### Requirement: Commands and roles
From a watched worker, a person with the `approver` role SHALL be able to steer, prompt, interrupt (take the floor), hand back, and answer permission requests, with the broker's own commands (`acp-broker/steering`). A person with only the `planner` role SHALL be able to watch, and SHALL be refused every command but `state` with `403`; the chat pane SHALL not offer those commands to them. The workbench SHALL record each command it relays, with the person's identity, the operation, its text, the run it was sent to, and the time.

#### Scenario: A planner tries to steer
- **WHEN** a person with only the `planner` role sends `steer` to `PLAT-3`
- **THEN** the workbench answers `403` and relays nothing

#### Scenario: An approver steers
- **WHEN** Ann, an approver, steers `PLAT-3` with "use the existing invoice table"
- **THEN** the broker receives the steer, and everyone watching `PLAT-3` sees the message with "Ann" as its sender

### Requirement: Follow across attempts
While a person watches a story, the stream SHALL follow the story's runs: when the watched run ends and Sortie starts another run of the same story, for a retry or the next stage, the pane SHALL switch to the new run's session and say so, naming the new stage. When the story has no running or retrying run, the pane SHALL say that the worker ended.

#### Scenario: A retry
- **WHEN** a person watches `PLAT-3`, its run fails, and Sortie starts attempt 2
- **THEN** the pane says that it follows the new run, and shows that run's session

#### Scenario: The story is done
- **WHEN** the watched run ends and Sortie runs nothing more for the story
- **THEN** the pane says the worker ended

### Requirement: Cancel from the view
A watched worker SHALL offer *Cancel story* to a person with the `approver` role. It SHALL cancel through the workbench's story cancel (`planning/story-lifecycle`), with its confirmation, so its dependents go to re-review.

#### Scenario: Cancel while watching
- **WHEN** an approver watching `PLAT-3` chooses *Cancel story* and confirms
- **THEN** Sortie stops the worker and cancels the issue, and the stories that depend on `billing/b1` need re-review
