Work is in `~/dev/plan-workbench`, plus one field in the Sortie fork. Every task ends with `uv run pytest`, and, for frontend tasks, `npm run check` and `npm test` in `frontend/`.

## 1. planlib

- [x] 1.1 Make `status` and `approved_digest` optional in the breakdown schema, and add `review` and `supersedes` to deliverables, in the store template and the test fixtures. Verify with schema tests: a breakdown without status, and the two new fields.
- [x] 1.2 Add `story_digest`, and make `validate` take `approvals` and `frozen` (design D2): per-story approval, epic approval from its stories, `review` and `digest` on story nodes, `supersedes` rewiring, and the `frozen` and supersede checks. Remove `approve`. Verify with tests for each scenario of `planning/story-approval`, `planning/plan-validator`, and `planning/story-lifecycle` that planlib owns.

## 2. Sortie

- [x] 2.1 Add `plan_states` to `GET /api/v1/plan/graph` under plan control, null otherwise. Verify with a handler test, and update the workflow reference and CHANGELOG.

## 3. Workbench backend

- [x] 3.1 Add migration `002_approvals.sql` and registry methods for approvals and re-reviews (design D1). Verify with registry tests, including that deleting a project removes its rows.
- [x] 3.2 Add the overlay (design D3) and use it in `Hub.rebuild`. Pass approvals and the frozen set to `PlanState.refresh`. Verify with tests for each plan status, `held_by`, re-review, and a frozen edit.
- [x] 3.3 Replace the approve route, and add pull-back, cancel, and supersede (design D5), each needing the `approver` role and recording the actor. Verify with route tests, including `403` for a planner, and the dependents' re-reviews after a cancel.
- [x] 3.4 Build the sync graph from the overlay, with `release`, `review`, `approved_by`, and `approved_at`, and strip overlay-only fields. Verify with a test that the graph posted to a fake Sortie validates against the published plan graph schema.
- [x] 3.5 Pull back a released story whose content changed (design D4), and import old approvals on project open (design D6). Verify with tests for both.

## 4. Frontend

- [x] 4.1 Show each story's plan status on its node and in the selection details, with the reasons, approver, and review gate. Verify with component tests for each status.
- [x] 4.2 Add the approver actions: approve the epic, approve one story, approve all drafts, pull back, cancel, and supersede. Hide them for a planner. Show releases in the sync dialog. Verify with component tests, then check them in the workbench Firefox.

## 5. Documentation

- [x] 5.1 Update `docs/operator-guide.md` (planning steps, approval, release, cancel, and supersede) and the planning prompt (`prompts/planning-session.md`: the agent never approves, writes `review`, and uses `supersedes` for started stories). Verify that each new route and status named in the specs appears in the guide.
