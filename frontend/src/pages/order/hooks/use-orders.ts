import { useCallback } from "react";
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { useSearchParams } from "react-router-dom";
import { useShopFilter } from "@/components/custom/app-shell/hooks/use-shop-filter";
import { api } from "@/lib/api-client";
import type { components } from "@/lib/api-types";
import { queryKeys } from "@/lib/query-keys";
import { useListSort, useSettledSort } from "@/lib/use-list-sort";
import { useQuickFilter } from "@/lib/use-quick-filter";
import { ORDER_QUICK_KEYS, ORDER_SORT_KEYS, PAGE_SIZE, isLocalStatus, type LocalStatus } from "../logic/order-columns";

/** 订单列表：店铺筛选、本地状态、排序、页码都在 URL 里（刷新与分享后保持）；切换筛选或排序回到第 1 页。 */
export function useOrders() {
  const { shopIds } = useShopFilter();
  const [params, setParams] = useSearchParams();
  const sorting = useListSort(ORDER_SORT_KEYS);
  const quick = useQuickFilter(ORDER_QUICK_KEYS);

  const rawStatus = params.get("status");
  const status: LocalStatus | undefined = isLocalStatus(rawStatus) ? rawStatus : undefined;
  const rawPage = Number(params.get("page"));
  const page = Number.isInteger(rawPage) && rawPage >= 1 ? rawPage : 1;

  const update = useCallback(
    (patch: { status?: LocalStatus | null; page?: number }) =>
      setParams((prev) => {
        const next = new URLSearchParams(prev);
        if (patch.status !== undefined) {
          if (patch.status) next.set("status", patch.status);
          else next.delete("status");
          next.delete("page");
        }
        if (patch.page !== undefined) {
          if (patch.page > 1) next.set("page", String(patch.page));
          else next.delete("page");
        }
        return next;
      }),
    [setParams],
  );

  const query = useQuery({
    queryKey: queryKeys.orders(shopIds, { status, page, ...sorting.query, ...quick.query }),
    queryFn: () =>
      api.get<components["schemas"]["OrderPage"]>("/api/orders", {
        shop_ids: shopIds,
        status,
        page,
        page_size: PAGE_SIZE,
        ...sorting.query,
        ...quick.query,
      }),
    placeholderData: keepPreviousData,
  });

  const shownSort = useSettledSort(sorting.sort, !query.isPlaceholderData);
  return {
    query,
    shopIds,
    status,
    page,
    sort: shownSort,
    quick,
    setSort: sorting.setSort,
    setStatus: (s: LocalStatus | undefined) => update({ status: s ?? null }),
    setPage: (p: number) => update({ page: p }),
  };
}
