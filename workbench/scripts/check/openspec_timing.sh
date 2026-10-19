#!/usr/bin/env bash
# Measure what an OpenSpec call costs a plan check, on this machine.
#
#   scripts/check/openspec_timing.sh [store]    (default: a copy of the test fixture)
#
# Prints, for one change: Node's bare startup; `openspec show` with OpenSpec's
# telemetry on (its default) and off; and planlib.validate cold, warm, and
# after a spec edit. planlib turns telemetry off and caches `openspec show`
# by file contents (src/planlib/requirements.py), so a warm check should cost
# milliseconds. If "warm" is not far below "cold", that default regressed.
set -euo pipefail

ROOT=$(cd "$(dirname "$0")/../.." && pwd)
WORK=$(mktemp -d)
trap 'rm -rf "$WORK"' EXIT
if [[ -n ${1:-} ]]; then
  cp -r "$1" "$WORK/store"
else
  # A new store, as the workbench scaffolds it, holding the test fixture's change.
  (cd "$ROOT" && uv run python -c 'import sys; from workbench.scaffold import scaffold_store; scaffold_store(sys.argv[1], "timing")' "$WORK/store")
  cp -r "$ROOT/tests/fixtures/openspec-1.13/billing" "$WORK/store/openspec/changes/billing"
  printf 'schema_version: 1\nchanges:\n  - name: billing\n    depends_on: []\n' > "$WORK/store/openspec/plan.yaml"
fi
STORE=$WORK/store
CHANGE=$(ls "$STORE/openspec/changes" | grep -v -e '^archive$' -e '^\.gitkeep$' | head -1)

secs() { python3 -c "import sys; print(f'{float(sys.argv[2])-float(sys.argv[1]):.3f}s')" "$1" "$2"; }
timeit() { local s e; s=$(date +%s.%N); "$@" >/dev/null 2>&1 || true; e=$(date +%s.%N); secs "$s" "$e"; }

echo "openspec $(openspec --version 2>/dev/null), change \"$CHANGE\""
printf '%-44s %s\n' "node -e 0" "$(timeit node -e 0)"
cd "$STORE"
printf '%-44s %s\n' "openspec show, telemetry on (OpenSpec default)" \
  "$(env -u DO_NOT_TRACK OPENSPEC_TELEMETRY=1 bash -c "$(declare -f secs timeit); timeit openspec show $CHANGE --type change --json --no-interactive")"
printf '%-44s %s\n' "openspec show, telemetry off (planlib default)" \
  "$(OPENSPEC_TELEMETRY=0 DO_NOT_TRACK=1 bash -c "$(declare -f secs timeit); timeit openspec show $CHANGE --type change --json --no-interactive")"
cd "$ROOT"
uv run python - "$STORE" "$CHANGE" <<'EOF'
import sys, time
from pathlib import Path
import planlib
store, change = Path(sys.argv[1]), sys.argv[2]
def t(label):
    s = time.time(); planlib.validate(store); print(f"{label:<44} {time.time() - s:.3f}s")
t("planlib.validate, cold")
t("planlib.validate, warm (an approval)")
specs = sorted((store / "openspec/changes" / change).rglob("spec.md"))
if specs:
    specs[0].write_text(specs[0].read_text() + "\n")
    t("planlib.validate, after a spec edit")
EOF
