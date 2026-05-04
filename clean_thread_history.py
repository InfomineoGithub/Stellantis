"""Repair a LangGraph thread checkpoint to remove invalid message sequences.

Why this script exists
----------------------
DeerFlow stores LangGraph chat history inside ``backend/.deer-flow/checkpoints.db``
(SQLite, ``AsyncSqliteSaver`` schema). When a run is interrupted mid-tool-call,
when an LLM provider truncates a stream, or when a frontend client drops a
turn, the persisted message history can end up with:

* an ``AIMessage`` with ``tool_calls`` that have no matching ``ToolMessage``
  response (dangling tool calls — the next turn will fail with
  "tool_call_id not found"),
* duplicated consecutive ``HumanMessage`` or ``AIMessage`` entries,
* a trailing ``HumanMessage`` (the assistant never replied), or
* orphan ``ToolMessage`` entries whose ``tool_call_id`` does not match any
  prior tool call.

LangGraph cannot resume a thread in those states. This script rewrites the
**latest** checkpoint of a given thread so the message list is well-formed,
and clears pending ``writes`` rows that reference the broken turn. It does
not touch older checkpoints (you can still use LangGraph history to inspect
them), but the resumable head is repaired.

Usage
-----
From the repository root, with the backend virtualenv active::

    # Clean a single thread
    python clean_thread_history.py <thread_id>

    # Dry-run (show what would change without writing)
    python clean_thread_history.py <thread_id> --dry-run

    # Use a non-default DB location
    python clean_thread_history.py <thread_id> --db backend/.deer-flow/checkpoints.db

    # Clean every thread that currently has issues
    python clean_thread_history.py --all
    python clean_thread_history.py --all --dry-run

The script is idempotent: running it again on a clean thread is a no-op.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent
DEFAULT_DB = REPO_ROOT / "backend" / ".deer-flow" / "checkpoints.db"


# ---------------------------------------------------------------------------
# Message classification helpers
# ---------------------------------------------------------------------------


def _msg_kind(m: Any) -> str:
    t = type(m).__name__
    if t in ("HumanMessage", "AIMessage", "ToolMessage", "SystemMessage"):
        return t
    # Fall back to LangChain ``.type`` attribute when available
    typ = getattr(m, "type", "") or ""
    return {
        "human": "HumanMessage",
        "ai": "AIMessage",
        "tool": "ToolMessage",
        "system": "SystemMessage",
    }.get(typ, t)


def _tool_calls(m: Any) -> list[dict]:
    tcs = getattr(m, "tool_calls", None) or []
    out: list[dict] = []
    for tc in tcs:
        if isinstance(tc, dict):
            out.append(tc)
        else:
            out.append(
                {
                    "id": getattr(tc, "id", None),
                    "name": getattr(tc, "name", None),
                    "args": getattr(tc, "args", None),
                }
            )
    return out


def _content_is_empty(m: Any) -> bool:
    c = getattr(m, "content", None)
    if c is None:
        return True
    if isinstance(c, str):
        return c.strip() == ""
    if isinstance(c, list):
        if not c:
            return True
        # All empty text blocks?
        for block in c:
            if isinstance(block, dict):
                txt = block.get("text") or block.get("content") or ""
                if isinstance(txt, str) and txt.strip():
                    return False
            elif isinstance(block, str) and block.strip():
                return False
        return True
    return False


# ---------------------------------------------------------------------------
# Cleaning logic
# ---------------------------------------------------------------------------


@dataclass
class CleanReport:
    original: int = 0
    final: int = 0
    dropped_orphan_tool: int = 0
    injected_tool_responses: int = 0
    dropped_duplicate_human: int = 0
    dropped_duplicate_ai: int = 0
    dropped_trailing_human: int = 0
    dropped_empty_ai: int = 0
    notes: list[str] = field(default_factory=list)

    def changed(self) -> bool:
        return self.original != self.final or any(
            getattr(self, f) > 0
            for f in (
                "dropped_orphan_tool",
                "injected_tool_responses",
                "dropped_duplicate_human",
                "dropped_duplicate_ai",
                "dropped_trailing_human",
                "dropped_empty_ai",
            )
        )

    def summary(self) -> str:
        return (
            f"messages: {self.original} -> {self.final} "
            f"(orphan_tool={self.dropped_orphan_tool}, "
            f"injected_tool_responses={self.injected_tool_responses}, "
            f"dup_human={self.dropped_duplicate_human}, "
            f"dup_ai={self.dropped_duplicate_ai}, "
            f"empty_ai={self.dropped_empty_ai}, "
            f"trailing_human={self.dropped_trailing_human})"
        )


def _make_synthetic_tool_message(tool_call: dict) -> Any:
    """Create a placeholder ToolMessage for a dangling tool call."""
    from langchain_core.messages import ToolMessage

    tcid = tool_call.get("id") or ""
    name = tool_call.get("name") or "unknown_tool"
    return ToolMessage(
        content=(
            "[cleanup] Original tool response was missing or lost. "
            "Synthesized empty result to keep history consistent."
        ),
        tool_call_id=tcid,
        name=name,
        status="error",
    )


def clean_messages(messages: list[Any]) -> tuple[list[Any], CleanReport]:
    """Rewrite a message list so it is well-formed for LangGraph resumption.

    Rules applied in order:
        1. Drop ``ToolMessage`` entries whose ``tool_call_id`` does not match
           any previously seen open tool call (orphan tool messages).
        2. For every ``AIMessage`` with ``tool_calls``, ensure each
           ``tool_call_id`` is followed (within the same tool-call window) by
           a ``ToolMessage``; inject a synthetic placeholder for missing ones.
        3. Collapse consecutive ``HumanMessage`` entries (keep the last).
        4. Drop empty ``AIMessage`` entries that have no content and no
           tool calls when adjacent to another AIMessage.
        5. Drop a trailing ``HumanMessage`` (history must not end with the
           user waiting for a reply that never came).
    """
    report = CleanReport(original=len(messages))

    # Pass 1: walk linearly, keep ToolMessages only if they answer an open call.
    pass1: list[Any] = []
    open_calls: dict[str, dict] = {}  # tcid -> tool_call dict (most recent AI)
    for m in messages:
        kind = _msg_kind(m)
        if kind == "AIMessage":
            tcs = _tool_calls(m)
            if tcs:
                # Reset open call tracking to the new AI's tool_calls
                open_calls = {tc["id"]: tc for tc in tcs if tc.get("id")}
            else:
                open_calls = {}
            pass1.append(m)
        elif kind == "ToolMessage":
            tcid = getattr(m, "tool_call_id", None)
            if tcid and tcid in open_calls:
                pass1.append(m)
                open_calls.pop(tcid, None)
            else:
                report.dropped_orphan_tool += 1
        else:
            # Human / System: clear any expectation of pending tool responses
            # because the agent moved on. We will retroactively inject
            # placeholders below before such messages.
            pass1.append(m)

    # Pass 2: inject synthetic ToolMessages for any still-open tool calls
    # that are followed by a non-Tool message (or end of history).
    pass2: list[Any] = []
    pending: dict[str, dict] = {}
    pending_anchor_idx: int | None = None
    for m in pass1:
        kind = _msg_kind(m)
        if kind == "AIMessage":
            # Before recording a new AI, flush any leftover pending tool calls
            for tc in pending.values():
                pass2.append(_make_synthetic_tool_message(tc))
                report.injected_tool_responses += 1
            pending = {tc["id"]: tc for tc in _tool_calls(m) if tc.get("id")}
            pending_anchor_idx = len(pass2)
            pass2.append(m)
        elif kind == "ToolMessage":
            tcid = getattr(m, "tool_call_id", None)
            if tcid and tcid in pending:
                pending.pop(tcid, None)
            pass2.append(m)
        else:
            # Human/System: flush before
            for tc in pending.values():
                pass2.append(_make_synthetic_tool_message(tc))
                report.injected_tool_responses += 1
            pending = {}
            pending_anchor_idx = None
            pass2.append(m)

    # Flush trailing pending tool calls at end of history
    for tc in pending.values():
        pass2.append(_make_synthetic_tool_message(tc))
        report.injected_tool_responses += 1

    # Pass 3: collapse duplicate consecutive Human messages (keep last).
    pass3: list[Any] = []
    for m in pass2:
        if (
            pass3
            and _msg_kind(m) == "HumanMessage"
            and _msg_kind(pass3[-1]) == "HumanMessage"
        ):
            pass3[-1] = m  # keep the last one
            report.dropped_duplicate_human += 1
        else:
            pass3.append(m)

    # Pass 4: drop empty AIMessages adjacent to another AIMessage.
    pass4: list[Any] = []
    for m in pass3:
        if (
            _msg_kind(m) == "AIMessage"
            and _content_is_empty(m)
            and not _tool_calls(m)
            and pass4
            and _msg_kind(pass4[-1]) == "AIMessage"
        ):
            report.dropped_empty_ai += 1
            continue
        if (
            pass4
            and _msg_kind(m) == "AIMessage"
            and _msg_kind(pass4[-1]) == "AIMessage"
            and _content_is_empty(pass4[-1])
            and not _tool_calls(pass4[-1])
        ):
            # previous AI is empty filler, drop it in favour of current
            pass4[-1] = m
            report.dropped_duplicate_ai += 1
            continue
        pass4.append(m)

    # Pass 5: drop trailing HumanMessage(s).
    pass5 = list(pass4)
    while pass5 and _msg_kind(pass5[-1]) == "HumanMessage":
        pass5.pop()
        report.dropped_trailing_human += 1

    report.final = len(pass5)
    return pass5, report


# ---------------------------------------------------------------------------
# Checkpoint persistence
# ---------------------------------------------------------------------------


async def _list_threads(saver: Any) -> list[str]:
    rows = await saver.conn.execute_fetchall(
        "SELECT DISTINCT thread_id FROM checkpoints"
    )
    return [r[0] for r in rows]


async def _delete_writes(saver: Any, thread_id: str, checkpoint_id: str) -> int:
    cur = await saver.conn.execute(
        "DELETE FROM writes WHERE thread_id=? AND checkpoint_id=?",
        (thread_id, checkpoint_id),
    )
    await saver.conn.commit()
    return cur.rowcount or 0


async def repair_thread(
    saver: Any,
    thread_id: str,
    *,
    dry_run: bool = False,
) -> CleanReport | None:
    config = {"configurable": {"thread_id": thread_id, "checkpoint_ns": ""}}
    tup = await saver.aget_tuple(config)
    if tup is None:
        print(f"[{thread_id}] no checkpoint found")
        return None

    ckpt = tup.checkpoint
    msgs = ckpt.get("channel_values", {}).get("messages", []) or []
    cleaned, report = clean_messages(list(msgs))

    if not report.changed():
        print(f"[{thread_id}] clean — {report.summary()}")
        return report

    print(f"[{thread_id}] repairing — {report.summary()}")
    if dry_run:
        return report

    # Replace messages in place and re-write the same checkpoint id.
    ckpt["channel_values"]["messages"] = cleaned
    metadata = tup.metadata or {}
    write_config = {
        "configurable": {
            "thread_id": thread_id,
            "checkpoint_ns": "",
            "checkpoint_id": ckpt.get("id"),
        }
    }
    # new_versions={} avoids bumping channel versions; INSERT OR REPLACE
    # rewrites the existing row's blob/metadata.
    await saver.aput(write_config, ckpt, metadata, {})

    # Drop pending writes that reference this checkpoint (they may point at
    # tool-calls we just resolved or removed).
    deleted = await _delete_writes(saver, thread_id, ckpt["id"])
    if deleted:
        print(f"[{thread_id}] cleared {deleted} pending writes rows")
    return report


async def _run(args: argparse.Namespace) -> int:
    db_path = Path(args.db).resolve()
    if not db_path.exists():
        print(f"error: database not found: {db_path}", file=sys.stderr)
        return 2

    try:
        from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
    except ImportError:
        print(
            "error: langgraph-checkpoint-sqlite not installed. "
            "Run from the backend venv (uv run python clean_thread_history.py ...).",
            file=sys.stderr,
        )
        return 2

    async with AsyncSqliteSaver.from_conn_string(str(db_path)) as saver:
        await saver.setup()

        if args.all:
            thread_ids = await _list_threads(saver)
            print(f"scanning {len(thread_ids)} thread(s) in {db_path}")
        else:
            thread_ids = [args.thread_id]

        any_changed = False
        for tid in thread_ids:
            rep = await repair_thread(saver, tid, dry_run=args.dry_run)
            if rep and rep.changed():
                any_changed = True

        if args.dry_run:
            print("\n(dry-run — no changes written)")
        elif any_changed:
            print(
                "\nDone. Restart the LangGraph / Gateway server so it reloads the checkpoint."
            )
        return 0


def _parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="clean_thread_history.py",
        description="Repair LangGraph thread checkpoints in DeerFlow's SQLite store.",
    )
    p.add_argument(
        "thread_id",
        nargs="?",
        help="Thread id to clean. Required unless --all is passed.",
    )
    p.add_argument(
        "--all",
        action="store_true",
        help="Scan and repair every thread in the database.",
    )
    p.add_argument(
        "--db",
        default=str(DEFAULT_DB),
        help=f"Path to the checkpoints SQLite file (default: {DEFAULT_DB}).",
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Report what would change without writing.",
    )
    args = p.parse_args(argv)
    if not args.all and not args.thread_id:
        p.error("either provide a thread_id positional argument or pass --all")
    return args


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(list(sys.argv[1:] if argv is None else argv))
    return asyncio.run(_run(args))


if __name__ == "__main__":
    sys.exit(main())
