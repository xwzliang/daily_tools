#!/usr/bin/env bash

dir="$(dirname $(realpath "$0"))"
my_bin_dir=$HOME/bin
mkdir -p $my_bin_dir

scripts=$(ls $dir | grep -v $0 | grep -v README)

# Delete broken links from my_bin_dir
find $my_bin_dir -type l | perl -nle '-e || print' | xargs rm -f

while read script; do
	ln -sf $dir/$script $my_bin_dir/$script
done <<< "$scripts"

echo "Install Finished."
