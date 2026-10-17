Work is in `~/dev/plan-workbench`. Every task ends with `uv run pytest`, and, for frontend tasks, `npm run check` and `npm test` in `frontend/`.

## 1. Backend

- [ ] 1.1 Add `state()`, `issue(identifier)`, and `broker(identifier)` to the Sortie client, and add the worker fields of design D1 to story runtimes on each poll. Verify with hub tests: a running, watchable worker; a retrying one; a failed state read.
- [ ] 1.2 Add migration `003_worker_commands.sql` and registry methods to record and list commands (design D4). Verify with registry tests, including that deleting a project removes its rows.
- [ ] 1.3 Add `WorkerRelay` and the worker routes (design D2, D3): the followed event stream, commands with role checks and recording, and messages. Verify with route tests against a fake Sortie and a fake broker: a planner refused a steer with `403`; an approver's steer reaches the broker and is recorded with the name; an unknown identifier gets `404` without a Sortie call; no response carries the viewer token; the stream follows to a new run and ends.

## 2. Frontend

- [ ] 2.1 Extract `Transcript.svelte` from `ChatPane` with no change in behavior. Verify with the existing chat tests.
- [ ] 2.2 Add the worker client, `WorkerPane`, the worker list, and *Watch* in the selection details (design D5), with the approver-only composer, take over, hand back, and cancel, the follow and end notices, and senders' names. Verify with component tests for a planner and an approver, and check it in the workbench Firefox.

## 3. Documentation

- [ ] 3.1 Describe watching and steering workers, and the roles they need, in `docs/operator-guide.md`. Verify that each route and role in the specs appears in it.
