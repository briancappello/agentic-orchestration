## Context

See proposal.md for the motivation and the specs for the requirements. The facts below come from the Sortie fork on `plan-bench`.

**Dispatch and control**

- All orchestrator state (`Running`, `Claimed`, `RetryAttempts`, and the rest) belongs to one event-loop goroutine (`internal/orchestrator/state.go:836`). HTTP control requests reach it as commands on `controlCh`, with a reply channel and a 5 s bound on both the send and the reply (`orchestrator.go:1883`). `hold`, `release`, and `escalate` use this path.
- `handleTick` dispatches straight from the `FetchCandidateIssues` snapshot and never reads the tracker again (`orchestrator.go:864`). `DispatchIssue` claims on the loop, but the worker goroutine makes the move to `in_progress_state` later (`worker.go:785`). A freshly claimed issue can therefore still read `Todo`.
- Huly's `TransitionIssue` reads and then writes. It has no compare-and-swap (`tracker/huly/writes.go:18`).
- Reconcile already stops a run whose issue turned terminal: it cancels the worker, calls `releaseIssueRuntimeState`, and leaves workspace cleanup to the exit (`reconcile.go:536`, `exit.go:265`). Under `environment.host_prefix`, the broker kills the agent's process group 5 s after the cancel.

**Blockers and merges**

- `domain.BlockerRef` carries `ID`, `Identifier`, `State`, and `DisplayID`, but no plan key (`domain/issue.go:89`). Huly fills it from the candidate read (`tracker/huly/issues.go:228`).
- `EvaluateCandidate` is the one real dispatch predicate (`dispatch.go:451`). The retry lane repeats the blocker rule (`retry.go:529`), and so does `firstNonTerminalBlocker` for logs (`dispatch.go:400`).
- Merge completion latches the merge commit in `reaction_fingerprints(issue_id, "merge-completion", sha)` (`merge_completion_reconcile.go:224`). It seeds only on the exit of the final stage, and only while the issue is in `handoff_state` (`exit.go:949`, `merge_completion_reconcile.go:181`). Its row stores no pull request URL.
- A no-change run is recorded only as `succeeded` (`exit.go:413`). Self-review can retract a no-change declaration that it did not confirm (`worker.go:1938`).

**Plan sync and stages**

- Graph nodes are decoded with `DisallowUnknownFields` (`plan/graph.go:119`). Any `draft` node puts its whole `change` in `SkippedDrafts` (`plan/preview.go:172`). The tracker digest of a preview leaves out state (`preview.go:327`).
- `TransitionIssue` and the label operations are already on the base `TrackerAdapter` (`domain/tracker.go:105`).
- Dispatch rules match on `labels` (`config/dispatch.go:96`). Auto-merge is on or off for the whole workflow. It merges when the forge reports the review decision as `Approved` or `NotRequired` (`auto_merge_reconcile.go:130`).
- The broker's Sortie client starts before the HTTP listener binds (`acp-broker/cmd/acp-broker/broker.go:147`, `:211`). Only the broker's registry file holds the URL.

**Constraints**

- Every change stays additive, and is off unless a workflow opts in, so upstream merges into `plan-bench` stay cheap.
- `Reload()` stays fail-safe.
- Files in `.sortie/` are untrusted input from the agent, and are read only through `workspacekit`.

## Goals / Non-Goals

**Goals:**

- A pull-back and a dispatch can never both win, even when the tracker read is stale.
- Only Sortie's own durable records can satisfy a blocker with a plan key.
- With plan control off, behavior matches `plan-bench` exactly, and the existing tests pass unchanged.

**Non-Goals:**

- A compare-and-swap in the tracker. The guarantee comes from Sortie's claim, not from the tracker.
- Following a pull request after a person drags its issue out of `handoff_state`. Sortie reports `awaiting_merge_record` instead.
- Deciding what a plan does about a cancelled or unverified story. The workbench owns that (change `plan-approvals`).

## Decisions

### D1. `tracker.release_state` turns plan control on

Plan control is on when `tracker.release_state` is set. The other plan-control settings are required only then, and are checked together in the tracker validators (`config.go:628`), and in Huly's startup check that each state exists (`huly.go:145`).

- *Alternative:* a separate `plan_control: true` switch. Rejected: a second setting that must agree with the first can only add a misconfiguration.
- The validator also checks the states against each other: release is active, backlog is neither active nor terminal, and cancel and done are terminal. It requires `reactions.merge_completion`, because without it Sortie cannot satisfy any blocker with a plan key, and every story after the first would wait forever.

### D2. Pull-back and cancel run on the event loop, with a dispatch block

Both requests take one shape:

