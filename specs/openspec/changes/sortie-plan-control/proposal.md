## Why

Change `plan-approvals` makes the workbench the place where engineers release, pull back, cancel, and supersede stories, and the tracker becomes a view for non-technical people. Sortie cannot carry out those decisions today:

- **Plan sync never sets a status.** The `sortie/plan-sync` spec forbids it, so a released story stays in `Backlog` until a person moves it in the tracker.
- **There is no stop control.** Sortie has no start, stop, cancel, or retry endpoint. `hold` only suspends the watchdog, and the agent keeps running.
- **Blockers are satisfied too easily.** Any blocker in a terminal tracker state counts as satisfied. That includes `Canceled`, and a `Done` that someone set by hand. A story can then start without the work it depends on.
- **"No change needed" proves nothing.** An agent that declares this is trusted, with no evidence.
- **Sortie cannot record who approved.** It writes to the tracker with one token, so the tracker cannot show who approved each story.
- **The workbench cannot find the workers.** Only the host-local broker registry knows which broker serves which issue, so the workbench cannot attach to a worker session.

## What Changes

- **Release through sync.** Each node in the plan graph carries `release: true | false`. Sync moves a released story from its initial state to `tracker.release_state` (for example `Todo`) one time only. It makes that move only from the initial state, so it never overrides a later state. This is the one exception to the rule that plan sync does not change status. Sync still never deletes an issue, and never changes an assignee or a label.
- **Atomic pull-back.** `POST /api/v1/plan/pull-back` moves a released story back to its initial state, but only when no worker has claimed it. The check and the move run under the orchestrator's dispatch claim, so the request cannot race a poll tick. If a worker already claimed the story, the request returns `409 already_claimed`.
- **Cancel.** `POST /api/v1/plan/cancel` stops the story's worker when one is running: it ends the agent session and its broker, and releases the claim. It then moves the issue to `tracker.cancel_state`. The run is recorded as cancelled, so it is not retried.
- **Blockers are satisfied by Sortie's own record, not by tracker state.**
  - A blocker with a plan key is satisfied only when Sortie's trusted record shows one of two things:
    - its pull request merged, with the merge commit Sortie already latches in `merge_completion_reconcile.go`;
    - a confirmed claim that the work was already done (see below).
  - A merged pull request counts as reviewed, even when the forge required no review.
  - A cancelled blocker is never satisfied.
  - A blocker without a plan key, which Sortie never ran, is satisfied only by `tracker.done_state`.
  - The orchestrator's blocker check (`isBlockedByNonTerminalSet`) uses these rules for issues with a plan key. Workflows that do not use plan sync keep the old behavior.
- **The review gate decides how a story reaches the merge.**
  - `review: human`: a person reviews the pull request in the forge and merges it.
  - `review: criteria`: a separate Sortie stage (stage chain `next`) runs a new agent session. That session checks the story's acceptance criteria and gives a verdict. When it passes, Sortie merges the pull request through its auto-merge reaction.
  - The self-review of the implementing agent never counts as the gate.
- **A claim that the work was already done needs evidence.** Along with `no-change-needed` in `.sortie/status`, the agent writes `.sortie/evidence.json`, which cites either a plan key or a commit.
  - A cited commit is confirmed only when it is on the base branch of the host-owned mirror (change `execution-environment`).
  - A cited plan key is reported to the workbench as a proposed supersede.
  - A claim without a confirmed citation satisfies nothing, and the plan graph reports it as `unverified_no_change`.
- **The approver goes into the tracker.** Each node in the sync carries `approved_by` and `approved_at`. A new capability, `approval_fields`, stores them as explicit tracker fields. The Huly adapter uses custom attributes, the same way it stores `sortiePlanKey`. An adapter that does not declare the capability writes no approval fields, and the capabilities report says so.
- **Worker discovery.** `GET /api/v1/state` and `GET /api/v1/{identifier}` include each running issue's broker `http_url`. The broker reports its address to Sortie with its session token when it registers. The viewer token never appears in these unauthenticated responses. `GET /api/v1/{identifier}/broker` returns it, and requires operator scope.
- **The plan graph reports satisfaction.** `GET /api/v1/plan/graph` gives each node its satisfaction (`merged`, `no_change_confirmed`, `unverified_no_change`, `canceled`, or none), its merge commit, and its pull request URL.

## Capabilities

### New Capabilities
- `sortie/plan-release`: the `release` flag in the sync, the one-time move to `tracker.release_state`, and the atomic pull-back.
- `sortie/plan-cancel`: the cancel endpoint, stopping the worker and its broker, the cancel state, and the rule that a cancelled run is not retried.
- `sortie/blocker-satisfaction`: satisfaction from Sortie's record for issues with a plan key (merged, or a confirmed claim that the work was already done), tracker `done_state` for blockers without a plan key, and the rule that a cancelled blocker never counts.
- `sortie/review-gate`: the `review` field on plan nodes, how a `human` story reaches the merge, and the separate acceptance-criteria stage with auto-merge for a `criteria` story.
- `sortie/no-change-evidence`: the `.sortie/evidence.json` format, how a citation is confirmed against the mirror or the plan, and how the result is reported.
- `sortie/approval-fields`: the tracker capability, the per-node approver fields in the sync, and how Huly stores them.
- `sortie/worker-discovery`: the broker's report to Sortie, `http_url` in the state API, and the token endpoint that requires operator scope.

### Modified Capabilities

None. This store has no archived specs yet. This change revises in-flight specs of other changes:
- change `plan-to-tracker-dag`: `sortie/plan-sync` (the release exception), `sortie/plan-graph-api` (satisfaction fields), `sortie/tracker-write-capabilities` (`approval_fields`);
- change `sortie-session-control`: the cancel control;
- change `acp-broker`: the broker reports its address.

## Impact

- Sortie fork (`~/dev/sortie`), on a branch off `feat/plan-to-tracker-dag`. Changes are additive wherever possible, so upstream rebases stay small:
  - `internal/plan`: the release flag, the approver fields, and the satisfaction fields in the graph;
  - `internal/server`: the pull-back, cancel, and broker-token endpoints, and the broker URL in state;
  - `internal/orchestrator`: the blocker check for issues with a plan key, the pull-back under the claim, cancel, and the evidence check on a no-change exit;
  - `internal/persistence`: cancelled runs, and confirmed no-change claims with their evidence;
  - `internal/config`: `release_state`, `cancel_state`, and `done_state`;
  - `internal/registry` and the Huly adapter: `approval_fields`;
  - `acp-broker/internal/broker`: the broker reports its address.
- Docs in the fork: the workflow reference, the agent-to-orchestrator protocol (`.sortie/evidence.json`), and the Huly adapter notes.
- The `review: criteria` path needs the auto-merge reaction and an SCM adapter. The no-change commit check needs the host mirror from change `execution-environment`. Without the mirror, a cited commit cannot be confirmed and counts as unverified.
- Out of scope:
  - dispatch across several projects;
  - tracker adapters other than Huly for `approval_fields`;
  - steering workers from the workbench; this change only lets the workbench find them.
