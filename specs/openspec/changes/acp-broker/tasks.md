All work is in `acp-broker/`, starting from the spike. Every task ends with `go test -race ./acp-broker/...` and the lint target passing.

## 1. Core loop hardening

- [x] 1.1 Split the spike into the D1 layout (core loop, `transport`, `registry`, `sortieclient`, `cmd`) without changing behavior. Verify that the existing eight spike tests pass unchanged.
- [x] 1.2 Add sequence numbers and timestamps to events, plus the bounded replay buffer (count and bytes). Verify with unit tests: event order, eviction at each limit, and a late viewer receiving state, then the buffer, then live events.
- [x] 1.3 Add the handback grace when the last viewer leaves, configurable with a 60-second default. Verify with a test: takeover, then disconnect, then automatic handback after the grace; and reattach within the grace keeps the floor.
- [x] 1.4 Add tests for every relay requirement the spike did not cover: transparent pass-through of unhandled messages, exit code propagation, and closing the agent's input when the driver closes. Verify with a fake agent process.

## 2. Steering

- [x] 2.1 Keep native and fallback steering, and add the "one steer at a time" checks. Verify with tests for native steering (floor unchanged), fallback steering (cancel, same-session prompt, automatic handback), steering while idle (driver prompt queued), and each rejection.
- [x] 2.2 Steer an idle session the same way for every agent: skip native steering when no driver turn runs and run a same-session steer turn instead; on a `promptRequired` answer, resend once if a driver turn is running, else run a steer turn. Verify with tests for a native steer while idle (hold `steer`, then release), `promptRequired` with a new driver turn (resent natively), and `promptRequired` while idle (steer turn). Update the operator guide's `steer` row and the broker notes, and live-check an idle steer with Claude.
- [ ] 2.3 Make steering a queue of log entries and interrupting a separate command (design D7, user decision 2026-10-11). Changes:
  - steers are always accepted and delivered together, injected natively into any running turn or run as a steer turn when idle or after the running turn ends;
  - the driver's answer is withheld until its steers land, with a `steer` hold;
  - `promptRequired` requeues the steer and runs it as a turn, with no resend;
  - no steer ever cancels a turn;
  - `interrupt` (aliases `takeover`, `cancel`) always gives humans the floor;
  - steers under a human floor keep the floor;
  - `state` reports queued steers.
  Verify with loop tests for each new scenario in the steering and session-relay specs, a check that each test fails when its rule is removed, the operator guide and notes updated, and live checks with OpenCode (steer queued until turn end) and Claude.

## 3. Sortie integration

- [x] 3.1 Implement `sortieclient` with hold, release, and escalate, authenticated with `SORTIE_SESSION_TOKEN`. Use desired-state reconciliation with capped backoff. Verify against an `httptest` server: the bearer header, retries, the final release on exit, and that the loop never blocks while the server hangs.
- [x] 3.2 Read `SORTIE_API_URL`, `SORTIE_ISSUE_IDENTIFIER`, `SORTIE_SESSION_PURPOSE`, and `SORTIE_SESSION_TOKEN`, and skip all Sortie calls when any is absent. Remove `SORTIE_SESSION_TOKEN` from the agent's launch environment. Verify with tests for a broker under Sortie, a standalone broker, and an agent environment without the token but with the other variables.
- [x] 3.3 Set the desired hold on takeover, fallback steering, and waiting permission requests; clear it on handback and on resolution. Verify with loop tests that assert the desired-state sequence.

## 4. Permissions and questions

- [x] 4.1 Add the escalation timer (default 30 seconds, immediate with no viewer attached) and the answer timeout (default 10 minutes, 0 means no limit), and keep the spike's routing to viewers. Verify with tests: answered by a viewer, escalated, forwarded to the driver on timeout, and the hold released on each path.
- [x] 4.2 Classify questions (no allow-kind option) and escalate them with kind `question` and the option names. Verify with a test using a two-option question.
- [x] 4.3 Answer waiting requests as `cancelled` on any cancel of the asking turn. Verify with tests for takeover, a viewer cancel, and a driver cancel.

## 5. Viewer transport

- [x] 5.1 Create the socket with mode `0600` in a directory with mode `0700`, and serve the command set with validated errors. Verify with tests for permissions and for each rejected command.
- [x] 5.2 Add the HTTP listener: `GET /events` (Server-Sent Events, heartbeat, `Last-Event-ID`), `POST /commands`, `GET /state`, bearer auth, and refusal to start without a viewer token. Verify with `httptest` tests for auth (including rejection of a token in the URL), resume from `Last-Event-ID`, the dropped-events marker, and a slow client being disconnected while the relay keeps its speed.
- [x] 5.3 Add `POST /login` and `POST /logout` with an in-memory session cookie (`HttpOnly`, `SameSite=Strict`, `Secure` under an HTTPS public URL, 12-hour default lifetime). Verify with tests: login then `EventSource`-style access with the cookie only, a wrong token setting no cookie, logout, expiry, and a cookie from another broker process getting `401`.
- [x] 5.4 Update `attach` to use the replay (print history, then live events) and add `-http` to `ls` output. Verify by hand with a fake agent and record the output in the change notes.

## 6. Session registry

- [x] 6.1 Write, update, and remove registry records, keyed by the sanitized `SORTIE_ISSUE_IDENTIFIER` or the working directory. Verify with tests for the record contents, two brokers for one key, and stale-record cleanup.
- [x] 6.2 Make credential-check brokers pass-through only. Verify with a test that no record, socket, or listener appears.
- [x] 6.3 Move `ls`, `attach -follow`, and `send` to the registry. Verify by following a key across two broker processes in a test.

## 7. Documentation and end-to-end checks

- [x] 7.1 Write the broker operator guide: flags, tokens, the agent command prefix, and agent isolation examples for OpenCode, Pi, and Claude. Update `acp-broker/docs/notes.md` with a deferred Pi parity section. Verify that the guide's example command runs as written.
- [x] 7.2 Run the live harness against Sortie with change `sortie-session-control` deployed, using OpenCode (primary) and Claude. Check takeover and handback with Sortie showing the run as held, steering on both agents, a permission request escalated to a webhook destination, and an HTTP viewer resuming with `Last-Event-ID`. Record the commands and outcomes in the change notes.
