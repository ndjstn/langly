#!/bin/bash
set -euo pipefail

BASE_URL=${1:-http://localhost:8000}

RUNS=$(curl -s "$BASE_URL/api/v2/runs")
RUN_ID=$(echo "$RUNS" | python -c "import sys, json; data=json.load(sys.stdin); print(data['runs'][0]['id'] if data['runs'] else '')")

if [ -z "$RUN_ID" ]; then
  echo "No runs"
  exit 0
fi

echo "Latest run: $RUN_ID"
curl -s "$BASE_URL/api/v2/runs/$RUN_ID/deltas"
