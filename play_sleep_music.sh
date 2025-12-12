#!/bin/bash

MP3="/Users/broliang/Music/sleep_meditation.mp3"
END_HOUR=9  # Stop at 07:00
BLUETOOTH_SPEAKER_ADDR="50-4f-3b-d2-27-74"
BLUEUTIL="/usr/local/bin/blueutil"
LOGFILE="$HOME/tmp/sleep_music.log"

# Ensure PATH is sane (launchd jobs have almost nothing)
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"

log() {
    # log with timestamp
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" >> "$LOGFILE"
}

connect_bluetooth() {
    echo "Connecting to Bluetooth speaker..."
    log "Trying to connect to Bluetooth speaker ($BLUETOOTH_SPEAKER_ADDR)..."
    "$BLUEUTIL" --connect "$BLUETOOTH_SPEAKER_ADDR"
    sleep 2
}

while true; do
    HOUR=$(date +%H)          # e.g. "09"
    HOUR_DEC=$((10#$HOUR))    # forces base 10, so "09" → 9

    # Stop only when hour >= 7 AND hour < 23
    if (( HOUR_DEC >= END_HOUR && HOUR_DEC < 23 )); then
        exit 0
    fi

	# Ensure Bluetooth stays connected
    if [[ "$("$BLUEUTIL" --is-connected "$BLUETOOTH_SPEAKER_ADDR")" == "0" ]]; then
		log "Speaker is not connected. Attempting reconnect..."
        connect_bluetooth
    fi

	log "Starting playback of $MP3"
    afplay "$MP3" || log "afplay exited with code $?"
done
