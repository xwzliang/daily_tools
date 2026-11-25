#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")"
stage=$(mktemp -d)
trap 'rm -rf "$stage"' EXIT
xcrun swiftc -module-cache-path "$stage/cache" -parse-as-library Database.swift PageOCR.swift Library.swift LibraryTests.swift -o "$stage/tests"
"$stage/tests"
