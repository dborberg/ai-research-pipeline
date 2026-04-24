#!/bin/zsh
set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd -P)"
START_APPLESCRIPT_SOURCE="$REPO_DIR/macos/ai_signal_command_center_launcher.applescript"
STOP_APPLESCRIPT_SOURCE="$REPO_DIR/macos/ai_signal_command_center_stop.applescript"
START_APP_NAME="AI Signal Command Center.app"
STOP_APP_NAME="Stop AI Signal Command Center.app"
DEFAULT_TARGET_DIR="$HOME/Applications"
TARGET_DIR="${1:-$DEFAULT_TARGET_DIR}"

build_app() {
  local applescript_source="$1"
  local app_name="$2"
  local app_path="$TARGET_DIR/$app_name"
  local resources_link="$app_path/Contents/Resources/ai-research-pipeline"

  if [[ ! -f "$applescript_source" ]]; then
    echo "AppleScript source not found: $applescript_source" >&2
    exit 1
  fi

  rm -rf "$app_path"
  osacompile -o "$app_path" "$applescript_source"
  ln -sfn "$REPO_DIR" "$resources_link"
  echo "Created: $app_path"
}

mkdir -p "$TARGET_DIR"
build_app "$START_APPLESCRIPT_SOURCE" "$START_APP_NAME"
build_app "$STOP_APPLESCRIPT_SOURCE" "$STOP_APP_NAME"

echo "Drag the app(s) you use most into the Dock for one-click control."