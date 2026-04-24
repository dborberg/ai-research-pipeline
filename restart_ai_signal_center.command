#!/bin/zsh
set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")" && pwd -P)"

"$REPO_DIR/stop_ai_signal_center.command" >/dev/null 2>&1 || true
"$REPO_DIR/launch_ai_signal_center.command"