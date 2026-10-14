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
