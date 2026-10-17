# Verification

All work is on Sortie branch `feat/plan-control`, off `plan-bench`. `make test` (race detector) passes all 71 packages, `make lint` reports 0 issues on linux, darwin, and windows, and `make lint-docs` (lychee 0, offline) reports 0 errors.

## End-to-end check (task 10.1)

Task 10.1 asked for a walk through `scripts/dev.sh` with a local Huly. That was not possible without changing the user's Huly: plan control requires merge completion, which requires `tracker.handoff_state`, and the classic workflow of workspace `sortie` has no state that is neither active, terminal, nor the backlog state (Backlog, Todo, In Progress, Done, Canceled). Adding `In Review` means editing the space type that the user's `DEV` project shares. The dev stack was also running at the time, on Sortie's port.

The loop was instead walked in `internal/orchestrator/plan_loop_test.go` (`TestPlanControlLoop`). It uses the real plan syncer, a real SQLite store with every migration, the real blocker judge, the real dispatch predicate (`EvaluateCandidate`), and the real pull-back and cancel. One in-memory tracker serves both the sync and the candidate reads, as Huly does. Its output:

```
step 1 preview: {Creates:4 Updates:0 Parents:0 RelationsAdded:1 RelationsRemoved:0 Orphans:0 Releases:3 Labels:3 Approvals:3}
step 1: synced; a3, b1, c1 released to Todo with review labels and approvers
step 2: a3 and c1 dispatchable, b1 held by a3 (not_merged)
step 3: c1 pulled back to Backlog; a stale Todo read cannot dispatch it
step 3: pull-back of the dispatched a3 refused with already_claimed
step 4: a3 merged and recorded; b1 dispatchable
step 5: b1 cancelled while running: worker stopped, issue Canceled, dependents held (canceled)
--- PASS: TestPlanControlLoop (0.14s)
```

What the loop does not exercise, and where it is covered instead:

- The event loop's control path (`sendControl`, `handleControl`): covered by the existing hold, release, and escalate tests, which share it.
- Merge completion latching the commit from a forge: `TestReconcileMergeCompletion_RecordsThePlanMerge` and `TestReconcileMergeCompletion_FailedPlanRecordRetries`. Step 4 records the merge through the same `recordPlanMerge`.
- The broker reporting its address (step 6 of the task): `acp-broker/cmd/acp-broker` runs the real broker binary against a fake Sortie API (`TestBroker_ReportsItsHTTPListenerToSortie`, `TestBroker_RunsWhenSortieIsDown`, `TestBroker_CredentialCheckReportsNothing`). The server routes are covered by `TestBrokerReport`, `TestBrokerRead`, and `TestStateCarriesTheBrokerURLOnly`.
- Huly specifics: the adapter tests against the Huly fake, which now honors projections like the real server (task 2.3).

The real binary validates a plan-control workflow with a criteria chain, and refuses one whose criteria rule leads to no `gate: criteria` rule:

```
$ sortie validate WORKFLOW.md
valid rc=0
$ sortie validate broken.md
error: config.dispatch.rules[0]: rule "implement" matches sortie-review:criteria, but its chain [implement] ends in no gate: criteria rule
broken rc=1
```

## Deviations from the design

- **Merge record.** `pr` holds `owner/repo#number`, not a URL. The merge-completion entry knows the pull request only by number, owner, and repository.
- **Unverified claims** are kept in `plan_satisfaction` with kind `unverified_no_change` and the reason in `ref`, not in run history, so the plan graph can report the reason with one read.
- **Branch-protection warning (5.5).** No SCM adapter can read branch protection. Instead of a startup preflight, auto-merge logs one warning per criteria story that waits on the forge's `REVIEW_REQUIRED`.
- **Dispatch block clearing.** A block clears when a candidate read no longer reports the issue at all. Candidate reads hold only active states, so this means the tracker moved it out of them.
- **No-change confirmation** runs in the worker goroutine, which already holds the repository, not at exit on the event loop. The exit only records the verdict.
- **The approval-fields capability** is never offered through the agent's `tracker_api` tool.

## Pre-existing defects fixed on the way

- The fork's migrations 025 to 027 reused upstream's numbers. They are now 1001 to 1003 (`plan-bench`, `b83d669b`), and an old fork database is refused with a message to delete it.
- Huly never checked that `no_change_state` exists in the project (`100f35c4`).
- Three flaky tests: `TestServe_RestartedAtSamePathServesNewConnection` (`7ff19d19`), `TestSessionToken_DoesNotTrimTruncatedText` (`d07d3333`), and `TestTelemetry_ModelAtTurnStart` (in `acp-broker`). The last one failed once in a full run and could not be reproduced afterwards. Its fix orders the two streams explicitly.
- The Huly test fake ignored projections, so a missing projected field could not fail a test.
