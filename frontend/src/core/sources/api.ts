import { fetchWithAuth } from "@/core/api/auth-fetch";
import { getBackendBaseURL } from "@/core/config";
import type { Vehicle } from "@/core/vehicles/types";

import type { CreateSourceInput, Source, UpdateSourceInput } from "./types";

const BASE = () => `${getBackendBaseURL()}/api/sources`;

export async function fetchSources(): Promise<Source[]> {
  const res = await fetchWithAuth(BASE());
  if (!res.ok) throw new Error(`Failed to fetch sources: ${res.statusText}`);
  return res.json() as Promise<Source[]>;
}

export async function fetchSource(id: string): Promise<Source> {
  const res = await fetchWithAuth(`${BASE()}/${id}`);
  if (!res.ok) throw new Error(`Source '${id}' not found`);
  return res.json() as Promise<Source>;
}

export async function createSource(input: CreateSourceInput): Promise<Source> {
  const res = await fetchWithAuth(BASE(), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
  });
  if (!res.ok) throw new Error(`Failed to create source: ${res.statusText}`);
  return res.json() as Promise<Source>;
}

export async function updateSource(
  id: string,
  input: UpdateSourceInput,
): Promise<Source> {
  const res = await fetchWithAuth(`${BASE()}/${id}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
  });
  if (!res.ok) throw new Error(`Failed to update source: ${res.statusText}`);
  return res.json() as Promise<Source>;
}

export async function deleteSource(id: string): Promise<void> {
  const res = await fetchWithAuth(`${BASE()}/${id}`, { method: "DELETE" });
  if (!res.ok) throw new Error(`Failed to delete source: ${res.statusText}`);
}

export async function fetchSourceVehicles(id: string): Promise<Vehicle[]> {
  const res = await fetchWithAuth(`${BASE()}/${id}/vehicles`);
  if (!res.ok)
    throw new Error(
      `Failed to fetch vehicles for source '${id}': ${res.statusText}`,
    );
  return res.json() as Promise<Vehicle[]>;
}

export async function linkVehicleToSource(
  sourceId: string,
  vehicleId: string,
): Promise<void> {
  const res = await fetchWithAuth(
    `${BASE()}/${sourceId}/vehicles/${vehicleId}`,
    {
      method: "POST",
    },
  );
  if (!res.ok) throw new Error(`Failed to link vehicle: ${res.statusText}`);
}

export async function unlinkVehicleFromSource(
  sourceId: string,
  vehicleId: string,
): Promise<void> {
  const res = await fetchWithAuth(
    `${BASE()}/${sourceId}/vehicles/${vehicleId}`,
    {
      method: "DELETE",
    },
  );
  if (!res.ok) throw new Error(`Failed to unlink vehicle: ${res.statusText}`);
}