1. The HTTP handler resolves the plan key to an issue id, using the plan-key lookup, outside the loop. That tracker read never blocks dispatch.
2. The handler sends a new `controlKind` (`controlPullBack` or `controlCancel`) through `sendControl`.
3. On the loop, Sortie checks `Claimed`, `Running`, and `RetryAttempts`, which are the only truth for "a worker has it":
   - Pull-back answers `already_claimed` when any of them holds the issue.
   - Cancel cancels the worker and calls `releaseIssueRuntimeState`, as the terminal path of reconcile does.
4. On the loop, Sortie sets a **dispatch block** for the issue: `state.DispatchBlocks[id] = {want: <target state>}`.
5. On the loop, Sortie calls `TransitionIssue` to `backlog_state` or `cancel_state`. When the write fails, Sortie removes the block for a pull-back and replies with the error. For a cancel, Sortie keeps the block and reports the failed write, so the worker it stopped is not dispatched again before a retry of the cancel.
6. `EvaluateCandidate` and the retry lane refuse every issue that has a block. A candidate read that no longer reports the issue clears the block: candidate reads hold only active states, so the tracker then shows the move. A block also expires after 10 minutes, so it is never permanent. After it expires, Sortie only logs that the tracker still disagrees.

The tracker write happens on the loop because the claim check and the write must not have a dispatch between them. Exit handling already writes the tracker on the loop (`exit.go:811`), and the 5 s control bound limits the stall.

- *Alternative:* a write outside the loop, and a block only. Rejected: a tick between the check and the block could dispatch.
- *Alternative:* re-read the tracker before every dispatch. Rejected: it adds one tracker call to each dispatch for every workflow, and it still races the claim.

Cancel records the run as `cancelled` through the existing `WorkerExitCancelled` path. `cancel_state` is terminal, so neither retry nor reconcile starts the issue again.

### D3. A table of its own for satisfaction

A new table holds what satisfies a blocker: `plan_satisfaction(issue_id, kind, ref, pr_url, recorded_at)`, with the primary key `(issue_id, kind)`.

- `kind = merged`: `ref` is the merge commit and `pr` is `owner/repo#number`. Merge completion writes it before the transition, so a failed write keeps the entry pending.
- `kind = unverified_no_change`: `ref` is the reason. It satisfies nothing and only explains why dependents wait.
- `kind = no_change`: `ref` is `commit:<sha>` or `plan:<key>` (D6).

Sortie never deletes from this table. A migration fills it from the existing `merge-completion` fingerprints, so issues that merged before the upgrade still count.

- *Alternative:* read `reaction_fingerprints` directly. Rejected: it is a reaction's internal state. It stores no pull request URL, and a later change to reactions could start deleting from it. A table of our own also keeps the upstream merge surface small.

### D4. The blocker check is a hook that is off by default

`domain.BlockerRef` gains `PlanKey string`. Huly fills it from the plan-key attribute it already reads on candidates. An adapter that cannot read plan keys leaves it empty, and those blockers follow the `done_state` rule.

`EvaluateCandidate` takes a `BlockerJudge`. With plan control off, the judge is the existing terminal-state rule. With plan control on, it applies the rules in `sortie/blocker-satisfaction`. Each tick loads satisfaction for every blocker id of the candidate set in one query. The retry lane, the dry run, and the log reason (`firstNonTerminalBlocker`) all use the same judge, so the four copies of the rule become one.

`awaiting_merge_record` is the reason Sortie gives when the blocker's state is terminal but it has no `merged` row. That is the visible sign that a person dragged a card ahead of its merge.

### D5. The review gate is a label and a gated rule

Sync keeps one label on each story, `sortie-review:human` or `sortie-review:criteria`. It writes it with the adapter's label operations as a new kind of preview operation, `label`.

A dispatch rule gains `gate: criteria`. Validation, with plan control on, requires every chain that a `sortie-review:criteria` issue can enter to end in a `gate: criteria` rule. A stage hop already starts a new run and a new agent session, so the criteria session never shares a session with the implementing one. A task verifies this.

Auto-merge gains one check when plan control is on: it merges an issue only when the issue carries `sortie-review:criteria` and its last successful run came from a `gate: criteria` rule. A `human` story is never merged by Sortie.

The criteria session reports through the existing exit protocol:
- a normal successful exit is a pass;
- `blocked` or `needs-human-review` is a fail.

On a fail, the rule's `on_fail` decides what happens: the name of a rule to hop back to, or `escalate`, the default, which raises `session.escalated`. Sortie posts the session's summary, which names the failed criteria, as the tracker comment.

- *Alternative:* a custom tracker field for the gate. Rejected: dispatch rules can already match labels, and other adapters have labels too.
- *Constraint:* auto-merge still respects the forge. A repository whose branch protection requires an approving review cannot auto-merge `criteria` stories. No SCM adapter reads branch protection, so instead of a startup preflight, auto-merge warns once per criteria story that waits on `REVIEW_REQUIRED`. The smolvm environment guide says so.
- Auto-merge is gated at the one place that merges, through `ReconcileParams.ReviewGate`, which reads the story's labels and the rule of the run that seeded the entry. A failed criteria check seeds no reaction at all.

