"""Inspect LangGraph checkpoints.db for thread 05279256-9e78-49ca-8914-4dd3195222cc."""

import sqlite3
from pathlib import Path

DB = Path(__file__).resolve().parent.parent / ".deer-flow" / "checkpoints.db"
THREAD_ID = "05279256-9e78-49ca-8914-4dd3195222cc"

conn = sqlite3.connect(str(DB))
c = conn.cursor()

print("=== Tables ===")
for row in c.execute("SELECT name FROM sqlite_master WHERE type='table'"):
    print(row[0])

print("\n=== checkpoints schema ===")
for row in c.execute("PRAGMA table_info(checkpoints)"):
    print(row)

print("\n=== writes schema ===")
for row in c.execute("PRAGMA table_info(writes)"):
    print(row)

print("\n=== checkpoint count for thread ===")
c.execute("SELECT COUNT(*) FROM checkpoints WHERE thread_id=?", (THREAD_ID,))
print(c.fetchone())

print("\n=== last 10 checkpoints (by checkpoint_id) ===")
for row in c.execute(
    "SELECT checkpoint_id, parent_checkpoint_id, checkpoint_ns FROM checkpoints WHERE thread_id=? ORDER BY checkpoint_id DESC LIMIT 10",
    (THREAD_ID,),
):
    print(row)
