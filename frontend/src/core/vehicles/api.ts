import { fetchWithAuth } from "@/core/api/auth-fetch";
import { getBackendBaseURL } from "@/core/config";

import type { CreateVehicleInput, UpdateVehicleInput, Vehicle } from "./types";

const BASE = () => `${getBackendBaseURL()}/api/vehicles`;

export async function fetchVehicles(): Promise<Vehicle[]> {
  const res = await fetchWithAuth(BASE());
  if (!res.ok) throw new Error(`Failed to fetch vehicles: ${res.statusText}`);
  return res.json() as Promise<Vehicle[]>;
}

export async function fetchVehicle(id: string): Promise<Vehicle> {
  const res = await fetchWithAuth(`${BASE()}/${id}`);
  if (!res.ok) throw new Error(`Vehicle '${id}' not found`);
  return res.json() as Promise<Vehicle>;
}

export async function fetchVehicleWithSources(id: string): Promise<Vehicle> {
  const res = await fetchWithAuth(`${BASE()}/${id}/with-sources`);
  if (!res.ok) throw new Error(`Vehicle '${id}' not found`);
  return res.json() as Promise<Vehicle>;
}

export async function createVehicle(input: CreateVehicleInput): Promise<Vehicle> {
  const res = await fetchWithAuth(BASE(), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
  });
  if (!res.ok) throw new Error(`Failed to create vehicle: ${res.statusText}`);
  return res.json() as Promise<Vehicle>;
}

export async function updateVehicle(id: string, input: UpdateVehicleInput): Promise<Vehicle> {
  const res = await fetchWithAuth(`${BASE()}/${id}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
  });
  if (!res.ok) throw new Error(`Failed to update vehicle: ${res.statusText}`);
  return res.json() as Promise<Vehicle>;
}

export async function deleteVehicle(id: string): Promise<void> {
  const res = await fetchWithAuth(`${BASE()}/${id}`, { method: "DELETE" });
  if (!res.ok) throw new Error(`Failed to delete vehicle: ${res.statusText}`);
}
