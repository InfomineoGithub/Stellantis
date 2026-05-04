"""Find the checkpoint containing the target AI message."""

import asyncio
from pathlib import Path

from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

DB = Path(__file__).resolve().parent.parent / ".deer-flow" / "checkpoints.db"
THREAD_ID = "05279256-9e78-49ca-8914-4dd3195222cc"
TARGET_SUBSTR = "To complete the remaining 130 parameters"


async def main():
    async with AsyncSqliteSaver.from_conn_string(str(DB)) as saver:
        config = {"configurable": {"thread_id": THREAD_ID}}
        # Walk history (latest first)
        count = 0
        target_checkpoint_id = None
        target_parent = None
        async for tup in saver.alist(config):
            count += 1
            ckpt = tup.checkpoint
            messages = ckpt.get("channel_values", {}).get("messages", [])
            if not messages:
                continue
            last = messages[-1]
            ai_content = ""
            msg_type = type(last).__name__
            content = getattr(last, "content", "")
            if isinstance(content, str):
                ai_content = content
            elif isinstance(content, list):
                ai_content = " ".join(p.get("text", "") if isinstance(p, dict) else str(p) for p in content)
            ckpt_id = ckpt.get("id")
            preview = ai_content[-200:].replace("\n", " ") if ai_content else "<no content>"
            tool_calls = getattr(last, "tool_calls", None)
            print(f"[{count}] ckpt={ckpt_id} type={msg_type} tool_calls={bool(tool_calls)} | ...{preview}")
            if TARGET_SUBSTR in ai_content and target_checkpoint_id is None:
                target_checkpoint_id = ckpt_id
                target_parent = tup.parent_config
                print(">>> FOUND TARGET CHECKPOINT <<<")
                print(f"    parent_config: {tup.parent_config}")
                # Show num messages
                print(f"    num messages: {len(messages)}")
            if count >= 30:
                break

        print(f"\nTarget checkpoint id: {target_checkpoint_id}")


asyncio.run(main())
