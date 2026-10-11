# Verification: acp-broker

All runs on 2026-10-11 against Sortie's branch `feat/session-control` and the broker as these tasks left it. The automated checks for each task are the tests named in the commit history; this file records the manual checks the tasks ask for.

## Task 5.4: attach replay and `ls` with the HTTP URL

The harness is in `/tmp/opencode/scs-broker`:
- `fake_acp.py` is a minimal ACP agent that streams five chunks per prompt, 0.8 s apart.
- `driver.py` drives one session the way Sortie would: `initialize`, `session/new`, then one prompt.
- `handcheck.sh` starts the driver, and with it the broker (`-key demo -http 127.0.0.1:7711 -viewer-token-file token`). While the turn runs, it calls `ls`, two `curl` requests, and `attach`.

```sh
cd /tmp/opencode/scs-broker && ./handcheck.sh
```

```text
$ acp-broker ls
KEY   PID     ISSUE  RULE  AGENT         SESSION   STARTED   HTTP                   SOCKET
demo  281066  -      -     fake-acp 0.1  ses_fake  15:25:05  http://127.0.0.1:7711  /tmp/opencode/scs-broker/xdg/acp-broker/demo.281066.sock

$ curl -N -H "Last-Event-ID: 3" http://127.0.0.1:7711/events   (bearer token, 0.5 s)
: connected

id: 4
data: {"seq":4,"time":"2026-10-11T21:25:06.990309556Z","type":"update","update":{"sessionId":"ses_fake","update":{"sessionUpdate":"agent_message_chunk","content":{"type":"text","text":"[driver turn] step 3. "}}}}


$ curl http://127.0.0.1:7711/events?access_token=...   (token in the URL)
HTTP 401
$ acp-broker attach -key demo   (2.5 s, joined mid-turn)
[attached] demo.281066.sock

[state] floor=driver driverTurn=active session=ses_fake

--- history ---

[state] floor=driver driverTurn=active session=ses_fake

agent> [driver turn] step 1. [driver turn] step 2. [driver turn] step 3. 
--- live ---

agent> [driver turn] step 4. [driver turn] step 5. 
[state] floor=driver driverTurn=none session=ses_fake

[detached]


driver: prompt 3 -> {"stopReason": "end_turn"}
driver: broker exited 0
$ acp-broker ls   (after the session ended)
KEY  PID  ISSUE  RULE  AGENT  SESSION  STARTED  HTTP  SOCKET
demo.log
```

Result:
- **`ls`** shows the session with its agent, session ID, and HTTP URL. Once the session ends, the record and socket are gone; only the broker's log remains.
- **`attach`** joined mid-turn. It printed the state, then the history (steps 1 to 3), then live events (steps 4 and 5).
- **HTTP resume.** With `Last-Event-ID: 3`, the stream starts at event 4.
- **Token in the URL.** A token passed as a URL parameter gets `401`.

## Task 7.1: the guide's example command runs as written

```sh
printf '%s\n' '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":1}}' \
  | ./acp-broker -key demo -- opencode acp
```

```text
{"jsonrpc":"2.0","id":1,"result":{"protocolVersion":1,"agentCapabilities":{"loadSession":true,"mcpCapabilities":{"http":true,"sse":true},"promptCapabilities":{"embeddedContext":true,"image":true},"sessionCapabilities":{"close":{},"fork":{},"list":{},"resume":{}}},"authMethods":[{"description":"Run `
exit 0
```

The output is shortened to 300 characters per line. The first line is OpenCode's full `initialize` result, ending in `"agentInfo":{"name":"OpenCode","version":"1.18.29"}`. The broker exited with the agent's code, 0.

## Task 7.2: live harness against Sortie with change sortie-session-control

The harness is in `/tmp/opencode/scs-live`:
- **Sortie** uses the file tracker and the `agent-client-protocol` kind, with this agent command: `acp-broker -http 127.0.0.1:7701 -viewer-token-file token -public-url http://127.0.0.1:7701 -- <agent>`.
- **Notifications:** one webhook entry that lists `session.escalated`, received by `webhook.py` on port 7696.
- **OpenCode** runs as `env XDG_CONFIG_HOME=/tmp/opencode/broker-live/oc-config opencode acp`. That config sets model `anthropic/claude-haiku-5-5` and `bash: ask`.
- **Claude** runs as `claude-agent-acp` 0.89.1, with `disableAllHooks` set in the workspace's `.claude/settings.json` by `hooks.after_create`.
- **The task:** issue `LIVE-1` asks for `sleep 20`, write `progress.txt`, `sleep 20`, append, then write `needs-human-review` to `.sortie/status`.

