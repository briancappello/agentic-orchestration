## Why

The plan workbench is meant to be the engineers' one surface: plan there, release there, and watch and correct the agents doing the work there too. Today it can show only that a story is running. To watch or steer that worker, an engineer has to find its broker by hand on Sortie's host, with `acp-broker ls`, and attach from a terminal. The workbench already holds a full broker client: the chat pane relays the planning session's events and its steer, prompt, permit, interrupt, and handback commands. Change `sortie-plan-control` lets the workbench find each worker's broker through Sortie. Nothing yet connects the two.

## What Changes

- **A list of workers.** Each project view lists the stories that are running, retrying, or held, with their stage, attempt, turn count, last message, and floor holder (the driver or a human). The list comes from Sortie's state (`sortie/worker-discovery`) and the plan graph. Selecting a worker selects its node on the graph, and selecting a running node offers its worker.
- **Attach in the chat pane.** Attaching opens the worker's session in the chat pane, in place of the planning session, with a clear label naming the story and the attempt. The pane shows the session from its start: the broker replays the earlier events to a late viewer. The planning session keeps running, and a switch returns to it.
- **The backend relays, the browser never sees a broker.** The backend reads the broker's URL and viewer token from Sortie with the control token, then relays events and commands under the person's workbench session, as it does for the planning session today. Tokens never reach the browser.
- **Steering.** From an attached worker, a person can steer, prompt, interrupt (take over), hand back, and answer permission requests. These are the broker's own commands (`acp-broker/steering`, `acp-broker/viewer-transport`). The workbench records who sent each command, with the identity from change `workbench-identity`, and the chat shows it.
- **Follow across attempts.** When the attached run ends and Sortie starts the next attempt or stage of the same story, the pane follows to the new session, and says so.
- **Cancel from the view.** The worker view and the graph node offer *Cancel* through Sortie (`sortie/plan-cancel`). The plan side of a cancel, which sends dependents to re-review, belongs to change `plan-approvals`.
- **Roles.** Watching needs the `planner` role. Steering, taking over, answering permissions, and cancelling need `approver`, because each one changes what an agent does.

## Capabilities

### New Capabilities
- `planning/worker-sessions`: the worker list, attaching and switching, the backend relay of a worker's broker, the commands a person may send and the roles they need, recording who sent them, following across attempts, and cancel from the view.

### Modified Capabilities
- `planning/plan-workbench`: `Two-pane layout` and `Selection details`. The chat pane can hold a worker's session as well as the planning session, and a running node offers its worker.

## Impact

- Workbench backend (`src/workbench/`): a worker relay beside the planning-session relay, sharing its broker client (`sessions.py`, `session_routes.py`). The Sortie client gains the state and broker-token reads. The command routes gain role checks and a record of who sent each command.
- Workbench frontend: the worker list, the attach and switch control in the chat pane, the attempt-follow notice, and *Cancel*.
- Depends on change `sortie-plan-control` (broker discovery and cancel) and on change `workbench-identity` (roles and identity).
- Out of scope:
  - herdr panes and herdr-web-ui; the configured `human-surfaces` work stays separate;
  - workers of projects that Sortie does not dispatch;
  - changes to the broker protocol.
