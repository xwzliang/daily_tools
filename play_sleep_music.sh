#!/bin/bash

MP3="/Users/broliang/Music/sleep_meditation.mp3"
END_HOUR=7  # Stop at 07:00

while true; do
    HOUR=$(date +%H)          # e.g. "09"
    HOUR_DEC=$((10#$HOUR))    # forces base 10, so "09" → 9

    # Stop only when hour >= 7 AND hour < 23
    if (( HOUR_DEC >= END_HOUR && HOUR_DEC < 23 )); then
        exit 0
    fi

    afplay "$MP3"
done
