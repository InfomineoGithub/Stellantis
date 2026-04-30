"use client";

import { Client as LangGraphClient } from "@langchain/langgraph-sdk/client";

import { getLangGraphBaseURL } from "../config";

import { getAuthHeaders, clearJwtTokenCache } from "./auth-fetch";
import { sanitizeRunStreamOptions } from "./stream-mode";

function createCompatibleClient(isMock?: boolean): LangGraphClient {
  const client = new LangGraphClient({
    apiUrl: getLangGraphBaseURL(isMock),
    // onRequest is called before every SDK request — the correct extension
    // point for injecting dynamic (async) headers like a JWT Bearer token.
    onRequest: async (_url, init) => {
      const authHeaders = await getAuthHeaders();
      return {
        ...init,
        credentials: "include" as RequestCredentials,
        headers: {
          ...authHeaders,
          ...(init.headers as Record<string, string> | undefined),
        },
      };
    },
  });

  const originalRunStream = client.runs.stream.bind(client.runs);
  client.runs.stream = ((threadId, assistantId, payload) =>
    originalRunStream(
      threadId,
      assistantId,
      sanitizeRunStreamOptions(payload),
    )) as typeof client.runs.stream;

  const originalJoinStream = client.runs.joinStream.bind(client.runs);
  client.runs.joinStream = ((threadId, runId, options) =>
    originalJoinStream(
      threadId,
      runId,
      sanitizeRunStreamOptions(options),
    )) as typeof client.runs.joinStream;

  return client;
}

// Reset singleton when needed (e.g. after sign-out).
export function resetAPIClient(): void {
  _singleton = null;
  // Also clear the cached JWT so the next request fetches a fresh token.
  clearJwtTokenCache();
}

let _singleton: LangGraphClient | null = null;
export function getAPIClient(isMock?: boolean): LangGraphClient {
  _singleton ??= createCompatibleClient(isMock);
  return _singleton;
}
