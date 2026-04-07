# Langly V2 Endpoints

## Workflows
- POST /api/v2/workflows/run
  - body: { "message": "...", "session_id": "optional" }

## Runs
- GET /api/v2/runs
- GET /api/v2/runs/{run_id}
- GET /api/v2/runs/{run_id}/deltas

## Timeline
- GET /api/v2/timeline/{run_id}
- GET /api/v2/timeline/recent

## Recent
- GET /api/v2/recent/deltas

## Snapshots
- GET /api/v2/snapshots/{session_id}
- GET /api/v2/snapshots/{session_id}/latest

## HITL
- POST /api/v2/hitl/requests
- GET /api/v2/hitl/requests
- GET /api/v2/hitl/requests/{request_id}
- POST /api/v2/hitl/requests/{request_id}/resolve
- GET /api/v2/hitl/pending-tools

## Events
- WS /api/v2/ws/deltas

## Health
- GET /api/v2/health/v2
- GET /api/v2/health/ready
- GET /api/v2/health/live

## Agents
- GET /api/v2/agents
- GET /api/v2/agents/{role}

## Sessions
- GET /api/v2/sessions/{session_id}/runs
- GET /api/v2/sessions/{session_id}/messages
- GET /api/v2/sessions/{session_id}/summary
- POST /api/v2/sessions/{session_id}/clear
- DELETE /api/v2/sessions/runs/{run_id}

## Dashboard
- GET /api/v2/dashboard

## Seed
- POST /api/v2/seed/run

## Status
- GET /api/v2/status

## Config
- GET /api/v2/config

## Overview
- GET /api/v2/overview

## Metrics
- GET /api/v2/metrics

## Reset
- POST /api/v2/reset

## Cleanup
- POST /api/v2/cleanup/prune

## Diagnostics
- GET /api/v2/diagnostics

## Summary
- GET /api/v2/summary

## Models
- GET /api/v2/models

## Neo4j
- GET /api/v2/neo4j

## Tools
- GET /api/v2/tools
- GET /api/v2/tools/{tool_name}

## Docs
- GET /api/v2/docs

## Harness
- POST /api/v2/harness/run
- POST /api/v2/harness/batch

## Files
- GET /api/v2/files/tree
- GET /api/v2/files/read
- POST /api/v2/files/upload

## Notes (Zettelkasten)
- GET /api/v2/notes
- GET /api/v2/notes/{note_id}
- POST /api/v2/notes
- POST /api/v2/notes/search