`viewer.py` is a scripted human that uses only the broker's HTTP transport: a bearer token, Server-Sent Events, and `POST /commands`. It reads Sortie's `/api/v1/state` after each step. It does these things in order:
1. Waits for the work session's registry record.
2. Waits for the webhook escalation that a permission request causes while nobody watches, and checks that Sortie shows the run held.
3. Attaches over HTTP and answers the permission.
4. Drops the stream and resumes with `Last-Event-ID`.
5. Takes over or steers once `progress.txt` exists.

`run.sh AGENT MODE` starts the webhook receiver and Sortie, recording their PIDs. It runs the viewer, prints the run history, and stops both by PID.

```sh
cd /tmp/opencode/scs-live
./run.sh opencode takeover
./run.sh opencode steer
./run.sh claude steer
```

### OpenCode: takeover and handback

```text
    3.0s REGISTRY {"key": "LIVE-1", "pid": 297904, "issue": "LIVE-1", "rule": null, "session_id": null, "http_url": "http://127.0.0.1:7701"}
    9.5s WEBHOOK {"notification_id":"IAYTVFQ33AFCKUY25WP72THIPR","timestamp":"2026-10-11T21:30:12Z","source":"p1","issue_id":"1","identifier":"LIVE-1","dispatch_id":"LZEOBRUHFDRED5F3MJDFZTB5Y5","session_id":"ses_ed320806affev45cpRE7mRfDCJ","attempt":null,"agent":"agent-client-protocol","severity":"warning","title":"LIVE-1: session.escalated","body":"The running session of LIVE-1 asks for a person (permission).\nSe
    9.5s SORTIE while the request waits: {'held': True, 'hold_reason': 'permission request', 'holder': 'acp-broker', 'held_since': '2026-10-11T21:30:12.245768884Z', 'held_total_ms': 357}
    9.5s GET /events Last-Event-ID=None -> 200
    9.5s EVENT id=None {"seq": 0, "time": "2026-10-11T21:30:12.604178141Z", "type": "state", "floor": "driver", "sessionId": "ses_ed320806affev45cpRE7mRfDCJ", "driverTurn": "active", "steering": false}
    9.5s EVENT id=2 {"seq": 2, "time": "2026-10-11T21:30:07.163165147Z", "type": "state", "floor": "driver", "sessionId": "ses_ed320806affev45cpRE7mRfDCJ", "driverTurn": "active", "steering": false}
    9.5s tool_call bash
    9.5s EVENT id=37 {"seq": 37, "time": "2026-10-11T21:30:12.245027801Z", "type": "permission", "id": "0", "request": {"sessionId": "ses_ed320806affev45cpRE7mRfDCJ", "toolCall": {"toolCallId": "toolu_015nvNxHYWdVmdwPg5G9DB9J", "title": "sleep 20", "kind": "execute", "status": "pe
    9.5s POST /commands {"op": "permit", "id": "0", "option": "allow_once"} -> 200 state  floor=driver
    9.5s SORTIE after the answer: {'held': False, 'hold_reason': '', 'holder': '', 'held_since': None, 'held_total_ms': 359}
    9.5s dropping the stream after event 37
   11.5s GET /events Last-Event-ID=37 -> 200
   11.5s RESUMED: first event id=38 permission_resolved (expected id 38)
   11.5s EVENT id=38 {"seq": 38, "time": "2026-10-11T21:30:12.605255059Z", "type": "permission_resolved", "id": "0", "message": "answered by a viewer: once"}
   31.9s tool_call write
   33.8s tool_call bash
   33.8s POST /commands {"op": "takeover"} -> 200 state  floor=human
   33.8s SORTIE after takeover: {'held': True, 'hold_reason': 'takeover', 'holder': 'acp-broker', 'held_since': '2026-10-11T21:30:36.878686791Z', 'held_total_ms': 360}
   33.8s EVENT id=51 {"seq": 51, "time": "2026-10-11T21:30:36.878534361Z", "type": "state", "floor": "human", "sessionId": "ses_ed320806affev45cpRE7mRfDCJ", "driverTurn": "active", "steering": false}
   34.1s EVENT id=54 {"seq": 54, "time": "2026-10-11T21:30:37.20924748Z", "type": "state", "floor": "human", "sessionId": "ses_ed320806affev45cpRE7mRfDCJ", "driverTurn": "held", "steering": false}
   34.1s POST /commands {"op": "prompt", "text": "Human here, interrupting. Before anything else, create the file human.txt containing the line 'human was here'. Then reply 'done' and stop; do not continue the original steps in this reply."} -> 200 state  floor=human
   35.3s tool_call write
   36.6s EVENT id=60 {"seq": 60, "time": "2026-10-11T21:30:39.690115565Z", "type": "result", "op": "prompt", "result": {"stopReason": "end_turn", "usage": {"inputTokens": 2, "outputTokens": 3, "totalTokens": 15865, "cachedReadTokens": 15741, "cachedWriteTokens": 119}, "_meta": {}}
   36.6s POST /commands {"op": "handback"} -> 200 state  floor=driver
   36.6s SORTIE after handback: {'held': False, 'hold_reason': '', 'holder': '', 'held_since': None, 'held_total_ms': 3171}
   36.6s EVENT id=61 {"seq": 61, "time": "2026-10-11T21:30:39.690813773Z", "type": "state", "floor": "driver", "sessionId": "ses_ed320806affev45cpRE7mRfDCJ", "driverTurn": "none", "steering": false}
   36.6s stream ended
   36.6s human.txt exists: True
viewer exit 0
identifier|rule_name|status|turns_completed|held_ms
LIVE-1||succeeded|1|3171
step 1 done
human was here
```

