#!/bin/bash

MP3="/Users/broliang/Music/sleep_meditation.mp3"
END_HOUR=7  # Stop at 07:00
BLUETOOTH_SPEAKER_ADDR="50-4f-3b-d2-27-74"

connect_bluetooth() {
    echo "Connecting to Bluetooth speaker..."
    blueutil --connect "$BLUETOOTH_SPEAKER_ADDR"
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
    if [[ "$(blueutil --is-connected "$BLUETOOTH_SPEAKER_ADDR")" == "0" ]]; then
        connect_bluetooth
    fi

    afplay "$MP3"
done
