export const vehicleKeys = {
  all:         (): readonly string[]           => ["vehicles"],
  lists:       (): readonly string[]           => [...vehicleKeys.all(), "list"],
  detail:      (id: string): readonly string[] => [...vehicleKeys.all(), "detail", id],
  withSources: (id: string): readonly string[] => [...vehicleKeys.detail(id), "with-sources"],
} as const;