### OpenCode: steering (fallback, a same-session turn)

The `permission_resolved` lines are left out.

```text
    3.0s REGISTRY {"key": "LIVE-1", "pid": 300360, "issue": "LIVE-1", "rule": null, "session_id": null, "http_url": "http://127.0.0.1:7701"}
   10.5s WEBHOOK {"notification_id":"MS2P5TH53O557K25RML57D7GHV","timestamp":"2026-10-11T21:30:59Z","source":"p1","issue_id":"1","identifier":"LIVE-1","dispatch_id":"AXEZ7TZMWP3T3SJGNFHGXCU3AH","session_id":"ses_ed31fcab5ffeVvQtPkQpvpHweT","attempt":null,"agent":"agent-client-protocol","severity":"warning","title":"LIVE-1: session.escalated","body":"The running session of LIVE-1 asks for a person (permission).\nSe
   10.5s SORTIE while the request waits: {'held': True, 'hold_reason': 'permission request', 'holder': 'acp-broker', 'held_since': '2026-10-11T21:30:59.701109343Z', 'held_total_ms': 401}
   10.5s GET /events Last-Event-ID=None -> 200
   10.5s EVENT id=None {"seq": 0, "time": "2026-10-11T21:31:00.10300527Z", "type": "state", "floor": "driver", "sessionId": "ses_ed31fcab5ffeVvQtPkQpvpHweT", "driverTurn": "active", "steering": false}
   10.5s EVENT id=2 {"seq": 2, "time": "2026-10-11T21:30:53.691061607Z", "type": "state", "floor": "driver", "sessionId": "ses_ed31fcab5ffeVvQtPkQpvpHweT", "driverTurn": "active", "steering": false}
   10.5s tool_call bash
   10.5s EVENT id=45 {"seq": 45, "time": "2026-10-11T21:30:59.700503864Z", "type": "permission", "id": "0", "request": {"sessionId": "ses_ed31fcab5ffeVvQtPkQpvpHweT", "toolCall": {"toolCallId": "toolu_01VRBHX856WT3QHdPbKbDyWv", "title": "sleep 20", "kind": "execute", "status": "pe
   10.5s POST /commands {"op": "permit", "id": "0", "option": "allow_once"} -> 200 state  floor=driver
   10.5s SORTIE after the answer: {'held': False, 'hold_reason': '', 'holder': '', 'held_since': None, 'held_total_ms': 403}
   10.5s dropping the stream after event 45
   12.5s GET /events Last-Event-ID=45 -> 200
   12.5s RESUMED: first event id=46 permission_resolved (expected id 46)
   32.2s tool_call write
   34.0s tool_call bash
   34.0s POST /commands {"op": "steer", "text": "Human here, steering: also create the file human.txt containing the line 'human was here', then carry on with the remaining original steps."} -> 200 state  floor=human
   34.0s SORTIE after steer: {'held': True, 'hold_reason': 'steer', 'holder': 'acp-broker', 'held_since': '2026-10-11T21:31:23.622205131Z', 'held_total_ms': 403}
   34.0s EVENT id=58 {"seq": 58, "time": "2026-10-11T21:31:23.622059058Z", "type": "state", "floor": "human", "sessionId": "ses_ed31fcab5ffeVvQtPkQpvpHweT", "driverTurn": "active", "steering": false}
   34.4s EVENT id=61 {"seq": 61, "time": "2026-10-11T21:31:23.953018508Z", "type": "state", "floor": "human", "sessionId": "ses_ed31fcab5ffeVvQtPkQpvpHweT", "driverTurn": "held", "steering": false}
   38.0s tool_call write
   39.4s tool_call bash
   39.5s EVENT id=92 {"seq": 92, "time": "2026-10-11T21:31:29.078963322Z", "type": "permission", "id": "1", "request": {"sessionId": "ses_ed31fcab5ffeVvQtPkQpvpHweT", "toolCall": {"toolCallId": "toolu_01MYQEAv9QPuNTJ4ejER278w", "title": "sleep 20", "kind": "execute", "status": "pe
   39.5s POST /commands {"op": "permit", "id": "1", "option": "allow_once"} -> 200 state  floor=human
   61.0s tool_call bash
   61.3s EVENT id=101 {"seq": 101, "time": "2026-10-11T21:31:50.847103721Z", "type": "permission", "id": "2", "request": {"sessionId": "ses_ed31fcab5ffeVvQtPkQpvpHweT", "toolCall": {"toolCallId": "toolu_01F4XBLoEZVzwGy5ZqVpyPo1", "title": "printf '%s\\n' 'step 3 done' >> progress.t
   61.3s POST /commands {"op": "permit", "id": "2", "option": "allow_once"} -> 200 state  floor=human
   62.2s tool_call bash
   62.5s EVENT id=110 {"seq": 110, "time": "2026-10-11T21:31:52.114002459Z", "type": "permission", "id": "3", "request": {"sessionId": "ses_ed31fcab5ffeVvQtPkQpvpHweT", "toolCall": {"toolCallId": "toolu_01JwxbT17fM2bUJGJc5ZwKnf", "title": "mkdir -p .sortie && printf '%s\\n' 'needs-
   62.5s POST /commands {"op": "permit", "id": "3", "option": "allow_once"} -> 200 state  floor=human
   66.3s EVENT id=161 {"seq": 161, "time": "2026-10-11T21:31:55.886566126Z", "type": "result", "op": "steer-turn", "result": {"stopReason": "end_turn", "usage": {"inputTokens": 2, "outputTokens": 173, "totalTokens": 16594, "cachedReadTokens": 16256, "cachedWriteTokens": 163}, "_met
   66.3s SORTIE after the steer's outcome: {'held': False, 'hold_reason': '', 'holder': '', 'held_since': None, 'held_total_ms': 32667}
   66.3s EVENT id=162 {"seq": 162, "time": "2026-10-11T21:31:55.886613244Z", "type": "state", "floor": "driver", "sessionId": "ses_ed31fcab5ffeVvQtPkQpvpHweT", "driverTurn": "none", "steering": false}
   66.3s stream ended
   66.3s human.txt exists: True
viewer exit 0
identifier|rule_name|status|turns_completed|held_ms
LIVE-1||succeeded|1|32667
step 1 done
step 3 done
human was here
```

