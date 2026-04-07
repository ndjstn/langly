#!/usr/bin/env bash
set -euo pipefail

OUT_FILE=${1:-/tmp/ollama-watch.log}
INTERVAL=${2:-2}

while true; do
  printf "[%s]\n" "$(date -Iseconds)" >> "$OUT_FILE"
  if command -v ollama >/dev/null 2>&1; then
    ollama ps >> "$OUT_FILE" 2>&1
  else
    echo "ollama not found" >> "$OUT_FILE"
  fi
  echo "" >> "$OUT_FILE"
  sleep "$INTERVAL"
done
