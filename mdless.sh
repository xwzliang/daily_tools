#!/usr/bin/env bash

pandoc "${1:-README.md}" | w3m -T text/html
# pandoc -t plain "${1:-README.md}" | less