### Claude: steering (native `_session/steering`)

The `permission_resolved` lines are left out.

```text
    3.0s REGISTRY {"key": "LIVE-1", "pid": 304908, "issue": "LIVE-1", "rule": null, "session_id": null, "http_url": "http://127.0.0.1:7701"}
   27.0s WEBHOOK {"notification_id":"LFFOT5JX5P757V7EWHYRYBRYX4","timestamp":"2026-10-11T21:32:33Z","source":"p1","issue_id":"1","identifier":"LIVE-1","dispatch_id":"NJCRJTWQ4TN3ESJ3CP55MTAQHD","session_id":"367d4b87-e8b2-43ac-9349-1db8b052c42c","attempt":null,"agent":"agent-client-protocol","severity":"warning","title":"LIVE-1: session.escalated","body":"The running session of LIVE-1 asks for a person (permission
   27.0s SORTIE while the request waits: {'held': True, 'hold_reason': 'permission request', 'holder': 'acp-broker', 'held_since': '2026-10-11T21:32:33.650782559Z', 'held_total_ms': 463}
   27.0s GET /events Last-Event-ID=None -> 200
   27.0s EVENT id=None {"seq": 0, "time": "2026-10-11T21:32:34.114881352Z", "type": "state", "floor": "driver", "sessionId": "367d4b87-e8b2-43ac-9349-1db8b052c42c", "driverTurn": "active", "steering": true}
   27.0s EVENT id=1 {"seq": 1, "time": "2026-10-11T21:32:10.326849305Z", "type": "state", "floor": "driver", "sessionId": "367d4b87-e8b2-43ac-9349-1db8b052c42c", "driverTurn": "active", "steering": true}
   27.0s tool_call Terminal
   27.0s tool_call Preparing file…
   27.0s EVENT id=22 {"seq": 22, "time": "2026-10-11T21:32:33.650045602Z", "type": "permission", "id": "0", "request": {"toolCall": {"toolCallId": "toolu_014u712nCotXGwkX5YSNjyne", "name": "Write", "status": "pending", "rawInput": {"file_path": "/tmp/opencode/scs-live/ws/LIVE-1/pr
   27.0s POST /commands {"op": "permit", "id": "0", "option": "allow_once"} -> 200 state  floor=driver
   27.0s SORTIE after the answer: {'held': False, 'hold_reason': '', 'holder': '', 'held_since': None, 'held_total_ms': 465}
   27.0s dropping the stream after event 22
   29.0s GET /events Last-Event-ID=22 -> 200
   29.0s RESUMED: first event id=23 update (expected id 23)
   29.0s tool_call Terminal
   29.0s POST /commands {"op": "steer", "text": "Human here, steering: also create the file human.txt containing the line 'human was here', then carry on with the remaining original steps."} -> 200 state  floor=driver
   29.0s SORTIE after steer: {'held': False, 'hold_reason': '', 'holder': '', 'held_since': None, 'held_total_ms': 465}
   29.0s EVENT id=35 {"seq": 35, "time": "2026-10-11T21:32:36.119940492Z", "type": "result", "op": "steer", "result": {"outcome": "injected"}}
   29.0s SORTIE after the steer's outcome: {'held': False, 'hold_reason': '', 'holder': '', 'held_since': None, 'held_total_ms': 465}
   33.3s tool_call Preparing file…
   33.5s EVENT id=50 {"seq": 50, "time": "2026-10-11T21:32:40.618047369Z", "type": "permission", "id": "1", "request": {"toolCall": {"toolCallId": "toolu_01M7rNhxaPPus4HHZAFrE4z1", "name": "Write", "status": "pending", "rawInput": {"file_path": "/tmp/opencode/scs-live/ws/LIVE-1/hu
   33.5s POST /commands {"op": "permit", "id": "1", "option": "allow_once"} -> 200 state  floor=driver
   34.3s EVENT id=68 {"seq": 68, "time": "2026-10-11T21:32:41.365348134Z", "type": "state", "floor": "driver", "sessionId": "367d4b87-e8b2-43ac-9349-1db8b052c42c", "driverTurn": "none", "steering": true}
   34.3s stream ended
   34.3s human.txt exists: True
viewer exit 0
identifier|rule_name|status|turns_completed|held_ms
LIVE-1||succeeded|1|466
step 1 done
human was here
```

