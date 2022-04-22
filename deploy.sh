#!/usr/bin/env bash

set -euo pipefail
IFS=$'\n\t'

files=("config.json" "main.py" "render_helpers.py" "ssd1306")
port=${1:-}

if [[ -z "$port" ]]; then
  echo "Please specify port as first argument (e.g. /dev/ttyUSB0)"
  exit 1
fi

for file in "${files[@]}"; do
  if [[ -e $file ]]; then
    ampy --port $port put $file
    echo "$file copied to device at $port"
  else
    echo "$file not found"
  fi
done

