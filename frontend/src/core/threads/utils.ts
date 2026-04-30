import type { Message } from "@langchain/langgraph-sdk";

import type { AgentThread } from "./types";

type ThreadContext = { agent_name?: string };
type ThreadLike =
  | string
  | { thread_id: string; context?: ThreadContext; metadata?: ThreadContext };

export function pathOfThread(thread: ThreadLike, context?: ThreadContext) {
  let threadId: string;
  let agentName: string | undefined;

  if (typeof thread === "string") {
    threadId = thread;
    agentName = context?.agent_name;
  } else {
    threadId = thread.thread_id;
    agentName = thread.context?.agent_name ?? thread.metadata?.agent_name;
  }

  if (agentName) {
    return `/workspace/agents/${encodeURIComponent(agentName)}/chats/${threadId}`;
  }
  return `/workspace/chats/${threadId}`;
}

export function textOfMessage(message: Message) {
  if (typeof message.content === "string") {
    return message.content;
  } else if (Array.isArray(message.content)) {
    for (const part of message.content) {
      if (part.type === "text") {
        return part.text;
      }
    }
  }
  return null;
}

export function titleOfThread(thread: AgentThread) {
  return thread.values?.title ?? "Untitled";
}