### Sortie's own records of the three runs

These are the `run held`, `run released`, and `session escalated` records from Sortie's logs:

```text
15:30:12.245 run held {'hold_reason': 'permission request', 'holder': 'acp-broker'}
15:30:12.246 session escalated {'kind': 'permission'}
15:30:12.605 run released {'held_ms': 359}
15:30:36.878 run held {'hold_reason': 'takeover', 'holder': 'acp-broker'}
15:30:39.691 run released {'held_ms': 2812}
15:30:59.701 run held {'hold_reason': 'permission request', 'holder': 'acp-broker'}
15:30:59.701 session escalated {'kind': 'permission'}
15:31:00.104 run released {'held_ms': 403}
15:31:23.622 run held {'hold_reason': 'steer', 'holder': 'acp-broker'}
15:31:55.886 run released {'held_ms': 32264}
15:32:33.650 run held {'hold_reason': 'permission request', 'holder': 'acp-broker'}
15:32:33.651 session escalated {'kind': 'permission'}
15:32:34.116 run released {'held_ms': 465}
15:32:40.618 run held {'hold_reason': 'permission request', 'holder': 'acp-broker'}
15:32:40.618 run released {'held_ms': 0}
```

The webhook body Sortie delivered for the Claude run's escalation:

```json
{"notification_id":"LFFOT5JX5P757V7EWHYRYBRYX4","timestamp":"2026-10-11T21:32:33Z","source":"p1","issue_id":"1","identifier":"LIVE-1","dispatch_id":"NJCRJTWQ4TN3ESJ3CP55MTAQHD","session_id":"367d4b87-e8b2-43ac-9349-1db8b052c42c","attempt":null,"agent":"agent-client-protocol","severity":"warning","title":"LIVE-1: session.escalated","body":"The running session of LIVE-1 asks for a person (permission).\nSession: http://127.0.0.1:7701","event_type":"session.escalated","agent_text":"Write progress.txt","escalation":{"kind":"permission","rule":"","url":"http://127.0.0.1:7701"}}
```

