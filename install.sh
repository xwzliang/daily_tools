#!/usr/bin/env bash
set -eo pipefail

usage() {
    echo "Usage: $0 [--target DIRECTORY] [--dry-run]"
}

target="$HOME/bin"
preview=false
while (($#)); do
    case "$1" in
        --target) [[ $# -ge 2 && -n "$2" ]] || { usage >&2; exit 2; }; target=$2; shift 2 ;;
        --dry-run) preview=true; shift ;;
        -h|--help) usage; exit 0 ;;
        *) usage >&2; exit 2 ;;
    esac
done

[[ "$target" == /* ]] || target="$PWD/$target"
source_dir=$(dirname "$(realpath "$0")")
pending=()
conflicts=0
if [[ -e "$target" || -L "$target" ]]; then
    [[ -d "$target" ]] || { echo "Target is not a directory: $target" >&2; exit 1; }
fi
for source in "$source_dir"/*; do
    [[ -f "$source" ]] || continue
    name=${source##*/}
    case "$name" in install.sh|README*|test_*.py) continue ;; esac
    link="$target/$name"
    if [[ -L "$link" && "$link" -ef "$source" ]]; then
        continue
    fi
    if [[ -e "$link" || -L "$link" ]]; then
        echo "Name already in use: $link" >&2
        conflicts=1
    else
        pending+=("$source")
    fi
done
((conflicts == 0)) || exit 1
if [[ "$preview" == true ]]; then
    for source in "${pending[@]}"; do
        printf 'Would link %s -> %s\n' "$target/${source##*/}" "$source"
    done
    exit 0
fi

mkdir -p -- "$target"
for source in "${pending[@]}"; do
    # Pass the parent directory. ln creates one entry and refuses a collision
    # even if a new file or directory appears after the preflight.
    ln -s "$source" "$target/"
done
echo "Daily tools installed in $target"
