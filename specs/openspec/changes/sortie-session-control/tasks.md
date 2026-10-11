All work is in the Sortie fork (`~/dev/sortie`) on a branch off the current spike base. Run `make help` to find the lint and test targets; every task ends with them passing.

## 1. Agent session context

- [ ] 1.1 Add `SessionEnv` to `domain.StartSessionParams` and to `agentcore.LaunchTarget`. Apply it last in `BindWorkspace` and add it to the settings `SSHOptions` carries. Verify with unit tests: a local `exec.Cmd` gets the values and overrides an inherited variable of the same name, and an SSH launch carries them on standard input, never in its arguments.
- [ ] 1.2 Fill `SessionEnv` in the worker from the run's dispatch ID, rule, chain ID, attempt, workspace, server URL, and purpose. Mark the credential-check launch `credential-check`. Verify with a worker test using the mock adapter that asserts each variable's value against the run history row.
- [ ] 1.3 Check that every adapter's launch path, including `AuxiliaryCommand`, goes through `BindWorkspace` or `SSHOptions`. Verify with one table test per adapter kind that asserts `SORTIE_ISSUE_ID` reaches the launched command.
- [ ] 1.4 Document the variables in the fork's agent adapter contract section and in `docs/workflow-reference.md`, and add a `CHANGELOG.md` entry. Verify that the docs name every variable the tests assert.

## 2. Control API authentication

- [ ] 2.1 Add `server.control_token` with `$VAR` resolution and secret masking, and a startup check that rejects a non-loopback `server.host` without a token. Verify with config tests for a set token, an unset token on loopback, and the error that names the setting.
- [ ] 2.2 Add the auth wrapper and apply it to `POST /api/v1/refresh`. Verify with handler tests: `401` without a token, `401` with a wrong token, `202` with the right token, and no refresh signal on a rejected request.
- [ ] 2.3 Mint a session token per work session in the worker, store it on the running entry, register it for masking, and add it to `SessionEnv`; credential-check launches get none. Verify with worker tests: two dispatches get different tokens, a credential check gets none, and the token is masked in a logged status statement.
- [ ] 2.4 Teach the auth wrapper session tokens: `401` for an unknown or expired token; `403` for the wrong issue or a route other than hold, release, or escalate; and acceptance on the run's own hold, release, and escalate. Verify with handler tests for each case, including a token used after its run ended. Test against stub routes; tasks 3.2 and 4.3 then reuse these tests on the real routes.
- [ ] 2.5 Document the setting, session tokens, the binding rule, and the breaking change for non-loopback deployments. Verify that the docs and `CHANGELOG.md` mention the migration step and `SORTIE_SESSION_TOKEN`.

## 3. Held runs

- [ ] 3.1 Add the hold fields to the running entry. Add hold and release control messages to the event loop, with replies that carry the outcome. Verify with event-loop tests for a running issue, a known issue that is not running (`409`), an unknown issue (`404`), a double hold that keeps its start time, and release of a run that is not held.
- [ ] 3.2 Add `POST /api/v1/{identifier}/hold` and `/release` behind the auth wrapper, wired to the new callbacks. Verify with handler tests for each status code and the response body.
- [ ] 3.3 Make reconciliation skip stall checks for held entries and reset the stall base on release. Verify with reconcile tests: no stop during a hold longer than `stall_timeout_ms`, and a stop no earlier than release plus the timeout.
- [ ] 3.4 Replace the fixed turn deadline with a turn clock the hold can pause. Verify with worker tests for a hold that begins before, during, and exactly at the deadline, and for the extended deadline after release.
- [ ] 3.5 Keep tracker reconciliation and the token ceiling active for held runs. Verify with a reconcile test where a held issue turns terminal and is stopped, with its hold ended.
- [ ] 3.6 End any open hold on worker exit. Add `run_history.held_ms` with a migration and store the total. Verify with an exit test and a migration test.
- [ ] 3.7 Show the held state in `/api/v1/state`, the per-issue detail, and the dashboard. Add the held-runs gauge and the hold-duration counter. Verify with server and metrics tests.
- [ ] 3.8 Document holds in the observability, HTTP server, and persistence sections, and in `CHANGELOG.md`. Verify that every endpoint and field appears in the docs.

## 4. Operator escalation

- [ ] 4.1 Add the `session.escalated` event type to the catalog and its payload. Verify with routing tests: the event is accepted from the orchestrator and reaches only subscribed destinations.
- [ ] 4.2 Add the escalate control message: check for a running worker, apply the 60-second window per issue, mask the message, and route it. Verify with event-loop tests for `202`, `400`, `409`, `429`, masking, and the no-destination log record.
- [ ] 4.3 Add `POST /api/v1/{identifier}/escalate` behind the auth wrapper. Verify with handler tests.
- [ ] 4.4 Document the event in the notifications event catalog in `docs/workflow-reference.md` and in `CHANGELOG.md`. Verify with the docs check that every event in the catalog code is documented, if one exists; otherwise review by hand.

## 5. End-to-end check

- [ ] 5.1 Run Sortie with the file tracker and the mock agent. Hold a run for longer than `stall_timeout_ms`, release it, and confirm that the run finishes normally, that `held_ms` is recorded, and that an escalation reaches a webhook destination. Record the commands and output in the change's verification notes.
