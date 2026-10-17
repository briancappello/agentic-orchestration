The Sortie work is in the fork (`~/dev/sortie`), on branch `feat/plan-control` off `plan-bench`, merged back into `plan-bench` when done. Run `make help` to find the lint and test targets. Every Sortie task ends with `make lint` and `make test` (race detector) passing. "Plan control on" in a test means a workflow with `release_state`, `backlog_state`, `cancel_state`, `done_state`, and merge completion configured. Every task that touches a shared path also checks that the existing tests pass unchanged with plan control off.

## 1. Configuration

- [x] 1.1 Add `tracker.release_state`, `backlog_state`, `cancel_state`, and `done_state` to the tracker config, the schema, and `domain.TrackerStates` (design D1). Verify with config tests:
  - each one alone is accepted when `release_state` is unset;
  - with `release_state` set, each missing setting and each wrong state class (release not active, backlog active or terminal, cancel or done not terminal) is rejected with an error naming the setting;
  - a missing `reactions.merge_completion` is rejected;
  - a failed reload keeps the previous configuration.
- [x] 1.2 Add the four states to Huly's startup existence check, and also `no_change_state`, which the same check misses today. Verify with a Huly adapter test where each state name is absent from the project.

## 2. Satisfaction records and the blocker judge

- [ ] 2.1 Add the migration for `plan_satisfaction(issue_id, kind, ref, pr_url, recorded_at)`, keyed by `(issue_id, kind)`, with the backfill from `merge-completion` fingerprints, and add store methods to upsert a row and load rows for a set of issue ids (design D3). Verify with persistence tests: the backfill copies existing rows, a second migration run is a no-op, and a load of 500 ids is one query.
- [ ] 2.2 Write a `merged` row (merge commit and pull request URL) where merge completion latches its fingerprint. Verify with a merge-completion reconcile test that asserts the row, and a restart test where the workspace is removed and the row stays.
- [ ] 2.3 Add `PlanKey` to `domain.BlockerRef` and fill it in the Huly candidate read from the plan-key attribute. Verify with a Huly test whose blockers include one plan-keyed and one unkeyed issue.
- [ ] 2.4 Add the `BlockerJudge` interface with two implementations: the terminal-state rule of today, and the plan-control rule of `sortie/blocker-satisfaction` with its reasons (design D4). Inject it into `EvaluateCandidate`, the retry lane, the dry run, and the blocked-reason log. Verify with:
  - a table test over each spec scenario (merged, a Done set by hand, canceled, unkeyed Done, unkeyed Canceled, unreadable state, an adapter without plan keys, `awaiting_merge_record`);
  - a test proving the four call sites share the judge;
  - the full existing dispatch test suite passing unchanged with plan control off.
- [ ] 2.5 Load satisfaction rows once per tick for every blocker id in the candidate set, and skip the load when plan control is off. Verify with an orchestrator test that counts store calls per tick.

## 3. Dispatch blocks, pull-back, and cancel

- [ ] 3.1 Add `state.DispatchBlocks` with its target state and expiry, refused in `EvaluateCandidate` and in the retry lane. A poll that reads the target state clears a block, and an expired block is logged and cleared (design D2). Verify with orchestrator tests: a blocked issue is not dispatched from a stale snapshot, a poll in the target state clears the block, and the expiry clears it with a log record.
- [ ] 3.2 Add `controlPullBack` on the event loop: refuse with `already_claimed` when `Claimed`, `Running`, or `RetryAttempts` holds the issue; otherwise set the block, call `TransitionIssue(backlog_state)`, and remove the block when the write fails. Verify with tests for each spec scenario, including a claim made in the same tick as the request, and a failed tracker write that leaves no block behind.
- [ ] 3.3 Add `controlCancel` on the event loop: cancel a running worker through the reconcile terminal path, drop its retry, claim, and pending reactions, set the block, and call `TransitionIssue(cancel_state)`. Keep the block when that write fails. Verify with tests: a running worker stops and its run is recorded `cancelled` with no retry; a waiting story moves to `cancel_state`; an issue already in `cancel_state` is a no-op; another terminal state answers `already_terminal`; and with a fake broker in `host_prefix`, the agent process exits.
- [ ] 3.4 Add `POST /api/v1/plan/pull-back` and `POST /api/v1/plan/cancel`: resolve the plan key outside the loop, return `404` for an unknown key and `409` with each code, and require operator scope. Verify with server tests for every status code, a `403` for a session token, and a `401` without a token.

## 4. Plan sync

- [ ] 4.1 Accept plan graph schema version 2, with the optional story fields `release`, `review`, `approved_by`, and `approved_at` (design D7). Copy the JSON Schema into the workbench's store template in the same change. In the workbench, add a test that compares the template with Sortie's copy at `$SORTIE_SRC`, and fails rather than skips when `SORTIE_SRC` is set but the file is missing. Verify with decoder tests: version 1 and 2 graphs both load, version 1 implies no release and no review, and an unknown field is still rejected.
- [ ] 4.2 Skip draft stories one at a time instead of by `change`, and sync an epic when it, or any of its stories, is approved. Verify with preview tests for the `sortie/plan-sync` scenario "New drafts beside approved stories", and an edge whose second node is a draft.
- [ ] 4.3 Make new issues start in `backlog_state`, and add the `release` preview operation and its apply phase after creates and relations. Re-check `backlog_state` for each issue at apply time, and report a skip when it moved. Verify with tests for each `sortie/plan-release` sync scenario, and one where the issue leaves `Backlog` between preview and apply.
- [ ] 4.4 Add the `label` preview operation, which keeps exactly one `sortie-review:*` label, and never touches other labels. Verify with tests: the label is added, it is swapped when the gate changes, and a label a person added survives.
- [ ] 4.5 Add the **approval fields** capability to the registry and to the capabilities report. Add the three Huly custom attributes, created like `sortiePlanKey` and read-only. Make approval values part of the update diff and the tracker digest. Report `approval_fields_unsupported` for adapters without the capability. Verify with registry declaration tests, Huly write and read tests, a stale-preview test after an approver change, and a test of a non-Huly adapter's preview.