### Result

| Check | OpenCode | Claude |
| --- | --- | --- |
| A permission request with no viewer is escalated to the webhook at once, and Sortie holds the run (`permission request`, holder `acp-broker`) | yes | yes |
| A viewer's answer reaches the agent, and Sortie releases the hold | yes | yes |
| An HTTP viewer that reconnects with `Last-Event-ID: N` resumes at event N+1 | yes (37 to 38, 45 to 46) | yes (22 to 23) |
| Takeover: Sortie shows the run held (`takeover`); a human prompt runs in the same session (`human.txt` written); handback releases the hold; `held_ms` recorded (3171) | yes | not run |
| Steering | fallback: Sortie held (`steer`) during the steer turn, then automatic handback and release; `held_ms` 32667 | native: outcome `injected`, the floor stays with the driver, no hold |
| The run finishes normally after the human's part | `succeeded` | `succeeded` |

Notes:
- **Takeover ends the run early.** With `max_turns: 1`, Sortie ends the run when the held driver turn is answered with `end_turn` on handback. A takeover therefore ends the run unless the workflow allows more turns. This is expected: a handed-back turn looks like an ordinary completed turn to Sortie.
- **Claude stopped after the steer.** It wrote `human.txt` and then ended its turn without finishing the remaining original steps. That is the agent's own choice; the broker delivered the steer as an injection.
- **Brief holds with a viewer attached.** In the Claude run, the second permission request was answered by the attached viewer within milliseconds, so it produced a hold of 0 ms. The broker holds the run whenever a request waits, viewer or not.

## Task 2.2: steer an idle session the same way for every agent

Code: `acp-broker`.

### Tests

New tests in `acp-broker/internal/broker/steering_test.go`:
- `TestSteer_NativeWhileIdleRunsASteerTurn`
- `TestSteer_PromptRequiredResendsIntoANewDriverTurn`
- `TestSteer_PromptRequiredWhileIdleRunsASteerTurn`
- `TestSteer_SecondPromptRequiredCancelsAndRunsASteerTurn`
- `TestSteer_PromptRequiredAfterATakeoverIsDropped`

New tests in `acp-broker/internal/broker/hold_test.go`:
- `TestHold_NativeSteerWhileIdleHoldsUntilItsTurnEnds`
- `TestHold_PromptRequiredWhileIdleHoldsUntilItsTurnEnds`

```
$ set -o pipefail; go test -race -count=1 ./acp-broker/...
ok  	github.com/briancappello/agentic-orchestration/acp-broker/internal/broker	3.256s
ok  	github.com/briancappello/agentic-orchestration/acp-broker/internal/registry	2.026s
ok  	github.com/briancappello/agentic-orchestration/acp-broker/internal/sortieclient	1.226s
ok  	github.com/briancappello/agentic-orchestration/acp-broker/internal/transport	3.758s
ok  	github.com/briancappello/agentic-orchestration/acp-broker/cmd/acp-broker	11.735s
$ golangci-lint run ./acp-broker/...
0 issues.
```

Each part of the fix was broken on purpose, and the tests were run again:

| Break | Tests that failed |
| --- | --- |
| Send a native steer even when idle | `NativeWhileIdleRunsASteerTurn`, `Hold_NativeSteerWhileIdle…` |
| Treat `promptRequired` as final | all five `PromptRequired…` tests |
| Resend without a limit | `SecondPromptRequiredCancelsAndRunsASteerTurn` |
| No takeover guard | `PromptRequiredAfterATakeoverIsDropped` |

