import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  createVehicle,
  deleteVehicle,
  fetchVehicle,
  fetchVehicles,
  fetchVehicleWithSources,
  updateVehicle,
} from "./api";
import { vehicleKeys } from "./keys";
import type { CreateVehicleInput, UpdateVehicleInput } from "./types";

export function useVehicles() {
  return useQuery({
    queryKey: vehicleKeys.lists(),
    queryFn: () => fetchVehicles(),
  });
}

export function useVehicle(id: string | null | undefined) {
  return useQuery({
    queryKey: vehicleKeys.detail(id ?? ""),
    queryFn: () => fetchVehicle(id!),
    enabled: !!id,
  });
}

export function useVehicleWithSources(id: string | null | undefined) {
  return useQuery({
    queryKey: vehicleKeys.withSources(id ?? ""),
    queryFn: () => fetchVehicleWithSources(id!),
    enabled: !!id,
  });
}

export function useCreateVehicle() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: CreateVehicleInput) => createVehicle(input),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: vehicleKeys.lists() });
    },
  });
}

export function useUpdateVehicle() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, input }: { id: string; input: UpdateVehicleInput }) =>
      updateVehicle(id, input),
    onSuccess: (_data, { id }) => {
      void queryClient.invalidateQueries({ queryKey: vehicleKeys.detail(id) });
      void queryClient.invalidateQueries({ queryKey: vehicleKeys.lists() });
    },
  });
}

export function useDeleteVehicle() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => deleteVehicle(id),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: vehicleKeys.lists() });
    },
  });
}
