import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { loadAdaptersConfig, updateAdaptersConfig } from "./api";
import type { AdaptersConfig } from "./types";

export function useAdaptersConfig() {
  const { data, isLoading, error } = useQuery({
    queryKey: ["adaptersConfig"],
    queryFn: loadAdaptersConfig,
  });
  return { config: data, isLoading, error };
}

export function useUpdateAdapter() {
  const queryClient = useQueryClient();
  const { config } = useAdaptersConfig();

  return useMutation({
    mutationFn: async ({
      adapterName,
      patch,
    }: {
      adapterName: string;
      patch: Partial<AdaptersConfig["adapters"][string]>;
    }) => {
      if (!config) throw new Error("Adapters config not loaded");
      return updateAdaptersConfig({
        adapters: {
          ...config.adapters,
          [adapterName]: {
            ...config.adapters[adapterName]!,
            ...patch,
          },
        },
      });
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["adaptersConfig"] });
    },
  });
}
