export const sourceKeys = {
  all: (): readonly string[] => ["sources"],
  lists: (): readonly string[] => [...sourceKeys.all(), "list"],
  detail: (id: string): readonly string[] => [
    ...sourceKeys.all(),
    "detail",
    id,
  ],
  vehicles: (id: string): readonly string[] => [
    ...sourceKeys.detail(id),
    "vehicles",
  ],
} as const;
