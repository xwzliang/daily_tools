#!/usr/bin/env bash
# Standalone macOS Chrome remote-debugging consent monitor.
# Run this script in Terminal; stop with Ctrl-C.
# Grant your terminal Accessibility access in System Settings > Privacy & Security,
# and allow it to control System Events when macOS asks.
# Chrome remote debugging must already be enabled (chrome://inspect/#remote-debugging).
# This approves consent prompts; it does not launch or configure Chrome.
set -eu

if [[ "${1:-}" == --help || "${1:-}" == -h ]]; then
  sed -n '2,7p' "$0"
  exit 0
fi
if [[ $# -ne 0 ]]; then
  echo "Usage: $0 [--help]" >&2
  exit 2
fi
if [[ "$(uname -s)" != Darwin ]]; then
  echo 'This script requires macOS.' >&2
  exit 1
fi
trap 'exit 0' INT TERM

echo '[auto-allow] Monitoring Chrome remote debugging consent prompts. Stop with Ctrl-C.'
while true; do
  if ! result=$(/usr/bin/osascript <<'APPLESCRIPT'
on approvePrompt(container)
  tell application "System Events"
    try
      set elements to entire contents of container
    on error
      return false
    end try
    set isDebuggingPrompt to false
    repeat with element in elements
      try
        if class of element is static text then
          set labelText to ""
          try
            set labelText to value of element as text
          end try
          if labelText is "" then
            try
              set labelText to name of element as text
            end try
          end if
          if (labelText contains "remote debugging") or (labelText contains "远程调试") then set isDebuggingPrompt to true
        end if
      end try
    end repeat
    if not isDebuggingPrompt then return false
    repeat with element in elements
      try
        if class of element is button then
          set btnName to ""
          try
            set btnName to name of element as text
          end try
          if (btnName is "Allow") or (btnName is "允许") or (btnName contains "允许") or (btnName contains "Allow") then
            click element
            return true
          end if
        end if
      end try
    end repeat
  end tell
  return false
end approvePrompt

tell application "System Events"
  if not UI elements enabled then error "Accessibility access is disabled."
  if not (exists process "Google Chrome") then return ""
  tell process "Google Chrome"
    set chromeWindows to windows
  end tell
end tell
repeat with chromeWindow in chromeWindows
  tell application "System Events" to set chromeSheets to sheets of chromeWindow
  repeat with chromeSheet in chromeSheets
    if my approvePrompt(chromeSheet) then return "Approved Chrome remote debugging."
  end repeat
  if my approvePrompt(chromeWindow) then return "Approved Chrome remote debugging."
end repeat
return ""
APPLESCRIPT
  ); then
    echo '[auto-allow] Cannot inspect Chrome. Grant this terminal Accessibility access and permission to control System Events, then rerun.' >&2
    exit 1
  fi
  if [[ -n "$result" ]]; then
    echo "[auto-allow] $result"
  fi
  sleep 0.5
done
