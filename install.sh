#!/usr/bin/env bash

dir="$(dirname $(realpath "$0"))"
my_bin_dir=$HOME/bin
mkdir -p $my_bin_dir
echo $dir

scripts=$(ls $dir | grep -v $0 | grep -v README)

while read script; do
	ln -s $dir/$script $my_bin_dir/$script
done <<< "$scripts"

echo "Install Finished."
