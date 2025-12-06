#!/bin/bash

MP3="/Users/broliang/Music/sleep_meditation.mp3"
END_HOUR=7  # Stop at 07:00

while true; do
    HOUR=$(date +%H)

    # Stop only when hour >= 7 AND hour < 23
    # i.e., only stop in the daytime, not at night
    if (( HOUR >= END_HOUR && HOUR < 23 )); then
        exit 0
    fi

    afplay "$MP3"
done
