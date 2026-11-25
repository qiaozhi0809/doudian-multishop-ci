import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { useShopFilter } from "@/components/custom/app-shell/hooks/use-shop-filter";
import { ApiError, api } from "@/lib/api-client";
import type { components } from "@/lib/api-types";
import { summarizeSync, type AggregateSyncMessage } from "@/lib/aggregate-sync-message";
import { queryKeys } from "@/lib/query-keys";

type SyncResponse = components["schemas"]["FundSyncResponse"];

/** 手动同步资金（待结算 + 保证金）：同步当前店铺筛选范围，结果就地显示。 */
export function useFundSync() {
  const client = useQueryClient();
  const { shopIds } = useShopFilter();
  const [pending, setPending] = useState(false);
  const [message, setMessage] = useState<AggregateSyncMessage | null>(null);

  const sync = async () => {
    setPending(true);
    setMessage(null);
    try {
      const resp = await api.post<SyncResponse>("/api/fund/sync", undefined, {
        shop_ids: shopIds,
      });
      const notes = resp.shops
        .map((shop) => shop.note)
        .filter((note): note is string => Boolean(note));
      const skipped = resp.shops.filter((shop) => !shop.margin_synced && !shop.error).length;
      const base = summarizeSync(resp.shops, (n) => `${n} 家店资金已同步`);
      const suffix = notes[0] ?? (skipped > 0 ? `${skipped} 家店未同步保证金` : null);
      setMessage(
        suffix && base.tone === "success" ? { tone: "warning", text: `${base.text}；${suffix}` } : base,
      );
      await client.invalidateQueries({ queryKey: queryKeys.fundRoot() });
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
