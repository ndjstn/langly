#!/bin/bash
set -euo pipefail

BASE_URL=${1:-http://localhost:8000}

SEED=$(curl -s -X POST "$BASE_URL/api/v2/seed/run")
RUN_ID=$(echo "$SEED" | python -c "import sys, json; print(json.load(sys.stdin)['run_id'])")

curl -s "$BASE_URL/api/v2/runs/$RUN_ID/deltas"
