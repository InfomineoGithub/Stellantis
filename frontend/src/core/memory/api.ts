import { getBackendBaseURL } from "../config";
import { fetchWithAuth } from "@/core/api/auth-fetch";

import type { UserMemory } from "./types";

export async function loadMemory() {
  const memory = await fetchWithAuth(`${getBackendBaseURL()}/api/memory`);
  const json = await memory.json();
  return json as UserMemory;
}
