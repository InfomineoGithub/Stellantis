export interface AdapterConfig {
  enabled: boolean;
  wraps_server: string | null;
  hide_wrapped_tools: boolean;
  tool_mappings: Record<string, string>;
}

export interface AdaptersConfig {
  adapters: Record<string, AdapterConfig>;
}
