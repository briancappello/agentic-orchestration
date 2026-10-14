# Operator guide: Sortie, the broker, and the workbench on one host

This guide runs the three parts of the planning loop on one machine:

- **Sortie**, which syncs the approved plan into the tracker and dispatches agents.
- **`acp-broker`**, which the workbench starts for each planning session.
- **The plan workbench**, the web app where you plan with an agent and watch the graph.

The tracker here is a local Huly. Any tracker whose Sortie adapter declares the write capabilities works the same way; the workbench only talks to Sortie.

## Prerequisites

- Go, through the toolchain pinned in the Sortie repository.
- `uv`, Node.js 20 or newer with `npm`, and the `openspec` CLI (1.13).
- An ACP agent. The default is OpenCode (`opencode acp`), already signed in to a model provider.
- A local Huly at `http://localhost:8087` (see `docs/huly-adapter-notes.md` in the Sortie repository), with:
  - an account and a login token;
  - a project, for example `HULY`;
  - the task types `Epic` and `Story` in the project's space type (see "Plan task types" in the Huly adapter notes).
- An OpenSpec spec store that uses planning: `openspec/schemas/planning/` and `openspec/plan.yaml`.

Ports used below: Sortie `7678`, workbench `8790`. Each broker picks a free localhost port.

**For development, skip the steps below and run `scripts/dev.sh`.** It creates the token and password files the first time, clones a scratch spec store, builds Sortie and the broker, starts Huly when it is down, and runs Sortie, the backend (`--reload`), and Vite in one terminal. Open the URL it prints; Ctrl-C stops all three. Its settings are at the top of the script.

## 1. Build Sortie and the broker

In the Sortie checkout, on the branch that carries plan sync (`feat/plan-to-tracker-dag`):

```sh
go build -o ~/.local/bin/sortie ./cmd/sortie
go build -o ~/.local/bin/acp-broker ./cmd/acp-broker  # in the acp-broker checkout
```

`~/.local/bin` must be on `PATH`, because the workbench starts `acp-broker` by name. To use another path, set `WORKBENCH_BROKER_COMMAND`.

## 2. Configure and start Sortie

Create a working directory for Sortie, with a `WORKFLOW.md` like this one:

```yaml
---
tracker:
  kind: huly
  endpoint: $SORTIE_HULY_URL
  api_key: $SORTIE_HULY_TOKEN
  project: $SORTIE_HULY_PROJECT
  active_states: [Todo, In Progress]
  terminal_states: [Done, Canceled]
  in_progress_state: In Progress

huly:
  workspace: $SORTIE_HULY_WORKSPACE
  epic_type: Epic
  story_type: Story

server:
  port: 7678
  control_token: $SORTIE_CONTROL_TOKEN

polling:
  interval_ms: 10000

workspace:
  root: /tmp/sortie-plan-workspaces

agent:
  kind: mock
  max_turns: 3
  max_concurrent_agents: 2

mock:
  turn_delay_ms: 20000
---
**{{ .issue.identifier }}**: {{ .issue.title }}
```

The mock agent makes each turn last 20 seconds, so a running agent stays visible on the graph. Replace the agent block with a real agent when you want real work done.

Get a Huly login token, choose a control token, and start Sortie:

```sh
export SORTIE_HULY_URL=http://localhost:8087 SORTIE_HULY_WORKSPACE=sortie SORTIE_HULY_PROJECT=HULY
export SORTIE_HULY_TOKEN=$(curl -s -X POST $SORTIE_HULY_URL/_accounts -H 'Content-Type: application/json' \
  -d '{"method":"login","params":{"email":"you@example.com","password":"..."}}' | jq -r .result.token)
export SORTIE_CONTROL_TOKEN=$(openssl rand -hex 24)
echo "$SORTIE_CONTROL_TOKEN" > ~/.config/plan-workbench-sortie-token   # the workbench reads it below
sortie WORKFLOW.md
```

Check it: `curl -s -H "Authorization: Bearer $SORTIE_CONTROL_TOKEN" localhost:7678/api/v1/plan/capabilities` lists the four write capabilities and `custom_field`.

Sortie dispatches issues in `Todo` or `In Progress`. Synced issues start in `Backlog`, so nothing runs until you move stories to `Todo` in Huly. Sortie still starts only a story whose blockers are done.

## 3. Install and build the workbench

```sh
git clone <plan-workbench repository> && cd plan-workbench
uv sync
(cd frontend && npm ci && npm run build)
```

`uv sync` installs `planlib` and the backend into `.venv`. Started with `uv run`, the workbench puts `.venv/bin` first on `PATH`, so the planning agent it launches can run `planlib validate`.

Choose an operator password and keep its hash:

