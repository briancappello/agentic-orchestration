#!/usr/bin/env bash
# Check the workbench's UI by hand, with no Huly and no real Sortie.
#
#   scripts/check/ui.sh planner    sign in through Dex as a person with only the planner role
#   scripts/check/ui.sh approver   the same person, given the approver role as well
#   scripts/check/ui.sh local      local mode (password "check"): both roles
#
# Starts, from a blank slate each time:
#   - a fake Sortie with fake worker brokers (fake_sortie.py, port 7690);
#   - for planner and approver, Dex (dex.yaml, port 5556), in a container;
#   - the workbench on http://127.0.0.1:8799, serving the built frontend,
#     with one project whose store holds the plan of seed_store.py.
# Story billing/b1 runs as HLAB-1, so it can be watched. Drive its runs with
#   curl -X POST 127.0.0.1:7690/admin/next   (the next run)
#   curl -X POST 127.0.0.1:7690/admin/end    (no more runs)
# Ctrl-C stops everything. State lives in $CHECK_HOME (~/.cache/plan-workbench-check).
set -euo pipefail

MODE=${1:-}
case $MODE in planner | approver | local) ;; *) echo "usage: $0 planner|approver|local" >&2; exit 2 ;; esac
ROOT=$(cd "$(dirname "$0")/../.." && pwd)
HERE=$ROOT/scripts/check
CHECK_HOME=${CHECK_HOME:-$HOME/.cache/plan-workbench-check}
TOKEN=check-sortie-token
DEX=plan-workbench-check-dex

say() { printf '\033[1m==> %s\033[0m\n' "$*"; }
die() { printf 'ui.sh: %s\n' "$*" >&2; exit 1; }
for port in 7690 8799; do ss -ltn | grep -q ":$port " && die "port $port is in use"; done
[[ $MODE == local ]] || { ss -ltn | grep -q ":5556 " && die "port 5556 is in use"; }

PIDS=()
stop() {
  trap - INT TERM EXIT
  say "Stopping"
  for pid in "${PIDS[@]}"; do kill "$pid" 2>/dev/null || true; done
  [[ $MODE == local ]] || docker rm -f "$DEX" >/dev/null 2>&1 || true
  wait 2>/dev/null || true
}
trap stop INT TERM EXIT

say "Fresh state in $CHECK_HOME"
rm -rf "$CHECK_HOME" && mkdir -p "$CHECK_HOME"
(cd "$ROOT" && uv sync -q && uv run python "$HERE/seed_store.py" "$CHECK_HOME/store")

say "Building the frontend"
(cd "$ROOT/frontend" && { [[ -d node_modules ]] || npm install --silent; } && npx vite build --logLevel warn)

say "Starting the fake Sortie"
(cd "$ROOT" && exec uv run python "$HERE/fake_sortie.py" --port 7690 --token "$TOKEN" --project HLAB) &
PIDS+=("$!")

ENV=(WORKBENCH_HOME="$CHECK_HOME/home" WORKBENCH_STORE="$CHECK_HOME/store" WORKBENCH_HULY_PROJECT=HLAB
  WORKBENCH_SORTIE_URL=http://127.0.0.1:7690 WORKBENCH_SORTIE_TOKEN=$TOKEN WORKBENCH_SECRET_KEY=check
  WORKBENCH_RUNTIME_DIR="$CHECK_HOME/sessions" WORKBENCH_FRONTEND_DIR="$ROOT/frontend/dist")
if [[ $MODE == local ]]; then
  ENV+=(WORKBENCH_PASSWORD_HASH="$(cd "$ROOT" && uv run python -c 'from workbench.auth import hash_password; print(hash_password("check"))')")
else
  say "Starting Dex"
  docker rm -f "$DEX" >/dev/null 2>&1 || true
  docker run -d --name "$DEX" -p 127.0.0.1:5556:5556 -v "$HERE/dex.yaml:/etc/dex/config.yaml:ro,Z" \
    ghcr.io/dexidp/dex:v2.41.1 dex serve /etc/dex/config.yaml >/dev/null
  for _ in $(seq 30); do curl -sf -o /dev/null http://127.0.0.1:5556/dex/.well-known/openid-configuration && break; sleep 1; done
  # Kilgore Trout is in "authors": that group is the planner group, and for
  # "approver" the approver group too (which grants both roles).
  APPROVERS=nobody-approves
  [[ $MODE == approver ]] && APPROVERS=authors
  ENV+=(WORKBENCH_OIDC_ISSUER=http://127.0.0.1:5556/dex WORKBENCH_OIDC_CLIENT_ID=workbench
    WORKBENCH_OIDC_CLIENT_SECRET=dex-client-secret-0123 WORKBENCH_OIDC_REDIRECT_URL=http://127.0.0.1:8799/api/auth/callback
    WORKBENCH_OIDC_PLANNER_GROUP=authors WORKBENCH_OIDC_APPROVER_GROUP=$APPROVERS
    WORKBENCH_OIDC_SCOPES="openid profile email groups")
fi

say "Starting the workbench"
(cd "$ROOT" && exec env "${ENV[@]}" uv run workbench serve --port 8799) &
PIDS+=("$!")
for _ in $(seq 60); do curl -sf -o /dev/null http://127.0.0.1:8799/api/auth/mode && break; sleep 1; done
say "Ready ($MODE): open http://127.0.0.1:8799   Ctrl-C to stop"
wait
