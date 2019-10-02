#!/usr/bin/env bash

torrent_file=$1
file_extension=$2

indices=$(aria2c $torrent_file -S | grep $file_extension | cut -f 1 -d \| | paste -sd "," - | tr -d "[:space:]")
aria2c --select-file=$indices $torrent_file
