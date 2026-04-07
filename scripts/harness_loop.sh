#!/usr/bin/env bash
set -euo pipefail

HOST=${HOST:-http://localhost:8000}
COUNT=${1:-10}
OUT_FILE=${2:-/tmp/harness-loop.log}

for i in $(seq 1 "$COUNT"); do
  printf "[%s] run %s\n" "$(date -Iseconds)" "$i" >> "$OUT_FILE"
  curl -sS "$HOST/api/v2/harness/run" \
    -H "Content-Type: application/json" \
    -d '{"message":"Quick status check","grade":false}' >> "$OUT_FILE" 2>&1 || true
  echo "" >> "$OUT_FILE"
  sleep 0.5
 done
