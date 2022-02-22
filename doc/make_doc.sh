#!/bin/bash

#
# Add host "kodi" to your ~/.ssh/config file.
#

top="$(readlink -f "$(dirname "$0")/..")"

cd "$top/script.module.libka/lib"
pdoc3 --output-dir "$top/html" --html --force libka/ && rsync -Pah --delete --stats -e ssh "$top/html/libka/" kodi:/home/kodi/doc/libka/
