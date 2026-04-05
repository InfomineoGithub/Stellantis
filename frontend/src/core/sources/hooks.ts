import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { vehicleKeys } from "@/core/vehicles/keys";

import {
  createSource,
  deleteSource,
  fetchSource,
  fetchSources,
  fetchSourceVehicles,
  linkVehicleToSource,
  unlinkVehicleFromSource,
  updateSource,
} from "./api";
import { sourceKeys } from "./keys";
import type { CreateSourceInput, UpdateSourceInput } from "./types";

export function useSources() {
  return useQuery({
    queryKey: sourceKeys.lists(),
    queryFn: () => fetchSources(),
  });
}

export function useSource(id: string | null | undefined) {
  return useQuery({
    queryKey: sourceKeys.detail(id ?? ""),
    queryFn: () => fetchSource(id!),
    enabled: !!id,
  });
}

export function useCreateSource() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: CreateSourceInput) => createSource(input),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: sourceKeys.lists() });
    },
  });
}

export function useUpdateSource() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, input }: { id: string; input: UpdateSourceInput }) =>
      updateSource(id, input),
    onSuccess: (_data, { id }) => {
      void queryClient.invalidateQueries({ queryKey: sourceKeys.detail(id) });
      void queryClient.invalidateQueries({ queryKey: sourceKeys.lists() });
    },
  });
}

export function useDeleteSource() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => deleteSource(id),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: sourceKeys.lists() });
    },
  });
}

export function useSourceVehicles(id: string | null | undefined) {
  return useQuery({
    queryKey: sourceKeys.vehicles(id ?? ""),
    queryFn: () => fetchSourceVehicles(id!),
    enabled: !!id,
  });
}

export function useLinkVehicle() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ sourceId, vehicleId }: { sourceId: string; vehicleId: string }) =>
      linkVehicleToSource(sourceId, vehicleId),
    onSuccess: (_data, { sourceId, vehicleId }) => {
      void queryClient.invalidateQueries({ queryKey: sourceKeys.vehicles(sourceId) });
      void queryClient.invalidateQueries({ queryKey: vehicleKeys.withSources(vehicleId) });
    },
  });
}

export function useUnlinkVehicle() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ sourceId, vehicleId }: { sourceId: string; vehicleId: string }) =>
      unlinkVehicleFromSource(sourceId, vehicleId),
    onSuccess: (_data, { sourceId, vehicleId }) => {
      void queryClient.invalidateQueries({ queryKey: sourceKeys.vehicles(sourceId) });
      void queryClient.invalidateQueries({ queryKey: vehicleKeys.withSources(vehicleId) });
    },
  });
}
