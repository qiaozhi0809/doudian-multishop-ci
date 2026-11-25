import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { useShopFilter } from "@/components/custom/app-shell/hooks/use-shop-filter";
import { ApiError, api } from "@/lib/api-client";
import type { components } from "@/lib/api-types";
import { queryKeys } from "@/lib/query-keys";
import { syncMessage } from "../logic/sync-message";

export interface SyncMessage {
  tone: "success" | "info" | "danger";
  text: string;
}

/** 手动同步订单：同步当前店铺筛选范围，结果就地显示。 */
export function useOrderSync() {
  const client = useQueryClient();
  const { shopIds } = useShopFilter();
  const [pending, setPending] = useState(false);
  const [message, setMessage] = useState<SyncMessage | null>(null);

  const sync = async () => {
    setPending(true);
    setMessage(null);
    try {
      const resp = await api.post<components["schemas"]["SyncStarted"]>("/api/orders/sync", undefined, { shop_ids: shopIds });
      setMessage(syncMessage(resp));
      await Promise.all([
        client.invalidateQueries({ queryKey: queryKeys.ordersRoot() }),
        client.invalidateQueries({ queryKey: queryKeys.orderCountsRoot() }),
      ]);
    } catch (e) {
      setMessage({ tone: "danger", text: e instanceof ApiError ? e.message : "同步失败，请确认本地服务正常后重试" });
    } finally {
      setPending(false);
    }
  };

  return { sync, pending, message, dismiss: () => setMessage(null) };
}
