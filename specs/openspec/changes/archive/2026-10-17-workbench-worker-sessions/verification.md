# Verification

Work is in `~/dev/plan-workbench` on `main`. Sortie needed no change.

| Task | Commit |
| --- | --- |
| 1.1 worker fields | `822038b` |
| 1.2 command records | `ae34994` |
| 1.3 relay and routes | `e62a482` |
| 2.1 `Transcript.svelte` | `4790e95` |
| 2.2 worker list and pane | `3b7a692` |
| 3.1 docs | `3c1fec9` |

## Checks

- `uv run pytest`: 176 passed. `npm run check`: 0 errors, 0 warnings. `npm test`: 64 passed.
- `tests/workbench/test_workers.py`: worker fields (running and watchable, retrying, a broker that did not report, a failed state read, no state read without a runtime); an approver's steer reaches the broker and is recorded with the name and run; a planner gets `403` for every command but `state`, and can watch; an unknown identifier gets `404` with no Sortie call; the stream follows to a new run (`id: 0`, the browser's `Last-Event-ID` sent to the first broker only) and ends; no response carries the viewer token or the broker's address; a worker without a broker gets `409`.
- `frontend/tests/workers.test.ts`: the list, *Watch* in the details, the pane in place of the planning chat and the return, an approver's steer (with the sender's name), take over, hand back, and cancel, a planner's watch-only pane, following and ending.
- Mutation checks, each restored after: no role check on commands; no project check on the identifier; `Last-Event-ID` sent to every broker; permission answers offered to a planner. Each failed at least one test.

## Live check in the workbench Firefox

An isolated workbench (local mode, port 8798) against a fake Sortie and fake brokers over HTTP (`/tmp/opencode/live/fakes.py`), with story `billing/b1` running as `HLAB-1`:

1. The context card listed `HLAB-1` under **Workers**, with its last message and **Watch**.
2. **Watch** showed "Watching HLAB-1 · billing/b1 · implement · running · floor: driver", the replayed tool call, and the permission request.
3. A steer reached the fake broker with the viewer token, was recorded as sent by "Local operator", and showed with that name. **Take over** sent `interrupt`; the floor changed to "human".
4. Three run changes: each time the pane said "The earlier run ended. Following the new run (review).", cleared the earlier run, and showed the new one. Ending the story showed "The worker ended".
5. **Back to planning** returned to the planning chat.

One defect found and fixed before the commit: *Watch the worker* stayed offered for the worker already shown.

Not checked live: a planner's view (local mode has one identity with both roles, and the Dex container from `workbench-identity` was removed); the tests cover it on both sides. A real `acp-broker` behind real Sortie, for the reason in the design's risks.
