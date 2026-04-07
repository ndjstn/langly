## Langly Memory Architecture (Draft)

### Context + goals
- Provide long-lived memory without modifying model weights.
- Capture thought patterns (JJ katas), task outcomes, and research.
- Enable iterative improvement of input/output via notes, summaries, and feedback loops.
- Support lightweight local-first storage with optional graph/vector backends.

### Components
- Zettelkasten Store (file-backed)
  - Markdown body + JSON metadata per note
  - Used for: katas, research notes, system prompts, postmortems
- Memory Routers
  - Decide when to read/write notes based on scope + task type
  - Emit “memory actions” into harness status stream
- Vector/Graph Memory (optional)
  - Vector index for semantic retrieval (future)
  - Neo4j for relationships between notes, tasks, and agents
- Cron Jobs / Offline Workers
  - Summarize runs into notes
  - Refresh domain research via Searx
  - Generate “kata” improvements per agent

### Interfaces (API)
- `GET /api/v2/notes` list notes
- `GET /api/v2/notes/{id}` read note
- `POST /api/v2/notes` create note
- `POST /api/v2/notes/search` search notes

### Data flow
1) Harness classifies scope → Memory router decides actions.
2) Notes created/updated for runs, katas, research.
3) Retrieval injects summaries into prompt enhancement context.
4) Optional vector/graph store tracks links + relationships.

### Risks + mitigations
- Note sprawl → daily “compaction” cron to prune/merge.
- Sensitive data → keep local-only storage + explicit opt-in sync.
- Performance → cap note sizes + limit retrieval count.

### Implementation milestones
1) File-backed Zettelkasten + API endpoints (done)
2) Memory router + harness status events (next)
3) Vector index + Neo4j link sync (future)
4) Cron workers for katas + research refresh (future)
