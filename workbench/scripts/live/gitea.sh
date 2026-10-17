#!/usr/bin/env bash
# A local Gitea for the live run: the forge Sortie's agents push to and whose
# merges finish stories (scripts/live/live.sh runs this).
#
#   scripts/live/gitea.sh up      start it and seed the repository, if needed; print exports
#   scripts/live/gitea.sh down    remove the container and its data
#
# Idempotent: "up" reuses a running container and creates only what is missing.
# Prints, on stdout, the exports live.sh evaluates: the URL, the owner/repo,
# and an access token (in $LIVE_HOME/gitea-token, mode 0600).
set -euo pipefail

CMD=${1:-}
HERE=$(cd "$(dirname "$0")" && pwd)
LIVE_HOME=${LIVE_HOME:-$HOME/.cache/plan-workbench-live}
NAME=plan-workbench-live-gitea
IMAGE=docker.io/gitea/gitea:1.27.3
PORT=${GITEA_PORT:-3001}
URL=http://127.0.0.1:$PORT
USER_=sortie
PASS=Live-Gitea-Pw1
REPO=live-lab

log() { printf 'gitea.sh: %s\n' "$*" >&2; }

case $CMD in
down)
  docker rm -f "$NAME" >/dev/null 2>&1 || true
  rm -f "$LIVE_HOME/gitea-token"
  log "removed"
  exit 0
  ;;
up) ;;
*) echo "usage: $0 up|down" >&2; exit 2 ;;
esac

mkdir -p "$LIVE_HOME"
if ! docker ps --format '{{.Names}}' | grep -qx "$NAME"; then
  docker rm -f "$NAME" >/dev/null 2>&1 || true
  log "starting $IMAGE on $URL"
  # INSTALL_LOCK skips the first-run wizard; ROOT_URL makes clone URLs and PR
  # links point at the host port.
  docker run -d --name "$NAME" -p "127.0.0.1:$PORT:3000" \
    -e GITEA__security__INSTALL_LOCK=true -e GITEA__service__DISABLE_REGISTRATION=true \
    -e GITEA__server__ROOT_URL="$URL/" -e GITEA__database__DB_TYPE=sqlite3 \
    "$IMAGE" >/dev/null
fi
for _ in $(seq 60); do curl -sf -o /dev/null "$URL/api/v1/version" && break; sleep 2; done
curl -sf -o /dev/null "$URL/api/v1/version" || { log "Gitea did not come up"; exit 1; }

if ! curl -sf -o /dev/null -u "$USER_:$PASS" "$URL/api/v1/user"; then
  log "creating user $USER_"
  # Without --must-change-password=false a new admin cannot mint a token.
  docker exec -u git "$NAME" gitea admin user create --username "$USER_" --password "$PASS" \
    --email sortie@example.com --admin --must-change-password=false >/dev/null
fi

TOKEN_FILE=$LIVE_HOME/gitea-token
if [[ ! -s $TOKEN_FILE ]] || ! curl -sf -o /dev/null -H "Authorization: token $(cat "$TOKEN_FILE")" "$URL/api/v1/user"; then
  log "creating an access token"
  curl -sf -u "$USER_:$PASS" -H 'Content-Type: application/json' -X POST "$URL/api/v1/users/$USER_/tokens" \
    -d "{\"name\":\"live-$(date +%s)\",\"scopes\":[\"write:repository\",\"write:issue\",\"read:user\"]}" |
    python3 -c 'import json,sys; print(json.load(sys.stdin)["sha1"])' > "$TOKEN_FILE"
  chmod 600 "$TOKEN_FILE"
fi
TOKEN=$(cat "$TOKEN_FILE")

if ! curl -sf -o /dev/null -H "Authorization: token $TOKEN" "$URL/api/v1/repos/$USER_/$REPO"; then
  log "creating and seeding $USER_/$REPO"
  # Basic auth: creating a repository needs write:user, which the token Sortie gets does not carry.
  curl -sf -o /dev/null -u "$USER_:$PASS" -H 'Content-Type: application/json' -X POST "$URL/api/v1/user/repos" \
    -d "{\"name\":\"$REPO\",\"private\":false,\"default_branch\":\"main\"}"
  tmp=$(mktemp -d)
  cp -r "$HERE/repo/." "$tmp/"
  git -C "$tmp" init -q -b main
  git -C "$tmp" add -A
  git -C "$tmp" -c user.name=live -c user.email=live@localhost commit -qm "Seed the live lab"
  git -C "$tmp" push -q "http://$USER_:$TOKEN@127.0.0.1:$PORT/$USER_/$REPO.git" main
  rm -rf "$tmp"
fi

echo "export LIVE_GITEA_URL=$URL LIVE_GITEA_PROJECT=$USER_/$REPO LIVE_GITEA_TOKEN=$TOKEN"