## 5. Review gate

- [ ] 5.1 Confirm that a stage hop starts a new run with a new agent session and no resumed session id. Verify with an orchestrator test over a two-stage chain that asserts two different session ids. When it fails, stop and raise it with the user, because design D5 depends on it.
- [ ] 5.2 Add `gate: criteria` and `on_fail` (a rule name, or `escalate` as the default) to dispatch rules. With plan control on, refuse a workflow in which a chain that a `sortie-review:criteria` issue can enter does not end in a `gate: criteria` rule. Verify with config tests for valid chains, a chain without the gate, an unknown `on_fail` rule, and a failed reload that keeps the old configuration.
- [ ] 5.3 Gate auto-merge with plan control on: merge only an issue labelled `sortie-review:criteria` whose last successful run came from a `gate: criteria` rule. Never merge a `sortie-review:human` issue. Verify with auto-merge reconcile tests for each `sortie/review-gate` scenario, including a passing self-review on the implementing stage.
- [ ] 5.4 Handle a failed criteria exit (`blocked` or `needs-human-review` from a `gate: criteria` rule): no merge, then a hop to `on_fail` or a `session.escalated` notification, plus a tracker comment with the session summary. Verify with exit tests for both `on_fail` forms.
- [ ] 5.5 Add the startup preflight warning for a repository whose branch protection requires an approving review, when a `gate: criteria` rule exists. Verify with an SCM fake that reports required reviews.

## 6. No-change evidence

- [ ] 6.1 Parse `.sortie/evidence.json` through `workspacekit` with a 4 KiB cap and no links followed. Accept only the two citation kinds, a 40-character hexadecimal commit, and a note of at most 2,000 characters. Verify with table tests for each malformed file, a symlink, an oversize file, and a long note.
- [ ] 6.2 At exit, for a standing `no-change-needed` with plan control on, confirm the citation (design D6). Check a commit with `git merge-base --is-ancestor` in the host mirror, with hooks and fsmonitor off. Check a plan key by lookup in the same project, with self and cycle detection. Record a `no_change` row, or an unverified reason in run history. Verify with tests: a commit on base, a commit off base, no mirror (`no_mirror`), an unknown key, a self-citation, a two-story cycle, and a self-review retraction that leaves no row.
- [ ] 6.3 In the judge, satisfy a story with a `no_change` row: `commit:` at once, and `plan:<key>` only while the cited story is satisfied, one level deep. Verify with judge tests for the `sortie/no-change-evidence` scenario "A plan story that did the work".

## 7. Worker discovery

- [ ] 7.1 Add `POST /api/v1/{identifier}/broker`, accepting only the session token of the issue's current run, and keep the URL and the viewer token on `RunningEntry` in memory. Register the token for masking. Verify with server tests: the run's own token, another issue's token (`403`), no running worker (`404`), and a log capture showing the token masked.
- [ ] 7.2 Add `broker.http_url`, or `broker: null`, to `/api/v1/state` and `/api/v1/{identifier}`, and add `GET /api/v1/{identifier}/broker` with operator scope. Verify with handler tests that the state responses never contain the token, and that the read endpoint refuses a session token.
- [ ] 7.3 In the broker, report `{http_url, viewer_token}` after the HTTP listener binds, with backoff capped at 30 s, and never from a credential check or without the Sortie variables (design D8). Verify with broker tests against a fake Sortie: the report arrives after bind, retries after two failures, is absent for a credential check, and a Sortie that is down leaves the relay working.

## 8. Plan graph API

- [ ] 8.1 Add the plan-control story fields to `GET /api/v1/plan/graph`: review gate, approver, satisfaction, merge commit, pull request URL, wait reasons, and proposed supersede. Use `null`, never omission, when a field does not apply. Verify with handler tests for each `sortie/plan-graph-api` scenario, and a plan-control-off test that shows the fields as `null`.

## 9. Documentation

- [ ] 9.1 Update the fork's docs:
  - the workflow reference: the four states, `gate`, `on_fail`, and the auto-merge gate;
  - the agent-to-orchestrator protocol: `.sortie/evidence.json`;
  - the HTTP API reference: pull-back, cancel, the broker routes, and the new state and graph fields;
  - the Huly adapter notes: the approval attributes and state checks;
  - the smolvm environment guide: the branch-protection constraint;
  - `CHANGELOG.md`.

  Verify that every new setting and endpoint named in the specs appears in the reference, and that the docs link check (`lychee.toml`) passes.

## 10. End-to-end check

- [ ] 10.1 With `scripts/dev.sh` in the plan workbench, a local Huly, the mock agent, and a fake forge, walk the loop and record each step's command and result in `verification.md`:
  1. sync a version 2 graph of 3 stories (a3 blocks b1, plus a held c1);
  2. see a3 released and dispatched;
  3. pull back c1 before its release reaches a poll;
  4. merge a3's pull request and see b1 dispatched;
  5. cancel b1 while it runs, and see its process exit and the issue in `Canceled`;
  6. read the broker URL from `/api/v1/state` and attach to a3's broker with the token from `/api/v1/{identifier}/broker`.