```sh
uv run workbench hash-password > ~/.config/plan-workbench-password-hash   # type the password at the prompt
```

## 4. Configure and start the workbench

| Variable | Required | Meaning |
|---|---|---|
| `WORKBENCH_STORE` | Yes | Spec store root, the directory that holds `openspec/`. |
| `WORKBENCH_SORTIE_URL` | Yes | Sortie's HTTP address, for example `http://127.0.0.1:7678`. |
| `WORKBENCH_SORTIE_TOKEN` | When Sortie has a control token | Sortie's `server.control_token`. |
| `WORKBENCH_PASSWORD_HASH` | Yes | Output of `workbench hash-password`. |
| `WORKBENCH_SECRET_KEY` | Yes | Random string that signs the session cookie. |
| `WORKBENCH_BROKER_COMMAND` | No | Broker command, default `acp-broker`. |
| `WORKBENCH_AGENT_COMMAND` | No | Agent command, default `opencode acp`. |
| `WORKBENCH_PROMPT_FILE` | No | Planning prompt, default `prompts/planning-session.md`. |
| `WORKBENCH_COOKIE_SECURE` | No | `1` behind HTTPS. |
| `WORKBENCH_RUNTIME_DIR` | No | Where the running session's state, broker token, and logs live. Default: `$XDG_RUNTIME_DIR/plan-workbench/<store>-<hash>`, else under `~/.cache`. |

```sh
export WORKBENCH_STORE=~/dev/agent-platform-specs
export WORKBENCH_SORTIE_URL=http://127.0.0.1:7678
export WORKBENCH_SORTIE_TOKEN=$(cat ~/.config/plan-workbench-sortie-token)
export WORKBENCH_PASSWORD_HASH=$(cat ~/.config/plan-workbench-password-hash)
export WORKBENCH_SECRET_KEY=$(openssl rand -hex 32)
uv run workbench serve --port 8790
```

The tokens stay in this process. The browser holds only the workbench's own cookie.

To work on the workbench itself, add `--reload`: the backend restarts when its Python code changes. Run `npm run dev` in `frontend/` and open `http://localhost:5173` for hot reload of the frontend; Vite forwards `/api` to the backend on port 8790. Keep `WORKBENCH_SECRET_KEY` fixed so a restart keeps you signed in.

## 5. Plan

Open `http://127.0.0.1:8790` and sign in.

1. **Start a planning session** in the chat pane. The workbench starts one broker with the agent in the spec store, and the agent reports what the plan holds. Answer its permission requests in the chat.
2. **Ask for a breakdown**, for example "break the `billing` change into deliverables". The agent writes `breakdown.yaml`, runs `planlib validate`, and fixes what it reports. The graph redraws as the files change. Problems the validator finds appear in the red panel above the graph; select one to select its node.
3. **Point at nodes.** Selecting a node shows its details at the top of the chat and attaches it to your next message. Remove the attachment with its × before sending if you do not mean it.
4. **Approve.** Select the change's epic and choose **Approve breakdown**. Any later edit to its deliverables returns it to draft.
5. **Sync.** Choose **Sync…** in the graph's top bar. The dialog shows how many issues will be created and updated and how many relations added and removed. Nothing reaches the tracker until you apply. A tracker that lacks a needed capability is named, and there is no apply.
6. **Run.** Move the stories to `Todo` in the tracker. Sortie dispatches the unblocked ones; their running badges appear on the graph within a few seconds.

A planning session runs apart from the backend: a detached driver process holds the broker, and the backend finds it again through the runtime directory. So a page reload, another tab, a backend restart, or a `--reload` after a code change reattaches to the same session with its history. Only **End session** in the chat pane stops it.

## Stop

Choose **End session** in the chat pane first: stopping the backend leaves the planning session and its agent running, and the next backend start reattaches to it. Then stop the workbench and Sortie with Ctrl-C.

## Troubleshooting

- **"Sortie unreachable" in the top bar.** Check `WORKBENCH_SORTIE_URL` and the token: `curl -H "Authorization: Bearer $WORKBENCH_SORTIE_TOKEN" $WORKBENCH_SORTIE_URL/api/v1/plan/graph`.
- **The session does not start.** `acp-broker` is not on `PATH`, or the agent command fails. The runtime directory, named in the workbench log, holds `driver.log`, the broker's `<key>.stderr`, and `state.json`, whose `error` field says what failed.
- **A session is still running after the backend stopped.** That is by design. Start the backend and choose **End session**, or send SIGTERM to the `driver_pid` in the runtime directory's `state.json`.
- **`planlib: ... planning schema not found`.** The store has no `openspec/schemas/planning/`.
- **Sync refused with `stale_preview`.** The plan or the tracker changed after the preview. Preview again.
