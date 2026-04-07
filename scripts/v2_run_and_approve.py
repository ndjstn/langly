#!/usr/bin/env python3
import json
import sys
import urllib.request

base = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000"

payload = {
    "message": "Run approval tool\n```tools\n{\"tool_calls\":[{\"name\":\"approval_required\",\"arguments\":{\"action\":\"deploy\"}}]}\n```",
}

req = urllib.request.Request(
    f"{base}/api/v2/workflows/run",
    data=json.dumps(payload).encode(),
    headers={"Content-Type": "application/json"},
)

urllib.request.urlopen(req).read()

reqs = json.load(urllib.request.urlopen(f"{base}/api/v2/hitl/requests"))
if not reqs.get("requests"):
    print("No approval request found")
    sys.exit(1)

request_id = reqs["requests"][0]["id"]

resolve_req = urllib.request.Request(
    f"{base}/api/v2/hitl/requests/{request_id}/resolve",
    data=json.dumps({"approved": True}).encode(),
    headers={"Content-Type": "application/json"},
)

print(urllib.request.urlopen(resolve_req).read().decode())
