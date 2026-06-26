#!/bin/zsh
set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")" && pwd -P)"
PREFERRED_PYTHON="$REPO_DIR/venv/bin/python"
FALLBACK_PYTHON="$(command -v python3 || true)"
PYTHON_BIN="$PREFERRED_PYTHON"

if [[ ! -x "$PYTHON_BIN" ]]; then
  PYTHON_BIN="$FALLBACK_PYTHON"
fi

if [[ -z "$PYTHON_BIN" || ! -x "$PYTHON_BIN" ]]; then
  osascript -e 'display alert "Python environment not found" message "Expected venv/bin/python in the repository root or a python3 binary on PATH." as critical'
  exit 1
fi

cd "$REPO_DIR"

DEFAULT_WEEK_ENDING="$($PYTHON_BIN - <<'PY'
from app.reporting import get_latest_completed_friday
print(get_latest_completed_friday().isoformat())
PY
)"

WEEK_ENDING="$DEFAULT_WEEK_ENDING"
DEBUG_FLAG=""

if [[ $# -ge 1 ]]; then
  WEEK_ENDING="$1"
else
  WEEK_ENDING="$(osascript <<OSA
text returned of (display dialog "Replay which Friday week-ending date?" default answer "$DEFAULT_WEEK_ENDING" buttons {"Cancel", "Run Replay"} default button "Run Replay")
OSA
)"

  DEBUG_RESPONSE="$(osascript <<OSA
button returned of (display dialog "Include the internal weekly scoring table?" buttons {"No", "Yes"} default button "No")
OSA
)"

  if [[ "$DEBUG_RESPONSE" == "Yes" ]]; then
    DEBUG_FLAG="--debug-weekly-scoring"
  fi
fi

echo "Running weekly replay for $WEEK_ENDING"
"$PYTHON_BIN" scripts/replay_weekly_reports.py --week-ending "$WEEK_ENDING" ${=DEBUG_FLAG}

OUTPUT_DIR="$REPO_DIR/outputs/replay/$WEEK_ENDING"
if [[ -d "$OUTPUT_DIR" ]]; then
  open "$OUTPUT_DIR"
fi