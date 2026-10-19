---
# Sortie for development, under plan control, with the mock agent.
# scripts/dev.sh renders the ${DEV_*} placeholders.
tracker:
  kind: huly
  endpoint: ${DEV_HULY_URL}
  api_key: ${DEV_HULY_TOKEN}
  project: ${DEV_HULY_PROJECT}
  active_states: [Todo, In Progress]
  terminal_states: [Done, Canceled]
  in_progress_state: In Progress
  # Where a story waits while its pull request is reviewed: neither active,
  # terminal, nor the backlog state (scripts/dev/huly_project.py adds it).
  handoff_state: In Review
  # Plan control: a sync releases approved stories from Backlog to Todo.
  release_state: Todo
  backlog_state: Backlog
  cancel_state: Canceled
  done_state: Done
  # The mock agent changes no code, so Sortie would see no work and withhold
  # the handoff. The after_run hook commits a placeholder instead.
  handoff_evidence: "off"

huly:
  workspace: ${DEV_HULY_WORKSPACE}
  epic_type: Epic
  story_type: Story

# A story is done when its pull request merges in the local Gitea.
reactions:
  merge_completion:
    provider: gitea
    target_state: Done
    poll_interval_ms: 30000

gitea:
  endpoint: ${DEV_FORGE_URL}
  api_key: ${DEV_FORGE_TOKEN}
  project: ${DEV_FORGE_PROJECT}

server:
  port: ${DEV_SORTIE_PORT}
  control_token: ${DEV_SORTIE_TOKEN}

polling:
  interval_ms: 10000

workspace:
  root: ${DEV_HOME}/workspaces

# Hooks see SORTIE_* variables only; dev.sh exports the forge coordinates that way.
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
  kind: mock
  max_turns: 3
  max_concurrent_agents: 2

mock:
  turn_delay_ms: 20000
---
**{{ .issue.identifier }}**: {{ .issue.title }}
