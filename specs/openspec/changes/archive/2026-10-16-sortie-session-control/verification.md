# Verification: sortie-session-control

## Task 5.1: end-to-end check

Run on 2026-10-11 against the Sortie fork, branch `feat/session-control` at `bcb732b1`.
The harness lives in `/tmp/opencode/scs-e2e`: the binary built from that commit, the file tracker, the mock agent, and a small webhook receiver.

### Setup

`WORKFLOW.md`, abridged to the settings that matter:

```yaml
tracker: {kind: file, active_states: [To Do], handoff_state: Review, terminal_states: [Done]}
polling: {interval_ms: 1000}
agent:
  kind: mock
  max_turns: 1
  turn_timeout_ms: 60000
  stall_timeout_ms: 4000      # the hold below lasts 9 s
mock:
  turn_delay_ms: 12000        # the turn is silent for 12 s
  events_per_turn: 1
dispatch:
  rules:
    - name: implement
      match: {identifier: ["E2E-*"]}
notifications:
  - kind: webhook
    url: http://127.0.0.1:7693/hook
    events: [session.escalated]
server:
  port: 7692
  control_token: $SORTIE_E2E_CONTROL_TOKEN
```

`webhook.py` appends each POST body to `hooks.log`. `run.sh` starts the receiver and Sortie (recording both PIDs), waits for `E2E-1` to run, and then does the following:
- holds the run, checks state and metrics, and escalates twice
- releases the run and waits for the run history row
- prints the log records and the webhook body, and stops both processes by PID

### Commands

```sh
go -C ~/dev/sortie build -o /tmp/opencode/scs-e2e/sortie ./cmd/sortie
cd /tmp/opencode/scs-e2e
./run.sh       # held run
./control.sh   # the same workflow with no hold
```

### Output of run.sh

```text
[20:56:35.761] webhook pid 159451, sortie pid 159452
[20:56:35.910] E2E-1 running
[20:56:35.911] POST hold without a token:
  HTTP 401
[20:56:35.919] POST hold with the control token:
{"issue_identifier":"E2E-1","issue_id":"1","held":true,"hold_reason":"human takeover","holder":"e2e","held_since":"2026-10-11T20:56:35.923666523Z","held_total_ms":0}

  HTTP 200
[20:56:35.925] holding for 9s with stall_timeout_ms=4000 and a silent 12s mock turn
  state: {'held': True, 'hold_reason': 'human takeover', 'holder': 'e2e', 'held_since': '2026-10-11T20:56:35.923666523Z', 'held_total_ms': 3010, 'last_event_at': '2026-10-11T20:56:35.777482715Z'}
  state: {'held': True, 'hold_reason': 'human takeover', 'holder': 'e2e', 'held_since': '2026-10-11T20:56:35.923666523Z', 'held_total_ms': 6028, 'last_event_at': '2026-10-11T20:56:35.777482715Z'}
  state: {'held': True, 'hold_reason': 'human takeover', 'holder': 'e2e', 'held_since': '2026-10-11T20:56:35.923666523Z', 'held_total_ms': 9046, 'last_event_at': '2026-10-11T20:56:35.777482715Z'}
  metric: sortie_runs_held 1
[20:56:44.990] POST escalate with the control token:
{"issue_identifier":"E2E-1","event_type":"session.escalated","accepted":true}

  HTTP 202
[20:56:44.998] POST escalate again within the window:
{"error":{"code":"rate_limited","message":"issue \"E2E-1\" was escalated less than 1m0s ago"}}

  HTTP 429
[20:56:45.005] POST release:
{"issue_identifier":"E2E-1","issue_id":"1","held":false,"hold_reason":"","holder":"","held_since":null,"held_total_ms":9086}

  HTTP 200
[20:56:47.838] run_history:
identifier|attempt|rule_name|status|error|turns_completed|held_ms|started_at|completed_at
E2E-1|1|implement|succeeded||1|9086|2026-10-11T20:56:35Z|2026-10-11T20:56:47Z
  metric: sortie_hold_seconds_total{rule="implement"} 9.086971889
  metric: sortie_runs_held 0
[20:56:47.848] log records:
   14:56:35.917 control request rejected {'status': 401}
   14:56:35.923 run held {'hold_reason': 'human takeover', 'holder': 'e2e'}
   14:56:44.996 session escalated {'kind': 'question'}
   14:56:45.010 run released {'held_ms': 9086, 'held_total_ms': 9086}
   14:56:47.783 worker exiting {'exit_kind': 'normal'}
[20:56:48.866] webhook received:
  {"notification_id":"GIUQPDRPSN6LY6H4KEULRRFFRU","timestamp":"2026-10-11T20:56:44Z","source":"p1","issue_id":"1","identifier":"E2E-1","dispatch_id":"K66VJ63WKFV3FL7SMQG54SQFEH","session_id":"","attempt":null,"agent":"mock","severity":"warning","title":"E2E-1: session.escalated","body":"The running session of E2E-1 on rule implement asks for a person (question).\nSession: https://viewer.example/E2E-1","event_type":"session.escalated","agent_text":"Which database should I target?","escalation":{"kind":"question","rule":"implement","url":"https://viewer.example/E2E-1"}}
[20:56:50.873] stopped
```

### Output of control.sh (negative control)

```text
   14:57:01.321 stall detected, cancelling worker {'elapsed_ms': 4006, 'stall_timeout_ms': 4000}
identifier|status|error|held_ms
E2E-1|cancelled|agent turn 1: context canceled|0
```

### Result

- **Hold beyond the stall timeout.** The run was held for 9.1 s against `stall_timeout_ms: 4000`. The agent was silent the whole time: `last_event_at` never moved. Sortie did not stop the run. The state showed `held`, the reason, the holder, and `held_since`, and `sortie_runs_held` read 1.
- **Release and normal finish.** Release answered 200 with `held_total_ms` 9086. The turn then ended about 2.8 s later, inside the restarted stall window. The worker exited `normal`, and the run history row has status `succeeded`.
- **Held time recorded.** `run_history.held_ms` is 9086, and `sortie_hold_seconds_total{rule="implement"}` is 9.09.
- **Escalation.** The first escalate answered 202, and the webhook received one `session.escalated` payload carrying the issue, the rule, the kind, the URL, and the message as `agent_text`. The second escalate, inside the 60-second window, answered 429, and nothing more was delivered.
- **Authentication.** A hold without a token answered 401 and was logged as `control request rejected`.
- **Negative control.** The same workflow without a hold was stopped by stall detection 4.0 s into the silent turn (`cancelled`, `held_ms` 0). This proves the hold is what kept the first run alive.
