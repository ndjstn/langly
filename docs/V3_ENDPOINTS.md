# Langly V3 Endpoints (Experimental)

Base path: `/api/v3`

## Workflows
- POST `/workflows/run`
  - body: `{ "message": "...", "session_id": "<uuid>" }`
  - response: `{ "run_id", "session_id", "status", "response" }`

## Runs
- GET `/runs`
  - query: `limit` (default 50)
- GET `/runs/{run_id}`
- GET `/runs/{run_id}/deltas`

## Tools
- GET `/tools`
- POST `/tools/call`
  - body: `{ "name": "...", "arguments": { ... }, "session_id": "<uuid?>", "run_id": "<uuid?>", "actor": "api" }`

## HITL
- GET `/hitl/requests`
  - query: `resolved` (optional)
- POST `/hitl/requests/{request_id}/resolve`
  - response includes `resumed` when an approval resumes a pending tool.

## Events
- WebSocket `/api/v3/ws/deltas`

## Tool Call Format
```tools
{
  "tool_calls": [
    { "name": "echo", "arguments": { "text": "hello" } }
  ]
}
```
## Notes
- V3 uses `runtime_v3.db` by default. Override with `V3_DB_PATH`.
- V3 is a from-scratch runtime and does not share state with v2.