### Live check with Claude

Harness: `/tmp/opencode/scs-live`, with the broker built from these tasks. It adds the `idle` mode:
- `run.sh claude idle` uses `max_turns: 2` and an issue that finishes only on the second turn. Turn 1 creates `progress.txt`. Turn 2 appends to it and writes `needs-human-review`.
- `viewer.py` attaches at once. It steers on the first `driverTurn: none` state after a driver turn was active.

```
cd /tmp/opencode/scs-live && ./run.sh claude idle > run-claude-idle.out 2>&1
```

**Sortie leaves no idle gap by itself.** The first attempt steered when turn 1 ended. Sortie's turn-2 prompt reached the broker 0.5 ms after the `none` state (seq 24 at `22:15:45.819235`, seq 25 `active` at `.819736`). The steer therefore went natively into turn 2 and came back `injected`, as the spec requires for a running turn. At the end of the run, the driver closed its input 3 ms after the last turn ended. Under Sortie, a session is idle only for milliseconds, so the `promptRequired` race is the more likely case there. An idle session matters most for a broker without Sortie, or for a slower driver. Logs: `*-claude-idle-race.*`.

**A gap made with `SIGSTOP`.** To get a real idle window with real components, the viewer pauses Sortie by its recorded PID (`kill -STOP`), steers, and resumes it (`kill -CONT`). It pauses once turn 1's permission request is answered and Sortie has confirmed the release. Turn 1 then ends while Sortie cannot send turn 2.

A first try paused Sortie before it confirmed the release, while the hold call for the permission request was still in flight. That call landed late and kept its reason. The release and the `steer` hold then merged into "still held", so Sortie showed `permission request` for the steer. This follows the documented rule that a held run keeps its first reason; the cause was the pause, not the broker. Logs: `*-claude-idle-early-stop.*`.

The clean run (`viewer-claude-idle.log`, trimmed):

```
  4.7s POST /commands {"op": "permit", "id": "0", "option": "allow_once"} -> 200 state  floor=driver
  4.7s SORTIE after the answer: {'held': False, ...}
  4.7s SIGSTOP sortie 484180 after turn 1's request was answered and released
  5.3s EVENT id=23 {"type": "state", "floor": "driver", "driverTurn": "none", "steering": true}
  5.3s POST /commands {"op": "steer", "text": "Human here, steering while you are idle: create the file human.txt ..."} -> 200 state  floor=human
  5.3s SIGCONT sortie 484180
  5.5s SORTIE after the idle steer: {'held': True, 'hold_reason': 'steer', 'holder': 'acp-broker', ...}
  5.5s EVENT id=24 {"type": "state", "floor": "human", "driverTurn": "none", "steering": true}
  5.5s EVENT id=25 {"type": "state", "floor": "human", "driverTurn": "none+queued", "steering": true}
  6.3s POST /commands {"op": "permit", "id": "1", "option": "allow_once"} -> 200 state  floor=human
  6.8s EVENT id=39 {"type": "result", "op": "steer-turn", "result": {"stopReason": "end_turn", "usage": {...}}}
  6.8s SORTIE after the steer's outcome: {'held': False, 'held_total_ms': 1453}
  6.8s EVENT id=40 {"type": "state", "floor": "driver", "driverTurn": "active", "steering": true}
 10.3s state after the steer: floor=driver driverTurn=none
identifier|rule_name|status|turns_completed|held_ms
LIVE-1||succeeded|2|1455
turn 1 done
turn 2 done
human was here
```

From the broker log (`broker-claude-idle.log`): no `_session/steering` was sent in this run.

```
16:17:55.555 sortie hold updated held=true reason=steer
16:17:57.000 sortie hold updated held=false reason=steer
```

Sortie logged `run released ... held_ms: 1445` at `16:17:57.000`.

### Result

| Check | Claude |
| --- | --- |
| An idle steer of a native-steering agent runs as a same-session turn, with no `_session/steering` | yes |
| Sortie holds the run with reason `steer` during the steer turn | yes |
| Sortie's next prompt is queued (`none+queued`) and forwarded on handback | yes |
| Automatic handback and release when the steer turn ends; the run finishes `succeeded` | yes (`held_ms` 1455) |
| A steer during a running turn stays native (`injected`) | yes (first attempt) |
| `promptRequired` race (resend, or a steer turn) | unit tests only; not provoked live |
