## Context

The workbench relays one broker today: the planning session's, whose address and token it reads from its own runtime directory (`sessions.py`, `session_routes.py`). Sortie now reports each worker's broker (`sortie/worker-discovery`): `GET /api/v1/state` carries `broker.http_url` for each running issue, and `GET /api/v1/{identifier}/broker` returns the address and viewer token to a control-token caller. `GET /api/v1/{identifier}` carries the running entry (`session_id`, `rule_name`) or the retry entry (`attempt`). The workbench's Sortie token is the control token. Roles and identity come from `workbench-identity`; cancel comes from `plan-approvals`.

## Goals / Non-Goals

**Goals:** list workers, watch one in the chat pane, steer it under the approver role with a record of who sent what, follow a story across runs, cancel from the view.

**Non-Goals:** herdr panes; workers of projects Sortie does not dispatch; any change to the broker or to Sortie.

## Decisions

### D1. Worker fields join the graph, not a second feed

Each poll also reads `GET /api/v1/state`, and the hub adds to each story node's `runtime` the fields the worker list needs: `stage` (`rule_name`), `session_id`, `held` and `holder`, and `watchable` (the broker reported). The worker list is the story nodes with a runtime, so it updates with the graph's SSE stream and needs no route of its own. A failed state read leaves the plan graph's runtime as it is, with `watchable` false.

*Alternative:* a separate `/workers` stream. Rejected: it would duplicate the poll and could disagree with the graph.

### D2. A relay keyed by tracker identifier, resolved per request

`workers.py` holds `WorkerRelay`. It never caches a broker token: each command and each stream (re)connect asks Sortie for the broker. Routes check that the identifier is the tracker identifier of a story node of the project (D1's data) before calling Sortie, so a planner of one project cannot reach another project's worker.

Routes, under `/api/projects/{slug}/workers/{identifier}`:

| Route | Role | Does |
| --- | --- | --- |
| `GET events` | planner | The followed SSE stream (D3). |
| `GET messages` | planner | The recorded commands of the story (D4). |
| `POST commands` | approver, `planner` for `state` | Relays one broker command and records it. |

### D3. Following runs in the backend stream

The `events` stream loops: read `GET /api/v1/{identifier}`; with a running entry whose broker reported, emit `event: run` (`session_id`, `stage`, and `follow: true` after the first), then relay the broker's `/events` until it closes; with a retry entry or a running entry whose broker has not reported yet, wait and read again; with neither, emit `event: ended` and close. The browser's `Last-Event-ID` is passed on only to the first run's broker. Each `run` event carries `id: 0`, so a reconnect after a follow asks the new broker for its whole replay, and the transcript's sequence check drops what it already has.

*Alternative:* the browser re-reads state and reconnects. Rejected: two places would decide what "the same story" is, and a backend stream already exists.

### D4. Commands are recorded in `workbench.db`

Migration `003_worker_commands.sql` adds `worker_commands (project_id, identifier, session_id, op, text, actor_id, actor_name, created_at)`, deleted with the project. The relay records a command after the broker accepts it. `GET messages` returns them for the story, oldest first; the chat pane shows `steer` and `prompt` text as messages with the sender's name, as the planning chat shows its own.

### D5. One chat pane, two sessions

`ProjectView` holds `watching` (an identifier or null). With it set, the chat pane renders `WorkerPane` under the same context card, instead of the planning chat. Both render the transcript with one shared component, `Transcript.svelte`, extracted from `ChatPane`. `WorkerPane` shows the story, identifier, and stage; the floor holder from the broker's `state` events; a composer and *Take over*, *Hand back*, and *Cancel story* for an approver only; and a notice at each follow and at the end. Leaving the planning chat unmounts it but keeps its session, which reconnects with its replay on return, as after a reload.

## Risks / Trade-offs

- **Each command reads Sortie first.** One extra local request per command. Accepted for never holding a token.
- **A follow resets the transcript.** The earlier run's events are not shown after the switch; its broker is gone. The notice says so.
- **No live worker check against Huly.** As with `sortie-plan-control`, plan control needs a handoff state that the user's Huly lacks. The relay is checked against a fake Sortie and a fake broker in tests, and the UI in the workbench Firefox against them.
