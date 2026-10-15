#!/usr/bin/env bash
# Development mode for the plan workbench, from a blank slate.
#
#   scripts/dev.sh           start (the first run creates an empty environment)
#   scripts/dev.sh --reset   wipe the environment back to empty, then start
#
# The environment is yours alone: an empty spec store (schemas, an empty
# plan.yaml, nothing else), an empty Huly project DEV, and a Sortie that
# watches only DEV with the mock agent. Nothing runs until you plan, sync,
# and move stories to Todo. Work persists across runs until --reset.
#
# Runs Sortie, the backend (reloads on Python edits), and Vite (hot reload)
# in this terminal; Ctrl-C stops them. A planning session keeps running
# across restarts; end it from the chat pane, or with --reset.
#
# Optional settings (environment): SORTIE_SRC (~/dev/sortie), SPECS
# (~/dev/agent-platform-specs, where the planning schemas come from),
# DEV_HOME (~/dev/plan-workbench-worktrees/dev), HULY_PROJECT (DEV),
# HULY_EMAIL / HULY_PASSWORD.
set -euo pipefail

ROOT=$(cd "$(dirname "$0")/.." && pwd)
SORTIE_SRC=${SORTIE_SRC:-$HOME/dev/sortie}
SPECS=${SPECS:-$HOME/dev/agent-platform-specs}
DEV_HOME=${DEV_HOME:-$HOME/dev/plan-workbench-worktrees/dev}
STORE=$DEV_HOME/store
RUN_DIR=$DEV_HOME/sortie
RUNTIME=$DEV_HOME/sessions
HULY_URL=${HULY_URL:-http://localhost:8087}
HULY_WORKSPACE=${HULY_WORKSPACE:-sortie}
HULY_PROJECT=${HULY_PROJECT:-DEV}
HULY_EMAIL=${HULY_EMAIL:-sortie@example.com}
HULY_PASSWORD=${HULY_PASSWORD:-sortie-dev-pass}
TOKEN_FILE=$HOME/.config/plan-workbench-sortie-token
HASH_FILE=$HOME/.config/plan-workbench-password-hash
RESET=
[[ ${1:-} == --reset ]] && RESET=1
[[ $# -gt 0 && -z $RESET ]] && { echo "usage: $0 [--reset]" >&2; exit 2; }

say() { printf '\033[1m==> %s\033[0m\n' "$*"; }
die() { printf 'dev.sh: %s\n' "$*" >&2; exit 1; }

for port in 7678 8790 5173; do
  ss -ltn | grep -q ":$port " && die "port $port is in use; stop whatever runs there first"
done

mkdir -p "$HOME/.config"
[[ -s $TOKEN_FILE ]] || { openssl rand -hex 24 > "$TOKEN_FILE"; chmod 600 "$TOKEN_FILE"; }
if [[ ! -s $HASH_FILE ]]; then
  say "Choose the password you will sign in to the workbench with"
  (cd "$ROOT" && uv run workbench hash-password) > "$HASH_FILE"
  chmod 600 "$HASH_FILE"
fi

if [[ -n $RESET ]]; then
  say "Resetting the dev environment"
  if [[ -f $RUNTIME/state.json ]]; then  # end a planning session that is still running
    pid=$(jq -r '.driver_pid // empty' "$RUNTIME/state.json")
    [[ -n $pid ]] && kill -TERM "$pid" 2>/dev/null && sleep 2 || true
  fi
  rm -rf "$STORE" "$RUN_DIR" "$RUNTIME"
fi

if [[ ! -d $STORE/openspec ]]; then
  say "Creating an empty spec store in $STORE"
  mkdir -p "$STORE/openspec/changes" "$STORE/openspec/specs" "$STORE/openspec/schemas"
  cp -r "$SPECS/openspec/schemas/planning" "$SPECS/openspec/schemas/spec-driven-planned" "$STORE/openspec/schemas/"
  printf 'schema: spec-driven-planned\n' > "$STORE/openspec/config.yaml"
  printf '# The order between changes. Format: openspec/schemas/planning/plan.schema.json\nschema_version: 1\nchanges: []\n' > "$STORE/openspec/plan.yaml"
  (cd "$STORE" && git init -q && git add -A && git -c user.name=dev -c user.email=dev@localhost commit -qm "empty spec store")
fi
mkdir -p "$RUN_DIR"
cp "$ROOT/scripts/dev/WORKFLOW.md" "$RUN_DIR/WORKFLOW.md"

say "Building sortie and acp-broker"
mkdir -p "$HOME/.local/bin"
(cd "$SORTIE_SRC" && go build -o "$HOME/.local/bin/sortie" ./cmd/sortie) && (cd "$BROKER_SRC" && go build -o "$HOME/.local/bin/acp-broker" ./cmd/acp-broker)
export PATH=$HOME/.local/bin:$PATH

say "Installing workbench dependencies"
(cd "$ROOT" && uv sync -q)
[[ -d $ROOT/frontend/node_modules ]] || (cd "$ROOT/frontend" && npm install --silent)

if ! curl -sf -o /dev/null "$HULY_URL/config.json"; then
  say "Starting Huly"
  (cd "$HOME/dev/huly-selfhost" && CONTAINERS_REGISTRIES_CONF=$PWD/.podman-registries.conf docker compose up -d >/dev/null)
  for _ in $(seq 60); do curl -sf -o /dev/null "$HULY_URL/config.json" && break; sleep 2; done
fi
HULY_TOKEN=$(python3 "$ROOT/scripts/dev/huly_project.py" "$HULY_URL" "$HULY_WORKSPACE" "$HULY_EMAIL" "$HULY_PASSWORD" \
  "$HULY_PROJECT" ${RESET:+--reset}) || die "could not prepare Huly project $HULY_PROJECT at $HULY_URL"

PGIDS=()
start() { # name dir command...; each runs in its own process group so Ctrl-C stops it whole
  local name=$1 dir=$2; shift 2
  (cd "$dir" && exec setsid "$@") > >(sed -u "s/^/[$name] /") 2>&1 &
  PGIDS+=("$!")
}
stop() {
  trap - INT TERM EXIT
  say "Stopping (a running planning session keeps going; end it in the chat pane)"
  for pg in "${PGIDS[@]}"; do kill -TERM -- "-$pg" 2>/dev/null || true; done
  wait 2>/dev/null || true
}
trap stop INT TERM EXIT

say "Starting Sortie, the workbench backend, and Vite"
SORTIE_HULY_URL=$HULY_URL SORTIE_HULY_WORKSPACE=$HULY_WORKSPACE SORTIE_HULY_PROJECT=$HULY_PROJECT \
SORTIE_HULY_TOKEN=$HULY_TOKEN SORTIE_CONTROL_TOKEN=$(cat "$TOKEN_FILE") \
  start sortie "$RUN_DIR" sortie WORKFLOW.md

WORKBENCH_STORE=$STORE WORKBENCH_SORTIE_URL=http://127.0.0.1:7678 \
WORKBENCH_SORTIE_TOKEN=$(cat "$TOKEN_FILE") WORKBENCH_PASSWORD_HASH=$(cat "$HASH_FILE") \
WORKBENCH_SECRET_KEY=dev-secret WORKBENCH_RUNTIME_DIR=$RUNTIME \
  start backend "$ROOT" uv run workbench serve --port 8790 --reload

start vite "$ROOT/frontend" npm run dev -- --host 127.0.0.1 --strictPort

ready=
for _ in $(seq 90); do
  # The backend first (asking through Vite before it is up logs proxy errors),
  # then Vite and its proxy: 401 from /api/me means both answer.
  [[ $(curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:8790/api/me) == 401 ]] &&
    [[ $(curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:5173/api/me) == 401 ]] && { ready=1; break; }
  sleep 1
done
[[ -n $ready ]] || die "the workbench did not come up; see the [backend] and [vite] lines above"
say "Ready: open http://127.0.0.1:5173   (Huly project $HULY_PROJECT: $HULY_URL/workbench/$HULY_WORKSPACE/tracker)   Ctrl-C to stop"
wait
