#!/usr/bin/env bash

pandoc -t plain "${1:-README.md}" | less
