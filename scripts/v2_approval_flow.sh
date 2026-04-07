#!/bin/bash
set -euo pipefail

BASE_URL=${1:-http://localhost:8000}

RUN=$(curl -s "$BASE_URL/api/v2/workflows/run" \
  -H "Content-Type: application/json" \
  -d '{"message":"Run approval tool\n```tools\n{\"tool_calls\":[{\"name\":\"approval_required\",\"arguments\":{\"action\":\"deploy\"}}]}\n```"}')

REQS=$(curl -s "$BASE_URL/api/v2/hitl/requests")
REQ_ID=$(echo "$REQS" | python -c "import sys, json; data=json.load(sys.stdin); print(data['requests'][0]['id'] if data['requests'] else '')")

if [ -z "$REQ_ID" ]; then
  echo "No approval request found"
  exit 1
fi

echo "Approving request $REQ_ID"

curl -s -X POST "$BASE_URL/api/v2/hitl/requests/$REQ_ID/resolve" \
  -H "Content-Type: application/json" \
  -d '{"approved": true}'
