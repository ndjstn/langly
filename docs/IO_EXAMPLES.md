# I/O Examples

This page shows concrete request/response examples for the current API surface.
UUIDs and timestamps are placeholders.

## V2: Run a Workflow

Request:

```bash
curl -s http://localhost:8000/api/v2/workflows/run \
  -H "Content-Type: application/json" \
  -d '{"message":"Summarize the repo status"}'
```

Response:

```json
{
  "session_id": "11111111-1111-1111-1111-111111111111",
  "response": "Here is a concise summary...",
  "run_id": "22222222-2222-2222-2222-222222222222",
  "status": "completed"
}
```

## V2: Harness Run (Scope + Trace)

Request:

```bash
curl -s http://localhost:8000/api/v2/harness/run \
  -H "Content-Type: application/json" \
  -d '{"message":"Audit the API surface","auto_tools":["greptile","lint","jj"]}'
```

Response (fields abbreviated):

```json
{
  "run_id": "99999999-9999-9999-9999-999999999999",
  "session_id": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
  "status": "completed",
  "response": "Here is the audit...",
  "scope": {
    "mode": "knowing",
    "intent": "analysis",
    "difficulty": 2,
    "tags": ["api"],
    "requires_tools": ["greptile", "lint", "jj"],
    "summary": "Audit the API surface"
  },
  "tools_used": [
    {"name": "greptile", "status": "ok"},
    {"name": "lint", "status": "ok"},
    {"name": "jj status", "status": "ok"}
  ],
  "trace": {
    "why": "...",
    "how": "...",
    "suggestions": "...",
    "hindsight": "...",
    "foresight": "..."
  },
  "mermaid": "graph TD\\nU[User Input] --> S[Scope] --> R[Response]"
}
```

## V2: List Tools

Request:

```bash
curl -s http://localhost:8000/api/v2/tools
```

Response (schemas abbreviated):

```json
{
  "tools": [
    {
      "name": "echo",
      "description": "Return the provided text.",
      "requires_approval": false,
      "input_schema": {
        "title": "EchoInput",
        "type": "object",
        "properties": {"text": {"title": "Text", "type": "string"}},
        "required": ["text"]
      },
      "output_schema": {
        "title": "ToolOutput",
        "type": "object",
        "properties": {
          "success": {"type": "boolean"},
          "result": {},
          "error": {"type": ["string", "null"]}
        }
      }
    }
  ],
  "total": 2
}
```

## V2: HITL Approval (Create + Resolve)

Create a request:

```bash
curl -s http://localhost:8000/api/v2/hitl/requests \
  -H "Content-Type: application/json" \
  -d '{"prompt":"Approve deploy?","context":{"env":"staging"}}'
```

Response:

```json
{
  "id": "33333333-3333-3333-3333-333333333333",
  "run_id": null,
  "prompt": "Approve deploy?",
  "context": {"env": "staging"},
  "created_at": "2025-01-01T12:00:00Z",
  "resolved": false
}
```

Resolve the request:

```bash
curl -s http://localhost:8000/api/v2/hitl/requests/33333333-3333-3333-3333-333333333333/resolve \
  -H "Content-Type: application/json" \
  -d '{"approved": true, "notes": "ok"}'
```

Response (tool_result included when a pending tool is resumed):

```json
{
  "request_id": "33333333-3333-3333-3333-333333333333",
  "approved": true,
  "notes": "ok",
  "responded_at": "2025-01-01T12:01:00Z",
  "tool_result": {
    "success": true,
    "result": {"action": "deploy"},
    "error": null,
    "metadata": {}
  }
}
```

## V2: WebSocket Delta

Connect:

```
WS /api/v2/ws/deltas
```

Sample message:

```json
{
  "type": "state_delta",
  "delta": {
    "id": "44444444-4444-4444-4444-444444444444",
    "run_id": "22222222-2222-2222-2222-222222222222",
    "node": "router",
    "changes": {"current_agent": "pm"},
    "errors": [],
    "created_at": "2025-01-01T12:00:05Z"
  }
}
```

## V3: Run a Workflow

Request:

```bash
curl -s http://localhost:8000/api/v3/workflows/run \
  -H "Content-Type: application/json" \
  -d '{"message":"Hello from v3"}'
```

Response:

```json
{
  "run_id": "55555555-5555-5555-5555-555555555555",
  "session_id": "66666666-6666-6666-6666-666666666666",
  "status": "completed",
  "response": "v3 response text"
}
```

## V3: Tool Call (Normal)

Request:

```bash
curl -s http://localhost:8000/api/v3/tools/call \
  -H "Content-Type: application/json" \
  -d '{"name":"echo","arguments":{"text":"hi"}}'
```

Response:

```json
{
  "success": true,
  "result": {"text": "hi"},
  "error": null,
  "metadata": {}
}
```

## V3: Tool Call (Approval Required)

Request:

```bash
curl -s http://localhost:8000/api/v3/tools/call \
  -H "Content-Type: application/json" \
  -d '{"name":"approval_required","arguments":{"action":"deploy"}}'
```

Response:

```json
{
  "success": false,
  "result": null,
  "error": "approval_required",
  "metadata": {"request_id": "77777777-7777-7777-7777-777777777777"}
}
```

## V3: HITL Resolve

Request:

```bash
curl -s http://localhost:8000/api/v3/hitl/requests/77777777-7777-7777-7777-777777777777/resolve \
  -H "Content-Type: application/json" \
  -d '{"approved": true}'
```

Response:

```json
{
  "request_id": "77777777-7777-7777-7777-777777777777",
  "approved": true,
  "notes": null,
  "resumed": true
}
```

## V3: WebSocket Delta

Connect:

```
WS /api/v3/ws/deltas
```

Sample message:

```json
{
  "type": "state_delta",
  "delta": {
    "id": "88888888-8888-8888-8888-888888888888",
    "run_id": "55555555-5555-5555-5555-555555555555",
    "node_id": "router",
    "kind": "node_start",
    "changes": {},
    "errors": [],
    "created_at": "2025-01-01T12:00:10Z"
  }
}
```
