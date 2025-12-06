#!/usr/bin/env bash

set -e

# Paths
SCRIPT_DIR="$HOME/git/daily_tools"
PLAYER_SCRIPT="$SCRIPT_DIR/play_sleep_music.sh"
PLIST_PATH="$HOME/Library/LaunchAgents/com.user.sleepmusic.plist"

# Check that play_sleep_music.sh exists
if [[ ! -f "$PLAYER_SCRIPT" ]]; then
    echo "Error: $PLAYER_SCRIPT not found."
    exit 1
fi

echo "Creating LaunchAgent plist..."

cat > "$PLIST_PATH" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.user.sleepmusic</string>

    <key>ProgramArguments</key>
    <array>
        <string>$PLAYER_SCRIPT</string>
    </array>

    <!-- Run every day at 23:00 -->
    <key>StartCalendarInterval</key>
    <dict>
        <key>Hour</key><integer>23</integer>
        <key>Minute</key><integer>0</integer>
    </dict>

    <key>KeepAlive</key><false/>

    <key>RunAtLoad</key><false/>
</dict>
</plist>
EOF

echo "Plist created at: $PLIST_PATH"

echo "Setting correct permissions..."
chmod 644 "$PLIST_PATH"

# Unload old version (ignore error)
echo "Unloading previous launchd job if exists..."
launchctl unload "$PLIST_PATH" 2>/dev/null || true

echo "Loading new launchd job..."
launchctl load "$PLIST_PATH"

echo "Done! Sleep music automation is now active."
echo "It will run at 23:00 every night."
