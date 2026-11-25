import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { useShopFilter } from "@/components/custom/app-shell/hooks/use-shop-filter";
import { ApiError, api } from "@/lib/api-client";
import type { components } from "@/lib/api-types";
import { summarizeSync, type AggregateSyncMessage } from "@/lib/aggregate-sync-message";
import { queryKeys } from "@/lib/query-keys";

type SyncResponse = components["schemas"]["AftersaleSyncResponse"];

/** 手动同步售后：同步当前店铺筛选范围，结果就地显示。 */
export function useAftersaleSync() {
  const client = useQueryClient();
  const { shopIds } = useShopFilter();
  const [pending, setPending] = useState(false);
  const [message, setMessage] = useState<AggregateSyncMessage | null>(null);

  const sync = async () => {
    setPending(true);
    setMessage(null);
    try {
      const resp = await api.post<SyncResponse>("/api/aftersale/sync", undefined, {
        shop_ids: shopIds,
      });
      setMessage(summarizeSync(resp.shops, (n) => `${n} 家店售后已同步`));
      await client.invalidateQueries({ queryKey: queryKeys.aftersaleRoot() });
    } catch (e) {
      setMessage({
        tone: "danger",
        text: e instanceof ApiError ? e.message : "同步失败，请确认本地服务正常后重试",
      });
    } finally {
      setPending(false);
    }
  };

  return { sync, pending, message, dismiss: () => setMessage(null) };
}
