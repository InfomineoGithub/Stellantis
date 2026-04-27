import { getBackendBaseURL } from "@/core/config";
import { fetchWithAuth } from "@/core/api/auth-fetch";
import type { AdaptersConfig } from "./types";

export async function loadAdaptersConfig(): Promise<AdaptersConfig> {
  const response = await fetchWithAuth(
    `${getBackendBaseURL()}/api/adapters/config`,
  );
  return response.json() as Promise<AdaptersConfig>;
}

export async function updateAdaptersConfig(
  config: AdaptersConfig,
): Promise<AdaptersConfig> {
  const response = await fetchWithAuth(
    `${getBackendBaseURL()}/api/adapters/config`,
    {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(config),
    },
  );
  return response.json() as Promise<AdaptersConfig>;
}
