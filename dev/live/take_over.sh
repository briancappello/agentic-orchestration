#!/usr/bin/env bash
# Catch a worker of the live run as soon as it starts, and take the floor, so
# a person can watch, steer, and hand back in the workbench before the agent
# finishes (small stories take an agent seconds).
#
#   dev/live/take_over.sh LIVE-7      wait up to 10 minutes for LIVE-7's worker
#
# Goes through the workbench, signed in with the live run's password, so the
# command is relayed and recorded like one sent from the page. Then open the
# story in the workbench, choose Watch, steer it, and choose Hand back.
set -euo pipefail

IDENT=${1:?usage: $0 <tracker identifier>}
B=http://127.0.0.1:${WB_PORT:-8791}/api
P=$B/projects/${PROJECT_SLUG:-store}
JAR=$(mktemp)
trap 'rm -f "$JAR"' EXIT

curl -sf -c "$JAR" -o /dev/null -H 'Content-Type: application/json' -d "{\"password\":\"${LIVE_PASSWORD:-live}\"}" "$B/login"
# Watch Sortie itself: the workbench polls it only every few seconds.
SORTIE=http://127.0.0.1:${SORTIE_PORT:-7679}
TOKEN=$(cat "${LIVE_HOME:-$HOME/.cache/plan-workbench-live}/sortie-token")
echo "waiting for $IDENT's worker" >&2
for _ in $(seq 3000); do
  if curl -sf -o /dev/null -H "Authorization: Bearer $TOKEN" "$SORTIE/api/v1/$IDENT/broker"; then
    # The workbench relays only stories it has seen running; give its poll a moment.
    for _ in $(seq 40); do
      code=$(curl -s -o /dev/null -w '%{http_code}' -b "$JAR" -H 'Content-Type: application/json' -d '{"op":"interrupt"}' "$P/workers/$IDENT/commands")
      if [[ $code == 200 ]]; then
        echo "took the floor of $IDENT: watch it in the workbench, then Hand back" >&2
        exit 0
      fi
      sleep 0.25
    done
    echo "the workbench did not relay $IDENT (last answer $code)" >&2
    exit 1
  fi
  sleep 0.2
done
echo "no worker for $IDENT" >&2
exit 1
