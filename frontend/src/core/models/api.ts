import { getBackendBaseURL } from "../config";
import { fetchWithAuth } from "@/core/api/auth-fetch";

import type { Model } from "./types";

export async function loadModels() {
  const res = await fetchWithAuth(`${getBackendBaseURL()}/api/models`);
  const { models } = (await res.json()) as { models: Model[] };
  return models;
}
