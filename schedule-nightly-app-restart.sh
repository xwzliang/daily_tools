#!/usr/bin/env bash

set -euo pipefail

LABEL="com.broliang.nightly-app-restart"
SCRIPT_PATH="$(cd "$(dirname "$0")" && pwd)/$(basename "$0")"
LAUNCH_AGENTS_DIR="$HOME/Library/LaunchAgents"
PLIST_PATH="$LAUNCH_AGENTS_DIR/$LABEL.plist"
LOG_DIR="$HOME/Library/Logs"
LOG_PATH="$LOG_DIR/nightly-app-restart.log"

usage() {
  cat <<EOF
Usage: $(basename "$0") {install|run|status|uninstall}

  install    Schedule the restart every day at 02:00
  run        Restart VS Code, Chrome, and Firefox if they are running
  status     Show whether the schedule is installed and loaded
  uninstall  Remove the schedule
EOF
}

is_running() {
  osascript -e "application \"$1\" is running" 2>/dev/null | grep -q true
}

restart_running_apps() {
  local app
  local running_apps=()
  local apps=("Visual Studio Code" "Google Chrome" "Firefox")

  for app in "${apps[@]}"; do
    if is_running "$app"; then
      running_apps+=("$app")
    fi
  done

  if ((${#running_apps[@]} == 0)); then
    echo "$(date '+%Y-%m-%d %H:%M:%S') No target apps were running."
    return
  fi

  for app in "${running_apps[@]}"; do
    echo "$(date '+%Y-%m-%d %H:%M:%S') Restarting $app"
    osascript -e "tell application \"$app\" to quit"
  done

  # Give each application time to save state and exit cleanly.
  for app in "${running_apps[@]}"; do
    for _ in {1..30}; do
      is_running "$app" || break
      sleep 1
    done
  done

  for app in "${running_apps[@]}"; do
    if is_running "$app"; then
      echo "$(date '+%Y-%m-%d %H:%M:%S') $app did not quit; leaving it untouched."
    else
      open -a "$app"
      echo "$(date '+%Y-%m-%d %H:%M:%S') Reopened $app"
    fi
  done
}

install_schedule() {
  mkdir -p "$LAUNCH_AGENTS_DIR" "$LOG_DIR"

  cat >"$PLIST_PATH" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>$LABEL</string>
  <key>ProgramArguments</key>
  <array>
    <string>/bin/bash</string>
    <string>$SCRIPT_PATH</string>
    <string>run</string>
  </array>
  <key>StartCalendarInterval</key>
  <dict>
    <key>Hour</key>
    <integer>2</integer>
    <key>Minute</key>
    <integer>0</integer>
  </dict>
  <key>StandardOutPath</key>
  <string>$LOG_PATH</string>
  <key>StandardErrorPath</key>
  <string>$LOG_PATH</string>
</dict>
</plist>
EOF

  plutil -lint "$PLIST_PATH"
  launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null || true
  launchctl bootstrap "gui/$(id -u)" "$PLIST_PATH"
  echo "Installed nightly restart schedule for 02:00."
  echo "Log: $LOG_PATH"
}

show_status() {
  if [[ -f "$PLIST_PATH" ]]; then
    echo "Installed: $PLIST_PATH"
  else
    echo "Not installed."
    return 1
  fi

  if launchctl print "gui/$(id -u)/$LABEL" >/dev/null 2>&1; then
    echo "Loaded: yes"
  else
    echo "Loaded: no"
    return 1
  fi
}

uninstall_schedule() {
  launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null || true
  rm -f "$PLIST_PATH"
  echo "Removed nightly restart schedule."
}

case "${1:-}" in
  install) install_schedule ;;
  run) restart_running_apps ;;
  status) show_status ;;
  uninstall) uninstall_schedule ;;
  *) usage >&2; exit 2 ;;
esac
