#!/bin/sh
set -eu
WOWPATH="$HOME/Games/world-of-warcraft/drive_c/Blizzard/World of Warcraft/_retail_"

DIRNAME=$(dirname `readlink -f "$0"`)
cd "$WOWPATH"
exec "$DIRNAME/CurseBreaker.py"
