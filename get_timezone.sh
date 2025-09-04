#!/bin/bash

get_timezone() {
  if command -v timedatectl >/dev/null 2>&1; then
    timedatectl | grep "Time zone" | awk '{print $3}'
  elif [ -f /etc/timezone ]; then
    cat /etc/timezone
  elif readlink /etc/localtime >/dev/null 2>&1; then
    readlink /etc/localtime | sed 's|.*/zoneinfo/||'
  else
    date +%Z
  fi
}

timezone=$(get_timezone)
echo "Detected timezone: $timezone"