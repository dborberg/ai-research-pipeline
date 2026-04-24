#!/bin/zsh
set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")" && pwd -P)"
APP_PORT="8510"
APP_URL="http://localhost:${APP_PORT}"
PYTHON_BIN="$REPO_DIR/venv/bin/python"
STREAMLIT_APP="$REPO_DIR/streamlit_app.py"
LOG_DIR="$REPO_DIR/logs"
LOG_FILE="$LOG_DIR/streamlit_app.log"
PID_FILE="$LOG_DIR/streamlit_app.pid"

mkdir -p "$LOG_DIR"
cd "$REPO_DIR"

if [[ ! -x "$PYTHON_BIN" ]]; then
  osascript -e 'display alert "Python environment not found" message "Expected venv/bin/python in the repository root." as critical'
  exit 1
fi

if [[ -f "$PID_FILE" ]]; then
  existing_pid="$(cat "$PID_FILE")"
  if [[ -n "$existing_pid" ]] && kill -0 "$existing_pid" >/dev/null 2>&1; then
    if curl -fsS "$APP_URL/_stcore/health" >/dev/null 2>&1; then
      open "$APP_URL"
      exit 0
    fi
  fi
  rm -f "$PID_FILE"
fi

if ! curl -fsS "$APP_URL/_stcore/health" >/dev/null 2>&1; then
  nohup "$PYTHON_BIN" -m streamlit run "$STREAMLIT_APP" --server.headless true --server.port "$APP_PORT" > "$LOG_FILE" 2>&1 &
  echo $! > "$PID_FILE"

  for _ in {1..20}; do
    if curl -fsS "$APP_URL/_stcore/health" >/dev/null 2>&1; then
      break
    fi
    sleep 1
  done
fi

open "$APP_URL"