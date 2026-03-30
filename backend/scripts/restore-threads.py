"""Restore LangGraph thread registry from PostgreSQL checkpoints.

This script runs as a Kubernetes init container before `langgraph dev` starts.
It queries the PostgreSQL checkpointer for all distinct threads and rebuilds
the pickle file that `langgraph_runtime_inmem` uses for its thread registry.
"""

import datetime
import os
import pickle
import sys
import uuid

import psycopg


DATABASE_URI = os.environ.get("DATABASE_URI", "")
PICKLE_PATH = os.environ.get("PICKLE_PATH", "/app/backend/.langgraph_api/.langgraph_ops.pckl")


def main():
    if not DATABASE_URI:
        print("DATABASE_URI not set, skipping thread restore")
        sys.exit(0)

    print(f"Connecting to PostgreSQL...")
    try:
        conn = psycopg.connect(DATABASE_URI)
    except Exception as e:
        print(f"Failed to connect to PostgreSQL: {e}")
        sys.exit(1)

    # Get all distinct threads with their latest checkpoint metadata
    rows = conn.execute("""
        SELECT DISTINCT ON (thread_id)
            thread_id, metadata
        FROM checkpoints
        WHERE checkpoint_ns = ''
        ORDER BY thread_id, checkpoint_id DESC
    """).fetchall()
    conn.close()

    print(f"Found {len(rows)} threads in PostgreSQL")

    # Build thread entries matching the langgraph_runtime_inmem pickle format
    now = datetime.datetime.now(datetime.timezone.utc)
    threads = []
    for row in rows:
        thread_id = row[0]
        metadata = row[1] if isinstance(row[1], dict) else {}

        threads.append({
            "thread_id": uuid.UUID(thread_id),
            "created_at": now,
            "updated_at": now,
            "state_updated_at": now,
            "metadata": {},
            "status": "idle",
            "config": {},
            "values": None,
        })

    # Build the full pickle structure
    store = {
        "threads": threads,
        "runs": [],
        "assistants": [],
        "assistant_versions": [],
        "crons": [],
    }

    # Ensure directory exists
    os.makedirs(os.path.dirname(PICKLE_PATH), exist_ok=True)

    with open(PICKLE_PATH, "wb") as f:
        pickle.dump(store, f)

    print(f"Wrote {len(threads)} threads to {PICKLE_PATH}")


if __name__ == "__main__":
    main()
