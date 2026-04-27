"use client";

import {
  Item,
  ItemActions,
  ItemContent,
  ItemDescription,
  ItemTitle,
} from "@/components/ui/item";
import { Switch } from "@/components/ui/switch";
import { useAdaptersConfig, useUpdateAdapter } from "@/core/adapters/hooks";
import type { AdaptersConfig } from "@/core/adapters/types";
import { useI18n } from "@/core/i18n/hooks";
import { useMCPConfig, useEnableMCPServer } from "@/core/mcp/hooks";
import type { MCPServerConfig } from "@/core/mcp/types";
import { env } from "@/env";

import { SettingsSection } from "./settings-section";

export function ToolSettingsPage() {
  const { t } = useI18n();
  const { config, isLoading, error } = useMCPConfig();
  return (
    <SettingsSection
      title={t.settings.tools.title}
      description={t.settings.tools.description}
    >
      {isLoading ? (
        <div className="text-muted-foreground text-sm">{t.common.loading}</div>
      ) : error ? (
        <div>Error: {error.message}</div>
      ) : (
        config && <MCPServerList servers={config.mcp_servers} />
      )}
    </SettingsSection>
  );
}

function MCPServerList({
  servers,
}: {
  servers: Record<string, MCPServerConfig>;
}) {
  const { mutate: enableMCPServer } = useEnableMCPServer();
  const { config: adaptersConfig } = useAdaptersConfig();

  return (
    <div className="flex w-full flex-col gap-4">
      {Object.entries(servers).map(([name, config]) => (
        <div key={name} className="flex flex-col gap-2">
          <Item className="w-full" variant="outline">
            <ItemContent>
              <ItemTitle>
                <div className="flex items-center gap-2">
                  <div>{name}</div>
                </div>
              </ItemTitle>
              <ItemDescription className="line-clamp-4">
                {config.description}
              </ItemDescription>
            </ItemContent>
            <ItemActions>
              <Switch
                checked={config.enabled}
                disabled={env.NEXT_PUBLIC_STATIC_WEBSITE_ONLY === "true"}
                onCheckedChange={(checked) =>
                  enableMCPServer({ serverName: name, enabled: checked })
                }
              />
            </ItemActions>
          </Item>
          {adaptersConfig &&
            Object.entries(adaptersConfig.adapters)
              .filter(([, adapterCfg]) => adapterCfg.wraps_server === name)
              .map(([adapterName, adapterCfg]) => (
                <AdapterCard
                  key={adapterName}
                  adapterName={adapterName}
                  config={adapterCfg}
                />
              ))}
        </div>
      ))}
    </div>
  );
}

function AdapterCard({
  adapterName,
  config,
}: {
  adapterName: string;
  config: AdaptersConfig["adapters"][string];
}) {
  const { t } = useI18n();
  const { mutate: updateAdapter } = useUpdateAdapter();

  return (
    <Item className="ml-4 w-full border-l-2 border-dashed" variant="outline">
      <ItemContent>
        <ItemTitle>
          <div className="flex items-center gap-2">
            <span className="text-muted-foreground text-xs">adapter</span>
            <span>{adapterName}</span>
          </div>
        </ItemTitle>
        <ItemDescription>
          {config.hide_wrapped_tools
            ? t.settings.tools.adapterDescriptionHideRaw
            : t.settings.tools.adapterDescriptionShowRaw}
        </ItemDescription>
      </ItemContent>
      <ItemActions className="flex items-center gap-3">
        <div className="flex items-center gap-1">
          <span className="text-muted-foreground text-xs">
            {t.settings.tools.adapterHideRaw}
          </span>
          <Switch
            checked={config.hide_wrapped_tools}
            onCheckedChange={(checked) =>
              updateAdapter({
                adapterName,
                patch: { hide_wrapped_tools: checked },
              })
            }
          />
        </div>
        <div className="flex items-center gap-1">
          <span className="text-muted-foreground text-xs">
            {t.settings.tools.adapterEnable}
          </span>
          <Switch
            checked={config.enabled}
            onCheckedChange={(checked) =>
              updateAdapter({ adapterName, patch: { enabled: checked } })
            }
          />
        </div>
      </ItemActions>
    </Item>
  );
}