### D6. Evidence is checked on the host at exit

When a run's standing declaration at exit is `no-change-needed` and plan control is on, Sortie reads `.sortie/evidence.json` through `workspacekit`, with a 4 KiB cap and no links followed. "Standing" means after any retraction by self-review.

- **Commit:** Sortie runs `git merge-base --is-ancestor <sha> <base>` in the host-owned mirror (`internal/gitsync`), with hooks and fsmonitor off. The commit must be a full 40-character hexadecimal id. Without `environment.smolvm.repository` there is no mirror, and the claim is unverified with `no_mirror`. Sortie never runs `git` in a workspace the agent controls.
- **Plan key:** Sortie looks up the key in the same project. A key that is found records `no_change` with `plan:<key>`. The judge then treats the claiming story as satisfied exactly while the cited story is satisfied, one level deep. A plan key that cites itself, or a story that cites it back, is unverified with `cycle`.

The worker goroutine, which already holds the repository, makes these checks off the event loop and reports the verdict in its result; the exit only records it. An unverified claim is recorded as `unverified_no_change` with its reason.

### D7. Graph schema version 2

Plan graph schema version 2 adds four optional fields to story nodes: `release`, `review`, `approved_by` (`{name, id}`), and `approved_at`. Sortie accepts versions 1 and 2. A version 1 graph means no releases, no review labels, and no approval fields, even with plan control on, so a workbench that has not been upgraded cannot release anything by accident. The change `plan-approvals` makes planlib write version 2. The JSON Schema in the workbench's store template and Sortie's decoder change in lockstep, and a test compares the two.

Per-story drafts replace the skip by `change` in `preview.go`. Approval fields take part in the update diff and the tracker digest. A release is checked again for each issue at apply time: an issue that left `backlog_state` after the preview is skipped and reported, never forced.

### D8. The broker reports after its listener binds

After `-http` binds, the broker's Sortie client posts `{http_url, viewer_token}` to `POST /api/v1/{identifier}/broker` with its session token. It retries with exponential backoff, capped at 30 s, until it succeeds or the session ends. Sortie keeps both values on `RunningEntry`, which lives only in memory, and registers the token with the masker. The state snapshot copies only the URL, and `GET /api/v1/{identifier}/broker` reads both with operator scope.

- *Alternative:* Sortie reads the broker registry directory. Rejected: it works only when Sortie and the broker share a host and a user, and the registry is the broker's private interface.

## Risks / Trade-offs

- [A tracker write on the event loop stalls dispatch for up to 5 s] → Only pull-back and cancel do it, and both are rare actions by a person. The control bound already caps the wait, and the stall shows in the loop latency metrics.
- [A person moves a story at the same moment Sortie pulls it back] → The tracker has no compare-and-swap, so the last write wins. The dispatch block still stops Sortie from starting it, and the next sync shows the state.
- [A card dragged out of `handoff_state` before its merge never gets a merge record] → The story's dependents wait with `awaiting_merge_record`, which the workbench shows. The way out is a supersede or a cancel in the plan. Following such pull requests is left for later.
- [Repositories that require an approving review cannot auto-merge `criteria` stories] → The preflight warns, and the docs say so. Those repositories use `review: human`.
- [The judge in `EvaluateCandidate` touches upstream's core dispatch path] → The change is one injected interface whose default is today's rule. Upstream merges into `plan-bench` conflict only at that call site.
- [Evidence by plan key could chain stories into loops] → Sortie resolves the citation one level deep only, and detects cycles (D6).
- [Satisfaction lookups add a query to each tick] → One indexed query for the whole candidate set. It is skipped when plan control is off.

## Migration Plan

1. Deploy the new binary. The migration creates `plan_satisfaction` and fills it from the `merge-completion` fingerprints. With `release_state` unset, nothing else changes.
2. Configure `backlog_state`, `release_state`, `cancel_state`, `done_state`, merge completion, and a `gate: criteria` rule in the workflow, then reload. The validator rejects a partial setup, so the reload keeps the old configuration until it is complete.
3. Upgrade the workbench (change `plan-approvals`) to send version 2 graphs. Until then, sync works as before and releases nothing.

Rollback: unset `tracker.release_state` and reload. The new table stays, and nothing reads it.

## Open Questions

- Whether merge completion should keep following a plan-keyed issue's pull request after the issue leaves `handoff_state`. That would remove most `awaiting_merge_record` cases, and it can be added later without changing these specs.
- The exact backoff and expiry values (the 10-minute dispatch block, the 30 s cap on broker reports). These are tuning values, not contract.
