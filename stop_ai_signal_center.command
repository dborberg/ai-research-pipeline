#!/bin/zsh
set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")" && pwd)"
APP_PORT="8510"
LOG_DIR="$REPO_DIR/logs"
PID_FILE="$LOG_DIR/streamlit_app.pid"

stop_pid() {
  local pid="$1"
  if [[ -n "$pid" ]] && kill -0 "$pid" >/dev/null 2>&1; then
    kill "$pid" >/dev/null 2>&1 || true
    for _ in {1..10}; do
      if ! kill -0 "$pid" >/dev/null 2>&1; then
        break
      fi
      sleep 1
    done
    if kill -0 "$pid" >/dev/null 2>&1; then
      kill -9 "$pid" >/dev/null 2>&1 || true
    fi
  fi
}

if [[ -f "$PID_FILE" ]]; then
  stop_pid "$(cat "$PID_FILE")"
  rm -f "$PID_FILE"
fi

port_pid="$(lsof -ti tcp:"$APP_PORT" -sTCP:LISTEN 2>/dev/null || true)"
if [[ -n "$port_pid" ]]; then
  stop_pid "$port_pid"
fi

osascript -e 'display notification "AI Signal Command Center stopped" with title "Streamlit Launcher"'