# Verification

Work is in `~/dev/plan-workbench` on `main`, plus `plan_states` in the Sortie fork (branch `feat/plan-states`, merged into `plan-bench` as `e8366e65`).

| Task | Commit |
| --- | --- |
| 1.1, 1.2 planlib | `cf88f8f` |
| 2.1 Sortie `plan_states` | `e8366e65` (Sortie) |
| 3.1 to 3.5 backend | `387abdf`, and `418937b` (schema upgrade, below) |
| 4.1, 4.2 frontend | `f44268d` |
| 5.1 docs and prompt | `16f8ae1` |

## Checks

- `uv run pytest`: 165 passed. `npm run check`: 0 errors. `npm test`: 57 passed.
- Each scenario has a test: planlib in `tests/planlib/test_approval.py` and `test_lifecycle.py`; the workbench in `tests/workbench/test_approvals.py` (held and ready, the sync graph validated against the published plan graph schema, frozen edit, pull-back of an edited released story, cancel and re-review, supersede, a pull-back that loses to a claim, an unverified no-change claim, a planner refused, the one-time import of old approvals) and `test_approvals_registry.py`; the frontend in `frontend/tests/sync.test.ts` ("approver actions").
- Mutation checks, each restored after: approving a story without its blockers (`held_by` forced empty) fails 2 tests; dropping the re-review insert of a cancel fails 2 tests; showing the approver actions without the `approver` role fails "hides every action from a planner"; not writing upgraded schema files fails `test_an_old_store_gets_the_current_schemas`.

## Live check in the workbench Firefox

An isolated workbench (local mode, port 8798, a copy of the dev home) with a two-change plan: `accounts/a3`, and `billing/b1` (depends on `a3`) and `billing/b2` (`review: criteria`).

1. The copied project carried the old breakdown schema and rejected `review` ("unknown field review"). This found the defect fixed in `418937b`: on open, the workbench now replaces the schema files it ships that differ in the store, in one commit. After a restart the plan was valid.
2. The `billing` epic showed **Approve the epic (2 stories)**. After it: `b1` was Held ("Waits for the approval of accounts/a3", "held for approval" on its node), `b2` Ready, each "Approved by Local operator" with the time.
3. **Approve the epic (1 story)** on `accounts`: `b1` became Ready.

Two display defects found and fixed in `f44268d` before the commit: the approve button rendered white on white (a later `.attach` rule overrode `.approve`), and the node hid the plan status of stories not yet in the tracker.

Not checked live: pull-back, cancel, supersede, and the release counts of the sync dialog, because they need a Sortie under plan control. The route tests cover them against the fake Sortie, and Sortie's side is covered by `TestPlanControlLoop` (see `archive/2026-10-17-sortie-plan-control/verification.md`).

## Deviation

- Design D6 said old approvals are imported on project open. Opening a project now also updates its planning schemas (`418937b`); without that, no project made before this change accepts `review` or `supersedes`.
