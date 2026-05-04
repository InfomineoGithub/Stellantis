"""Verify rewind result and inspect remaining writes for the target checkpoint."""

import asyncio
from pathlib import Path

from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

DB = Path(__file__).resolve().parent.parent / ".deer-flow" / "checkpoints.db"
THREAD_ID = "05279256-9e78-49ca-8914-4dd3195222cc"
TARGET = "1f1471d7-8465-6761-82c5-0b32a721b1fe"


async def main():
    async with AsyncSqliteSaver.from_conn_string(str(DB)) as saver:
        config = {"configurable": {"thread_id": THREAD_ID}}
        tup = await saver.aget_tuple(config)
        ckpt = tup.checkpoint
        print(f"Head checkpoint id: {ckpt.get('id')}")
        assert ckpt.get("id") == TARGET
        messages = ckpt.get("channel_values", {}).get("messages", [])
        print(f"Number of messages: {len(messages)}")
        last = messages[-1]
        print(f"Last message type:  {type(last).__name__}")
        content = getattr(last, "content", "")
        if isinstance(content, str):
            tail = content[-300:]
        else:
            tail = str(content)[-300:]
        print(f"Last message tail:  ...{tail}")
        print(f"Last message tool_calls: {getattr(last, 'tool_calls', None)}")
        print("\nPending writes:")
        for w in tup.pending_writes or []:
            print(f"  {w}")


asyncio.run(main())
