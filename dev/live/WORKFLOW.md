---
# Sortie under plan control, for the plan workbench's live run.
# dev/live/live.sh renders the ${LIVE_*} placeholders.
tracker:
  kind: huly
  endpoint: ${LIVE_HULY_URL}
  api_key: ${LIVE_HULY_TOKEN}
  project: ${LIVE_HULY_PROJECT}
  active_states: [Todo, In Progress]
  terminal_states: [Done, Canceled]
  in_progress_state: In Progress
  # The state a story waits in while its pull request is reviewed: neither
  # active, terminal, nor the backlog state (dev/huly_project.py adds it).
  handoff_state: In Review
  # Plan control: sync releases approved stories from Backlog to Todo.
  release_state: Todo
  backlog_state: Backlog
  cancel_state: Canceled
  done_state: Done

huly:
  workspace: ${LIVE_HULY_WORKSPACE}
  epic_type: Epic
  story_type: Story

# A story is done when its pull request merges, whoever merges it.
reactions:
  merge_completion:
    provider: gitea
    target_state: Done
    poll_interval_ms: 30000

gitea:
  endpoint: ${LIVE_FORGE_URL}
  api_key: ${LIVE_FORGE_TOKEN}
  project: ${LIVE_FORGE_PROJECT}

server:
  port: ${LIVE_SORTIE_PORT}
  control_token: ${LIVE_SORTIE_TOKEN}

polling:
  interval_ms: 10000

workspace:
  root: ${LIVE_HOME}/workspaces

# The forge work is the hooks' job, so the agent only changes code. Hooks see
# SORTIE_* variables only; live.sh exports the forge coordinates that way.
hooks:
  after_create: |
    git clone -q "$SORTIE_FORGE_REMOTE" .
    echo .sortie/ >> .git/info/exclude
    git config user.name "Sortie ($SORTIE_ISSUE_IDENTIFIER)"
    git config user.email sortie@localhost
  before_run: |
    git fetch -q origin
    branch="sortie/$SORTIE_ISSUE_IDENTIFIER"
    if git rev-parse -q --verify "origin/$branch" >/dev/null; then
      git checkout -q -B "$branch" "origin/$branch"
    else
      git checkout -q -B "$branch" origin/main
    fi
  after_run: |
    python3 "$SORTIE_FORGE_KIT/open_pr.py"
  timeout_ms: 120000

agent:
  kind: agent-client-protocol
  # The broker reports its address to Sortie, so the workbench can watch and
  # steer the worker. The agent gets a configuration home of its own.
  command: acp-broker -http 127.0.0.1:0 -viewer-token-file ${LIVE_HOME}/viewer-token -- env XDG_CONFIG_HOME=${LIVE_HOME}/agent-config opencode acp
  max_turns: 8
  max_concurrent_agents: 2
  turn_timeout_ms: 1200000
  stall_timeout_ms: 600000
---
You are working on story **{{ .issue.identifier }}**: {{ .issue.title }}

{{ .issue.description }}

You are in a git checkout of the `live-lab` repository, on the story's branch.
Change the code to meet the story's acceptance criteria, add or update tests,
and run `python3 -m unittest` until it passes. Keep the change small and
focused on this story. Do not push and do not open a pull request: when you
stop, your changes are committed, pushed, and proposed for review for you.
