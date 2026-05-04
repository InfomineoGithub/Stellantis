"""Rewind LangGraph thread to a specific checkpoint by deleting all newer checkpoints/writes.

Backs up the DB, then deletes all checkpoints with id > target for the thread, and
deletes any writes attached to those checkpoints.
"""

import shutil
import sqlite3
from datetime import datetime
from pathlib import Path

DB = Path(__file__).resolve().parent.parent / ".deer-flow" / "checkpoints.db"
THREAD_ID = "05279256-9e78-49ca-8914-4dd3195222cc"
TARGET_CHECKPOINT_ID = "1f1471d7-8465-6761-82c5-0b32a721b1fe"

# 1. Backup
backup_path = DB.with_suffix(f".backup-{datetime.now():%Y%m%d-%H%M%S}.db")
shutil.copy2(DB, backup_path)
print(f"Backup written to: {backup_path}")

conn = sqlite3.connect(str(DB))
c = conn.cursor()

# Show current state for thread
c.execute("SELECT COUNT(*) FROM checkpoints WHERE thread_id=?", (THREAD_ID,))
total_before = c.fetchone()[0]
print(f"Total checkpoints for thread (before): {total_before}")

# Verify target exists
c.execute(
    "SELECT 1 FROM checkpoints WHERE thread_id=? AND checkpoint_id=?",
    (THREAD_ID, TARGET_CHECKPOINT_ID),
)
if c.fetchone() is None:
    raise SystemExit(f"Target checkpoint {TARGET_CHECKPOINT_ID} NOT FOUND for thread {THREAD_ID}")
print(f"Target checkpoint exists: {TARGET_CHECKPOINT_ID}")

# Count what will be deleted
c.execute(
    "SELECT COUNT(*) FROM checkpoints WHERE thread_id=? AND checkpoint_id > ?",
    (THREAD_ID, TARGET_CHECKPOINT_ID),
)
n_ckpts_to_delete = c.fetchone()[0]
c.execute(
    "SELECT COUNT(*) FROM writes WHERE thread_id=? AND checkpoint_id > ?",
    (THREAD_ID, TARGET_CHECKPOINT_ID),
)
n_writes_to_delete = c.fetchone()[0]

# Also delete pending writes belonging TO the target checkpoint (so it's clean tail).
c.execute(
    "SELECT COUNT(*) FROM writes WHERE thread_id=? AND checkpoint_id = ?",
    (THREAD_ID, TARGET_CHECKPOINT_ID),
)
n_target_writes = c.fetchone()[0]

print(f"Checkpoints to delete (newer than target): {n_ckpts_to_delete}")
print(f"Writes to delete (newer than target):     {n_writes_to_delete}")
print(f"Writes attached to target checkpoint:     {n_target_writes} (kept)")

# 2. Delete
c.execute(
    "DELETE FROM checkpoints WHERE thread_id=? AND checkpoint_id > ?",
    (THREAD_ID, TARGET_CHECKPOINT_ID),
)
deleted_ckpts = c.rowcount
c.execute(
    "DELETE FROM writes WHERE thread_id=? AND checkpoint_id > ?",
    (THREAD_ID, TARGET_CHECKPOINT_ID),
)
deleted_writes = c.rowcount

conn.commit()

# 3. Verify
c.execute("SELECT COUNT(*) FROM checkpoints WHERE thread_id=?", (THREAD_ID,))
total_after = c.fetchone()[0]
c.execute(
    "SELECT checkpoint_id FROM checkpoints WHERE thread_id=? ORDER BY checkpoint_id DESC LIMIT 1",
    (THREAD_ID,),
)
new_head = c.fetchone()[0]

print(f"\nDeleted {deleted_ckpts} checkpoint rows, {deleted_writes} write rows")
print(f"Total checkpoints for thread (after):  {total_after}")
print(f"New head checkpoint id:                {new_head}")
assert new_head == TARGET_CHECKPOINT_ID, "Head mismatch!"
print("OK — head matches target.")

conn.close()
