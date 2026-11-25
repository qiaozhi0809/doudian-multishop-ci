import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { useShopFilter } from "@/components/custom/app-shell/hooks/use-shop-filter";
import { ApiError, api } from "@/lib/api-client";
import type { components } from "@/lib/api-types";
import { summarizeSync, type AggregateSyncMessage } from "@/lib/aggregate-sync-message";
import { queryKeys } from "@/lib/query-keys";

type SyncResponse = components["schemas"]["StockSyncResponse"];

/** 手动同步库存快照：同步当前店铺筛选范围，结果就地显示。 */
export function useStockSync() {
  const client = useQueryClient();
  const { shopIds } = useShopFilter();
  const [pending, setPending] = useState(false);
  const [message, setMessage] = useState<AggregateSyncMessage | null>(null);

  const sync = async () => {
    setPending(true);
    setMessage(null);
    try {
      const resp = await api.post<SyncResponse>("/api/catalog/stock/sync", undefined, {
        shop_ids: shopIds,
      });
      const alarm = resp.shops.reduce((sum, shop) => sum + shop.alarm_count, 0);
      setMessage(summarizeSync(resp.shops, (n) => `${n} 家店库存已同步，预警 ${alarm} 个`));
      await client.invalidateQueries({ queryKey: queryKeys.stockRoot() });
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
