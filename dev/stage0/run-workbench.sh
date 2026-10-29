#!/usr/bin/env bash
# Start the stage-0 plan workbench (the ortus-stage0-workbench user unit runs
# this). Local mode: one password, kept as a hash in $STAGE0_HOME; the
# password itself is in $STAGE0_HOME/workbench-password (0600) for the
# operator. The workbench binds to loopback only. Planning sessions run the
# host's opencode with the live kit's agent configuration (Anthropic sign-in
# plugin only).
set -euo pipefail

STAGE0_HOME=${STAGE0_HOME:-$HOME/.local/share/ortus-nova/stage0}
# shellcheck source=/dev/null
. "$STAGE0_HOME/stage0.env"

export PATH=$STAGE0_HOME/bin:$HOME/.local/bin:$HOME/.local/share/pnpm/bin:/usr/local/bin:/usr/bin:/bin
WB=$STAGE0_KIT_ROOT/workbench
cd "$WB"
exec env WORKBENCH_HOME="$STAGE0_HOME/home" WORKBENCH_STORE="$STAGE0_STORE" WORKBENCH_HULY_PROJECT="$STAGE0_HULY_PROJECT" \
  WORKBENCH_SORTIE_URL="http://127.0.0.1:$STAGE0_SORTIE_PORT" WORKBENCH_SORTIE_TOKEN="$(cat "$STAGE0_HOME/sortie-token")" \
  WORKBENCH_PASSWORD_HASH="$(cat "$STAGE0_HOME/workbench-password-hash")" \
  WORKBENCH_SECRET_KEY="$(cat "$STAGE0_HOME/workbench-secret")" \
  WORKBENCH_RUNTIME_DIR="$STAGE0_HOME/sessions" WORKBENCH_FRONTEND_DIR="$WB/frontend/dist" \
  WORKBENCH_AGENT_COMMAND="env XDG_CONFIG_HOME=$STAGE0_KIT_ROOT/dev/live/agent-config opencode acp" \
  "$WB/.venv/bin/workbench" serve --host 127.0.0.1 --port "$STAGE0_WORKBENCH_PORT"
