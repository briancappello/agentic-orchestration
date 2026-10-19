#!/usr/bin/env bash
# Check what each role may do, through the API, against a running
#   scripts/check/ui.sh planner    then   scripts/check/roles_api.sh planner
#   scripts/check/ui.sh approver   then   scripts/check/roles_api.sh approver
#
# Signs in through Dex's mock connector with curl, then sends the commands a
# planner must be refused and an approver allowed. Prints one line per check
# and exits non-zero if any fails.
set -uo pipefail

ROLE=${1:-}
case $ROLE in planner | approver) ;; *) echo "usage: $0 planner|approver" >&2; exit 2 ;; esac
# The session cookie belongs to 127.0.0.1, so every request must use it, not localhost.
B=http://127.0.0.1:8799/api
P=$B/projects/store
JAR=$(mktemp)
trap 'rm -f "$JAR"' EXIT
FAILED=0

curl -s -c "$JAR" -b "$JAR" -L -o /dev/null "$B/auth/login?next=/"
roles=$(curl -s -b "$JAR" "$B/me" | python3 -c 'import json,sys; print(",".join(json.load(sys.stdin)["identity"]["roles"]))')

check() { # label expected-code method path [json]
  local code
  code=$(curl -s -b "$JAR" -o /dev/null -w '%{http_code}' -X "$3" -H 'content-type: application/json' ${5:+-d "$5"} "$4")
  if [[ $code == "$2" ]]; then echo "ok    $1: $code"; else echo "FAIL  $1: $code, want $2"; FAILED=1; fi
}

if [[ $ROLE == planner ]]; then
  [[ $roles == planner ]] && echo "ok    roles: $roles" || { echo "FAIL  roles: $roles, want planner"; FAILED=1; }
  check "watch the worker" 200 GET "$P/workers/HLAB-1/messages"
  check "read the broker state" 200 POST "$P/workers/HLAB-1/commands" '{"op":"state"}'
  for op in steer prompt interrupt handback permit; do
    check "send $op" 403 POST "$P/workers/HLAB-1/commands" "{\"op\":\"$op\",\"text\":\"x\"}"
  done
  check "approve the epic" 403 POST "$P/approve" '{"epic":"billing"}'
  check "pull back" 403 POST "$P/stories/pull-back" '{"key":"billing/b2"}'
  check "cancel" 403 POST "$P/stories/cancel" '{"key":"billing/b1"}'
  check "supersede" 403 POST "$P/stories/supersede" '{"key":"billing/b2"}'
else
  [[ $roles == planner,approver ]] && echo "ok    roles: $roles" || { echo "FAIL  roles: $roles, want planner,approver"; FAILED=1; }
  check "send steer" 200 POST "$P/workers/HLAB-1/commands" '{"op":"steer","text":"from roles_api.sh"}'
  check "approve a story" 200 POST "$P/approve" '{"keys":["billing/b2"]}'
fi
exit $FAILED
