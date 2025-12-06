#!/bin/bash

MP3="/Users/broliang/Music/sleep_meditation.mp3"
END_HOUR=7  # Stop at 07:00

while true; do
    # Check current time
    HOUR=$(date +%H)
    if [ "$HOUR" -ge "$END_HOUR" ]; then
        exit 0
    fi

    # Play the mp3 once (afplay waits until the file finishes)
    afplay "$MP3"
done
