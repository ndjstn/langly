#!/bin/bash
set -euo pipefail

BASE_URL=${1:-http://localhost:8000}

curl -s "$BASE_URL/api/v2/health/v2" | jq .
curl -s "$BASE_URL/api/v2/status" | jq .
curl -s "$BASE_URL/api/v2/metrics" | jq .
