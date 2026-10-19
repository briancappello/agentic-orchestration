#!/usr/bin/env bash
# A local Gitea: the forge Sortie's workers push to, and whose merges finish
# stories under plan control. dev/dev.sh and dev/live/live.sh run it.
#
#   dev/forge/gitea.sh up      start it and seed the repository, if needed; print exports
#   dev/forge/gitea.sh down    remove the container and all its repositories
#
# Idempotent: "up" reuses a running container and creates only what is missing.
# Settings: GITEA_HOME (where the token file lives), GITEA_REPO (the repository,
# seeded from dev/forge/repo/), GITEA_PORT (3001).
# Prints, on stdout, the exports the caller evaluates: FORGE_URL, FORGE_PROJECT
# (owner/repo), and FORGE_TOKEN (also in $GITEA_HOME/gitea-token, mode 0600).
set -euo pipefail

CMD=${1:-}
HERE=$(cd "$(dirname "$0")" && pwd)
GITEA_HOME=${GITEA_HOME:-$HOME/.cache/plan-workbench-live}
NAME=plan-workbench-live-gitea
IMAGE=docker.io/gitea/gitea:1.27.3
PORT=${GITEA_PORT:-3001}
URL=http://127.0.0.1:$PORT
USER_=sortie
PASS=Live-Gitea-Pw1
REPO=${GITEA_REPO:-live-lab}

log() { printf 'gitea.sh: %s\n' "$*" >&2; }

case $CMD in
down)
  docker rm -f "$NAME" >/dev/null 2>&1 || true
  rm -f "$GITEA_HOME/gitea-token"
  log "removed"
  exit 0
  ;;
up) ;;
*) echo "usage: $0 up|down" >&2; exit 2 ;;
esac

mkdir -p "$GITEA_HOME"
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

TOKEN_FILE=$GITEA_HOME/gitea-token
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

echo "export FORGE_URL=$URL FORGE_PROJECT=$USER_/$REPO FORGE_TOKEN=$TOKEN"
