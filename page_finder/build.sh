#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")"
out="${1:-$HOME/Applications/Page Finder.app}"
if [[ -e "$out" ]]; then
  echo "Choose a new output path. A bundle already exists at $out" >&2
  exit 1
fi
stage=$(mktemp -d)
trap 'rm -rf "$stage"' EXIT
app="$stage/Page Finder.app"
mkdir -p "$app/Contents/MacOS"
mac_arch=$(uname -m)
xcrun swiftc -O -parse-as-library -target "${mac_arch}-apple-macos13.0" Database.swift Library.swift PageFinder.swift -o "$app/Contents/MacOS/PageFinder"
cp Info.plist "$app/Contents/Info.plist"
codesign --force --sign - "$app"
codesign --verify --strict "$app"
mkdir -p "$(dirname "$out")"
mv -n "$app" "$out"
[[ ! -e "$app" ]] || { echo "Destination appeared during build" >&2; exit 1; }
echo "$out"
