#!/usr/bin/env bash
# Start the whole planning stack for development: Huly (if down), Sortie,
# the workbench backend (reloads on Python edits), and Vite (hot reload).
# Ctrl-C stops Sortie, the backend, and Vite. A running planning session
# keeps going; end it from the chat pane.
#
# Settings, all optional (environment overrides):
#   STORE        spec store to plan in   (default: a scratch clone of ~/dev/agent-platform-specs)
#   SORTIE_SRC   Sortie checkout          (default: ~/dev/sortie)
#   HULY_EMAIL / HULY_PASSWORD             (default: sortie@example.com / sortie-dev-pass)
set -euo pipefail

ROOT=$(cd "$(dirname "$0")/.." && pwd)
SORTIE_SRC=${SORTIE_SRC:-$HOME/dev/sortie}
SPECS=${SPECS:-$HOME/dev/agent-platform-specs}
WORK=${WORK:-$HOME/dev/plan-workbench-worktrees/live}
STORE=${STORE:-$WORK/store}
RUN_DIR=$WORK/sortie-run
HULY_URL=${HULY_URL:-http://localhost:8087}
HULY_EMAIL=${HULY_EMAIL:-sortie@example.com}
HULY_PASSWORD=${HULY_PASSWORD:-sortie-dev-pass}
TOKEN_FILE=$HOME/.config/plan-workbench-sortie-token
HASH_FILE=$HOME/.config/plan-workbench-password-hash

say() { printf '\033[1m==> %s\033[0m\n' "$*"; }
die() { printf 'dev.sh: %s\n' "$*" >&2; exit 1; }

for port in 7678 8790 5173; do
  ss -ltn | grep -q ":$port " && die "port $port is in use; stop whatever runs there first"
done

# One-time setup.
mkdir -p "$HOME/.config"
[[ -s $TOKEN_FILE ]] || { openssl rand -hex 24 > "$TOKEN_FILE"; chmod 600 "$TOKEN_FILE"; }
if [[ ! -s $HASH_FILE ]]; then
  say "Choose the password you will sign in to the workbench with"
  (cd "$ROOT" && uv run workbench hash-password) > "$HASH_FILE"
  chmod 600 "$HASH_FILE"
fi
[[ -d $STORE/openspec ]] || { say "Cloning a scratch spec store into $STORE"; git clone -q "$SPECS" "$STORE"; }
mkdir -p "$RUN_DIR"
[[ -f $RUN_DIR/WORKFLOW.md ]] || cp "$ROOT/scripts/dev/WORKFLOW.md" "$RUN_DIR/WORKFLOW.md"

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
HULY_TOKEN=$(curl -sf -X POST "$HULY_URL/_accounts" -H 'Content-Type: application/json' \
  -d "{\"method\":\"login\",\"params\":{\"email\":\"$HULY_EMAIL\",\"password\":\"$HULY_PASSWORD\"}}" | jq -r .result.token)
[[ -n $HULY_TOKEN && $HULY_TOKEN != null ]] || die "could not log in to Huly at $HULY_URL as $HULY_EMAIL"

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
SORTIE_HULY_URL=$HULY_URL SORTIE_HULY_WORKSPACE=sortie SORTIE_HULY_PROJECT=HULY \
SORTIE_HULY_TOKEN=$HULY_TOKEN SORTIE_CONTROL_TOKEN=$(cat "$TOKEN_FILE") \
  start sortie "$RUN_DIR" sortie WORKFLOW.md

WORKBENCH_STORE=$STORE WORKBENCH_SORTIE_URL=http://127.0.0.1:7678 \
WORKBENCH_SORTIE_TOKEN=$(cat "$TOKEN_FILE") WORKBENCH_PASSWORD_HASH=$(cat "$HASH_FILE") \
WORKBENCH_SECRET_KEY=dev-secret \
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
say "Ready: open http://127.0.0.1:5173  (store: $STORE)  Ctrl-C to stop"
wait
