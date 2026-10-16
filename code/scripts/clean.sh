#!/usr/bin/env zsh
set -euo pipefail                      # stop on any error
cd "$(dirname "$0")/../frontend"       # relative to this script's location, not your terminal
rm -rf __pycache__ .web .gitignore
find . -name __pycache__ -type d -prune -exec rm -rf {} +
echo "Cleaned Reflex build artifacts in $(pwd)"