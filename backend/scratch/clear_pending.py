"""Delete pending writes attached to the target checkpoint."""

import sqlite3
from pathlib import Path

DB = Path(__file__).resolve().parent.parent / ".deer-flow" / "checkpoints.db"
THREAD_ID = "05279256-9e78-49ca-8914-4dd3195222cc"
TARGET = "1f1471d7-8465-6761-82c5-0b32a721b1fe"

conn = sqlite3.connect(str(DB))
c = conn.cursor()
n = c.execute(
    "DELETE FROM writes WHERE thread_id=? AND checkpoint_id=?",
    (THREAD_ID, TARGET),
).rowcount
conn.commit()
print("Deleted pending writes:", n)
conn.close()
