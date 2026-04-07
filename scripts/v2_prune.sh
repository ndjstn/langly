#!/bin/bash
set -euo pipefail

DB_PATH=${1:-./runtime_v2.db}
MAX_RUNS=${2:-100}

python - <<'PY'
import sqlite3
import sys

path = sys.argv[1]
max_runs = int(sys.argv[2])
conn = sqlite3.connect(path)
cur = conn.cursor()

cur.execute("SELECT id FROM runs ORDER BY created_at DESC")
rows = cur.fetchall()
if len(rows) <= max_runs:
    print("Nothing to prune")
    sys.exit(0)

keep = {row[0] for row in rows[:max_runs]}
prune = [row[0] for row in rows[max_runs:]]

cur.executemany("DELETE FROM runs WHERE id = ?", [(rid,) for rid in prune])
cur.executemany("DELETE FROM run_deltas WHERE run_id = ?", [(rid,) for rid in prune])
conn.commit()
print(f"Pruned {len(prune)} runs")
PY
